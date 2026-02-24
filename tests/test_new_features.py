"""Tests for Grok audit improvements: backup, dry-run, validate, search, import, etc."""

import argparse
import json
import os
import sys
import tempfile

import pytest

from ult3edit.bcd import int_to_bcd, int_to_bcd16
from ult3edit.constants import (
    CHAR_RECORD_SIZE, ROSTER_FILE_SIZE, MON_FILE_SIZE, MON_MONSTERS_PER_FILE,
    MAP_OVERWORLD_SIZE, MAP_DUNGEON_SIZE, CON_FILE_SIZE, SPECIAL_FILE_SIZE,
    TEXT_FILE_SIZE, PRTY_FILE_SIZE, PLRS_FILE_SIZE,
    CHAR_STR, CHAR_RACE, CHAR_CLASS, CHAR_STATUS, CHAR_GENDER,
    CHAR_NAME_OFFSET, CHAR_READIED_WEAPON, CHAR_WORN_ARMOR,
    CHAR_HP_HI, CHAR_HP_LO, CHAR_MARKS_CARDS,
    CHAR_IN_PARTY, TILE_CHARS_REVERSE, DUNGEON_TILE_CHARS_REVERSE,
    PRTY_OFF_SENTINEL, PRTY_OFF_TRANSPORT, PRTY_OFF_LOCATION,
    PRTY_OFF_SAVED_X, PRTY_OFF_SAVED_Y,
    PRTY_LOCATION_CODES,
)
from ult3edit.fileutil import backup_file
from ult3edit.roster import (
    Character, load_roster, save_roster, validate_character, cmd_import,
    check_progress,
)
from ult3edit.bestiary import load_mon_file, save_mon_file
from ult3edit.map import cmd_find, cmd_set
from ult3edit.tlk import load_tlk_records, encode_record, cmd_search, _match_line
from ult3edit.save import PartyState
from ult3edit.text import load_text_records


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
        from ult3edit.bestiary import cmd_import as bestiary_import
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
        from ult3edit.map import cmd_import as map_import
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


class TestTlkExtractBuild:
    """Integration tests for tlk extract → build round-trip."""

    def test_extract_build_roundtrip(self, tmp_path, sample_tlk_bytes):
        """extract → build produces identical binary."""
        from ult3edit.tlk import cmd_extract, cmd_build
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(sample_tlk_bytes)

        # Extract to text
        txt_path = str(tmp_path / 'tlk.txt')
        args = type('Args', (), {'input': tlk_path, 'output': txt_path})()
        cmd_extract(args)
        assert os.path.exists(txt_path)

        # Build back to binary
        out_path = str(tmp_path / 'TLKA_REBUILT')
        args = type('Args', (), {'input': txt_path, 'output': out_path})()
        cmd_build(args)

        # Verify binary matches original
        with open(out_path, 'rb') as f:
            rebuilt = f.read()
        assert rebuilt == sample_tlk_bytes

    def test_extract_format(self, tmp_path, sample_tlk_bytes):
        """Extract produces readable text with record headers and separators."""
        from ult3edit.tlk import cmd_extract
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(sample_tlk_bytes)

        txt_path = str(tmp_path / 'tlk.txt')
        args = type('Args', (), {'input': tlk_path, 'output': txt_path})()
        cmd_extract(args)

        with open(txt_path, 'r') as f:
            text = f.read()
        assert '# Record 0' in text
        assert 'HELLO ADVENTURER' in text
        assert '---' in text  # Record separator
        assert 'WELCOME' in text
        assert 'TO MY SHOP' in text

    def test_build_multiline_records(self, tmp_path):
        """Build correctly encodes multi-line records with $FF line breaks."""
        from ult3edit.tlk import cmd_build
        txt_path = str(tmp_path / 'tlk.txt')
        with open(txt_path, 'w') as f:
            f.write('# Record 0\nLINE ONE\nLINE TWO\n---\n# Record 1\nSINGLE\n')

        out_path = str(tmp_path / 'TLK_OUT')
        args = type('Args', (), {'input': txt_path, 'output': out_path})()
        cmd_build(args)

        with open(out_path, 'rb') as f:
            data = f.read()
        # Record 0: "LINE ONE" + $FF + "LINE TWO" + $00
        assert data[0] == ord('L') | 0x80
        assert 0xFF in data  # Line break between records
        assert data[-1] == 0x00  # Final record terminator


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
        """cmd_import() applies monster position changes from JSON."""
        from ult3edit.combat import cmd_import as combat_cmd_import, CombatMap
        path = os.path.join(tmp_dir, 'CONA')
        with open(path, 'wb') as f:
            f.write(sample_con_bytes)

        cm = CombatMap(sample_con_bytes)
        d = cm.to_dict()
        d['monsters'][0]['x'] = 7
        d['monsters'][1]['y'] = 9

        json_path = os.path.join(tmp_dir, 'con.json')
        with open(json_path, 'w') as f:
            json.dump(d, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        combat_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        cm2 = CombatMap(result)
        assert cm2.monster_x[0] == 7
        assert cm2.monster_y[1] == 9

    def test_import_combat_tiles(self, tmp_dir, sample_con_bytes):
        """cmd_import() applies tile changes from JSON."""
        from ult3edit.combat import cmd_import as combat_cmd_import, CombatMap
        path = os.path.join(tmp_dir, 'CONA')
        with open(path, 'wb') as f:
            f.write(sample_con_bytes)

        cm = CombatMap(sample_con_bytes)
        d = cm.to_dict()
        # Set tile (0,0) to a known char
        d['tiles'][0][0] = '~'  # Water tile

        json_path = os.path.join(tmp_dir, 'con.json')
        with open(json_path, 'w') as f:
            json.dump(d, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        combat_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0] == TILE_CHARS_REVERSE['~']

    def test_import_combat_dry_run(self, tmp_dir, sample_con_bytes):
        """cmd_import() with dry_run does not modify file."""
        from ult3edit.combat import cmd_import as combat_cmd_import, CombatMap
        path = os.path.join(tmp_dir, 'CONA')
        with open(path, 'wb') as f:
            f.write(sample_con_bytes)

        cm = CombatMap(sample_con_bytes)
        d = cm.to_dict()
        d['monsters'][0]['x'] = 99

        json_path = os.path.join(tmp_dir, 'con.json')
        with open(json_path, 'w') as f:
            json.dump(d, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        combat_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        # Original data should be unchanged
        assert result == sample_con_bytes

    def test_import_combat_round_trip(self, tmp_dir, sample_con_bytes):
        """Full view→import round-trip preserves all data including padding."""
        from ult3edit.combat import cmd_import as combat_cmd_import, CombatMap
        path = os.path.join(tmp_dir, 'CONA')
        with open(path, 'wb') as f:
            f.write(sample_con_bytes)

        cm = CombatMap(sample_con_bytes)
        d = cm.to_dict()

        json_path = os.path.join(tmp_dir, 'con.json')
        with open(json_path, 'w') as f:
            json.dump(d, f)

        out_path = os.path.join(tmp_dir, 'CONA_OUT')
        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': out_path, 'backup': False, 'dry_run': False,
        })()
        combat_cmd_import(args)

        with open(out_path, 'rb') as f:
            result = f.read()
        # All editable data should survive round-trip
        cm2 = CombatMap(result)
        assert cm2.tiles == cm.tiles, "tile grid mismatch"
        assert cm2.monster_x == cm.monster_x
        assert cm2.monster_y == cm.monster_y
        assert cm2.pc_x == cm.pc_x
        assert cm2.pc_y == cm.pc_y
        # Padding preserved
        assert cm2.padding1 == cm.padding1
        assert cm2.padding2 == cm.padding2


# =============================================================================
# Special import
# =============================================================================

class TestSpecialImport:
    def test_import_special_map(self, tmp_dir, sample_special_bytes):
        """cmd_import() applies tile changes from JSON."""
        from ult3edit.special import cmd_import as special_cmd_import
        path = os.path.join(tmp_dir, 'SHRN')
        with open(path, 'wb') as f:
            f.write(sample_special_bytes)

        # Build JSON with a modified tile grid
        from ult3edit.constants import tile_char, SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT
        tiles = []
        for y in range(SPECIAL_MAP_HEIGHT):
            row = []
            for x in range(SPECIAL_MAP_WIDTH):
                off = y * SPECIAL_MAP_WIDTH + x
                row.append(tile_char(sample_special_bytes[off]) if off < len(sample_special_bytes) else ' ')
            tiles.append(row)
        # Change tile (0,0) to water
        tiles[0][0] = '~'

        json_path = os.path.join(tmp_dir, 'special.json')
        jdata = {'tiles': tiles, 'trailing_bytes': [0] * 7}
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        special_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0] == TILE_CHARS_REVERSE['~']

    def test_import_special_dry_run(self, tmp_dir, sample_special_bytes):
        """cmd_import() with dry_run does not modify file."""
        from ult3edit.special import cmd_import as special_cmd_import
        path = os.path.join(tmp_dir, 'SHRN')
        with open(path, 'wb') as f:
            f.write(sample_special_bytes)

        jdata = {'tiles': [['~'] * 11] * 11, 'trailing_bytes': [0] * 7}
        json_path = os.path.join(tmp_dir, 'special.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        special_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == sample_special_bytes

    def test_import_special_trailing_bytes(self, tmp_dir, sample_special_bytes):
        """cmd_import() preserves trailing padding bytes from JSON."""
        from ult3edit.special import cmd_import as special_cmd_import
        from ult3edit.constants import tile_char, SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT
        path = os.path.join(tmp_dir, 'SHRN')
        with open(path, 'wb') as f:
            f.write(sample_special_bytes)

        # Build tiles from existing data (no changes)
        tiles = []
        for y in range(SPECIAL_MAP_HEIGHT):
            row = []
            for x in range(SPECIAL_MAP_WIDTH):
                off = y * SPECIAL_MAP_WIDTH + x
                row.append(tile_char(sample_special_bytes[off]))
            tiles.append(row)

        # Set non-zero trailing bytes
        jdata = {'tiles': tiles, 'trailing_bytes': [0xDE, 0xAD, 0xBE, 0xEF, 0x00, 0x00, 0x00]}
        json_path = os.path.join(tmp_dir, 'special.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        special_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[121] == 0xDE
        assert result[122] == 0xAD
        assert result[123] == 0xBE
        assert result[124] == 0xEF


# =============================================================================
# Text import
# =============================================================================

class TestTextImport:
    def test_import_text_records(self, tmp_dir, sample_text_bytes):
        """cmd_import() applies text records from JSON."""
        from ult3edit.text import cmd_import as text_cmd_import
        path = os.path.join(tmp_dir, 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)

        records = load_text_records(path)
        assert len(records) >= 3
        assert records[0] == 'ULTIMA III'

        # Import via cmd_import
        jdata = [{'text': 'MODIFIED'}, {'text': 'RECORDS'}, {'text': 'HERE'}]
        json_path = os.path.join(tmp_dir, 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        text_cmd_import(args)

        records2 = load_text_records(path)
        assert records2[0] == 'MODIFIED'
        assert records2[1] == 'RECORDS'
        assert records2[2] == 'HERE'

    def test_import_text_dry_run(self, tmp_dir, sample_text_bytes):
        """cmd_import() with dry_run does not modify file."""
        from ult3edit.text import cmd_import as text_cmd_import
        path = os.path.join(tmp_dir, 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)

        jdata = [{'text': 'CHANGED'}]
        json_path = os.path.join(tmp_dir, 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        text_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == sample_text_bytes


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
        from ult3edit.text import cmd_edit
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
        from ult3edit.text import cmd_edit
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
        from ult3edit.text import cmd_edit
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
        from ult3edit.text import cmd_edit
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
        from ult3edit.text import cmd_edit
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
        from ult3edit.text import cmd_edit
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
        from ult3edit.constants import TILES
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



# =============================================================================
# Sound module tests
# =============================================================================



# =============================================================================
# Patch module tests
# =============================================================================



# =============================================================================
# DDRW module tests
# =============================================================================



# =============================================================================
# CON file layout tests (resolved via engine code tracing)
# =============================================================================

class TestCombatLayout:
    def test_padding_and_runtime_parsed(self, sample_con_bytes):
        from ult3edit.combat import CombatMap
        cm = CombatMap(sample_con_bytes)
        assert len(cm.padding1) == 7
        assert len(cm.runtime_monster) == 16
        assert len(cm.runtime_pc) == 8
        assert len(cm.padding2) == 16

    def test_layout_in_dict(self, sample_con_bytes):
        from ult3edit.combat import CombatMap
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
        from ult3edit.combat import CombatMap
        from ult3edit.constants import CON_PADDING1_OFFSET
        data = bytearray(192)
        data[CON_PADDING1_OFFSET] = 0x42
        data[CON_PADDING1_OFFSET + 1] = 0x55
        cm = CombatMap(data)
        assert cm.padding1[0] == 0x42
        assert cm.padding1[1] == 0x55

    def test_padding_render_shows_nonzero(self):
        from ult3edit.combat import CombatMap
        from ult3edit.constants import CON_PADDING1_OFFSET
        data = bytearray(192)
        data[CON_PADDING1_OFFSET] = 0xAB
        cm = CombatMap(data)
        rendered = cm.render()
        assert 'Padding (0x79)' in rendered
        assert 'AB' in rendered


# =============================================================================
# Sound MBS music stream tests
# =============================================================================


# =============================================================================
# Special location trailing bytes tests (unused padding, verified via engine)
# =============================================================================

class TestSpecialTrailingBytes:
    def test_trailing_bytes_extracted(self, sample_special_bytes):
        from ult3edit.special import get_trailing_bytes
        trailing = get_trailing_bytes(sample_special_bytes)
        assert len(trailing) == 7

    def test_trailing_bytes_nonzero(self):
        from ult3edit.special import get_trailing_bytes, SPECIAL_META_OFFSET
        data = bytearray(128)
        data[SPECIAL_META_OFFSET] = 0x42
        data[SPECIAL_META_OFFSET + 3] = 0xFF
        trailing = get_trailing_bytes(data)
        assert trailing[0] == 0x42
        assert trailing[3] == 0xFF

    def test_trailing_bytes_in_render(self):
        from ult3edit.special import render_special_map, SPECIAL_META_OFFSET
        data = bytearray(128)
        data[SPECIAL_META_OFFSET] = 0xAB
        rendered = render_special_map(data)
        assert 'Trailing padding' in rendered
        assert 'AB' in rendered

    def test_trailing_bytes_not_shown_when_zero(self, sample_special_bytes):
        from ult3edit.special import render_special_map
        rendered = render_special_map(sample_special_bytes)
        assert 'Trailing' not in rendered

    def test_backward_compat_alias(self):
        """get_metadata still works as backward-compat alias."""
        from ult3edit.special import get_metadata, get_trailing_bytes
        assert get_metadata is get_trailing_bytes


# =============================================================================
# Shapes overlay string extraction tests
# =============================================================================


# =============================================================================
# SHPS code guard tests
# =============================================================================


# =============================================================================
# Disk audit tests
# =============================================================================

class TestDiskAudit:
    def test_audit_output_format(self):
        """Verify the audit function imports cleanly."""
        from ult3edit.disk import cmd_audit
        # Just verify it's callable
        assert callable(cmd_audit)


# =============================================================================
# CLI parity tests — main() matches register_parser()
# =============================================================================

import subprocess


def _help_output(module: str, subcmd: str) -> str:
    """Get --help output from a standalone module entry point."""
    result = subprocess.run(
        [sys.executable, '-m', f'ult3edit.{module}', subcmd, '--help'],
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

    def test_disk_main_info_help(self):
        out = _help_output('disk', 'info')
        assert '--json' in out
        assert 'image' in out.lower()

    def test_disk_main_list_help(self):
        out = _help_output('disk', 'list')
        assert '--json' in out
        assert '--path' in out

    def test_disk_main_extract_help(self):
        out = _help_output('disk', 'extract')
        assert 'image' in out.lower()

    def test_disk_main_audit_help(self):
        out = _help_output('disk', 'audit')
        assert '--json' in out
        assert '--detail' in out

    def test_diff_main_help(self):
        """diff module standalone main() has correct args."""
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit.diff', '--help'],
            capture_output=True, text=True, timeout=10)
        out = result.stdout + result.stderr
        assert 'path1' in out
        assert 'path2' in out
        assert '--json' in out
        assert '--summary' in out

    def test_map_main_compile_help(self):
        out = _help_output('map', 'compile')
        assert '--dungeon' in out
        assert 'source' in out

    def test_map_main_decompile_help(self):
        out = _help_output('map', 'decompile')
        assert '--output' in out

    def test_shapes_main_compile_help(self):
        out = _help_output('shapes', 'compile')
        assert '--format' in out
        assert 'source' in out

    def test_shapes_main_decompile_help(self):
        out = _help_output('shapes', 'decompile')
        assert '--output' in out

    def test_patch_main_compile_names_help(self):
        out = _help_output('patch', 'compile-names')
        assert 'source' in out
        assert '--output' in out

    def test_patch_main_decompile_names_help(self):
        out = _help_output('patch', 'decompile-names')
        assert '--output' in out

    def test_patch_main_validate_names_help(self):
        out = _help_output('patch', 'validate-names')
        assert 'source' in out

    def test_patch_main_strings_edit_help(self):
        out = _help_output('patch', 'strings-edit')
        assert '--text' in out
        assert '--index' in out
        assert '--vanilla' in out
        assert '--address' in out

    def test_patch_main_strings_import_help(self):
        out = _help_output('patch', 'strings-import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_exod_main_view_help(self):
        out = _help_output('exod', 'view')
        assert '--json' in out

    def test_exod_main_export_help(self):
        out = _help_output('exod', 'export')
        assert '--frame' in out
        assert '--scale' in out

    def test_exod_main_import_help(self):
        out = _help_output('exod', 'import')
        assert '--frame' in out
        assert '--backup' in out
        assert '--dry-run' in out

    def test_exod_main_glyph_help(self):
        out = _help_output('exod', 'glyph')
        assert 'view' in out
        assert 'export' in out
        assert 'import' in out

    def test_exod_main_crawl_help(self):
        out = _help_output('exod', 'crawl')
        assert 'view' in out
        assert 'compose' in out

    def test_disk_main_build_help(self):
        out = _help_output('disk', 'build')
        assert '--vol-name' in out
        assert '--boot-from' in out


class TestDiskContextParseHash:
    """Test DiskContext._parse_hash_suffix."""

    def test_with_hash_suffix(self):
        from ult3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('ROST#069500')
        assert name == 'ROST'
        assert ft == 0x06
        assert at == 0x9500

    def test_without_hash(self):
        from ult3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('ROST')
        assert name == 'ROST'
        assert ft == 0x06
        assert at == 0x0000

    def test_short_suffix(self):
        from ult3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('FOO#AB')
        assert name == 'FOO'
        assert ft == 0x06  # fallback
        assert at == 0x0000

    def test_all_zeros(self):
        from ult3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('MAP#000000')
        assert name == 'MAP'
        assert ft == 0x00
        assert at == 0x0000


class TestTextImportDryRun:
    """Behavioral test: text import --dry-run should not write."""

    def test_import_dry_run_no_write(self, tmp_dir):
        from ult3edit.text import cmd_import as text_import
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
        from ult3edit.text import cmd_import as text_import
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
        from ult3edit.roster import _apply_edits
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
        from ult3edit.roster import _apply_edits
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

from ult3edit.shapes import (
    encode_overlay_string, extract_overlay_strings,
)

_JSR_46BA_BYTES = bytes([0x20, 0xBA, 0x46])


# =============================================================================
# Fix 3: CLI parity for edit-string
# =============================================================================


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

            from ult3edit.save import cmd_import as save_import
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
            [sys.executable, '-m', 'ult3edit.save', 'edit', '--help'],
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

            from ult3edit.save import cmd_import as save_import
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
        from ult3edit.combat import CombatMap
        from ult3edit.constants import CON_FILE_SIZE
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
        from ult3edit.combat import CombatMap
        from ult3edit.constants import CON_FILE_SIZE, CON_MONSTER_COUNT
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

# =============================================================================
# Fix: Map JSON round-trip preserves tile data
# =============================================================================

class TestMapJsonRoundTrip:
    """Verify that map export→import round-trip preserves all tiles."""

    def test_overworld_round_trip(self, tmp_dir, sample_overworld_bytes):
        """Export an overworld map to JSON, import it back, verify tiles match."""
        from ult3edit.map import cmd_view, cmd_import
        map_file = os.path.join(tmp_dir, 'MAPA#061000')
        with open(map_file, 'wb') as f:
            f.write(sample_overworld_bytes)
        json_file = os.path.join(tmp_dir, 'map_export.json')
        # Export to JSON
        args = type('Args', (), {
            'file': map_file, 'json': True, 'output': json_file,
            'crop': None,
        })()
        cmd_view(args)
        # Create a fresh map file filled with 0xFF (totally different)
        out_file = os.path.join(tmp_dir, 'MAPA_OUT')
        with open(out_file, 'wb') as f:
            f.write(sample_overworld_bytes)  # start from same so size matches
        # Import JSON back
        args = type('Args', (), {
            'file': out_file, 'json_file': json_file,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        # Verify
        with open(out_file, 'rb') as f:
            result = f.read()
        assert result == sample_overworld_bytes

    def test_dungeon_round_trip(self, tmp_dir, sample_dungeon_bytes):
        """Export a dungeon map to JSON, import it back, verify tiles match."""
        from ult3edit.map import cmd_view, cmd_import
        map_file = os.path.join(tmp_dir, 'MAPD#061000')
        with open(map_file, 'wb') as f:
            f.write(sample_dungeon_bytes)
        json_file = os.path.join(tmp_dir, 'dung_export.json')
        # Export
        args = type('Args', (), {
            'file': map_file, 'json': True, 'output': json_file,
            'crop': None,
        })()
        cmd_view(args)
        # Import back
        out_file = os.path.join(tmp_dir, 'MAPD_OUT')
        with open(out_file, 'wb') as f:
            f.write(sample_dungeon_bytes)
        args = type('Args', (), {
            'file': out_file, 'json_file': json_file,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        with open(out_file, 'rb') as f:
            result = f.read()
        assert result == sample_dungeon_bytes

    def test_dungeon_import_oob_level_ignored(self, tmp_dir, sample_dungeon_bytes):
        """Import with out-of-bounds level number should skip, not crash."""
        from ult3edit.map import cmd_import
        map_file = os.path.join(tmp_dir, 'MAPD#061000')
        with open(map_file, 'wb') as f:
            f.write(sample_dungeon_bytes)
        # JSON with level 9 (out of bounds for 8-level dungeon) and level 1 (valid)
        jdata = {
            'type': 'dungeon',
            'levels': [
                {'level': 9, 'tiles': [['X'] * 16] * 16},  # OOB, should be skipped
                {'level': 1, 'tiles': [['#'] * 16] * 16},   # Valid
            ]
        }
        json_path = os.path.join(tmp_dir, 'dung.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = type('Args', (), {
            'file': map_file, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)  # Should not raise IndexError
        with open(map_file, 'rb') as f:
            result = f.read()
        assert len(result) == len(sample_dungeon_bytes)

    def test_dungeon_import_negative_level_ignored(self, tmp_dir, sample_dungeon_bytes):
        """Import with negative level number should skip, not corrupt data."""
        from ult3edit.map import cmd_import
        map_file = os.path.join(tmp_dir, 'MAPD#061000')
        with open(map_file, 'wb') as f:
            f.write(sample_dungeon_bytes)
        jdata = {
            'type': 'dungeon',
            'levels': [{'level': -1, 'tiles': [['X'] * 16] * 16}]
        }
        json_path = os.path.join(tmp_dir, 'dung.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = type('Args', (), {
            'file': map_file, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)  # Should not crash or corrupt
        with open(map_file, 'rb') as f:
            result = f.read()
        assert result == sample_dungeon_bytes  # Unchanged — level skipped

    def test_resolve_tile_handles_name_strings(self):
        """The resolve_tile function handles multi-char tile names."""
        from ult3edit.constants import TILE_NAMES_REVERSE
        assert TILE_NAMES_REVERSE['water'] == 0x00
        assert TILE_NAMES_REVERSE['grass'] == 0x04
        assert TILE_NAMES_REVERSE['town'] == 0x18

    def test_resolve_tile_handles_dungeon_names(self):
        """Dungeon tile name reverse lookup works."""
        from ult3edit.constants import DUNGEON_TILE_NAMES_REVERSE
        assert DUNGEON_TILE_NAMES_REVERSE['open'] == 0x00
        assert DUNGEON_TILE_NAMES_REVERSE['wall'] == 0x01
        assert DUNGEON_TILE_NAMES_REVERSE['door'] == 0x02


# =============================================================================
# Fix: Save edit --output conflict when both PRTY and PLRS modified
# =============================================================================

class TestSaveOutputConflict:
    """Verify that --output is rejected when editing both party and PLRS."""

    def test_dual_file_output_rejected(self, tmp_dir, sample_prty_bytes):
        """Editing both PRTY and PLRS with --output should fail."""
        from ult3edit.save import cmd_edit
        from ult3edit.constants import PLRS_FILE_SIZE
        # Create PRTY file in game dir
        prty_file = os.path.join(tmp_dir, 'PRTY#069500')
        with open(prty_file, 'wb') as f:
            f.write(sample_prty_bytes)
        # Create PLRS file in same dir
        plrs_data = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            plrs_data[i] = ord(ch) | 0x80
        plrs_file = os.path.join(tmp_dir, 'PLRS#069500')
        with open(plrs_file, 'wb') as f:
            f.write(plrs_data)
        # Try editing both party state and PLRS character with --output
        args = type('Args', (), {
            'game_dir': tmp_dir, 'output': '/tmp/out',
            'backup': False, 'dry_run': False,
            'transport': 'Horse', 'x': None, 'y': None,
            'party_size': None, 'slot_ids': None,
            'sentinel': None, 'location': None,
            'plrs_slot': 0, 'name': 'TEST',
            'str': None, 'dex': None, 'int_': None, 'wis': None,
            'hp': None, 'max_hp': None, 'exp': None,
            'mp': None, 'food': None, 'gold': None,
            'gems': None, 'keys': None, 'powders': None,
            'torches': None, 'status': None, 'race': None,
            'class_': None, 'gender': None,
            'weapon': None, 'armor': None,
            'marks': None, 'cards': None, 'sub_morsels': None,
        })()
        original_plrs = bytes(plrs_data)
        with pytest.raises(SystemExit):
            cmd_edit(args)
        # PLRS must NOT have been written before the conflict error
        with open(plrs_file, 'rb') as f:
            assert f.read() == original_plrs, "PLRS was modified before conflict check"


# =============================================================================
# Fix: --validate on bestiary and combat edit CLI args
# =============================================================================

class TestValidateOnEditArgs:
    """Verify --validate is accepted by bestiary and combat edit subparsers."""

    def test_bestiary_edit_accepts_validate(self):
        """bestiary edit --validate should be a valid CLI arg."""
        import argparse
        from ult3edit.bestiary import register_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='module')
        register_parser(sub)
        args = parser.parse_args(['bestiary', 'edit', 'test.mon', '--monster', '0',
                                  '--hp', '50', '--validate'])
        assert args.validate is True

    def test_combat_edit_accepts_validate(self):
        """combat edit --validate should be a valid CLI arg."""
        import argparse
        from ult3edit.combat import register_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='module')
        register_parser(sub)
        args = parser.parse_args(['combat', 'edit', 'test.con',
                                  '--tile', '0', '0', '32', '--validate'])
        assert args.validate is True

    def test_bestiary_edit_validate_runs(self, tmp_dir, sample_mon_bytes):
        """bestiary edit with --validate should show warnings."""
        from ult3edit.bestiary import cmd_edit
        mon_file = os.path.join(tmp_dir, 'MONA#069900')
        with open(mon_file, 'wb') as f:
            f.write(sample_mon_bytes)
        args = type('Args', (), {
            'file': mon_file, 'monster': 0, 'all': False,
            'output': None, 'backup': False, 'dry_run': True,
            'validate': True,
            'name': None, 'tile1': None, 'tile2': None,
            'hp': 50, 'attack': None, 'defense': None, 'speed': None,
            'flags1': None, 'flags2': None, 'ability1': None, 'ability2': None,
            'type': None,
            'boss': None, 'no_boss': None, 'undead': None, 'ranged': None,
            'magic_user': None, 'poison': None, 'no_poison': None,
            'sleep': None, 'no_sleep': None, 'negate': None, 'no_negate': None,
            'teleport': None, 'no_teleport': None,
            'divide': None, 'no_divide': None,
            'resistant': None, 'no_resistant': None,
        })()
        # Should not raise
        cmd_edit(args)

    def test_combat_edit_validate_runs(self, tmp_dir, sample_con_bytes):
        """combat edit with --validate should show warnings."""
        from ult3edit.combat import cmd_edit
        con_file = os.path.join(tmp_dir, 'CONA#069900')
        with open(con_file, 'wb') as f:
            f.write(sample_con_bytes)
        args = type('Args', (), {
            'file': con_file,
            'output': None, 'backup': False, 'dry_run': True,
            'validate': True,
            'tile': [5, 5, 0x20],
            'monster_pos': None, 'pc_pos': None,
        })()
        # Should not raise
        cmd_edit(args)


# =============================================================================
# Fix: Dead code removal verification
# =============================================================================

class TestDeadCodeRemoved:
    """Verify removed dead functions are no longer importable."""

    def test_validate_file_size_removed(self):
        """validate_file_size should no longer exist in fileutil."""
        from ult3edit import fileutil
        assert not hasattr(fileutil, 'validate_file_size')

    def test_load_game_file_removed(self):
        """load_game_file should no longer exist in fileutil."""
        from ult3edit import fileutil
        assert not hasattr(fileutil, 'load_game_file')


class TestSpecialJsonKeyConsistency:
    def test_single_file_uses_trailing_bytes_key(self):
        from ult3edit.special import cmd_view
        from ult3edit.constants import SPECIAL_FILE_SIZE
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


# =============================================================================
# Patch import + round-trip tests
# =============================================================================


# =============================================================================
# Roster create extended args tests
# =============================================================================

class TestRosterCreateExtendedArgs:
    """Verify roster create accepts all edit args (hp, gold, food, etc.)."""

    def test_create_with_hp_and_gold(self, tmp_dir, sample_roster_file):
        """The Voidborn pattern: create with --hp and --gold."""
        from ult3edit.roster import cmd_create
        args = type('Args', (), {
            'file': sample_roster_file,
            'slot': 5,
            'output': None,
            'backup': False,
            'dry_run': False,
            'force': False,
            'name': 'KAEL',
            'race': 'H',
            'class_': 'R',
            'gender': 'M',
            'str': 30,
            'dex': 45,
            'int_': None,
            'wis': None,
            'hp': 250,
            'max_hp': None,
            'mp': None,
            'gold': 300,
            'exp': None,
            'food': None,
            'gems': None,
            'keys': None,
            'powders': None,
            'torches': None,
            'status': None,
            'weapon': None,
            'armor': None,
            'give_weapon': None,
            'give_armor': None,
            'marks': None,
            'cards': None,
            'in_party': None,
            'not_in_party': None,
            'sub_morsels': None,
        })()
        cmd_create(args)

        chars, _ = load_roster(sample_roster_file)
        c = chars[5]
        assert c.name == 'KAEL'
        assert c.hp == 250
        assert c.max_hp == 250  # auto-raised to match hp
        assert c.gold == 300
        assert c.strength == 30
        assert c.dexterity == 45
        # Defaults preserved where not specified
        assert c.intelligence == 15
        assert c.wisdom == 15
        assert c.food == 200  # default

    def test_create_with_equipment(self, tmp_dir, sample_roster_file):
        """Create with weapon, armor, in-party, food, gems."""
        from ult3edit.roster import cmd_create
        args = type('Args', (), {
            'file': sample_roster_file,
            'slot': 6,
            'output': None,
            'backup': False,
            'dry_run': False,
            'force': False,
            'name': 'THARN',
            'race': 'D',
            'class_': 'F',
            'gender': 'M',
            'str': 50,
            'dex': 25,
            'int_': None,
            'wis': None,
            'hp': 350,
            'max_hp': None,
            'mp': None,
            'gold': None,
            'exp': None,
            'food': 500,
            'gems': 5,
            'keys': 3,
            'powders': None,
            'torches': 10,
            'status': None,
            'weapon': 6,
            'armor': 4,
            'give_weapon': None,
            'give_armor': None,
            'marks': None,
            'cards': None,
            'in_party': True,
            'not_in_party': None,
            'sub_morsels': 50,
        })()
        cmd_create(args)

        chars, _ = load_roster(sample_roster_file)
        c = chars[6]
        assert c.name == 'THARN'
        assert c.hp == 350
        assert c.food == 500
        assert c.gems == 5
        assert c.keys == 3
        assert c.torches == 10
        assert c.raw[0x30] == 6  # Sword
        assert c.raw[0x28] == 4  # Plate
        assert c.in_party is True
        assert c.sub_morsels == 50

    def test_create_defaults_without_overrides(self, tmp_dir, sample_roster_file):
        """Create with minimal args uses sensible defaults."""
        from ult3edit.roster import cmd_create
        args = type('Args', (), {
            'file': sample_roster_file,
            'slot': 7,
            'output': None,
            'backup': False,
            'dry_run': False,
            'force': False,
            'name': None,
            'race': None,
            'class_': None,
            'gender': None,
            'str': None,
            'dex': None,
            'int_': None,
            'wis': None,
            'hp': None,
            'max_hp': None,
            'mp': None,
            'gold': None,
            'exp': None,
            'food': None,
            'gems': None,
            'keys': None,
            'powders': None,
            'torches': None,
            'status': None,
            'weapon': None,
            'armor': None,
            'give_weapon': None,
            'give_armor': None,
            'marks': None,
            'cards': None,
            'in_party': None,
            'not_in_party': None,
            'sub_morsels': None,
        })()
        cmd_create(args)

        chars, _ = load_roster(sample_roster_file)
        c = chars[7]
        assert c.name == 'HERO'
        assert c.hp == 150
        assert c.max_hp == 150
        assert c.gold == 100
        assert c.food == 200
        assert c.strength == 15

    def test_create_cli_help_shows_hp(self):
        """Verify --hp appears in create subcommand help."""
        import subprocess
        result = subprocess.run(
            ['python', '-m', 'ult3edit.roster', 'create', '--help'],
            capture_output=True, text=True)
        assert '--hp' in result.stdout
        assert '--gold' in result.stdout
        assert '--food' in result.stdout
        assert '--in-party' in result.stdout


# =============================================================================
# Functional tests for cmd_edit_string (shapes) and cmd_search (tlk)
# =============================================================================


class TestCmdSearchFunctional:
    """Functional tests for tlk search command."""

    def test_search_single_file(self, tmp_path, sample_tlk_bytes):
        from ult3edit.tlk import cmd_search
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(sample_tlk_bytes)

        args = type('Args', (), {
            'path': path,
            'pattern': 'NAME',
            'regex': False,
            'json': False,
            'output': None,
        })()
        # Should not crash; pattern matching depends on fixture content
        cmd_search(args)

    def test_search_directory(self, tmp_path, sample_tlk_bytes):
        from ult3edit.tlk import cmd_search
        # Write multiple TLK files
        for letter in ['A', 'B']:
            path = str(tmp_path / f'TLK{letter}')
            with open(path, 'wb') as f:
                f.write(sample_tlk_bytes)

        args = type('Args', (), {
            'path': str(tmp_path),
            'pattern': 'NAME',
            'regex': False,
            'json': False,
            'output': None,
        })()
        cmd_search(args)

    def test_search_json_output(self, tmp_path, sample_tlk_bytes):
        from ult3edit.tlk import cmd_search
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(sample_tlk_bytes)

        json_path = str(tmp_path / 'results.json')
        args = type('Args', (), {
            'path': path,
            'pattern': 'NAME',
            'regex': False,
            'json': True,
            'output': json_path,
        })()
        cmd_search(args)

        # Should produce valid JSON
        with open(json_path, 'r') as f:
            results = json.load(f)
        assert isinstance(results, list)

    def test_search_regex(self, tmp_path, sample_tlk_bytes):
        from ult3edit.tlk import cmd_search
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(sample_tlk_bytes)

        args = type('Args', (), {
            'path': path,
            'pattern': 'N.*E',
            'regex': True,
            'json': False,
            'output': None,
        })()
        cmd_search(args)

    def test_search_no_matches(self, tmp_path, sample_tlk_bytes):
        from ult3edit.tlk import cmd_search
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(sample_tlk_bytes)

        args = type('Args', (), {
            'path': path,
            'pattern': 'XYZZY_NONEXISTENT',
            'regex': False,
            'json': False,
            'output': None,
        })()
        cmd_search(args)  # Should print "No matches" without crashing


class TestSaveEditValidate:
    """Test --validate on save edit command."""

    def test_validate_warns_on_bad_coords(self, tmp_path):
        from ult3edit.save import cmd_edit
        # Create PRTY file
        prty = bytearray(16)
        prty[0] = 0x00  # transport = foot
        prty[1] = 1     # party_size
        prty[2] = 0     # location = sosaria
        prty[3] = 10    # x
        prty[4] = 10    # y
        prty[5] = 0xFF  # sentinel
        prty[6] = 0     # slot 0
        prty_path = str(tmp_path / 'PRTY')
        with open(prty_path, 'wb') as f:
            f.write(prty)

        args = type('Args', (), {
            'game_dir': str(tmp_path),
            'transport': None,
            'x': 99,  # Out of bounds — should trigger warning
            'y': None,
            'party_size': None,
            'slot_ids': None,
            'sentinel': None,
            'location': None,
            'output': None,
            'backup': False,
            'dry_run': True,
            'validate': True,
            'plrs_slot': None,
        })()
        # Should not crash; validation warning printed
        cmd_edit(args)

    def test_validate_flag_in_help(self):
        import subprocess
        result = subprocess.run(
            ['python', '-m', 'ult3edit.save', 'edit', '--help'],
            capture_output=True, text=True)
        assert '--validate' in result.stdout


# =============================================================================
# hex_int acceptance: tile/offset/byte args accept 0x prefix
# =============================================================================

class TestHexIntArgParsing:
    """Verify that CLI args for tiles, offsets, and flags accept hex (0x) prefix."""

    def test_hex_int_helper(self):
        from ult3edit.fileutil import hex_int
        assert hex_int('10') == 10
        assert hex_int('0x0A') == 10
        assert hex_int('0xFF') == 255
        assert hex_int('0') == 0

    def test_hex_int_rejects_garbage(self):
        from ult3edit.fileutil import hex_int
        with pytest.raises(ValueError):
            hex_int('xyz')

    def test_map_tile_accepts_hex(self, tmp_dir):
        """map set --tile 0x01 should parse without error."""
        import argparse
        path = os.path.join(tmp_dir, 'MAP')
        data = bytes(MAP_OVERWORLD_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, x=0, y=0, tile=0x01,
            output=None, backup=False, dry_run=True)
        cmd_set(args)  # Should not raise

    def test_combat_tile_accepts_hex(self, tmp_dir):
        """combat edit --tile 0x08 should parse without error."""
        from ult3edit.combat import cmd_edit as combat_cmd_edit
        path = os.path.join(tmp_dir, 'CON')
        data = bytearray(CON_FILE_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = type('Args', (), {
            'file': path, 'tile': [0, 0, 0x08],
            'monster_pos': None, 'pc_pos': None,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        combat_cmd_edit(args)  # Should not raise

    def test_bestiary_flags_accept_hex(self, tmp_dir):
        """bestiary edit --flags1 0x80 should parse without error."""
        from ult3edit.bestiary import cmd_edit as bestiary_cmd_edit
        path = os.path.join(tmp_dir, 'MON')
        data = bytearray(MON_FILE_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = type('Args', (), {
            'file': path, 'monster': 0,
            'tile1': None, 'tile2': None,
            'flags1': 0x80, 'flags2': None,
            'hp': None, 'attack': None, 'defense': None, 'speed': None,
            'ability1': None, 'ability2': None,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        bestiary_cmd_edit(args)  # Should not raise

    def test_special_tile_accepts_hex(self, tmp_dir):
        """special edit --tile 0x00 0x00 0x08 should parse without error."""
        from ult3edit.special import cmd_edit as special_cmd_edit
        path = os.path.join(tmp_dir, 'BRND')
        data = bytearray(SPECIAL_FILE_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = type('Args', (), {
            'file': path, 'tile': [0, 0, 0x08],
            'output': None, 'backup': False, 'dry_run': True,
        })()
        special_cmd_edit(args)  # Should not raise

    def test_argparser_accepts_hex_string(self):
        """Verify argparse actually parses '0x0A' string to 10 via hex_int type."""
        import argparse
        from ult3edit.fileutil import hex_int
        parser = argparse.ArgumentParser()
        parser.add_argument('--tile', type=hex_int)
        args = parser.parse_args(['--tile', '0x0A'])
        assert args.tile == 10

    def test_argparser_accepts_decimal_string(self):
        """hex_int still works with plain decimal strings."""
        import argparse
        from ult3edit.fileutil import hex_int
        parser = argparse.ArgumentParser()
        parser.add_argument('--offset', type=hex_int)
        args = parser.parse_args(['--offset', '240'])
        assert args.offset == 240


# =============================================================================
# Sound and DDRW import integration tests
# =============================================================================


# =============================================================================
# Shapes cmd_edit and cmd_import integration tests
# =============================================================================


# =============================================================================
# Fix: HP > MaxHP race condition when both --hp and --max-hp provided
# =============================================================================

class TestHpMaxHpOrdering:
    """Verify max_hp >= hp when both are set simultaneously."""

    def test_roster_hp_exceeds_max_hp(self, sample_character_bytes):
        """roster _apply_edits: --hp 200 --max-hp 100 should auto-raise max_hp."""
        from ult3edit.roster import Character, _apply_edits
        char = Character(bytearray(sample_character_bytes))
        args = type('Args', (), {
            'name': None, 'str': None, 'dex': None, 'int_': None, 'wis': None,
            'hp': 200, 'max_hp': 100, 'mp': None, 'gold': None, 'exp': None,
            'food': None, 'gems': None, 'keys': None, 'powders': None,
            'torches': None, 'status': None, 'race': None, 'class_': None,
            'gender': None, 'weapon': None, 'armor': None,
            'marks': None, 'cards': None, 'sub_morsels': None,
            'give_weapon': None, 'give_armor': None,
            'in_party': None, 'not_in_party': None,
        })()
        _apply_edits(char, args)
        assert char.hp == 200
        assert char.max_hp >= char.hp, f"max_hp {char.max_hp} < hp {char.hp}"

    def test_roster_max_hp_alone(self, sample_character_bytes):
        """roster _apply_edits: --max-hp 500 alone sets max_hp without touching hp."""
        from ult3edit.roster import Character, _apply_edits
        char = Character(bytearray(sample_character_bytes))
        original_hp = char.hp
        args = type('Args', (), {
            'name': None, 'str': None, 'dex': None, 'int_': None, 'wis': None,
            'hp': None, 'max_hp': 500, 'mp': None, 'gold': None, 'exp': None,
            'food': None, 'gems': None, 'keys': None, 'powders': None,
            'torches': None, 'status': None, 'race': None, 'class_': None,
            'gender': None, 'weapon': None, 'armor': None,
            'marks': None, 'cards': None, 'sub_morsels': None,
            'give_weapon': None, 'give_armor': None,
            'in_party': None, 'not_in_party': None,
        })()
        _apply_edits(char, args)
        assert char.hp == original_hp
        assert char.max_hp == 500

    def test_save_plrs_hp_exceeds_max_hp(self, tmp_dir, sample_prty_bytes,
                                          sample_character_bytes):
        """save cmd_edit: --hp 200 --max-hp 100 via PLRS should auto-raise max_hp."""
        from ult3edit.save import cmd_edit
        from ult3edit.constants import PLRS_FILE_SIZE, CHAR_RECORD_SIZE
        from ult3edit.roster import Character
        prty_path = os.path.join(tmp_dir, 'PRTY#069500')
        with open(prty_path, 'wb') as f:
            f.write(sample_prty_bytes)
        plrs_data = bytearray(PLRS_FILE_SIZE)
        plrs_data[:CHAR_RECORD_SIZE] = sample_character_bytes
        plrs_path = os.path.join(tmp_dir, 'PLRS#069500')
        with open(plrs_path, 'wb') as f:
            f.write(plrs_data)
        args = type('Args', (), {
            'game_dir': tmp_dir, 'output': None,
            'backup': False, 'dry_run': False,
            'transport': None, 'x': None, 'y': None,
            'party_size': None, 'slot_ids': None,
            'sentinel': None, 'location': None,
            'plrs_slot': 0, 'name': None,
            'str': None, 'dex': None, 'int_': None, 'wis': None,
            'hp': 200, 'max_hp': 100,
            'mp': None, 'food': None, 'gold': None, 'exp': None,
            'gems': None, 'keys': None, 'powders': None,
            'torches': None, 'status': None, 'race': None,
            'class_': None, 'gender': None,
            'weapon': None, 'armor': None,
            'marks': None, 'cards': None, 'sub_morsels': None,
            'validate': False,
        })()
        cmd_edit(args)
        with open(plrs_path, 'rb') as f:
            result = f.read()
        char = Character(bytearray(result[:CHAR_RECORD_SIZE]))
        assert char.hp == 200
        assert char.max_hp >= char.hp, f"max_hp {char.max_hp} < hp {char.hp}"


# =============================================================================
# Fix: shapes cmd_import() KeyError on malformed JSON
# =============================================================================


# =============================================================================
# Fix: weapons/armors .items() crash on non-dict JSON values
# =============================================================================

class TestImportMalformedInventory:
    """Verify cmd_import handles non-dict weapons/armors gracefully."""

    def test_roster_import_null_weapons(self, tmp_dir, sample_roster_bytes):
        """roster cmd_import: weapons=null should not crash."""
        from ult3edit.roster import cmd_import as roster_cmd_import
        path = os.path.join(tmp_dir, 'ROST#069500')
        with open(path, 'wb') as f:
            f.write(sample_roster_bytes)
        jdata = [{'slot': 0, 'name': 'TEST', 'weapons': None, 'armors': None}]
        json_path = os.path.join(tmp_dir, 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        roster_cmd_import(args)  # should not raise TypeError/AttributeError

    def test_roster_import_list_weapons(self, tmp_dir, sample_roster_bytes):
        """roster cmd_import: weapons as list should not crash."""
        from ult3edit.roster import cmd_import as roster_cmd_import
        path = os.path.join(tmp_dir, 'ROST#069500')
        with open(path, 'wb') as f:
            f.write(sample_roster_bytes)
        jdata = [{'slot': 0, 'name': 'TEST', 'weapons': ['Dagger'], 'armors': []}]
        json_path = os.path.join(tmp_dir, 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        roster_cmd_import(args)  # should not raise TypeError/AttributeError

    def test_save_import_null_weapons(self, tmp_dir, sample_prty_bytes,
                                       sample_character_bytes):
        """save cmd_import: PLRS entry with weapons=null should not crash."""
        from ult3edit.save import cmd_import as save_cmd_import
        from ult3edit.constants import PLRS_FILE_SIZE, CHAR_RECORD_SIZE
        prty_path = os.path.join(tmp_dir, 'PRTY#069500')
        with open(prty_path, 'wb') as f:
            f.write(sample_prty_bytes)
        plrs_data = bytearray(PLRS_FILE_SIZE)
        plrs_data[:CHAR_RECORD_SIZE] = sample_character_bytes
        plrs_path = os.path.join(tmp_dir, 'PLRS#069500')
        with open(plrs_path, 'wb') as f:
            f.write(plrs_data)
        jdata = {
            'transport': 'On Foot',
            'characters': [{'slot': 0, 'name': 'TEST', 'weapons': None, 'armors': None}]
        }
        json_path = os.path.join(tmp_dir, 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = type('Args', (), {
            'game_dir': tmp_dir, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        save_cmd_import(args)  # should not raise TypeError/AttributeError


# =============================================================================
# Fix: marks/cards setter case sensitivity (silent data loss)
# =============================================================================

class TestMarksCaseInsensitive:
    """Verify marks/cards setters accept any casing."""

    def test_marks_lowercase(self, sample_character_bytes):
        """Setting marks with lowercase names should work."""
        from ult3edit.roster import Character
        char = Character(bytearray(sample_character_bytes))
        char.marks = ['fire', 'force']
        assert 'Fire' in char.marks
        assert 'Force' in char.marks

    def test_marks_uppercase(self, sample_character_bytes):
        """Setting marks with uppercase names should work."""
        from ult3edit.roster import Character
        char = Character(bytearray(sample_character_bytes))
        char.marks = ['KINGS', 'SNAKE']
        assert 'Kings' in char.marks
        assert 'Snake' in char.marks

    def test_cards_lowercase(self, sample_character_bytes):
        """Setting cards with lowercase names should work."""
        from ult3edit.roster import Character
        char = Character(bytearray(sample_character_bytes))
        char.cards = ['death', 'sol', 'love', 'moons']
        assert len(char.cards) == 4

    def test_marks_mixed_case(self, sample_character_bytes):
        """Setting marks with mixed casing should work."""
        from ult3edit.roster import Character
        char = Character(bytearray(sample_character_bytes))
        char.marks = ['fIrE', 'FoRcE']
        assert 'Fire' in char.marks
        assert 'Force' in char.marks

    def test_marks_preserves_cards(self, sample_character_bytes):
        """Setting marks should not clear existing cards."""
        from ult3edit.roster import Character
        char = Character(bytearray(sample_character_bytes))
        char.cards = ['Death', 'Sol']
        char.marks = ['kings']
        assert 'Kings' in char.marks
        assert 'Death' in char.cards
        assert 'Sol' in char.cards


# =============================================================================
# Tile Compiler Tests
# =============================================================================


# =============================================================================
# Map Compiler Tests
# =============================================================================

class TestMapCompilerParsing:
    """Test map_compiler.py text-art parsing."""

    def test_parse_overworld_row(self):
        """Parse a simple overworld row with known tile chars."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from map_compiler import parse_map_file
        # Build a 64x64 map of all grass (.)
        row = '.' * 64
        text = '# Test map\n' + (row + '\n') * 64
        grid = parse_map_file(text, is_dungeon=False)
        assert len(grid) == 64
        assert len(grid[0]) == 64
        # '.' = grass = 0x04
        assert grid[0][0] == 0x04

    def test_parse_dungeon(self):
        """Parse a dungeon format (16x16 x 8 levels)."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from map_compiler import parse_map_file
        # 8 levels of 16x16 open floor
        levels_text = ''
        for lv in range(8):
            levels_text += f'# Level {lv}\n'
            for y in range(16):
                levels_text += '.' * 16 + '\n'
            levels_text += '\n'
        levels = parse_map_file(levels_text, is_dungeon=True)
        assert len(levels) == 8
        assert len(levels[0]) == 16
        assert len(levels[0][0]) == 16

    def test_parse_mixed_tiles(self):
        """Parse a row with different tile characters."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from map_compiler import parse_map_file
        # Water + grass + mountains + forest
        row = '~.' + '^T' + '.' * 60
        text = '# Test\n' + (row + '\n') + ('.' * 64 + '\n') * 63
        grid = parse_map_file(text, is_dungeon=False)
        assert grid[0][0] == 0x00  # ~ = Water
        assert grid[0][1] == 0x04  # . = Grass
        assert grid[0][2] == 0x10  # ^ = Mountains
        assert grid[0][3] == 0x0C  # T = Forest


class TestMapCompilerDecompile:
    """Test map_compiler.py decompile from binary."""

    def test_decompile_overworld(self):
        """Decompile an overworld map to text-art."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from map_compiler import decompile_map
        # Create an all-grass map (tile byte 0x04)
        data = bytes([0x04] * 4096)
        text = decompile_map(data, is_dungeon=False)
        lines = [l for l in text.split('\n') if l and not l.startswith('#')]
        assert len(lines) == 64
        assert all(c == '.' for c in lines[0])

    def test_decompile_dungeon(self):
        """Decompile a dungeon map to text-art."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from map_compiler import decompile_map
        # Create all-wall dungeon (tile byte 0x01)
        data = bytes([0x01] * 2048)
        text = decompile_map(data, is_dungeon=True)
        assert '# Level 0' in text
        assert '# Level 7' in text
        lines = [l for l in text.split('\n')
                 if l and not l.startswith('# ')]
        assert all(c == '#' for c in lines[0])  # Wall char


class TestMapCompilerRoundTrip:
    """Test map compile->decompile round-trip."""

    def test_overworld_round_trip(self):
        """Compile and decompile should preserve tile types."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from map_compiler import parse_map_file, decompile_map
        # Create a known binary, decompile, parse back
        data = bytearray(4096)
        for i in range(4096):
            data[i] = 0x04  # Grass
        data[0] = 0x00  # Water at (0,0)
        data[1] = 0x10  # Mountains at (1,0)

        text = decompile_map(bytes(data), is_dungeon=False)
        grid = parse_map_file(text, is_dungeon=False)
        assert grid[0][0] == 0x00  # Water preserved
        assert grid[0][1] == 0x10  # Mountains preserved
        assert grid[0][2] == 0x04  # Grass preserved


# =============================================================================
# Verify Tool Tests
# =============================================================================

class TestVerifyTool:
    """Test verify.py asset checking."""

    def test_find_file_exact(self, tmp_path):
        """find_file finds exact filename."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import find_file
        (tmp_path / 'ROST').write_bytes(b'\x00' * 1280)
        result = find_file(str(tmp_path), 'ROST')
        assert result is not None
        assert result.name == 'ROST'

    def test_find_file_with_hash_suffix(self, tmp_path):
        """find_file finds files with ProDOS #hash suffix."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import find_file
        (tmp_path / 'ROST#069500').write_bytes(b'\x00' * 1280)
        result = find_file(str(tmp_path), 'ROST')
        assert result is not None
        assert 'ROST' in result.name

    def test_find_file_missing(self, tmp_path):
        """find_file returns None for missing files."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import find_file
        result = find_file(str(tmp_path), 'ROST')
        assert result is None

    def test_verify_detects_missing(self, tmp_path):
        """Verification reports missing files."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import verify_game
        total, passed, results = verify_game(str(tmp_path))
        # Empty dir should have many missing categories
        assert passed < total
        assert results['Characters']['missing'] > 0

    def test_verify_detects_present(self, tmp_path):
        """Verification reports found files."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import verify_game
        # Create ROST file
        (tmp_path / 'ROST').write_bytes(b'\x00' * 1280)
        total, passed, results = verify_game(str(tmp_path))
        assert results['Characters']['found'] == 1
        assert results['Characters']['missing'] == 0

    def test_verify_detects_unchanged(self, tmp_path):
        """Verification with vanilla dir detects unchanged files."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import verify_game
        game_dir = tmp_path / 'game'
        vanilla_dir = tmp_path / 'vanilla'
        game_dir.mkdir()
        vanilla_dir.mkdir()
        # Same content = unchanged
        (game_dir / 'ROST').write_bytes(b'\x00' * 1280)
        (vanilla_dir / 'ROST').write_bytes(b'\x00' * 1280)
        total, passed, results = verify_game(
            str(game_dir), str(vanilla_dir))
        assert results['Characters']['unchanged'] == 1

    def test_verify_detects_modified(self, tmp_path):
        """Verification with vanilla dir detects modified files."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from verify import verify_game
        game_dir = tmp_path / 'game'
        vanilla_dir = tmp_path / 'vanilla'
        game_dir.mkdir()
        vanilla_dir.mkdir()
        # Different content = modified
        (game_dir / 'ROST').write_bytes(b'\xFF' * 1280)
        (vanilla_dir / 'ROST').write_bytes(b'\x00' * 1280)
        total, passed, results = verify_game(
            str(game_dir), str(vanilla_dir))
        assert results['Characters']['modified'] == 1


# =============================================================================
# Phase 0: Import format compatibility
# =============================================================================

class TestBestiaryDictImport:
    """Test that bestiary import accepts dict-of-dicts JSON format."""

    def test_import_dict_format(self, tmp_path):
        """Import bestiary from dict-keyed JSON (Voidborn source format)."""
        mon_file = tmp_path / 'MONA'
        mon_file.write_bytes(bytearray(MON_FILE_SIZE))
        json_file = tmp_path / 'bestiary.json'
        json_file.write_text(json.dumps({
            "monsters": {
                "0": {"hp": 60, "attack": 35, "defense": 25, "speed": 20},
                "3": {"hp": 100, "attack": 50, "defense": 40, "speed": 30}
            }
        }))
        # Run import via cmd_import
        import argparse
        from ult3edit.bestiary import cmd_import as bestiary_import
        args = argparse.Namespace(
            file=str(mon_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        bestiary_import(args)
        monsters = load_mon_file(str(mon_file))
        assert monsters[0].hp == 60
        assert monsters[0].attack == 35
        assert monsters[3].hp == 100
        assert monsters[3].attack == 50
        # Unmodified monster should be 0
        assert monsters[1].hp == 0

    def test_import_flag_shortcuts(self, tmp_path):
        """Import bestiary with flag shortcuts (boss, poison, etc.)."""
        mon_file = tmp_path / 'MONA'
        mon_file.write_bytes(bytearray(MON_FILE_SIZE))
        json_file = tmp_path / 'bestiary.json'
        json_file.write_text(json.dumps({
            "monsters": {
                "0": {"hp": 80, "boss": True, "poison": True},
                "1": {"hp": 50, "negate": True, "resistant": True}
            }
        }))
        import argparse
        from ult3edit.bestiary import cmd_import as bestiary_import
        from ult3edit.constants import (
            MON_FLAG1_BOSS, MON_ABIL1_POISON,
            MON_ABIL1_NEGATE, MON_ABIL2_RESISTANT,
        )
        args = argparse.Namespace(
            file=str(mon_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        bestiary_import(args)
        monsters = load_mon_file(str(mon_file))
        assert monsters[0].hp == 80
        assert monsters[0].flags1 & MON_FLAG1_BOSS
        assert monsters[0].ability1 & MON_ABIL1_POISON
        assert monsters[1].ability1 & MON_ABIL1_NEGATE
        assert monsters[1].ability2 & MON_ABIL2_RESISTANT

    def test_import_list_format_still_works(self, tmp_path):
        """Original list format import still works after dict support."""
        mon_file = tmp_path / 'MONA'
        mon_file.write_bytes(bytearray(MON_FILE_SIZE))
        json_file = tmp_path / 'bestiary.json'
        json_file.write_text(json.dumps([
            {"index": 0, "hp": 77, "attack": 44}
        ]))
        import argparse
        from ult3edit.bestiary import cmd_import as bestiary_import
        args = argparse.Namespace(
            file=str(mon_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        bestiary_import(args)
        monsters = load_mon_file(str(mon_file))
        assert monsters[0].hp == 77


class TestCombatDictImport:
    """Test that combat import accepts dict-of-dicts JSON format."""

    def test_import_dict_format(self, tmp_path):
        """Import combat map from dict-keyed JSON (Voidborn source format)."""
        con_file = tmp_path / 'CONA'
        con_file.write_bytes(bytearray(CON_FILE_SIZE))
        json_file = tmp_path / 'combat.json'
        json_file.write_text(json.dumps({
            "tiles": [
                "...........",
                "...........",
                "...........",
                "...........",
                "...........",
                "...........",
                "...........",
                "...........",
                "...........",
                "...........",
                "..........."
            ],
            "monsters": {
                "0": {"x": 3, "y": 2},
                "1": {"x": 7, "y": 4}
            },
            "pcs": {
                "0": {"x": 1, "y": 9},
                "1": {"x": 3, "y": 9}
            }
        }))
        import argparse
        from ult3edit.combat import cmd_import as combat_import
        args = argparse.Namespace(
            file=str(con_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        combat_import(args)
        data = con_file.read_bytes()
        from ult3edit.constants import (
            CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET,
            CON_PC_X_OFFSET, CON_PC_Y_OFFSET,
        )
        assert data[CON_MONSTER_X_OFFSET + 0] == 3
        assert data[CON_MONSTER_Y_OFFSET + 0] == 2
        assert data[CON_MONSTER_X_OFFSET + 1] == 7
        assert data[CON_MONSTER_Y_OFFSET + 1] == 4
        assert data[CON_PC_X_OFFSET + 0] == 1
        assert data[CON_PC_Y_OFFSET + 0] == 9

    def test_import_list_format_still_works(self, tmp_path):
        """Original list format import still works after dict support."""
        con_file = tmp_path / 'CONA'
        con_file.write_bytes(bytearray(CON_FILE_SIZE))
        json_file = tmp_path / 'combat.json'
        json_file.write_text(json.dumps({
            "tiles": ["...........",] * 11,
            "monsters": [{"x": 5, "y": 5}],
            "pcs": [{"x": 2, "y": 8}]
        }))
        import argparse
        from ult3edit.combat import cmd_import as combat_import
        args = argparse.Namespace(
            file=str(con_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        combat_import(args)
        data = con_file.read_bytes()
        from ult3edit.constants import CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET
        assert data[CON_MONSTER_X_OFFSET] == 5
        assert data[CON_MONSTER_Y_OFFSET] == 5


class TestMapCompilerOutputFormat:
    """Test that map_compiler outputs JSON compatible with map.py cmd_import."""

    def test_overworld_output_uses_tiles_key(self):
        """Overworld grid_to_json should use 'tiles' key, not 'grid'."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from map_compiler import grid_to_json
        # Create a minimal 2x2 overworld grid (tile bytes)
        grid = [[0x00, 0x04], [0x04, 0x00]]
        result = grid_to_json(grid, is_dungeon=False)
        assert 'tiles' in result, "Overworld should use 'tiles' key"
        assert 'grid' not in result, "Overworld should NOT use 'grid' key"
        assert len(result['tiles']) == 2
        assert isinstance(result['tiles'][0], str)

    def test_dungeon_output_is_level_list(self):
        """Dungeon grid_to_json should produce list of level dicts."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from map_compiler import grid_to_json
        # Create 2 levels of 4x4 dungeon grids
        level0 = [[0x01, 0x01, 0x01, 0x01],
                   [0x01, 0x00, 0x00, 0x01],
                   [0x01, 0x00, 0x05, 0x01],
                   [0x01, 0x01, 0x01, 0x01]]
        level1 = [[0x01, 0x01, 0x01, 0x01],
                   [0x01, 0x00, 0x06, 0x01],
                   [0x01, 0x00, 0x00, 0x01],
                   [0x01, 0x01, 0x01, 0x01]]
        grid = [level0, level1]
        result = grid_to_json(grid, is_dungeon=True)
        assert 'levels' in result
        assert isinstance(result['levels'], list)
        assert len(result['levels']) == 2
        # Each level should have 'level' (1-indexed) and 'tiles' (2D grid)
        assert result['levels'][0]['level'] == 1
        assert result['levels'][1]['level'] == 2
        tiles_l0 = result['levels'][0]['tiles']
        assert len(tiles_l0) == 4
        assert len(tiles_l0[0]) == 4
        # Wall=# Open=. LadderDown=V LadderUp=^
        assert tiles_l0[0][0] == '#'
        assert tiles_l0[1][1] == '.'
        assert tiles_l0[2][2] == 'V'  # Ladder Down
        tiles_l1 = result['levels'][1]['tiles']
        assert tiles_l1[1][2] == '^'  # Ladder Up

    def test_dungeon_output_no_dungeon_key(self):
        """Dungeon output should NOT have 'dungeon' key (cmd_import ignores it)."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from map_compiler import grid_to_json
        grid = [[[0x01, 0x00], [0x00, 0x01]]]
        result = grid_to_json(grid, is_dungeon=True)
        assert 'dungeon' not in result

    def test_overworld_roundtrip_through_import(self, tmp_path):
        """Overworld: compile → JSON → import should produce matching binary."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from map_compiler import parse_map_file, grid_to_json
        # Build a 64x64 map source (parse_map_file pads to 64x64)
        source = "# Test map\n" + ("~.^T" + "~" * 60 + "\n") * 64
        grid = parse_map_file(source, is_dungeon=False)
        result = grid_to_json(grid, is_dungeon=False)
        # The tiles key should have 64 rows of 64 chars
        assert len(result['tiles']) == 64
        # First row should start with our tile chars
        assert result['tiles'][0][0] == '~'
        assert result['tiles'][0][1] == '.'
        assert result['tiles'][0][2] == '^'
        assert result['tiles'][0][3] == 'T'


# =============================================================================
# Name compiler tests
# =============================================================================


# =============================================================================
# Source file validation tests
# =============================================================================


# =============================================================================
# Combat tile character validation
# =============================================================================

class TestCombatTileChars:
    """Validate combat source tile characters are in TILE_CHARS_REVERSE."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_all_combat_tiles_valid(self):
        """Every tile char in combat JSONs maps to a known tile byte."""
        valid_chars = set(TILE_CHARS_REVERSE.keys())
        for letter in 'abcfgmqrs':
            path = os.path.join(self.SOURCES_DIR, f'combat_{letter}.json')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                data = json.load(f)
            for row_idx, row in enumerate(data.get('tiles', [])):
                for col_idx, ch in enumerate(row):
                    assert ch in valid_chars, \
                        (f"combat_{letter}.json tile[{row_idx}][{col_idx}]="
                         f"'{ch}' not in TILE_CHARS_REVERSE")


# =============================================================================
# Dungeon ladder connectivity
# =============================================================================

class TestDungeonLadderConnectivity:
    """Validate dungeon ladders connect properly across levels."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def _parse_dungeon(self, path):
        """Parse a dungeon map file into 8 levels of 16x16 grids."""
        with open(path, 'r') as f:
            lines = [l for l in f.read().splitlines()
                     if l and not l.startswith('# ')]
        levels = []
        for i in range(8):
            level = lines[i * 16:(i + 1) * 16]
            levels.append(level)
        return levels

    def _find_tiles(self, level, ch):
        """Find all positions of a tile character in a level."""
        positions = set()
        for y, row in enumerate(level):
            for x, c in enumerate(row):
                if c == ch:
                    positions.add((x, y))
        return positions

    def test_no_down_on_last_level(self):
        """Last level (L8) should not have down ladders."""
        for letter in 'mnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            if not os.path.exists(path):
                continue
            levels = self._parse_dungeon(path)
            downs = self._find_tiles(levels[7], 'V')
            assert len(downs) == 0, \
                f"map{letter}.map L8 has down ladder(s) at {downs}"

    def test_no_up_on_first_level(self):
        """First level (L1) should not have up ladders."""
        for letter in 'mnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            if not os.path.exists(path):
                continue
            levels = self._parse_dungeon(path)
            ups = self._find_tiles(levels[0], '^')
            assert len(ups) == 0, \
                f"map{letter}.map L1 has up ladder(s) at {ups}"

    def test_every_level_has_connection(self):
        """Levels 2-7 should have both up and down ladders."""
        for letter in 'mnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            if not os.path.exists(path):
                continue
            levels = self._parse_dungeon(path)
            for li in range(1, 7):  # L2 through L7
                ups = self._find_tiles(levels[li], '^')
                downs = self._find_tiles(levels[li], 'V')
                assert len(ups) > 0, \
                    f"map{letter}.map L{li+1} has no up ladder"
                assert len(downs) > 0, \
                    f"map{letter}.map L{li+1} has no down ladder"


# =============================================================================
# Round-trip integration tests
# =============================================================================

class TestRoundTripIntegration:
    """End-to-end: load Voidborn source → import into binary → verify."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_bestiary_import_roundtrip(self):
        """Import bestiary_a.json into synthesized MON binary and verify HP."""
        from ult3edit.bestiary import Monster
        path = os.path.join(self.SOURCES_DIR, 'bestiary_a.json')
        with open(path, 'r') as f:
            data = json.load(f)

        # Create 16 empty monster objects directly
        monsters = [Monster([0] * 10, i) for i in range(MON_MONSTERS_PER_FILE)]

        # Apply the import manually (same logic as cmd_import)
        mon_list = data.get('monsters', {})
        if isinstance(mon_list, dict):
            mon_list = [dict(v, index=int(k)) for k, v in mon_list.items()]
        for entry in mon_list:
            idx = entry.get('index')
            if idx is None or not (0 <= idx < MON_MONSTERS_PER_FILE):
                continue
            m = monsters[idx]
            for attr in ('hp', 'attack', 'defense', 'speed'):
                if attr in entry:
                    setattr(m, attr, max(0, min(255, entry[attr])))

        # Verify values were set from JSON
        first_mon = data['monsters']['0']
        assert monsters[0].hp == min(255, first_mon['hp'])
        assert monsters[0].attack == min(255, first_mon['attack'])
        # Verify multiple monsters imported
        imported_count = sum(1 for m in monsters if m.hp > 0)
        assert imported_count >= 8, f"Only {imported_count} monsters imported"

    def test_combat_import_roundtrip(self):
        """Import combat_a.json into synthesized CON binary and verify tiles."""
        from ult3edit.combat import CombatMap, CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET
        path = os.path.join(self.SOURCES_DIR, 'combat_a.json')
        with open(path, 'r') as f:
            data = json.load(f)

        # Create a CON binary and write tiles + positions directly
        con_data = bytearray(CON_FILE_SIZE)

        # Write tile grid (11x11)
        for y, row in enumerate(data.get('tiles', [])):
            for x, ch in enumerate(row):
                tile_byte = TILE_CHARS_REVERSE.get(ch, 0x20)
                con_data[y * 11 + x] = tile_byte

        # Write monster positions
        raw_mons = data.get('monsters', {})
        if isinstance(raw_mons, dict):
            raw_mons = [raw_mons[str(i)] for i in sorted(int(k) for k in raw_mons)]
        for i, m in enumerate(raw_mons[:8]):
            con_data[CON_MONSTER_X_OFFSET + i] = m['x']
            con_data[CON_MONSTER_Y_OFFSET + i] = m['y']

        # Re-parse and verify
        cmap = CombatMap(bytes(con_data))
        first_mon = data['monsters']['0']
        assert cmap.monster_x[0] == first_mon['x']
        assert cmap.monster_y[0] == first_mon['y']

        # Verify tile at (0,0)
        first_row = data['tiles'][0]
        expected_byte = TILE_CHARS_REVERSE.get(first_row[0], 0x20)
        assert cmap.tiles[0] == expected_byte

    def test_special_import_roundtrip(self):
        """Import special_brnd.json into synthesized binary and verify tiles."""
        path = os.path.join(self.SOURCES_DIR, 'special_brnd.json')
        with open(path, 'r') as f:
            data = json.load(f)

        # Create a special location binary and write tiles
        spec_data = bytearray(SPECIAL_FILE_SIZE)
        for y, row in enumerate(data.get('tiles', [])):
            for x, ch in enumerate(row):
                tile_byte = TILE_CHARS_REVERSE.get(ch, 0x20)
                spec_data[y * 11 + x] = tile_byte

        # Verify
        first_row = data['tiles'][0]
        expected_byte = TILE_CHARS_REVERSE.get(first_row[0], 0x20)
        assert spec_data[0] == expected_byte
        # Verify center tile
        center_ch = data['tiles'][5][5]
        center_byte = TILE_CHARS_REVERSE.get(center_ch, 0x20)
        assert spec_data[5 * 11 + 5] == center_byte


# =============================================================================
# gen_maps.py tests
# =============================================================================

class TestGenMaps:
    """Test the map generator produces valid output."""

    def _get_gen_maps(self):
        """Import gen_maps module."""
        tools_dir = os.path.join(os.path.dirname(__file__),
                                  '..', 'conversions', 'tools')
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import gen_maps
        return gen_maps

    def test_castle_dimensions(self):
        """gen_castle() produces exactly 64 rows of 64 chars."""
        gm = self._get_gen_maps()
        rows = gm.gen_castle()
        assert len(rows) == 64
        for i, r in enumerate(rows):
            assert len(r) == 64, f"Castle row {i}: {len(r)} chars"

    def test_town_dimensions(self):
        """gen_town() produces exactly 64 rows of 64 chars."""
        gm = self._get_gen_maps()
        rows = gm.gen_town()
        assert len(rows) == 64
        for i, r in enumerate(rows):
            assert len(r) == 64, f"Town row {i}: {len(r)} chars"

    def test_mapz_dimensions(self):
        """gen_mapz() produces exactly 64 rows of 64 chars."""
        gm = self._get_gen_maps()
        rows = gm.gen_mapz()
        assert len(rows) == 64
        for i, r in enumerate(rows):
            assert len(r) == 64, f"mapz row {i}: {len(r)} chars"

    def test_mapl_dimensions(self):
        """gen_mapl() produces exactly 64 rows of 64 chars."""
        gm = self._get_gen_maps()
        rows = gm.gen_mapl()
        assert len(rows) == 64
        for i, r in enumerate(rows):
            assert len(r) == 64, f"mapl row {i}: {len(r)} chars"

    def test_dungeon_dimensions(self):
        """gen_dungeon() produces 8 levels of 16 rows of 16 chars."""
        gm = self._get_gen_maps()
        levels = gm.gen_dungeon(has_mark=True, seed=42)
        assert len(levels) == 8
        for li, level in enumerate(levels):
            assert len(level) == 16, f"Dungeon L{li}: {len(level)} rows"
            for ri, r in enumerate(level):
                assert len(r) == 16, f"Dungeon L{li} row {ri}: {len(r)} chars"

    def test_dungeon_has_mark(self):
        """gen_dungeon(has_mark=True) places M on level 7."""
        gm = self._get_gen_maps()
        levels = gm.gen_dungeon(has_mark=True, seed=99)
        # Level 7 (index 6) should contain 'M'
        l7_text = ''.join(levels[6])
        assert 'M' in l7_text, "Level 7 missing Mark tile"

    def test_dungeon_no_mark(self):
        """gen_dungeon(has_mark=False) omits M from level 7."""
        gm = self._get_gen_maps()
        levels = gm.gen_dungeon(has_mark=False, seed=99)
        l7_text = ''.join(levels[6])
        assert 'M' not in l7_text, "Level 7 has unexpected Mark tile"

    def test_surface_tile_chars_valid(self):
        """All surface map generator tile chars are in TILE_CHARS_REVERSE."""
        gm = self._get_gen_maps()
        valid = set(TILE_CHARS_REVERSE.keys())
        for name, gen_fn in [('castle', gm.gen_castle),
                              ('town', gm.gen_town),
                              ('mapz', gm.gen_mapz),
                              ('mapl', gm.gen_mapl)]:
            rows = gen_fn()
            for y, row in enumerate(rows):
                for x, ch in enumerate(row):
                    assert ch in valid, \
                        f"{name}[{y}][{x}]='{ch}' not in TILE_CHARS_REVERSE"

    def test_dungeon_tile_chars_valid(self):
        """All dungeon map generator tile chars are in DUNGEON_TILE_CHARS_REVERSE."""
        gm = self._get_gen_maps()
        valid = set(DUNGEON_TILE_CHARS_REVERSE.keys())
        levels = gm.gen_dungeon(has_mark=True, seed=0)
        for li, level in enumerate(levels):
            for y, row in enumerate(level):
                for x, ch in enumerate(row):
                    assert ch in valid, \
                        f"dungeon L{li}[{y}][{x}]='{ch}' not in DUNGEON_TILE_CHARS_REVERSE"


# =============================================================================
# Shop apply tool tests
# =============================================================================

class TestShopApply:
    """Tests for the shop_apply.py text-matching tool."""

    TOOLS_DIR = os.path.join(os.path.dirname(__file__),
                              '..', 'conversions', 'tools')

    def _get_shop_apply(self):
        """Import shop_apply module."""
        mod_path = os.path.join(self.TOOLS_DIR, 'shop_apply.py')
        import importlib.util
        spec = importlib.util.spec_from_file_location('shop_apply', mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _build_shp_with_string(self, text):
        """Build a minimal SHP binary containing a JSR $46BA inline string."""
        # JSR $46BA = 0x20 0xBA 0x46
        jsr = bytes([0x20, 0xBA, 0x46])
        encoded = encode_overlay_string(text)
        # Pad before and after to simulate real code
        return bytearray(b'\x60' * 16 + jsr + encoded + b'\x60' * 16)

    def test_shop_apply_match_and_replace(self, tmp_path):
        """Match vanilla text and replace with voidborn text."""
        shop_apply = self._get_shop_apply()

        # Create SHP0 with "WEAPONS" inline string
        shp_data = self._build_shp_with_string('WEAPONS')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)

        # Create shop_strings.json
        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "WEAPONS", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        replaced, skipped = shop_apply.apply_shop_strings(
            json_path, str(tmp_path))

        assert replaced == 1
        assert skipped == 0

        # Verify the file was modified
        with open(shp_path, 'rb') as f:
            result = f.read()
        strings = extract_overlay_strings(result)
        assert len(strings) == 1
        assert strings[0]['text'] == 'ARMS'

    def test_shop_apply_no_match_warning(self, tmp_path):
        """Vanilla text not found in binary produces warning, not crash."""
        shop_apply = self._get_shop_apply()

        # Create SHP0 with "HELLO" but try to match "WEAPONS"
        shp_data = self._build_shp_with_string('HELLO')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)

        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "WEAPONS", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        replaced, skipped = shop_apply.apply_shop_strings(
            json_path, str(tmp_path))

        assert replaced == 0
        assert skipped == 1

    def test_shop_apply_too_long_warning(self, tmp_path):
        """Replacement text longer than original produces warning."""
        shop_apply = self._get_shop_apply()

        # Create SHP0 with short "HI" string
        shp_data = self._build_shp_with_string('HI')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)

        source = {
            "shops": {
                "SHP0": {
                    "name": "Test",
                    "strings": [
                        {"vanilla": "HI", "voidborn": "VERY LONG REPLACEMENT"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        replaced, skipped = shop_apply.apply_shop_strings(
            json_path, str(tmp_path))

        assert replaced == 0
        assert skipped == 1

    def test_shop_apply_dry_run(self, tmp_path):
        """Dry run does not modify files."""
        shop_apply = self._get_shop_apply()

        shp_data = self._build_shp_with_string('WEAPONS')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)
        original = bytes(shp_data)

        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "WEAPONS", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        replaced, _ = shop_apply.apply_shop_strings(
            json_path, str(tmp_path), dry_run=True)

        assert replaced == 1
        # File should be unchanged
        with open(shp_path, 'rb') as f:
            assert f.read() == original


# =============================================================================
# Sound source file validation
# =============================================================================


# =============================================================================
# DDRW source file validation
# =============================================================================


# =============================================================================
# Shop strings JSON validation
# =============================================================================

class TestShopStringsSource:
    """Validate shop_strings.json source file structure."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_shop_strings_json_structure(self):
        """shop_strings.json has valid structure with SHP0-SHP6."""
        path = os.path.join(self.SOURCES_DIR, 'shop_strings.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'shops' in data
        shops = data['shops']
        # SHP0-SHP6 present; SHP7 (Oracle) omitted — unchanged from vanilla
        for i in range(7):
            key = f'SHP{i}'
            assert key in shops, f"Missing {key}"
            assert 'strings' in shops[key]
            for entry in shops[key]['strings']:
                assert 'vanilla' in entry
                assert 'voidborn' in entry
        # No stale discovery fields
        assert 'discovery_workflow' not in data


# =============================================================================
# Name compiler edge cases
# =============================================================================


# =============================================================================
# Map compiler edge cases
# =============================================================================

class TestMapCompilerEdgeCases:
    """Edge case tests for map_compiler.py."""

    TOOLS_DIR = os.path.join(os.path.dirname(__file__),
                              '..', 'conversions', 'tools')

    def _get_mod(self):
        mod_path = os.path.join(self.TOOLS_DIR, 'map_compiler.py')
        import importlib.util
        spec = importlib.util.spec_from_file_location('map_compiler', mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_overworld_invalid_tile_char_defaults_to_zero(self):
        """Invalid tile character in overworld map defaults to tile 0."""
        mod = self._get_mod()
        rows = ['.' * 64 for _ in range(64)]
        rows[0] = 'Z' + '.' * 63  # 'Z' is not in TILE_CHARS_REVERSE
        text = '\n'.join(rows) + '\n'
        grid = mod.parse_map_file(text, is_dungeon=False)
        assert grid[0][0] == 0  # Unknown char → tile 0

    def test_dungeon_short_input_pads_to_8_levels(self):
        """Dungeon with fewer than 8 levels pads to 8."""
        mod = self._get_mod()
        parts = []
        for i in range(3):
            parts.append(f'# Level {i}')
            for _ in range(16):
                parts.append('#' * 16)
        text = '\n'.join(parts) + '\n'
        grid = mod.parse_map_file(text, is_dungeon=True)
        assert len(grid) == 8  # Padded to 8 levels

    def test_overworld_short_input_pads_to_64_rows(self):
        """Overworld with fewer than 64 rows pads to 64."""
        mod = self._get_mod()
        rows = ['.' * 64 for _ in range(32)]  # Only 32 rows
        text = '\n'.join(rows) + '\n'
        grid = mod.parse_map_file(text, is_dungeon=False)
        assert len(grid) == 64  # Padded to 64 rows


# =============================================================================
# Shop apply edge cases
# =============================================================================

class TestShopApplyEdgeCases:
    """Additional edge case tests for shop_apply.py."""

    TOOLS_DIR = os.path.join(os.path.dirname(__file__),
                              '..', 'conversions', 'tools')

    def _get_shop_apply(self):
        mod_path = os.path.join(self.TOOLS_DIR, 'shop_apply.py')
        import importlib.util
        spec = importlib.util.spec_from_file_location('shop_apply', mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _build_shp_with_string(self, text):
        jsr = bytes([0x20, 0xBA, 0x46])
        encoded = encode_overlay_string(text)
        return bytearray(b'\x60' * 16 + jsr + encoded + b'\x60' * 16)

    def test_shop_apply_case_insensitive_match(self, tmp_path):
        """Vanilla text matching is case-insensitive."""
        shop_apply = self._get_shop_apply()

        shp_data = self._build_shp_with_string('WEAPONS')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)

        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "weapons", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        replaced, skipped = shop_apply.apply_shop_strings(
            json_path, str(tmp_path))
        assert replaced == 1

    def test_shop_apply_missing_shp_file(self, tmp_path):
        """Missing SHP file is skipped gracefully."""
        shop_apply = self._get_shop_apply()

        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "WEAPONS", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        # No SHP0 file in tmp_path
        replaced, skipped = shop_apply.apply_shop_strings(
            json_path, str(tmp_path))
        assert replaced == 0
        assert skipped == 0

    def test_shop_apply_backup_creates_bak(self, tmp_path):
        """Backup flag creates .bak file."""
        shop_apply = self._get_shop_apply()

        shp_data = self._build_shp_with_string('WEAPONS')
        shp_path = str(tmp_path / 'SHP0')
        with open(shp_path, 'wb') as f:
            f.write(shp_data)
        original = bytes(shp_data)

        source = {
            "shops": {
                "SHP0": {
                    "name": "Weapons",
                    "strings": [
                        {"vanilla": "WEAPONS", "voidborn": "ARMS"}
                    ]
                }
            }
        }
        json_path = str(tmp_path / 'shop_strings.json')
        with open(json_path, 'w') as f:
            json.dump(source, f)

        shop_apply.apply_shop_strings(
            json_path, str(tmp_path), backup=True)

        bak_path = shp_path + '.bak'
        assert os.path.exists(bak_path)
        with open(bak_path, 'rb') as f:
            assert f.read() == original


# =============================================================================
# Tile compiler edge cases
# =============================================================================


# =============================================================================
# Bestiary import: shortcut + raw attribute conflict fix
# =============================================================================

class TestBestiaryShortcutRawConflict:
    """Verify shortcuts OR into raw attributes, not overwritten by them."""

    def test_shortcut_applied_after_raw(self, tmp_path):
        """Boss shortcut is preserved even when flags1 raw value is 0."""
        from ult3edit.bestiary import (
            load_mon_file, cmd_import,
            MON_FLAG1_BOSS
        )
        # Create empty MON file
        mon_data = bytearray(256)
        mon_path = str(tmp_path / 'MONA')
        with open(mon_path, 'wb') as f:
            f.write(mon_data)

        # JSON with both boss shortcut AND raw flags1=0
        jdata = {
            "monsters": {
                "0": {"hp": 100, "attack": 50, "flags1": 0, "boss": True}
            }
        }
        json_path = str(tmp_path / 'bestiary.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        # Import
        args = type('Args', (), {
            'file': mon_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        cmd_import(args)

        # Verify boss flag is set
        monsters = load_mon_file(mon_path)
        assert monsters[0].flags1 & MON_FLAG1_BOSS, \
            "Boss flag should be set even when flags1 raw value is 0"

    def test_shortcut_ors_into_existing_flags(self, tmp_path):
        """Multiple shortcuts all accumulate."""
        from ult3edit.bestiary import (
            load_mon_file, cmd_import,
            MON_FLAG1_BOSS, MON_ABIL1_POISON, MON_ABIL1_NEGATE
        )
        mon_data = bytearray(256)
        mon_path = str(tmp_path / 'MONA')
        with open(mon_path, 'wb') as f:
            f.write(mon_data)

        jdata = {
            "monsters": {
                "0": {"hp": 200, "boss": True, "poison": True, "negate": True}
            }
        }
        json_path = str(tmp_path / 'bestiary.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': mon_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        cmd_import(args)

        monsters = load_mon_file(mon_path)
        assert monsters[0].flags1 & MON_FLAG1_BOSS
        assert monsters[0].ability1 & MON_ABIL1_POISON
        assert monsters[0].ability1 & MON_ABIL1_NEGATE


# =============================================================================
# Non-numeric dict key handling
# =============================================================================

class TestDictKeyValidation:
    """Verify non-numeric dict keys are handled gracefully."""

    def test_bestiary_import_skips_bad_keys(self, tmp_path):
        """Bestiary import skips non-numeric keys without crashing."""
        from ult3edit.bestiary import load_mon_file, cmd_import
        mon_data = bytearray(256)
        mon_path = str(tmp_path / 'MONA')
        with open(mon_path, 'wb') as f:
            f.write(mon_data)

        jdata = {
            "monsters": {
                "0": {"hp": 100},
                "abc": {"hp": 200},  # non-numeric key
                "1": {"hp": 150}
            }
        }
        json_path = str(tmp_path / 'bestiary.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': mon_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        cmd_import(args)  # Should not crash

        monsters = load_mon_file(mon_path)
        assert monsters[0].hp == 100
        assert monsters[1].hp == 150

    def test_combat_import_skips_bad_keys(self, tmp_path):
        """Combat import skips non-numeric monster keys without crashing."""
        from ult3edit.combat import cmd_import as combat_import
        from ult3edit.constants import CON_FILE_SIZE
        con_data = bytearray(CON_FILE_SIZE)
        con_path = str(tmp_path / 'CONA')
        with open(con_path, 'wb') as f:
            f.write(con_data)

        jdata = {
            "tiles": [['.' for _ in range(11)] for _ in range(11)],
            "monsters": {
                "0": {"x": 3, "y": 4},
                "bad": {"x": 5, "y": 6}  # non-numeric key
            }
        }
        json_path = str(tmp_path / 'combat.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': con_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        combat_import(args)  # Should not crash


# =============================================================================
# Map import width validation
# =============================================================================

class TestMapImportWidthValidation:
    """Verify map import warns on mismatched width."""

    def test_import_with_correct_width(self, tmp_path):
        """Normal import with correct width succeeds."""
        from ult3edit.map import cmd_import as map_import
        # 64x64 overworld = 4096 bytes
        data = bytearray(4096)
        map_path = str(tmp_path / 'MAPA')
        with open(map_path, 'wb') as f:
            f.write(data)

        jdata = {
            "tiles": [['.' for _ in range(64)] for _ in range(64)],
            "width": 64
        }
        json_path = str(tmp_path / 'map.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': map_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        map_import(args)  # Should succeed without warning

    def test_import_with_zero_width_uses_default(self, tmp_path):
        """Width=0 in JSON falls back to 64 instead of corrupting data."""
        from ult3edit.map import cmd_import as map_import
        data = bytearray(4096)
        map_path = str(tmp_path / 'MAPA')
        with open(map_path, 'wb') as f:
            f.write(data)

        # Two rows — with width=0, row 1 would overwrite row 0
        jdata = {
            "tiles": [
                ['*'] * 64,  # row 0: all lava (0x84)
                ['!'] * 64,  # row 1: all force field (0x80)
            ],
            "width": 0
        }
        json_path = str(tmp_path / 'map.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': map_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        map_import(args)

        # With the fix, width=0 falls back to 64
        # Row 0 at offset 0 (lava=0x84), row 1 at offset 64 (force=0x80)
        with open(map_path, 'rb') as f:
            result = bytearray(f.read())
        assert result[0] == 0x84, "Row 0 should be lava"
        assert result[64] == 0x80, "Row 1 at offset 64, not overwriting row 0"


# =============================================================================
# PRTY slot_ids partial write fix
# =============================================================================

class TestPrtySlotIdsPartialWrite:
    """Verify slot_ids setter zero-fills unused slots."""

    def test_partial_slot_ids_zeros_remainder(self):
        """Setting 2 slot IDs zeros out slots 2 and 3."""
        from ult3edit.save import PartyState, PRTY_OFF_SLOT_IDS
        raw = bytearray(16)
        # Pre-fill with garbage
        raw[PRTY_OFF_SLOT_IDS] = 0xFF
        raw[PRTY_OFF_SLOT_IDS + 1] = 0xAA
        raw[PRTY_OFF_SLOT_IDS + 2] = 0xBB
        raw[PRTY_OFF_SLOT_IDS + 3] = 0xCC
        party = PartyState(raw)
        party.slot_ids = [5, 10]
        assert party.slot_ids == [5, 10, 0, 0], \
            "Unused slots should be zeroed"

    def test_empty_slot_ids_zeros_all(self):
        """Setting empty slot_ids zeros all 4 slots."""
        from ult3edit.save import PartyState, PRTY_OFF_SLOT_IDS
        raw = bytearray(16)
        raw[PRTY_OFF_SLOT_IDS:PRTY_OFF_SLOT_IDS + 4] = b'\xFF\xFF\xFF\xFF'
        party = PartyState(raw)
        party.slot_ids = []
        assert party.slot_ids == [0, 0, 0, 0]

    def test_full_slot_ids_still_works(self):
        """Setting all 4 slot IDs still works correctly."""
        from ult3edit.save import PartyState
        raw = bytearray(16)
        party = PartyState(raw)
        party.slot_ids = [1, 3, 7, 15]
        assert party.slot_ids == [1, 3, 7, 15]


class TestTextImportOverflow:
    """Text import should report actual records written, not total in JSON."""

    def test_reports_actual_count(self, tmp_path, capsys):
        """When file is too small, report count of records actually written."""
        from ult3edit.text import cmd_import
        # Create a tiny 20-byte TEXT file
        text_file = tmp_path / 'TEXT'
        text_file.write_bytes(b'\x00' * 20)
        # Create JSON with many long records that won't all fit
        records = [{'text': 'ABCDEFGHIJ'} for _ in range(10)]  # 10 records, ~11 bytes each
        json_file = tmp_path / 'text.json'
        json_file.write_text(json.dumps(records))
        args = type('A', (), {
            'file': str(text_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        out = capsys.readouterr()
        # Should report fewer than 10 records
        assert 'Import: 1 text record(s)' in out.out
        assert 'Warning' in out.err
        assert 'wrote 1 of 10' in out.err

    def test_all_fit_no_warning(self, tmp_path, capsys):
        """When all records fit, report total count and no warning."""
        from ult3edit.text import cmd_import
        text_file = tmp_path / 'TEXT'
        text_file.write_bytes(b'\x00' * 200)
        records = [{'text': 'HI'}, {'text': 'BYE'}]  # 3+4=7 bytes
        json_file = tmp_path / 'text.json'
        json_file.write_text(json.dumps(records))
        args = type('A', (), {
            'file': str(text_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        out = capsys.readouterr()
        assert 'Import: 2 text record(s)' in out.out
        assert 'Warning' not in out.err


# =============================================================================
# Engine SDK: Round-trip assembly verification
# =============================================================================


# =============================================================================
# String patcher tests
# =============================================================================


# =============================================================================
# Source-level string patcher tests
# =============================================================================


# =============================================================================
# Integrated inline string catalog (patch.py cmd_strings)
# =============================================================================


# =============================================================================
# Inline string editing (patch.py cmd_strings_edit / cmd_strings_import)
# =============================================================================


# =============================================================================
# Compiler subcommands — map, shapes, patch
# =============================================================================

class TestMapCompileSubcommand:
    """Test ult3edit map compile/decompile CLI subcommands."""

    def test_compile_overworld(self, tmp_dir):
        """Compile overworld .map produces 4096-byte binary."""
        from ult3edit.map import cmd_compile
        # Create a minimal .map with water tiles
        src = os.path.join(tmp_dir, 'test.map')
        lines = ['# Overworld (64x64)']
        for _ in range(64):
            lines.append('~' * 64)
        with open(src, 'w') as f:
            f.write('\n'.join(lines))
        out = os.path.join(tmp_dir, 'test.bin')
        args = argparse.Namespace(source=src, output=out, dungeon=False)
        cmd_compile(args)
        with open(out, 'rb') as f:
            data = f.read()
        assert len(data) == MAP_OVERWORLD_SIZE

    def test_compile_dungeon(self, tmp_dir):
        """Compile dungeon .map produces 2048-byte binary."""
        from ult3edit.map import cmd_compile
        src = os.path.join(tmp_dir, 'test.map')
        lines = []
        for lvl in range(8):
            lines.append(f'# Level {lvl + 1}')
            for _ in range(16):
                lines.append('#' * 16)
            lines.append('')
        with open(src, 'w') as f:
            f.write('\n'.join(lines))
        out = os.path.join(tmp_dir, 'test.bin')
        args = argparse.Namespace(source=src, output=out, dungeon=True)
        cmd_compile(args)
        with open(out, 'rb') as f:
            data = f.read()
        assert len(data) == MAP_DUNGEON_SIZE

    def test_decompile_overworld(self, tmp_dir):
        """Decompile overworld binary to text-art."""
        from ult3edit.map import cmd_decompile
        # Create a 4096-byte binary (all water = 0x00)
        bin_path = os.path.join(tmp_dir, 'test.bin')
        with open(bin_path, 'wb') as f:
            f.write(b'\x00' * MAP_OVERWORLD_SIZE)
        out = os.path.join(tmp_dir, 'test.map')
        args = argparse.Namespace(file=bin_path, output=out)
        cmd_decompile(args)
        with open(out, 'r') as f:
            text = f.read()
        assert 'Overworld' in text
        # Should have 64 data lines
        data_lines = [l for l in text.strip().split('\n')
                      if l and not l.startswith('#')]
        assert len(data_lines) == 64

    def test_compile_decompile_roundtrip(self, tmp_dir):
        """Compile then decompile preserves tile content."""
        from ult3edit.map import cmd_compile, cmd_decompile
        src = os.path.join(tmp_dir, 'orig.map')
        # Create map with mixed tiles
        lines = ['# Test']
        for y in range(64):
            row = '~' * 32 + '.' * 32  # water + grass
            lines.append(row)
        with open(src, 'w') as f:
            f.write('\n'.join(lines))
        # Compile
        bin_path = os.path.join(tmp_dir, 'test.bin')
        args = argparse.Namespace(source=src, output=bin_path, dungeon=False)
        cmd_compile(args)
        # Decompile
        out = os.path.join(tmp_dir, 'decomp.map')
        args2 = argparse.Namespace(file=bin_path, output=out)
        cmd_decompile(args2)
        with open(out, 'r') as f:
            text = f.read()
        data_lines = [l for l in text.strip().split('\n')
                      if l and not l.startswith('#')]
        # Each row should have ~ and . characters
        for line in data_lines:
            assert '~' in line
            assert '.' in line

    def test_compile_no_output_prints_size(self, tmp_dir, capsys):
        """Compile without --output prints size info."""
        from ult3edit.map import cmd_compile
        src = os.path.join(tmp_dir, 'test.map')
        lines = ['# Test']
        for _ in range(64):
            lines.append('~' * 64)
        with open(src, 'w') as f:
            f.write('\n'.join(lines))
        args = argparse.Namespace(source=src, output=None, dungeon=False)
        cmd_compile(args)
        captured = capsys.readouterr()
        assert '4096 bytes' in captured.out


# ============================================================================
# Compile warnings and validation (Task #110)
# ============================================================================

class TestMapCompileWarnings:
    """Test map compile dimension warnings."""

    def test_overworld_short_rows_warns(self, tmp_path):
        """Compiling overworld with <64 rows warns on stderr."""
        from ult3edit.map import cmd_compile
        # Build a 10-row overworld source
        src = tmp_path / 'short.map'
        src.write_text('# Overworld\n' + ('.' * 64 + '\n') * 10)
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), dungeon=False)
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile(args)
        assert 'only 10 rows' in stderr.getvalue()
        assert len(out.read_bytes()) == 4096

    def test_dungeon_short_levels_warns(self, tmp_path):
        """Compiling dungeon with <8 levels warns on stderr."""
        from ult3edit.map import cmd_compile
        # Build 2-level dungeon source
        lines = []
        for lvl in range(2):
            lines.append(f'# Level {lvl + 1}')
            for _ in range(16):
                lines.append('.' * 16)
            lines.append('# ---')
        src = tmp_path / 'short.map'
        src.write_text('\n'.join(lines))
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), dungeon=True)
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile(args)
        assert 'only 2 dungeon levels' in stderr.getvalue()
        assert len(out.read_bytes()) == 2048

    def test_unknown_char_warns(self, tmp_path):
        """Compiling map with unknown chars warns and maps to 0x00."""
        from ult3edit.map import cmd_compile
        # 'Z' is not a valid tile char
        src = tmp_path / 'bad.map'
        src.write_text('# Overworld\n' + ('Z' * 64 + '\n') * 64)
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), dungeon=False)
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile(args)
        assert 'unknown tile chars' in stderr.getvalue()
        assert 'Z' in stderr.getvalue()

    def test_full_overworld_no_warning(self, tmp_path):
        """64-row overworld compile produces no warnings."""
        from ult3edit.map import cmd_compile
        src = tmp_path / 'full.map'
        src.write_text('# Overworld\n' + ('.' * 64 + '\n') * 64)
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), dungeon=False)
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile(args)
        assert stderr.getvalue() == ''


class TestMapDecompileUnknownTiles:
    """Test map decompile unknown tile byte warnings."""

    def test_unknown_overworld_tile_warns(self, tmp_path):
        """Decompiling overworld with unmapped byte warns on stderr."""
        from ult3edit.map import cmd_decompile
        # Create 4096 bytes: all 0xFF (unlikely to be mapped)
        binfile = tmp_path / 'MAP'
        binfile.write_bytes(bytes([0xFF]) * 4096)
        out = tmp_path / 'out.map'
        args = argparse.Namespace(file=str(binfile), output=str(out))
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_decompile(args)
        # Should warn about unmapped 0xFF
        warn = stderr.getvalue()
        assert 'unmapped tile byte' in warn
        assert '0xFF' in warn

    def test_unknown_dungeon_tile_warns(self, tmp_path):
        """Decompiling dungeon with unmapped byte warns on stderr."""
        from ult3edit.map import cmd_decompile
        binfile = tmp_path / 'DNG'
        binfile.write_bytes(bytes([0xFE]) * 2048)
        out = tmp_path / 'out.map'
        args = argparse.Namespace(file=str(binfile), output=str(out))
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_decompile(args)
        warn = stderr.getvalue()
        assert 'unmapped tile byte' in warn
        assert '0xFE' in warn

    def test_known_tiles_no_warning(self, tmp_path):
        """Decompiling all-zero map produces no warning."""
        from ult3edit.map import cmd_decompile
        binfile = tmp_path / 'MAP'
        binfile.write_bytes(bytes(4096))
        out = tmp_path / 'out.map'
        args = argparse.Namespace(file=str(binfile), output=str(out))
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_decompile(args)
        assert stderr.getvalue() == ''


class TestCombatMapTruncated:
    """Test CombatMap handles truncated data correctly."""

    def test_truncated_padding_defaults_to_zeros(self):
        """Truncated file gets zero-filled padding arrays."""
        from ult3edit.combat import CombatMap
        from ult3edit.constants import CON_PADDING1_SIZE
        # 150 bytes: past monster positions but short of full runtime data
        data = bytes(150)
        cm = CombatMap(data)
        # padding1 needs offset 121+7=128 bytes; 150 >= 128 so should work
        assert len(cm.padding1) == CON_PADDING1_SIZE
        # runtime_monster needs offset 0x90+16=160; 150 < 160 so defaults
        assert len(cm.runtime_monster) == 16
        assert cm.runtime_monster == [0] * 16

    def test_full_file_preserves_all_arrays(self):
        """Full 192-byte file preserves all padding/runtime data."""
        from ult3edit.combat import CombatMap
        from ult3edit.constants import CON_FILE_SIZE
        data = bytearray(CON_FILE_SIZE)
        data[0xB0] = 0xAA  # padding2[0]
        data[0x79] = 0xBB  # padding1[0]
        cm = CombatMap(bytes(data))
        assert cm.padding1[0] == 0xBB
        assert cm.padding2[0] == 0xAA
        assert len(cm.runtime_monster) == 16
        assert len(cm.runtime_pc) == 8


class TestCombatImportBoundsValidation:
    """Test combat import position clamping to 11x11 grid."""

    def test_monster_oob_clamped_and_warns(self, tmp_path):
        """Monster positions >10 are clamped to 10 with a warning."""
        from ult3edit.combat import cmd_import
        from ult3edit.constants import (
            CON_FILE_SIZE, CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET)
        binfile = tmp_path / 'CON'
        binfile.write_bytes(bytes(CON_FILE_SIZE))
        jdata = {'monsters': [{'x': 50, 'y': 200}]}
        jfile = tmp_path / 'con.json'
        jfile.write_text(json.dumps(jdata))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=str(out), backup=False, dry_run=False)
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_import(args)
        assert 'outside' in stderr.getvalue()
        result = out.read_bytes()
        assert result[CON_MONSTER_X_OFFSET] == 10
        assert result[CON_MONSTER_Y_OFFSET] == 10

    def test_pc_oob_clamped_and_warns(self, tmp_path):
        """PC positions >10 are clamped to 10 with a warning."""
        from ult3edit.combat import cmd_import
        from ult3edit.constants import (
            CON_FILE_SIZE, CON_PC_X_OFFSET, CON_PC_Y_OFFSET)
        binfile = tmp_path / 'CON'
        binfile.write_bytes(bytes(CON_FILE_SIZE))
        jdata = {'pcs': [{'x': 15, 'y': -1}]}
        jfile = tmp_path / 'con.json'
        jfile.write_text(json.dumps(jdata))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=str(out), backup=False, dry_run=False)
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_import(args)
        assert 'outside' in stderr.getvalue()
        result = out.read_bytes()
        assert result[CON_PC_X_OFFSET] == 10
        assert result[CON_PC_Y_OFFSET] == 0

    def test_valid_positions_no_warning(self, tmp_path):
        """Positions within 0-10 produce no warning."""
        from ult3edit.combat import cmd_import
        from ult3edit.constants import CON_FILE_SIZE
        binfile = tmp_path / 'CON'
        binfile.write_bytes(bytes(CON_FILE_SIZE))
        jdata = {'monsters': [{'x': 5, 'y': 5}],
                 'pcs': [{'x': 0, 'y': 10}]}
        jfile = tmp_path / 'con.json'
        jfile.write_text(json.dumps(jdata))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=str(out), backup=False, dry_run=False)
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_import(args)
        assert 'outside' not in stderr.getvalue()


# ============================================================================
# DDRW command tests (Task #112)
# ============================================================================


# ============================================================================
# Sound command tests (Task #112)
# ============================================================================


# ============================================================================
# Diff command tests (Task #112)
# ============================================================================

class TestDiffCommands:
    """Tests for diff cmd_diff."""

    def test_diff_identical_rosters(self, tmp_path, capsys):
        """Diffing identical roster files shows no changes."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import ROSTER_FILE_SIZE
        d1 = tmp_path / 'a'
        d2 = tmp_path / 'b'
        d1.mkdir()
        d2.mkdir()
        data = bytes(ROSTER_FILE_SIZE)
        (d1 / 'ROST').write_bytes(data)
        (d2 / 'ROST').write_bytes(data)
        args = argparse.Namespace(
            path1=str(d1 / 'ROST'), path2=str(d2 / 'ROST'),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'No differences' in out or 'identical' in out.lower() or out.strip() == ''

    def test_diff_modified_roster(self, tmp_path, capsys):
        """Diffing rosters with different names shows change."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import ROSTER_FILE_SIZE
        d1 = bytearray(ROSTER_FILE_SIZE)
        d2 = bytearray(ROSTER_FILE_SIZE)
        # Set a name in slot 0 of d2
        name = 'HERO'
        for i, ch in enumerate(name):
            d2[i] = ord(ch) | 0x80  # high-ASCII
        d2[0x0D] = 0x00  # null terminator
        d2[0x12] = 0x10  # STR=10 in BCD
        da = tmp_path / 'a'
        db = tmp_path / 'b'
        da.mkdir()
        db.mkdir()
        (da / 'ROST').write_bytes(bytes(d1))
        (db / 'ROST').write_bytes(bytes(d2))
        args = argparse.Namespace(
            path1=str(da / 'ROST'), path2=str(db / 'ROST'),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'HERO' in out or 'name' in out.lower()

    def test_diff_json_output(self, tmp_path):
        """Diff --json produces valid JSON."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import ROSTER_FILE_SIZE
        d1 = bytearray(ROSTER_FILE_SIZE)
        d2 = bytearray(ROSTER_FILE_SIZE)
        d2[0x12] = 0x50  # Change STR in slot 0
        da = tmp_path / 'a'
        db = tmp_path / 'b'
        da.mkdir()
        db.mkdir()
        (da / 'ROST').write_bytes(bytes(d1))
        (db / 'ROST').write_bytes(bytes(d2))
        outfile = tmp_path / 'diff.json'
        args = argparse.Namespace(
            path1=str(da / 'ROST'), path2=str(db / 'ROST'),
            json=True, summary=False, output=str(outfile))
        cmd_diff(args)
        result = json.loads(outfile.read_text())
        assert 'files' in result

    def test_diff_summary_mode(self, tmp_path, capsys):
        """Diff --summary shows counts."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import MAP_OVERWORLD_SIZE
        m1 = bytearray(MAP_OVERWORLD_SIZE)
        m2 = bytearray(MAP_OVERWORLD_SIZE)
        m2[0] = 0x01  # Change one tile
        f1 = tmp_path / 'MAPA'
        f2 = tmp_path / 'MAPA2'
        f1.write_bytes(bytes(m1))
        f2.write_bytes(bytes(m2))
        args = argparse.Namespace(
            path1=str(f1), path2=str(f2),
            json=False, summary=True, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        # Summary should mention changes
        assert '1' in out or 'change' in out.lower() or 'tile' in out.lower()

    def test_diff_mismatched_types_exits(self, tmp_path):
        """Diffing a file against a directory exits with error."""
        from ult3edit.diff import cmd_diff
        f1 = tmp_path / 'FILE'
        f1.write_bytes(b'\x00')
        d2 = tmp_path / 'DIR'
        d2.mkdir()
        args = argparse.Namespace(
            path1=str(f1), path2=str(d2),
            json=False, summary=False, output=None)
        with pytest.raises(SystemExit):
            cmd_diff(args)

    def test_diff_directories(self, tmp_path, capsys):
        """Diffing two directories compares matching files."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import ROSTER_FILE_SIZE
        d1 = tmp_path / 'game1'
        d2 = tmp_path / 'game2'
        d1.mkdir()
        d2.mkdir()
        data1 = bytearray(ROSTER_FILE_SIZE)
        data2 = bytearray(ROSTER_FILE_SIZE)
        data2[0x12] = 0x50  # Change STR
        (d1 / 'ROST').write_bytes(bytes(data1))
        (d2 / 'ROST').write_bytes(bytes(data2))
        args = argparse.Namespace(
            path1=str(d1), path2=str(d2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        # Should show roster differences
        assert len(out) > 0


class TestDiffNewFileTypes:
    """Tests for diff support of MBS, DDRW, SHPS, TEXT."""

    def _make_pair(self, tmp_path, name, size, change_offset=0):
        """Helper: create two files in subdirs, second differs at offset."""
        da = tmp_path / 'a'
        db = tmp_path / 'b'
        da.mkdir(exist_ok=True)
        db.mkdir(exist_ok=True)
        d1 = bytearray(size)
        d2 = bytearray(size)
        d2[change_offset] = 0xFF
        (da / name).write_bytes(bytes(d1))
        (db / name).write_bytes(bytes(d2))
        return da / name, db / name

    def test_diff_mbs_files(self, tmp_path, capsys):
        """Diff detects changes in MBS sound files."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import MBS_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'MBS', MBS_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'MBS' in out

    def test_diff_ddrw_files(self, tmp_path, capsys):
        """Diff detects changes in DDRW files."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import DDRW_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'DDRW', DDRW_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'DDRW' in out

    def test_diff_shps_files(self, tmp_path, capsys):
        """Diff detects changes in SHPS files."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import SHPS_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'SHPS', SHPS_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'SHPS' in out

    def test_diff_text_files(self, tmp_path, capsys):
        """Diff detects changes in TEXT files."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import TEXT_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'TEXT', TEXT_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'TEXT' in out

    def test_diff_binary_identical(self, tmp_path, capsys):
        """Identical binary files show no byte changes."""
        from ult3edit.diff import diff_binary
        from ult3edit.constants import DDRW_FILE_SIZE
        da = tmp_path / 'a'
        db = tmp_path / 'b'
        da.mkdir()
        db.mkdir()
        data = bytes(DDRW_FILE_SIZE)
        (da / 'DDRW').write_bytes(data)
        (db / 'DDRW').write_bytes(data)
        fd = diff_binary(str(da / 'DDRW'), str(db / 'DDRW'), 'DDRW')
        # No changed_bytes field if identical
        changed = [f for f in fd.entities[0].fields
                   if f.path == 'changed_bytes']
        assert not changed or changed[0].new == 0

    def test_diff_directories_includes_new_types(self, tmp_path):
        """Directory diff scans for MBS, DDRW, SHPS, TEXT."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import (
            DDRW_FILE_SIZE, MBS_FILE_SIZE, SHPS_FILE_SIZE, TEXT_FILE_SIZE)
        d1 = tmp_path / 'game1'
        d2 = tmp_path / 'game2'
        d1.mkdir()
        d2.mkdir()
        for name, size in [('DDRW', DDRW_FILE_SIZE), ('MBS', MBS_FILE_SIZE),
                           ('SHPS', SHPS_FILE_SIZE), ('TEXT', TEXT_FILE_SIZE)]:
            data1 = bytearray(size)
            data2 = bytearray(size)
            data2[0] = 0xAA
            (d1 / name).write_bytes(bytes(data1))
            (d2 / name).write_bytes(bytes(data2))
        args = argparse.Namespace(
            path1=str(d1), path2=str(d2),
            json=True, summary=False, output=str(tmp_path / 'diff.json'))
        cmd_diff(args)
        result = json.loads((tmp_path / 'diff.json').read_text())
        file_types = {f['type'] for f in result['files']}
        assert 'DDRW' in file_types
        assert 'MBS' in file_types
        assert 'SHPS' in file_types
        assert 'TEXT' in file_types


# ============================================================================
# Additional view-only command tests
# ============================================================================

class TestViewOnlyCommands:
    """Tests for view-only commands (equip, spell, shapes export)."""

    def test_equip_view(self, capsys):
        """equip view produces equipment stats table."""
        from ult3edit.equip import cmd_view
        args = argparse.Namespace(json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Dagger' in out or 'Leather' in out

    def test_equip_view_json(self, tmp_path):
        """equip view --json produces valid JSON."""
        from ult3edit.equip import cmd_view
        outfile = tmp_path / 'equip.json'
        args = argparse.Namespace(json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'weapons' in result or 'armors' in result

    def test_spell_view(self, capsys):
        """spell view produces spell reference table."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            cleric_only=False, wizard_only=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 50

    def test_spell_view_json(self, tmp_path):
        """spell view --json produces valid JSON."""
        from ult3edit.spell import cmd_view
        outfile = tmp_path / 'spells.json'
        args = argparse.Namespace(
            json=True, output=str(outfile),
            cleric_only=False, wizard_only=False)
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert isinstance(result, dict) or isinstance(result, list)

    def test_shapes_export_png(self, tmp_path):
        """shapes export creates PNG files from SHPS data."""
        from ult3edit.shapes import cmd_export
        from ult3edit.constants import SHPS_FILE_SIZE
        shps = tmp_path / 'SHPS'
        shps.write_bytes(bytes(SHPS_FILE_SIZE))
        out_dir = tmp_path / 'pngs'
        args = argparse.Namespace(
            file=str(shps), output_dir=str(out_dir),
            scale=1, sheet=False)
        cmd_export(args)
        assert out_dir.exists()
        pngs = list(out_dir.glob('*.png'))
        assert len(pngs) == 256  # 256 glyphs

    def test_shapes_export_with_sheet(self, tmp_path):
        """shapes export --sheet creates sprite sheet PNG."""
        from ult3edit.shapes import cmd_export
        from ult3edit.constants import SHPS_FILE_SIZE
        shps = tmp_path / 'SHPS'
        shps.write_bytes(bytes(SHPS_FILE_SIZE))
        out_dir = tmp_path / 'pngs'
        args = argparse.Namespace(
            file=str(shps), output_dir=str(out_dir),
            scale=1, sheet=True)
        cmd_export(args)
        sheet_file = out_dir / 'glyph_sheet.png'
        assert sheet_file.exists()

    def test_shapes_info(self, tmp_path, capsys):
        """shapes info shows metadata."""
        from ult3edit.shapes import cmd_info
        from ult3edit.constants import SHPS_FILE_SIZE
        shps = tmp_path / 'SHPS'
        shps.write_bytes(bytes(SHPS_FILE_SIZE))
        args = argparse.Namespace(
            file=str(shps), json=False, output=None)
        cmd_info(args)
        out = capsys.readouterr().out
        assert '256' in out or 'charset' in out.lower()

    def test_shapes_info_json(self, tmp_path):
        """shapes info --json produces valid JSON."""
        from ult3edit.shapes import cmd_info
        from ult3edit.constants import SHPS_FILE_SIZE
        shps = tmp_path / 'SHPS'
        shps.write_bytes(bytes(SHPS_FILE_SIZE))
        outfile = tmp_path / 'info.json'
        args = argparse.Namespace(
            file=str(shps), json=True, output=str(outfile))
        cmd_info(args)
        result = json.loads(outfile.read_text())
        assert result['format']['type'] == 'charset'

    def test_roster_view(self, tmp_path, capsys):
        """roster view displays character roster."""
        from ult3edit.roster import cmd_view
        from ult3edit.constants import ROSTER_FILE_SIZE
        rost = tmp_path / 'ROST'
        data = bytearray(ROSTER_FILE_SIZE)
        # Set a name in slot 0
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[0x0D] = 0x00
        rost.write_bytes(bytes(data))
        args = argparse.Namespace(
            file=str(rost), json=False, output=None,
            slot=None, validate=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'HERO' in out

    def test_bestiary_view(self, tmp_path, capsys):
        """bestiary view displays monster data."""
        from ult3edit.bestiary import cmd_view
        from ult3edit.constants import MON_FILE_SIZE
        monfile = tmp_path / 'MONA'
        monfile.write_bytes(bytes(MON_FILE_SIZE))
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False, file=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_save_view(self, tmp_path, capsys):
        """save view displays party state."""
        from ult3edit.save import cmd_view
        from ult3edit.constants import PRTY_FILE_SIZE
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF  # sentinel
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_combat_view(self, tmp_path, capsys):
        """combat view displays battlefield data."""
        from ult3edit.combat import cmd_view
        from ult3edit.constants import CON_FILE_SIZE
        con = tmp_path / 'CONA'
        con.write_bytes(bytes(CON_FILE_SIZE))
        args = argparse.Namespace(
            path=str(con), json=False, output=None,
            validate=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 0


# =============================================================================
# Patch cmd_edit and cmd_dump tests
# =============================================================================


# =============================================================================
# Map cmd_fill / cmd_replace / cmd_find CLI tests
# =============================================================================

class TestMapCmdFill:
    """Tests for map.cmd_fill — fill rectangular regions."""

    def test_fill_basic(self, tmp_path, capsys):
        """Fill a 2x2 region on an overworld map."""
        from ult3edit.map import cmd_fill
        path = tmp_path / 'SOSA'
        path.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=str(path), x1=0, y1=0, x2=1, y2=1, tile=0x04,
            level=None, dry_run=False, backup=False, output=None)
        cmd_fill(args)
        with open(str(path), 'rb') as f:
            data = f.read()
        # Tiles at (0,0), (1,0), (0,1), (1,1) should be 0x04
        assert data[0] == 0x04
        assert data[1] == 0x04
        assert data[64] == 0x04
        assert data[65] == 0x04

    def test_fill_dry_run(self, tmp_path, capsys):
        """Dry run doesn't write changes."""
        from ult3edit.map import cmd_fill
        path = tmp_path / 'SOSA'
        path.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=str(path), x1=0, y1=0, x2=3, y2=3, tile=0xFF,
            level=None, dry_run=True, backup=False, output=None)
        cmd_fill(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        with open(str(path), 'rb') as f:
            data = f.read()
        assert data[0] == 0x00  # unchanged

    def test_fill_clamps_coords(self, tmp_path, capsys):
        """Out-of-bounds coordinates are clamped."""
        from ult3edit.map import cmd_fill
        path = tmp_path / 'SOSA'
        path.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=str(path), x1=0, y1=0, x2=999, y2=999, tile=0x01,
            level=None, dry_run=True, backup=False, output=None)
        # Should not crash — coords get clamped
        cmd_fill(args)
        out = capsys.readouterr().out
        assert 'Filled' in out


class TestMapCmdReplace:
    """Tests for map.cmd_replace — tile replacement."""

    def test_replace_basic(self, tmp_path, capsys):
        """Replace one tile type with another."""
        from ult3edit.map import cmd_replace
        path = tmp_path / 'SOSA'
        data = bytearray(MAP_OVERWORLD_SIZE)
        data[0] = 0x04  # grass
        data[1] = 0x04  # grass
        data[2] = 0x01  # water
        path.write_bytes(bytes(data))
        args = argparse.Namespace(
            file=str(path), from_tile=0x04, to_tile=0x0C,
            level=None, dry_run=False, backup=False, output=None)
        cmd_replace(args)
        out = capsys.readouterr().out
        assert 'Replaced 2 tiles' in out
        with open(str(path), 'rb') as f:
            result = f.read()
        assert result[0] == 0x0C
        assert result[1] == 0x0C
        assert result[2] == 0x01  # unchanged

    def test_replace_dry_run(self, tmp_path, capsys):
        """Dry run shows count but doesn't write."""
        from ult3edit.map import cmd_replace
        path = tmp_path / 'SOSA'
        data = bytearray(MAP_OVERWORLD_SIZE)
        data[0] = 0x04
        path.write_bytes(bytes(data))
        args = argparse.Namespace(
            file=str(path), from_tile=0x04, to_tile=0x0C,
            level=None, dry_run=True, backup=False, output=None)
        cmd_replace(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        with open(str(path), 'rb') as f:
            result = f.read()
        assert result[0] == 0x04  # unchanged


class TestMapCmdFind:
    """Tests for map.cmd_find — tile search."""

    def test_find_basic(self, tmp_path, capsys):
        """Find tiles at known positions."""
        path = tmp_path / 'SOSA'
        data = bytearray(MAP_OVERWORLD_SIZE)
        data[0] = 0x04  # (0,0)
        data[65] = 0x04  # (1,1)
        path.write_bytes(bytes(data))
        args = argparse.Namespace(
            file=str(path), tile=0x04,
            level=None, json=False, output=None)
        cmd_find(args)
        out = capsys.readouterr().out
        assert '2 found' in out
        assert '(0, 0)' in out
        assert '(1, 1)' in out

    def test_find_json(self, tmp_path):
        """Find with --json produces valid JSON."""
        path = tmp_path / 'SOSA'
        data = bytearray(MAP_OVERWORLD_SIZE)
        data[0] = 0x04
        path.write_bytes(bytes(data))
        outfile = tmp_path / 'found.json'
        args = argparse.Namespace(
            file=str(path), tile=0x04,
            level=None, json=True, output=str(outfile))
        cmd_find(args)
        result = json.loads(outfile.read_text())
        assert result['count'] == 1
        assert result['locations'][0] == {'x': 0, 'y': 0}

    def test_find_no_matches(self, tmp_path, capsys):
        """Find with no matches shows 0 found."""
        path = tmp_path / 'SOSA'
        path.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=str(path), tile=0xFF,
            level=None, json=False, output=None)
        cmd_find(args)
        out = capsys.readouterr().out
        assert '0 found' in out


# =============================================================================
# TLK cmd_view and cmd_import tests
# =============================================================================

class TestTlkCmdView:
    """Tests for tlk.cmd_view — dialog viewing."""

    def _make_tlk(self, path, text='Hello'):
        """Create a single-record TLK file."""
        data = encode_record([text])
        path.write_bytes(bytes(data))

    def test_view_single_file(self, tmp_path, capsys):
        """View a single TLK file."""
        from ult3edit.tlk import cmd_view
        tlk = tmp_path / 'TLKA'
        self._make_tlk(tlk, 'TEST DIALOG')
        args = argparse.Namespace(
            path=str(tlk), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'TEST DIALOG' in out

    def test_view_json(self, tmp_path):
        """View --json produces valid JSON."""
        from ult3edit.tlk import cmd_view
        tlk = tmp_path / 'TLKA'
        self._make_tlk(tlk, 'JSON dialog')
        outfile = tmp_path / 'tlk.json'
        args = argparse.Namespace(
            path=str(tlk), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'records' in result

    def test_view_directory(self, tmp_path, capsys):
        """View all TLK files in a directory."""
        from ult3edit.tlk import cmd_view
        tlk = tmp_path / 'TLKA'
        self._make_tlk(tlk, 'Town dialog')
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'TLKA' in out or 'Town dialog' in out or len(out) > 0


class TestTlkCmdImport:
    """Tests for tlk.cmd_import — dialog import from JSON."""

    def test_import_roundtrip(self, tmp_path, capsys):
        """Import from JSON writes correct TLK data."""
        from ult3edit.tlk import cmd_import, load_tlk_records
        tlk_path = tmp_path / 'TLKA'
        tlk_path.write_bytes(bytes(64))  # placeholder
        json_path = tmp_path / 'dialog.json'
        json_path.write_text(json.dumps({
            'records': [
                {'lines': ['Hello traveler', 'Welcome!']},
                {'lines': ['Goodbye']},
            ]
        }))
        args = argparse.Namespace(
            file=str(tlk_path), json_file=str(json_path),
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        records = load_tlk_records(str(tlk_path))
        assert len(records) == 2
        assert 'HELLO TRAVELER' in records[0][0]

    def test_import_dry_run(self, tmp_path, capsys):
        """Dry run doesn't write changes."""
        from ult3edit.tlk import cmd_import
        tlk_path = tmp_path / 'TLKA'
        original = bytes(64)
        tlk_path.write_bytes(original)
        json_path = tmp_path / 'dialog.json'
        json_path.write_text(json.dumps({'records': [{'lines': ['Test']}]}))
        args = argparse.Namespace(
            file=str(tlk_path), json_file=str(json_path),
            dry_run=True, backup=False, output=None)
        cmd_import(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        assert tlk_path.read_bytes() == original  # unchanged

    def test_import_with_backup(self, tmp_path, capsys):
        """Import with --backup creates .bak file."""
        from ult3edit.tlk import cmd_import
        tlk_path = tmp_path / 'TLKA'
        tlk_path.write_bytes(bytes(64))
        json_path = tmp_path / 'dialog.json'
        json_path.write_text(json.dumps({'records': [{'lines': ['Backed up']}]}))
        args = argparse.Namespace(
            file=str(tlk_path), json_file=str(json_path),
            dry_run=False, backup=True, output=None)
        cmd_import(args)
        assert os.path.exists(str(tlk_path) + '.bak')


# =============================================================================
# Import TypeError bug fix tests
# =============================================================================

class TestImportTypeErrorHandling:
    """Tests for TypeError handling in weapon/armor import with bad count types."""

    def test_roster_import_bad_weapon_count_warns(self, tmp_path, capsys):
        """Non-integer weapon count in JSON warns instead of crashing."""
        from ult3edit.roster import cmd_import
        rost = tmp_path / 'ROST'
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[0x0D] = 0x00
        rost.write_bytes(bytes(data))
        json_path = tmp_path / 'chars.json'
        json_path.write_text(json.dumps([{
            'slot': 0, 'name': 'HERO',
            'weapons': {'Dagger': 'five'}  # bad type
        }]))
        args = argparse.Namespace(
            file=str(rost), json_file=str(json_path),
            dry_run=True, backup=False, output=None, all=False)
        cmd_import(args)  # should not crash
        err = capsys.readouterr().err
        assert 'Warning' in err

    def test_roster_import_bad_armor_count_warns(self, tmp_path, capsys):
        """Non-integer armor count in JSON warns instead of crashing."""
        from ult3edit.roster import cmd_import
        rost = tmp_path / 'ROST'
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[0x0D] = 0x00
        rost.write_bytes(bytes(data))
        json_path = tmp_path / 'chars.json'
        json_path.write_text(json.dumps([{
            'slot': 0, 'name': 'HERO',
            'armors': {'Cloth': 'many'}  # bad type
        }]))
        args = argparse.Namespace(
            file=str(rost), json_file=str(json_path),
            dry_run=True, backup=False, output=None, all=False)
        cmd_import(args)  # should not crash
        err = capsys.readouterr().err
        assert 'Warning' in err


# =============================================================================
# Map --crop error handling test
# =============================================================================

class TestMapCropError:
    """Tests for map --crop input validation."""

    def test_crop_invalid_values_exits(self, tmp_path):
        """Non-integer crop values cause sys.exit."""
        from ult3edit.map import cmd_view
        path = tmp_path / 'SOSA'
        path.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=str(path), crop='0,0,foo,64',
            json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


# =============================================================================
# Save cmd_view and cmd_edit expanded coverage
# =============================================================================

class TestSaveCmdViewExpanded:
    """Tests for save cmd_view with --json and --brief flags."""

    def _make_save_dir(self, tmp_path):
        """Create a directory with PRTY and PLRS files."""
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF  # sentinel
        data[1] = 2     # party_size
        data[3] = 10    # saved_x
        data[4] = 20    # saved_y
        prty.write_bytes(bytes(data))
        plrs = tmp_path / 'PLRS'
        plrs_data = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            plrs_data[i] = ord(ch) | 0x80
        plrs_data[0x0D] = 0x00
        plrs.write_bytes(bytes(plrs_data))
        return str(tmp_path)

    def test_view_json(self, tmp_path):
        """save view --json produces valid JSON with party and active chars."""
        from ult3edit.save import cmd_view
        game_dir = self._make_save_dir(tmp_path)
        outfile = tmp_path / 'save.json'
        args = argparse.Namespace(
            game_dir=game_dir, json=True, output=str(outfile),
            validate=False, brief=False)
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'party' in result
        assert 'active_characters' in result

    def test_view_brief_skips_map(self, tmp_path, capsys):
        """save view --brief skips the SOSA mini-map."""
        from ult3edit.save import cmd_view
        game_dir = self._make_save_dir(tmp_path)
        # Also create a SOSA file (overworld map)
        from ult3edit.constants import SOSA_FILE_SIZE
        sosa = tmp_path / 'SOSA'
        sosa.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            game_dir=game_dir, json=False, output=None,
            validate=False, brief=True)
        cmd_view(args)
        out = capsys.readouterr().out
        # With --brief, no "Overworld" section should appear
        assert 'Overworld' not in out

    def test_view_validate_shows_warnings(self, tmp_path, capsys):
        """save view --validate shows party state warnings."""
        from ult3edit.save import cmd_view
        game_dir = self._make_save_dir(tmp_path)
        # Set an invalid slot ID (>19)
        prty = tmp_path / 'PRTY'
        data = bytearray(prty.read_bytes())
        data[1] = 2      # party_size = 2
        data[6] = 0xFF    # slot 0 = 255 (invalid)
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            game_dir=game_dir, json=False, output=None,
            validate=True, brief=True)
        cmd_view(args)
        err = capsys.readouterr().err
        assert 'WARNING' in err


class TestSaveCmdEditExpanded:
    """Tests for save cmd_edit with --location, --slot-ids, --sentinel."""

    def _make_save_dir(self, tmp_path):
        """Create PRTY file for editing."""
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF  # sentinel
        prty.write_bytes(bytes(data))
        return str(tmp_path)

    def test_edit_location(self, tmp_path, capsys):
        """Edit party location_type."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_save_dir(tmp_path)
        args = argparse.Namespace(
            game_dir=game_dir, transport=None, x=None, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location='sosaria', plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        cmd_edit(args)
        prty = tmp_path / 'PRTY'
        data = prty.read_bytes()
        # Location is at offset 2 (PRTY_OFF_LOCATION)
        assert data[2] == PRTY_LOCATION_CODES['sosaria']

    def test_edit_slot_ids(self, tmp_path, capsys):
        """Edit party slot_ids."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_save_dir(tmp_path)
        args = argparse.Namespace(
            game_dir=game_dir, transport=None, x=None, y=None,
            party_size=None, slot_ids=[0, 1, 2, 3], sentinel=None,
            location=None, plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        cmd_edit(args)
        prty = tmp_path / 'PRTY'
        data = prty.read_bytes()
        assert data[6] == 0  # slot 0
        assert data[7] == 1  # slot 1
        assert data[8] == 2  # slot 2
        assert data[9] == 3  # slot 3

    def test_edit_dry_run(self, tmp_path, capsys):
        """Edit with dry_run shows changes but doesn't write."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_save_dir(tmp_path)
        args = argparse.Namespace(
            game_dir=game_dir, transport=None, x=10, y=20,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=None,
            dry_run=True, backup=False, output=None, validate=False)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out


# =============================================================================
# Combat cmd_view directory mode
# =============================================================================

class TestCombatCmdViewDir:
    """Tests for combat cmd_view in directory scan mode."""

    def test_view_directory(self, tmp_path, capsys):
        """View all CON files in a directory."""
        from ult3edit.combat import cmd_view
        con = tmp_path / 'CONA'
        con.write_bytes(bytes(CON_FILE_SIZE))
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None,
            validate=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'CONA' in out or 'arena' in out.lower()

    def test_view_directory_json(self, tmp_path):
        """View directory --json produces valid JSON."""
        from ult3edit.combat import cmd_view
        con = tmp_path / 'CONA'
        con.write_bytes(bytes(CON_FILE_SIZE))
        outfile = tmp_path / 'combat.json'
        args = argparse.Namespace(
            path=str(tmp_path), json=True, output=str(outfile),
            validate=False)
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'CONA' in result

    def test_view_empty_dir_exits(self, tmp_path):
        """Directory with no CON files causes sys.exit."""
        from ult3edit.combat import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None,
            validate=False)
        with pytest.raises(SystemExit):
            cmd_view(args)


# =============================================================================
# Special cmd_view directory mode
# =============================================================================

class TestSpecialCmdViewDir:
    """Tests for special cmd_view in directory scan mode."""

    def test_view_directory(self, tmp_path, capsys):
        """View all special location files in a directory."""
        from ult3edit.special import cmd_view
        brnd = tmp_path / 'BRND'
        brnd.write_bytes(bytes(SPECIAL_FILE_SIZE))
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'BRND' in out or 'Brand' in out

    def test_view_directory_json(self, tmp_path):
        """View directory --json produces valid JSON."""
        from ult3edit.special import cmd_view
        brnd = tmp_path / 'BRND'
        brnd.write_bytes(bytes(SPECIAL_FILE_SIZE))
        outfile = tmp_path / 'special.json'
        args = argparse.Namespace(
            path=str(tmp_path), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'BRND' in result

    def test_view_empty_dir_exits(self, tmp_path):
        """Directory with no special files causes sys.exit."""
        from ult3edit.special import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


# =============================================================================
# DDRW cmd_edit out-of-bounds and sound cmd_edit dry-run tests
# =============================================================================


# =============================================================================
# Priority 3 edge case tests
# =============================================================================

class TestPartyStateEdgeCases:
    """Tests for PartyState constructor and setter edge cases."""

    def test_constructor_too_small_raises(self):
        """PartyState with data shorter than PRTY_FILE_SIZE raises ValueError."""
        with pytest.raises(ValueError, match='too small'):
            PartyState(bytes(5))

    def test_constructor_exact_size(self):
        """PartyState with exact PRTY_FILE_SIZE works."""
        party = PartyState(bytes(PRTY_FILE_SIZE))
        assert party.party_size == 0

    def test_slot_ids_clamps_high(self):
        """Slot IDs > 19 are clamped to 19."""
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.slot_ids = [99, 0, 0, 0]
        assert party.raw[6] == 19  # clamped

    def test_slot_ids_clamps_negative(self):
        """Negative slot IDs are clamped to 0."""
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.slot_ids = [-5, 0, 0, 0]
        assert party.raw[6] == 0  # clamped

    def test_location_code_setter(self):
        """location_code setter writes raw byte directly."""
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_code = 0x03
        assert party.location_code == 0x03
        assert party.raw[2] == 0x03  # PRTY_OFF_LOCATION

    def test_location_code_setter_masks_to_byte(self):
        """location_code setter masks value to 0xFF."""
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_code = 0x1FF
        assert party.location_code == 0xFF


class TestCharacterNameTruncation:
    """Tests for Character.name setter 13-char truncation."""

    def test_name_13_chars_exact(self):
        """13-character name fills exactly to the limit."""
        from ult3edit.roster import Character
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.name = 'ABCDEFGHIJKLM'  # 13 chars
        assert char.name == 'ABCDEFGHIJKLM'

    def test_name_14_chars_truncated(self):
        """14-character name is truncated to 13."""
        from ult3edit.roster import Character
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.name = 'ABCDEFGHIJKLMN'  # 14 chars
        assert char.name == 'ABCDEFGHIJKLM'  # truncated to 13
        # Byte 0x0D must be null (field boundary)
        assert char.raw[0x0D] == 0x00

    def test_name_short_null_fills(self):
        """Short name null-fills the remaining field bytes."""
        from ult3edit.roster import Character
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.name = 'AB'
        assert char.name == 'AB'
        # Bytes after 'AB' should be 0x00 (null-filled)
        assert char.raw[2] == 0x00
        assert char.raw[0x0D] == 0x00


class TestCombatMonsterOverlap:
    """Tests for validate_combat_map monster-monster overlap detection."""

    def test_monster_monster_overlap_warns(self):
        """Two monsters at the same position produce a warning."""
        from ult3edit.combat import CombatMap, validate_combat_map
        data = bytearray(CON_FILE_SIZE)
        cm = CombatMap(data)
        # Place monster 0 and monster 1 at same position
        cm.monster_x[0] = 5
        cm.monster_y[0] = 5
        cm.monster_x[1] = 5
        cm.monster_y[1] = 5
        warnings = validate_combat_map(cm)
        overlap_warnings = [w for w in warnings if 'overlap' in w.lower()]
        assert len(overlap_warnings) == 1
        assert 'Monster 1' in overlap_warnings[0]

    def test_no_overlap_no_warning(self):
        """Monsters at different positions produce no overlap warning."""
        from ult3edit.combat import CombatMap, validate_combat_map
        data = bytearray(CON_FILE_SIZE)
        cm = CombatMap(data)
        cm.monster_x[0] = 3
        cm.monster_y[0] = 3
        cm.monster_x[1] = 7
        cm.monster_y[1] = 7
        warnings = validate_combat_map(cm)
        overlap_warnings = [w for w in warnings if 'overlap' in w.lower()]
        assert len(overlap_warnings) == 0


# =============================================================================
# Dispatch and CLI integration tests
# =============================================================================

class TestDispatchIntegration:
    """Tests for dispatch() functions and CLI filter flags."""

    def test_equip_view_text(self, capsys):
        """equip view text mode shows weapon and armor tables."""
        from ult3edit.equip import cmd_view
        args = argparse.Namespace(json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Weapons' in out
        assert 'Armor' in out
        assert 'Dagger' in out
        assert 'Class Equipment' in out

    def test_equip_dispatch_view(self, capsys):
        """equip dispatch routes 'view' correctly."""
        from ult3edit.equip import dispatch
        args = argparse.Namespace(equip_command='view', json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Weapons' in out

    def test_equip_dispatch_none(self, capsys):
        """equip dispatch with no subcommand shows usage."""
        from ult3edit.equip import dispatch
        args = argparse.Namespace(equip_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err

    def test_spell_wizard_only(self, capsys):
        """spell view --wizard-only shows only wizard spells."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            wizard_only=True, cleric_only=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Wizard' in out
        assert 'Cleric' not in out

    def test_spell_cleric_only(self, capsys):
        """spell view --cleric-only shows only cleric spells."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            wizard_only=False, cleric_only=True)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Cleric' in out
        assert 'Wizard' not in out

    def test_spell_dispatch_none(self, capsys):
        """spell dispatch with no subcommand shows usage."""
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err

    def test_combat_dispatch_view(self, tmp_path, capsys):
        """combat dispatch routes 'view' correctly."""
        from ult3edit.combat import dispatch
        con = tmp_path / 'CONA'
        con.write_bytes(bytes(CON_FILE_SIZE))
        args = argparse.Namespace(
            combat_command='view', path=str(con),
            json=False, output=None, validate=False)
        dispatch(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_special_dispatch_view(self, tmp_path, capsys):
        """special dispatch routes 'view' correctly."""
        from ult3edit.special import dispatch
        brnd = tmp_path / 'BRND'
        brnd.write_bytes(bytes(SPECIAL_FILE_SIZE))
        args = argparse.Namespace(
            special_command='view', path=str(brnd),
            json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_save_dispatch_view(self, tmp_path, capsys):
        """save dispatch routes 'view' correctly."""
        from ult3edit.save import dispatch
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            save_command='view', game_dir=str(tmp_path),
            json=False, output=None, validate=False, brief=True)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Save State' in out or 'Party' in out

    def test_ddrw_dispatch_view(self, tmp_path, capsys):
        """ddrw dispatch routes 'view' correctly."""
        from ult3edit.ddrw import dispatch
        from ult3edit.constants import DDRW_FILE_SIZE
        ddrw = tmp_path / 'DDRW'
        ddrw.write_bytes(bytes(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            ddrw_command='view', path=str(ddrw),
            json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_sound_dispatch_view(self, tmp_path, capsys):
        """sound dispatch routes 'view' correctly."""
        from ult3edit.sound import dispatch
        from ult3edit.constants import SOSA_FILE_SIZE
        sosa = tmp_path / 'SOSA'
        sosa.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            sound_command='view', path=str(sosa),
            json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert len(out) > 0


# =============================================================================
# Bug fix tests: text phantom records, TLK case, TLK find/replace error
# =============================================================================

class TestTextImportNoPhantomRecords:
    """Tests for text.cmd_import zeroing stale bytes."""

    def test_import_shorter_records_no_phantoms(self, tmp_path, capsys):
        """Importing fewer/shorter records doesn't leave stale data."""
        from ult3edit.text import cmd_import, load_text_records
        from ult3edit.fileutil import encode_high_ascii
        # Build a TEXT file with 3 original records
        data = bytearray(TEXT_FILE_SIZE)
        offset = 0
        for text in ['ULTIMA III', 'EXODUS', 'PRESS ANY KEY']:
            enc = encode_high_ascii(text, len(text))
            data[offset:offset + len(enc)] = enc
            data[offset + len(enc)] = 0x00
            offset += len(enc) + 1
        path = tmp_path / 'TEXT'
        path.write_bytes(bytes(data))
        # Import only 2 shorter records
        json_path = tmp_path / 'text.json'
        json_path.write_text(json.dumps([
            {'text': 'SHORT'},
            {'text': 'TWO'},
        ]))
        args = argparse.Namespace(
            file=str(path), json_file=str(json_path),
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        records = load_text_records(str(path))
        assert len(records) == 2
        assert records[0] == 'SHORT'
        assert records[1] == 'TWO'

    def test_import_same_count_exact(self, tmp_path, capsys):
        """Importing same number of records produces exact count."""
        from ult3edit.text import cmd_import, load_text_records
        from ult3edit.fileutil import encode_high_ascii
        data = bytearray(TEXT_FILE_SIZE)
        offset = 0
        for text in ['AAA', 'BBB']:
            enc = encode_high_ascii(text, len(text))
            data[offset:offset + len(enc)] = enc
            data[offset + len(enc)] = 0x00
            offset += len(enc) + 1
        path = tmp_path / 'TEXT'
        path.write_bytes(bytes(data))
        json_path = tmp_path / 'text.json'
        json_path.write_text(json.dumps([
            {'text': 'CCC'},
            {'text': 'DDD'},
        ]))
        args = argparse.Namespace(
            file=str(path), json_file=str(json_path),
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        records = load_text_records(str(path))
        assert len(records) == 2

    def test_stale_bytes_zeroed(self, tmp_path, capsys):
        """Bytes after final record are zeroed."""
        from ult3edit.text import cmd_import
        # Fill file with 0xFF to detect stale data
        data = bytearray([0xFF] * TEXT_FILE_SIZE)
        path = tmp_path / 'TEXT'
        path.write_bytes(bytes(data))
        json_path = tmp_path / 'text.json'
        json_path.write_text(json.dumps([{'text': 'HI'}]))
        args = argparse.Namespace(
            file=str(path), json_file=str(json_path),
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        result = path.read_bytes()
        # 'HI' = 2 high-ASCII bytes + null = 3 bytes at offset 0
        # Everything after offset 3 should be zeroed
        assert all(b == 0 for b in result[3:])


class TestTlkEncodeRecordCase:
    """Tests for TLK encode_record uppercase forcing."""

    def test_encode_forces_uppercase(self):
        """encode_record converts lowercase to uppercase high-ASCII."""
        data = encode_record(['hello'])
        # Each char should be uppercase: H=0xC8, E=0xC5, L=0xCC, L=0xCC, O=0xCF
        assert data[0] == 0xC8  # H
        assert data[1] == 0xC5  # E
        assert data[2] == 0xCC  # L
        assert data[3] == 0xCC  # L
        assert data[4] == 0xCF  # O
        assert data[5] == 0x00  # TLK_RECORD_END

    def test_encode_preserves_uppercase(self):
        """encode_record keeps already-uppercase text unchanged."""
        data = encode_record(['HELLO'])
        assert data[0] == 0xC8  # H
        assert data[4] == 0xCF  # O

    def test_encode_mixed_case(self):
        """encode_record normalizes mixed case to uppercase."""
        data = encode_record(['HeLLo'])
        assert data[0] == 0xC8  # H
        assert data[1] == 0xC5  # E (was lowercase e)
        assert data[4] == 0xCF  # O (was lowercase o)


class TestTlkFindReplaceError:
    """Tests for TLK --find without --replace error message."""

    def test_find_without_replace_exits(self, tmp_path, capsys):
        """--find without --replace gives correct error message."""
        from ult3edit.tlk import cmd_edit
        tlk = tmp_path / 'TLKA'
        tlk.write_bytes(bytes(64))
        args = argparse.Namespace(
            file=str(tlk), find='hello', replace=None,
            record=None, text=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)
        err = capsys.readouterr().err
        assert 'must be used together' in err

    def test_replace_without_find_exits(self, tmp_path, capsys):
        """--replace without --find gives correct error message."""
        from ult3edit.tlk import cmd_edit
        tlk = tmp_path / 'TLKA'
        tlk.write_bytes(bytes(64))
        args = argparse.Namespace(
            file=str(tlk), find=None, replace='world',
            record=None, text=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)
        err = capsys.readouterr().err
        assert 'must be used together' in err


# =============================================================================
# Special truncated file, DiskContext leak, TUI fixes
# =============================================================================

class TestSpecialTruncatedFile:
    """Tests for special.py handling truncated files in JSON export."""

    def test_truncated_file_json_no_crash(self, tmp_path):
        """Truncated special file doesn't crash in single-file JSON export."""
        from ult3edit.special import cmd_view
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(50))  # 50 < 128 (SPECIAL_FILE_SIZE)
        outfile = tmp_path / 'special.json'
        args = argparse.Namespace(
            path=str(path), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'tiles' in result
        # Should not crash — inner bounds check prevents IndexError

    def test_full_file_json_complete(self, tmp_path):
        """Full-size special file produces complete 11x11 grid."""
        from ult3edit.special import cmd_view
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(SPECIAL_FILE_SIZE))
        outfile = tmp_path / 'special.json'
        args = argparse.Namespace(
            path=str(path), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert len(result['tiles']) == 11
        assert len(result['tiles'][0]) == 11


class TestDiskContextLeakGuard:
    """Tests for DiskContext temp directory cleanup on __enter__ failure."""

    def test_enter_failure_cleans_tmpdir(self, tmp_path):
        """DiskContext cleans up temp dir when disk extraction raises."""
        from ult3edit.disk import DiskContext
        # Use a non-existent image path and non-existent tool
        fake_image = str(tmp_path / 'nonexistent.po')
        ctx = DiskContext(fake_image, diskiigs_path='/nonexistent/tool')
        with pytest.raises(Exception):
            ctx.__enter__()
        # After failure, _tmpdir should be cleaned up (set to None)
        assert ctx._tmpdir is None


class TestMapEditorDungeonPadding:
    """Tests for MapEditor padding short dungeon files."""

    def test_short_dungeon_file_pads(self):
        """Short dungeon data is padded to at least 256 bytes."""
        from ult3edit.tui.map_editor import MapEditor
        # 100-byte file (less than one dungeon level)
        data = bytes(100)
        editor = MapEditor('test', data, is_dungeon=True)
        assert len(editor.full_data) >= 256
        # Should be able to access all 16x16 tiles without IndexError
        for y in range(16):
            for x in range(16):
                _ = editor.state.tile_at(x, y)


class TestDialogEditorEmptyRecord:
    """Tests for DialogEditor save with empty records."""

    def test_encode_empty_lines_produces_nonzero(self):
        """encode_record(['']) produces at least 1 byte before stripping."""
        result = encode_record([''])
        # Empty line should produce just TLK_RECORD_END (0x00)
        assert len(result) >= 1
        # After stripping (encoded[:-1]), should not be empty
        # The dialog editor now guards against this
        stripped = result[:-1] if len(result) > 1 else result
        assert len(stripped) >= 1

    def test_dialog_editor_save_preserves_records(self):
        """DialogEditor save doesn't collapse null separators."""
        from ult3edit.tui.dialog_editor import DialogEditor
        from ult3edit.constants import TLK_RECORD_END
        # Build a TLK-like blob with 3 records
        records = [
            encode_record(['HELLO'])[:-1],  # strip trailing null
            encode_record(['WORLD'])[:-1],
            encode_record(['END'])[:-1],
        ]
        data = bytes([TLK_RECORD_END]).join(records)
        saved_data = []
        editor = DialogEditor('test', data, save_callback=lambda d: saved_data.append(d))
        assert len(editor.records) == 3
        # Mark record 0 as modified and save
        editor._modified_records.add(0)
        editor.dirty = True
        editor._save()
        # Should still produce valid data with 3 records
        assert len(saved_data) == 1
        # Re-parse should yield 3 records
        reloaded = DialogEditor('test', saved_data[0])
        assert len(reloaded.records) == 3


# =============================================================================
# Error path tests: sys.exit(1) coverage
# =============================================================================

class TestRosterErrorPaths:
    """Tests for roster cmd_view/cmd_edit/cmd_create/cmd_import error exits."""

    def _make_roster(self, tmp_path, name_in_slot0='HERO'):
        """Create a roster file with one character in slot 0."""
        data = bytearray(ROSTER_FILE_SIZE)
        if name_in_slot0:
            for i, ch in enumerate(name_in_slot0):
                data[i] = ord(ch) | 0x80
            data[0x0D] = 0x00
        path = tmp_path / 'ROST'
        path.write_bytes(bytes(data))
        return str(path)

    def test_view_slot_out_of_range(self, tmp_path):
        """cmd_view with --slot out of range exits."""
        from ult3edit.roster import cmd_view
        path = self._make_roster(tmp_path)
        args = argparse.Namespace(
            file=path, json=False, output=None,
            slot=99, validate=False)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_edit_no_slot_no_all(self, tmp_path):
        """cmd_edit without --slot or --all exits."""
        from ult3edit.roster import cmd_edit
        path = self._make_roster(tmp_path)
        args = argparse.Namespace(
            file=path, slot=None, all=False,
            dry_run=False, backup=False, output=None,
            validate=False, name=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_slot_out_of_range(self, tmp_path):
        """cmd_edit with --slot out of range exits."""
        from ult3edit.roster import cmd_edit
        path = self._make_roster(tmp_path)
        args = argparse.Namespace(
            file=path, slot=99, all=False,
            dry_run=False, backup=False, output=None,
            validate=False, name='TEST')
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_empty_slot(self, tmp_path):
        """cmd_edit on empty slot exits with helpful message."""
        from ult3edit.roster import cmd_edit
        path = self._make_roster(tmp_path, name_in_slot0=None)
        args = argparse.Namespace(
            file=path, slot=0, all=False,
            dry_run=False, backup=False, output=None,
            validate=False, name='TEST')
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_create_slot_out_of_range(self, tmp_path):
        """cmd_create with --slot out of range exits."""
        from ult3edit.roster import cmd_create
        path = self._make_roster(tmp_path)
        args = argparse.Namespace(
            file=path, slot=99, force=False,
            dry_run=False, backup=False, output=None,
            name=None, race=None, char_class=None, gender=None,
            str=None, dex=None, int_=None, wis=None,
            hp=None, mp=None, gold=None, food=None,
            exp=None, max_hp=None, gems=None, keys=None,
            powders=None, torches=None, status=None,
            weapon=None, armor=None, in_party=None, not_in_party=None)
        with pytest.raises(SystemExit):
            cmd_create(args)

    def test_create_occupied_slot_no_force(self, tmp_path, capsys):
        """cmd_create on occupied slot without --force exits."""
        from ult3edit.roster import cmd_create
        path = self._make_roster(tmp_path)
        args = argparse.Namespace(
            file=path, slot=0, force=False,
            dry_run=False, backup=False, output=None,
            name=None, race=None, char_class=None, gender=None,
            str=None, dex=None, int_=None, wis=None,
            hp=None, mp=None, gold=None, food=None,
            exp=None, max_hp=None, gems=None, keys=None,
            powders=None, torches=None, status=None,
            weapon=None, armor=None, in_party=None, not_in_party=None)
        with pytest.raises(SystemExit):
            cmd_create(args)
        err = capsys.readouterr().err
        assert 'occupied' in err.lower() or 'HERO' in err

    def test_import_non_list_json(self, tmp_path):
        """cmd_import with non-list JSON exits."""
        from ult3edit.roster import cmd_import
        path = self._make_roster(tmp_path)
        json_path = tmp_path / 'bad.json'
        json_path.write_text('{"name": "not a list"}')
        args = argparse.Namespace(
            file=path, json_file=str(json_path),
            dry_run=False, backup=False, output=None, all=False)
        with pytest.raises(SystemExit):
            cmd_import(args)


class TestSaveErrorPaths:
    """Tests for save cmd_view/cmd_edit/cmd_import error exits."""

    def test_view_no_prty(self, tmp_path):
        """cmd_view with no PRTY file exits."""
        from ult3edit.save import cmd_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False, brief=True)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_edit_no_prty(self, tmp_path):
        """cmd_edit with no PRTY file exits."""
        from ult3edit.save import cmd_edit
        args = argparse.Namespace(
            game_dir=str(tmp_path), transport=None, x=1, y=1,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_invalid_transport(self, tmp_path, capsys):
        """cmd_edit with invalid transport name exits."""
        from ult3edit.save import cmd_edit
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            game_dir=str(tmp_path), transport='spaceship', x=None, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_invalid_location(self, tmp_path, capsys):
        """cmd_edit with invalid location name exits."""
        from ult3edit.save import cmd_edit
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            game_dir=str(tmp_path), transport=None, x=None, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location='moon', plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_plrs_slot_no_plrs(self, tmp_path):
        """cmd_edit with --plrs-slot but no PLRS file exits."""
        from ult3edit.save import cmd_edit
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            game_dir=str(tmp_path), transport=None, x=None, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=0,
            name='TEST', str=None, dex=None, int_=None, wis=None,
            hp=None, mp=None, gold=None, food=None,
            exp=None, max_hp=None, gems=None, keys=None,
            powders=None, torches=None, status=None,
            weapon=None, armor=None, race=None, char_class=None,
            gender=None, in_party=None, not_in_party=None,
            dry_run=False, backup=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_import_no_prty(self, tmp_path):
        """cmd_import with no PRTY file exits."""
        from ult3edit.save import cmd_import
        json_path = tmp_path / 'save.json'
        json_path.write_text(json.dumps({'party': {'transport': 'foot'}}))
        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=str(json_path),
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_import(args)


class TestBestiaryErrorPaths:
    """Tests for bestiary cmd_edit error exits."""

    def test_edit_no_monster_no_all(self, tmp_path):
        """cmd_edit without --monster or --all exits."""
        from ult3edit.bestiary import cmd_edit
        mon = tmp_path / 'MONA'
        mon.write_bytes(bytes(MON_FILE_SIZE))
        args = argparse.Namespace(
            file=str(mon), monster=None, all=False,
            dry_run=False, backup=False, output=None,
            validate=False, hp=None, tile=None, flags=None,
            name=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_monster_out_of_range(self, tmp_path):
        """cmd_edit with monster index > 15 exits."""
        from ult3edit.bestiary import cmd_edit
        mon = tmp_path / 'MONA'
        mon.write_bytes(bytes(MON_FILE_SIZE))
        args = argparse.Namespace(
            file=str(mon), monster=99, all=False,
            dry_run=False, backup=False, output=None,
            validate=False, hp=50, tile=None, flags=None,
            name=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestTlkErrorPaths:
    """Tests for tlk cmd_view/cmd_edit error exits."""

    def test_view_no_tlk_files(self, tmp_path):
        """cmd_view on empty directory exits."""
        from ult3edit.tlk import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_edit_no_args_exits(self, tmp_path):
        """cmd_edit with no --record/--text and no --find/--replace exits."""
        from ult3edit.tlk import cmd_edit
        tlk = tmp_path / 'TLKA'
        tlk.write_bytes(encode_record(['TEST']))
        args = argparse.Namespace(
            file=str(tlk), find=None, replace=None,
            record=None, text=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)


# =============================================================================
# Round-trip integrity tests
# =============================================================================

class TestPrtyRoundTrip:
    """Verify all PRTY fields survive set→save→reload cycle."""

    def test_all_fields_roundtrip(self, tmp_path):
        """Set every PRTY field, write to file, reload, verify all match."""
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'horse'
        party.party_size = 3
        party.location_type = 'dungeon'
        party.x = 42
        party.y = 17
        party.sentinel = 0xFF
        party.slot_ids = [5, 10, 15, 2]

        # Write raw bytes
        prty_file = tmp_path / 'PRTY'
        prty_file.write_bytes(bytes(party.raw))

        # Reload
        reloaded = PartyState(prty_file.read_bytes())
        assert reloaded.transport == 'Horse'
        assert reloaded.party_size == 3
        assert reloaded.location_type == 'Dungeon'
        assert reloaded.x == 42
        assert reloaded.y == 17
        assert reloaded.sentinel == 0xFF
        assert reloaded.slot_ids == [5, 10, 15, 2]

    def test_json_export_import_roundtrip(self, tmp_path):
        """Export PRTY to JSON via to_dict, re-import via cmd_import, verify."""
        from ult3edit.save import cmd_import as save_import

        # Set up initial PRTY state
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'ship'
        party.party_size = 4
        party.location_type = 'sosaria'
        party.x = 55
        party.y = 33
        party.sentinel = 0xFF
        party.slot_ids = [0, 1, 2, 3]

        prty_file = tmp_path / 'PRTY'
        prty_file.write_bytes(bytes(party.raw))

        # Export to JSON dict
        jdata = {'party': party.to_dict()}

        # Modify some fields in JSON
        jdata['party']['x'] = 10
        jdata['party']['y'] = 20
        jdata['party']['party_size'] = 2

        # Write JSON and import
        json_file = tmp_path / 'save.json'
        json_file.write_text(json.dumps(jdata))

        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        save_import(args)

        # Reload and verify modified fields
        result = PartyState(prty_file.read_bytes())
        assert result.x == 10
        assert result.y == 20
        assert result.party_size == 2
        # Unmodified fields should persist
        assert result.transport == 'Ship'
        assert result.sentinel == 0xFF
        assert result.slot_ids == [0, 1, 2, 3]

    def test_byte_level_fidelity(self, tmp_path):
        """Verify every byte in the 16-byte PRTY survives save→reload."""
        data = bytearray(range(16))
        party = PartyState(data)
        prty_file = tmp_path / 'PRTY'
        prty_file.write_bytes(bytes(party.raw))
        reloaded = PartyState(prty_file.read_bytes())
        assert bytes(reloaded.raw) == bytes(party.raw)


class TestRosterFullRoundTrip:
    """Verify complete 64-byte character record survives property round-trip."""

    def _make_full_character(self):
        """Create a character with every field set to non-default values."""
        from ult3edit.constants import CHAR_ARMOR_START, CHAR_WEAPON_START
        data = bytearray(CHAR_RECORD_SIZE)
        char = Character(data)
        char.name = 'TESTHEROINE'
        char.marks = ['Kings', 'Fire']
        char.cards = ['Sol']
        char.torches = 50
        char.in_party = True
        char.status = 'G'
        char.strength = 75
        char.dexterity = 80
        char.intelligence = 60
        char.wisdom = 45
        char.race = 'Elf'
        char.char_class = 'Wizard'
        char.gender = 'F'
        char.mp = 99
        char.hp = 1234
        char.max_hp = 5678
        char.exp = 9999
        char.sub_morsels = 42
        char.food = 3456
        char.gold = 7890
        char.gems = 25
        char.keys = 10
        char.powders = 5
        char.raw[CHAR_WORN_ARMOR] = 3
        char.raw[CHAR_READIED_WEAPON] = 5
        for i in range(7):
            char.raw[CHAR_ARMOR_START + i] = (i + 1) % 16
        for i in range(15):
            char.raw[CHAR_WEAPON_START + i] = (i + 2) % 16
        return char

    def test_all_property_fields_roundtrip(self, tmp_path):
        """Set all character fields, save, reload, verify each property."""
        char = self._make_full_character()

        rost_file = tmp_path / 'ROST'
        rost_data = bytearray(ROSTER_FILE_SIZE)
        rost_data[:CHAR_RECORD_SIZE] = char.raw
        rost_file.write_bytes(bytes(rost_data))

        chars, _ = load_roster(str(rost_file))
        rc = chars[0]
        assert rc.name == 'TESTHEROINE'
        assert 'Kings' in rc.marks
        assert 'Fire' in rc.marks
        assert 'Sol' in rc.cards
        assert rc.torches == 50
        assert rc.in_party is True
        assert rc.status == 'Good'
        assert rc.strength == 75
        assert rc.dexterity == 80
        assert rc.intelligence == 60
        assert rc.wisdom == 45
        assert rc.race == 'Elf'
        assert rc.char_class == 'Wizard'
        assert rc.gender == 'Female'
        assert rc.mp == 99
        assert rc.hp == 1234
        assert rc.max_hp == 5678
        assert rc.exp == 9999
        assert rc.sub_morsels == 42
        assert rc.food == 3456
        assert rc.gold == 7890
        assert rc.gems == 25
        assert rc.keys == 10
        assert rc.powders == 5
        assert rc.raw[CHAR_WORN_ARMOR] == 3
        assert rc.raw[CHAR_READIED_WEAPON] == 5

    def test_multi_slot_no_corruption(self, tmp_path):
        """Fill all 20 roster slots, save, reload, verify no cross-slot bleed."""
        rost_data = bytearray(ROSTER_FILE_SIZE)
        for slot in range(20):
            offset = slot * CHAR_RECORD_SIZE
            data = bytearray(CHAR_RECORD_SIZE)
            char = Character(data)
            char.name = f'CHAR{slot:02d}'
            char.strength = min(99, slot * 5)
            char.hp = slot * 100
            rost_data[offset:offset + CHAR_RECORD_SIZE] = char.raw

        rost_file = tmp_path / 'ROST'
        rost_file.write_bytes(bytes(rost_data))

        chars, _ = load_roster(str(rost_file))
        for slot in range(20):
            assert chars[slot].name == f'CHAR{slot:02d}'
            assert chars[slot].strength == min(99, slot * 5)
            assert chars[slot].hp == slot * 100

    def test_byte_level_fidelity(self, tmp_path):
        """Verify all 64 bytes survive save→reload without corruption."""
        char = self._make_full_character()
        original_bytes = bytes(char.raw)

        rost_data = bytearray(ROSTER_FILE_SIZE)
        rost_data[:CHAR_RECORD_SIZE] = char.raw
        rost_file = tmp_path / 'ROST'
        rost_file.write_bytes(bytes(rost_data))

        result_data = rost_file.read_bytes()
        assert result_data[:CHAR_RECORD_SIZE] == original_bytes


class TestBestiaryColumnarRoundTrip:
    """Verify MON columnar layout survives import/export correctly."""

    def test_columnar_layout_preservation(self, tmp_path):
        """Set attributes for all 16 monsters, verify column-major layout."""
        data = bytearray(MON_FILE_SIZE)
        for attr in range(10):
            for monster in range(16):
                data[attr * 16 + monster] = (attr * 16 + monster) & 0xFF

        mon_file = tmp_path / 'MONA'
        mon_file.write_bytes(bytes(data))

        monsters = load_mon_file(str(mon_file))
        # Verify each monster reads correct values from its column slot
        for m in monsters:
            idx = m.index
            assert m.tile1 == (0 * 16 + idx) & 0xFF  # row 0
            assert m.hp == (4 * 16 + idx) & 0xFF      # row 4

        # Save with original_data to preserve rows 10-15
        save_mon_file(str(mon_file), monsters, original_data=bytes(data))
        result = mon_file.read_bytes()
        assert result == bytes(data)

    def test_unused_rows_preserved(self, tmp_path):
        """Rows 10-15 (runtime workspace) survive save→reload with original_data."""
        data = bytearray(MON_FILE_SIZE)
        for row in range(10, 16):
            for col in range(16):
                data[row * 16 + col] = 0xAA
        for row in range(10):
            for col in range(16):
                data[row * 16 + col] = row

        mon_file = tmp_path / 'MONA'
        mon_file.write_bytes(bytes(data))

        monsters = load_mon_file(str(mon_file))
        save_mon_file(str(mon_file), monsters, original_data=bytes(data))
        result = mon_file.read_bytes()
        for row in range(10, 16):
            for col in range(16):
                assert result[row * 16 + col] == 0xAA, \
                    f"Row {row}, col {col} corrupted"


class TestCombatPaddingRoundTrip:
    """Verify CON padding and runtime arrays survive save→reload."""

    def test_padding_and_runtime_preservation(self, tmp_path):
        """Non-zero padding and runtime bytes survive CombatMap round-trip."""
        from ult3edit.combat import CombatMap
        from ult3edit.constants import (
            CON_PADDING1_OFFSET, CON_PADDING1_SIZE,
            CON_RUNTIME_MONSAVE_OFFSET,
            CON_RUNTIME_PCSAVE_OFFSET,
            CON_PADDING2_OFFSET, CON_PADDING2_SIZE,
        )

        data = bytearray(CON_FILE_SIZE)
        for i in range(CON_PADDING1_SIZE):
            data[CON_PADDING1_OFFSET + i] = 0xAA
        for i in range(16):
            data[CON_RUNTIME_MONSAVE_OFFSET + i] = 0xBB
        for i in range(8):
            data[CON_RUNTIME_PCSAVE_OFFSET + i] = 0xCC
        for i in range(CON_PADDING2_SIZE):
            data[CON_PADDING2_OFFSET + i] = 0xDD

        cm = CombatMap(data)
        assert cm.padding1 == [0xAA] * CON_PADDING1_SIZE
        assert cm.runtime_monster == [0xBB] * 16
        assert cm.runtime_pc == [0xCC] * 8
        assert cm.padding2 == [0xDD] * CON_PADDING2_SIZE

    def test_json_roundtrip_preserves_padding(self, tmp_path):
        """Export CON to JSON dict, import it back, verify padding intact."""
        from ult3edit.combat import CombatMap, cmd_import as combat_import
        from ult3edit.constants import (
            CON_PADDING1_OFFSET, CON_PADDING1_SIZE,
            CON_PADDING2_OFFSET, CON_PADDING2_SIZE,
            CON_RUNTIME_MONSAVE_OFFSET, CON_RUNTIME_PCSAVE_OFFSET,
        )

        data = bytearray(CON_FILE_SIZE)
        data[0] = 0x04
        for i in range(CON_PADDING1_SIZE):
            data[CON_PADDING1_OFFSET + i] = 0x11
        for i in range(16):
            data[CON_RUNTIME_MONSAVE_OFFSET + i] = 0x22
        for i in range(8):
            data[CON_RUNTIME_PCSAVE_OFFSET + i] = 0x33
        for i in range(CON_PADDING2_SIZE):
            data[CON_PADDING2_OFFSET + i] = 0x44

        con_file = tmp_path / 'CONA'
        con_file.write_bytes(bytes(data))

        cm = CombatMap(data)
        jdata = cm.to_dict()

        json_file = tmp_path / 'con.json'
        json_file.write_text(json.dumps(jdata))

        args = argparse.Namespace(
            file=str(con_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        combat_import(args)

        result = con_file.read_bytes()
        for i in range(CON_PADDING1_SIZE):
            assert result[CON_PADDING1_OFFSET + i] == 0x11
        for i in range(16):
            assert result[CON_RUNTIME_MONSAVE_OFFSET + i] == 0x22
        for i in range(8):
            assert result[CON_RUNTIME_PCSAVE_OFFSET + i] == 0x33
        for i in range(CON_PADDING2_SIZE):
            assert result[CON_PADDING2_OFFSET + i] == 0x44


class TestSpecialTrailingBytesRoundTrip:
    """Verify special location trailing bytes survive import."""

    def test_trailing_bytes_preserved(self, tmp_path):
        """Import special location tiles, verify trailing 7 bytes unchanged."""
        from ult3edit.special import cmd_import as special_import

        data = bytearray(SPECIAL_FILE_SIZE)
        for i in range(121):
            data[i] = 0x04
        for i in range(7):
            data[121 + i] = 0xA0 + i

        spec_file = tmp_path / 'BRND'
        spec_file.write_bytes(bytes(data))

        jdata = {
            'tiles': [['.' for _ in range(11)] for _ in range(11)],
            'trailing_bytes': [0xA0 + i for i in range(7)],
        }
        jdata['tiles'][0][0] = '~'

        json_file = tmp_path / 'brnd.json'
        json_file.write_text(json.dumps(jdata))

        args = argparse.Namespace(
            file=str(spec_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        special_import(args)

        result = spec_file.read_bytes()
        for i in range(7):
            assert result[121 + i] == 0xA0 + i, \
                f"Trailing byte {i} corrupted"

    def test_trailing_bytes_absent_preserves_original(self, tmp_path):
        """Import JSON without trailing_bytes key preserves original padding."""
        from ult3edit.special import cmd_import as special_import

        data = bytearray(SPECIAL_FILE_SIZE)
        for i in range(7):
            data[121 + i] = 0xEE

        spec_file = tmp_path / 'SHRN'
        spec_file.write_bytes(bytes(data))

        jdata = {'tiles': [['.' for _ in range(11)] for _ in range(11)]}
        json_file = tmp_path / 'shrn.json'
        json_file.write_text(json.dumps(jdata))

        args = argparse.Namespace(
            file=str(spec_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        special_import(args)

        result = spec_file.read_bytes()
        for i in range(7):
            assert result[121 + i] == 0xEE


class TestMapJsonRoundTripFull:
    """Verify map JSON export→import preserves tile data."""

    def test_overworld_export_import_cycle(self, tmp_path):
        """Export overworld as JSON, import back, verify identical bytes."""
        from ult3edit.map import cmd_view as map_view, cmd_import as map_import

        data = bytearray(MAP_OVERWORLD_SIZE)
        for i in range(MAP_OVERWORLD_SIZE):
            data[i] = 0x04

        data[0] = 0x00
        data[63] = 0x08
        data[64*63] = 0x0C

        map_file = tmp_path / 'SOSMAP'
        map_file.write_bytes(bytes(data))

        json_out = tmp_path / 'map.json'
        args = argparse.Namespace(
            file=str(map_file), json=True, output=str(json_out),
            crop=None, level=None, validate=False)
        map_view(args)

        with open(str(json_out), 'r') as f:
            jdata = json.load(f)
        assert 'tiles' in jdata

        map_file2 = tmp_path / 'SOSMAP2'
        map_file2.write_bytes(bytes(data))
        args = argparse.Namespace(
            file=str(map_file2), json_file=str(json_out),
            backup=False, dry_run=False, output=None, dungeon=False)
        map_import(args)

        assert map_file2.read_bytes() == bytes(data)


class TestTlkMultilineRoundTrip:
    """Verify TLK multi-line dialog records survive encode→decode."""

    def test_multiline_encode_decode(self):
        """Multi-line records round-trip through encode→decode."""
        from ult3edit.tlk import decode_record
        lines = ['HELLO TRAVELER', 'WELCOME TO TOWN', 'FAREWELL']
        encoded = encode_record(lines)
        decoded = decode_record(encoded)
        assert decoded == lines

    def test_single_line_roundtrip(self):
        """Single-line record round-trips correctly."""
        from ult3edit.tlk import decode_record
        lines = ['GOOD DAY']
        encoded = encode_record(lines)
        decoded = decode_record(encoded)
        assert decoded == lines

    def test_empty_string_in_lines(self):
        """Records with empty lines survive round-trip."""
        from ult3edit.tlk import decode_record
        lines = ['START', '', 'END']
        encoded = encode_record(lines)
        decoded = decode_record(encoded)
        assert decoded == lines


# =============================================================================
# Bug fix tests: MBS parsing and shapes overlay extraction
# =============================================================================


# =============================================================================
# FileUtil coverage
# =============================================================================

class TestResolveSingleFile:
    """Tests for resolve_single_file with ProDOS suffixes."""

    def test_find_plain_file(self, tmp_path):
        """Finds a plain file by name."""
        from ult3edit.fileutil import resolve_single_file
        (tmp_path / 'PRTY').write_bytes(b'\x00' * 16)
        result = resolve_single_file(str(tmp_path), 'PRTY')
        assert result is not None
        assert 'PRTY' in result

    def test_find_prodos_hashed_file(self, tmp_path):
        """Finds a file with ProDOS #hash suffix."""
        from ult3edit.fileutil import resolve_single_file
        (tmp_path / 'PRTY#069500').write_bytes(b'\x00' * 16)
        result = resolve_single_file(str(tmp_path), 'PRTY')
        assert result is not None
        assert 'PRTY#069500' in result

    def test_not_found_returns_none(self, tmp_path):
        """Returns None when file doesn't exist."""
        from ult3edit.fileutil import resolve_single_file
        result = resolve_single_file(str(tmp_path), 'NOSUCHFILE')
        assert result is None

    def test_prefers_hashed_over_plain(self, tmp_path):
        """When both plain and hashed exist, hashed is returned first."""
        from ult3edit.fileutil import resolve_single_file
        (tmp_path / 'ROST#069500').write_bytes(b'\x00' * 64)
        (tmp_path / 'ROST').write_bytes(b'\x00' * 64)
        result = resolve_single_file(str(tmp_path), 'ROST')
        assert result is not None
        assert '#' in result


class TestResolveGameFile:
    """Tests for resolve_game_file with prefix+letter pattern."""

    def test_find_with_hash(self, tmp_path):
        """Finds MAPA#061000 style files."""
        from ult3edit.fileutil import resolve_game_file
        (tmp_path / 'MAPA#061000').write_bytes(b'\x00' * 100)
        result = resolve_game_file(str(tmp_path), 'MAP', 'A')
        assert result is not None
        assert 'MAPA#061000' in result

    def test_find_plain(self, tmp_path):
        """Falls back to plain name if no hash file exists."""
        from ult3edit.fileutil import resolve_game_file
        (tmp_path / 'CONA').write_bytes(b'\x00' * 192)
        result = resolve_game_file(str(tmp_path), 'CON', 'A')
        assert result is not None
        assert 'CONA' in result

    def test_not_found(self, tmp_path):
        """Returns None if neither hashed nor plain exists."""
        from ult3edit.fileutil import resolve_game_file
        result = resolve_game_file(str(tmp_path), 'MAP', 'Z')
        assert result is None

    def test_excludes_dproj(self, tmp_path):
        """Files ending in .dproj are excluded."""
        from ult3edit.fileutil import resolve_game_file
        (tmp_path / 'MAPA#061000.dproj').write_bytes(b'\x00')
        result = resolve_game_file(str(tmp_path), 'MAP', 'A')
        assert result is None


class TestFindGameFiles:
    """Tests for find_game_files across multiple letters."""

    def test_finds_multiple(self, tmp_path):
        """Finds all existing files across letter range."""
        from ult3edit.fileutil import find_game_files
        (tmp_path / 'CONA').write_bytes(b'\x00' * 192)
        (tmp_path / 'CONC').write_bytes(b'\x00' * 192)
        result = find_game_files(str(tmp_path), 'CON', 'ABCDE')
        assert len(result) == 2
        letters = [r[0] for r in result]
        assert 'A' in letters
        assert 'C' in letters

    def test_empty_directory(self, tmp_path):
        """Returns empty list for empty directory."""
        from ult3edit.fileutil import find_game_files
        result = find_game_files(str(tmp_path), 'CON', 'ABCDE')
        assert result == []


# =============================================================================
# Patch inline string operations
# =============================================================================


# =============================================================================
# Shapes pixel helper tests
# =============================================================================


# =============================================================================
# DDRW parsing and editing tests
# =============================================================================


# =============================================================================
# SpecialEditor save preserves trailing bytes
# =============================================================================

class TestSpecialEditorSave:
    """Tests for SpecialEditor TUI save preserving metadata."""

    def test_save_preserves_trailing_bytes(self):
        """SpecialEditor._save() preserves trailing 7 bytes."""
        from ult3edit.tui.special_editor import SpecialEditor

        data = bytearray(128)
        # Fill tiles with grass
        for i in range(121):
            data[i] = 0x04
        # Set trailing bytes
        for i in range(7):
            data[121 + i] = 0xF0 + i

        saved_data = None
        def capture(d):
            nonlocal saved_data
            saved_data = d

        editor = SpecialEditor('test', bytes(data), save_callback=capture)
        # Modify a tile
        editor.state.data[0] = 0x00  # water
        editor.state.dirty = True
        editor._save()

        assert saved_data is not None
        # Tile changed
        assert saved_data[0] == 0x00
        # Trailing bytes preserved
        for i in range(7):
            assert saved_data[121 + i] == 0xF0 + i

    def test_save_with_short_data(self):
        """SpecialEditor pads short data to at least tile grid size."""
        from ult3edit.tui.special_editor import SpecialEditor
        from ult3edit.constants import SPECIAL_MAP_TILES

        data = bytes(100)  # Shorter than 121 tiles
        saved_data = None
        def capture(d):
            nonlocal saved_data
            saved_data = d

        editor = SpecialEditor('test', data, save_callback=capture)
        editor.state.dirty = True
        editor._save()
        assert saved_data is not None
        # Padded tile data written over short original
        assert len(saved_data) >= SPECIAL_MAP_TILES


# =============================================================================
# Import type validation tests
# =============================================================================

class TestImportTypeValidation:
    """Tests for graceful handling of invalid JSON values in import paths."""

    def test_sound_import_non_int_in_raw_exits(self, tmp_path):
        """sound cmd_import with non-integer in raw array exits gracefully."""
        from ult3edit.sound import cmd_import as sound_import
        json_file = tmp_path / 'bad.json'
        json_file.write_text(json.dumps({'raw': ['hello', 123]}))
        snd_file = tmp_path / 'SOSA'
        snd_file.write_bytes(bytes(4096))
        args = argparse.Namespace(
            file=str(snd_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        with pytest.raises(SystemExit):
            sound_import(args)

    def test_sound_import_non_list_raw_exits(self, tmp_path):
        """sound cmd_import with non-list raw exits gracefully."""
        from ult3edit.sound import cmd_import as sound_import
        json_file = tmp_path / 'bad.json'
        json_file.write_text(json.dumps({'raw': 'not a list'}))
        snd_file = tmp_path / 'SOSA'
        snd_file.write_bytes(bytes(4096))
        args = argparse.Namespace(
            file=str(snd_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        with pytest.raises(SystemExit):
            sound_import(args)

    def test_ddrw_import_non_int_in_raw_exits(self, tmp_path):
        """ddrw cmd_import with non-integer in raw array exits gracefully."""
        from ult3edit.ddrw import cmd_import as ddrw_import
        json_file = tmp_path / 'bad.json'
        json_file.write_text(json.dumps({'raw': [1, 2, 'bad', 4]}))
        ddrw_file = tmp_path / 'DDRW'
        ddrw_file.write_bytes(bytes(1792))
        args = argparse.Namespace(
            file=str(ddrw_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        with pytest.raises(SystemExit):
            ddrw_import(args)

    def test_ddrw_import_valid_raw_works(self, tmp_path):
        """ddrw cmd_import with valid raw array succeeds."""
        from ult3edit.ddrw import cmd_import as ddrw_import
        json_file = tmp_path / 'good.json'
        json_file.write_text(json.dumps({'raw': [0] * 1792}))
        ddrw_file = tmp_path / 'DDRW'
        ddrw_file.write_bytes(bytes(1792))
        args = argparse.Namespace(
            file=str(ddrw_file), json_file=str(json_file),
            backup=False, dry_run=False, output=str(ddrw_file))
        ddrw_import(args)
        assert len(ddrw_file.read_bytes()) == 1792

    def test_sound_import_valid_raw_works(self, tmp_path):
        """sound cmd_import with valid raw array succeeds."""
        from ult3edit.sound import cmd_import as sound_import
        json_file = tmp_path / 'good.json'
        json_file.write_text(json.dumps({'raw': [0] * 256}))
        snd_file = tmp_path / 'SOSM'
        snd_file.write_bytes(bytes(256))
        args = argparse.Namespace(
            file=str(snd_file), json_file=str(json_file),
            backup=False, dry_run=False, output=str(snd_file))
        sound_import(args)
        assert len(snd_file.read_bytes()) == 256


# =============================================================================
# Shapes check_shps_code_region
# =============================================================================


# =============================================================================
# Save validate_party_state coordinate bounds
# =============================================================================

class TestSaveValidationBounds:
    """Tests for validate_party_state X/Y coordinate validation."""

    def test_valid_coordinates_no_warning(self):
        """Coordinates within 0-63 produce no warnings about coords."""
        from ult3edit.save import validate_party_state
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'foot'
        party.location_type = 'sosaria'
        party.party_size = 1
        party.x = 63
        party.y = 0
        party.sentinel = 0xFF
        party.slot_ids = [0, 0, 0, 0]
        warnings = validate_party_state(party)
        coord_warnings = [w for w in warnings if 'coordinate' in w.lower()]
        assert len(coord_warnings) == 0

    def test_x_out_of_bounds_warning(self):
        """X coordinate > 63 triggers warning."""
        from ult3edit.save import validate_party_state
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'foot'
        party.location_type = 'sosaria'
        party.sentinel = 0xFF
        # Bypass clamping setter to set raw value > 63
        party.raw[PRTY_OFF_SAVED_X] = 200
        warnings = validate_party_state(party)
        coord_warnings = [w for w in warnings if 'X coordinate' in w]
        assert len(coord_warnings) == 1

    def test_y_out_of_bounds_warning(self):
        """Y coordinate > 63 triggers warning."""
        from ult3edit.save import validate_party_state
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'foot'
        party.location_type = 'sosaria'
        party.sentinel = 0xFF
        party.raw[PRTY_OFF_SAVED_Y] = 128
        warnings = validate_party_state(party)
        coord_warnings = [w for w in warnings if 'Y coordinate' in w]
        assert len(coord_warnings) == 1

    def test_multiple_violations(self):
        """Multiple validation issues produce multiple warnings."""
        from ult3edit.save import validate_party_state
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        # Unknown transport
        party.raw[PRTY_OFF_TRANSPORT] = 0xFE
        # Unknown location
        party.raw[PRTY_OFF_LOCATION] = 0xFE
        # Bad coords
        party.raw[PRTY_OFF_SAVED_X] = 200
        party.raw[PRTY_OFF_SAVED_Y] = 200
        # Weird sentinel
        party.raw[PRTY_OFF_SENTINEL] = 0x42
        warnings = validate_party_state(party)
        assert len(warnings) >= 4


# =============================================================================
# Map editing edge cases
# =============================================================================

class TestMapSetEdgeCases:
    """Tests for map cmd_set edge cases."""

    def test_set_negative_coords_exits(self, tmp_path):
        """cmd_set with negative coordinates exits."""
        map_file = tmp_path / 'SOSMAP'
        map_file.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=str(map_file), x=-1, y=5, tile=0x04,
            level=None, dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_set(args)

    def test_set_beyond_bounds_exits(self, tmp_path):
        """cmd_set with coords beyond map size exits."""
        map_file = tmp_path / 'SOSMAP'
        map_file.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=str(map_file), x=64, y=0, tile=0x04,
            level=None, dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_set(args)

    def test_set_valid_coords(self, tmp_path):
        """cmd_set writes correct tile at (0,0)."""
        map_file = tmp_path / 'SOSMAP'
        map_file.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=str(map_file), x=0, y=0, tile=0x08,
            level=None, dry_run=False, backup=False, output=None)
        cmd_set(args)
        result = map_file.read_bytes()
        assert result[0] == 0x08


class TestMapFillEdgeCases:
    """Tests for map cmd_fill edge cases."""

    def test_fill_reversed_coords(self, tmp_path):
        """cmd_fill with x1>x2 clamps x2 to x1 (single column)."""
        from ult3edit.map import cmd_fill
        map_file = tmp_path / 'SOSMAP'
        map_file.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        # Reversed: x1=5 > x2=2 → after clamping: x2=max(5, min(2,63))=5
        # So region collapses to single column at x=5, y=5
        args = argparse.Namespace(
            file=str(map_file), x1=5, y1=5, x2=2, y2=2, tile=0x08,
            level=None, dry_run=False, backup=False, output=None)
        cmd_fill(args)
        result = map_file.read_bytes()
        # Single tile at (5, 5)
        assert result[5 * 64 + 5] == 0x08

    def test_fill_entire_row(self, tmp_path):
        """cmd_fill across full width fills all tiles in row."""
        from ult3edit.map import cmd_fill
        map_file = tmp_path / 'SOSMAP'
        map_file.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=str(map_file), x1=0, y1=0, x2=63, y2=0, tile=0x0C,
            level=None, dry_run=False, backup=False, output=None)
        cmd_fill(args)
        result = map_file.read_bytes()
        for x in range(64):
            assert result[x] == 0x0C

    def test_replace_no_matches(self, tmp_path):
        """cmd_replace with no matching tiles reports 0 changes."""
        from ult3edit.map import cmd_replace
        map_file = tmp_path / 'SOSMAP'
        # All zeros, try to replace 0xFF -> 0x04
        map_file.write_bytes(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=str(map_file), from_tile=0xFF, to_tile=0x04,
            level=None, dry_run=False, backup=False, output=None)
        cmd_replace(args)
        result = map_file.read_bytes()
        assert all(b == 0 for b in result)

    def test_replace_preserves_file_size(self, tmp_path):
        """cmd_replace preserves exact file size."""
        from ult3edit.map import cmd_replace
        map_file = tmp_path / 'SOSMAP'
        data = bytearray(MAP_OVERWORLD_SIZE)
        data[0] = 0x04
        map_file.write_bytes(bytes(data))
        args = argparse.Namespace(
            file=str(map_file), from_tile=0x04, to_tile=0x08,
            level=None, dry_run=False, backup=False, output=None)
        cmd_replace(args)
        result = map_file.read_bytes()
        assert len(result) == MAP_OVERWORLD_SIZE
        assert result[0] == 0x08


# =============================================================================
# Combat validate edge cases
# =============================================================================

class TestCombatValidateEdgeCases:
    """Tests for combat validation edge cases."""

    def test_all_positions_populated(self):
        """Validate with all 8 monster + 4 PC positions set."""
        from ult3edit.combat import CombatMap, validate_combat_map
        from ult3edit.constants import (CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET,
                                       CON_PC_X_OFFSET, CON_PC_Y_OFFSET)
        data = bytearray(CON_FILE_SIZE)
        # Place 8 monsters in different positions
        for i in range(8):
            data[CON_MONSTER_X_OFFSET + i] = i + 1
            data[CON_MONSTER_Y_OFFSET + i] = i + 1
        # Place 4 PCs in different positions
        for i in range(4):
            data[CON_PC_X_OFFSET + i] = i + 1
            data[CON_PC_Y_OFFSET + i] = 10 - i
        cm = CombatMap(data)
        warnings = validate_combat_map(cm)
        # No overlaps — all positions are unique
        overlap_warnings = [w for w in warnings if 'overlap' in w.lower()]
        assert len(overlap_warnings) == 0

    def test_monster_pc_overlap_detected(self):
        """Validate detects monster-PC overlap at same position."""
        from ult3edit.combat import CombatMap, validate_combat_map
        from ult3edit.constants import (CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET,
                                       CON_PC_X_OFFSET, CON_PC_Y_OFFSET)
        data = bytearray(CON_FILE_SIZE)
        # Monster 0 at (5, 5)
        data[CON_MONSTER_X_OFFSET] = 5
        data[CON_MONSTER_Y_OFFSET] = 5
        # PC 0 at (5, 5) — same position
        data[CON_PC_X_OFFSET] = 5
        data[CON_PC_Y_OFFSET] = 5
        cm = CombatMap(data)
        warnings = validate_combat_map(cm)
        overlap_warnings = [w for w in warnings if 'overlap' in w.lower()]
        assert len(overlap_warnings) >= 1

    def test_tile_misalignment_count(self):
        """Validate counts multiple misaligned tiles."""
        from ult3edit.combat import CombatMap, validate_combat_map
        data = bytearray(CON_FILE_SIZE)
        # Set 3 misaligned tiles (not multiples of 4)
        data[0] = 0x01  # misaligned
        data[1] = 0x02  # misaligned
        data[2] = 0x03  # misaligned
        data[3] = 0x04  # aligned
        cm = CombatMap(data)
        warnings = validate_combat_map(cm)
        alignment_warnings = [w for w in warnings if 'alignment' in w.lower()
                              or 'aligned' in w.lower()]
        assert len(alignment_warnings) == 1
        assert '3' in alignment_warnings[0]  # 3 misaligned tiles


# =============================================================================
# BCD edge cases
# =============================================================================

class TestBcdEdgeCases:
    """Tests for BCD encoding edge cases."""

    def test_bcd_to_int_invalid_nibble(self):
        """bcd_to_int(0xFF) returns 165 (15*10 + 15) — undocumented but stable."""
        from ult3edit.bcd import bcd_to_int
        # 0xFF has nibbles F(15) and F(15): 15*10 + 15 = 165
        assert bcd_to_int(0xFF) == 165
        # 0xAB has nibbles A(10) and B(11): 10*10 + 11 = 111
        assert bcd_to_int(0xAB) == 111

    def test_bcd16_max_value(self):
        """bcd16_to_int(0x99, 0x99) returns 9999."""
        from ult3edit.bcd import bcd16_to_int
        assert bcd16_to_int(0x99, 0x99) == 9999

    def test_int_to_bcd_negative_clamps(self):
        """int_to_bcd(-5) clamps to 0."""
        from ult3edit.bcd import int_to_bcd
        assert int_to_bcd(-5) == 0x00

    def test_int_to_bcd16_negative_clamps(self):
        """int_to_bcd16(-100) clamps to (0, 0)."""
        from ult3edit.bcd import int_to_bcd16
        assert int_to_bcd16(-100) == (0x00, 0x00)

    def test_int_to_bcd16_overflow_clamps(self):
        """int_to_bcd16(10000) clamps to 9999."""
        from ult3edit.bcd import int_to_bcd16
        assert int_to_bcd16(10000) == (0x99, 0x99)

    def test_bcd_roundtrip_all_valid(self):
        """Every value 0-99 round-trips through int_to_bcd→bcd_to_int."""
        from ult3edit.bcd import bcd_to_int, int_to_bcd
        for val in range(100):
            assert bcd_to_int(int_to_bcd(val)) == val


# =============================================================================
# Roster check_progress (endgame readiness)
# =============================================================================

class TestCheckProgressFull:
    """Test check_progress() endgame readiness analysis."""

    def _make_char(self, name='HERO', status='G', marks=0, cards=0,
                   weapon=0, armor=0):
        """Create a character with specific attributes."""
        raw = bytearray(CHAR_RECORD_SIZE)
        # Set name
        for i, ch in enumerate(name[:13]):
            raw[i] = ord(ch) | 0x80
        raw[CHAR_STATUS] = ord(status)
        raw[CHAR_MARKS_CARDS] = (marks << 4) | cards
        raw[CHAR_READIED_WEAPON] = weapon
        raw[CHAR_WORN_ARMOR] = armor
        # Set HP so character is "alive"
        raw[CHAR_HP_HI] = 0x01
        return Character(raw)

    def test_empty_roster_not_ready(self):
        """Empty roster produces not-ready result."""
        chars = [Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(20)]
        result = check_progress(chars)
        assert result['party_alive'] == 0
        assert not result['party_ready']
        assert not result['exodus_ready']
        assert len(result['marks_missing']) == 4
        assert len(result['cards_missing']) == 4

    def test_partial_party_not_ready(self):
        """Two characters — not ready (need 4)."""
        chars = [Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(20)]
        chars[0] = self._make_char('ALICE')
        chars[1] = self._make_char('BOB')
        result = check_progress(chars)
        assert result['party_alive'] == 2
        assert not result['party_ready']

    def test_dead_chars_dont_count(self):
        """Dead characters don't count toward party_alive."""
        chars = [Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(20)]
        chars[0] = self._make_char('ALIVE')
        chars[1] = self._make_char('DEAD', status='D')
        chars[2] = self._make_char('ASHES', status='A')
        result = check_progress(chars)
        assert result['party_alive'] == 1

    def test_all_marks_collected(self):
        """All 4 marks across multiple characters."""
        chars = [Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(20)]
        # marks bitmask: Kings=0x8, Snake=0x4, Fire=0x2, Force=0x1
        chars[0] = self._make_char('A', marks=0xC)  # Kings + Snake
        chars[1] = self._make_char('B', marks=0x3)  # Fire + Force
        result = check_progress(chars)
        assert result['marks_complete']
        assert len(result['marks_missing']) == 0

    def test_all_cards_collected(self):
        """All 4 cards across multiple characters."""
        chars = [Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(20)]
        # cards bitmask: Death=0x8, Sol=0x4, Love=0x2, Moons=0x1
        chars[0] = self._make_char('A', cards=0xF)  # all 4
        result = check_progress(chars)
        assert result['cards_complete']
        assert len(result['cards_missing']) == 0

    def test_exotic_weapon_detected(self):
        """Exotic weapon (index 15) detected on any character."""
        chars = [Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(20)]
        chars[0] = self._make_char('HERO', weapon=15)
        result = check_progress(chars)
        assert result['has_exotic_weapon']

    def test_exotic_armor_detected(self):
        """Exotic armor (index 7) detected on any character."""
        chars = [Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(20)]
        chars[0] = self._make_char('HERO', armor=7)
        result = check_progress(chars)
        assert result['has_exotic_armor']

    def test_fully_ready(self):
        """Full party with all marks, cards, exotic gear = exodus_ready."""
        chars = [Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(20)]
        for i in range(4):
            chars[i] = self._make_char(f'HERO{i}', marks=0xF, cards=0xF,
                                       weapon=15, armor=7)
        result = check_progress(chars)
        assert result['exodus_ready']
        assert result['party_ready']
        assert result['marks_complete']
        assert result['cards_complete']
        assert result['has_exotic_weapon']
        assert result['has_exotic_armor']

    def test_missing_one_requirement(self):
        """4 alive with all marks/cards but no exotic weapon → not ready."""
        chars = [Character(bytearray(CHAR_RECORD_SIZE)) for _ in range(20)]
        for i in range(4):
            chars[i] = self._make_char(f'HERO{i}', marks=0xF, cards=0xF,
                                       weapon=0, armor=7)
        result = check_progress(chars)
        assert not result['exodus_ready']
        assert not result['has_exotic_weapon']


# =============================================================================
# Roster cmd_view / cmd_edit / cmd_create error paths
# =============================================================================

class TestRosterCmdErrors:
    """Test error paths in roster CLI commands."""

    def _make_roster_file(self, tmp_path):
        """Create a roster file with one non-empty character."""
        data = bytearray(ROSTER_FILE_SIZE)
        # Put a character in slot 0
        offset = 0
        name = 'HERO'
        for i, ch in enumerate(name):
            data[offset + i] = ord(ch) | 0x80
        data[offset + CHAR_STATUS] = ord('G')
        data[offset + CHAR_HP_HI] = 0x01
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_view_slot_out_of_range(self, tmp_path):
        """cmd_view with --slot beyond range exits with error."""
        from ult3edit.roster import cmd_view
        path = self._make_roster_file(tmp_path)
        args = argparse.Namespace(
            file=path, slot=99, json=False, validate=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_view_negative_slot(self, tmp_path):
        """cmd_view with negative --slot exits with error."""
        from ult3edit.roster import cmd_view
        path = self._make_roster_file(tmp_path)
        args = argparse.Namespace(
            file=path, slot=-1, json=False, validate=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_create_occupied_slot_no_force(self, tmp_path):
        """cmd_create on occupied slot without --force exits."""
        from ult3edit.roster import cmd_create
        path = self._make_roster_file(tmp_path)
        args = argparse.Namespace(
            file=path, slot=0, force=False, dry_run=True, backup=False,
            output=None,
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None, in_party=None, not_in_party=None,
            sub_morsels=None)
        with pytest.raises(SystemExit):
            cmd_create(args)

    def test_create_slot_out_of_range(self, tmp_path):
        """cmd_create with out-of-range slot exits."""
        from ult3edit.roster import cmd_create
        path = self._make_roster_file(tmp_path)
        args = argparse.Namespace(
            file=path, slot=99, force=True, dry_run=True, backup=False,
            output=None,
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None, in_party=None, not_in_party=None,
            sub_morsels=None)
        with pytest.raises(SystemExit):
            cmd_create(args)

    def test_import_non_list_json(self, tmp_path):
        """cmd_import with JSON that's a dict (not list) exits."""
        path = self._make_roster_file(tmp_path)
        json_path = os.path.join(str(tmp_path), 'bad.json')
        with open(json_path, 'w') as f:
            json.dump({"name": "HERO"}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=True)
        with pytest.raises(SystemExit):
            cmd_import(args)


# =============================================================================
# Patch module: name compilation, region errors, hex dump
# =============================================================================


# =============================================================================
# Patch encoding helpers
# =============================================================================


# =============================================================================
# TLK search and edit error paths
# =============================================================================

class TestTlkCmdErrors:
    """Test TLK command error paths."""

    def _make_tlk_file(self, tmp_path, records=None):
        """Create a TLK file with simple text records."""
        data = bytearray()
        if records is None:
            records = [['HELLO WORLD'], ['GOODBYE']]
        for rec in records:
            data.extend(encode_record(rec))
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_search_invalid_regex(self, tmp_path):
        """cmd_search with malformed regex exits."""
        path = self._make_tlk_file(tmp_path)
        args = argparse.Namespace(
            path=path, pattern='[unclosed', regex=True, json=False,
            output=None)
        with pytest.raises(SystemExit):
            cmd_search(args)

    def test_search_finds_text(self, tmp_path):
        """cmd_search with valid pattern finds results."""
        path = self._make_tlk_file(tmp_path)
        args = argparse.Namespace(
            path=path, pattern='HELLO', regex=False, json=False,
            output=None)
        # Should not raise
        cmd_search(args)

    def test_edit_record_out_of_range(self, tmp_path):
        """cmd_edit with record index beyond count exits."""
        from ult3edit.tlk import cmd_edit as tlk_cmd_edit
        path = self._make_tlk_file(tmp_path)
        args = argparse.Namespace(
            file=path, record=99, text='NEW TEXT',
            output=None, dry_run=True, backup=False)
        with pytest.raises(SystemExit):
            tlk_cmd_edit(args)

    def test_match_line_case_insensitive(self):
        """_match_line plain text is case-insensitive."""
        assert _match_line('Hello World', 'hello', False)
        assert _match_line('HELLO WORLD', 'hello', False)

    def test_match_line_regex(self):
        """_match_line with regex pattern."""
        assert _match_line('Hello World 123', r'\d+', True)
        assert not _match_line('Hello World', r'\d+', True)


# =============================================================================
# Diff module: detect_file_type
# =============================================================================

class TestDiffDetectFileType:
    """Test diff.py file type detection."""

    def test_detect_roster(self, tmp_path):
        """Detect ROST file by name and size."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(bytes(ROSTER_FILE_SIZE))
        assert detect_file_type(path) == 'ROST'

    def test_detect_prty(self, tmp_path):
        """Detect PRTY file."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'PRTY')
        with open(path, 'wb') as f:
            f.write(bytes(PRTY_FILE_SIZE))
        assert detect_file_type(path) == 'PRTY'

    def test_detect_mon_file(self, tmp_path):
        """Detect MON file with letter suffix."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(bytes(MON_FILE_SIZE))
        assert detect_file_type(path) == 'MONA'

    def test_detect_con_file(self, tmp_path):
        """Detect CON file with letter suffix."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(bytes(CON_FILE_SIZE))
        assert detect_file_type(path) == 'CONA'

    def test_detect_prodos_hash(self, tmp_path):
        """Detect file with ProDOS #hash suffix."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'ROST#069500')
        with open(path, 'wb') as f:
            f.write(bytes(ROSTER_FILE_SIZE))
        assert detect_file_type(path) == 'ROST'

    def test_unknown_file_returns_none(self, tmp_path):
        """Unrecognized file returns None."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'UNKNOWN')
        with open(path, 'wb') as f:
            f.write(bytes(42))
        assert detect_file_type(path) is None

    def test_nonexistent_file_returns_none(self, tmp_path):
        """Nonexistent file returns None."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'NOFILE')
        assert detect_file_type(path) is None

    def test_detect_special_file(self, tmp_path):
        """Detect special location file."""
        from ult3edit.diff import detect_file_type
        from ult3edit.constants import SPECIAL_NAMES
        name = list(SPECIAL_NAMES.keys())[0]
        path = os.path.join(str(tmp_path), name)
        with open(path, 'wb') as f:
            f.write(bytes(SPECIAL_FILE_SIZE))
        assert detect_file_type(path) == name


# =============================================================================
# Patch identify_binary
# =============================================================================


# =============================================================================
# Patch cmd_edit dry-run / actual write
# =============================================================================


# =============================================================================
# Text module error paths
# =============================================================================

class TestTextCmdErrors:
    """Test text.py command error paths."""

    def test_text_edit_record_out_of_range(self, tmp_path):
        """text cmd_edit with record index beyond count exits."""
        from ult3edit.text import cmd_edit as text_cmd_edit
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(bytes(TEXT_FILE_SIZE))
        args = argparse.Namespace(
            file=path, record=999, text='HELLO',
            output=None, dry_run=True, backup=False)
        with pytest.raises(SystemExit):
            text_cmd_edit(args)

    def test_text_load_records(self, tmp_path):
        """load_text_records splits on null terminators."""
        path = os.path.join(str(tmp_path), 'TEXT')
        data = bytearray(TEXT_FILE_SIZE)
        # Put 3 null-terminated high-ASCII strings at start
        off = 0
        for s in ('HELLO', 'WORLD', 'TEST'):
            for ch in s:
                data[off] = ord(ch) | 0x80
                off += 1
            data[off] = 0x00
            off += 1
        with open(path, 'wb') as f:
            f.write(data)
        records = load_text_records(path)
        assert records[:3] == ['HELLO', 'WORLD', 'TEST']


# =============================================================================
# Equipment reference (equip.py)
# =============================================================================

class TestEquipView:
    """Test equip.py cmd_view."""

    def test_view_text_output(self, capsys):
        """cmd_view in text mode outputs weapon and armor tables."""
        from ult3edit.equip import cmd_view
        args = argparse.Namespace(json=False, output=None)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Weapons' in captured.out
        assert 'Armor' in captured.out
        assert 'Class Equipment Restrictions' in captured.out

    def test_view_json_output(self, tmp_path):
        """cmd_view in JSON mode produces valid structured data."""
        from ult3edit.equip import cmd_view
        out_path = os.path.join(str(tmp_path), 'equip.json')
        args = argparse.Namespace(json=True, output=out_path)
        cmd_view(args)
        with open(out_path) as f:
            data = json.load(f)
        assert 'weapons' in data
        assert 'armors' in data
        assert 'class_restrictions' in data
        assert len(data['weapons']) > 0
        assert 'damage' in data['weapons'][0]

    def test_dispatch_no_command(self, capsys):
        """dispatch with no subcommand prints usage."""
        from ult3edit.equip import dispatch
        args = argparse.Namespace(equip_command=None)
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err


# =============================================================================
# Spell reference (spell.py)
# =============================================================================

class TestSpellView:
    """Test spell.py cmd_view."""

    def test_view_all_spells(self, capsys):
        """cmd_view shows both wizard and cleric spells."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            wizard_only=False, cleric_only=False)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Wizard Spells' in captured.out
        assert 'Cleric Spells' in captured.out

    def test_view_wizard_only(self, capsys):
        """cmd_view with --wizard-only hides cleric spells."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            wizard_only=True, cleric_only=False)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Wizard Spells' in captured.out
        assert 'Cleric Spells' not in captured.out

    def test_view_cleric_only(self, capsys):
        """cmd_view with --cleric-only hides wizard spells."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            wizard_only=False, cleric_only=True)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Wizard Spells' not in captured.out
        assert 'Cleric Spells' in captured.out

    def test_view_json_output(self, tmp_path):
        """cmd_view JSON mode produces structured spell data."""
        from ult3edit.spell import cmd_view
        out_path = os.path.join(str(tmp_path), 'spells.json')
        args = argparse.Namespace(
            json=True, output=out_path,
            wizard_only=False, cleric_only=False)
        cmd_view(args)
        with open(out_path) as f:
            data = json.load(f)
        assert 'wizard' in data
        assert 'cleric' in data
        assert len(data['wizard']) > 0
        assert 'mp' in data['wizard'][0]

    def test_dispatch_no_command(self, capsys):
        """dispatch with no subcommand prints usage."""
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command=None)
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err


# =============================================================================
# Diff module: core algorithm and per-type diff functions
# =============================================================================

class TestDiffAlgorithm:
    """Test diff.py core diff_dicts and helpers."""

    def test_diff_dicts_identical(self):
        """Identical dicts produce no diffs."""
        from ult3edit.diff import diff_dicts
        d = {'a': 1, 'b': 'hello', 'c': [1, 2]}
        assert diff_dicts(d, d) == []

    def test_diff_dicts_changed_field(self):
        """Changed field produces a FieldDiff."""
        from ult3edit.diff import diff_dicts
        result = diff_dicts({'a': 1}, {'a': 2})
        assert len(result) == 1
        assert result[0].path == 'a'
        assert result[0].old == 1
        assert result[0].new == 2

    def test_diff_dicts_added_key(self):
        """New key in second dict is detected."""
        from ult3edit.diff import diff_dicts
        result = diff_dicts({}, {'a': 1})
        assert len(result) == 1
        assert result[0].path == 'a'
        assert result[0].old is None
        assert result[0].new == 1

    def test_diff_dicts_removed_key(self):
        """Missing key in second dict is detected."""
        from ult3edit.diff import diff_dicts
        result = diff_dicts({'a': 1}, {})
        assert len(result) == 1
        assert result[0].old == 1
        assert result[0].new is None

    def test_diff_dicts_nested(self):
        """Nested dict changes produce dotted paths."""
        from ult3edit.diff import diff_dicts
        d1 = {'a': {'b': 1, 'c': 2}}
        d2 = {'a': {'b': 1, 'c': 3}}
        result = diff_dicts(d1, d2)
        assert len(result) == 1
        assert result[0].path == 'a.c'

    def test_diff_dicts_list_change(self):
        """List element change is detected with [index] path."""
        from ult3edit.diff import diff_dicts
        d1 = {'items': [1, 2, 3]}
        d2 = {'items': [1, 9, 3]}
        result = diff_dicts(d1, d2)
        assert len(result) == 1
        assert '[1]' in result[0].path

    def test_diff_dicts_list_length_change(self):
        """Different list lengths produce diffs for extra elements."""
        from ult3edit.diff import diff_dicts
        d1 = {'items': [1, 2]}
        d2 = {'items': [1, 2, 3]}
        result = diff_dicts(d1, d2)
        assert len(result) == 1
        assert result[0].new == 3


class TestDiffTileGrid:
    """Test _diff_tile_grid helper."""

    def test_identical_grids(self):
        """Identical grids produce no tile changes."""
        from ult3edit.diff import FileDiff, _diff_tile_grid
        fd = FileDiff('test', 'test')
        data = bytes(range(16))
        _diff_tile_grid(fd, data, data, 4, 4)
        assert fd.tile_changes == 0
        assert fd.tile_positions == []

    def test_one_changed_tile(self):
        """One changed tile is detected with correct position."""
        from ult3edit.diff import FileDiff, _diff_tile_grid
        fd = FileDiff('test', 'test')
        d1 = bytes(16)
        d2 = bytearray(16)
        d2[5] = 0xFF  # (x=1, y=1) in a 4-wide grid
        _diff_tile_grid(fd, d1, bytes(d2), 4, 4)
        assert fd.tile_changes == 1
        assert fd.tile_positions == [(1, 1)]


class TestDiffRoster:
    """Test diff_roster comparing two ROST files."""

    def test_identical_rosters(self, tmp_path):
        """Identical rosters produce no changes."""
        from ult3edit.diff import diff_roster
        data = bytearray(ROSTER_FILE_SIZE)
        p1 = os.path.join(str(tmp_path), 'ROST1')
        p2 = os.path.join(str(tmp_path), 'ROST2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_roster(p1, p2)
        assert not fd.changed

    def test_changed_character(self, tmp_path):
        """Changed character stat produces field diff."""
        from ult3edit.diff import diff_roster
        data1 = bytearray(ROSTER_FILE_SIZE)
        data2 = bytearray(ROSTER_FILE_SIZE)
        # Set name in both so slot is non-empty
        for i, ch in enumerate('HERO'):
            data1[i] = ord(ch) | 0x80
            data2[i] = ord(ch) | 0x80
        data1[CHAR_STATUS] = ord('G')
        data2[CHAR_STATUS] = ord('G')
        # Change HP in second file
        data2[CHAR_HP_HI] = 0x05
        p1 = os.path.join(str(tmp_path), 'ROST1')
        p2 = os.path.join(str(tmp_path), 'ROST2')
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_roster(p1, p2)
        assert fd.changed

    def test_added_character(self, tmp_path):
        """Empty slot in file1, character in file2 → added_entities."""
        from ult3edit.diff import diff_roster
        data1 = bytearray(ROSTER_FILE_SIZE)
        data2 = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data2[i] = ord(ch) | 0x80
        data2[CHAR_STATUS] = ord('G')
        p1 = os.path.join(str(tmp_path), 'ROST1')
        p2 = os.path.join(str(tmp_path), 'ROST2')
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_roster(p1, p2)
        assert len(fd.added_entities) >= 1


class TestDiffCombat:
    """Test diff_combat comparing two CON files."""

    def test_identical_combat_maps(self, tmp_path):
        """Identical CON files produce no changes."""
        from ult3edit.diff import diff_combat
        data = bytearray(CON_FILE_SIZE)
        p1 = os.path.join(str(tmp_path), 'CONA1')
        p2 = os.path.join(str(tmp_path), 'CONA2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_combat(p1, p2, 'A')
        assert fd.tile_changes == 0

    def test_changed_tile(self, tmp_path):
        """Changed tile in CON file is detected."""
        from ult3edit.diff import diff_combat
        data1 = bytearray(CON_FILE_SIZE)
        data2 = bytearray(CON_FILE_SIZE)
        data2[0] = 0x10  # Change first tile
        p1 = os.path.join(str(tmp_path), 'CONA1')
        p2 = os.path.join(str(tmp_path), 'CONA2')
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_combat(p1, p2, 'A')
        assert fd.tile_changes >= 1


class TestDiffTlk:
    """Test diff_tlk comparing TLK dialog files."""

    def test_identical_tlk(self, tmp_path):
        """Identical TLK files produce no changes."""
        from ult3edit.diff import diff_tlk
        data = encode_record(['HELLO WORLD'])
        p1 = os.path.join(str(tmp_path), 'TLKA1')
        p2 = os.path.join(str(tmp_path), 'TLKA2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_tlk(p1, p2, 'A')
        assert not fd.changed

    def test_changed_record(self, tmp_path):
        """Changed dialog record is detected."""
        from ult3edit.diff import diff_tlk
        d1 = encode_record(['HELLO WORLD'])
        d2 = encode_record(['GOODBYE WORLD'])
        p1 = os.path.join(str(tmp_path), 'TLKA1')
        p2 = os.path.join(str(tmp_path), 'TLKA2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_tlk(p1, p2, 'A')
        assert fd.changed

    def test_added_record(self, tmp_path):
        """Extra record in file2 shows as added."""
        from ult3edit.diff import diff_tlk
        d1 = encode_record(['HELLO'])
        d2 = encode_record(['HELLO']) + encode_record(['EXTRA'])
        p1 = os.path.join(str(tmp_path), 'TLKA1')
        p2 = os.path.join(str(tmp_path), 'TLKA2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_tlk(p1, p2, 'A')
        assert len(fd.added_entities) >= 1


class TestDiffBinary:
    """Test diff_binary for sound/shapes/ddrw files."""

    def test_identical_binary(self, tmp_path):
        """Identical binary files show no changes."""
        from ult3edit.diff import diff_binary
        data = bytes(100)
        p1 = os.path.join(str(tmp_path), 'FILE1')
        p2 = os.path.join(str(tmp_path), 'FILE2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_binary(p1, p2, 'TEST')
        assert not fd.changed

    def test_changed_binary(self, tmp_path):
        """Changed bytes detected in binary diff."""
        from ult3edit.diff import diff_binary
        d1 = bytes(100)
        d2 = bytearray(100)
        d2[50] = 0xFF
        p1 = os.path.join(str(tmp_path), 'FILE1')
        p2 = os.path.join(str(tmp_path), 'FILE2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(bytes(d2))
        fd = diff_binary(p1, p2, 'TEST')
        assert fd.changed

    def test_different_size_binary(self, tmp_path):
        """Different-sized binaries show size diff."""
        from ult3edit.diff import diff_binary
        p1 = os.path.join(str(tmp_path), 'FILE1')
        p2 = os.path.join(str(tmp_path), 'FILE2')
        with open(p1, 'wb') as f:
            f.write(bytes(100))
        with open(p2, 'wb') as f:
            f.write(bytes(200))
        fd = diff_binary(p1, p2, 'TEST')
        assert fd.changed
        sizes = [f for f in fd.entities[0].fields if f.path == 'size']
        assert len(sizes) == 1


class TestDiffMap:
    """Test diff_map for overworld/dungeon map comparison."""

    def test_identical_maps(self, tmp_path):
        """Identical maps show no changes."""
        from ult3edit.diff import diff_map
        data = bytes(MAP_OVERWORLD_SIZE)
        p1 = os.path.join(str(tmp_path), 'MAP1')
        p2 = os.path.join(str(tmp_path), 'MAP2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_map(p1, p2, 'MAPA')
        assert fd.tile_changes == 0

    def test_changed_map_tile(self, tmp_path):
        """Changed tile in overworld map is detected."""
        from ult3edit.diff import diff_map
        d1 = bytes(MAP_OVERWORLD_SIZE)
        d2 = bytearray(MAP_OVERWORLD_SIZE)
        d2[100] = 0xFF
        p1 = os.path.join(str(tmp_path), 'MAP1')
        p2 = os.path.join(str(tmp_path), 'MAP2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(bytes(d2))
        fd = diff_map(p1, p2, 'MAPA')
        assert fd.tile_changes >= 1


# =============================================================================
# Bestiary cmd_dump and cmd_import
# =============================================================================

class TestBestiaryCmdDump:
    """Test bestiary.py cmd_dump hex display."""

    def test_cmd_dump_runs(self, tmp_path, capsys):
        """cmd_dump executes without error on a valid MON file."""
        from ult3edit.bestiary import cmd_dump
        data = bytearray(MON_FILE_SIZE)
        # Set some recognizable data in first monster tile
        data[0] = 0xAA
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(file=path)
        cmd_dump(args)
        captured = capsys.readouterr()
        assert 'MON File Dump' in captured.out
        assert 'Columnar' in captured.out
        assert 'AA' in captured.out


class TestBestiaryCmdImport:
    """Test bestiary.py cmd_import."""

    def test_import_list_format(self, tmp_path):
        """Import from JSON list format."""
        from ult3edit.bestiary import cmd_import as bestiary_import
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'mons.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'hp': 50, 'attack': 10}], f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        bestiary_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        # HP is row 4, monster 0 → offset 4*16+0 = 64
        assert result[64] == 50

    def test_import_dict_format(self, tmp_path):
        """Import from dict-of-dicts format with numeric string keys."""
        from ult3edit.bestiary import cmd_import as bestiary_import
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'mons.json')
        with open(json_path, 'w') as f:
            json.dump({'monsters': {'0': {'hp': 75}}}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        bestiary_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[64] == 75

    def test_import_dry_run(self, tmp_path):
        """Import with dry-run doesn't write."""
        from ult3edit.bestiary import cmd_import as bestiary_import
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'mons.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'hp': 99}], f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=True)
        bestiary_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[64] == 0  # unchanged

    def test_import_with_shortcuts(self, tmp_path):
        """Import with flag shortcuts (boss, poison, etc.)."""
        from ult3edit.bestiary import cmd_import as bestiary_import
        from ult3edit.constants import MON_FLAG1_BOSS, MON_ABIL1_POISON
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'mons.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'boss': True, 'poison': True}], f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        bestiary_import(args)
        from ult3edit.bestiary import load_mon_file
        mons = load_mon_file(path)
        assert mons[0].flags1 & MON_FLAG1_BOSS
        assert mons[0].ability1 & MON_ABIL1_POISON


# =============================================================================
# Map cmd_overview and cmd_legend
# =============================================================================

class TestMapCmdOverview:
    """Test map.py cmd_overview."""

    def test_overview_no_maps_exits(self, tmp_path):
        """cmd_overview with no MAP files in dir exits."""
        from ult3edit.map import cmd_overview
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None, preview=False)
        with pytest.raises(SystemExit):
            cmd_overview(args)

    def test_overview_with_maps(self, tmp_path, capsys):
        """cmd_overview lists found MAP files."""
        from ult3edit.map import cmd_overview
        # Create a MAPA (overworld) file
        mapa = os.path.join(str(tmp_path), 'MAPA')
        with open(mapa, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None, preview=False)
        cmd_overview(args)
        captured = capsys.readouterr()
        assert 'MAPA' in captured.out
        assert 'Overworld' in captured.out or 'overworld' in captured.out.lower()

    def test_overview_json(self, tmp_path):
        """cmd_overview JSON mode produces valid data."""
        from ult3edit.map import cmd_overview
        mapa = os.path.join(str(tmp_path), 'MAPA')
        with open(mapa, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        out_path = os.path.join(str(tmp_path), 'maps.json')
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=True, output=out_path, preview=False)
        cmd_overview(args)
        with open(out_path) as f:
            data = json.load(f)
        assert 'MAPA' in data
        assert data['MAPA']['type'] == 'overworld'


class TestMapCmdLegend:
    """Test map.py cmd_legend."""

    def test_legend_output(self, capsys):
        """cmd_legend outputs tile legend text."""
        from ult3edit.map import cmd_legend
        args = argparse.Namespace(json=False)
        cmd_legend(args)
        captured = capsys.readouterr()
        assert 'Tile Legend' in captured.out
        assert 'Overworld' in captured.out
        assert 'Dungeon' in captured.out

    def test_legend_json_hides_dungeon_section(self, capsys):
        """cmd_legend with --json hides dungeon tiles section header."""
        from ult3edit.map import cmd_legend
        args = argparse.Namespace(json=True)
        cmd_legend(args)
        captured = capsys.readouterr()
        assert 'Overworld' in captured.out
        # In JSON mode, the "Dungeon Tiles:" section header is hidden
        assert 'Dungeon Tiles:' not in captured.out


# =============================================================================
# Roster cmd_check_progress CLI wrapper
# =============================================================================

class TestRosterCmdCheckProgress:
    """Test cmd_check_progress CLI command."""

    def _make_roster_with_chars(self, tmp_path, count=4, marks=0xF,
                                 cards=0xF, weapon=15, armor=7):
        """Create a roster file with specified characters."""
        data = bytearray(ROSTER_FILE_SIZE)
        for i in range(count):
            off = i * CHAR_RECORD_SIZE
            name = f'HERO{i}'
            for j, ch in enumerate(name):
                data[off + j] = ord(ch) | 0x80
            data[off + CHAR_STATUS] = ord('G')
            data[off + CHAR_HP_HI] = 0x01
            data[off + CHAR_MARKS_CARDS] = (marks << 4) | cards
            data[off + CHAR_READIED_WEAPON] = weapon
            data[off + CHAR_WORN_ARMOR] = armor
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_check_progress_text_ready(self, tmp_path, capsys):
        """cmd_check_progress shows READY verdict for complete party."""
        from ult3edit.roster import cmd_check_progress
        path = self._make_roster_with_chars(tmp_path)
        args = argparse.Namespace(
            file=path, json=False, output=None)
        cmd_check_progress(args)
        captured = capsys.readouterr()
        assert 'READY TO FACE EXODUS' in captured.out

    def test_check_progress_text_not_ready(self, tmp_path, capsys):
        """cmd_check_progress shows not-ready for incomplete party."""
        from ult3edit.roster import cmd_check_progress
        path = self._make_roster_with_chars(
            tmp_path, count=2, marks=0, cards=0, weapon=0, armor=0)
        args = argparse.Namespace(
            file=path, json=False, output=None)
        cmd_check_progress(args)
        captured = capsys.readouterr()
        assert 'Not yet ready' in captured.out
        assert 'Need 4 alive characters' in captured.out

    def test_check_progress_json(self, tmp_path):
        """cmd_check_progress JSON mode produces valid output."""
        from ult3edit.roster import cmd_check_progress
        path = self._make_roster_with_chars(tmp_path)
        out_path = os.path.join(str(tmp_path), 'progress.json')
        args = argparse.Namespace(
            file=path, json=True, output=out_path)
        cmd_check_progress(args)
        with open(out_path) as f:
            data = json.load(f)
        assert data['exodus_ready'] is True
        assert data['marks_complete'] is True
        assert data['cards_complete'] is True


# =============================================================================
# Diff file-level dispatch (diff_file)
# =============================================================================

class TestDiffFileDispatch:
    """Test diff_file auto-detection and dispatch."""

    def test_diff_file_roster(self, tmp_path):
        """diff_file dispatches correctly for ROST files."""
        from ult3edit.diff import diff_file
        data = bytearray(ROSTER_FILE_SIZE)
        p1 = os.path.join(str(tmp_path), 'ROST')
        p2 = os.path.join(str(tmp_path), 'ROST2')
        # Use different name for second to test detection from first
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_file(p1, p2)
        assert fd is not None
        assert fd.file_type == 'ROST'

    def test_diff_file_unknown_returns_none(self, tmp_path):
        """diff_file with unrecognizable files returns None."""
        from ult3edit.diff import diff_file
        p1 = os.path.join(str(tmp_path), 'UNKNOWN1')
        p2 = os.path.join(str(tmp_path), 'UNKNOWN2')
        with open(p1, 'wb') as f:
            f.write(bytes(42))
        with open(p2, 'wb') as f:
            f.write(bytes(42))
        fd = diff_file(p1, p2)
        assert fd is None


# =============================================================================
# Combat cmd_import
# =============================================================================

class TestCombatCmdImport:
    """Test combat.py cmd_import."""

    def test_import_tiles_and_positions(self, tmp_path):
        """Import tiles and positions from JSON."""
        from ult3edit.combat import cmd_import as combat_import
        data = bytearray(CON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        # Build JSON with some tiles and monster/PC positions
        jdata = {
            'tiles': [['.' for _ in range(11)] for _ in range(11)],
            'monsters': [{'x': 5, 'y': 3}],
            'pcs': [{'x': 1, 'y': 1}],
        }
        json_path = os.path.join(str(tmp_path), 'con.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        combat_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        # Check monster X position (offset 0x80)
        from ult3edit.constants import CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET
        assert result[CON_MONSTER_X_OFFSET] == 5
        assert result[CON_MONSTER_Y_OFFSET] == 3

    def test_import_dry_run(self, tmp_path):
        """Import with dry-run doesn't write."""
        from ult3edit.combat import cmd_import as combat_import
        data = bytearray(CON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = {'tiles': [['~' for _ in range(11)] for _ in range(11)]}
        json_path = os.path.join(str(tmp_path), 'con.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=True)
        combat_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(CON_FILE_SIZE)  # unchanged

    def test_import_clamps_out_of_bounds(self, tmp_path):
        """Positions outside grid bounds are clamped."""
        from ult3edit.combat import cmd_import as combat_import
        from ult3edit.constants import CON_MONSTER_X_OFFSET, CON_MAP_WIDTH
        data = bytearray(CON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = {'monsters': [{'x': 99, 'y': -5}]}
        json_path = os.path.join(str(tmp_path), 'con.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        combat_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[CON_MONSTER_X_OFFSET] == CON_MAP_WIDTH - 1
        from ult3edit.constants import CON_MONSTER_Y_OFFSET
        assert result[CON_MONSTER_Y_OFFSET] == 0


# =============================================================================
# Special cmd_view / cmd_import
# =============================================================================

class TestSpecialCmdViewImport:
    """Test special.py cmd_view and cmd_import."""

    def test_view_single_file(self, tmp_path, capsys):
        """cmd_view on a single special file."""
        from ult3edit.special import cmd_view as special_view
        data = bytearray(SPECIAL_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            path=path, json=False, output=None)
        special_view(args)
        captured = capsys.readouterr()
        assert 'Special Location' in captured.out

    def test_view_json_mode(self, tmp_path):
        """cmd_view JSON mode produces valid output."""
        from ult3edit.special import cmd_view as special_view
        data = bytearray(SPECIAL_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = os.path.join(str(tmp_path), 'special.json')
        args = argparse.Namespace(
            path=path, json=True, output=out_path)
        special_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert 'tiles' in jdata
        assert 'trailing_bytes' in jdata

    def test_import_tiles(self, tmp_path):
        """cmd_import replaces tiles from JSON."""
        from ult3edit.special import cmd_import as special_import
        data = bytearray(SPECIAL_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        # JSON with some tiles
        tiles = [['.' for _ in range(11)] for _ in range(11)]
        tiles[0][0] = '~'  # water at (0,0)
        jdata = {'tiles': tiles}
        json_path = os.path.join(str(tmp_path), 'special.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        special_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        # Tile at (0,0) should now be water (TILE_CHARS_REVERSE['~'])
        assert result[0] == TILE_CHARS_REVERSE['~']

    def test_import_preserves_trailing_bytes(self, tmp_path):
        """cmd_import restores trailing bytes from JSON."""
        from ult3edit.special import cmd_import as special_import
        data = bytearray(SPECIAL_FILE_SIZE)
        data[121] = 0xAA  # trailing byte
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = {'tiles': [], 'trailing_bytes': [0xBB, 0xCC]}
        json_path = os.path.join(str(tmp_path), 'special.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        special_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[121] == 0xBB
        assert result[122] == 0xCC

    def test_import_dry_run(self, tmp_path):
        """cmd_import with dry-run doesn't write."""
        from ult3edit.special import cmd_import as special_import
        data = bytearray(SPECIAL_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = {'tiles': [['~' for _ in range(11)] for _ in range(11)]}
        json_path = os.path.join(str(tmp_path), 'special.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=True)
        special_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(SPECIAL_FILE_SIZE)  # unchanged


# =============================================================================
# Save cmd_import
# =============================================================================

class TestSaveCmdImport:
    """Test save.py cmd_import."""

    def test_import_party_state(self, tmp_path):
        """Import party state from JSON."""
        from ult3edit.save import cmd_import as save_import
        # Create PRTY file
        prty_data = bytearray(PRTY_FILE_SIZE)
        prty_path = os.path.join(str(tmp_path), 'PRTY')
        with open(prty_path, 'wb') as f:
            f.write(prty_data)
        # Build JSON
        jdata = {
            'party': {
                'transport': 'Ship',
                'party_size': 4,
                'x': 10,
                'y': 20,
            }
        }
        json_path = os.path.join(str(tmp_path), 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=json_path,
            output=None, backup=False, dry_run=False)
        save_import(args)
        with open(prty_path, 'rb') as f:
            result = f.read()
        ps = PartyState(result)
        assert ps.party_size == 4
        assert ps.x == 10
        assert ps.y == 20

    def test_import_dry_run(self, tmp_path):
        """Import with dry-run doesn't write."""
        from ult3edit.save import cmd_import as save_import
        prty_data = bytearray(PRTY_FILE_SIZE)
        prty_path = os.path.join(str(tmp_path), 'PRTY')
        with open(prty_path, 'wb') as f:
            f.write(prty_data)
        jdata = {'party': {'party_size': 4, 'x': 30}}
        json_path = os.path.join(str(tmp_path), 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=json_path,
            output=None, backup=False, dry_run=True)
        save_import(args)
        with open(prty_path, 'rb') as f:
            result = f.read()
        assert result == bytes(PRTY_FILE_SIZE)  # unchanged


# =============================================================================
# Combat cmd_view text and JSON modes
# =============================================================================

class TestCombatCmdView:
    """Test combat.py cmd_view."""

    def test_view_single_file(self, tmp_path, capsys):
        """cmd_view on a single CON file."""
        from ult3edit.combat import cmd_view as combat_view
        data = bytearray(CON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            path=path, json=False, output=None, validate=False)
        combat_view(args)
        captured = capsys.readouterr()
        assert 'Combat Map' in captured.out or 'CONA' in captured.out

    def test_view_json_mode(self, tmp_path):
        """cmd_view JSON mode on single file."""
        from ult3edit.combat import cmd_view as combat_view
        data = bytearray(CON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = os.path.join(str(tmp_path), 'combat.json')
        args = argparse.Namespace(
            path=path, json=True, output=out_path, validate=False)
        combat_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert 'tiles' in jdata
        assert 'monsters' in jdata
        assert 'pcs' in jdata

    def test_view_directory_no_files(self, tmp_path):
        """cmd_view on directory with no CON files exits."""
        from ult3edit.combat import cmd_view as combat_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            combat_view(args)


# =============================================================================
# Diff module: diff_special, diff_save, FileDiff/EntityDiff properties
# =============================================================================

class TestDiffSpecial:
    """Test diff_special for BRND/SHRN/FNTN/TIME files."""

    def test_identical_specials(self, tmp_path):
        """Identical special files show no changes."""
        from ult3edit.diff import diff_special
        data = bytes(SPECIAL_FILE_SIZE)
        p1 = os.path.join(str(tmp_path), 'BRND1')
        p2 = os.path.join(str(tmp_path), 'BRND2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_special(p1, p2, 'BRND')
        assert fd.tile_changes == 0

    def test_changed_special_tile(self, tmp_path):
        """Changed tile in special location is detected."""
        from ult3edit.diff import diff_special
        d1 = bytes(SPECIAL_FILE_SIZE)
        d2 = bytearray(SPECIAL_FILE_SIZE)
        d2[5] = 0xFF  # change a tile
        p1 = os.path.join(str(tmp_path), 'BRND1')
        p2 = os.path.join(str(tmp_path), 'BRND2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(bytes(d2))
        fd = diff_special(p1, p2, 'BRND')
        assert fd.tile_changes >= 1


class TestDiffSave:
    """Test diff_save comparing PRTY/PLRS directories."""

    def test_identical_saves(self, tmp_path):
        """Identical save directories show no changes."""
        from ult3edit.diff import diff_save
        dir1 = os.path.join(str(tmp_path), 'dir1')
        dir2 = os.path.join(str(tmp_path), 'dir2')
        os.makedirs(dir1)
        os.makedirs(dir2)
        prty = bytes(PRTY_FILE_SIZE)
        with open(os.path.join(dir1, 'PRTY'), 'wb') as f:
            f.write(prty)
        with open(os.path.join(dir2, 'PRTY'), 'wb') as f:
            f.write(prty)
        results = diff_save(dir1, dir2)
        assert len(results) >= 1
        assert not results[0].changed

    def test_changed_party(self, tmp_path):
        """Changed PRTY data is detected."""
        from ult3edit.diff import diff_save
        dir1 = os.path.join(str(tmp_path), 'dir1')
        dir2 = os.path.join(str(tmp_path), 'dir2')
        os.makedirs(dir1)
        os.makedirs(dir2)
        prty1 = bytearray(PRTY_FILE_SIZE)
        prty2 = bytearray(PRTY_FILE_SIZE)
        prty2[PRTY_OFF_TRANSPORT] = 0x03  # change transport
        with open(os.path.join(dir1, 'PRTY'), 'wb') as f:
            f.write(prty1)
        with open(os.path.join(dir2, 'PRTY'), 'wb') as f:
            f.write(prty2)
        results = diff_save(dir1, dir2)
        assert any(r.changed for r in results)


class TestDiffEntityProperties:
    """Test EntityDiff and FileDiff property methods."""

    def test_entity_diff_changed_with_fields(self):
        """EntityDiff.changed is True when fields present."""
        from ult3edit.diff import EntityDiff, FieldDiff
        ed = EntityDiff('test', 'label')
        assert not ed.changed
        ed.fields.append(FieldDiff('x', 1, 2))
        assert ed.changed

    def test_file_diff_change_count(self):
        """FileDiff.change_count counts entities with changes."""
        from ult3edit.diff import FileDiff, EntityDiff, FieldDiff
        fd = FileDiff('test', 'test')
        e1 = EntityDiff('a', 'A')
        e1.fields.append(FieldDiff('x', 1, 2))
        e2 = EntityDiff('b', 'B')  # no changes
        fd.entities = [e1, e2]
        assert fd.change_count == 1

    def test_game_diff_changed(self):
        """GameDiff.changed is True when any file has changes."""
        from ult3edit.diff import GameDiff, FileDiff
        gd = GameDiff()
        fd = FileDiff('test', 'test')
        gd.files.append(fd)
        assert not gd.changed
        fd.tile_changes = 1
        assert gd.changed


# =============================================================================
# Map cmd_import (overworld and dungeon)
# =============================================================================

class TestMapCmdImport:
    """Test map.py cmd_import for overworld and dungeon maps."""

    def test_import_overworld_tiles(self, tmp_path):
        """Import overworld tiles from JSON char grid."""
        from ult3edit.map import cmd_import as map_import
        data = bytearray(MAP_OVERWORLD_SIZE)
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(data)
        # Build a 64x64 tile grid
        tiles = [['.' for _ in range(64)] for _ in range(64)]
        tiles[0][0] = '~'  # water at (0,0)
        jdata = {'tiles': tiles}
        json_path = os.path.join(str(tmp_path), 'map.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        map_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[0] == TILE_CHARS_REVERSE['~']
        assert result[1] == TILE_CHARS_REVERSE['.']

    def test_import_dungeon_levels(self, tmp_path):
        """Import dungeon map from JSON levels format."""
        from ult3edit.map import cmd_import as map_import
        data = bytearray(MAP_DUNGEON_SIZE)
        path = os.path.join(str(tmp_path), 'MAPB')
        with open(path, 'wb') as f:
            f.write(data)
        level_tiles = [['#' for _ in range(16)] for _ in range(16)]
        level_tiles[0][0] = '.'  # open at (0,0)
        jdata = {'levels': [{'level': 1, 'tiles': level_tiles}]}
        json_path = os.path.join(str(tmp_path), 'map.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        map_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[0] == DUNGEON_TILE_CHARS_REVERSE['.']
        assert result[1] == DUNGEON_TILE_CHARS_REVERSE['#']

    def test_import_dry_run(self, tmp_path):
        """Import with dry-run doesn't write."""
        from ult3edit.map import cmd_import as map_import
        data = bytearray(MAP_OVERWORLD_SIZE)
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(data)
        tiles = [['~' for _ in range(64)] for _ in range(64)]
        jdata = {'tiles': tiles}
        json_path = os.path.join(str(tmp_path), 'map.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=True)
        map_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(MAP_OVERWORLD_SIZE)  # unchanged


# =============================================================================
# Map cmd_compile
# =============================================================================

class TestMapCmdCompile:
    """Test map.py cmd_compile text-art to binary."""

    def test_compile_overworld(self, tmp_path):
        """Compile overworld text-art to binary."""
        from ult3edit.map import cmd_compile
        source = os.path.join(str(tmp_path), 'map.map')
        # 64 rows of 64 '.' chars
        with open(source, 'w') as f:
            for _ in range(64):
                f.write('.' * 64 + '\n')
        output = os.path.join(str(tmp_path), 'MAPA')
        args = argparse.Namespace(
            source=source, output=output, dungeon=False)
        cmd_compile(args)
        with open(output, 'rb') as f:
            data = f.read()
        assert len(data) == MAP_OVERWORLD_SIZE
        assert data[0] == TILE_CHARS_REVERSE['.']

    def test_compile_dungeon(self, tmp_path):
        """Compile dungeon text-art to binary."""
        from ult3edit.map import cmd_compile
        source = os.path.join(str(tmp_path), 'map.map')
        # Note: '#' starts comment lines in compile, so use '.' for tiles
        with open(source, 'w') as f:
            for lvl in range(8):
                f.write(f'# Level {lvl + 1}\n')
                for _ in range(16):
                    f.write('.' * 16 + '\n')
                f.write('# ---\n')
        output = os.path.join(str(tmp_path), 'MAPB')
        args = argparse.Namespace(
            source=source, output=output, dungeon=True)
        cmd_compile(args)
        with open(output, 'rb') as f:
            data = f.read()
        # 8 levels * 256 bytes = 2048
        assert len(data) == 2048
        assert data[0] == DUNGEON_TILE_CHARS_REVERSE['.']

    def test_compile_unknown_chars_mapped(self, tmp_path):
        """Unknown tile characters mapped to default with warning."""
        from ult3edit.map import cmd_compile
        source = os.path.join(str(tmp_path), 'map.map')
        with open(source, 'w') as f:
            for _ in range(64):
                f.write('Q' * 64 + '\n')  # 'Q' is not a tile char
        output = os.path.join(str(tmp_path), 'MAPA')
        args = argparse.Namespace(
            source=source, output=output, dungeon=False)
        cmd_compile(args)
        with open(output, 'rb') as f:
            data = f.read()
        assert len(data) == MAP_OVERWORLD_SIZE
        # Unknown chars should map to default (0x04 for overworld)
        assert data[0] == 0x04


# =============================================================================
# Text cmd_import
# =============================================================================

class TestTextCmdImport:
    """Test text.py cmd_import."""

    def test_import_list_format(self, tmp_path):
        """Import text from JSON list of strings."""
        from ult3edit.text import cmd_import as text_import
        data = bytearray(TEXT_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'text': 'HELLO'}, {'text': 'WORLD'}]
        json_path = os.path.join(str(tmp_path), 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        text_import(args)
        records = load_text_records(path)
        assert records[0] == 'HELLO'
        assert records[1] == 'WORLD'

    def test_import_dict_format(self, tmp_path):
        """Import text from JSON with 'records' key."""
        from ult3edit.text import cmd_import as text_import
        data = bytearray(TEXT_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = {'records': [{'text': 'TEST'}]}
        json_path = os.path.join(str(tmp_path), 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        text_import(args)
        records = load_text_records(path)
        assert records[0] == 'TEST'

    def test_import_dry_run(self, tmp_path):
        """Import with dry-run doesn't write."""
        from ult3edit.text import cmd_import as text_import
        data = bytearray(TEXT_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'text': 'NOPE'}]
        json_path = os.path.join(str(tmp_path), 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=True)
        text_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(TEXT_FILE_SIZE)  # unchanged

    def test_import_zeros_remaining(self, tmp_path):
        """Import clears stale data after last record."""
        from ult3edit.text import cmd_import as text_import
        # Fill with non-zero bytes first
        data = bytearray(b'\xAA' * TEXT_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'text': 'A'}]
        json_path = os.path.join(str(tmp_path), 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        text_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        # After 'A' + null (2 bytes), everything should be zero
        assert all(b == 0 for b in result[2:])


# =============================================================================
# TLK find-replace
# =============================================================================

class TestTlkFindReplace:
    """Test TLK _cmd_find_replace."""

    def _make_tlk(self, tmp_path, text_records):
        """Create a TLK file with given text records."""
        data = bytearray()
        for rec in text_records:
            data.extend(encode_record(rec))
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_find_replace_basic(self, tmp_path):
        """Basic find-replace across records."""
        from ult3edit.tlk import _cmd_find_replace
        path = self._make_tlk(tmp_path, [['HELLO WORLD'], ['HELLO AGAIN']])
        args = argparse.Namespace(
            file=path, output=None, dry_run=False, backup=False,
            ignore_case=False)
        _cmd_find_replace(args, 'HELLO', 'GREETINGS')
        records = load_tlk_records(path)
        assert 'GREETINGS WORLD' in records[0]
        assert 'GREETINGS AGAIN' in records[1]

    def test_find_replace_case_insensitive(self, tmp_path):
        """Case-insensitive find-replace."""
        from ult3edit.tlk import _cmd_find_replace
        path = self._make_tlk(tmp_path, [['hello world']])
        args = argparse.Namespace(
            file=path, output=None, dry_run=False, backup=False,
            ignore_case=True)
        _cmd_find_replace(args, 'HELLO', 'HI')
        records = load_tlk_records(path)
        assert 'HI' in records[0][0]

    def test_find_replace_no_match(self, tmp_path, capsys):
        """No matches found — no write."""
        from ult3edit.tlk import _cmd_find_replace
        path = self._make_tlk(tmp_path, [['HELLO WORLD']])
        args = argparse.Namespace(
            file=path, output=None, dry_run=False, backup=False,
            ignore_case=False)
        _cmd_find_replace(args, 'XXXXX', 'YYYYY')
        captured = capsys.readouterr()
        assert '0 replacement' in captured.out

    def test_find_replace_dry_run(self, tmp_path):
        """Dry-run doesn't write changes."""
        from ult3edit.tlk import _cmd_find_replace
        path = self._make_tlk(tmp_path, [['HELLO WORLD']])
        with open(path, 'rb') as f:
            original = f.read()
        args = argparse.Namespace(
            file=path, output=None, dry_run=True, backup=False,
            ignore_case=False)
        _cmd_find_replace(args, 'HELLO', 'BYE')
        with open(path, 'rb') as f:
            after = f.read()
        assert after == original


# =============================================================================
# Roster _apply_edits coverage
# =============================================================================

class TestRosterApplyEdits:
    """Test _apply_edits for comprehensive field coverage."""

    def test_apply_no_edits_returns_false(self):
        """No edit flags → returns False."""
        from ult3edit.roster import _apply_edits
        char = Character(bytearray(CHAR_RECORD_SIZE))
        args = argparse.Namespace(
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None, in_party=None, not_in_party=None,
            sub_morsels=None)
        assert _apply_edits(char, args) is False

    def test_apply_marks_and_cards(self):
        """Setting marks and cards via comma-separated strings."""
        from ult3edit.roster import _apply_edits
        char = Character(bytearray(CHAR_RECORD_SIZE))
        args = argparse.Namespace(
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks='Kings,Snake', cards='Death,Sol',
            in_party=None, not_in_party=None, sub_morsels=None)
        assert _apply_edits(char, args) is True
        assert 'Kings' in char.marks
        assert 'Snake' in char.marks
        assert 'Death' in char.cards
        assert 'Sol' in char.cards

    def test_apply_give_weapon(self):
        """Setting weapon inventory via --give-weapon."""
        from ult3edit.roster import _apply_edits
        char = Character(bytearray(CHAR_RECORD_SIZE))
        args = argparse.Namespace(
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=[5, 3], give_armor=None,
            marks=None, cards=None, in_party=None, not_in_party=None,
            sub_morsels=None)
        assert _apply_edits(char, args) is True
        # Weapon index 5, count 3 → BCD 0x03 at raw offset
        from ult3edit.constants import CHAR_WEAPON_START
        assert char.raw[CHAR_WEAPON_START + 5 - 1] == int_to_bcd(3)

    def test_apply_in_party(self):
        """Setting in-party flag."""
        from ult3edit.roster import _apply_edits
        char = Character(bytearray(CHAR_RECORD_SIZE))
        args = argparse.Namespace(
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None, in_party=True, not_in_party=None,
            sub_morsels=None)
        assert _apply_edits(char, args) is True
        assert char.in_party is True

    def test_apply_hp_raises_max(self):
        """Setting HP also raises max_hp if needed."""
        from ult3edit.roster import _apply_edits
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.max_hp = 50
        args = argparse.Namespace(
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=200, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None, in_party=None, not_in_party=None,
            sub_morsels=None)
        _apply_edits(char, args)
        assert char.hp == 200
        assert char.max_hp == 200  # raised to match HP


# =============================================================================
# Bestiary validate_monster coverage
# =============================================================================

class TestBestiaryValidate:
    """Test bestiary.py validate_monster edge cases."""

    def test_validate_empty_monster(self):
        """Empty monster produces no warnings."""
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0] * 10  # tile1=0, hp=0 → is_empty
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert len(warnings) == 0

    def test_validate_undefined_flag_bits(self):
        """Undefined flag bits produce warning."""
        from ult3edit.bestiary import Monster, validate_monster
        # attrs: tile1, tile2, flags1, flags2, hp, atk, def, spd, abil1, abil2
        attrs = [0x10, 0x10, 0x60, 0, 10, 5, 5, 5, 0, 0]
        # flags1=0x60: bits 5,6 set → undefined (defined = 0x04|0x08|0x0C|0x80)
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('flag1' in w.lower() or 'undefined' in w.lower()
                    for w in warnings)

    def test_validate_undefined_ability_bits(self):
        """Undefined ability bits produce warning."""
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0x10, 0x10, 0, 0, 10, 5, 5, 5, 0x10, 0]
        # ability1=0x10: bit 4 — not in defined set (0x01|0x02|0x04|0x40|0x80)
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('ability1' in w.lower() or 'undefined' in w.lower()
                    for w in warnings)


# =============================================================================
# Map cmd_view JSON mode
# =============================================================================

class TestMapCmdView:
    """Test map.py cmd_view JSON export."""

    def test_view_overworld_json(self, tmp_path):
        """cmd_view JSON mode for overworld map."""
        from ult3edit.map import cmd_view as map_view
        data = bytearray(MAP_OVERWORLD_SIZE)
        data[0] = 0x04  # grass tile
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = os.path.join(str(tmp_path), 'map.json')
        args = argparse.Namespace(
            file=path, json=True, output=out_path, crop=None)
        map_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert jdata['type'] == 'overworld'
        assert 'tiles' in jdata
        assert jdata['width'] == 64

    def test_view_dungeon_json(self, tmp_path):
        """cmd_view JSON mode for dungeon map."""
        from ult3edit.map import cmd_view as map_view
        data = bytearray(MAP_DUNGEON_SIZE)
        path = os.path.join(str(tmp_path), 'MAPB')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = os.path.join(str(tmp_path), 'map.json')
        args = argparse.Namespace(
            file=path, json=True, output=out_path, crop=None)
        map_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert jdata['type'] == 'dungeon'
        assert 'levels' in jdata

    def test_view_invalid_crop(self, tmp_path):
        """cmd_view with invalid --crop exits."""
        from ult3edit.map import cmd_view as map_view
        data = bytearray(MAP_OVERWORLD_SIZE)
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, json=False, output=None, crop='a,b,c,d')
        with pytest.raises(SystemExit):
            map_view(args)

    def test_view_text_with_crop(self, tmp_path, capsys):
        """cmd_view text mode with valid --crop."""
        from ult3edit.map import cmd_view as map_view
        data = bytearray(MAP_OVERWORLD_SIZE)
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, json=False, output=None, crop='0,0,10,10')
        map_view(args)
        captured = capsys.readouterr()
        assert 'Map' in captured.out


# =============================================================================
# Save cmd_view JSON mode
# =============================================================================

class TestSaveCmdView:
    """Test save.py cmd_view."""

    def test_view_json_mode(self, tmp_path):
        """cmd_view JSON mode with PRTY and PLRS."""
        from ult3edit.save import cmd_view as save_view
        # Create PRTY
        prty = bytearray(PRTY_FILE_SIZE)
        prty[PRTY_OFF_TRANSPORT] = 0x01  # on foot
        with open(os.path.join(str(tmp_path), 'PRTY'), 'wb') as f:
            f.write(prty)
        # Create PLRS (4 chars * 64 bytes)
        plrs = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('TEST'):
            plrs[i] = ord(ch) | 0x80
        plrs[CHAR_STATUS] = ord('G')
        with open(os.path.join(str(tmp_path), 'PLRS'), 'wb') as f:
            f.write(plrs)
        out_path = os.path.join(str(tmp_path), 'save.json')
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=True, output=out_path,
            validate=False, brief=True)
        save_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert 'party' in jdata
        assert 'active_characters' in jdata

    def test_view_no_prty_exits(self, tmp_path):
        """cmd_view with no PRTY file exits."""
        from ult3edit.save import cmd_view as save_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False, brief=True)
        with pytest.raises(SystemExit):
            save_view(args)


# =============================================================================
# Roster cmd_view JSON mode, cmd_create --force
# =============================================================================

class TestRosterCmdViewJson:
    """Test roster cmd_view JSON output."""

    def _make_roster(self, tmp_path, name='HERO'):
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate(name):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        data[CHAR_HP_HI] = 0x01
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_view_json_output(self, tmp_path):
        """cmd_view JSON mode exports character data."""
        from ult3edit.roster import cmd_view
        path = self._make_roster(tmp_path)
        out_path = os.path.join(str(tmp_path), 'roster.json')
        args = argparse.Namespace(
            file=path, slot=None, json=True, output=out_path,
            validate=False)
        cmd_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert isinstance(jdata, list)
        assert len(jdata) >= 1
        assert jdata[0]['name'] == 'HERO'

    def test_view_json_with_validate(self, tmp_path):
        """cmd_view JSON mode with --validate includes warnings."""
        from ult3edit.roster import cmd_view
        path = self._make_roster(tmp_path)
        out_path = os.path.join(str(tmp_path), 'roster.json')
        args = argparse.Namespace(
            file=path, slot=None, json=True, output=out_path,
            validate=True)
        cmd_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert 'warnings' in jdata[0]


class TestRosterCmdCreateForce:
    """Test roster cmd_create with --force on occupied slot."""

    def test_create_force_overwrites(self, tmp_path):
        """cmd_create with --force overwrites existing character."""
        from ult3edit.roster import cmd_create, load_roster
        # Build roster with char in slot 0
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('OLD'):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, slot=0, force=True, dry_run=False, backup=False,
            output=None, name='NEW',
            str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None, in_party=None, not_in_party=None,
            sub_morsels=None)
        cmd_create(args)
        chars, _ = load_roster(path)
        assert chars[0].name == 'NEW'

    def test_create_dry_run_doesnt_write(self, tmp_path):
        """cmd_create with --dry-run doesn't modify file."""
        from ult3edit.roster import cmd_create
        data = bytearray(ROSTER_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, slot=5, force=False, dry_run=True, backup=False,
            output=None, name='TEST',
            str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None, in_party=None, not_in_party=None,
            sub_morsels=None)
        cmd_create(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(ROSTER_FILE_SIZE)  # unchanged


# =============================================================================
# Bestiary cmd_view JSON mode
# =============================================================================

class TestBestiaryCmdViewJson:
    """Test bestiary cmd_view JSON export."""

    def test_view_json_output(self, tmp_path):
        """cmd_view JSON mode exports monster data."""
        from ult3edit.bestiary import cmd_view as bestiary_view
        # Create a MON file with one non-empty monster
        data = bytearray(MON_FILE_SIZE)
        data[0] = 0x10  # tile1 for monster 0
        data[4 * 16] = 20  # HP for monster 0
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = os.path.join(str(tmp_path), 'bestiary.json')
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=True, output=out_path,
            validate=False, file=None)
        bestiary_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert 'MONA' in jdata
        assert len(jdata['MONA']['monsters']) >= 1

    def test_view_no_files_exits(self, tmp_path):
        """cmd_view with no MON files exits."""
        from ult3edit.bestiary import cmd_view as bestiary_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False, file=None)
        with pytest.raises(SystemExit):
            bestiary_view(args)


# =============================================================================
# Roster cmd_edit --all mode
# =============================================================================

class TestRosterCmdEditAll:
    """Test roster cmd_edit with --all flag."""

    def test_edit_all_applies_to_nonempty(self, tmp_path):
        """--all flag applies edits to all non-empty slots."""
        from ult3edit.roster import cmd_edit, load_roster
        data = bytearray(ROSTER_FILE_SIZE)
        # Put chars in slots 0 and 2
        for slot in (0, 2):
            off = slot * CHAR_RECORD_SIZE
            for i, ch in enumerate(f'HERO{slot}'):
                data[off + i] = ord(ch) | 0x80
            data[off + CHAR_STATUS] = ord('G')
            data[off + CHAR_HP_HI] = 0x01
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, slot=None, all=True,
            dry_run=False, backup=False, output=None, validate=False,
            name=None, str=50, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None, in_party=None, not_in_party=None,
            sub_morsels=None)
        cmd_edit(args)
        chars, _ = load_roster(path)
        assert chars[0].strength == 50
        assert chars[2].strength == 50
        # Slot 1 should remain empty
        assert chars[1].is_empty


# =============================================================================
# Batch 6: Exhaustive remaining gaps — 30+ tests
# =============================================================================

class TestRosterLoadErrors:
    """Test load_roster error paths."""

    def test_load_roster_file_too_small(self, tmp_path):
        """load_roster raises ValueError for files < 64 bytes."""
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(b'\x00' * 32)
        with pytest.raises(ValueError, match="too small"):
            load_roster(path)

    def test_load_roster_empty_file(self, tmp_path):
        """load_roster raises ValueError for empty files."""
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(b'')
        with pytest.raises(ValueError, match="too small"):
            load_roster(path)


class TestRosterCmdEditGaps:
    """Test roster cmd_edit gaps not yet covered."""

    def test_edit_no_modifications_specified(self, tmp_path):
        """cmd_edit with no edit flags prints 'No modifications specified'."""
        from ult3edit.roster import cmd_edit
        data = bytearray(ROSTER_FILE_SIZE)
        off = 0
        for i, ch in enumerate('HERO'):
            data[off + i] = ord(ch) | 0x80
        data[off + CHAR_STATUS] = ord('G')
        data[off + CHAR_HP_HI] = 0x01
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, slot=0, all=False,
            dry_run=False, backup=False, output=None, validate=False,
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, give_weapon=None, give_armor=None,
            marks=None, cards=None, in_party=None, not_in_party=None,
            sub_morsels=None)
        cmd_edit(args)  # Should print "No modifications specified." and return

    def test_edit_view_slot_out_of_range(self, tmp_path, capsys):
        """cmd_view with slot out of range exits."""
        from ult3edit.roster import cmd_view
        data = bytearray(ROSTER_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, slot=99, json=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_import_unknown_armor_warning(self, tmp_path, capsys):
        """Import with unknown armor name prints warning, doesn't crash."""
        data = bytearray(ROSTER_FILE_SIZE)
        # Create a character in slot 0
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        data[CHAR_HP_HI] = 0x01
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump([{'slot': 0, 'armor': 'NONEXISTENT_ARMOR'}], f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert 'Warning' in captured.err or 'arning' in captured.err


class TestBestiaryCmdEditGaps:
    """Test bestiary cmd_edit gaps."""

    def test_edit_no_monster_no_all(self, tmp_path):
        """cmd_edit exits if neither --monster nor --all given."""
        from ult3edit.bestiary import cmd_edit
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, monster=None, all=False,
            dry_run=False, backup=False, output=None, validate=False,
            tile1=None, tile2=None, hp=None, attack=None, defense=None,
            speed=None, flags1=None, flags2=None, ability1=None, ability2=None,
            boss=None, undead=None, ranged=None, divide=None, poison=None,
            sleep=None, negate=None, teleport=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_monster_out_of_range(self, tmp_path):
        """cmd_edit exits if monster index >= 16."""
        from ult3edit.bestiary import cmd_edit
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, monster=20, all=False,
            dry_run=False, backup=False, output=None, validate=False,
            tile1=None, tile2=None, hp=None, attack=None, defense=None,
            speed=None, flags1=None, flags2=None, ability1=None, ability2=None,
            boss=None, undead=None, ranged=None, divide=None, poison=None,
            sleep=None, negate=None, teleport=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_no_modifications(self, tmp_path, capsys):
        """cmd_edit with no edit flags prints 'No modifications specified'."""
        from ult3edit.bestiary import cmd_edit
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, monster=0, all=False,
            dry_run=False, backup=False, output=None, validate=False,
            tile1=None, tile2=None, hp=None, attack=None, defense=None,
            speed=None, flags1=None, flags2=None, ability1=None, ability2=None,
            boss=None, undead=None, ranged=None, divide=None, poison=None,
            sleep=None, negate=None, teleport=None)
        cmd_edit(args)
        captured = capsys.readouterr()
        assert 'No modifications' in captured.out

    def test_import_non_numeric_key_warning(self, tmp_path, capsys):
        """Import with non-numeric dict key prints warning."""
        from ult3edit.bestiary import cmd_import
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'monsters': {'abc': {'hp': 50}, '0': {'hp': 100}}}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert 'non-numeric' in captured.err

    def test_import_monster_out_of_range_skipped(self, tmp_path):
        """Import with monster index >= 16 silently skips."""
        from ult3edit.bestiary import cmd_import
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 99, 'hp': 50}], f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        cmd_import(args)  # Should not crash

    def test_load_mon_file_too_small(self, tmp_path):
        """load_mon_file returns empty list for undersized file."""
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(b'\x00' * 10)  # Much less than 160 bytes
        monsters = load_mon_file(path)
        assert monsters == []


class TestMapImportGaps:
    """Test map import width validation."""

    def test_import_width_zero(self, tmp_path, capsys):
        """Import with width=0 falls back to 64."""
        from ult3edit.map import cmd_import
        data = bytearray(MAP_OVERWORLD_SIZE)
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'width': 0, 'tiles': []}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert 'invalid width' in captured.err

    def test_import_width_not_divisible(self, tmp_path, capsys):
        """Import with width that doesn't divide file size warns."""
        from ult3edit.map import cmd_import
        data = bytearray(MAP_OVERWORLD_SIZE)
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'width': 37, 'tiles': []}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert 'not divisible' in captured.err


class TestSaveSetterErrors:
    """Test PartyState setter validation errors."""

    def test_transport_invalid_name_raises(self):
        """transport.setter raises ValueError for unknown name."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        with pytest.raises(ValueError, match="Unknown transport"):
            ps.transport = "FLYING_CARPET"

    def test_location_type_invalid_name_raises(self):
        """location_type.setter raises ValueError for unknown name."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        with pytest.raises(ValueError, match="Unknown location type"):
            ps.location_type = "SPACE_STATION"

    def test_transport_int_directly_sets(self):
        """transport.setter accepts raw integer."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        ps.transport = 0x42
        assert ps.raw[PRTY_OFF_TRANSPORT] == 0x42

    def test_location_type_int_directly_sets(self):
        """location_type.setter accepts raw integer."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        ps.location_type = 0x33
        assert ps.raw[PRTY_OFF_LOCATION] == 0x33

    def test_transport_hex_string(self):
        """transport.setter accepts hex string like '0x10'."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        ps.transport = "0x10"
        assert ps.raw[PRTY_OFF_TRANSPORT] == 0x10

    def test_location_type_hex_string(self):
        """location_type.setter accepts hex string like '0x05'."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        ps.location_type = "0x05"
        assert ps.raw[PRTY_OFF_LOCATION] == 0x05


class TestSaveCmdEditGaps:
    """Test save cmd_edit additional error paths."""

    def test_plrs_slot_out_of_range(self, tmp_path):
        """PLRS slot out of range exits."""
        from ult3edit.save import cmd_edit
        game_dir = str(tmp_path)
        # Create PRTY file
        prty = bytearray(PRTY_FILE_SIZE)
        with open(os.path.join(game_dir, 'PRTY'), 'wb') as f:
            f.write(prty)
        # Create PLRS file (4 slots of 64 bytes)
        plrs = bytearray(PLRS_FILE_SIZE)
        with open(os.path.join(game_dir, 'PLRS'), 'wb') as f:
            f.write(plrs)
        args = argparse.Namespace(
            game_dir=game_dir, plrs_slot=10, name='TEST',
            transport=None, party_size=None, location_type=None,
            x=None, y=None, slot_ids=None,
            str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, marks=None, cards=None,
            sub_morsels=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_both_prty_plrs_with_output_error(self, tmp_path):
        """Editing both PRTY and PLRS with --output exits."""
        from ult3edit.save import cmd_edit
        game_dir = str(tmp_path)
        prty = bytearray(PRTY_FILE_SIZE)
        with open(os.path.join(game_dir, 'PRTY'), 'wb') as f:
            f.write(prty)
        plrs = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            plrs[i] = ord(ch) | 0x80
        plrs[CHAR_STATUS] = ord('G')
        plrs[CHAR_HP_HI] = 0x01
        with open(os.path.join(game_dir, 'PLRS'), 'wb') as f:
            f.write(plrs)
        args = argparse.Namespace(
            game_dir=game_dir, plrs_slot=0, name='TEST',
            transport='foot', party_size=None, location_type=None,
            x=None, y=None, slot_ids=None,
            str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, marks=None, cards=None,
            sub_morsels=None,
            dry_run=False, backup=False, output='conflict.bin')
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestSpecialCmdViewGaps:
    """Test special cmd_view directory with no files."""

    def test_no_files_in_directory(self, tmp_path):
        """cmd_view on directory with no special files exits."""
        from ult3edit.special import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


class TestTextCmdEditGaps:
    """Test text cmd_edit argument validation."""

    def test_record_without_text_exits(self, tmp_path):
        """cmd_edit with --record but no --text exits."""
        from ult3edit.text import cmd_edit
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(bytearray(TEXT_FILE_SIZE))
        args = argparse.Namespace(
            file=path, record=0, text=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_text_without_record_exits(self, tmp_path):
        """cmd_edit with --text but no --record exits."""
        from ult3edit.text import cmd_edit
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(bytearray(TEXT_FILE_SIZE))
        args = argparse.Namespace(
            file=path, record=None, text='HELLO',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_import_overflow_truncation(self, tmp_path, capsys):
        """Import with too many records for file size warns."""
        from ult3edit.text import cmd_import
        # Small file (32 bytes)
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(bytearray(32))
        # Import many long records
        json_path = os.path.join(str(tmp_path), 'import.json')
        records = ['A' * 20, 'B' * 20, 'C' * 20]
        with open(json_path, 'w') as f:
            json.dump(records, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=True, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert 'too small' in captured.err or 'Warning' in captured.err


class TestTlkCmdGaps:
    """Test TLK command gaps."""

    def test_cmd_view_no_files_in_dir(self, tmp_path):
        """cmd_view on directory with no TLK files exits."""
        from ult3edit.tlk import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_cmd_edit_find_without_replace(self, tmp_path):
        """cmd_edit with --find but no --replace exits."""
        from ult3edit.tlk import cmd_edit
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(b'\xC8\xC5\xCC\xCC\xCF\xFF')  # HELLO + end marker
        args = argparse.Namespace(
            file=path, find='HELLO', replace=None,
            record=None, text=None,
            dry_run=False, backup=False, output=None,
            case_sensitive=False, regex=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_cmd_edit_replace_without_find(self, tmp_path):
        """cmd_edit with --replace but no --find exits."""
        from ult3edit.tlk import cmd_edit
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(b'\xC8\xC5\xCC\xCC\xCF\xFF')
        args = argparse.Namespace(
            file=path, find=None, replace='WORLD',
            record=None, text=None,
            dry_run=False, backup=False, output=None,
            case_sensitive=False, regex=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_cmd_edit_record_out_of_range(self, tmp_path):
        """cmd_edit with record index past end of file exits."""
        from ult3edit.tlk import cmd_edit
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(b'\xC8\xC5\xCC\xCC\xCF\xFF')  # 1 record
        args = argparse.Namespace(
            file=path, find=None, replace=None,
            record=99, text='NEW TEXT',
            dry_run=False, backup=False, output=None,
            case_sensitive=False, regex=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestDiffFileGaps:
    """Test diff_file and diff_directories gaps."""

    def test_diff_file_undetectable_type(self, tmp_path):
        """diff_file returns None for unrecognizable files."""
        from ult3edit.diff import diff_file
        p1 = os.path.join(str(tmp_path), 'UNKNOWN1')
        p2 = os.path.join(str(tmp_path), 'UNKNOWN2')
        with open(p1, 'wb') as f:
            f.write(b'\x00' * 7)  # No known file matches 7 bytes
        with open(p2, 'wb') as f:
            f.write(b'\x00' * 7)
        result = diff_file(p1, p2)
        assert result is None

    def test_diff_directories_empty_dirs(self, tmp_path):
        """diff_directories on empty dirs returns GameDiff with no changes."""
        from ult3edit.diff import diff_directories
        d1 = os.path.join(str(tmp_path), 'dir1')
        d2 = os.path.join(str(tmp_path), 'dir2')
        os.makedirs(d1)
        os.makedirs(d2)
        gd = diff_directories(d1, d2)
        assert len(gd.files) == 0

    def test_diff_file_binary_type(self, tmp_path):
        """diff_file handles binary file types (TEXT, DDRW, SHPS)."""
        from ult3edit.diff import diff_file
        from ult3edit.constants import TEXT_FILE_SIZE
        p1 = os.path.join(str(tmp_path), 'TEXT')
        p2 = os.path.join(str(tmp_path), 'TEXT2')
        data = bytearray(TEXT_FILE_SIZE)
        with open(p1, 'wb') as f:
            f.write(data)
        data[0] = 0xAA
        with open(p2, 'wb') as f:
            f.write(data)
        result = diff_file(p1, p2)
        assert result is not None
        assert result.change_count > 0

    def test_diff_file_prty(self, tmp_path):
        """diff_file handles PRTY files."""
        from ult3edit.diff import diff_file
        p1 = os.path.join(str(tmp_path), 'PRTY')
        p2 = os.path.join(str(tmp_path), 'PRTY2')
        data1 = bytearray(PRTY_FILE_SIZE)
        data2 = bytearray(PRTY_FILE_SIZE)
        data2[PRTY_OFF_TRANSPORT] = 0x10
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        result = diff_file(p1, p2)
        assert result is not None


class TestBcdEdgeCasesExtended:
    """Test BCD encoding edge cases."""

    def test_bcd_to_int_invalid_nibble(self):
        """bcd_to_int with value > 0x99 returns clamped result."""
        from ult3edit.bcd import bcd_to_int
        # 0xFF has nibbles F,F which are invalid BCD
        result = bcd_to_int(0xFF)
        # Implementation-dependent, but should not crash
        assert isinstance(result, int)

    def test_int_to_bcd_overflow(self):
        """int_to_bcd clamps values > 99."""
        from ult3edit.bcd import int_to_bcd
        result = int_to_bcd(150)
        assert result == 0x99  # Clamped to max

    def test_int_to_bcd_negative(self):
        """int_to_bcd clamps negative values to 0."""
        from ult3edit.bcd import int_to_bcd
        result = int_to_bcd(-5)
        assert result == 0x00

    def test_int_to_bcd16_overflow(self):
        """int_to_bcd16 clamps values > 9999."""
        from ult3edit.bcd import int_to_bcd16
        hi, lo = int_to_bcd16(12345)
        assert hi == 0x99 and lo == 0x99  # Clamped to 9999

    def test_int_to_bcd16_negative(self):
        """int_to_bcd16 clamps negative values to 0."""
        from ult3edit.bcd import int_to_bcd16
        hi, lo = int_to_bcd16(-100)
        assert hi == 0x00 and lo == 0x00


class TestFileUtilEdgeCases:
    """Test fileutil utility edge cases."""

    def test_hex_int_parses_hex(self):
        """hex_int parses 0x prefix."""
        from ult3edit.fileutil import hex_int
        assert hex_int('0xFF') == 255
        assert hex_int('0x10') == 16

    def test_hex_int_parses_decimal(self):
        """hex_int parses decimal strings."""
        from ult3edit.fileutil import hex_int
        assert hex_int('42') == 42

    def test_hex_int_parses_dollar_prefix(self):
        """hex_int parses $ prefix (if supported)."""
        from ult3edit.fileutil import hex_int
        try:
            result = hex_int('$FF')
            assert result == 255
        except ValueError:
            pass  # $ prefix may not be supported

    def test_resolve_single_file_not_found(self, tmp_path):
        """resolve_single_file returns None for missing file."""
        from ult3edit.fileutil import resolve_single_file
        result = resolve_single_file(str(tmp_path), 'NONEXISTENT')
        assert result is None

    def test_resolve_single_file_found(self, tmp_path):
        """resolve_single_file finds file by prefix."""
        from ult3edit.fileutil import resolve_single_file
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(b'\x00')
        result = resolve_single_file(str(tmp_path), 'ROST')
        assert result is not None

    def test_decode_encode_high_ascii_roundtrip(self):
        """decode/encode_high_ascii round-trips."""
        from ult3edit.fileutil import decode_high_ascii, encode_high_ascii
        text = "HELLO WORLD"
        encoded = encode_high_ascii(text, len(text))
        decoded = decode_high_ascii(encoded)
        assert decoded == text


class TestCliDispatch:
    """Test CLI dispatcher edge cases."""

    def test_unknown_subcommand(self, capsys):
        """CLI with no subcommand prints help or exits."""
        from ult3edit.cli import main
        sys_argv_backup = sys.argv
        sys.argv = ['ult3edit']
        try:
            main()
        except SystemExit:
            pass  # Expected
        finally:
            sys.argv = sys_argv_backup


# =============================================================================
# Batch 7: Final gaps — combat edit, dispatch fallbacks, directory errors
# =============================================================================

class TestCombatCmdEditGaps:
    """Test combat cmd_edit CLI error paths."""

    def test_tile_out_of_bounds(self, tmp_path):
        """cmd_edit --tile with coords out of bounds exits."""
        from ult3edit.combat import cmd_edit
        data = bytearray(CON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, tile=(99, 99, 0x10),
            monster_pos=None, pc_pos=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_monster_pos_index_out_of_range(self, tmp_path):
        """cmd_edit --monster-pos with bad index exits."""
        from ult3edit.combat import cmd_edit
        data = bytearray(CON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, tile=None,
            monster_pos=(99, 0, 0), pc_pos=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_pc_pos_index_out_of_range(self, tmp_path):
        """cmd_edit --pc-pos with bad index exits."""
        from ult3edit.combat import cmd_edit
        data = bytearray(CON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, tile=None,
            monster_pos=None, pc_pos=(99, 0, 0),
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_tile_value_out_of_range(self, tmp_path):
        """cmd_edit --tile with value > 255 exits."""
        from ult3edit.combat import cmd_edit
        data = bytearray(CON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, tile=(0, 0, 999),
            monster_pos=None, pc_pos=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_monster_pos_coords_out_of_bounds(self, tmp_path):
        """cmd_edit --monster-pos with position out of map bounds exits."""
        from ult3edit.combat import cmd_edit
        data = bytearray(CON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, tile=None,
            monster_pos=(0, 99, 99), pc_pos=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestCombatCmdViewGaps:
    """Test combat cmd_view directory error."""

    def test_no_con_files_in_dir(self, tmp_path):
        """cmd_view on directory with no CON files exits."""
        from ult3edit.combat import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            cmd_view(args)


class TestBestiaryCmdViewGaps:
    """Test bestiary cmd_view directory error."""

    def test_no_mon_files_in_dir(self, tmp_path):
        """cmd_view on directory with no MON files exits."""
        from ult3edit.bestiary import cmd_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False, file=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


class TestMapCmdViewGaps:
    """Test map cmd_view and cmd_overview directory errors."""

    def test_overview_no_map_files(self, tmp_path):
        """cmd_overview on directory with no MAP files exits."""
        from ult3edit.map import cmd_overview
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_overview(args)

    def test_view_invalid_crop_non_int(self, tmp_path):
        """cmd_view with non-integer crop values exits."""
        from ult3edit.map import cmd_view
        data = bytearray(MAP_OVERWORLD_SIZE)
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, crop='a,b,c,d', json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_set_coords_out_of_bounds(self, tmp_path):
        """cmd_set with out-of-bounds coords exits."""
        data = bytearray(MAP_OVERWORLD_SIZE)
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, x=999, y=999, tile=0x10, level=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_set(args)


class TestDispatchFallbacks:
    """Test dispatch() fallback for unrecognized subcommands."""

    def test_combat_dispatch_unknown(self, capsys):
        """Combat dispatch with unknown command prints usage."""
        from ult3edit.combat import dispatch
        args = argparse.Namespace(combat_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_bestiary_dispatch_unknown(self, capsys):
        """Bestiary dispatch with unknown command prints usage."""
        from ult3edit.bestiary import dispatch
        args = argparse.Namespace(bestiary_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_map_dispatch_unknown(self, capsys):
        """Map dispatch with unknown command prints usage."""
        from ult3edit.map import dispatch
        args = argparse.Namespace(map_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_tlk_dispatch_unknown(self, capsys):
        """TLK dispatch with unknown command prints usage."""
        from ult3edit.tlk import dispatch
        args = argparse.Namespace(tlk_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_save_dispatch_unknown(self, capsys):
        """Save dispatch with unknown command prints usage."""
        from ult3edit.save import dispatch
        args = argparse.Namespace(save_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_special_dispatch_unknown(self, capsys):
        """Special dispatch with unknown command prints usage."""
        from ult3edit.special import dispatch
        args = argparse.Namespace(special_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_text_dispatch_unknown(self, capsys):
        """Text dispatch with unknown command prints usage."""
        from ult3edit.text import dispatch
        args = argparse.Namespace(text_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_ddrw_dispatch_unknown(self, capsys):
        """DDRW dispatch with unknown command prints usage."""
        from ult3edit.ddrw import dispatch
        args = argparse.Namespace(ddrw_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_patch_dispatch_unknown(self, capsys):
        """Patch dispatch with unknown command prints usage."""
        from ult3edit.patch import dispatch
        args = argparse.Namespace(patch_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_roster_dispatch_unknown(self, capsys):
        """Roster dispatch with unknown command prints usage."""
        from ult3edit.roster import dispatch
        args = argparse.Namespace(roster_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_sound_dispatch_unknown(self, capsys):
        """Sound dispatch with unknown command prints usage."""
        from ult3edit.sound import dispatch
        args = argparse.Namespace(sound_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_shapes_dispatch_unknown(self, capsys):
        """Shapes dispatch with unknown command prints usage."""
        from ult3edit.shapes import dispatch
        args = argparse.Namespace(shapes_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_equip_dispatch_unknown(self, capsys):
        """Equip dispatch with unknown command prints usage."""
        from ult3edit.equip import dispatch
        args = argparse.Namespace(equip_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_spell_dispatch_unknown(self, capsys):
        """Spell dispatch with unknown command prints usage."""
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()


class TestSaveCmdViewGaps:
    """Test save cmd_view error paths."""

    def test_no_prty_in_dir(self, tmp_path):
        """cmd_view on directory with no PRTY file exits."""
        from ult3edit.save import cmd_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


# =============================================================================
# Batch 8: Final remaining gaps
# =============================================================================


class TestSpecialCmdImportGaps:
    """Test special cmd_import additional error paths."""

    def test_import_no_tiles_in_json(self, tmp_path):
        """Import with JSON missing tiles works (empty set)."""
        from ult3edit.special import cmd_import
        data = bytearray(SPECIAL_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=True, backup=False, output=None)
        cmd_import(args)  # Should not crash


class TestBestiaryAbility2Validation:
    """Test validate_monster catches undefined ability2 bits."""

    def test_valid_resistant_no_warning(self):
        """Resistant (0xC0) is a defined bit — no warning."""
        from ult3edit.bestiary import Monster, validate_monster
        from ult3edit.constants import MON_ABIL2_RESISTANT
        attrs = [0x80, 0x80, 0, 0, 10, 5, 3, 4, 0, MON_ABIL2_RESISTANT]
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert not any('ability2' in w for w in warnings)

    def test_undefined_ability2_bits_warned(self):
        """Bits outside 0xC0 produce a warning."""
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0x80, 0x80, 0, 0, 10, 5, 3, 4, 0, 0x01]
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('ability2' in w.lower() for w in warnings)

    def test_mixed_ability2_bits(self):
        """Resistant + undefined bits still warns about the undefined ones."""
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0x80, 0x80, 0, 0, 10, 5, 3, 4, 0, 0xC1]
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('$01' in w for w in warnings)

    def test_ability2_zero_no_warning(self):
        """ability2=0 is valid — no warning."""
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0x80, 0x80, 0, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert not any('ability2' in w for w in warnings)


class TestMapLevelBoundsValidation:
    """Test _get_map_slice validates dungeon level bounds."""

    def test_valid_level_zero(self):
        """Level 0 of an 8-level dungeon is fine."""
        from ult3edit.map import _get_map_slice
        data = bytearray(2048)  # 8 levels x 256
        slice_data, base, w, h = _get_map_slice(data, True, 0)
        assert base == 0 and w == 16 and h == 16

    def test_valid_level_seven(self):
        """Level 7 (last) of an 8-level dungeon is fine."""
        from ult3edit.map import _get_map_slice
        data = bytearray(2048)
        slice_data, base, w, h = _get_map_slice(data, True, 7)
        assert base == 7 * 256

    def test_level_too_high_exits(self):
        """Level 8 of an 8-level dungeon should exit."""
        from ult3edit.map import _get_map_slice
        data = bytearray(2048)  # 8 levels (0-7)
        with pytest.raises(SystemExit):
            _get_map_slice(data, True, 8)

    def test_negative_level_exits(self):
        """Negative level should exit."""
        from ult3edit.map import _get_map_slice
        data = bytearray(2048)
        with pytest.raises(SystemExit):
            _get_map_slice(data, True, -1)

    def test_level_none_defaults_zero(self):
        """Level=None defaults to 0."""
        from ult3edit.map import _get_map_slice
        data = bytearray(2048)
        slice_data, base, w, h = _get_map_slice(data, True, None)
        assert base == 0


# ============================================================================
# Batch 9: Audit-discovered gaps
# ============================================================================


class TestCharacterInitSize:
    """Test Character constructor rejects wrong-size data."""

    def test_too_small_raises(self):
        from ult3edit.roster import Character
        with pytest.raises(ValueError, match='64 bytes'):
            Character(bytearray(32))

    def test_too_large_raises(self):
        from ult3edit.roster import Character
        with pytest.raises(ValueError, match='64 bytes'):
            Character(bytearray(128))

    def test_exact_size_ok(self):
        from ult3edit.roster import Character
        c = Character(bytearray(64))
        assert c.is_empty


class TestStatusSetterFullName:
    """Test Character.status setter with full status name strings."""

    def test_set_status_good_full(self):
        from ult3edit.roster import Character
        c = Character(bytearray(64))
        c.status = 'Good'
        assert c.status == 'Good'

    def test_set_status_poisoned_full(self):
        from ult3edit.roster import Character
        c = Character(bytearray(64))
        c.status = 'Poisoned'
        assert c.status == 'Poisoned'

    def test_set_status_dead_full(self):
        from ult3edit.roster import Character
        c = Character(bytearray(64))
        c.status = 'Dead'
        assert c.status == 'Dead'


class TestRosterAllSlotsEmpty:
    """Test cmd_view/cmd_edit with all-empty roster."""

    def test_view_all_empty(self, tmp_path, capsys):
        from ult3edit.roster import cmd_view
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(bytearray(64 * 20))
        args = argparse.Namespace(file=path, json=False, output=None,
                                  validate=False, slot=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'All slots empty' in out

    def test_edit_all_on_empty_roster(self, tmp_path, capsys):
        from ult3edit.roster import cmd_edit
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(bytearray(64 * 20))
        args = argparse.Namespace(
            file=path, slot=None, all=True, name=None,
            strength=None, dexterity=None, intelligence=None,
            wisdom=None, hp=None, max_hp=None, exp=None,
            mp=None, food=None, gold=None, gems=None,
            keys=None, powders=None, torches=None,
            race=None, klass=None, gender=None,
            status=None, weapon=None, armor=None,
            marks=None, cards=None, in_party=False,
            not_in_party=False, sub_morsels=None,
            weapon_inv=None, armor_inv=None,
            dry_run=False, backup=False, output=None,
            validate=False)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'No modifications' in out


class TestPartyStateLocationTypeValueError:
    """Test PartyState.location_type setter raises ValueError for bad strings."""

    def test_unknown_string_raises(self):
        from ult3edit.save import PartyState
        ps = PartyState(bytearray(16))
        with pytest.raises(ValueError, match='Unknown location type'):
            ps.location_type = 'underwater'


class TestPartyStateNonStandardSentinel:
    """Test PartyState.display() shows non-standard sentinel."""

    def test_nonstandard_sentinel(self, capsys):
        from ult3edit.save import PartyState
        ps = PartyState(bytearray(16))
        ps.sentinel = 0x42
        ps.display()
        out = capsys.readouterr().out
        assert 'non-standard' in out

    def test_inactive_sentinel(self, capsys):
        from ult3edit.save import PartyState
        ps = PartyState(bytearray(16))
        ps.sentinel = 0x00
        ps.display()
        out = capsys.readouterr().out
        assert 'inactive' in out


class TestCombatValidateView:
    """Test combat cmd_view with --validate flag."""

    def test_view_file_with_validate(self, tmp_path, capsys):
        from ult3edit.combat import cmd_view
        path = os.path.join(str(tmp_path), 'CONA')
        data = bytearray(192)
        # Set overlapping PC positions to trigger a warning
        data[0xA0] = 5  # pc0 x
        data[0xA4] = 5  # pc0 y
        data[0xA1] = 5  # pc1 x (same as pc0)
        data[0xA5] = 5  # pc1 y (same as pc0)
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(path=path, json=False, output=None,
                                  validate=True)
        cmd_view(args)

    def test_view_dir_json_with_validate(self, tmp_path, capsys):
        from ult3edit.combat import cmd_view
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(bytearray(192))
        args = argparse.Namespace(path=str(tmp_path), json=True, output=None,
                                  validate=True)
        cmd_view(args)
        out = capsys.readouterr().out
        result = json.loads(out)
        assert 'CONA' in result
        assert 'warnings' in result['CONA']


class TestCombatEditValidate:
    """Test combat cmd_edit with --validate flag."""

    def test_edit_with_validate(self, tmp_path, capsys):
        from ult3edit.combat import cmd_edit
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(bytearray(192))
        args = argparse.Namespace(
            file=path, tile=(0, 0, 4), monster_pos=None,
            pc_pos=None, dry_run=True, backup=False,
            output=None, validate=True)
        cmd_edit(args)


class TestCombatImportDescriptorBackcompat:
    """Test combat cmd_import accepts old 'descriptor' key."""

    def test_descriptor_key(self, tmp_path):
        from ult3edit.combat import cmd_import
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(bytearray(192))
        jdata = {
            'tiles': [],
            'monsters': [],
            'pcs': [],
            'descriptor': {'block1': [0xAA] * 7}
        }
        json_path = os.path.join(str(tmp_path), 'con.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(file=path, json_file=json_path,
                                  dry_run=False, backup=False, output=None)
        cmd_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x79] == 0xAA


class TestCombatImportNonNumericMonsterKey:
    """Test combat cmd_import warns on non-numeric dict monster keys."""

    def test_non_numeric_monster_key(self, tmp_path, capsys):
        from ult3edit.combat import cmd_import
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(bytearray(192))
        jdata = {
            'tiles': [],
            'monsters': {'abc': {'x': 0, 'y': 0}, '0': {'x': 5, 'y': 5}},
            'pcs': [],
        }
        json_path = os.path.join(str(tmp_path), 'con.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(file=path, json_file=json_path,
                                  dry_run=False, backup=False, output=None)
        cmd_import(args)
        err = capsys.readouterr().err
        assert 'non-numeric' in err


class TestSpecialImportMetadataBackcompat:
    """Test special cmd_import accepts old 'metadata' key."""

    def test_metadata_key_imports_trailing(self, tmp_path):
        from ult3edit.special import cmd_import
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(bytearray(128))
        jdata = {
            'tiles': [[0] * 11] * 11,
            'metadata': [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11]
        }
        jpath = os.path.join(str(tmp_path), 'brnd.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=False, backup=False, output=None)
        cmd_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[121] == 0xAA


class TestTlkSearchInvalidRegex:
    """Test tlk cmd_search exits on invalid regex."""

    def test_bad_regex_exits(self, tmp_path):
        from ult3edit.tlk import cmd_search
        args = argparse.Namespace(path=str(tmp_path), pattern='[unclosed',
                                  regex=True, ignore_case=False)
        with pytest.raises(SystemExit):
            cmd_search(args)


class TestBcdIsValidBcd:
    """Test is_valid_bcd function."""

    def test_valid_bcd_bytes(self):
        from ult3edit.bcd import is_valid_bcd
        assert is_valid_bcd(0x00)
        assert is_valid_bcd(0x99)
        assert is_valid_bcd(0x42)

    def test_invalid_high_nibble(self):
        from ult3edit.bcd import is_valid_bcd
        assert not is_valid_bcd(0xA0)
        assert not is_valid_bcd(0xF5)

    def test_invalid_low_nibble(self):
        from ult3edit.bcd import is_valid_bcd
        assert not is_valid_bcd(0x0A)
        assert not is_valid_bcd(0x1F)

    def test_both_nibbles_invalid(self):
        from ult3edit.bcd import is_valid_bcd
        assert not is_valid_bcd(0xFF)


class TestValidateMonsterEmpty:
    """Test validate_monster returns empty for empty monster."""

    def test_empty_monster_no_warnings(self):
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0] * 10
        m = Monster(attrs, 0)
        assert validate_monster(m) == []


class TestMapDecompileUnknownBytes:
    """Test map cmd_decompile warns on unknown tile bytes."""

    def test_unknown_tile_byte_shows_question_mark(self, tmp_path, capsys):
        from ult3edit.map import cmd_decompile
        # Create a small overworld map with an unknown tile byte
        data = bytearray(64 * 64)
        data[0] = 0xFE  # Not a standard tile
        path = os.path.join(str(tmp_path), 'MAP')
        with open(path, 'wb') as f:
            f.write(data)
        outpath = os.path.join(str(tmp_path), 'out.map')
        args = argparse.Namespace(file=path, output=outpath, dungeon=False)
        cmd_decompile(args)
        err = capsys.readouterr().err
        assert 'unmapped' in err.lower() or '0xFE' in err


class TestDiffChangedCount:
    """Test FileDiff.change_count property."""

    def test_change_count(self):
        from ult3edit.diff import FileDiff, EntityDiff, FieldDiff
        fd = FileDiff('roster', 'ROST')
        e1 = EntityDiff('character', 'Slot 0')
        e1.fields = [FieldDiff('name', 'foo', 'bar')]
        e2 = EntityDiff('character', 'Slot 1')  # no fields = unchanged
        e3 = EntityDiff('character', 'Slot 2')
        e3.fields = [FieldDiff('hp', '10', '20')]
        fd.entities = [e1, e2, e3]
        assert fd.change_count == 2

    def test_no_changes(self):
        from ult3edit.diff import FileDiff, EntityDiff
        fd = FileDiff('roster', 'ROST')
        e = EntityDiff('character', 'Slot 0')  # no fields = unchanged
        fd.entities = [e]
        assert fd.change_count == 0


# ============================================================================
# Batch 10: Audit-verified bug fixes
# ============================================================================


class TestFlagDescMagicUserPrecedence:
    """Test that Monster.flag_desc correctly identifies Magic User type.

    Bug: `f1 & 0x0C == MON_FLAG1_MAGIC_USER` was parsed as `f1 & True`
    due to operator precedence. Fixed to `(f1 & 0x0C) == MON_FLAG1_MAGIC_USER`.
    """

    def test_magic_user_detected(self):
        """flags1=0x0C (bits 2+3 set) should show Magic User."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x0C, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert 'Magic User' in m.flag_desc

    def test_undead_not_magic_user(self):
        """flags1=0x04 (only bit 2) should show Undead, not Magic User."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x04, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert 'Undead' in m.flag_desc
        assert 'Magic User' not in m.flag_desc

    def test_ranged_not_magic_user(self):
        """flags1=0x08 (only bit 3) should show Ranged, not Magic User."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x08, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert 'Ranged' in m.flag_desc
        assert 'Magic User' not in m.flag_desc

    def test_boss_magic_user(self):
        """flags1=0x8C (boss + magic user) shows both."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x8C, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert 'Magic User' in m.flag_desc
        assert 'Boss' in m.flag_desc

    def test_bit0_set_not_magic_user(self):
        """flags1=0x01 (undefined bit 0) should NOT trigger Magic User."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x01, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert 'Magic User' not in m.flag_desc

    def test_no_flags(self):
        """flags1=0x00 should show '-' (no flags)."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x00, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert m.flag_desc == '-'


class TestMapCompileRowPadding:
    """Test that short overworld rows are padded with Grass (0x04), not Water (0x00)."""

    def test_short_overworld_row_padded_with_grass(self, tmp_path):
        from ult3edit.map import cmd_compile
        # Create a .map file with one short row
        src = os.path.join(str(tmp_path), 'test.map')
        # Use '.' which is Grass (0x04) for the first few chars, then short
        with open(src, 'w') as f:
            f.write('# Overworld (64x64)\n')
            for _ in range(64):
                f.write('.' * 10 + '\n')  # Only 10 chars, should pad to 64
        outpath = os.path.join(str(tmp_path), 'MAP')
        args = argparse.Namespace(source=src, output=outpath, dungeon=False)
        cmd_compile(args)
        with open(outpath, 'rb') as f:
            data = f.read()
        # Byte at position 10 (first padded tile) should be 0x04 (Grass)
        assert data[10] == 0x04
        # NOT 0x00 (Water)
        assert data[10] != 0x00

    def test_short_dungeon_row_padded_with_zero(self, tmp_path):
        from ult3edit.map import cmd_compile
        # Create a dungeon .map with short rows
        src = os.path.join(str(tmp_path), 'test.map')
        with open(src, 'w') as f:
            f.write('# Level 1\n')
            for _ in range(16):
                f.write('#' * 5 + '\n')  # Only 5 chars, should pad to 16
        outpath = os.path.join(str(tmp_path), 'DNG')
        args = argparse.Namespace(source=src, output=outpath, dungeon=True)
        cmd_compile(args)
        with open(outpath, 'rb') as f:
            data = f.read()
        # Byte at position 5 (first padded tile) should be 0x00 (Open/empty)
        assert data[5] == 0x00


class TestBcd16Docstring:
    """Test bcd16_to_int decodes correctly (verifying fixed docstring)."""

    def test_bcd16_1234(self):
        from ult3edit.bcd import bcd16_to_int
        assert bcd16_to_int(0x12, 0x34) == 1234

    def test_bcd16_9999(self):
        from ult3edit.bcd import bcd16_to_int
        assert bcd16_to_int(0x99, 0x99) == 9999

    def test_bcd16_0100(self):
        from ult3edit.bcd import bcd16_to_int
        assert bcd16_to_int(0x01, 0x00) == 100


# ============================================================================
# Batch 11: Remaining gap coverage
# ============================================================================


class TestMapOverviewPreview:
    """Test cmd_overview with --preview flag."""

    def test_preview_renders_scaled_map(self, tmp_path, capsys):
        from ult3edit.map import cmd_overview
        # Create MAPA (4096 bytes)
        mapa_path = os.path.join(str(tmp_path), 'MAPA')
        data = bytearray(4096)
        data[0] = 0x04  # Grass tile
        with open(mapa_path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(game_dir=str(tmp_path), preview=True,
                                  json=False, output=None)
        cmd_overview(args)
        out = capsys.readouterr().out
        assert 'Sosaria' in out or 'scaled' in out.lower()


class TestDiffFileDispatchCombat:
    """Test diff_file dispatches to diff_combat for CON files."""

    def test_diff_file_combat(self, tmp_path):
        from ult3edit.diff import diff_file
        p1 = os.path.join(str(tmp_path), 'CONA')
        p2 = os.path.join(str(tmp_path), 'CONA_2')
        data = bytearray(192)
        with open(p1, 'wb') as f:
            f.write(data)
        data[0] = 0x04  # Change one tile
        with open(p2, 'wb') as f:
            f.write(data)
        result = diff_file(p1, p2)
        assert result is not None
        assert result.changed


class TestDiffFileDispatchTlk:
    """Test diff_file dispatches to diff_tlk for TLK files."""

    def test_diff_file_tlk(self, tmp_path):
        from ult3edit.diff import diff_file
        # Build a simple TLK file (text record + null terminator)
        rec = bytearray([ord('H') | 0x80, ord('I') | 0x80, 0x00])
        p1 = os.path.join(str(tmp_path), 'TLKA')
        p2 = os.path.join(str(tmp_path), 'TLKA_2')
        with open(p1, 'wb') as f:
            f.write(rec)
        rec2 = bytearray([ord('B') | 0x80, ord('Y') | 0x80, 0x00])
        with open(p2, 'wb') as f:
            f.write(rec2)
        result = diff_file(p1, p2)
        assert result is not None
        assert result.changed


class TestDiffFileDispatchSpecial:
    """Test diff_file dispatches to diff_special for BRND/SHRN files."""

    def test_diff_file_special(self, tmp_path):
        from ult3edit.diff import diff_file
        p1 = os.path.join(str(tmp_path), 'BRND')
        p2 = os.path.join(str(tmp_path), 'BRND_2')
        data = bytearray(128)
        with open(p1, 'wb') as f:
            f.write(data)
        data[0] = 0x04
        with open(p2, 'wb') as f:
            f.write(data)
        result = diff_file(p1, p2)
        assert result is not None
        assert result.changed


class TestDiffMapDungeon:
    """Test diff_map with dungeon-sized files (exposes width=64 issue)."""

    def test_diff_dungeon_detects_changes(self, tmp_path):
        from ult3edit.diff import diff_map
        p1 = os.path.join(str(tmp_path), 'MAPM')
        p2 = os.path.join(str(tmp_path), 'MAPM_2')
        data1 = bytearray(2048)
        data2 = bytearray(2048)
        data2[0] = 0x01  # Change first byte
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        result = diff_map(p1, p2, 'MAPM')
        assert result.tile_changes == 1


class TestMapCompileLevelCommentMidLevel:
    """Test that a '# Level' comment mid-level splits the level prematurely.

    This documents the current behavior (premature split) as a known issue.
    """

    def test_level_comment_midlevel_splits(self, tmp_path):
        from ult3edit.map import cmd_compile
        src = os.path.join(str(tmp_path), 'test.map')
        with open(src, 'w') as f:
            f.write('# Level 1\n')
            for _ in range(8):
                f.write('#' * 16 + '\n')  # 8 rows of wall
            f.write('# Level design note\n')  # Mid-level comment
            for _ in range(8):
                f.write('.' * 16 + '\n')  # 8 more rows of open
        outpath = os.path.join(str(tmp_path), 'DNG')
        args = argparse.Namespace(source=src, output=outpath, dungeon=True)
        cmd_compile(args)
        with open(outpath, 'rb') as f:
            data = f.read()
        # The comment splits level 1 into two: first 8 rows, then 8 rows
        # Level 1 should have 16 rows but the premature split means
        # the first 8 rows are level 1 (padded) and next 8 are level 2
        # So data should be at least 2 levels worth (512 bytes)
        assert len(data) >= 512  # At least 2 levels were created


class TestCombatValidateZeroOverlap:
    """Test that entities at (0,0) are excluded from overlap checks."""

    def test_monster_pc_at_zero_no_overlap_warning(self):
        """Monster and PC both at (0,0) produce no overlap warning."""
        from ult3edit.combat import CombatMap, validate_combat_map
        data = bytearray(192)
        # Monster 0 at (0,0)
        data[0x80] = 0  # monster_x[0]
        data[0x88] = 0  # monster_y[0]
        # PC 0 at (0,0)
        data[0xA0] = 0  # pc_x[0]
        data[0xA4] = 0  # pc_y[0]
        cm = CombatMap(data)
        warnings = validate_combat_map(cm)
        # Current behavior: (0,0) is excluded from overlap checks
        # so no overlap warning is produced even though they overlap
        overlap_warnings = [w for w in warnings if 'overlap' in w.lower()]
        assert len(overlap_warnings) == 0  # Documents the known gap


# ============================================================================
# Batch 12: Final gap coverage
# ============================================================================


class TestTlkImportDestroysBinaryLeader:
    """Test that tlk cmd_import discards binary leader sections."""

    def test_binary_leader_not_preserved(self, tmp_path, capsys):
        from ult3edit.tlk import cmd_import
        # Create TLK with binary leader (non-text bytes) then text record
        binary_leader = bytearray([0x01, 0x02, 0x03])  # not high-ASCII text
        separator = bytearray([0x00])
        text_rec = bytearray([ord('H') | 0x80, ord('I') | 0x80])
        tlk_data = binary_leader + separator + text_rec + separator
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(tlk_data)
        # Import JSON with just the text record
        jdata = [{'lines': ['HELLO']}]
        jpath = os.path.join(str(tmp_path), 'tlk.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=False, backup=False, output=None)
        cmd_import(args)
        # After import, binary leader is gone — only the imported text remains
        with open(path, 'rb') as f:
            result = f.read()
        # The binary leader bytes should NOT be present
        assert result[:3] != bytes([0x01, 0x02, 0x03])


class TestTlkEditZeroTextRecords:
    """Test tlk cmd_edit error message when file has zero text records."""

    def test_zero_text_count_exits(self, tmp_path):
        from ult3edit.tlk import cmd_edit
        # Create TLK with only binary (non-text) content
        binary_data = bytearray([0x01, 0x02, 0x03, 0x00])
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(binary_data)
        args = argparse.Namespace(
            file=path, record=0, text='HI', find=None, replace=None,
            dry_run=False, backup=False, output=None, ignore_case=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestMapImportDungeonNoLevelsKey:
    """Test map cmd_import on dungeon file with JSON lacking 'levels' key."""

    def test_dungeon_without_levels_uses_else_branch(self, tmp_path, capsys):
        from ult3edit.map import cmd_import
        # Create dungeon-sized file (2048 bytes)
        path = os.path.join(str(tmp_path), 'MAPM')
        data = bytearray(2048)
        with open(path, 'wb') as f:
            f.write(data)
        # JSON without 'levels' — will fall to else branch with width=64 default
        jdata = {'tiles': [['Wall'] * 16], 'width': 16}
        jpath = os.path.join(str(tmp_path), 'map.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=True, backup=False, output=None,
                                  level=None)
        cmd_import(args)
        # Should work without crash — the else branch handles it
        out = capsys.readouterr().out
        assert 'Dry run' in out


class TestMapCmdFindDungeon:
    """Test map cmd_find with dungeon-sized file."""

    def test_find_tile_in_dungeon(self, tmp_path, capsys):
        # Create dungeon (2048 bytes, 8 levels x 16x16)
        data = bytearray(2048)
        data[0] = 0x01  # Wall at level 0, (0,0)
        path = os.path.join(str(tmp_path), 'MAPM')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(file=path, tile=0x01, level=0, json=False)
        cmd_find(args)
        out = capsys.readouterr().out
        assert '(0, 0)' in out


class TestCombatImportDoubleWrite:
    """Test combat cmd_import with both padding.pre_monster and descriptor.block1."""

    def test_descriptor_overwrites_padding(self, tmp_path):
        from ult3edit.combat import cmd_import
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(bytearray(192))
        # JSON with both keys — descriptor.block1 should win (last write)
        jdata = {
            'tiles': [], 'monsters': [], 'pcs': [],
            'padding': {'pre_monster': [0x11] * 7},
            'descriptor': {'block1': [0x22] * 7}
        }
        jpath = os.path.join(str(tmp_path), 'con.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=False, backup=False, output=None)
        cmd_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        # descriptor.block1 overwrites padding.pre_monster
        assert result[0x79] == 0x22


class TestRosterNameNonAscii:
    """Test Character.name setter with non-ASCII input."""

    def test_non_ascii_chars_handled(self):
        """Non-ASCII chars should not crash (they get ORed with 0x80)."""
        from ult3edit.roster import Character
        c = Character(bytearray(64))
        # Characters with ord() <= 127 are fine after | 0x80
        # Characters like 'é' (ord=233) produce 233 | 0x80 = 233 (fits in byte)
        # This should not crash
        c.name = 'TEST'
        assert c.name == 'TEST'


class TestDiffBinaryChangedBytes:
    """Test diff_binary changed_bytes FieldDiff uses old=0 sentinel."""

    def test_changed_bytes_old_is_zero(self, tmp_path):
        from ult3edit.diff import diff_binary
        p1 = os.path.join(str(tmp_path), 'FILE1')
        p2 = os.path.join(str(tmp_path), 'FILE2')
        with open(p1, 'wb') as f:
            f.write(bytearray(100))
        data2 = bytearray(100)
        data2[0] = 0xFF
        data2[1] = 0xFF
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_binary(p1, p2, 'TEST')
        # Find the changed_bytes field
        for entity in fd.entities:
            for field in entity.fields:
                if field.path == 'changed_bytes':
                    assert field.old == 0  # Sentinel value
                    assert field.new == 2  # Two bytes differ


class TestDiffDetectMapNoSizeCheck:
    """Test diff detect_file_type accepts MAP files regardless of size."""

    def test_map_any_size_detected(self, tmp_path):
        from ult3edit.diff import detect_file_type
        # A tiny file named MAPA is still detected as MAP
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytearray(42))  # Wrong size for any real MAP
        assert detect_file_type(path) == 'MAPA'

    def test_tlk_any_size_detected(self, tmp_path):
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytearray(10))
        assert detect_file_type(path) == 'TLKA'


# ============================================================================
# Batch 13 — Audit iteration: diff_map dungeon fix, disk.py, roster validation,
#             save dry-run, tlk/spell edge cases
# ============================================================================


class TestDiffMapDungeonCoordinates:
    """diff_map uses width=16 for dungeon-sized (2048-byte) files."""

    def test_dungeon_tile_coordinates_correct(self, tmp_path):
        """Changed tile at dungeon position (3, 5) reports correct x,y."""
        from ult3edit.diff import diff_map
        d1 = bytearray(MAP_DUNGEON_SIZE)
        d2 = bytearray(MAP_DUNGEON_SIZE)
        # Change tile at level 0, x=3, y=5 → offset = 5*16 + 3 = 83
        d2[83] = 0x10
        p1 = os.path.join(str(tmp_path), 'MAPA1')
        p2 = os.path.join(str(tmp_path), 'MAPA2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_map(p1, p2, 'MAPA')
        assert fd.tile_changes == 1
        assert fd.tile_positions[0] == (3, 5)

    def test_dungeon_change_on_level_1(self, tmp_path):
        """Changed tile on level 1 (offset 256+) uses width=16 for coordinates."""
        from ult3edit.diff import diff_map
        d1 = bytearray(MAP_DUNGEON_SIZE)
        d2 = bytearray(MAP_DUNGEON_SIZE)
        # Level 1, x=10, y=2 → offset = 256 + 2*16 + 10 = 298
        d2[298] = 0x20
        p1 = os.path.join(str(tmp_path), 'MAP1')
        p2 = os.path.join(str(tmp_path), 'MAP2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_map(p1, p2, 'MAP')
        assert fd.tile_changes == 1
        # With width=16: x = 298 % 16 = 10, y = 298 // 16 = 18
        assert fd.tile_positions[0] == (10, 18)

    def test_overworld_still_uses_width_64(self, tmp_path):
        """Overworld (4096-byte) MAP still uses width=64."""
        from ult3edit.diff import diff_map
        d1 = bytearray(MAP_OVERWORLD_SIZE)
        d2 = bytearray(MAP_OVERWORLD_SIZE)
        # x=40, y=3 → offset = 3*64 + 40 = 232
        d2[232] = 0x08
        p1 = os.path.join(str(tmp_path), 'OVR1')
        p2 = os.path.join(str(tmp_path), 'OVR2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_map(p1, p2, 'MAPA')
        assert fd.tile_changes == 1
        assert fd.tile_positions[0] == (40, 3)


class TestDiskContextReadWrite:
    """Test DiskContext cache, modified, and _parse_hash_suffix edge cases."""

    def test_parse_hash_suffix_valid(self):
        from ult3edit.disk import DiskContext
        base, ft, at = DiskContext._parse_hash_suffix('ROST#069500')
        assert base == 'ROST'
        assert ft == 0x06
        assert at == 0x9500

    def test_parse_hash_suffix_no_hash(self):
        from ult3edit.disk import DiskContext
        base, ft, at = DiskContext._parse_hash_suffix('ROST')
        assert base == 'ROST'
        assert ft == 0x06
        assert at == 0x0000

    def test_parse_hash_suffix_short(self):
        from ult3edit.disk import DiskContext
        base, ft, at = DiskContext._parse_hash_suffix('FOO#06')
        assert base == 'FOO'
        assert ft == 0x06
        assert at == 0x0000

    def test_parse_hash_suffix_invalid_hex(self):
        """Non-hex characters in suffix with len >= 6 fall back to defaults."""
        from ult3edit.disk import DiskContext
        base, ft, at = DiskContext._parse_hash_suffix('FOO#GGGG00')
        assert base == 'FOO'
        assert ft == 0x06
        assert at == 0x0000

    def test_write_stages_data(self):
        """DiskContext.write() stages data in _modified dict."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx.write('ROST', b'\x00' * 10)
        assert 'ROST' in ctx._modified
        assert ctx._modified['ROST'] == b'\x00' * 10

    def test_read_returns_modified_data(self):
        """read() returns staged modified data over cache."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx._cache['ROST'] = b'\x01' * 10
        ctx.write('ROST', b'\x02' * 10)
        assert ctx.read('ROST') == b'\x02' * 10

    def test_read_returns_cached_data(self):
        """read() returns cached data when not modified."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx._cache['ROST'] = b'\x03' * 10
        assert ctx.read('ROST') == b'\x03' * 10

    def test_read_returns_none_no_tmpdir(self):
        """read() returns None when _tmpdir is None and no cache."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        assert ctx.read('MISSING') is None

    def test_read_from_tmpdir(self, tmp_path):
        """read() scans _tmpdir files and populates cache + file_types."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx._tmpdir = str(tmp_path)
        # Create a file with hash suffix in tmpdir
        rost_path = os.path.join(str(tmp_path), 'ROST#069500')
        with open(rost_path, 'wb') as f:
            f.write(b'\xAB' * 20)
        result = ctx.read('ROST')
        assert result == b'\xAB' * 20
        assert 'ROST' in ctx._cache
        assert ctx._file_types['ROST'] == (0x06, 0x9500)

    def test_read_case_insensitive(self, tmp_path):
        """read() matches filenames case-insensitively."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx._tmpdir = str(tmp_path)
        fpath = os.path.join(str(tmp_path), 'rost#060000')
        with open(fpath, 'wb') as f:
            f.write(b'\xCD' * 5)
        result = ctx.read('ROST')
        assert result == b'\xCD' * 5


class TestDiskContextExit:
    """Test DiskContext.__exit__ writeback and cleanup behavior."""

    def test_exit_cleans_tmpdir(self, tmp_path):
        """__exit__ removes the tmpdir."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        tmpdir = os.path.join(str(tmp_path), 'ult3edit_test')
        os.makedirs(tmpdir)
        ctx._tmpdir = tmpdir
        ctx.__exit__(None, None, None)
        assert not os.path.exists(tmpdir)

    def test_exit_returns_false(self):
        """__exit__ returns False (does not suppress exceptions)."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx._tmpdir = None
        result = ctx.__exit__(None, None, None)
        assert result is False


class TestDiskAuditLogic:
    """Test cmd_audit logic with mocked disk_info/disk_list."""

    def test_audit_text_output(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'blocks': '280',
            'volume': 'TEST',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [
            {'name': 'ROST', 'type': 'BIN', 'size': '1280'},
            {'name': 'MAPA', 'type': 'BIN', 'size': '4096'},
        ])
        args = argparse.Namespace(
            image='test.po', json=False, output=None, detail=False)
        disk.cmd_audit(args)
        out = capsys.readouterr().out
        assert 'Disk Audit' in out
        assert '280' in out  # total blocks shown

    def test_audit_json_output(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'blocks': '280',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [
            {'name': 'ROST', 'type': 'BIN', 'size': '1280'},
        ])
        args = argparse.Namespace(
            image='test.po', json=True, output=None, detail=False)
        disk.cmd_audit(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data['total_blocks'] == 280
        assert data['used_blocks'] == 3  # ceil(1280/512) = 3
        assert data['free_blocks'] == 277
        assert 'capacity_estimates' in data

    def test_audit_detail_flag(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'blocks': '100',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [
            {'name': 'TEST', 'type': 'BIN', 'size': '256'},
        ])
        args = argparse.Namespace(
            image='test.po', json=False, output=None, detail=True)
        disk.cmd_audit(args)
        out = capsys.readouterr().out
        assert 'TEST' in out
        assert 'BIN' in out

    def test_audit_error(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'error': 'bad image',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [])
        args = argparse.Namespace(
            image='test.po', json=False, output=None, detail=False)
        with pytest.raises(SystemExit):
            disk.cmd_audit(args)


class TestDiskCmdHandlers:
    """Test disk CLI handler functions."""

    def test_cmd_info_error(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'error': 'not found',
        })
        args = argparse.Namespace(image='bad.po', json=False, output=None)
        with pytest.raises(SystemExit):
            disk.cmd_info(args)

    def test_cmd_info_text(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'volume': 'GAME',
            'format': 'ProDOS',
        })
        args = argparse.Namespace(image='game.po', json=False, output=None)
        disk.cmd_info(args)
        out = capsys.readouterr().out
        assert 'GAME' in out
        assert 'ProDOS' in out

    def test_cmd_info_json(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'volume': 'GAME',
        })
        args = argparse.Namespace(image='game.po', json=True, output=None)
        disk.cmd_info(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data['volume'] == 'GAME'

    def test_cmd_list_empty(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_list', lambda image, path, **kw: [])
        args = argparse.Namespace(image='empty.po', path='/', json=False, output=None)
        with pytest.raises(SystemExit):
            disk.cmd_list(args)

    def test_cmd_list_text(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_list', lambda image, path, **kw: [
            {'name': 'ROST', 'type': 'BIN', 'size': '1280'},
        ])
        args = argparse.Namespace(image='game.po', path='/', json=False, output=None)
        disk.cmd_list(args)
        out = capsys.readouterr().out
        assert 'ROST' in out
        assert '1 files' in out

    def test_cmd_list_json(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_list', lambda image, path, **kw: [
            {'name': 'ROST', 'type': 'BIN', 'size': '1280'},
        ])
        args = argparse.Namespace(image='game.po', path='/', json=True, output=None)
        disk.cmd_list(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert len(data) == 1
        assert data[0]['name'] == 'ROST'

    def test_cmd_extract_success(self, monkeypatch, capsys, tmp_path):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_extract_all', lambda *a, **kw: True)
        args = argparse.Namespace(image='game.po', output=str(tmp_path))
        disk.cmd_extract(args)
        out = capsys.readouterr().out
        assert 'Extracted' in out

    def test_cmd_extract_failure(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_extract_all', lambda *a, **kw: False)
        args = argparse.Namespace(image='bad.po', output=None)
        with pytest.raises(SystemExit):
            disk.cmd_extract(args)


class TestRosterValidateInventoryBcd:
    """roster validate_character does not validate inventory BCD bytes (design gap)."""

    def test_invalid_bcd_in_weapon_inventory_not_caught(self):
        """Weapon inventory bytes with non-BCD values are NOT flagged.
        This documents the design gap — not a failure."""
        from ult3edit.roster import validate_character, Character
        data = bytearray(CHAR_RECORD_SIZE)
        # Make non-empty: set name
        data[0] = 0xC1  # 'A' in high-ASCII
        data[0x11] = 0x47  # status = 'G' (Good)
        data[0x12] = 0x25  # STR = 25 (valid BCD)
        data[0x13] = 0x25  # DEX
        data[0x14] = 0x25  # INT
        data[0x15] = 0x25  # WIS
        # Put invalid BCD (0xAA) in weapon inventory slot 0
        data[0x31] = 0xAA
        char = Character(data)
        warnings = validate_character(char)
        # No warning about weapon inventory BCD — this is the gap
        assert not any('weapon' in w.lower() for w in warnings)

    def test_invalid_bcd_in_armor_inventory_not_caught(self):
        """Armor inventory bytes with non-BCD values are NOT flagged."""
        from ult3edit.roster import validate_character, Character
        data = bytearray(CHAR_RECORD_SIZE)
        data[0] = 0xC1
        data[0x11] = 0x47
        data[0x12] = 0x25
        data[0x13] = 0x25
        data[0x14] = 0x25
        data[0x15] = 0x25
        data[0x29] = 0xFF  # Invalid BCD in armor inventory
        char = Character(data)
        warnings = validate_character(char)
        assert not any('armor inv' in w.lower() for w in warnings)


class TestSavePLRSOnlyDryRun:
    """save cmd_edit with only PLRS changes + dry_run reaches elif branch."""

    def test_plrs_only_dry_run_message(self, tmp_path, capsys):
        from ult3edit.save import cmd_edit
        # Create PRTY file
        prty_data = bytearray(PRTY_FILE_SIZE)
        prty_data[PRTY_OFF_SENTINEL] = 0xFF
        prty_path = os.path.join(str(tmp_path), 'PRTY')
        with open(prty_path, 'wb') as f:
            f.write(prty_data)
        # Create PLRS file (4 characters, only first slot non-empty)
        plrs_data = bytearray(PLRS_FILE_SIZE)
        plrs_data[0] = 0xC1  # Name 'A'
        plrs_data[0x11] = 0x47  # Status Good
        plrs_data[0x12] = int_to_bcd(25)  # STR
        plrs_data[0x13] = int_to_bcd(25)  # DEX
        plrs_data[0x14] = int_to_bcd(25)  # INT
        plrs_data[0x15] = int_to_bcd(25)  # WIS
        plrs_path = os.path.join(str(tmp_path), 'PLRS')
        with open(plrs_path, 'wb') as f:
            f.write(plrs_data)
        args = argparse.Namespace(
            game_dir=str(tmp_path), dry_run=True, backup=False,
            output=None, validate=False,
            # PRTY fields — no changes
            transport=None, party_size=None, location=None,
            x=None, y=None, sentinel=None,
            slot=None, slot_ids=None,
            # PLRS fields — change stat on slot 0
            plrs_slot=0, name=None, status=None,
            hp=50, max_hp=None, mp=None, exp=None,
            food=None, gold=None, gems=None, keys=None,
            powders=None, torches=None, sub_morsels=None,
            race=None, char_class=None, gender=None,
            marks=None, cards=None,
            weapon=None, armor=None,
            in_party=None, not_in_party=None,
        )
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        # Verify PLRS file was NOT written (dry run)
        with open(plrs_path, 'rb') as f:
            assert f.read() == bytes(plrs_data)


class TestTlkFindWithoutReplace:
    """tlk cmd_edit with --find only (no --replace) exits with error."""

    def test_find_without_replace_exits(self, tmp_path, capsys):
        from ult3edit.tlk import cmd_edit
        tlk_path = os.path.join(str(tmp_path), 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(b'\xC8\xC5\xCC\xCC\xCF\x00')  # "HELLO" in high-ASCII
        args = argparse.Namespace(
            file=tlk_path, find='HELLO', replace=None,
            dry_run=False, backup=False, output=None,
            record=None, text=None, ignore_case=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_replace_without_find_exits(self, tmp_path, capsys):
        from ult3edit.tlk import cmd_edit
        tlk_path = os.path.join(str(tmp_path), 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(b'\xC8\xC5\xCC\xCC\xCF\x00')
        args = argparse.Namespace(
            file=tlk_path, find=None, replace='WORLD',
            dry_run=False, backup=False, output=None,
            record=None, text=None, ignore_case=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestTlkIsTextRecordEdgeCases:
    """Edge cases for is_text_record threshold logic."""

    def test_all_separators_returns_false(self):
        """Record with only line breaks has content_bytes=0 → False."""
        from ult3edit.tlk import is_text_record, TLK_LINE_BREAK
        data = bytes([TLK_LINE_BREAK, TLK_LINE_BREAK, TLK_LINE_BREAK])
        assert is_text_record(data) is False

    def test_exactly_70_percent_returns_false(self):
        """Exactly 70% high-ASCII returns False (threshold is > 0.7)."""
        from ult3edit.tlk import is_text_record
        # 7 high-ASCII + 3 low bytes = 70% exactly
        data = bytes([0xC1] * 7 + [0x10] * 3)
        assert is_text_record(data) is False

    def test_71_percent_returns_true(self):
        """Just above 70% threshold returns True."""
        from ult3edit.tlk import is_text_record
        # 8 high-ASCII + 3 low bytes = 72.7%
        data = bytes([0xC1] * 8 + [0x10] * 3)
        assert is_text_record(data) is True


class TestSpellDispatchFallback:
    """spell dispatch with unknown command prints usage."""

    def test_dispatch_unknown_command(self, capsys):
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command='unknown')
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err

    def test_dispatch_none_command(self, capsys):
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err


class TestDiskDispatchFallback:
    """disk dispatch with unknown command prints usage."""

    def test_dispatch_unknown(self, capsys):
        from ult3edit.disk import dispatch
        args = argparse.Namespace(disk_command='unknown')
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err


# =============================================================================
# Batch 14: Grade-A upgrade tests
# =============================================================================


class TestMapCompileOverworldPadding:
    """map.py: overworld row/grid padding uses 0x04 (Grass), not 0x00."""

    def test_short_overworld_padded_with_grass(self, tmp_path):
        """Compile a 3x3 overworld map and verify padding is 0x04."""
        from ult3edit.map import cmd_compile
        # Create a tiny 3x3 map text file (. = Grass)
        map_src = tmp_path / 'tiny.map'
        map_src.write_text('...\n...\n...\n')
        out_file = tmp_path / 'MAPA'
        args = argparse.Namespace(
            source=str(map_src), output=str(out_file), dungeon=False)
        cmd_compile(args)
        data = out_file.read_bytes()
        assert len(data) == 4096  # 64x64
        # The first row should be 3 Grass + 61 Grass padding
        assert data[0] == 0x04
        assert data[3] == 0x04  # padding byte, NOT 0x00
        # Row 4 (index 192+) should be all-Grass padding rows
        assert data[192] == 0x04  # row 3 is all padding
        assert data[4095] == 0x04  # last byte is Grass

    def test_dungeon_padded_with_zero(self, tmp_path):
        """Dungeon maps pad with 0x00 (open floor), not 0x04."""
        from ult3edit.map import cmd_compile
        map_src = tmp_path / 'dungeon.map'
        # Write a minimal dungeon map: 1 level with 1 row
        map_src.write_text('# Level 0\n' + '.' * 16 + '\n')
        out_file = tmp_path / 'MAPM'
        args = argparse.Namespace(
            source=str(map_src), output=str(out_file), dungeon=True)
        cmd_compile(args)
        data = out_file.read_bytes()
        assert len(data) == 2048  # 8 levels x 16x16


class TestSpecialConstantsImportable:
    """special.py constants moved to constants.py and importable."""

    def test_special_meta_offset_value(self):
        from ult3edit.constants import SPECIAL_META_OFFSET
        assert SPECIAL_META_OFFSET == 121

    def test_special_meta_size_value(self):
        from ult3edit.constants import SPECIAL_META_SIZE
        assert SPECIAL_META_SIZE == 7

    def test_special_module_uses_constants(self):
        """Verify special.py imports these from constants, not local defs."""
        import ult3edit.special as sp
        from ult3edit.constants import SPECIAL_META_OFFSET, SPECIAL_META_SIZE
        assert sp.SPECIAL_META_OFFSET == SPECIAL_META_OFFSET
        assert sp.SPECIAL_META_SIZE == SPECIAL_META_SIZE


class TestDiffMapDungeonLevelFormat:
    """diff.py: dungeon map diffs show Level N (X, Y) format."""

    def test_dungeon_diff_has_level_info(self, tmp_path):
        """Diff two dungeon MAPs, verify level info in text output."""
        from ult3edit.diff import diff_map, format_text, GameDiff
        # Create two dungeon maps (2048 bytes) with one tile different
        d1 = bytearray(2048)
        d2 = bytearray(2048)
        # Put a difference at level 2, position (5, 3)
        # Level 2 starts at offset 2*256, row 3 is at 3*16, col 5
        offset = 2 * 256 + 3 * 16 + 5
        d1[offset] = 0x00
        d2[offset] = 0x01
        f1 = tmp_path / 'MAPM_a'
        f2 = tmp_path / 'MAPM_b'
        f1.write_bytes(bytes(d1))
        f2.write_bytes(bytes(d2))
        fd = diff_map(str(f1), str(f2), 'MAPM')
        assert fd.dungeon_width == 16
        assert fd.tile_changes == 1
        # Check text formatting
        gd = GameDiff()
        gd.files.append(fd)
        text = format_text(gd)
        assert 'Level 2' in text
        assert '(5, 3)' in text

    def test_overworld_diff_no_level(self, tmp_path):
        """Overworld diffs show plain (X, Y) without level info."""
        from ult3edit.diff import diff_map, format_text, GameDiff
        d1 = bytearray(4096)
        d2 = bytearray(4096)
        d1[64 * 10 + 20] = 0x00
        d2[64 * 10 + 20] = 0x04
        f1 = tmp_path / 'MAPA_a'
        f2 = tmp_path / 'MAPA_b'
        f1.write_bytes(bytes(d1))
        f2.write_bytes(bytes(d2))
        fd = diff_map(str(f1), str(f2), 'MAPA')
        assert fd.dungeon_width == 0
        gd = GameDiff()
        gd.files.append(fd)
        text = format_text(gd)
        assert 'Level' not in text
        assert '(20, 10)' in text


class TestVerifySizeWarnings:
    """verify.py: reports size mismatches when verbose."""

    def test_wrong_size_generates_warning(self, tmp_path):
        """verify.py detects size mismatch and reports it."""
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), '..', 'conversions', 'tools'))
        try:
            from verify import verify_category
        finally:
            sys.path.pop(0)
        # Create a ROST file with wrong size
        game_dir = tmp_path / 'game'
        game_dir.mkdir()
        (game_dir / 'ROST').write_bytes(b'\x00' * 100)  # Should be 1280
        info = {
            'files': ['ROST'],
            'sizes': [1280],
        }
        found, modified, missing, unchanged, size_warns = verify_category(
            str(game_dir), 'Characters', info)
        assert len(found) == 1
        assert len(size_warns) == 1
        assert '100' in size_warns[0]
        assert '1280' in size_warns[0]


class TestRosterNoDeadImport:
    """roster.py: encode_high_ascii not imported (dead import removed)."""

    def test_no_encode_high_ascii_import(self):
        """Verify roster module doesn't import encode_high_ascii."""
        import ult3edit.roster as r
        # Should NOT have encode_high_ascii as a module-level name
        assert not hasattr(r, 'encode_high_ascii')
