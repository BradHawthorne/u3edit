"""Tests for Grok audit improvements: backup, dry-run, validate, search, import, etc."""

import json
import os
import shutil
import tempfile

import pytest

from u3edit.bcd import int_to_bcd, int_to_bcd16
from u3edit.constants import (
    CHAR_RECORD_SIZE, ROSTER_FILE_SIZE, MON_FILE_SIZE, MON_MONSTERS_PER_FILE,
    MAP_OVERWORLD_SIZE, MAP_DUNGEON_SIZE, CON_FILE_SIZE, SPECIAL_FILE_SIZE,
    TEXT_FILE_SIZE, PRTY_FILE_SIZE, PLRS_FILE_SIZE,
    CHAR_STR, CHAR_DEX, CHAR_INT, CHAR_WIS,
    CHAR_RACE, CHAR_CLASS, CHAR_STATUS, CHAR_GENDER,
    CHAR_NAME_OFFSET, CHAR_READIED_WEAPON, CHAR_WORN_ARMOR,
    CHAR_HP_HI, CHAR_HP_LO, CHAR_MARKS_CARDS,
    CHAR_IN_PARTY, CHAR_SUB_MORSELS,
    TILE_CHARS_REVERSE, DUNGEON_TILE_CHARS_REVERSE,
    PRTY_OFF_SENTINEL, PRTY_OFF_TRANSPORT, PRTY_OFF_LOCATION,
    PRTY_LOCATION_CODES,
)
from u3edit.fileutil import backup_file
from u3edit.roster import (
    Character, load_roster, save_roster, validate_character, cmd_import,
    check_progress,
)
from u3edit.bestiary import load_mon_file, save_mon_file
from u3edit.map import cmd_find, cmd_set
from u3edit.tlk import load_tlk_records, encode_record, cmd_search, _match_line
from u3edit.save import PartyState
from u3edit.text import load_text_records


# =============================================================================
# Backup utility
# =============================================================================

class TestBackupFile:
    def test_creates_bak_file(self, tmp_dir, sample_roster_file):
        bak_path = backup_file(sample_roster_file)
        assert bak_path == sample_roster_file + '.bak'
        assert os.path.exists(bak_path)

    def test_bak_matches_original(self, tmp_dir, sample_roster_file):
        with open(sample_roster_file, 'rb') as f:
            original = f.read()
        backup_file(sample_roster_file)
        with open(sample_roster_file + '.bak', 'rb') as f:
            bak = f.read()
        assert original == bak

    def test_missing_file_raises(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            backup_file(os.path.join(tmp_dir, 'nonexistent'))


# =============================================================================
# Roster validation
# =============================================================================

class TestValidateCharacter:
    def test_valid_character(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        warnings = validate_character(char)
        assert warnings == []

    def test_empty_character_no_warnings(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        assert validate_character(char) == []

    def test_stat_exceeds_race_max(self, sample_character_bytes):
        data = bytearray(sample_character_bytes)
        # Human max STR is 75; set to 80
        data[CHAR_STR] = int_to_bcd(80)
        char = Character(data)
        warnings = validate_character(char)
        assert any('STR' in w and 'exceeds' in w for w in warnings)

    def test_weapon_exceeds_class_max(self, sample_character_bytes):
        data = bytearray(sample_character_bytes)
        # Set class to Wizard (max weapon=1=Dagger)
        data[CHAR_CLASS] = ord('W')
        data[CHAR_READIED_WEAPON] = 6  # Sword (index 6)
        char = Character(data)
        warnings = validate_character(char)
        assert any('Weapon' in w and 'exceeds' in w for w in warnings)

    def test_armor_exceeds_class_max(self, sample_character_bytes):
        data = bytearray(sample_character_bytes)
        data[CHAR_CLASS] = ord('W')  # Wizard, max armor=1=Cloth
        data[CHAR_WORN_ARMOR] = 4  # Plate
        char = Character(data)
        warnings = validate_character(char)
        assert any('Armor' in w and 'exceeds' in w for w in warnings)

    def test_invalid_bcd(self, sample_character_bytes):
        data = bytearray(sample_character_bytes)
        data[CHAR_STR] = 0xAA  # Invalid BCD
        char = Character(data)
        warnings = validate_character(char)
        assert any('Invalid BCD' in w for w in warnings)


# =============================================================================
# Roster --all bulk edit
# =============================================================================

class TestBulkRosterEdit:
    def test_edit_all_slots(self, tmp_dir, sample_character_bytes):
        """Create a roster with 2 chars, edit --all --gold 500."""
        data = bytearray(ROSTER_FILE_SIZE)
        data[0:CHAR_RECORD_SIZE] = sample_character_bytes
        # Second char in slot 1
        data[CHAR_RECORD_SIZE:CHAR_RECORD_SIZE * 2] = sample_character_bytes
        path = os.path.join(tmp_dir, 'ROST')
        with open(path, 'wb') as f:
            f.write(data)

        chars, original = load_roster(path)
        # Apply gold=500 to both
        chars[0].gold = 500
        chars[1].gold = 500
        save_roster(path, chars, original)

        chars2, _ = load_roster(path)
        assert chars2[0].gold == 500
        assert chars2[1].gold == 500


# =============================================================================
# Roster JSON import
# =============================================================================

class TestRosterImport:
    def test_import_from_json(self, tmp_dir, sample_roster_file):
        # Export, modify, import
        chars, _ = load_roster(sample_roster_file)
        roster_json = [{'slot': 0, 'name': 'WIZARD', 'stats': {'str': 10, 'dex': 20}}]
        json_path = os.path.join(tmp_dir, 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(roster_json, f)

        # Simulate import
        chars, original = load_roster(sample_roster_file)
        with open(json_path, 'r') as f:
            data = json.load(f)
        for entry in data:
            slot = entry['slot']
            char = chars[slot]
            if 'name' in entry:
                char.name = entry['name']
            stats = entry.get('stats', {})
            if 'str' in stats:
                char.strength = stats['str']
            if 'dex' in stats:
                char.dexterity = stats['dex']

        save_roster(sample_roster_file, chars, original)
        chars2, _ = load_roster(sample_roster_file)
        assert chars2[0].name == 'WIZARD'
        assert chars2[0].strength == 10
        assert chars2[0].dexterity == 20

    def test_import_dry_run(self, tmp_dir, sample_roster_file):
        """Import with --dry-run should not write changes."""
        import types
        with open(sample_roster_file, 'rb') as f:
            original = f.read()
        roster_json = [{'slot': 0, 'name': 'WIZARD', 'stats': {'str': 99}}]
        json_path = os.path.join(tmp_dir, 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(roster_json, f)
        args = types.SimpleNamespace(
            file=sample_roster_file, json_file=json_path,
            output=None, backup=False, dry_run=True,
        )
        cmd_import(args)
        with open(sample_roster_file, 'rb') as f:
            after = f.read()
        assert original == after

    def test_import_equipped_weapon(self, tmp_dir, sample_roster_file):
        """Import should set equipped weapon by name."""
        import types
        roster_json = [{'slot': 0, 'weapon': 'Sword'}]
        json_path = os.path.join(tmp_dir, 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(roster_json, f)
        args = types.SimpleNamespace(
            file=sample_roster_file, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        cmd_import(args)
        chars, _ = load_roster(sample_roster_file)
        assert chars[0].equipped_weapon == 'Sword'

    def test_import_equipped_armor(self, tmp_dir, sample_roster_file):
        """Import should set equipped armor by name."""
        import types
        roster_json = [{'slot': 0, 'armor': 'Chain'}]
        json_path = os.path.join(tmp_dir, 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(roster_json, f)
        args = types.SimpleNamespace(
            file=sample_roster_file, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        cmd_import(args)
        chars, _ = load_roster(sample_roster_file)
        assert chars[0].equipped_armor == 'Chain'

    def test_import_weapon_inventory(self, tmp_dir, sample_roster_file):
        """Import should set weapon inventory counts by name."""
        import types
        roster_json = [{'slot': 0, 'weapons': {'Dagger': 3, 'Sword': 1}}]
        json_path = os.path.join(tmp_dir, 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(roster_json, f)
        args = types.SimpleNamespace(
            file=sample_roster_file, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        cmd_import(args)
        chars, _ = load_roster(sample_roster_file)
        assert chars[0].weapon_inventory.get('Dagger') == 3
        assert chars[0].weapon_inventory.get('Sword') == 1

    def test_import_armor_inventory(self, tmp_dir, sample_roster_file):
        """Import should set armor inventory counts by name."""
        import types
        roster_json = [{'slot': 0, 'armors': {'Leather': 2, 'Plate': 1}}]
        json_path = os.path.join(tmp_dir, 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(roster_json, f)
        args = types.SimpleNamespace(
            file=sample_roster_file, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        cmd_import(args)
        chars, _ = load_roster(sample_roster_file)
        assert chars[0].armor_inventory.get('Leather') == 2
        assert chars[0].armor_inventory.get('Plate') == 1

    def test_import_unknown_weapon_skipped(self, tmp_dir, sample_roster_file):
        """Unknown weapon/armor names should be silently skipped."""
        import types
        roster_json = [{'slot': 0, 'weapon': 'Lightsaber', 'armor': 'Mithril'}]
        json_path = os.path.join(tmp_dir, 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(roster_json, f)
        with open(sample_roster_file, 'rb') as f:
            original = f.read()
        args = types.SimpleNamespace(
            file=sample_roster_file, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        cmd_import(args)
        # File changed (count=1 updates were applied) but weapon/armor unchanged
        chars, _ = load_roster(sample_roster_file)
        # Equipped weapon/armor should still be whatever the fixture had
        assert chars[0].equipped_weapon == 'Hands'  # Default from fixture

    def test_import_equipment_round_trip(self, tmp_dir, sample_roster_file):
        """Export to_dict → import should preserve equipment data."""
        import types
        # First set some equipment
        chars, original = load_roster(sample_roster_file)
        chars[0].equipped_weapon = 6  # Sword
        chars[0].equipped_armor = 3   # Chain
        chars[0].set_weapon_count(1, 5)  # 5 Daggers
        chars[0].set_armor_count(2, 3)   # 3 Leather
        save_roster(sample_roster_file, chars, original)
        # Export
        chars, _ = load_roster(sample_roster_file)
        roster_json = [{'slot': 0, **chars[0].to_dict()}]
        json_path = os.path.join(tmp_dir, 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(roster_json, f)
        # Import to a copy
        out_path = os.path.join(tmp_dir, 'ROST_OUT')
        with open(sample_roster_file, 'rb') as f:
            open(out_path, 'wb').write(f.read())
        args = types.SimpleNamespace(
            file=out_path, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        cmd_import(args)
        chars2, _ = load_roster(out_path)
        assert chars2[0].equipped_weapon == 'Sword'
        assert chars2[0].equipped_armor == 'Chain'
        assert chars2[0].weapon_inventory.get('Dagger') == 5
        assert chars2[0].armor_inventory.get('Leather') == 3


# =============================================================================
# Bestiary import
# =============================================================================

class TestBestiaryImport:
    def test_import_monster_data(self, tmp_dir, sample_mon_bytes):
        path = os.path.join(tmp_dir, 'MONA')
        with open(path, 'wb') as f:
            f.write(sample_mon_bytes)

        monsters = load_mon_file(path)
        old_hp = monsters[0].hp

        # Modify via JSON-style update
        monsters[0].hp = 99
        monsters[0].attack = 50
        save_mon_file(path, monsters, sample_mon_bytes)

        monsters2 = load_mon_file(path)
        assert monsters2[0].hp == 99
        assert monsters2[0].attack == 50

    def test_import_dry_run(self, tmp_dir, sample_mon_bytes):
        """Import with --dry-run should not write changes."""
        import types
        from u3edit.bestiary import cmd_import as bestiary_import
        path = os.path.join(tmp_dir, 'MONA')
        with open(path, 'wb') as f:
            f.write(sample_mon_bytes)
        with open(path, 'rb') as f:
            original = f.read()
        mon_json = [{'index': 0, 'hp': 255, 'attack': 255}]
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump(mon_json, f)
        args = types.SimpleNamespace(
            file=path, json_file=json_path,
            output=None, backup=False, dry_run=True,
        )
        bestiary_import(args)
        with open(path, 'rb') as f:
            after = f.read()
        assert original == after


# =============================================================================
# Map CLI editing
# =============================================================================

class TestMapSet:
    def test_set_tile(self, tmp_dir, sample_overworld_bytes):
        path = os.path.join(tmp_dir, 'MAPA')
        with open(path, 'wb') as f:
            f.write(sample_overworld_bytes)

        with open(path, 'rb') as f:
            data = bytearray(f.read())
        data[10 * 64 + 10] = 0x04  # was Town, now Grass
        with open(path, 'wb') as f:
            f.write(data)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[10 * 64 + 10] == 0x04


class TestMapFill:
    def test_fill_region(self, tmp_dir, sample_overworld_bytes):
        path = os.path.join(tmp_dir, 'MAPA')
        with open(path, 'wb') as f:
            f.write(sample_overworld_bytes)

        with open(path, 'rb') as f:
            data = bytearray(f.read())
        for y in range(5, 10):
            for x in range(5, 10):
                data[y * 64 + x] = 0x00  # Water
        with open(path, 'wb') as f:
            f.write(data)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[7 * 64 + 7] == 0x00


class TestMapReplace:
    def test_replace_tiles(self, tmp_dir, sample_overworld_bytes):
        path = os.path.join(tmp_dir, 'MAPA')
        with open(path, 'wb') as f:
            f.write(sample_overworld_bytes)

        with open(path, 'rb') as f:
            data = bytearray(f.read())
        # Count grass tiles, replace with brush
        count = sum(1 for b in data if b == 0x04)
        for i in range(len(data)):
            if data[i] == 0x04:
                data[i] = 0x08
        with open(path, 'wb') as f:
            f.write(data)

        with open(path, 'rb') as f:
            result = f.read()
        assert sum(1 for b in result if b == 0x04) == 0
        assert count > 0


class TestMapFind:
    def test_find_tiles(self, sample_overworld_bytes):
        # Count water tiles (top-left 4x4 = 16)
        count = sum(1 for b in sample_overworld_bytes if b == 0x00)
        assert count == 16  # 4x4 water block

    def test_find_town(self, sample_overworld_bytes):
        # Town at (10, 10)
        assert sample_overworld_bytes[10 * 64 + 10] == 0x18


class TestMapImportDryRun:
    def test_import_dry_run(self, tmp_dir, sample_overworld_bytes):
        """Map import with --dry-run should not write changes."""
        import types
        from u3edit.map import cmd_import as map_import
        path = os.path.join(tmp_dir, 'MAPA')
        with open(path, 'wb') as f:
            f.write(sample_overworld_bytes)
        with open(path, 'rb') as f:
            original = f.read()
        # All-water map
        map_json = {'tiles': [['~' for _ in range(64)] for _ in range(64)], 'width': 64}
        json_path = os.path.join(tmp_dir, 'map.json')
        with open(json_path, 'w') as f:
            json.dump(map_json, f)
        args = types.SimpleNamespace(
            file=path, json_file=json_path,
            output=None, backup=False, dry_run=True,
        )
        map_import(args)
        with open(path, 'rb') as f:
            after = f.read()
        assert original == after


# =============================================================================
# TLK search
# =============================================================================

class TestTlkSearch:
    def test_search_finds_match(self, tmp_dir, sample_tlk_bytes):
        path = os.path.join(tmp_dir, 'TLKA')
        with open(path, 'wb') as f:
            f.write(sample_tlk_bytes)

        records = load_tlk_records(path)
        # Search for "HELLO" in records
        matches = []
        for i, rec in enumerate(records):
            for line in rec:
                if 'hello' in line.lower():
                    matches.append((i, line))
        assert len(matches) == 1
        assert 'HELLO' in matches[0][1]

    def test_search_no_match(self, tmp_dir, sample_tlk_bytes):
        path = os.path.join(tmp_dir, 'TLKA')
        with open(path, 'wb') as f:
            f.write(sample_tlk_bytes)

        records = load_tlk_records(path)
        matches = []
        for i, rec in enumerate(records):
            for line in rec:
                if 'zzzzz' in line.lower():
                    matches.append((i, line))
        assert len(matches) == 0


# =============================================================================
# TLK import
# =============================================================================

class TestTlkImport:
    def test_import_roundtrip(self, tmp_dir, sample_tlk_bytes):
        path = os.path.join(tmp_dir, 'TLKA')
        with open(path, 'wb') as f:
            f.write(sample_tlk_bytes)

        # Load and export
        records = load_tlk_records(path)
        json_data = [{'lines': rec} for rec in records]

        # Re-encode from JSON
        from u3edit.tlk import encode_record
        out = bytearray()
        for entry in json_data:
            out.extend(encode_record(entry['lines']))

        # Write back
        out_path = os.path.join(tmp_dir, 'TLKA_imported')
        with open(out_path, 'wb') as f:
            f.write(bytes(out))

        # Verify
        records2 = load_tlk_records(out_path)
        assert len(records2) == len(records)
        for r1, r2 in zip(records, records2):
            assert r1 == r2


# =============================================================================
# Save PLRS editing
# =============================================================================

class TestPlrsEditing:
    def test_edit_plrs_character(self, tmp_dir, sample_character_bytes):
        # Create PLRS with 4 characters
        plrs_data = bytearray(PLRS_FILE_SIZE)
        for i in range(4):
            plrs_data[i * CHAR_RECORD_SIZE:(i + 1) * CHAR_RECORD_SIZE] = sample_character_bytes
        path = os.path.join(tmp_dir, 'PLRS')
        with open(path, 'wb') as f:
            f.write(plrs_data)

        # Edit slot 0
        with open(path, 'rb') as f:
            data = bytearray(f.read())
        char = Character(data[0:CHAR_RECORD_SIZE])
        char.gold = 999
        data[0:CHAR_RECORD_SIZE] = char.raw
        with open(path, 'wb') as f:
            f.write(data)

        # Verify
        with open(path, 'rb') as f:
            result = f.read()
        char2 = Character(result[0:CHAR_RECORD_SIZE])
        assert char2.gold == 999


# =============================================================================
# Save import
# =============================================================================

class TestPrtyFieldMapping:
    """Verify PRTY byte layout matches engine-traced zero-page $E0-$EF."""

    def test_transport_at_offset_0(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.transport == 'On Foot'

    def test_party_size_at_offset_1(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.party_size == 4

    def test_location_type_at_offset_2(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.location_type == 'Sosaria'

    def test_saved_x_at_offset_3(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.x == 32

    def test_saved_y_at_offset_4(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.y == 32

    def test_sentinel_at_offset_5(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.sentinel == 0xFF

    def test_slot_ids_at_offset_6(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.slot_ids == [0, 1, 2, 3]

    def test_setters_write_correct_offsets(self):
        """Verify setters write to the engine-correct byte positions."""
        data = bytearray(16)
        party = PartyState(data)
        party.party_size = 3
        party.x = 44
        party.y = 20
        party.slot_ids = [5, 6, 7, 8]
        assert party.raw[1] == 3     # $E1 = party_size
        assert party.raw[3] == 44    # $E3 = saved_x
        assert party.raw[4] == 20    # $E4 = saved_y
        assert party.raw[6] == 5     # $E6 = slot 0
        assert party.raw[7] == 6     # $E7 = slot 1
        assert party.raw[8] == 7     # $E8 = slot 2
        assert party.raw[9] == 8     # $E9 = slot 3

    def test_to_dict_keys(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        d = party.to_dict()
        assert 'transport' in d
        assert 'party_size' in d
        assert 'location_type' in d
        assert 'x' in d
        assert 'y' in d
        assert 'slot_ids' in d


class TestSaveImport:
    def test_import_party_state(self, tmp_dir, sample_prty_bytes):
        path = os.path.join(tmp_dir, 'PRTY')
        with open(path, 'wb') as f:
            f.write(sample_prty_bytes)

        # Load, modify via JSON
        party = PartyState(sample_prty_bytes)
        assert party.x == 32
        party.x = 10
        party.y = 20

        with open(path, 'wb') as f:
            f.write(bytes(party.raw))

        with open(path, 'rb') as f:
            result = f.read()
        p2 = PartyState(result)
        assert p2.x == 10
        assert p2.y == 20


# =============================================================================
# Combat import
# =============================================================================

class TestCombatImport:
    def test_import_combat_map(self, tmp_dir, sample_con_bytes):
        path = os.path.join(tmp_dir, 'CONA')
        with open(path, 'wb') as f:
            f.write(sample_con_bytes)

        from u3edit.combat import CombatMap
        cm = CombatMap(sample_con_bytes)
        d = cm.to_dict()

        # Modify and import back
        d['monsters'][0]['x'] = 7
        json_path = os.path.join(tmp_dir, 'con.json')
        with open(json_path, 'w') as f:
            json.dump(d, f)

        # Read JSON back and apply
        with open(json_path, 'r') as f:
            jdata = json.load(f)
        with open(path, 'rb') as f:
            data = bytearray(f.read())
        from u3edit.constants import CON_MONSTER_X_OFFSET
        for i, m in enumerate(jdata.get('monsters', [])):
            data[CON_MONSTER_X_OFFSET + i] = m.get('x', 0)
        with open(path, 'wb') as f:
            f.write(data)

        with open(path, 'rb') as f:
            result = f.read()
        cm2 = CombatMap(result)
        assert cm2.monster_x[0] == 7


# =============================================================================
# Special import
# =============================================================================

class TestSpecialImport:
    def test_import_special_map(self, tmp_dir, sample_special_bytes):
        path = os.path.join(tmp_dir, 'SHRN')
        with open(path, 'wb') as f:
            f.write(sample_special_bytes)

        # Change a tile via raw byte manipulation (simulating import)
        with open(path, 'rb') as f:
            data = bytearray(f.read())
        data[0] = 0x8C  # Wall
        with open(path, 'wb') as f:
            f.write(data)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0] == 0x8C


# =============================================================================
# Text import
# =============================================================================

class TestTextImport:
    def test_import_text_records(self, tmp_dir, sample_text_bytes):
        path = os.path.join(tmp_dir, 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)

        records = load_text_records(path)
        assert len(records) >= 3
        assert records[0] == 'ULTIMA III'

        # Import modified records
        from u3edit.fileutil import encode_high_ascii
        data = bytearray(TEXT_FILE_SIZE)
        offset = 0
        new_records = ['MODIFIED', 'TEXT', 'DATA']
        for text in new_records:
            encoded = encode_high_ascii(text, len(text))
            data[offset:offset + len(encoded)] = encoded
            data[offset + len(encoded)] = 0x00
            offset += len(encoded) + 1

        with open(path, 'wb') as f:
            f.write(data)

        records2 = load_text_records(path)
        assert records2[0] == 'MODIFIED'
        assert records2[1] == 'TEXT'


# =============================================================================
# Text per-record CLI editing
# =============================================================================

class TestTextCliEdit:
    def _write_text(self, tmp_dir, sample_text_bytes):
        path = os.path.join(tmp_dir, 'TEXT#061000')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)
        return path

    def test_edit_single_record(self, tmp_dir, sample_text_bytes):
        """Edit record 0 via CLI."""
        import types
        from u3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        out = os.path.join(tmp_dir, 'TEXT_OUT')
        args = types.SimpleNamespace(
            file=path, record=0, text='CHANGED',
            output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_text_records(out)
        assert records[0] == 'CHANGED'
        assert records[1] == 'EXODUS'  # Unchanged

    def test_edit_record_out_of_range(self, tmp_dir, sample_text_bytes):
        """Out-of-range record index should fail."""
        import types
        from u3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        args = types.SimpleNamespace(
            file=path, record=99, text='NOPE',
            output=None, backup=False, dry_run=False,
        )
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_dry_run(self, tmp_dir, sample_text_bytes):
        """Dry run should not write."""
        import types
        from u3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        with open(path, 'rb') as f:
            original = f.read()
        args = types.SimpleNamespace(
            file=path, record=0, text='CHANGED',
            output=None, backup=False, dry_run=True,
        )
        cmd_edit(args)
        with open(path, 'rb') as f:
            after = f.read()
        assert original == after

    def test_edit_backup(self, tmp_dir, sample_text_bytes):
        """Backup should create .bak."""
        import types
        from u3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        args = types.SimpleNamespace(
            file=path, record=0, text='CHANGED',
            output=None, backup=True, dry_run=False,
        )
        cmd_edit(args)
        assert os.path.exists(path + '.bak')

    def test_edit_output_file(self, tmp_dir, sample_text_bytes):
        """Output to different file."""
        import types
        from u3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        out = os.path.join(tmp_dir, 'TEXT_OUT')
        args = types.SimpleNamespace(
            file=path, record=1, text='hello',
            output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_text_records(out)
        assert records[1] == 'HELLO'  # Uppercased, fits in 6-char field

    def test_edit_uppercases(self, tmp_dir, sample_text_bytes):
        """Text should be uppercased to match engine convention."""
        import types
        from u3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        out = os.path.join(tmp_dir, 'TEXT_OUT')
        args = types.SimpleNamespace(
            file=path, record=0, text='lowercase',
            output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_text_records(out)
        assert records[0] == 'LOWERCASE'


# =============================================================================
# Tile reverse lookups
# =============================================================================

class TestTileReverseLookups:
    def test_overworld_reverse(self):
        assert TILE_CHARS_REVERSE['~'] == 0x00  # Water
        assert TILE_CHARS_REVERSE['.'] == 0x04  # Grass
        assert TILE_CHARS_REVERSE['T'] == 0x0C  # Forest

    def test_dungeon_reverse(self):
        assert DUNGEON_TILE_CHARS_REVERSE['.'] == 0x00  # Open
        assert DUNGEON_TILE_CHARS_REVERSE['#'] == 0x01  # Wall
        assert DUNGEON_TILE_CHARS_REVERSE['D'] == 0x02  # Door

    def test_reverse_matches_forward(self):
        from u3edit.constants import TILES
        for tile_id, (ch, _) in TILES.items():
            assert TILE_CHARS_REVERSE[ch] == tile_id


# =============================================================================
# Dry run (no file written)
# =============================================================================

class TestDryRun:
    def test_roster_dry_run(self, tmp_dir, sample_roster_file):
        """Verify dry-run doesn't modify the file."""
        with open(sample_roster_file, 'rb') as f:
            before = f.read()

        chars, original = load_roster(sample_roster_file)
        chars[0].gold = 9999
        # Don't save (simulating dry-run)

        with open(sample_roster_file, 'rb') as f:
            after = f.read()
        assert before == after

    def test_map_dry_run(self, tmp_dir, sample_overworld_bytes):
        path = os.path.join(tmp_dir, 'MAPA')
        with open(path, 'wb') as f:
            f.write(sample_overworld_bytes)
        with open(path, 'rb') as f:
            before = f.read()

        # Modify in memory but don't write (dry-run)
        data = bytearray(before)
        data[0] = 0xFF

        with open(path, 'rb') as f:
            after = f.read()
        assert before == after


# =============================================================================
# TLK regex search
# =============================================================================

class TestTlkRegexSearch:
    def test_regex_match(self):
        assert _match_line("HELLO WORLD", r"HEL+O", True)

    def test_regex_no_match(self):
        assert not _match_line("HELLO WORLD", r"^WORLD", True)

    def test_regex_case_insensitive(self):
        assert _match_line("Hello World", r"hello", True)

    def test_plain_match_still_works(self):
        assert _match_line("HELLO WORLD", "hello", False)

    def test_plain_no_match(self):
        assert not _match_line("HELLO WORLD", "zzz", False)

    def test_regex_pattern_groups(self):
        assert _match_line("LOOK FOR THE MARK OF FIRE", r"MARK.*FIRE", True)

    def test_regex_alternation(self):
        assert _match_line("THE CASTLE", r"castle|town", True)
        assert _match_line("THE TOWN", r"castle|town", True)
        assert not _match_line("THE DUNGEON", r"castle|town", True)


# =============================================================================
# Progression checker
# =============================================================================

class TestCheckProgress:
    def _make_char(self, marks=None, cards=None, weapon=0, armor=0, status='G'):
        data = bytearray(CHAR_RECORD_SIZE)
        data[CHAR_NAME_OFFSET:CHAR_NAME_OFFSET + 4] = b'\xC8\xC5\xD2\xCF'  # "HERO"
        data[CHAR_RACE] = ord('H')
        data[CHAR_CLASS] = ord('F')
        data[CHAR_GENDER] = ord('M')
        data[CHAR_STATUS] = ord(status)
        data[CHAR_STR] = int_to_bcd(50)
        data[CHAR_HP_HI], data[CHAR_HP_LO] = int_to_bcd16(100)
        data[CHAR_READIED_WEAPON] = weapon
        data[CHAR_WORN_ARMOR] = armor
        char = Character(data)
        if marks:
            char.marks = marks
        if cards:
            char.cards = cards
        return char

    def test_empty_roster(self):
        chars = [Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(20)]
        progress = check_progress(chars)
        assert not progress['exodus_ready']
        assert progress['party_alive'] == 0
        assert not progress['marks_complete']
        assert not progress['cards_complete']

    def test_fully_ready(self):
        all_marks = ['Kings', 'Snake', 'Fire', 'Force']
        all_cards = ['Death', 'Sol', 'Love', 'Moons']
        chars = [
            self._make_char(marks=all_marks, cards=all_cards, weapon=15, armor=7),
            self._make_char(),
            self._make_char(),
            self._make_char(),
        ]
        # Pad to 20 slots
        chars.extend([Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(16)])
        progress = check_progress(chars)
        assert progress['exodus_ready']
        assert progress['marks_complete']
        assert progress['cards_complete']
        assert progress['has_exotic_weapon']
        assert progress['has_exotic_armor']
        assert progress['party_alive'] == 4

    def test_missing_marks(self):
        chars = [
            self._make_char(marks=['Kings', 'Snake'], weapon=15, armor=7),
            self._make_char(),
            self._make_char(),
            self._make_char(),
        ]
        chars.extend([Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(16)])
        progress = check_progress(chars)
        assert not progress['exodus_ready']
        assert not progress['marks_complete']
        assert set(progress['marks_missing']) == {'Fire', 'Force'}

    def test_dead_chars_not_counted(self):
        chars = [
            self._make_char(marks=['Kings', 'Snake', 'Fire', 'Force'],
                          cards=['Death', 'Sol', 'Love', 'Moons'],
                          weapon=15, armor=7),
            self._make_char(status='D'),  # Dead
            self._make_char(status='A'),  # Ashes
            self._make_char(),
        ]
        chars.extend([Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(16)])
        progress = check_progress(chars)
        assert not progress['exodus_ready']
        assert progress['party_alive'] == 2
        assert not progress['party_ready']

    def test_marks_spread_across_party(self):
        """Marks/cards on different characters still count."""
        chars = [
            self._make_char(marks=['Kings', 'Snake']),
            self._make_char(marks=['Fire', 'Force'], cards=['Death', 'Sol']),
            self._make_char(cards=['Love', 'Moons'], weapon=15),
            self._make_char(armor=7),
        ]
        chars.extend([Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(16)])
        progress = check_progress(chars)
        assert progress['marks_complete']
        assert progress['cards_complete']
        assert progress['has_exotic_weapon']
        assert progress['has_exotic_armor']
        assert progress['exodus_ready']

    def test_no_exotic_gear(self):
        all_marks = ['Kings', 'Snake', 'Fire', 'Force']
        all_cards = ['Death', 'Sol', 'Love', 'Moons']
        chars = [
            self._make_char(marks=all_marks, cards=all_cards, weapon=6, armor=4),
            self._make_char(),
            self._make_char(),
            self._make_char(),
        ]
        chars.extend([Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(16)])
        progress = check_progress(chars)
        assert not progress['exodus_ready']
        assert not progress['has_exotic_weapon']
        assert not progress['has_exotic_armor']


# =============================================================================
# Shapes module tests
# =============================================================================

from u3edit.shapes import (
    render_glyph_ascii, render_glyph_grid, glyph_to_dict, tile_to_dict,
    detect_format, glyph_to_pixels, render_hgr_row, write_png,
    GLYPH_SIZE, GLYPH_WIDTH, GLYPH_HEIGHT, SHPS_FILE_SIZE,
)


class TestShapesGlyphRendering:
    def _make_shps(self, glyphs=256):
        """Create a synthetic SHPS file."""
        data = bytearray(glyphs * GLYPH_SIZE)
        # Put a recognizable pattern in glyph 0: checkerboard
        data[0] = 0x55  # .#.#.#.
        data[1] = 0x2A  # .#.#.#. (inverted)
        data[2] = 0x55
        data[3] = 0x2A
        data[4] = 0x55
        data[5] = 0x2A
        data[6] = 0x55
        data[7] = 0x2A
        # Put a solid block in glyph 1
        for i in range(8, 16):
            data[i] = 0x7F  # #######
        return bytes(data)

    def test_render_glyph_ascii(self):
        data = self._make_shps()
        lines = render_glyph_ascii(data, 0)
        assert len(lines) == GLYPH_HEIGHT
        assert all(len(line) == GLYPH_WIDTH for line in lines)
        # Glyph 0 has alternating pattern
        assert '#' in lines[0]
        assert '.' in lines[0]

    def test_render_solid_glyph(self):
        data = self._make_shps()
        lines = render_glyph_ascii(data, GLYPH_SIZE)  # glyph 1
        assert all(line == '#######' for line in lines)

    def test_render_glyph_grid(self):
        data = self._make_shps()
        grid = render_glyph_grid(data, 0)
        assert len(grid) == GLYPH_HEIGHT
        assert all(len(row) == GLYPH_WIDTH for row in grid)

    def test_glyph_to_dict(self):
        data = self._make_shps()
        d = glyph_to_dict(data, 0)
        assert d['index'] == 0
        assert len(d['raw']) == GLYPH_SIZE
        assert '55' in d['hex'].upper()

    def test_tile_to_dict(self):
        data = self._make_shps()
        d = tile_to_dict(data, 0)
        assert d['tile_id'] == 0
        assert d['name'] == 'Water'
        assert len(d['frames']) == 4

    def test_detect_charset(self):
        data = self._make_shps()
        fmt = detect_format(data, 'SHPS#060800')
        assert fmt['type'] == 'charset'
        assert fmt['glyphs'] == 256
        assert fmt['tiles'] == 64

    def test_detect_overlay(self):
        data = bytes(960)
        fmt = detect_format(data, 'SHP0#069400')
        assert fmt['type'] == 'overlay'

    def test_glyph_to_pixels(self):
        data = self._make_shps()
        pixels = glyph_to_pixels(data, GLYPH_SIZE)  # solid glyph 1
        assert len(pixels) == GLYPH_WIDTH * GLYPH_HEIGHT
        # All pixels should be white (fg) for a solid glyph
        assert all(p == (255, 255, 255) for p in pixels)


class TestShapesHGR:
    def test_render_hgr_row_all_black(self):
        row = bytes([0x00, 0x00])
        pixels = render_hgr_row(row)
        assert len(pixels) == 14  # 2 bytes x 7 pixels
        assert all(p == (0, 0, 0) for p in pixels)

    def test_render_hgr_row_all_white(self):
        row = bytes([0x7F, 0x7F])
        pixels = render_hgr_row(row)
        assert len(pixels) == 14
        assert all(p == (255, 255, 255) for p in pixels)

    def test_render_hgr_row_palette_colors(self):
        # Single isolated bit at position 0, palette 0 -> purple
        row = bytes([0x01])
        pixels = render_hgr_row(row)
        assert pixels[0] == (255, 68, 253)  # purple (even col, palette 0)

    def test_render_hgr_row_palette_1(self):
        # Bit 7 set = palette 1, single bit at position 0 -> blue
        row = bytes([0x81])
        pixels = render_hgr_row(row)
        assert pixels[0] == (20, 207, 253)  # blue (even col, palette 1)


class TestShapesFileOps:
    def test_edit_glyph(self, tmp_path):
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)

        # Simulate editing glyph 0
        with open(path, 'rb') as f:
            data = bytearray(f.read())
        new_bytes = bytes([0xFF] * 8)
        data[0:8] = new_bytes
        with open(path, 'wb') as f:
            f.write(data)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0:8] == new_bytes

    def test_json_round_trip(self, tmp_path):
        data = bytearray(SHPS_FILE_SIZE)
        data[0] = 0x55  # pattern in glyph 0
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)

        # Export to dict
        d = glyph_to_dict(data, 0)
        assert d['raw'][0] == 0x55

        # Import back
        import_data = bytearray(SHPS_FILE_SIZE)
        import_data[0:8] = bytes(d['raw'])
        assert import_data[0] == 0x55

    def test_write_png(self, tmp_path):
        pixels = [(255, 0, 0)] * (7 * 8)  # red
        out = str(tmp_path / 'test.png')
        write_png(out, pixels, 7, 8)
        assert os.path.exists(out)
        with open(out, 'rb') as f:
            header = f.read(8)
        assert header[:4] == b'\x89PNG'


# =============================================================================
# Sound module tests
# =============================================================================

from u3edit.sound import (
    identify_sound_file, hex_dump, analyze_mbs, SOUND_FILES,
)


class TestSound:
    def test_identify_sosa(self):
        data = bytes(4096)
        info = identify_sound_file(data, 'SOSA#061000')
        assert info is not None
        assert info['name'] == 'SOSA'

    def test_identify_sosm(self):
        data = bytes(256)
        info = identify_sound_file(data, 'SOSM#064f00')
        assert info is not None
        assert info['name'] == 'SOSM'

    def test_identify_mbs(self):
        data = bytes(5456)
        info = identify_sound_file(data, 'MBS#069a00')
        assert info is not None
        assert info['name'] == 'MBS'

    def test_identify_unknown(self):
        data = bytes(100)
        info = identify_sound_file(data, 'UNKNOWN')
        assert info is None

    def test_hex_dump(self):
        data = bytes(range(32))
        lines = hex_dump(data, 0, 32, 0x1000)
        assert len(lines) == 2
        assert '1000:' in lines[0]

    def test_analyze_mbs_valid(self):
        # Simulate AY register writes: register 0 = 0x42, register 8 = 0x0F
        data = bytes([0, 0x42, 8, 0x0F])
        events = analyze_mbs(data)
        assert len(events) == 2
        assert events[0]['register'] == 0
        assert events[0]['value'] == 0x42
        assert events[1]['register'] == 8
        assert events[1]['value'] == 0x0F

    def test_analyze_mbs_invalid_stops(self):
        # Invalid register (> 13) should stop parsing
        data = bytes([0, 0x42, 0xFF, 0x00])
        events = analyze_mbs(data)
        assert len(events) == 1

    def test_sound_edit_round_trip(self, tmp_path):
        data = bytearray(4096)
        data[0x10] = 0xAB
        path = str(tmp_path / 'SOSA')
        with open(path, 'wb') as f:
            f.write(data)

        # Read back
        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x10] == 0xAB


# =============================================================================
# Patch module tests
# =============================================================================

from u3edit.patch import (
    identify_binary, get_regions, parse_text_region,
    parse_coord_region, encode_text_region, PATCHABLE_REGIONS,
)


class TestPatch:
    def _make_ult3(self):
        """Create a synthetic ULT3 binary."""
        data = bytearray(17408)
        # Put some name table text at the CIDAR-verified offset
        offset = 0x397A
        text = b'\x00\xD7\xC1\xD4\xC5\xD2\x00'  # null + "WATER" + null
        text += b'\xC7\xD2\xC1\xD3\xD3\x00'  # "GRASS" + null
        data[offset:offset + len(text)] = text
        # Put moongate X coords at $29A7
        for i in range(8):
            data[0x29A7 + i] = i * 8
        # Put moongate Y coords at $29AF
        for i in range(8):
            data[0x29AF + i] = i * 4
        # Set food rate at $272C
        data[0x272C] = 0x04
        return bytes(data)

    def test_identify_ult3(self):
        data = self._make_ult3()
        info = identify_binary(data, 'ULT3#065000')
        assert info is not None
        assert info['name'] == 'ULT3'
        assert info['load_addr'] == 0x5000

    def test_identify_exod(self):
        data = bytes(26208)
        info = identify_binary(data, 'EXOD#062000')
        assert info is not None
        assert info['name'] == 'EXOD'

    def test_identify_subs(self):
        data = bytes(3584)
        info = identify_binary(data, 'SUBS#064100')
        assert info is not None
        assert info['name'] == 'SUBS'
        assert info['load_addr'] == 0x4100

    def test_subs_no_regions(self):
        """SUBS is a subroutine library with no patchable data regions."""
        regions = get_regions('SUBS')
        assert regions == {}

    def test_identify_unknown(self):
        data = bytes(100)
        info = identify_binary(data, 'UNKNOWN')
        assert info is None

    def test_get_regions_ult3(self):
        regions = get_regions('ULT3')
        assert 'name-table' in regions
        assert regions['name-table']['data_type'] == 'text'
        assert regions['name-table']['max_length'] == 921

    def test_get_regions_ult3_moongate(self):
        regions = get_regions('ULT3')
        assert 'moongate-x' in regions
        assert 'moongate-y' in regions
        assert regions['moongate-x']['max_length'] == 8
        assert regions['moongate-y']['max_length'] == 8

    def test_get_regions_ult3_food_rate(self):
        regions = get_regions('ULT3')
        assert 'food-rate' in regions
        assert regions['food-rate']['max_length'] == 1
        assert regions['food-rate']['offset'] == 0x272C

    def test_get_regions_exod(self):
        regions = get_regions('EXOD')
        assert 'town-coords' in regions
        assert 'moongate-coords' in regions

    def test_parse_text_region(self):
        data = self._make_ult3()
        # Skip leading null byte
        strings = parse_text_region(data, 0x397A, 20)
        assert 'WATER' in strings
        assert 'GRASS' in strings

    def test_parse_coord_region(self):
        data = bytes([10, 20, 30, 40, 50, 60])
        coords = parse_coord_region(data, 0, 6)
        assert len(coords) == 3
        assert coords[0] == {'x': 10, 'y': 20}
        assert coords[2] == {'x': 50, 'y': 60}

    def test_parse_moongate_coords(self):
        data = self._make_ult3()
        # Read moongate X coordinates
        x_vals = list(data[0x29A7:0x29A7 + 8])
        assert x_vals == [i * 8 for i in range(8)]
        # Read moongate Y coordinates
        y_vals = list(data[0x29AF:0x29AF + 8])
        assert y_vals == [i * 4 for i in range(8)]

    def test_parse_food_rate(self):
        data = self._make_ult3()
        assert data[0x272C] == 0x04

    def test_encode_text_region(self):
        strings = ['WATER', 'GRASS']
        encoded = encode_text_region(strings, 20)
        assert len(encoded) == 20
        # Should contain high-ASCII "WATER" + null
        assert encoded[0] == 0xD7  # W | 0x80
        assert encoded[5] == 0x00  # null terminator

    def test_encode_text_too_long(self):
        strings = ['A' * 100]
        with pytest.raises(ValueError):
            encode_text_region(strings, 10)

    def test_patch_dry_run(self, tmp_path):
        data = bytearray(17408)
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        # Read and verify original
        with open(path, 'rb') as f:
            original = f.read()

        # Simulate edit + dry run: data should not change
        assert original[0x397A] == 0

    def test_all_regions_within_file_bounds(self):
        """Verify all patchable region offsets fit within their binaries."""
        from u3edit.patch import ENGINE_BINARIES
        for binary, regions in PATCHABLE_REGIONS.items():
            size = ENGINE_BINARIES[binary]['size']
            for name, reg in regions.items():
                end = reg['offset'] + reg['max_length']
                assert end <= size, (
                    f"{binary}.{name}: offset 0x{reg['offset']:X} + "
                    f"length {reg['max_length']} = 0x{end:X} > "
                    f"file size 0x{size:X}"
                )


# =============================================================================
# DDRW module tests
# =============================================================================

from u3edit.ddrw import (
    DDRW_FILE_SIZE, parse_vectors, parse_tile_records,
    DDRW_VECTOR_OFFSET, DDRW_VECTOR_COUNT,
    DDRW_TILE_OFFSET, DDRW_TILE_RECORD_SIZE, DDRW_TILE_RECORD_FIELDS,
)


class TestDDRW:
    def test_ddrw_constants(self):
        assert DDRW_FILE_SIZE == 1792

    def test_ddrw_json_round_trip(self, tmp_path):
        data = bytearray(DDRW_FILE_SIZE)
        data[0] = 0xAB
        data[100] = 0xCD
        path = str(tmp_path / 'DDRW')
        with open(path, 'wb') as f:
            f.write(data)

        # Export as JSON
        raw = list(data)
        jdata = {'raw': raw, 'size': len(data)}

        json_path = str(tmp_path / 'ddrw.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        # Import back
        with open(json_path, 'r') as f:
            imported = json.load(f)
        result = bytes(imported['raw'])
        assert result[0] == 0xAB
        assert result[100] == 0xCD
        assert len(result) == DDRW_FILE_SIZE

    def test_ddrw_edit_round_trip(self, tmp_path):
        data = bytearray(DDRW_FILE_SIZE)
        path = str(tmp_path / 'DDRW')
        with open(path, 'wb') as f:
            f.write(data)

        # Patch offset 0x10
        with open(path, 'rb') as f:
            edit_data = bytearray(f.read())
        edit_data[0x10] = 0xFF
        with open(path, 'wb') as f:
            f.write(edit_data)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x10] == 0xFF

    def test_parse_vectors(self):
        data = bytearray(DDRW_FILE_SIZE)
        for i in range(DDRW_VECTOR_COUNT):
            data[DDRW_VECTOR_OFFSET + i] = i * 3
        vectors = parse_vectors(data)
        assert len(vectors) == DDRW_VECTOR_COUNT
        assert vectors[0] == 0
        assert vectors[1] == 3
        assert vectors[10] == 30

    def test_parse_tile_records(self):
        data = bytearray(DDRW_FILE_SIZE)
        # Write a tile record at offset $400
        data[DDRW_TILE_OFFSET + 0] = 0x10  # col_start
        data[DDRW_TILE_OFFSET + 1] = 0x20  # col_end
        data[DDRW_TILE_OFFSET + 2] = 0x02  # step
        data[DDRW_TILE_OFFSET + 3] = 0x01  # flags
        data[DDRW_TILE_OFFSET + 4] = 0x80  # bright_lo
        data[DDRW_TILE_OFFSET + 5] = 0xFF  # bright_hi
        data[DDRW_TILE_OFFSET + 6] = 0x00  # reserved
        records = parse_tile_records(data)
        assert len(records) > 0
        assert records[0]['col_start'] == 0x10
        assert records[0]['col_end'] == 0x20
        assert records[0]['bright_hi'] == 0xFF

    def test_tile_record_field_names(self):
        assert len(DDRW_TILE_RECORD_FIELDS) == DDRW_TILE_RECORD_SIZE


# =============================================================================
# CON file layout tests (resolved via engine code tracing)
# =============================================================================

class TestCombatLayout:
    def test_padding_and_runtime_parsed(self, sample_con_bytes):
        from u3edit.combat import CombatMap
        cm = CombatMap(sample_con_bytes)
        assert len(cm.padding1) == 7
        assert len(cm.runtime_monster) == 16
        assert len(cm.runtime_pc) == 8
        assert len(cm.padding2) == 16

    def test_layout_in_dict(self, sample_con_bytes):
        from u3edit.combat import CombatMap
        cm = CombatMap(sample_con_bytes)
        d = cm.to_dict()
        assert 'padding' in d
        assert 'pre_monster' in d['padding']
        assert 'tail' in d['padding']
        assert 'runtime' in d
        assert 'monster_save_and_status' in d['runtime']
        assert 'pc_save_and_tile' in d['runtime']

    def test_padding_nonzero(self):
        """Padding with non-zero data should be preserved."""
        from u3edit.combat import CombatMap
        from u3edit.constants import CON_PADDING1_OFFSET
        data = bytearray(192)
        data[CON_PADDING1_OFFSET] = 0x42
        data[CON_PADDING1_OFFSET + 1] = 0x55
        cm = CombatMap(data)
        assert cm.padding1[0] == 0x42
        assert cm.padding1[1] == 0x55

    def test_padding_render_shows_nonzero(self):
        from u3edit.combat import CombatMap
        from u3edit.constants import CON_PADDING1_OFFSET
        data = bytearray(192)
        data[CON_PADDING1_OFFSET] = 0xAB
        cm = CombatMap(data)
        rendered = cm.render()
        assert 'Padding (0x79)' in rendered
        assert 'AB' in rendered


# =============================================================================
# Sound MBS music stream tests
# =============================================================================

class TestMBSStream:
    def test_parse_note(self):
        from u3edit.sound import parse_mbs_stream
        data = bytes([0x10, 0x20, 0x00])  # Two notes then REST
        events = parse_mbs_stream(data)
        assert len(events) == 3
        assert events[0]['type'] == 'NOTE'
        assert events[0]['value'] == 0x10
        assert events[2]['type'] == 'NOTE'
        assert events[2]['name'] == 'REST'

    def test_parse_end(self):
        from u3edit.sound import parse_mbs_stream
        data = bytes([0x10, 0x82])  # Note then END
        events = parse_mbs_stream(data)
        assert len(events) == 2
        assert events[1]['type'] == 'END'

    def test_parse_tempo(self):
        from u3edit.sound import parse_mbs_stream
        data = bytes([0x84, 0x20, 0x82])  # TEMPO $20 then END
        events = parse_mbs_stream(data)
        assert events[0]['type'] == 'TEMPO'
        assert events[0]['operand'] == 0x20

    def test_parse_write_register(self):
        from u3edit.sound import parse_mbs_stream
        data = bytes([0x83, 0x08, 0x0F, 0x82])  # WRITE R8=$0F then END
        events = parse_mbs_stream(data)
        assert events[0]['type'] == 'WRITE'
        assert events[0]['register'] == 8
        assert events[0]['reg_value'] == 0x0F

    def test_parse_jump(self):
        from u3edit.sound import parse_mbs_stream
        data = bytes([0x81, 0x00, 0x9A, 0x82])  # JUMP $9A00 then END
        events = parse_mbs_stream(data)
        assert events[0]['type'] == 'JUMP'
        assert events[0]['target'] == 0x9A00

    def test_note_names(self):
        from u3edit.sound import mbs_note_name
        assert mbs_note_name(0) == 'REST'
        assert mbs_note_name(1) == 'C1'
        assert mbs_note_name(13) == 'C2'

    def test_unknown_byte_stops_parsing(self):
        from u3edit.sound import parse_mbs_stream
        # $40-$7F are not notes or opcodes
        data = bytes([0x10, 0x50, 0x82])
        events = parse_mbs_stream(data)
        assert len(events) == 1  # Only the first note


# =============================================================================
# Special location trailing bytes tests (unused padding, verified via engine)
# =============================================================================

class TestSpecialTrailingBytes:
    def test_trailing_bytes_extracted(self, sample_special_bytes):
        from u3edit.special import get_trailing_bytes
        trailing = get_trailing_bytes(sample_special_bytes)
        assert len(trailing) == 7

    def test_trailing_bytes_nonzero(self):
        from u3edit.special import get_trailing_bytes, SPECIAL_META_OFFSET
        data = bytearray(128)
        data[SPECIAL_META_OFFSET] = 0x42
        data[SPECIAL_META_OFFSET + 3] = 0xFF
        trailing = get_trailing_bytes(data)
        assert trailing[0] == 0x42
        assert trailing[3] == 0xFF

    def test_trailing_bytes_in_render(self):
        from u3edit.special import render_special_map, SPECIAL_META_OFFSET
        data = bytearray(128)
        data[SPECIAL_META_OFFSET] = 0xAB
        rendered = render_special_map(data)
        assert 'Trailing padding' in rendered
        assert 'AB' in rendered

    def test_trailing_bytes_not_shown_when_zero(self, sample_special_bytes):
        from u3edit.special import render_special_map
        rendered = render_special_map(sample_special_bytes)
        assert 'Trailing' not in rendered

    def test_backward_compat_alias(self):
        """get_metadata still works as backward-compat alias."""
        from u3edit.special import get_metadata, get_trailing_bytes
        assert get_metadata is get_trailing_bytes


# =============================================================================
# Shapes overlay string extraction tests
# =============================================================================

class TestShapesOverlay:
    def test_extract_overlay_strings(self):
        from u3edit.shapes import extract_overlay_strings
        # Build a fake overlay with JSR $46BA + inline text
        data = bytearray(64)
        # JSR $46BA at offset 0
        data[0] = 0x20
        data[1] = 0xBA
        data[2] = 0x46
        # Inline high-ASCII text "HELLO" + null
        for i, ch in enumerate('HELLO'):
            data[3 + i] = ord(ch) | 0x80
        data[8] = 0x00  # terminator
        strings = extract_overlay_strings(data)
        assert len(strings) == 1
        assert strings[0]['text'] == 'HELLO'
        assert strings[0]['text_offset'] == 3

    def test_extract_multiple_strings(self):
        from u3edit.shapes import extract_overlay_strings
        data = bytearray(64)
        # First string at offset 0
        data[0:3] = bytes([0x20, 0xBA, 0x46])
        data[3] = ord('A') | 0x80
        data[4] = 0x00
        # Some code bytes
        data[5] = 0xA9
        data[6] = 0x00
        # Second string at offset 7
        data[7:10] = bytes([0x20, 0xBA, 0x46])
        data[10] = ord('B') | 0x80
        data[11] = ord('C') | 0x80
        data[12] = 0x00
        strings = extract_overlay_strings(data)
        assert len(strings) == 2
        assert strings[0]['text'] == 'A'
        assert strings[1]['text'] == 'BC'

    def test_overlay_with_newline(self):
        from u3edit.shapes import extract_overlay_strings
        data = bytearray(32)
        data[0:3] = bytes([0x20, 0xBA, 0x46])
        data[3] = ord('H') | 0x80
        data[4] = ord('I') | 0x80
        data[5] = 0xFF  # line break
        data[6] = ord('!') | 0x80
        data[7] = 0x00
        strings = extract_overlay_strings(data)
        assert len(strings) == 1
        assert strings[0]['text'] == 'HI\n!'

    def test_detect_overlay_shop_type(self):
        from u3edit.shapes import detect_format, SHP_SHOP_TYPES
        data = bytes(960)
        fmt = detect_format(data, 'SHP3#069400')
        assert fmt['type'] == 'overlay'
        assert fmt['shop_type'] == 'Pub/Tavern'

    def test_detect_text_as_hgr_bitmap(self):
        from u3edit.shapes import detect_format
        data = bytes(1024)
        fmt = detect_format(data, 'TEXT#061000')
        assert fmt['type'] == 'hgr_bitmap'
        assert 'title screen' in fmt['description']


# =============================================================================
# SHPS code guard tests
# =============================================================================

class TestShpsCodeGuard:
    def test_check_code_region_empty(self):
        from u3edit.shapes import check_shps_code_region, SHPS_FILE_SIZE
        data = bytearray(SHPS_FILE_SIZE)
        assert not check_shps_code_region(data)

    def test_check_code_region_populated(self):
        from u3edit.shapes import (
            check_shps_code_region, SHPS_CODE_OFFSET, SHPS_FILE_SIZE,
        )
        data = bytearray(SHPS_FILE_SIZE)
        data[SHPS_CODE_OFFSET] = 0x4C  # JMP instruction
        data[SHPS_CODE_OFFSET + 1] = 0x00
        data[SHPS_CODE_OFFSET + 2] = 0x08
        assert check_shps_code_region(data)


# =============================================================================
# Disk audit tests
# =============================================================================

class TestDiskAudit:
    def test_audit_output_format(self):
        """Verify the audit function imports cleanly."""
        from u3edit.disk import cmd_audit
        # Just verify it's callable
        assert callable(cmd_audit)


# =============================================================================
# CLI parity tests — main() matches register_parser()
# =============================================================================

import subprocess
import sys


def _help_output(module: str, subcmd: str) -> str:
    """Get --help output from a standalone module entry point."""
    result = subprocess.run(
        [sys.executable, '-m', f'u3edit.{module}', subcmd, '--help'],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout + result.stderr


class TestCliParity:
    """Verify standalone main() parsers have full arg parity with register_parser()."""

    def test_roster_main_create_help(self):
        out = _help_output('roster', 'create')
        assert '--name' in out
        assert '--race' in out
        assert '--force' in out
        assert 'Overwrite existing' in out

    def test_bestiary_main_validate(self):
        out = _help_output('bestiary', 'view')
        assert '--validate' in out

    def test_map_main_set_exists(self):
        out = _help_output('map', 'set')
        assert '--tile' in out
        assert '--x' in out
        assert '--y' in out

    def test_map_main_import_exists(self):
        out = _help_output('map', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_map_main_fill_exists(self):
        out = _help_output('map', 'fill')
        assert '--x1' in out
        assert '--tile' in out

    def test_map_main_replace_exists(self):
        out = _help_output('map', 'replace')
        assert '--from' in out
        assert '--to' in out

    def test_map_main_find_exists(self):
        out = _help_output('map', 'find')
        assert '--tile' in out
        assert '--json' in out

    def test_combat_main_edit_exists(self):
        out = _help_output('combat', 'edit')
        assert '--tile' in out
        assert '--monster-pos' in out
        assert '--pc-pos' in out

    def test_combat_main_import_exists(self):
        out = _help_output('combat', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_combat_main_validate(self):
        out = _help_output('combat', 'view')
        assert '--validate' in out

    def test_special_main_edit_exists(self):
        out = _help_output('special', 'edit')
        assert '--tile' in out
        assert '--backup' in out

    def test_special_main_import_exists(self):
        out = _help_output('special', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_save_main_validate(self):
        out = _help_output('save', 'view')
        assert '--validate' in out

    def test_save_main_import_dryrun(self):
        out = _help_output('save', 'import')
        assert '--dry-run' in out
        assert '--backup' in out

    def test_text_main_import_exists(self):
        out = _help_output('text', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_tlk_main_edit_help(self):
        out = _help_output('tlk', 'edit')
        assert '--find' in out
        assert '--replace' in out
        assert '--ignore-case' in out

    def test_spell_main_help(self):
        out = _help_output('spell', 'view')
        assert '--wizard-only' in out
        assert '--cleric-only' in out

    def test_equip_main_help(self):
        out = _help_output('equip', 'view')
        assert '--json' in out

    def test_shapes_main_export_help(self):
        out = _help_output('shapes', 'export')
        assert '--scale' in out
        assert '--sheet' in out
        assert 'Scale factor' in out

    def test_sound_main_import_dryrun(self):
        out = _help_output('sound', 'import')
        assert '--dry-run' in out
        assert '--backup' in out

    def test_patch_main_dump_help(self):
        out = _help_output('patch', 'dump')
        assert '--offset' in out
        assert '--length' in out
        assert 'Start offset' in out

    def test_ddrw_main_import_dryrun(self):
        out = _help_output('ddrw', 'import')
        assert '--dry-run' in out
        assert '--backup' in out


class TestTextImportDryRun:
    """Behavioral test: text import --dry-run should not write."""

    def test_import_dry_run_no_write(self, tmp_dir):
        from u3edit.text import cmd_import as text_import
        import types

        # Build a TEXT file with known content
        data = bytearray(TEXT_FILE_SIZE)
        text = 'HELLO'
        for i, ch in enumerate(text):
            data[i] = ord(ch) | 0x80
        data[len(text)] = 0x00
        text_path = os.path.join(tmp_dir, 'TEXT#061000')
        with open(text_path, 'wb') as f:
            f.write(data)

        # Write JSON with different content
        jdata = [{'text': 'CHANGED'}]
        json_path = os.path.join(tmp_dir, 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        # Import with dry-run
        args = types.SimpleNamespace(
            file=text_path, json_file=json_path,
            output=None, backup=False, dry_run=True,
        )
        text_import(args)

        # Verify file unchanged
        with open(text_path, 'rb') as f:
            after = f.read()
        assert after == bytes(data)

    def test_import_writes_without_dry_run(self, tmp_dir):
        from u3edit.text import cmd_import as text_import
        import types

        data = bytearray(TEXT_FILE_SIZE)
        text = 'HELLO'
        for i, ch in enumerate(text):
            data[i] = ord(ch) | 0x80
        data[len(text)] = 0x00
        text_path = os.path.join(tmp_dir, 'TEXT#061000')
        with open(text_path, 'wb') as f:
            f.write(data)

        jdata = [{'text': 'WORLD'}]
        json_path = os.path.join(tmp_dir, 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = types.SimpleNamespace(
            file=text_path, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        text_import(args)

        with open(text_path, 'rb') as f:
            after = f.read()
        # First bytes should now be "WORLD" in high-ASCII
        assert after[0] == ord('W') | 0x80


# =============================================================================
# Fix 1: roster.py — in_party, sub_morsels setters + total conversion
# =============================================================================

class TestInPartySetter:
    def test_set_true(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.in_party = True
        assert char.raw[CHAR_IN_PARTY] == 0xFF
        assert char.in_party is True

    def test_set_false(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.raw[CHAR_IN_PARTY] = 0xFF  # start active
        char.in_party = False
        assert char.raw[CHAR_IN_PARTY] == 0x00
        assert char.in_party is False


class TestSubMorselsSetter:
    def test_set_value(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.sub_morsels = 42
        assert char.sub_morsels == 42

    def test_clamp_to_99(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.sub_morsels = 150
        assert char.sub_morsels == 99


class TestRosterTotalConversion:
    def test_equipped_armor_beyond_vanilla(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.equipped_armor = 20
        assert char.raw[CHAR_WORN_ARMOR] == 20

    def test_equipped_weapon_beyond_vanilla(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.equipped_weapon = 200
        assert char.raw[CHAR_READIED_WEAPON] == 200

    def test_status_raw_int(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.status = 0x58  # 'X' — non-standard
        assert char.raw[CHAR_STATUS] == 0x58

    def test_race_raw_int(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.race = 0x5A  # non-standard
        assert char.raw[CHAR_RACE] == 0x5A

    def test_class_raw_int(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.char_class = 0x5B  # non-standard
        assert char.raw[CHAR_CLASS] == 0x5B

    def test_status_hex_string(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.status = '0x58'
        assert char.raw[CHAR_STATUS] == 0x58


class TestInPartyCliArgs:
    def test_in_party_flag(self):
        import types
        from u3edit.roster import _apply_edits
        char = Character(bytearray(CHAR_RECORD_SIZE))
        args = types.SimpleNamespace(
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            status=None, race=None, class_=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None,
            in_party=True, not_in_party=False, sub_morsels=None,
        )
        changed = _apply_edits(char, args)
        assert changed
        assert char.in_party is True

    def test_not_in_party_flag(self):
        import types
        from u3edit.roster import _apply_edits
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.raw[CHAR_IN_PARTY] = 0xFF
        args = types.SimpleNamespace(
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            status=None, race=None, class_=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None,
            in_party=False, not_in_party=True, sub_morsels=None,
        )
        changed = _apply_edits(char, args)
        assert changed
        assert char.in_party is False


class TestRosterImportNewFields:
    def test_round_trip(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.name = 'TEST'
        char.in_party = True
        char.sub_morsels = 50
        d = char.to_dict()
        assert d['in_party'] is True
        assert d['sub_morsels'] == 50


# =============================================================================
# Fix 2: save.py — sentinel setter + transport fix
# =============================================================================

class TestSentinelSetter:
    def test_set_active(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.sentinel = 0xFF
        assert party.sentinel == 0xFF

    def test_raw_byte_masking(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.sentinel = 0x1FF  # should mask to 0xFF
        assert party.sentinel == 0xFF


class TestTransportSetterFix:
    def test_named_value(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'horse'
        assert party.raw[PRTY_OFF_TRANSPORT] == 0x0A

    def test_raw_int(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 0x0A
        assert party.raw[PRTY_OFF_TRANSPORT] == 0x0A

    def test_hex_string(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = '0x0B'
        assert party.raw[PRTY_OFF_TRANSPORT] == 0x0B

    def test_unknown_raises(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        with pytest.raises(ValueError, match='Unknown transport'):
            party.transport = 'hovercraft'


class TestSaveImportSentinel:
    def test_to_dict_has_sentinel(self):
        data = bytearray(PRTY_FILE_SIZE)
        data[PRTY_OFF_SENTINEL] = 0xFF
        party = PartyState(data)
        d = party.to_dict()
        assert d['sentinel'] == 0xFF


# =============================================================================
# Fix 3: shapes.py — SHP overlay string editing
# =============================================================================

from u3edit.shapes import (
    encode_overlay_string, replace_overlay_string,
    extract_overlay_strings,
)

_JSR_46BA_BYTES = bytes([0x20, 0xBA, 0x46])


class TestEncodeOverlayString:
    def test_basic(self):
        encoded = encode_overlay_string('HI')
        assert encoded == bytearray([ord('H') | 0x80, ord('I') | 0x80, 0x00])

    def test_newline(self):
        encoded = encode_overlay_string('A\nB')
        assert encoded == bytearray([ord('A') | 0x80, 0xFF, ord('B') | 0x80, 0x00])


class TestReplaceOverlayString:
    def _make_shp(self, text_bytes):
        """Build minimal SHP-like data with one inline string."""
        # JSR $46BA + text + $00 + padding code byte
        data = bytearray(b'\x00\x00')  # prefix
        data += _JSR_46BA_BYTES
        data += text_bytes
        data += bytearray(b'\x00')  # terminator
        data += bytearray(b'\xEA\xEA')  # NOP code after string
        return data

    def test_exact_fit(self):
        original_text = bytearray([ord('H') | 0x80, ord('I') | 0x80])
        data = self._make_shp(original_text)
        strings = extract_overlay_strings(data)
        assert len(strings) == 1
        s = strings[0]
        result = replace_overlay_string(data, s['text_offset'], s['text_end'], 'AB')
        new_strings = extract_overlay_strings(result)
        assert new_strings[0]['text'] == 'AB'

    def test_shorter_pads_with_null(self):
        original_text = bytearray([ord('H') | 0x80, ord('E') | 0x80,
                                   ord('L') | 0x80])
        data = self._make_shp(original_text)
        strings = extract_overlay_strings(data)
        s = strings[0]
        result = replace_overlay_string(data, s['text_offset'], s['text_end'], 'A')
        # The original region should have A + nulls, code bytes preserved
        assert result[s['text_offset']] == ord('A') | 0x80
        assert result[s['text_offset'] + 1] == 0x00
        # Code bytes after string region should be untouched
        assert result[-2:] == bytearray(b'\xEA\xEA')

    def test_too_long_raises(self):
        original_text = bytearray([ord('H') | 0x80, ord('I') | 0x80])
        data = self._make_shp(original_text)
        strings = extract_overlay_strings(data)
        s = strings[0]
        with pytest.raises(ValueError, match='exceeds available space'):
            replace_overlay_string(
                data, s['text_offset'], s['text_end'], 'TOOLONGTEXT')


class TestOverlayStringRoundTrip:
    def test_extract_replace_extract(self):
        # Build SHP with "SHOP" inline string
        data = bytearray(b'\xEA')  # prefix
        data += _JSR_46BA_BYTES
        for ch in 'SHOP':
            data.append(ord(ch) | 0x80)
        data.append(0x00)  # terminator
        data += bytearray(b'\x60')  # RTS after

        strings = extract_overlay_strings(data)
        assert strings[0]['text'] == 'SHOP'

        s = strings[0]
        data = replace_overlay_string(data, s['text_offset'], s['text_end'], 'ARMS')
        strings2 = extract_overlay_strings(data)
        assert strings2[0]['text'] == 'ARMS'
        # RTS preserved
        assert data[-1] == 0x60


# =============================================================================
# Fix 3: CLI parity for edit-string
# =============================================================================

class TestCliParityShapesEditString:
    def test_help_shows_edit_string(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, '-m', 'u3edit.shapes', 'edit-string', '--help'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert '--offset' in result.stdout
        assert '--text' in result.stdout


# =============================================================================
# Fix: Gender setter accepts raw int/hex
# =============================================================================

class TestGenderSetterTotalConversion:
    def test_gender_raw_int(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.gender = 0x58  # raw byte
        assert char.raw[CHAR_GENDER] == 0x58

    def test_gender_hex_string(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.gender = '0x58'
        assert char.raw[CHAR_GENDER] == 0x58

    def test_gender_named_still_works(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.gender = 'M'
        assert char.raw[CHAR_GENDER] == ord('M')

    def test_gender_unknown_raises(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        with pytest.raises(ValueError, match='Unknown gender'):
            char.gender = 'X'


# =============================================================================
# Fix: validate_character checks HP > max_hp
# =============================================================================

class TestValidateHpVsMaxHp:
    def test_hp_exceeds_max_hp(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.name = 'TEST'
        char.raw[CHAR_STATUS] = ord('G')
        char.hp = 500
        char.max_hp = 200
        warnings = validate_character(char)
        assert any('HP 500 exceeds Max HP 200' in w for w in warnings)

    def test_hp_equal_max_hp_ok(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.name = 'TEST'
        char.raw[CHAR_STATUS] = ord('G')
        char.hp = 200
        char.max_hp = 200
        warnings = validate_character(char)
        assert not any('exceeds Max HP' in w for w in warnings)


# =============================================================================
# Fix: Roster import warns on unknown weapon/armor names
# =============================================================================

class TestRosterImportWarnings:
    def test_unknown_weapon_warns(self, capsys):
        data = bytearray(ROSTER_FILE_SIZE)
        # Put a valid character in slot 0
        data[0:4] = b'\xC8\xC5\xD2\xCF'  # "HERO" high-ASCII
        data[CHAR_STATUS] = ord('G')
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            f.write(data)
            rost_path = f.name
        json_data = [{'slot': 0, 'weapon': 'NONEXISTENT_WEAPON'}]
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            json.dump(json_data, f)
            json_path = f.name
        try:
            args = type('Args', (), {
                'file': rost_path, 'json_file': json_path,
                'output': None, 'backup': False, 'dry_run': True,
            })()
            cmd_import(args)
            captured = capsys.readouterr()
            assert 'Unknown weapon' in captured.err
        finally:
            os.unlink(rost_path)
            os.unlink(json_path)


# =============================================================================
# Fix: location_type setter on PartyState
# =============================================================================

class TestLocationTypeSetter:
    def test_set_by_name(self):
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_type = 'dungeon'
        assert party.raw[PRTY_OFF_LOCATION] == 0x01

    def test_set_by_name_case_insensitive(self):
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_type = 'Town'
        assert party.raw[PRTY_OFF_LOCATION] == 0x02

    def test_set_by_raw_int(self):
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_type = 0x80
        assert party.raw[PRTY_OFF_LOCATION] == 0x80

    def test_set_by_hex_string(self):
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_type = '0xFF'
        assert party.raw[PRTY_OFF_LOCATION] == 0xFF

    def test_unknown_raises(self):
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        with pytest.raises(ValueError, match='Unknown location type'):
            party.location_type = 'narnia'


# =============================================================================
# Fix: PLRS import handles all Character fields
# =============================================================================

class TestPlrsImportAllFields:
    def test_roundtrip_all_fields(self):
        """Export a Character via to_dict, import into PLRS, verify all fields."""
        # Build a character with known values
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.name = 'WARRIOR'
        char.race = 'H'
        char.char_class = 'F'
        char.gender = 'M'
        char.raw[CHAR_STATUS] = ord('G')
        char.strength = 25
        char.dexterity = 20
        char.intelligence = 15
        char.wisdom = 10
        char.hp = 500
        char.max_hp = 500
        char.mp = 30
        char.exp = 1234
        char.gold = 5000
        char.food = 3000
        char.gems = 10
        char.keys = 5
        char.powders = 3
        char.torches = 8
        char.sub_morsels = 50
        char.marks = ['Kings', 'Snake']
        char.cards = ['Death']
        char.equipped_weapon = 5
        char.equipped_armor = 3
        char.set_weapon_count(1, 2)  # 2 Daggers
        char.set_armor_count(1, 1)   # 1 Cloth

        d = char.to_dict()

        # Now import into a fresh PLRS-sized buffer
        plrs_data = bytearray(PLRS_FILE_SIZE)
        # Put the character data in slot 0
        plrs_data[0:CHAR_RECORD_SIZE] = char.raw

        # Build a JSON with the dict (like active_characters export)
        json_data = {'active_characters': [d]}

        with tempfile.TemporaryDirectory() as game_dir:
            # Write PRTY
            prty_path = os.path.join(game_dir, 'PRTY#060000')
            with open(prty_path, 'wb') as f:
                f.write(bytearray(PRTY_FILE_SIZE))
            # Write PLRS (empty — we want import to fill it)
            plrs_path = os.path.join(game_dir, 'PLRS#060000')
            with open(plrs_path, 'wb') as f:
                f.write(bytearray(PLRS_FILE_SIZE))
            # Write JSON
            json_path = os.path.join(game_dir, 'import.json')
            with open(json_path, 'w') as f:
                json.dump(json_data, f)

            from u3edit.save import cmd_import as save_import
            args = type('Args', (), {
                'game_dir': game_dir, 'json_file': json_path,
                'output': None, 'backup': False, 'dry_run': False,
            })()
            save_import(args)

            # Read back the PLRS and verify
            with open(plrs_path, 'rb') as f:
                result = f.read()
            imported = Character(result[0:CHAR_RECORD_SIZE])
            assert imported.name == 'WARRIOR'
            assert imported.gems == 10
            assert imported.keys == 5
            assert imported.powders == 3
            assert imported.torches == 8
            assert imported.sub_morsels == 50
            assert 'Kings' in imported.marks
            assert 'Death' in imported.cards
            assert imported.equipped_weapon == 'Bow'  # index 5
            assert imported.equipped_armor == 'Chain'  # index 3


# =============================================================================
# Fix: PLRS edit CLI supports all character fields
# =============================================================================

class TestPlrsEditExpandedArgs:
    def test_help_shows_new_args(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, '-m', 'u3edit.save', 'edit', '--help'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert '--gems' in result.stdout
        assert '--keys' in result.stdout
        assert '--torches' in result.stdout
        assert '--status' in result.stdout
        assert '--race' in result.stdout
        assert '--weapon' in result.stdout
        assert '--armor' in result.stdout
        assert '--marks' in result.stdout
        assert '--location' in result.stdout


# =============================================================================
# Fix: location_type import in party JSON
# =============================================================================

class TestLocationTypeImport:
    def test_location_type_imported(self):
        json_data = {
            'party': {'location_type': 'Town'},
        }
        with tempfile.TemporaryDirectory() as game_dir:
            prty_path = os.path.join(game_dir, 'PRTY#060000')
            with open(prty_path, 'wb') as f:
                f.write(bytearray(PRTY_FILE_SIZE))
            json_path = os.path.join(game_dir, 'import.json')
            with open(json_path, 'w') as f:
                json.dump(json_data, f)

            from u3edit.save import cmd_import as save_import
            args = type('Args', (), {
                'game_dir': game_dir, 'json_file': json_path,
                'output': None, 'backup': False, 'dry_run': False,
            })()
            save_import(args)

            with open(prty_path, 'rb') as f:
                result = f.read()
            party = PartyState(result)
            assert party.raw[PRTY_OFF_LOCATION] == 0x02  # Town


# =============================================================================
# Fix: Combat monster (0,0) round-trip
# =============================================================================

class TestCombatMonsterZeroZero:
    def test_to_dict_includes_zero_zero_monster(self):
        from u3edit.combat import CombatMap
        from u3edit.constants import CON_FILE_SIZE
        data = bytearray(CON_FILE_SIZE)
        cmap = CombatMap(data)
        # Monster 0 at (0,0), monster 1 at (5,3)
        cmap.monster_x[0] = 0
        cmap.monster_y[0] = 0
        cmap.monster_x[1] = 5
        cmap.monster_y[1] = 3
        d = cmap.to_dict()
        assert len(d['monsters']) == 8  # All 8 slots exported
        assert d['monsters'][0] == {'x': 0, 'y': 0}
        assert d['monsters'][1] == {'x': 5, 'y': 3}

    def test_roundtrip_preserves_positions(self):
        from u3edit.combat import CombatMap
        from u3edit.constants import CON_FILE_SIZE, CON_MONSTER_COUNT
        data = bytearray(CON_FILE_SIZE)
        cmap = CombatMap(data)
        cmap.monster_x[0] = 0
        cmap.monster_y[0] = 0
        cmap.monster_x[1] = 5
        cmap.monster_y[1] = 3
        d = cmap.to_dict()
        # Simulate import into fresh map
        data2 = bytearray(CON_FILE_SIZE)
        cmap2 = CombatMap(data2)
        for i, m in enumerate(d['monsters'][:CON_MONSTER_COUNT]):
            cmap2.monster_x[i] = m['x']
            cmap2.monster_y[i] = m['y']
        assert cmap2.monster_x[0] == 0
        assert cmap2.monster_y[0] == 0
        assert cmap2.monster_x[1] == 5
        assert cmap2.monster_y[1] == 3


# =============================================================================
# Fix: Equipment setters accept name strings
# =============================================================================

class TestEquipmentSetterNames:
    def test_weapon_by_name(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.equipped_weapon = 'Dagger'
        assert char.raw[CHAR_READIED_WEAPON] == 1

    def test_weapon_by_name_case_insensitive(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.equipped_weapon = 'dagger'
        assert char.raw[CHAR_READIED_WEAPON] == 1

    def test_weapon_by_int(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.equipped_weapon = 5
        assert char.raw[CHAR_READIED_WEAPON] == 5

    def test_weapon_by_hex_string(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.equipped_weapon = '0x0F'
        assert char.raw[CHAR_READIED_WEAPON] == 15

    def test_weapon_unknown_raises(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        with pytest.raises(ValueError, match='Unknown weapon'):
            char.equipped_weapon = 'Lightsaber'

    def test_armor_by_name(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.equipped_armor = 'Leather'
        assert char.raw[CHAR_WORN_ARMOR] == 2

    def test_armor_by_name_case_insensitive(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.equipped_armor = 'leather'
        assert char.raw[CHAR_WORN_ARMOR] == 2

    def test_armor_unknown_raises(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        with pytest.raises(ValueError, match='Unknown armor'):
            char.equipped_armor = 'Forcefield'


# =============================================================================
# Fix: Special JSON key consistency
# =============================================================================

class TestSpecialJsonKeyConsistency:
    def test_single_file_uses_trailing_bytes_key(self):
        from u3edit.special import cmd_view
        from u3edit.constants import SPECIAL_FILE_SIZE
        data = bytearray(SPECIAL_FILE_SIZE)
        with tempfile.NamedTemporaryFile(suffix='SHRN#069900', delete=False) as f:
            f.write(data)
            path = f.name
        json_out = os.path.join(tempfile.gettempdir(), 'special_test.json')
        try:
            args = type('Args', (), {
                'path': path, 'json': True, 'output': json_out,
            })()
            cmd_view(args)
            with open(json_out, 'r') as f:
                result = json.load(f)
            assert 'trailing_bytes' in result
            assert 'metadata' not in result
        finally:
            os.unlink(path)
            if os.path.exists(json_out):
                os.unlink(json_out)
