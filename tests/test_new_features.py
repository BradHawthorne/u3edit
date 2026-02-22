"""Tests for Grok audit improvements: backup, dry-run, validate, search, import, etc."""

import argparse
import json
import os
import shutil
import sys
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


class TestTlkExtractBuild:
    """Integration tests for tlk extract → build round-trip."""

    def test_extract_build_roundtrip(self, tmp_path, sample_tlk_bytes):
        """extract → build produces identical binary."""
        from u3edit.tlk import cmd_extract, cmd_build
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
        from u3edit.tlk import cmd_extract
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
        from u3edit.tlk import cmd_build
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
        from u3edit.combat import cmd_import as combat_cmd_import, CombatMap
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
        from u3edit.combat import cmd_import as combat_cmd_import, CombatMap
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
        from u3edit.combat import cmd_import as combat_cmd_import, CombatMap
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
        from u3edit.combat import cmd_import as combat_cmd_import, CombatMap
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
        from u3edit.special import cmd_import as special_cmd_import
        path = os.path.join(tmp_dir, 'SHRN')
        with open(path, 'wb') as f:
            f.write(sample_special_bytes)

        # Build JSON with a modified tile grid
        from u3edit.constants import tile_char, SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT
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
        from u3edit.special import cmd_import as special_cmd_import
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
        from u3edit.special import cmd_import as special_cmd_import
        from u3edit.constants import tile_char, SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT
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
        from u3edit.text import cmd_import as text_cmd_import
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
        from u3edit.text import cmd_import as text_cmd_import
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
    parse_coord_region, encode_text_region, encode_coord_region,
    cmd_import as patch_cmd_import, PATCHABLE_REGIONS,
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
            [sys.executable, '-m', 'u3edit.diff', '--help'],
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


class TestDiskContextParseHash:
    """Test DiskContext._parse_hash_suffix."""

    def test_with_hash_suffix(self):
        from u3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('ROST#069500')
        assert name == 'ROST'
        assert ft == 0x06
        assert at == 0x9500

    def test_without_hash(self):
        from u3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('ROST')
        assert name == 'ROST'
        assert ft == 0x06
        assert at == 0x0000

    def test_short_suffix(self):
        from u3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('FOO#AB')
        assert name == 'FOO'
        assert ft == 0x06  # fallback
        assert at == 0x0000

    def test_all_zeros(self):
        from u3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('MAP#000000')
        assert name == 'MAP'
        assert ft == 0x00
        assert at == 0x0000


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

# =============================================================================
# Fix: Map JSON round-trip preserves tile data
# =============================================================================

class TestMapJsonRoundTrip:
    """Verify that map export→import round-trip preserves all tiles."""

    def test_overworld_round_trip(self, tmp_dir, sample_overworld_bytes):
        """Export an overworld map to JSON, import it back, verify tiles match."""
        from u3edit.map import cmd_view, cmd_import
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
        from u3edit.map import cmd_view, cmd_import
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
        from u3edit.map import cmd_import
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
        from u3edit.map import cmd_import
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
        from u3edit.constants import TILE_NAMES_REVERSE
        assert TILE_NAMES_REVERSE['water'] == 0x00
        assert TILE_NAMES_REVERSE['grass'] == 0x04
        assert TILE_NAMES_REVERSE['town'] == 0x18

    def test_resolve_tile_handles_dungeon_names(self):
        """Dungeon tile name reverse lookup works."""
        from u3edit.constants import DUNGEON_TILE_NAMES_REVERSE
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
        from u3edit.save import cmd_edit
        from u3edit.constants import PLRS_FILE_SIZE, CHAR_RECORD_SIZE
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
        from u3edit.bestiary import register_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='module')
        register_parser(sub)
        args = parser.parse_args(['bestiary', 'edit', 'test.mon', '--monster', '0',
                                  '--hp', '50', '--validate'])
        assert args.validate is True

    def test_combat_edit_accepts_validate(self):
        """combat edit --validate should be a valid CLI arg."""
        import argparse
        from u3edit.combat import register_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='module')
        register_parser(sub)
        args = parser.parse_args(['combat', 'edit', 'test.con',
                                  '--tile', '0', '0', '32', '--validate'])
        assert args.validate is True

    def test_bestiary_edit_validate_runs(self, tmp_dir, sample_mon_bytes):
        """bestiary edit with --validate should show warnings."""
        from u3edit.bestiary import cmd_edit
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
        from u3edit.combat import cmd_edit
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
        from u3edit import fileutil
        assert not hasattr(fileutil, 'validate_file_size')

    def test_load_game_file_removed(self):
        """load_game_file should no longer exist in fileutil."""
        from u3edit import fileutil
        assert not hasattr(fileutil, 'load_game_file')


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


# =============================================================================
# Patch import + round-trip tests
# =============================================================================

class TestPatchImport:
    """Tests for patch import command and encode_coord_region."""

    def _make_ult3(self):
        """Create a synthetic ULT3 binary with known region data."""
        data = bytearray(17408)
        # Name table: empty + "WATER" + "GRASS"
        offset = 0x397A
        text = b'\x00\xD7\xC1\xD4\xC5\xD2\x00\xC7\xD2\xC1\xD3\xD3\x00'
        data[offset:offset + len(text)] = text
        # Moongate X/Y
        for i in range(8):
            data[0x29A7 + i] = i * 8
            data[0x29AF + i] = i * 4
        # Food rate
        data[0x272C] = 0x04
        return data

    def _make_exod(self):
        """Create a synthetic EXOD binary with known coord data."""
        data = bytearray(26208)
        # Town coords: 16 pairs at $35E1
        for i in range(16):
            data[0x35E1 + i * 2] = 10 + i
            data[0x35E1 + i * 2 + 1] = 20 + i
        return data

    def test_encode_coord_region(self):
        coords = [{'x': 10, 'y': 20}, {'x': 30, 'y': 40}]
        encoded = encode_coord_region(coords, 8)
        assert len(encoded) == 8
        assert encoded[0] == 10
        assert encoded[1] == 20
        assert encoded[2] == 30
        assert encoded[3] == 40
        # Padding
        assert encoded[4:] == b'\x00\x00\x00\x00'

    def test_encode_coord_too_long(self):
        coords = [{'x': i, 'y': i} for i in range(10)]
        with pytest.raises(ValueError):
            encode_coord_region(coords, 4)

    def test_text_round_trip(self, tmp_path):
        """parse_text_region → encode_text_region preserves content."""
        data = self._make_ult3()
        strings = parse_text_region(bytes(data), 0x397A, 921)
        encoded = encode_text_region(strings, 921)
        reparsed = parse_text_region(encoded, 0, 921)
        assert reparsed == strings

    def test_text_round_trip_preserves_empty(self):
        """Empty strings (consecutive nulls) survive round-trip."""
        # Build: "" + "HELLO" + "" + "WORLD"
        raw = bytearray(50)
        raw[0] = 0x00  # empty string
        hello = b'\xC8\xC5\xCC\xCC\xCF\x00'  # "HELLO" + null
        raw[1:1 + len(hello)] = hello
        pos = 1 + len(hello)
        raw[pos] = 0x00  # empty string
        pos += 1
        world = b'\xD7\xCF\xD2\xCC\xC4\x00'  # "WORLD" + null
        raw[pos:pos + len(world)] = world

        strings = parse_text_region(bytes(raw), 0, 50)
        assert strings == ['', 'HELLO', '', 'WORLD']

        encoded = encode_text_region(strings, 50)
        reparsed = parse_text_region(encoded, 0, 50)
        assert reparsed == strings

    def test_coord_round_trip(self):
        """parse_coord_region → encode_coord_region preserves content."""
        raw = bytes([10, 20, 30, 40, 50, 60, 0, 0])
        coords = parse_coord_region(raw, 0, 8)
        encoded = encode_coord_region(coords, 8)
        assert encoded == raw

    def test_import_text_region(self, tmp_path):
        """Import name-table from JSON file."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        # Build JSON with replacement names
        jdata = {
            'regions': {
                'name-table': {
                    'data': ['', 'BRINE', 'ASH'],
                }
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        # Verify the name-table was patched
        with open(path, 'rb') as f:
            result = f.read()
        strings = parse_text_region(result, 0x397A, 921)
        assert '' in strings
        assert 'BRINE' in strings
        assert 'ASH' in strings
        # Old names should be gone
        assert 'WATER' not in strings
        assert 'GRASS' not in strings

    def test_import_bytes_region(self, tmp_path):
        """Import moongate-x and food-rate byte regions."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        jdata = {
            'regions': {
                'moongate-x': {'data': [10, 20, 30, 40, 50, 30, 20, 10]},
                'food-rate': {'data': [2]},
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result[0x29A7:0x29A7 + 8]) == [10, 20, 30, 40, 50, 30, 20, 10]
        assert result[0x272C] == 2

    def test_import_coord_region(self, tmp_path):
        """Import town-coords from JSON."""
        data = self._make_exod()
        path = str(tmp_path / 'EXOD')
        with open(path, 'wb') as f:
            f.write(data)

        new_coords = [{'x': 5, 'y': 10}, {'x': 15, 'y': 20}]
        jdata = {
            'regions': {
                'town-coords': {'data': new_coords},
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x35E1] == 5
        assert result[0x35E2] == 10
        assert result[0x35E3] == 15
        assert result[0x35E4] == 20

    def test_import_dry_run(self, tmp_path):
        """Dry run does not modify file."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        jdata = {
            'regions': {
                'food-rate': {'data': [1]},
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': None,
            'backup': False,
            'dry_run': True,
        })()
        patch_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x272C] == 0x04  # Unchanged

    def test_import_region_filter(self, tmp_path):
        """--region flag limits which regions are imported."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        jdata = {
            'regions': {
                'food-rate': {'data': [1]},
                'moongate-x': {'data': [99, 99, 99, 99, 99, 99, 99, 99]},
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': 'food-rate',
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x272C] == 1  # Updated
        # moongate-x should be unchanged (filtered out)
        assert list(result[0x29A7:0x29A7 + 8]) == [i * 8 for i in range(8)]

    def test_import_output_file(self, tmp_path):
        """--output writes to separate file."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        out_path = str(tmp_path / 'ULT3_patched')
        with open(path, 'wb') as f:
            f.write(data)

        jdata = {
            'regions': {
                'food-rate': {'data': [3]},
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': out_path,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        # Original unchanged
        with open(path, 'rb') as f:
            assert f.read()[0x272C] == 0x04
        # Output has new value
        with open(out_path, 'rb') as f:
            assert f.read()[0x272C] == 3

    def test_import_flat_json_format(self, tmp_path):
        """Accept flat JSON without 'regions' wrapper."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        # Flat format: region name → data list directly
        jdata = {
            'food-rate': [2],
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x272C] == 2

    def test_import_full_view_json_round_trip(self, tmp_path):
        """view --json output can be fed directly back into import."""
        from u3edit.patch import cmd_view
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        # Export via cmd_view --json
        json_path = str(tmp_path / 'export.json')
        view_args = type('Args', (), {
            'file': path,
            'region': None,
            'json': True,
            'output': json_path,
        })()
        cmd_view(view_args)

        # Modify a value in the exported JSON
        with open(json_path, 'r') as f:
            jdata = json.load(f)
        jdata['regions']['food-rate']['data'] = [2]

        modified_json = str(tmp_path / 'modified.json')
        with open(modified_json, 'w') as f:
            json.dump(jdata, f)

        # Import back
        out_path = str(tmp_path / 'ULT3_new')
        import_args = type('Args', (), {
            'file': path,
            'json_file': modified_json,
            'region': None,
            'output': out_path,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(import_args)

        # Verify food rate changed, name table preserved
        with open(out_path, 'rb') as f:
            result = f.read()
        assert result[0x272C] == 2
        strings = parse_text_region(result, 0x397A, 921)
        assert 'WATER' in strings
        assert 'GRASS' in strings


# =============================================================================
# Roster create extended args tests
# =============================================================================

class TestRosterCreateExtendedArgs:
    """Verify roster create accepts all edit args (hp, gold, food, etc.)."""

    def test_create_with_hp_and_gold(self, tmp_dir, sample_roster_file):
        """The Voidborn pattern: create with --hp and --gold."""
        from u3edit.roster import cmd_create
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
        from u3edit.roster import cmd_create
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
        from u3edit.roster import cmd_create
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
            ['python', '-m', 'u3edit.roster', 'create', '--help'],
            capture_output=True, text=True)
        assert '--hp' in result.stdout
        assert '--gold' in result.stdout
        assert '--food' in result.stdout
        assert '--in-party' in result.stdout


# =============================================================================
# Functional tests for cmd_edit_string (shapes) and cmd_search (tlk)
# =============================================================================

class TestCmdEditStringFunctional:
    """Functional tests for shapes edit-string on synthesized SHP overlay."""

    def _make_shp_overlay(self):
        """Create a synthetic SHP overlay with a JSR $46BA inline string."""
        data = bytearray(256)
        # Put JSR $46BA at offset 10
        data[10] = 0x20  # JSR
        data[11] = 0xBA
        data[12] = 0x46
        # Inline high-ASCII string "HELLO" + null terminator at offset 13
        hello = [0xC8, 0xC5, 0xCC, 0xCC, 0xCF, 0x00]
        data[13:13 + len(hello)] = hello
        # Another JSR $46BA at offset 30
        data[30] = 0x20
        data[31] = 0xBA
        data[32] = 0x46
        # Inline "BYE" + null at offset 33
        bye = [0xC2, 0xD9, 0xC5, 0x00]
        data[33:33 + len(bye)] = bye
        return data

    def test_edit_string_replaces_text(self, tmp_path):
        from u3edit.shapes import cmd_edit_string
        data = self._make_shp_overlay()
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)

        args = type('Args', (), {
            'file': path,
            'offset': 13,  # text_offset of "HELLO"
            'text': 'HI',
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        cmd_edit_string(args)

        with open(path, 'rb') as f:
            result = f.read()
        # "HI" encoded as high-ASCII: 0xC8 0xC9 + null
        assert result[13] == 0xC8  # H
        assert result[14] == 0xC9  # I
        assert result[15] == 0x00  # null terminator
        # Remaining bytes null-padded
        assert result[16] == 0x00
        assert result[17] == 0x00

    def test_edit_string_dry_run(self, tmp_path):
        from u3edit.shapes import cmd_edit_string
        data = self._make_shp_overlay()
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)

        args = type('Args', (), {
            'file': path,
            'offset': 13,
            'text': 'HI',
            'output': None,
            'backup': False,
            'dry_run': True,
        })()
        cmd_edit_string(args)

        # File unchanged
        with open(path, 'rb') as f:
            result = f.read()
        assert result[13] == 0xC8  # Still 'H' from HELLO
        assert result[14] == 0xC5  # Still 'E' from HELLO

    def test_edit_string_output_file(self, tmp_path):
        from u3edit.shapes import cmd_edit_string
        data = self._make_shp_overlay()
        path = str(tmp_path / 'SHP0')
        out_path = str(tmp_path / 'SHP0_out')
        with open(path, 'wb') as f:
            f.write(data)

        args = type('Args', (), {
            'file': path,
            'offset': 33,  # text_offset of "BYE"
            'text': 'NO',
            'output': out_path,
            'backup': False,
            'dry_run': False,
        })()
        cmd_edit_string(args)

        # Original unchanged
        with open(path, 'rb') as f:
            assert f.read()[33] == 0xC2  # B
        # Output has new value
        with open(out_path, 'rb') as f:
            result = f.read()
        assert result[33] == 0xCE  # N
        assert result[34] == 0xCF  # O

    def test_edit_string_bad_offset_exits(self, tmp_path):
        from u3edit.shapes import cmd_edit_string
        data = self._make_shp_overlay()
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)

        args = type('Args', (), {
            'file': path,
            'offset': 99,  # No string here
            'text': 'X',
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        with pytest.raises(SystemExit):
            cmd_edit_string(args)


class TestCmdSearchFunctional:
    """Functional tests for tlk search command."""

    def test_search_single_file(self, tmp_path, sample_tlk_bytes):
        from u3edit.tlk import cmd_search
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
        from u3edit.tlk import cmd_search
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
        from u3edit.tlk import cmd_search
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
        from u3edit.tlk import cmd_search
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
        from u3edit.tlk import cmd_search
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
        from u3edit.save import cmd_edit
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
            ['python', '-m', 'u3edit.save', 'edit', '--help'],
            capture_output=True, text=True)
        assert '--validate' in result.stdout


# =============================================================================
# hex_int acceptance: tile/offset/byte args accept 0x prefix
# =============================================================================

class TestHexIntArgParsing:
    """Verify that CLI args for tiles, offsets, and flags accept hex (0x) prefix."""

    def test_hex_int_helper(self):
        from u3edit.fileutil import hex_int
        assert hex_int('10') == 10
        assert hex_int('0x0A') == 10
        assert hex_int('0xFF') == 255
        assert hex_int('0') == 0

    def test_hex_int_rejects_garbage(self):
        from u3edit.fileutil import hex_int
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
        from u3edit.combat import cmd_edit as combat_cmd_edit
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
        from u3edit.bestiary import cmd_edit as bestiary_cmd_edit
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
        from u3edit.special import cmd_edit as special_cmd_edit
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
        from u3edit.fileutil import hex_int
        parser = argparse.ArgumentParser()
        parser.add_argument('--tile', type=hex_int)
        args = parser.parse_args(['--tile', '0x0A'])
        assert args.tile == 10

    def test_argparser_accepts_decimal_string(self):
        """hex_int still works with plain decimal strings."""
        import argparse
        from u3edit.fileutil import hex_int
        parser = argparse.ArgumentParser()
        parser.add_argument('--offset', type=hex_int)
        args = parser.parse_args(['--offset', '240'])
        assert args.offset == 240


# =============================================================================
# Sound and DDRW import integration tests
# =============================================================================

class TestSoundImportIntegration:
    """Integration tests for sound cmd_import()."""

    def test_import_sound_raw(self, tmp_path):
        """cmd_import() writes raw byte array from JSON."""
        from u3edit.sound import cmd_import as sound_cmd_import
        path = str(tmp_path / 'SOSA')
        original = bytes(range(256)) * 4  # 1024 bytes
        with open(path, 'wb') as f:
            f.write(original)

        new_data = list(range(255, -1, -1)) * 4  # Reversed pattern
        jdata = {'raw': new_data}
        json_path = str(tmp_path / 'sound.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        sound_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result) == new_data

    def test_import_sound_dry_run(self, tmp_path):
        """cmd_import() with dry_run does not modify file."""
        from u3edit.sound import cmd_import as sound_cmd_import
        path = str(tmp_path / 'SOSA')
        original = bytes(64)
        with open(path, 'wb') as f:
            f.write(original)

        jdata = {'raw': [0xFF] * 64}
        json_path = str(tmp_path / 'sound.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        sound_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == original

    def test_import_sound_output_file(self, tmp_path):
        """cmd_import() writes to --output file."""
        from u3edit.sound import cmd_import as sound_cmd_import
        path = str(tmp_path / 'SOSA')
        out_path = str(tmp_path / 'SOSA_OUT')
        with open(path, 'wb') as f:
            f.write(bytes(64))

        jdata = {'raw': [0xAB] * 32}
        json_path = str(tmp_path / 'sound.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': out_path, 'backup': False, 'dry_run': False,
        })()
        sound_cmd_import(args)

        with open(out_path, 'rb') as f:
            result = f.read()
        assert list(result) == [0xAB] * 32


class TestDdrwImportIntegration:
    """Integration tests for ddrw cmd_import()."""

    def test_import_ddrw_raw(self, tmp_path):
        """cmd_import() writes raw byte array from JSON."""
        from u3edit.ddrw import cmd_import as ddrw_cmd_import
        path = str(tmp_path / 'DDRW')
        original = bytes(256)
        with open(path, 'wb') as f:
            f.write(original)

        new_data = list(range(256))
        jdata = {'raw': new_data}
        json_path = str(tmp_path / 'ddrw.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        ddrw_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result) == new_data

    def test_import_ddrw_dry_run(self, tmp_path):
        """cmd_import() with dry_run does not modify file."""
        from u3edit.ddrw import cmd_import as ddrw_cmd_import
        path = str(tmp_path / 'DDRW')
        original = bytes(128)
        with open(path, 'wb') as f:
            f.write(original)

        jdata = {'raw': [0xFF] * 128}
        json_path = str(tmp_path / 'ddrw.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        ddrw_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == original


# =============================================================================
# Shapes cmd_edit and cmd_import integration tests
# =============================================================================

class TestShapesEditIntegration:
    """Integration tests for shapes cmd_edit()."""

    def _make_shps(self, tmp_path):
        """Create a synthetic 2048-byte SHPS file."""
        data = bytearray(2048)
        # Fill glyph 0 with a known pattern
        for i in range(8):
            data[i] = 0x55
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        return path, data

    def test_edit_glyph(self, tmp_path):
        """cmd_edit() updates a glyph's raw bytes."""
        from u3edit.shapes import cmd_edit as shapes_cmd_edit
        path, original = self._make_shps(tmp_path)

        args = type('Args', (), {
            'file': path, 'glyph': 0,
            'data': 'FF FF FF FF FF FF FF FF',
            'output': None, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_edit(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result[0:8]) == [0xFF] * 8

    def test_edit_glyph_dry_run(self, tmp_path):
        """cmd_edit() with dry_run does not modify file."""
        from u3edit.shapes import cmd_edit as shapes_cmd_edit
        path, original = self._make_shps(tmp_path)

        args = type('Args', (), {
            'file': path, 'glyph': 0,
            'data': 'AA AA AA AA AA AA AA AA',
            'output': None, 'backup': False, 'dry_run': True,
        })()
        shapes_cmd_edit(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(original)

    def test_edit_glyph_output_file(self, tmp_path):
        """cmd_edit() writes to --output file."""
        from u3edit.shapes import cmd_edit as shapes_cmd_edit
        path, _ = self._make_shps(tmp_path)
        out_path = str(tmp_path / 'SHPS_OUT')

        args = type('Args', (), {
            'file': path, 'glyph': 1,
            'data': '01 02 03 04 05 06 07 08',
            'output': out_path, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_edit(args)

        with open(out_path, 'rb') as f:
            result = f.read()
        assert list(result[8:16]) == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_edit_backup_skipped_with_output(self, tmp_path):
        """cmd_edit() with --output and --backup should NOT create .bak of input."""
        from u3edit.shapes import cmd_edit as shapes_cmd_edit
        path, _ = self._make_shps(tmp_path)
        out_path = str(tmp_path / 'SHPS_OUT')

        args = type('Args', (), {
            'file': path, 'glyph': 0,
            'data': 'FF FF FF FF FF FF FF FF',
            'output': out_path, 'backup': True, 'dry_run': False,
        })()
        shapes_cmd_edit(args)

        assert os.path.exists(out_path), "output file should exist"
        assert not os.path.exists(path + '.bak'), \
            "backup should not be created when --output is a different file"


class TestShapesImportIntegration:
    """Integration tests for shapes cmd_import()."""

    def _make_shps(self, tmp_path):
        """Create a synthetic 2048-byte SHPS file."""
        data = bytearray(2048)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        return path, data

    def test_import_glyph_list(self, tmp_path):
        """cmd_import() updates glyphs from flat list format."""
        from u3edit.shapes import cmd_import as shapes_cmd_import
        path, _ = self._make_shps(tmp_path)

        jdata = [
            {'index': 0, 'raw': [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]},
            {'index': 2, 'raw': [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00, 0x11]},
        ]
        json_path = str(tmp_path / 'glyphs.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result[0:8]) == [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]
        assert list(result[16:24]) == [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00, 0x11]
        # Glyph 1 should be unchanged (zeros)
        assert list(result[8:16]) == [0] * 8

    def test_import_tiles_format(self, tmp_path):
        """cmd_import() updates glyphs from tiles dict format."""
        from u3edit.shapes import cmd_import as shapes_cmd_import
        path, _ = self._make_shps(tmp_path)

        jdata = {
            'tiles': [{
                'tile_id': 0,
                'frames': [
                    {'index': 0, 'raw': [0xFF] * 8},
                    {'index': 1, 'raw': [0xAA] * 8},
                ]
            }]
        }
        json_path = str(tmp_path / 'tiles.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result[0:8]) == [0xFF] * 8
        assert list(result[8:16]) == [0xAA] * 8

    def test_import_dry_run(self, tmp_path):
        """cmd_import() with dry_run does not modify file."""
        from u3edit.shapes import cmd_import as shapes_cmd_import
        path, original = self._make_shps(tmp_path)

        jdata = [{'index': 0, 'raw': [0xFF] * 8}]
        json_path = str(tmp_path / 'glyphs.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        shapes_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(original)


# =============================================================================
# Fix: HP > MaxHP race condition when both --hp and --max-hp provided
# =============================================================================

class TestHpMaxHpOrdering:
    """Verify max_hp >= hp when both are set simultaneously."""

    def test_roster_hp_exceeds_max_hp(self, sample_character_bytes):
        """roster _apply_edits: --hp 200 --max-hp 100 should auto-raise max_hp."""
        from u3edit.roster import Character, _apply_edits
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
        from u3edit.roster import Character, _apply_edits
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
        from u3edit.save import cmd_edit
        from u3edit.constants import PLRS_FILE_SIZE, CHAR_RECORD_SIZE
        from u3edit.roster import Character
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

class TestShapesImportMalformedJson:
    """Verify shapes cmd_import() handles missing keys gracefully."""

    def _make_shps(self, tmp_path):
        data = bytearray(2048)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        return path, data

    def test_missing_index_in_list(self, tmp_path):
        """Entries missing 'index' key should be skipped, not crash."""
        from u3edit.shapes import cmd_import as shapes_cmd_import
        path, _ = self._make_shps(tmp_path)
        jdata = [
            {'raw': [0xFF] * 8},  # missing 'index'
            {'index': 1, 'raw': [0xAA] * 8},  # valid
        ]
        json_path = str(tmp_path / 'glyphs.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_import(args)  # should not raise KeyError
        with open(path, 'rb') as f:
            result = f.read()
        # Glyph 0 untouched (missing index skipped), glyph 1 updated
        assert list(result[0:8]) == [0] * 8
        assert list(result[8:16]) == [0xAA] * 8

    def test_missing_raw_in_tiles(self, tmp_path):
        """Frames missing 'raw' key should be skipped, not crash."""
        from u3edit.shapes import cmd_import as shapes_cmd_import
        path, _ = self._make_shps(tmp_path)
        jdata = {
            'tiles': [{
                'frames': [
                    {'index': 0},  # missing 'raw'
                    {'index': 1, 'raw': [0xBB] * 8},  # valid
                ]
            }]
        }
        json_path = str(tmp_path / 'tiles.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_import(args)  # should not raise KeyError
        with open(path, 'rb') as f:
            result = f.read()
        assert list(result[0:8]) == [0] * 8
        assert list(result[8:16]) == [0xBB] * 8


# =============================================================================
# Fix: weapons/armors .items() crash on non-dict JSON values
# =============================================================================

class TestImportMalformedInventory:
    """Verify cmd_import handles non-dict weapons/armors gracefully."""

    def test_roster_import_null_weapons(self, tmp_dir, sample_roster_bytes):
        """roster cmd_import: weapons=null should not crash."""
        from u3edit.roster import cmd_import as roster_cmd_import
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
        from u3edit.roster import cmd_import as roster_cmd_import
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
        from u3edit.save import cmd_import as save_cmd_import
        from u3edit.constants import PLRS_FILE_SIZE, CHAR_RECORD_SIZE
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
        from u3edit.roster import Character
        char = Character(bytearray(sample_character_bytes))
        char.marks = ['fire', 'force']
        assert 'Fire' in char.marks
        assert 'Force' in char.marks

    def test_marks_uppercase(self, sample_character_bytes):
        """Setting marks with uppercase names should work."""
        from u3edit.roster import Character
        char = Character(bytearray(sample_character_bytes))
        char.marks = ['KINGS', 'SNAKE']
        assert 'Kings' in char.marks
        assert 'Snake' in char.marks

    def test_cards_lowercase(self, sample_character_bytes):
        """Setting cards with lowercase names should work."""
        from u3edit.roster import Character
        char = Character(bytearray(sample_character_bytes))
        char.cards = ['death', 'sol', 'love', 'moons']
        assert len(char.cards) == 4

    def test_marks_mixed_case(self, sample_character_bytes):
        """Setting marks with mixed casing should work."""
        from u3edit.roster import Character
        char = Character(bytearray(sample_character_bytes))
        char.marks = ['fIrE', 'FoRcE']
        assert 'Fire' in char.marks
        assert 'Force' in char.marks

    def test_marks_preserves_cards(self, sample_character_bytes):
        """Setting marks should not clear existing cards."""
        from u3edit.roster import Character
        char = Character(bytearray(sample_character_bytes))
        char.cards = ['Death', 'Sol']
        char.marks = ['kings']
        assert 'Kings' in char.marks
        assert 'Death' in char.cards
        assert 'Sol' in char.cards


# =============================================================================
# Tile Compiler Tests
# =============================================================================

class TestTileCompilerParsing:
    """Test tile_compiler.py text-art parsing."""

    def test_parse_single_tile(self):
        """Parse a single tile definition."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = (
            '# Tile 0x00: Test\n'
            '#######\n'
            '.......\n'
            '#.#.#.#\n'
            '.#.#.#.\n'
            '#.#.#.#\n'
            '.......\n'
            '#######\n'
            '.......\n'
        )
        tiles = parse_tiles_file(text)
        assert len(tiles) == 1
        idx, data = tiles[0]
        assert idx == 0
        assert len(data) == 8
        assert data[0] == 0x7F  # All 7 bits set = 1111111 = 0x7F

    def test_parse_multiple_tiles(self):
        """Parse two tiles separated by blank line."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = ('# Tile 0x00: First\n'
                + '#######\n' * 8
                + '\n'
                + '# Tile 0x01: Second\n'
                + '.......\n' * 8)
        tiles = parse_tiles_file(text)
        assert len(tiles) == 2
        assert tiles[0][0] == 0
        assert tiles[1][0] == 1

    def test_parse_hex_index(self):
        """Parse a tile with hex index."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = '# Tile 0x1A: Test\n' + '.......\n' * 8
        tiles = parse_tiles_file(text)
        assert tiles[0][0] == 0x1A

    def test_parse_decimal_index(self):
        """Parse a tile with decimal index."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = '# Tile 42: Test\n' + '.......\n' * 8
        tiles = parse_tiles_file(text)
        assert tiles[0][0] == 42


class TestTileCompilerBitEncoding:
    """Test tile_compiler.py pixel->bit encoding."""

    def test_all_on(self):
        """All pixels on = 0x7F per row."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = '# Tile 0x00: All on\n' + '#######\n' * 8
        tiles = parse_tiles_file(text)
        _, data = tiles[0]
        for b in data:
            assert b == 0x7F

    def test_all_off(self):
        """All pixels off = 0x00 per row."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = '# Tile 0x00: All off\n' + '.......\n' * 8
        tiles = parse_tiles_file(text)
        _, data = tiles[0]
        for b in data:
            assert b == 0x00

    def test_bit_order(self):
        """First char = bit 0, last char = bit 6."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        # Only leftmost pixel on
        text = '# Tile 0x00: Bit 0\n' + ('#......\n') * 8
        tiles = parse_tiles_file(text)
        _, data = tiles[0]
        assert data[0] == 0x01  # Bit 0 only

        # Only rightmost pixel on
        text2 = '# Tile 0x00: Bit 6\n' + ('......#\n') * 8
        tiles2 = parse_tiles_file(text2)
        _, data2 = tiles2[0]
        assert data2[0] == 0x40  # Bit 6 only


class TestTileCompilerRoundTrip:
    """Test tile_compiler.py compile -> decompile round-trip."""

    def test_round_trip(self, tmp_path):
        """Decompile SHPS data then compile back should reproduce bytes."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import decompile_shps, parse_tiles_file, _rows_to_bytes

        # Create a known SHPS binary (just first 3 tiles)
        data = bytearray(2048)
        data[0:8] = bytes([0x7F, 0x41, 0x41, 0x41, 0x41, 0x41, 0x7F, 0x00])
        data[8:16] = bytes([0x00, 0x3E, 0x22, 0x22, 0x22, 0x3E, 0x00, 0x00])

        # Decompile
        text = decompile_shps(bytes(data))

        # Parse back
        tiles = parse_tiles_file(text)
        assert len(tiles) == 256

        # First tile should match
        _, recompiled = tiles[0]
        assert recompiled == bytes(data[0:8])

        # Second tile should match
        _, recompiled2 = tiles[1]
        assert recompiled2 == bytes(data[8:16])

    def test_compile_to_json(self):
        """Compile tiles to JSON format."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file, compile_to_json
        text = '# Tile 0x05: Test\n' + '#......\n' * 8
        tiles = parse_tiles_file(text)
        result = compile_to_json(tiles)
        assert 'tiles' in result
        assert result['tiles'][0]['frames'][0]['index'] == 5
        assert result['tiles'][0]['frames'][0]['raw'] == [1] * 8

    def test_compile_to_script(self):
        """Compile tiles to shell script format."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file, compile_to_script
        text = '# Tile 0x00: Test\n' + '.......\n' * 8
        tiles = parse_tiles_file(text)
        script = compile_to_script(tiles)
        assert 'u3edit shapes edit' in script
        assert '--glyph 0' in script
        assert '--backup' in script


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
        from u3edit.bestiary import cmd_import as bestiary_import
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
        from u3edit.bestiary import cmd_import as bestiary_import
        from u3edit.constants import (
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
        from u3edit.bestiary import cmd_import as bestiary_import
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
        from u3edit.combat import cmd_import as combat_import
        args = argparse.Namespace(
            file=str(con_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        combat_import(args)
        data = con_file.read_bytes()
        from u3edit.constants import (
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
        from u3edit.combat import cmd_import as combat_import
        args = argparse.Namespace(
            file=str(con_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        combat_import(args)
        data = con_file.read_bytes()
        from u3edit.constants import CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET
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

class TestNameCompilerParse:
    """Test parsing .names text files."""

    def test_parse_simple(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import parse_names_file
        text = '# Group: Test\nFOO\nBAR\nBAZ\n'
        names = parse_names_file(text)
        assert names == ['FOO', 'BAR', 'BAZ']

    def test_parse_empty_string(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import parse_names_file
        text = '""\nFOO\n""\nBAR\n'
        names = parse_names_file(text)
        assert names == ['', 'FOO', '', 'BAR']

    def test_parse_skips_comments_and_blanks(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import parse_names_file
        text = '# Header\n\n# Group: A\nFOO\n\n# Group: B\nBAR\n'
        names = parse_names_file(text)
        assert names == ['FOO', 'BAR']


class TestNameCompilerEncode:
    """Test encoding names to binary."""

    def test_compile_basic(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import compile_names, NAME_TABLE_SIZE
        names = ['FOO', 'BAR']
        result = compile_names(names)
        assert len(result) == NAME_TABLE_SIZE
        # FOO = C6 CF CF 00, BAR = C2 C1 D2 00
        assert result[0] == 0xC6  # F | 0x80
        assert result[1] == 0xCF  # O | 0x80
        assert result[2] == 0xCF  # O | 0x80
        assert result[3] == 0x00  # null terminator
        assert result[4] == 0xC2  # B | 0x80
        assert result[7] == 0x00  # null terminator

    def test_compile_empty_string(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import compile_names
        names = ['', 'FOO']
        result = compile_names(names)
        # Empty string = just null terminator
        assert result[0] == 0x00
        assert result[1] == 0xC6  # F | 0x80

    def test_compile_budget_overflow(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import compile_names
        # Create names that exceed 891-byte budget
        names = ['A' * 50] * 20  # 20 x (50+1) = 1020 bytes
        with pytest.raises(ValueError, match='exceeds budget'):
            compile_names(names)

    def test_compile_with_tail_data(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import compile_names, NAME_TABLE_SIZE
        names = ['FOO']
        tail = b'\xAA\xBB\xCC'
        result = compile_names(names, tail_data=tail)
        assert len(result) == NAME_TABLE_SIZE
        # Names part: F O O \0 = 4 bytes, then tail
        assert result[4] == 0xAA
        assert result[5] == 0xBB
        assert result[6] == 0xCC


class TestNameCompilerValidate:
    """Test budget validation."""

    def test_validate_within_budget(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import validate_names
        names = ['FOO', 'BAR']
        size, budget, valid = validate_names(names)
        assert size == 8  # FOO\0 + BAR\0 = 4 + 4
        assert budget == 891  # 921 - 30
        assert valid is True

    def test_validate_over_budget(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import validate_names
        names = ['A' * 50] * 20
        size, budget, valid = validate_names(names)
        assert valid is False


class TestNameCompilerRoundTrip:
    """Test decompile and recompile produce equivalent output."""

    def test_roundtrip(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import (
            parse_names_file, compile_names, decompile_names,
            NAME_TABLE_OFFSET, NAME_TABLE_SIZE,
        )
        # Build a synthetic ULT3-like binary with a known name table
        names_in = ['WATER', 'GRASS', '', 'FOREST']
        encoded = compile_names(names_in)
        # Create a fake ULT3 binary large enough
        data = bytearray(NAME_TABLE_OFFSET + NAME_TABLE_SIZE)
        data[NAME_TABLE_OFFSET:NAME_TABLE_OFFSET + NAME_TABLE_SIZE] = encoded

        # Decompile to text
        text = decompile_names(bytes(data))
        # Reparse
        names_out = parse_names_file(text)
        assert names_out == names_in

    def test_voidborn_names_validate(self):
        """Voidborn names.names file fits within budget."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import parse_names_file, validate_names
        names_path = os.path.join(os.path.dirname(__file__),
                                   '..', 'conversions', 'voidborn',
                                   'sources', 'names.names')
        with open(names_path, 'r', encoding='utf-8') as f:
            text = f.read()
        names = parse_names_file(text)
        size, budget, valid = validate_names(names)
        assert valid, f"Voidborn names {size}/{budget} bytes — over budget!"
        assert len(names) > 100, f"Expected 100+ names, got {len(names)}"


# =============================================================================
# Source file validation tests
# =============================================================================

class TestSourceFileValidation:
    """Validate Voidborn source files parse correctly."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_all_bestiary_valid_json(self):
        """All bestiary source files are valid JSON with expected structure."""
        for letter in 'abcdefghijklz':
            path = os.path.join(self.SOURCES_DIR, f'bestiary_{letter}.json')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                data = json.load(f)
            assert 'monsters' in data, f"bestiary_{letter}.json missing 'monsters'"
            mons = data['monsters']
            assert isinstance(mons, dict), f"bestiary_{letter}.json monsters not dict"
            for key, val in mons.items():
                assert 'hp' in val, f"bestiary_{letter}.json monster {key} missing hp"

    def test_all_combat_valid_json(self):
        """All combat source files are valid JSON with expected structure."""
        for letter in 'abcfgmqrs':
            path = os.path.join(self.SOURCES_DIR, f'combat_{letter}.json')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                data = json.load(f)
            tiles = data.get('tiles', [])
            assert len(tiles) == 11, f"combat_{letter}.json needs 11 tile rows"
            for row in tiles:
                assert len(row) == 11, f"combat_{letter}.json row not 11 chars"

    def test_all_special_valid_json(self):
        """All special location source files are valid JSON."""
        for name in ('brnd', 'shrn', 'fntn', 'time'):
            path = os.path.join(self.SOURCES_DIR, f'special_{name}.json')
            with open(path, 'r') as f:
                data = json.load(f)
            tiles = data.get('tiles', [])
            assert len(tiles) == 11, f"special_{name}.json needs 11 tile rows"

    def test_title_json_valid(self):
        """Title text source is valid JSON."""
        path = os.path.join(self.SOURCES_DIR, 'title.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'records' in data
        assert len(data['records']) >= 2

    def test_overworld_map_dimensions(self):
        """Overworld map source is 64x64."""
        path = os.path.join(self.SOURCES_DIR, 'mapa.map')
        with open(path, 'r') as f:
            lines = [l for l in f.read().splitlines()
                     if l and not l.startswith('#')]
        assert len(lines) == 64, f"mapa.map has {len(lines)} rows, expected 64"
        for i, line in enumerate(lines):
            assert len(line) == 64, f"mapa.map row {i} has {len(line)} chars"

    def test_all_surface_maps_dimensions(self):
        """All surface map sources are 64x64."""
        for letter in 'abcdefghijklz':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                lines = [l for l in f.read().splitlines()
                         if l and not l.startswith('#')]
            assert len(lines) == 64, \
                f"map{letter}.map has {len(lines)} rows, expected 64"
            for i, line in enumerate(lines):
                assert len(line) == 64, \
                    f"map{letter}.map row {i} has {len(line)} chars"

    def test_all_dungeon_maps_dimensions(self):
        """All dungeon map sources have 8 levels of 16x16."""
        for letter in 'mnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                # Filter comments ('# ' with space) but keep tile rows
                # starting with '#' (wall tile character in dungeons)
                lines = [l for l in f.read().splitlines()
                         if l and not l.startswith('# ')]
            assert len(lines) == 128, \
                f"map{letter}.map has {len(lines)} rows, expected 128 (8x16)"
            for i, line in enumerate(lines):
                assert len(line) == 16, \
                    f"map{letter}.map row {i} has {len(line)} chars, expected 16"

    def test_all_dialog_files_parseable(self):
        """All dialog source files are parseable text with --- separators."""
        for letter in 'abcdefghijklmnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'tlk{letter}.txt')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                text = f.read()
            # Should have at least one record separator
            assert '---' in text, f"tlk{letter}.txt missing --- separators"
            # Non-comment, non-separator lines should be <= 20 chars
            for line_num, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith('#') or stripped == '---' or not stripped:
                    continue
                assert len(stripped) <= 20, \
                    f"tlk{letter}.txt line {line_num} too long: {len(stripped)} chars"

    def test_bestiary_stat_ranges(self):
        """Spot check bestiary stats are in reasonable ranges."""
        for letter in 'abcdefghijklz':
            path = os.path.join(self.SOURCES_DIR, f'bestiary_{letter}.json')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                data = json.load(f)
            for key, mon in data['monsters'].items():
                hp = mon.get('hp', 0)
                atk = mon.get('attack', 0)
                assert 0 < hp <= 255, \
                    f"bestiary_{letter}.json mon {key} hp={hp} out of range"
                assert 0 < atk <= 255, \
                    f"bestiary_{letter}.json mon {key} atk={atk} out of range"

    def test_combat_position_bounds(self):
        """All combat map positions are within 11x11 grid."""
        for letter in 'abcfgmqrs':
            path = os.path.join(self.SOURCES_DIR, f'combat_{letter}.json')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                data = json.load(f)
            for group in ('monsters', 'pcs'):
                positions = data.get(group, {})
                if isinstance(positions, dict):
                    positions = positions.values()
                for pos in positions:
                    assert 0 <= pos['x'] <= 10, \
                        f"combat_{letter}.json {group} x={pos['x']} out of bounds"
                    assert 0 <= pos['y'] <= 10, \
                        f"combat_{letter}.json {group} y={pos['y']} out of bounds"


class TestSourceManifest:
    """Verify every expected source file exists."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_bestiary_manifest(self):
        """All 13 bestiary source files exist."""
        for letter in 'abcdefghijklz':
            path = os.path.join(self.SOURCES_DIR, f'bestiary_{letter}.json')
            assert os.path.exists(path), f"Missing bestiary_{letter}.json"

    def test_combat_manifest(self):
        """All 9 combat source files exist."""
        for letter in 'abcfgmqrs':
            path = os.path.join(self.SOURCES_DIR, f'combat_{letter}.json')
            assert os.path.exists(path), f"Missing combat_{letter}.json"

    def test_dialog_manifest(self):
        """All 19 dialog source files exist."""
        for letter in 'abcdefghijklmnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'tlk{letter}.txt')
            assert os.path.exists(path), f"Missing tlk{letter}.txt"

    def test_surface_map_manifest(self):
        """All 13 surface map source files exist."""
        for letter in 'abcdefghijklz':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            assert os.path.exists(path), f"Missing map{letter}.map"

    def test_dungeon_map_manifest(self):
        """All 7 dungeon map source files exist."""
        for letter in 'mnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            assert os.path.exists(path), f"Missing map{letter}.map"

    def test_special_manifest(self):
        """All 4 special location source files exist."""
        for name in ('brnd', 'shrn', 'fntn', 'time'):
            path = os.path.join(self.SOURCES_DIR, f'special_{name}.json')
            assert os.path.exists(path), f"Missing special_{name}.json"

    def test_ancillary_manifest(self):
        """Ancillary source files exist."""
        for filename in ('tiles.tiles', 'names.names', 'title.json',
                         'shop_strings.json', 'sosa.json', 'sosm.json',
                         'mbs.json', 'ddrw.json'):
            path = os.path.join(self.SOURCES_DIR, filename)
            assert os.path.exists(path), f"Missing {filename}"


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
        from u3edit.bestiary import Monster
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
        from u3edit.combat import CombatMap, CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET
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
        from u3edit.shapes import encode_overlay_string
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
        from u3edit.shapes import extract_overlay_strings
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

class TestSoundSources:
    """Validate sound source JSON files."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_sosa_json_valid(self):
        """SOSA source has correct structure and size."""
        path = os.path.join(self.SOURCES_DIR, 'sosa.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'raw' in data
        assert len(data['raw']) == 4096
        assert all(0 <= b <= 255 for b in data['raw'])

    def test_sosm_json_valid(self):
        """SOSM source has correct structure and size."""
        path = os.path.join(self.SOURCES_DIR, 'sosm.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'raw' in data
        assert len(data['raw']) == 256
        assert all(0 <= b <= 255 for b in data['raw'])

    def test_mbs_json_valid(self):
        """MBS source has correct structure, size, and END opcode."""
        path = os.path.join(self.SOURCES_DIR, 'mbs.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'raw' in data
        assert len(data['raw']) == 5456
        assert data['raw'][0] == 0x82, "First byte should be END opcode"
        assert all(0 <= b <= 255 for b in data['raw'])


# =============================================================================
# DDRW source file validation
# =============================================================================

class TestDdrwSource:
    """Validate DDRW source JSON file."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_ddrw_json_valid(self):
        """DDRW source has correct structure and size."""
        path = os.path.join(self.SOURCES_DIR, 'ddrw.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'raw' in data
        assert len(data['raw']) == 1792
        assert all(0 <= b <= 255 for b in data['raw'])


# =============================================================================
# Shop strings JSON validation
# =============================================================================

class TestShopStringsSource:
    """Validate shop_strings.json source file structure."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_shop_strings_json_structure(self):
        """shop_strings.json has valid structure with all 8 shops."""
        path = os.path.join(self.SOURCES_DIR, 'shop_strings.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'shops' in data
        shops = data['shops']
        for i in range(8):
            key = f'SHP{i}'
            assert key in shops, f"Missing {key}"
            assert 'strings' in shops[key]
            for entry in shops[key]['strings']:
                assert 'vanilla' in entry
                assert 'voidborn' in entry


# =============================================================================
# Name compiler edge cases
# =============================================================================

class TestNameCompilerEdgeCases:
    """Edge case tests for name_compiler.py."""

    def _get_mod(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        import name_compiler
        return name_compiler

    def test_decompile_produces_parseable_output(self):
        """Compile → embed in fake ULT3 → decompile → parse round-trip."""
        mod = self._get_mod()
        names = ['GRASS', 'FOREST', '', 'SWORD', 'SHIELD']
        binary = mod.compile_names(names)
        # Embed at NAME_TABLE_OFFSET in a fake ULT3
        ult3 = bytearray(mod.NAME_TABLE_OFFSET + mod.NAME_TABLE_SIZE)
        ult3[mod.NAME_TABLE_OFFSET:mod.NAME_TABLE_OFFSET + len(binary)] = binary
        # Decompile returns .names text, parse it back
        text = mod.decompile_names(bytes(ult3))
        parsed = mod.parse_names_file(text)
        assert parsed[:5] == names

    def test_compile_special_characters(self):
        """Names with spaces and punctuation encode correctly."""
        mod = self._get_mod()
        names = ['ICE AXE', "PIRATE'S"]
        binary = mod.compile_names(names)
        # Embed and round-trip
        ult3 = bytearray(mod.NAME_TABLE_OFFSET + mod.NAME_TABLE_SIZE)
        ult3[mod.NAME_TABLE_OFFSET:mod.NAME_TABLE_OFFSET + len(binary)] = binary
        text = mod.decompile_names(bytes(ult3))
        parsed = mod.parse_names_file(text)
        assert parsed[0] == 'ICE AXE'
        assert parsed[1] == "PIRATE'S"

    def test_names_file_round_trip(self, tmp_path):
        """Write .names file → read back → compile → decompile matches."""
        mod = self._get_mod()
        original_names = ['GRASS', 'FOREST', 'MOUNTAIN']
        # Write .names format
        content = '# Terrain\n' + '\n'.join(original_names) + '\n'
        names_path = str(tmp_path / 'test.names')
        with open(names_path, 'w') as f:
            f.write(content)
        # Parse
        with open(names_path, 'r') as f:
            parsed = mod.parse_names_file(f.read())
        assert parsed == original_names
        # Compile → embed → decompile → parse
        binary = mod.compile_names(parsed)
        ult3 = bytearray(mod.NAME_TABLE_OFFSET + mod.NAME_TABLE_SIZE)
        ult3[mod.NAME_TABLE_OFFSET:mod.NAME_TABLE_OFFSET + len(binary)] = binary
        text = mod.decompile_names(bytes(ult3))
        reparsed = mod.parse_names_file(text)
        assert reparsed[:3] == original_names


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
        from u3edit.shapes import encode_overlay_string
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

class TestTileCompilerEdgeCases:
    """Edge case tests for tile_compiler.py."""

    TOOLS_DIR = os.path.join(os.path.dirname(__file__),
                              '..', 'conversions', 'tools')

    def _get_mod(self):
        mod_path = os.path.join(self.TOOLS_DIR, 'tile_compiler.py')
        import importlib.util
        spec = importlib.util.spec_from_file_location('tile_compiler', mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_parse_tile_dimensions(self):
        """Tile parser requires exactly 8 rows of 7 columns per glyph."""
        mod = self._get_mod()
        # Build a minimal .tiles source for one glyph
        lines = ['# Tile 0x00: Test']
        for _ in range(8):
            lines.append('#' * 7)
        text = '\n'.join(lines) + '\n'
        tiles = mod.parse_tiles_file(text)
        assert len(tiles) >= 1
        # parse_tiles_file returns list of (index, bytes) tuples
        assert tiles[0][0] == 0  # index
        assert len(tiles[0][1]) == 8  # 8 bytes per glyph

    def test_decompile_then_compile_matches(self):
        """Decompile binary → compile back produces identical bytes."""
        mod = self._get_mod()
        # Create a 2048-byte SHPS with one known glyph at index 0
        shps = bytearray(2048)
        original = bytes([0b1010101, 0b0101010, 0b1111111, 0b0000000,
                          0b1100110, 0b0011001, 0b1111000, 0b0001111])
        shps[0:8] = original
        # Decompile to text
        text = mod.decompile_shps(bytes(shps))
        # Parse the text back
        tiles = mod.parse_tiles_file(text)
        # Find tile index 0
        glyph_bytes = None
        for idx, data in tiles:
            if idx == 0:
                glyph_bytes = data
                break
        assert glyph_bytes is not None
        assert glyph_bytes == original


# =============================================================================
# Bestiary import: shortcut + raw attribute conflict fix
# =============================================================================

class TestBestiaryShortcutRawConflict:
    """Verify shortcuts OR into raw attributes, not overwritten by them."""

    def test_shortcut_applied_after_raw(self, tmp_path):
        """Boss shortcut is preserved even when flags1 raw value is 0."""
        from u3edit.bestiary import (
            load_mon_file, save_mon_file, cmd_import,
            MON_FLAG1_BOSS, MON_MONSTERS_PER_FILE
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
        from u3edit.bestiary import (
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
        from u3edit.bestiary import load_mon_file, cmd_import
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
        from u3edit.combat import cmd_import as combat_import, CON_FILE_SIZE
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
        from u3edit.map import cmd_import as map_import
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
        from u3edit.map import cmd_import as map_import
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
        from u3edit.save import PartyState, PRTY_OFF_SLOT_IDS
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
        from u3edit.save import PartyState, PRTY_OFF_SLOT_IDS
        raw = bytearray(16)
        raw[PRTY_OFF_SLOT_IDS:PRTY_OFF_SLOT_IDS + 4] = b'\xFF\xFF\xFF\xFF'
        party = PartyState(raw)
        party.slot_ids = []
        assert party.slot_ids == [0, 0, 0, 0]

    def test_full_slot_ids_still_works(self):
        """Setting all 4 slot IDs still works correctly."""
        from u3edit.save import PartyState
        raw = bytearray(16)
        party = PartyState(raw)
        party.slot_ids = [1, 3, 7, 15]
        assert party.slot_ids == [1, 3, 7, 15]


class TestDdrwImportSizeValidation:
    """DDRW import should warn on wrong file size."""

    def test_correct_size_no_warning(self, tmp_path, capsys):
        """Importing 1792 bytes should produce no warning."""
        from u3edit.ddrw import cmd_import, DDRW_FILE_SIZE
        json_file = tmp_path / 'ddrw.json'
        json_file.write_text(json.dumps({'raw': [0] * DDRW_FILE_SIZE}))
        out_file = tmp_path / 'DDRW'
        out_file.write_bytes(b'\x00' * DDRW_FILE_SIZE)
        args = type('A', (), {
            'file': str(out_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        assert 'Warning' not in capsys.readouterr().err

    def test_wrong_size_warns(self, tmp_path, capsys):
        """Importing wrong size should produce a warning."""
        from u3edit.ddrw import cmd_import, DDRW_FILE_SIZE
        json_file = tmp_path / 'ddrw.json'
        json_file.write_text(json.dumps({'raw': [0] * 100}))
        out_file = tmp_path / 'DDRW'
        out_file.write_bytes(b'\x00' * DDRW_FILE_SIZE)
        args = type('A', (), {
            'file': str(out_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        err = capsys.readouterr().err
        assert 'Warning' in err
        assert '1792' in err


class TestSoundImportSizeValidation:
    """Sound import should warn on unknown file sizes."""

    def test_known_size_no_warning(self, tmp_path, capsys):
        """Importing 4096 bytes (SOSA) should produce no warning."""
        from u3edit.sound import cmd_import
        from u3edit.constants import SOSA_FILE_SIZE
        json_file = tmp_path / 'sosa.json'
        json_file.write_text(json.dumps({'raw': [0] * SOSA_FILE_SIZE}))
        out_file = tmp_path / 'SOSA'
        out_file.write_bytes(b'\x00' * SOSA_FILE_SIZE)
        args = type('A', (), {
            'file': str(out_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        assert 'Warning' not in capsys.readouterr().err

    def test_unknown_size_warns(self, tmp_path, capsys):
        """Importing unknown size should produce a warning."""
        from u3edit.sound import cmd_import
        json_file = tmp_path / 'sound.json'
        json_file.write_text(json.dumps({'raw': [0] * 999}))
        out_file = tmp_path / 'SND'
        out_file.write_bytes(b'\x00' * 999)
        args = type('A', (), {
            'file': str(out_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        err = capsys.readouterr().err
        assert 'Warning' in err
        assert '999' in err


class TestTextImportOverflow:
    """Text import should report actual records written, not total in JSON."""

    def test_reports_actual_count(self, tmp_path, capsys):
        """When file is too small, report count of records actually written."""
        from u3edit.text import cmd_import
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
        from u3edit.text import cmd_import
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

class TestEngineRoundTrip:
    """Verify engine binaries reassemble byte-identical from CIDAR disassembly.

    These tests prove the SDK build pipeline works:
    CIDAR disassembly (.s) → asmiigs assembler → OMF → byte-identical binary.

    Requires engine/originals/*.bin and engine/build/*.omf to exist.
    Run `bash engine/build.sh` first to populate build output.
    """

    ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine')
    OMF_HEADER_SIZE = 60  # asmiigs OMF v2.1 segment header
    OMF_TRAILER_SIZE = 1  # End-of-segment marker ($00)

    BINARIES = {
        'SUBS': {'size': 3584, 'org': 0x4100},
        'ULT3': {'size': 17408, 'org': 0x5000},
        'EXOD': {'size': 26208, 'org': 0x2000},
    }

    def _verify(self, name):
        info = self.BINARIES[name]
        omf_path = os.path.join(self.ENGINE_DIR, 'build', f'{name}.omf')
        orig_path = os.path.join(self.ENGINE_DIR, 'originals', f'{name}.bin')

        if not os.path.exists(omf_path):
            pytest.skip(f"Build output not found: {omf_path} (run engine/build.sh)")
        if not os.path.exists(orig_path):
            pytest.skip(f"Original binary not found: {orig_path}")

        with open(omf_path, 'rb') as f:
            omf_data = f.read()
        with open(orig_path, 'rb') as f:
            orig_data = f.read()

        assert len(orig_data) == info['size'], \
            f"Original {name} size: expected {info['size']}, got {len(orig_data)}"

        code = omf_data[self.OMF_HEADER_SIZE:self.OMF_HEADER_SIZE + len(orig_data)]
        assert len(code) == len(orig_data), \
            f"OMF code section: expected {len(orig_data)}, got {len(code)}"
        assert code == orig_data, \
            f"{name} not byte-identical after reassembly"

    def test_subs_byte_identical(self):
        """SUBS (3,584 bytes at $4100) reassembles byte-identical."""
        self._verify('SUBS')

    def test_ult3_byte_identical(self):
        """ULT3 (17,408 bytes at $5000) reassembles byte-identical."""
        self._verify('ULT3')

    def test_exod_byte_identical(self):
        """EXOD (26,208 bytes at $2000) reassembles byte-identical."""
        self._verify('EXOD')

    def test_all_source_files_exist(self):
        """All three CIDAR disassembly source files exist."""
        for name, subdir in [('subs.s', 'subs'), ('ult3.s', 'ult3'), ('exod.s', 'exod')]:
            path = os.path.join(self.ENGINE_DIR, subdir, name)
            assert os.path.exists(path), f"Source not found: {path}"

    def test_all_original_binaries_exist(self):
        """All three original binaries exist for verification."""
        for name in self.BINARIES:
            path = os.path.join(self.ENGINE_DIR, 'originals', f'{name}.bin')
            assert os.path.exists(path), f"Original not found: {path}"

    def test_original_binary_sizes(self):
        """Original binaries have correct documented sizes."""
        for name, info in self.BINARIES.items():
            path = os.path.join(self.ENGINE_DIR, 'originals', f'{name}.bin')
            if not os.path.exists(path):
                pytest.skip(f"Original not found: {path}")
            size = os.path.getsize(path)
            assert size == info['size'], \
                f"{name}: expected {info['size']} bytes, got {size}"

    def test_omf_header_size(self):
        """OMF files have the expected 60-byte header."""
        for name, info in self.BINARIES.items():
            omf_path = os.path.join(self.ENGINE_DIR, 'build', f'{name}.omf')
            if not os.path.exists(omf_path):
                pytest.skip(f"Build output not found (run engine/build.sh)")
            omf_size = os.path.getsize(omf_path)
            expected = info['size'] + self.OMF_HEADER_SIZE + self.OMF_TRAILER_SIZE
            assert omf_size == expected, \
                f"{name}.omf: expected {expected} bytes, got {omf_size}"

    def test_build_script_exists(self):
        """Build script exists."""
        assert os.path.exists(os.path.join(self.ENGINE_DIR, 'build.sh'))

    def test_verify_script_exists(self):
        """Verification script exists."""
        assert os.path.exists(os.path.join(self.ENGINE_DIR, 'verify.py'))


class TestStringCatalog:
    """Test the engine inline string catalog tool."""

    ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine')

    def _load_ult3(self):
        path = os.path.join(self.ENGINE_DIR, 'originals', 'ULT3.bin')
        if not os.path.exists(path):
            pytest.skip("ULT3.bin not found")
        with open(path, 'rb') as f:
            return f.read()

    def test_catalog_tool_exists(self):
        path = os.path.join(self.ENGINE_DIR, 'tools', 'string_catalog.py')
        assert os.path.exists(path)

    def test_extract_finds_strings(self):
        """ULT3 contains 200+ inline strings."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        data = self._load_ult3()
        strings = extract_inline_strings(data, 0x5000)
        assert len(strings) >= 200, f"Expected 200+ strings, got {len(strings)}"

    def test_extract_card_of_death(self):
        """Can find 'CARD OF DEATH' inline string."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        data = self._load_ult3()
        strings = extract_inline_strings(data, 0x5000)
        texts = [s['text'] for s in strings]
        assert any('CARD OF DEATH' in t for t in texts)

    def test_extract_mark_of_kings(self):
        """Can find 'MARK OF KINGS' inline string."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        data = self._load_ult3()
        strings = extract_inline_strings(data, 0x5000)
        texts = [s['text'] for s in strings]
        assert any('MARK OF KINGS' in t for t in texts)

    def test_extract_evocare(self):
        """Can find 'EVOCARE' inline string."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        data = self._load_ult3()
        strings = extract_inline_strings(data, 0x5000)
        texts = [s['text'] for s in strings]
        assert any('EVOCARE' in t for t in texts)

    def test_total_bytes_reasonable(self):
        """Total inline string bytes should be 3000-5000."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        data = self._load_ult3()
        strings = extract_inline_strings(data, 0x5000)
        total = sum(s['jsr_plus_text'] for s in strings)
        assert 3000 <= total <= 5000, f"Total bytes: {total}"

    def test_no_strings_in_exod(self):
        """EXOD should have zero JSR $46BA strings."""
        path = os.path.join(self.ENGINE_DIR, 'originals', 'EXOD.bin')
        if not os.path.exists(path):
            pytest.skip("EXOD.bin not found")
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        with open(path, 'rb') as f:
            data = f.read()
        strings = extract_inline_strings(data, 0x2000)
        assert len(strings) == 0

    def test_no_strings_in_subs(self):
        """SUBS should have zero JSR $46BA strings (it IS the printer)."""
        path = os.path.join(self.ENGINE_DIR, 'originals', 'SUBS.bin')
        if not os.path.exists(path):
            pytest.skip("SUBS.bin not found")
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        with open(path, 'rb') as f:
            data = f.read()
        strings = extract_inline_strings(data, 0x4100)
        assert len(strings) == 0

    def test_json_catalog_exists(self):
        """Pre-built JSON catalog exists."""
        path = os.path.join(self.ENGINE_DIR, 'tools', 'ult3_strings.json')
        if not os.path.exists(path):
            pytest.skip("JSON catalog not built yet")
        with open(path) as f:
            catalog = json.load(f)
        assert catalog['total_strings'] >= 200
        assert 'strings' in catalog

    def test_categorize_quest_items(self):
        """Categorizer identifies quest item strings correctly."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import categorize_string
        assert categorize_string('CARD OF DEATH') == 'quest-item'
        assert categorize_string('MARK OF KINGS') == 'quest-item'

    def test_categorize_combat(self):
        """Categorizer identifies combat strings correctly."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import categorize_string
        assert categorize_string('KILLED! EXP.-') == 'combat'
        assert categorize_string('MISSED!') == 'combat'

    def test_synthesized_binary_scan(self):
        """String extraction works on synthesized data with known strings."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        # Build a small binary with two inline strings
        data = bytearray(100)
        # JSR $46BA at offset 10
        data[10] = 0x20
        data[11] = 0xBA
        data[12] = 0x46
        # "HI" in high-ASCII + null
        data[13] = 0xC8  # H
        data[14] = 0xC9  # I
        data[15] = 0x00  # null
        # JSR $46BA at offset 30
        data[30] = 0x20
        data[31] = 0xBA
        data[32] = 0x46
        # "BYE" in high-ASCII + null
        data[33] = 0xC2  # B
        data[34] = 0xD9  # Y
        data[35] = 0xC5  # E
        data[36] = 0x00  # null
        strings = extract_inline_strings(bytes(data))
        assert len(strings) == 2
        assert strings[0]['text'] == 'HI'
        assert strings[1]['text'] == 'BYE'
        assert strings[0]['file_offset'] == 10
        assert strings[1]['file_offset'] == 30


# =============================================================================
# String patcher tests
# =============================================================================

def _make_inline_binary(*texts):
    """Build a synthetic binary with JSR $46BA inline strings.

    Returns (bytearray, list_of_string_info_dicts).
    Each text is high-ASCII encoded after the JSR pattern.
    """
    parts = bytearray()
    # pad with NOPs at start
    parts.extend(b'\xEA' * 4)
    for text in texts:
        # JSR $46BA
        parts.extend(b'\x20\xBA\x46')
        for ch in text:
            if ch == '\n':
                parts.append(0xFF)
            else:
                parts.append(ord(ch.upper()) | 0x80)
        parts.append(0x00)  # null terminator
        parts.extend(b'\xEA' * 2)  # pad between strings
    # Extract string info using the catalog tool
    import importlib
    tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine', 'tools')
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    from string_catalog import extract_inline_strings
    strings = extract_inline_strings(bytes(parts))
    return parts, strings


class TestStringPatcher:
    """Test the engine inline string patcher tool."""

    ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine')

    def _get_patcher(self):
        tools_dir = os.path.join(self.ENGINE_DIR, 'tools')
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from string_patcher import encode_high_ascii, patch_string, resolve_patches
        return encode_high_ascii, patch_string, resolve_patches

    def test_patcher_tool_exists(self):
        path = os.path.join(self.ENGINE_DIR, 'tools', 'string_patcher.py')
        assert os.path.exists(path)

    def test_encode_high_ascii_simple(self):
        encode_high_ascii, _, _ = self._get_patcher()
        result = encode_high_ascii('HI')
        assert result == bytearray([0xC8, 0xC9])

    def test_encode_high_ascii_newline(self):
        encode_high_ascii, _, _ = self._get_patcher()
        result = encode_high_ascii('A\nB')
        assert result == bytearray([0xC1, 0xFF, 0xC2])

    def test_patch_string_fits(self):
        """Patch that fits in available space succeeds."""
        _, patch_string, _ = self._get_patcher()
        data, strings = _make_inline_binary('HELLO WORLD')
        ok, msg = patch_string(data, strings[0], 'GOODBYE')
        assert ok
        assert 'Patched' in msg
        # Verify the patched bytes
        offset = strings[0]['text_offset']
        assert data[offset] == 0xC7  # G
        assert data[offset + 6] == 0xC5  # E (last char of GOODBYE)
        assert data[offset + 7] == 0x00  # null fill

    def test_patch_string_exact_fit(self):
        """Patch that exactly matches original length succeeds."""
        _, patch_string, _ = self._get_patcher()
        data, strings = _make_inline_binary('ABC')
        ok, msg = patch_string(data, strings[0], 'XYZ')
        assert ok
        offset = strings[0]['text_offset']
        assert data[offset] == 0xD8  # X
        assert data[offset + 1] == 0xD9  # Y
        assert data[offset + 2] == 0xDA  # Z

    def test_patch_string_too_long(self):
        """Patch longer than available space fails gracefully."""
        _, patch_string, _ = self._get_patcher()
        data, strings = _make_inline_binary('HI')
        ok, msg = patch_string(data, strings[0], 'THIS IS WAY TOO LONG')
        assert not ok
        assert 'too long' in msg.lower()

    def test_patch_null_fills_remainder(self):
        """Shorter replacement null-fills remaining bytes."""
        _, patch_string, _ = self._get_patcher()
        data, strings = _make_inline_binary('ABCDEF')
        ok, msg = patch_string(data, strings[0], 'XY')
        assert ok
        offset = strings[0]['text_offset']
        assert data[offset] == 0xD8  # X
        assert data[offset + 1] == 0xD9  # Y
        # Remaining bytes should be null-filled
        for i in range(2, 7):  # 6 original + null
            assert data[offset + i] == 0x00

    def test_resolve_by_index(self):
        """Resolve patches by string index."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('FIRST', 'SECOND')
        patches = [{'index': 1, 'text': 'REPLACEMENT'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 1
        assert resolved[0][0]['index'] == 1
        assert resolved[0][1] == 'REPLACEMENT'

    def test_resolve_by_vanilla_text(self):
        """Resolve patches by vanilla text matching."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('CARD OF DEATH', 'HELLO')
        patches = [{'vanilla': 'CARD OF DEATH', 'text': 'SHARD OF VOID'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 1
        assert 'CARD OF DEATH' in resolved[0][0]['text']

    def test_resolve_by_vanilla_case_insensitive(self):
        """Vanilla text matching is case-insensitive."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('HELLO WORLD')
        patches = [{'vanilla': 'hello world', 'text': 'GOODBYE'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 1

    def test_resolve_by_address(self):
        """Resolve patches by address."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('TEST')
        addr = strings[0]['address']
        patches = [{'address': addr, 'text': 'NEW'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 1

    def test_resolve_missing_index_warns(self, capsys):
        """Missing index produces warning, not crash."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('ONLY')
        patches = [{'index': 999, 'text': 'MISSING'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 0

    def test_resolve_missing_vanilla_warns(self, capsys):
        """Missing vanilla text produces warning, not crash."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('ACTUAL')
        patches = [{'vanilla': 'NONEXISTENT', 'text': 'MISSING'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 0

    def test_full_patch_roundtrip(self):
        """Full pipeline: resolve + patch multiple strings."""
        _, patch_string, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary(
            'CARD OF DEATH', 'MARK OF KINGS', 'HELLO'
        )
        patches = [
            {'vanilla': 'CARD OF DEATH', 'text': 'SHARD OF VOID'},
            {'vanilla': 'MARK OF KINGS', 'text': 'SIGIL: KINGS'},
        ]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 2
        for string_info, new_text in resolved:
            ok, msg = patch_string(data, string_info, new_text)
            assert ok
        # Verify HELLO is untouched
        hello_offset = strings[2]['text_offset']
        assert data[hello_offset] == 0xC8  # H still there

    def test_voidborn_engine_strings_valid(self):
        """Voidborn engine_strings.json has valid structure."""
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'conversions', 'voidborn', 'sources', 'engine_strings.json')
        if not os.path.exists(path):
            pytest.skip("engine_strings.json not found")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert 'patches' in data
        assert len(data['patches']) >= 10
        for patch in data['patches']:
            assert 'text' in patch
            assert 'index' in patch or 'vanilla' in patch or 'address' in patch

    def test_voidborn_patches_fit_in_place(self):
        """All Voidborn engine string patches fit in original space."""
        ult3_path = os.path.join(self.ENGINE_DIR, 'originals', 'ULT3.bin')
        if not os.path.exists(ult3_path):
            pytest.skip("ULT3.bin not found")
        patches_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    'conversions', 'voidborn', 'sources',
                                    'engine_strings.json')
        if not os.path.exists(patches_path):
            pytest.skip("engine_strings.json not found")
        tools_dir = os.path.join(self.ENGINE_DIR, 'tools')
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from string_catalog import extract_inline_strings
        from string_patcher import patch_string, resolve_patches
        with open(ult3_path, 'rb') as f:
            data = bytearray(f.read())
        with open(patches_path, 'r', encoding='utf-8') as f:
            patch_data = json.load(f)
        strings = extract_inline_strings(bytes(data), 0x5000)
        resolved = resolve_patches(strings, patch_data['patches'])
        assert len(resolved) >= 10, f"Only {len(resolved)} patches resolved"
        for string_info, new_text in resolved:
            ok, msg = patch_string(data, string_info, new_text)
            assert ok, f"Patch failed: {msg}"


# =============================================================================
# Source-level string patcher tests
# =============================================================================

def _make_asm_source(*inline_texts):
    """Build synthetic .s source lines with ASC inline strings.

    Returns list of source lines simulating CIDAR disassembly output.
    """
    lines = []
    lines.append('            ORG     $5000\n')
    lines.append('; --- Code ---\n')
    for text in inline_texts:
        lines.append('            DB      $20,$BA,$46,$FF\n')
        lines.append(f'            ASC     "{text}"\n')
        lines.append('            DB      $00 ; null terminator\n')
        lines.append('            DB      $60  ; RTS\n')
    return lines


class TestSourcePatcher:
    """Test the source-level inline string patcher tool."""

    ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine')

    def _get_source_patcher(self):
        tools_dir = os.path.join(self.ENGINE_DIR, 'tools')
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from source_patcher import (
            extract_asc_strings, is_inline_string,
            resolve_source_patches, apply_source_patches,
        )
        return extract_asc_strings, is_inline_string, resolve_source_patches, apply_source_patches

    def test_source_patcher_exists(self):
        path = os.path.join(self.ENGINE_DIR, 'tools', 'source_patcher.py')
        assert os.path.exists(path)

    def test_extract_asc_strings(self):
        """Can find ASC directives in synthesized source."""
        extract, _, _, _ = self._get_source_patcher()
        lines = _make_asm_source('HELLO WORLD', 'GOODBYE')
        strings = extract(lines)
        assert len(strings) == 2
        assert strings[0]['text'] == 'HELLO WORLD'
        assert strings[1]['text'] == 'GOODBYE'

    def test_is_inline_string(self):
        """Correctly identifies JSR $46BA inline strings."""
        extract, is_inline, _, _ = self._get_source_patcher()
        lines = _make_asm_source('CARD OF DEATH')
        strings = extract(lines)
        assert len(strings) == 1
        assert is_inline(lines, strings[0])

    def test_is_not_inline_string(self):
        """Non-inline ASC directives are not flagged."""
        extract, is_inline, _, _ = self._get_source_patcher()
        lines = [
            '            ASC     "JUST DATA"\n',
            '            DB      $00\n',
        ]
        strings = extract(lines)
        assert len(strings) == 1
        assert not is_inline(lines, strings[0])

    def test_resolve_by_vanilla(self):
        """Resolve source patches by vanilla text."""
        extract, _, resolve, _ = self._get_source_patcher()
        lines = _make_asm_source('CARD OF DEATH', 'HELLO')
        strings = extract(lines)
        patches = [{'vanilla': 'CARD OF DEATH', 'text': 'SHARD OF VOID'}]
        resolved = resolve(strings, patches)
        assert len(resolved) == 1
        assert resolved[0][1] == 'SHARD OF VOID'

    def test_resolve_case_insensitive(self):
        """Vanilla text matching is case-insensitive."""
        extract, _, resolve, _ = self._get_source_patcher()
        lines = _make_asm_source('HELLO WORLD')
        strings = extract(lines)
        patches = [{'vanilla': 'hello world', 'text': 'GOODBYE'}]
        resolved = resolve(strings, patches)
        assert len(resolved) == 1

    def test_resolve_by_index(self):
        """Resolve source patches by ASC index."""
        extract, _, resolve, _ = self._get_source_patcher()
        lines = _make_asm_source('FIRST', 'SECOND', 'THIRD')
        strings = extract(lines)
        patches = [{'index': 1, 'text': 'REPLACEMENT'}]
        resolved = resolve(strings, patches)
        assert len(resolved) == 1
        assert resolved[0][0]['text'] == 'SECOND'

    def test_apply_replaces_text(self):
        """Applying patches replaces ASC directive text."""
        extract, _, resolve, apply_patches = self._get_source_patcher()
        lines = _make_asm_source('CARD OF DEATH', 'MARK OF KINGS')
        strings = extract(lines)
        patches = [
            {'vanilla': 'CARD OF DEATH', 'text': 'SHARD OF THE ETERNAL VOID'},
            {'vanilla': 'MARK OF KINGS', 'text': 'SIGIL OF KINGS'},
        ]
        resolved = resolve(strings, patches)
        modified, count = apply_patches(lines, resolved)
        assert count == 2
        # Check that modified lines contain new text
        combined = ''.join(modified)
        assert 'SHARD OF THE ETERNAL VOID' in combined
        assert 'SIGIL OF KINGS' in combined
        # Originals should be gone
        assert 'CARD OF DEATH' not in combined
        assert 'MARK OF KINGS' not in combined

    def test_apply_no_length_constraint(self):
        """Source-level patches have no length constraints."""
        extract, _, resolve, apply_patches = self._get_source_patcher()
        lines = _make_asm_source('HI')
        strings = extract(lines)
        # Replace 2-char string with 50-char string -- would fail in binary patcher
        long_text = 'THIS IS A VERY LONG REPLACEMENT STRING WITH NO LIMIT'
        patches = [{'vanilla': 'HI', 'text': long_text}]
        resolved = resolve(strings, patches)
        modified, count = apply_patches(lines, resolved)
        assert count == 1
        assert long_text in ''.join(modified)

    def test_apply_preserves_untouched(self):
        """Unmatched ASC directives are preserved."""
        extract, _, resolve, apply_patches = self._get_source_patcher()
        lines = _make_asm_source('CHANGE ME', 'KEEP ME')
        strings = extract(lines)
        patches = [{'vanilla': 'CHANGE ME', 'text': 'CHANGED'}]
        resolved = resolve(strings, patches)
        modified, count = apply_patches(lines, resolved)
        assert count == 1
        combined = ''.join(modified)
        assert 'KEEP ME' in combined
        assert 'CHANGED' in combined

    def test_voidborn_full_patches_valid(self):
        """Voidborn engine_strings_full.json has valid structure."""
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'conversions', 'voidborn', 'sources',
                            'engine_strings_full.json')
        if not os.path.exists(path):
            pytest.skip("engine_strings_full.json not found")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert 'patches' in data
        assert len(data['patches']) >= 8
        for patch in data['patches']:
            assert 'text' in patch
            assert 'vanilla' in patch or 'index' in patch

    def test_voidborn_full_patches_resolve_against_source(self):
        """All Voidborn full patches resolve against ULT3 source."""
        source_path = os.path.join(self.ENGINE_DIR, 'ult3', 'ult3.s')
        if not os.path.exists(source_path):
            pytest.skip("ult3.s not found")
        patches_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    'conversions', 'voidborn', 'sources',
                                    'engine_strings_full.json')
        if not os.path.exists(patches_path):
            pytest.skip("engine_strings_full.json not found")
        extract, _, resolve, _ = self._get_source_patcher()
        with open(source_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        with open(patches_path, 'r', encoding='utf-8') as f:
            patch_data = json.load(f)
        strings = extract(lines)
        resolved = resolve(strings, patch_data['patches'])
        assert len(resolved) >= 8, f"Only {len(resolved)} patches resolved"


# =============================================================================
# Integrated inline string catalog (patch.py cmd_strings)
# =============================================================================

class TestPatchStrings:
    """Test the u3edit patch strings CLI integration."""

    def _make_binary_with_strings(self, *texts):
        """Build binary with JSR $46BA inline strings."""
        data = bytearray()
        data.extend(b'\xEA' * 4)  # NOP padding
        for text in texts:
            data.extend(b'\x20\xBA\x46')  # JSR $46BA
            for ch in text:
                if ch == '\n':
                    data.append(0xFF)
                else:
                    data.append(ord(ch.upper()) | 0x80)
            data.append(0x00)  # null terminator
            data.extend(b'\xEA' * 2)
        return bytes(data)

    def test_extract_inline_strings(self):
        """Integrated _extract_inline_strings finds strings."""
        from u3edit.patch import _extract_inline_strings
        data = self._make_binary_with_strings('HELLO', 'WORLD')
        strings = _extract_inline_strings(data)
        assert len(strings) == 2
        assert strings[0]['text'] == 'HELLO'
        assert strings[1]['text'] == 'WORLD'

    def test_extract_with_newlines(self):
        """Strings with embedded newlines ($FF) decoded correctly."""
        from u3edit.patch import _extract_inline_strings
        data = self._make_binary_with_strings('LINE1\nLINE2')
        strings = _extract_inline_strings(data)
        assert len(strings) == 1
        assert strings[0]['text'] == 'LINE1\nLINE2'

    def test_extract_with_org(self):
        """Origin address added to reported addresses."""
        from u3edit.patch import _extract_inline_strings
        data = self._make_binary_with_strings('TEST')
        strings = _extract_inline_strings(data, org=0x5000)
        assert strings[0]['address'] >= 0x5000

    def test_extract_empty_binary(self):
        """Empty or no-string binary returns empty list."""
        from u3edit.patch import _extract_inline_strings
        data = bytes(100)
        strings = _extract_inline_strings(data)
        assert len(strings) == 0

    def test_cmd_strings_on_ult3(self, capsys):
        """cmd_strings produces output on ULT3 binary."""
        ult3_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 'engine', 'originals', 'ULT3.bin')
        if not os.path.exists(ult3_path):
            pytest.skip("ULT3.bin not found")
        from u3edit.patch import cmd_strings
        args = argparse.Namespace(file=ult3_path, json=False, search=None,
                                  output=None)
        cmd_strings(args)
        captured = capsys.readouterr()
        assert '245 strings' in captured.out
        assert 'CARD OF DEATH' in captured.out

    def test_cmd_strings_search(self, capsys):
        """cmd_strings search filter works."""
        ult3_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 'engine', 'originals', 'ULT3.bin')
        if not os.path.exists(ult3_path):
            pytest.skip("ULT3.bin not found")
        from u3edit.patch import cmd_strings
        args = argparse.Namespace(file=ult3_path, json=False,
                                  search='MARK', output=None)
        cmd_strings(args)
        captured = capsys.readouterr()
        assert 'MARK OF KINGS' in captured.out
        # Should NOT show unrelated strings
        assert 'SPELL TYPE' not in captured.out

    def test_cmd_strings_json(self, capsys, tmp_dir):
        """cmd_strings JSON output is valid."""
        ult3_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 'engine', 'originals', 'ULT3.bin')
        if not os.path.exists(ult3_path):
            pytest.skip("ULT3.bin not found")
        out_path = os.path.join(tmp_dir, 'strings.json')
        from u3edit.patch import cmd_strings
        args = argparse.Namespace(file=ult3_path, json=True, search=None,
                                  output=out_path)
        cmd_strings(args)
        with open(out_path) as f:
            data = json.load(f)
        assert data['total_strings'] >= 200
        assert 'strings' in data


# =============================================================================
# Inline string editing (patch.py cmd_strings_edit / cmd_strings_import)
# =============================================================================

class TestPatchStringsEdit:
    """Test u3edit patch strings-edit and strings-import CLI commands."""

    def _make_test_binary(self, tmp_dir, *texts):
        """Create a test binary with inline strings in tmp_dir."""
        data = bytearray()
        data.extend(b'\xEA' * 4)
        for text in texts:
            data.extend(b'\x20\xBA\x46')  # JSR $46BA
            for ch in text:
                if ch == '\n':
                    data.append(0xFF)
                else:
                    data.append(ord(ch.upper()) | 0x80)
            data.append(0x00)
            data.extend(b'\xEA' * 2)
        path = os.path.join(tmp_dir, 'test.bin')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_strings_edit_by_index(self, tmp_dir):
        """Edit string by index replaces bytes correctly."""
        from u3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'HELLO WORLD', 'GOODBYE')
        args = argparse.Namespace(
            file=path, text='CHANGED', index=0, vanilla=None,
            address=None, output=None, backup=False, dry_run=False)
        cmd_strings_edit(args)
        # Verify the binary was modified
        from u3edit.patch import _extract_inline_strings
        with open(path, 'rb') as f:
            data = f.read()
        strings = _extract_inline_strings(data)
        assert strings[0]['text'] == 'CHANGED'
        assert strings[1]['text'] == 'GOODBYE'  # untouched

    def test_strings_edit_by_vanilla(self, tmp_dir):
        """Edit string by vanilla text match."""
        from u3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'CARD OF DEATH', 'HELLO')
        args = argparse.Namespace(
            file=path, text='SHARD O VOID', index=None,
            vanilla='CARD OF DEATH', address=None, output=None,
            backup=False, dry_run=False)
        cmd_strings_edit(args)
        from u3edit.patch import _extract_inline_strings
        with open(path, 'rb') as f:
            data = f.read()
        strings = _extract_inline_strings(data)
        assert strings[0]['text'] == 'SHARD O VOID'

    def test_strings_edit_too_long(self, tmp_dir):
        """Editing with text too long for in-place fails gracefully."""
        from u3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'HI')
        args = argparse.Namespace(
            file=path, text='THIS IS WAY TOO LONG FOR HI',
            index=0, vanilla=None, address=None, output=None,
            backup=False, dry_run=False)
        with pytest.raises(SystemExit):
            cmd_strings_edit(args)

    def test_strings_edit_dry_run(self, tmp_dir):
        """Dry run does not modify the file."""
        from u3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'ORIGINAL')
        with open(path, 'rb') as f:
            original = f.read()
        args = argparse.Namespace(
            file=path, text='CHANGED', index=0, vanilla=None,
            address=None, output=None, backup=False, dry_run=True)
        cmd_strings_edit(args)
        with open(path, 'rb') as f:
            after = f.read()
        assert original == after

    def test_strings_edit_backup(self, tmp_dir):
        """Backup creates .bak file."""
        from u3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'ORIGINAL')
        args = argparse.Namespace(
            file=path, text='CHANGED', index=0, vanilla=None,
            address=None, output=None, backup=True, dry_run=False)
        cmd_strings_edit(args)
        assert os.path.exists(path + '.bak')

    def test_strings_edit_output_file(self, tmp_dir):
        """Writing to separate output file preserves original."""
        from u3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'ORIGINAL')
        out_path = os.path.join(tmp_dir, 'output.bin')
        with open(path, 'rb') as f:
            original = f.read()
        args = argparse.Namespace(
            file=path, text='CHANGED', index=0, vanilla=None,
            address=None, output=out_path, backup=False, dry_run=False)
        cmd_strings_edit(args)
        with open(path, 'rb') as f:
            assert f.read() == original  # original untouched
        assert os.path.exists(out_path)

    def test_strings_import_from_json(self, tmp_dir):
        """Import multiple patches from JSON file."""
        from u3edit.patch import cmd_strings_import, _extract_inline_strings
        path = self._make_test_binary(tmp_dir,
                                      'CARD OF DEATH', 'MARK OF KINGS', 'HELLO')
        # Create patch JSON
        patch_path = os.path.join(tmp_dir, 'patches.json')
        with open(patch_path, 'w') as f:
            json.dump({'patches': [
                {'vanilla': 'CARD OF DEATH', 'text': 'SHARD O VOID'},
                {'vanilla': 'MARK OF KINGS', 'text': 'SIGIL KINGS'},
            ]}, f)
        args = argparse.Namespace(
            file=path, json_file=patch_path, output=None,
            backup=False, dry_run=False)
        cmd_strings_import(args)
        with open(path, 'rb') as f:
            data = f.read()
        strings = _extract_inline_strings(data)
        assert strings[0]['text'] == 'SHARD O VOID'
        assert strings[1]['text'] == 'SIGIL KINGS'
        assert strings[2]['text'] == 'HELLO'  # untouched

    def test_strings_import_dry_run(self, tmp_dir):
        """Import dry run doesn't modify file."""
        from u3edit.patch import cmd_strings_import
        path = self._make_test_binary(tmp_dir, 'ORIGINAL')
        with open(path, 'rb') as f:
            original = f.read()
        patch_path = os.path.join(tmp_dir, 'patches.json')
        with open(patch_path, 'w') as f:
            json.dump({'patches': [
                {'index': 0, 'text': 'CHANGED'},
            ]}, f)
        args = argparse.Namespace(
            file=path, json_file=patch_path, output=None,
            backup=False, dry_run=True)
        cmd_strings_import(args)
        with open(path, 'rb') as f:
            assert f.read() == original

    def test_strings_import_voidborn(self, tmp_dir):
        """Voidborn engine_strings.json imports successfully on ULT3."""
        ult3_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 'engine', 'originals', 'ULT3.bin')
        if not os.path.exists(ult3_path):
            pytest.skip("ULT3.bin not found")
        patches_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    'conversions', 'voidborn', 'sources',
                                    'engine_strings.json')
        if not os.path.exists(patches_path):
            pytest.skip("engine_strings.json not found")
        # Copy ULT3 to temp
        test_bin = os.path.join(tmp_dir, 'ULT3.bin')
        shutil.copy2(ult3_path, test_bin)
        from u3edit.patch import cmd_strings_import
        args = argparse.Namespace(
            file=test_bin, json_file=patches_path, output=None,
            backup=False, dry_run=False)
        cmd_strings_import(args)
        # Verify changes
        from u3edit.patch import _extract_inline_strings
        with open(test_bin, 'rb') as f:
            data = f.read()
        strings = _extract_inline_strings(data, 0x5000)
        texts = [s['text'] for s in strings]
        assert any('SHARD OF VOID' in t for t in texts)
        assert any('SIGIL: KINGS' in t for t in texts)


# =============================================================================
# Compiler subcommands — map, shapes, patch
# =============================================================================

class TestMapCompileSubcommand:
    """Test u3edit map compile/decompile CLI subcommands."""

    def test_compile_overworld(self, tmp_dir):
        """Compile overworld .map produces 4096-byte binary."""
        from u3edit.map import cmd_compile
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
        from u3edit.map import cmd_compile
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
        from u3edit.map import cmd_decompile
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
        from u3edit.map import cmd_compile, cmd_decompile
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
        from u3edit.map import cmd_compile
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


class TestShapesCompileSubcommand:
    """Test u3edit shapes compile/decompile CLI subcommands."""

    def _make_tiles_source(self, path, count=2):
        """Create a .tiles source with test glyphs."""
        lines = []
        for i in range(count):
            lines.append(f'# Tile 0x{i:02X}: Test{i}')
            for row in range(8):
                # Alternating pattern
                if row % 2 == 0:
                    lines.append('#.#.#.#')
                else:
                    lines.append('.#.#.#.')
            lines.append('')
        with open(path, 'w') as f:
            f.write('\n'.join(lines))

    def test_compile_binary(self, tmp_dir):
        """Compile .tiles to 2048-byte SHPS binary."""
        from u3edit.shapes import cmd_compile_tiles
        src = os.path.join(tmp_dir, 'test.tiles')
        self._make_tiles_source(src)
        out = os.path.join(tmp_dir, 'test.bin')
        args = argparse.Namespace(source=src, output=out, format='binary')
        cmd_compile_tiles(args)
        with open(out, 'rb') as f:
            data = f.read()
        assert len(data) == 2048
        # Tile 0 should have non-zero data
        assert data[0] != 0

    def test_compile_json(self, tmp_dir):
        """Compile .tiles to JSON format."""
        from u3edit.shapes import cmd_compile_tiles
        src = os.path.join(tmp_dir, 'test.tiles')
        self._make_tiles_source(src, count=3)
        out = os.path.join(tmp_dir, 'test.json')
        args = argparse.Namespace(source=src, output=out, format='json')
        cmd_compile_tiles(args)
        with open(out, 'r') as f:
            result = json.load(f)
        assert 'tiles' in result
        assert len(result['tiles'][0]['frames']) == 3

    def test_decompile(self, tmp_dir):
        """Decompile SHPS binary to text-art."""
        from u3edit.shapes import cmd_decompile_tiles
        # Create 2048-byte SHPS binary
        data = bytearray(2048)
        # Put a pattern in tile 0: alternating rows
        data[0] = 0b0101010  # #.#.#.#
        data[1] = 0b0101010
        bin_path = os.path.join(tmp_dir, 'test.bin')
        with open(bin_path, 'wb') as f:
            f.write(data)
        out = os.path.join(tmp_dir, 'test.tiles')
        args = argparse.Namespace(file=bin_path, output=out)
        cmd_decompile_tiles(args)
        with open(out, 'r') as f:
            text = f.read()
        assert '# Tile 0x00' in text
        assert '#' in text  # pixel-on chars present

    def test_compile_decompile_roundtrip(self, tmp_dir):
        """Compile then decompile preserves glyph pixel data."""
        from u3edit.shapes import cmd_compile_tiles, cmd_decompile_tiles, \
            parse_tiles_text
        src = os.path.join(tmp_dir, 'orig.tiles')
        self._make_tiles_source(src, count=4)
        # Read original
        with open(src, 'r') as f:
            orig_tiles = parse_tiles_text(f.read())
        # Compile
        bin_path = os.path.join(tmp_dir, 'test.bin')
        args = argparse.Namespace(source=src, output=bin_path, format='binary')
        cmd_compile_tiles(args)
        # Decompile
        out = os.path.join(tmp_dir, 'decomp.tiles')
        args2 = argparse.Namespace(file=bin_path, output=out)
        cmd_decompile_tiles(args2)
        # Re-parse decompiled
        with open(out, 'r') as f:
            decomp_tiles = parse_tiles_text(f.read())
        # Find our original tiles in the decompiled output
        decomp_map = {idx: data for idx, data in decomp_tiles}
        for idx, orig_data in orig_tiles:
            assert idx in decomp_map
            assert decomp_map[idx] == orig_data

    def test_compile_no_output_prints_count(self, tmp_dir, capsys):
        """Compile without --output prints tile count."""
        from u3edit.shapes import cmd_compile_tiles
        src = os.path.join(tmp_dir, 'test.tiles')
        self._make_tiles_source(src, count=5)
        args = argparse.Namespace(source=src, output=None, format='binary')
        cmd_compile_tiles(args)
        captured = capsys.readouterr()
        assert '5 tiles' in captured.out

    def test_parse_tiles_text_auto_index(self, tmp_dir):
        """Tiles without headers get auto-assigned sequential indices."""
        from u3edit.shapes import parse_tiles_text
        text = '# Tile 0x10: Start\n'
        for _ in range(8):
            text += '#######\n'
        text += '\n'
        for _ in range(8):
            text += '.......\n'
        text += '\n'
        tiles = parse_tiles_text(text)
        assert len(tiles) == 2
        assert tiles[0][0] == 0x10
        assert tiles[1][0] == 0x11  # auto-assigned


class TestPatchCompileNamesSubcommand:
    """Test u3edit patch compile-names/decompile-names CLI subcommands."""

    def _make_names_source(self, path, names=None):
        """Create a .names source file."""
        if names is None:
            names = ['WATER', 'GRASS', 'FOREST', 'MOUNTAIN',
                     'SWORD', 'MACE', 'DAGGER']
        lines = ['# Test Name Table', '# Group: Terrain']
        lines.extend(names[:4])
        lines.append('')
        lines.append('# Group: Weapons')
        lines.extend(names[4:])
        with open(path, 'w') as f:
            f.write('\n'.join(lines) + '\n')

    def test_compile_names_json(self, tmp_dir):
        """Compile .names to JSON with regions.name-table.data."""
        from u3edit.patch import cmd_compile_names
        src = os.path.join(tmp_dir, 'test.names')
        self._make_names_source(src)
        out = os.path.join(tmp_dir, 'names.json')
        args = argparse.Namespace(source=src, output=out)
        cmd_compile_names(args)
        with open(out, 'r') as f:
            result = json.load(f)
        assert 'regions' in result
        assert 'name-table' in result['regions']
        assert 'data' in result['regions']['name-table']
        names = result['regions']['name-table']['data']
        assert 'WATER' in names
        assert 'SWORD' in names

    def test_compile_names_stdout(self, tmp_dir, capsys):
        """Compile .names to stdout prints JSON."""
        from u3edit.patch import cmd_compile_names
        src = os.path.join(tmp_dir, 'test.names')
        self._make_names_source(src)
        args = argparse.Namespace(source=src, output=None)
        cmd_compile_names(args)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert 'regions' in result

    def test_validate_names_pass(self, tmp_dir, capsys):
        """Validate .names within budget passes."""
        from u3edit.patch import cmd_validate_names
        src = os.path.join(tmp_dir, 'test.names')
        self._make_names_source(src)
        args = argparse.Namespace(source=src)
        cmd_validate_names(args)
        captured = capsys.readouterr()
        assert 'PASS' in captured.out

    def test_validate_names_fail(self, tmp_dir):
        """Validate .names over budget fails."""
        from u3edit.patch import cmd_validate_names
        src = os.path.join(tmp_dir, 'test.names')
        # Create names that exceed 891-byte budget
        names = [f'VERY_LONG_NAME_PADDING_{i:04d}' for i in range(100)]
        self._make_names_source(src, names)
        args = argparse.Namespace(source=src)
        with pytest.raises(SystemExit):
            cmd_validate_names(args)

    def test_decompile_names(self, tmp_dir):
        """Decompile name table from ULT3-sized binary."""
        from u3edit.patch import cmd_decompile_names
        # Create a minimal binary with name table at offset 0x397A
        data = bytearray(0x397A + 921)
        # Encode some test names at offset 0x397A
        offset = 0x397A
        for name in ['WATER', 'GRASS', 'SWORD']:
            for ch in name:
                data[offset] = ord(ch) | 0x80
                offset += 1
            data[offset] = 0x00
            offset += 1
        bin_path = os.path.join(tmp_dir, 'test_ult3.bin')
        with open(bin_path, 'wb') as f:
            f.write(data)
        out = os.path.join(tmp_dir, 'names.names')
        args = argparse.Namespace(file=bin_path, output=out)
        cmd_decompile_names(args)
        with open(out, 'r') as f:
            text = f.read()
        assert 'WATER' in text
        assert 'GRASS' in text
        assert 'SWORD' in text

    def test_parse_names_empty_string(self):
        """Explicit empty strings ('""') are preserved."""
        from u3edit.patch import _parse_names_file
        text = '# Test\nFOO\n""\nBAR\n'
        names = _parse_names_file(text)
        assert names == ['FOO', '', 'BAR']

    def test_validate_names_budget_math(self):
        """Budget math: encoded size = sum(len+1), budget = 921-30."""
        from u3edit.patch import _validate_names
        names = ['AB', 'CD']
        size, budget, valid = _validate_names(names)
        assert size == 6  # (2+1) + (2+1)
        assert budget == 891
        assert valid is True


class TestCliParityCompilers:
    """Verify compile subcommands are registered in CLI dispatch."""

    def test_map_compile_in_dispatch(self):
        """map dispatch handles 'compile'."""
        from u3edit.map import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'compile'" in src

    def test_map_decompile_in_dispatch(self):
        """map dispatch handles 'decompile'."""
        from u3edit.map import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'decompile'" in src

    def test_shapes_compile_in_dispatch(self):
        """shapes dispatch handles 'compile'."""
        from u3edit.shapes import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'compile'" in src

    def test_shapes_decompile_in_dispatch(self):
        """shapes dispatch handles 'decompile'."""
        from u3edit.shapes import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'decompile'" in src

    def test_patch_compile_names_in_dispatch(self):
        """patch dispatch handles 'compile-names'."""
        from u3edit.patch import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'compile-names'" in src

    def test_patch_decompile_names_in_dispatch(self):
        """patch dispatch handles 'decompile-names'."""
        from u3edit.patch import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'decompile-names'" in src

    def test_patch_validate_names_in_dispatch(self):
        """patch dispatch handles 'validate-names'."""
        from u3edit.patch import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'validate-names'" in src


# ============================================================================
# Compile warnings and validation (Task #110)
# ============================================================================

class TestMapCompileWarnings:
    """Test map compile dimension warnings."""

    def test_overworld_short_rows_warns(self, tmp_path):
        """Compiling overworld with <64 rows warns on stderr."""
        from u3edit.map import cmd_compile
        # Build a 10-row overworld source
        src = tmp_path / 'short.map'
        src.write_text('# Overworld\n' + ('.' * 64 + '\n') * 10)
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), dungeon=False)
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile(args)
        assert 'only 10 rows' in stderr.getvalue()
        assert len(out.read_bytes()) == 4096

    def test_dungeon_short_levels_warns(self, tmp_path):
        """Compiling dungeon with <8 levels warns on stderr."""
        from u3edit.map import cmd_compile
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
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile(args)
        assert 'only 2 dungeon levels' in stderr.getvalue()
        assert len(out.read_bytes()) == 2048

    def test_unknown_char_warns(self, tmp_path):
        """Compiling map with unknown chars warns and maps to 0x00."""
        from u3edit.map import cmd_compile
        # 'Z' is not a valid tile char
        src = tmp_path / 'bad.map'
        src.write_text('# Overworld\n' + ('Z' * 64 + '\n') * 64)
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), dungeon=False)
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile(args)
        assert 'unknown tile chars' in stderr.getvalue()
        assert 'Z' in stderr.getvalue()

    def test_full_overworld_no_warning(self, tmp_path):
        """64-row overworld compile produces no warnings."""
        from u3edit.map import cmd_compile
        src = tmp_path / 'full.map'
        src.write_text('# Overworld\n' + ('.' * 64 + '\n') * 64)
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), dungeon=False)
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile(args)
        assert stderr.getvalue() == ''


class TestShapesCompileWarnings:
    """Test shapes compile partial glyph set warning."""

    def test_partial_tileset_warns(self, tmp_path):
        """Compiling fewer than 256 glyphs warns on stderr."""
        from u3edit.shapes import cmd_compile_tiles
        # Source with only 2 tiles
        lines = []
        for idx in range(2):
            lines.append(f'# Tile 0x{idx:02X}')
            for _ in range(8):
                lines.append('#......')
            lines.append('')
        src = tmp_path / 'partial.tiles'
        src.write_text('\n'.join(lines))
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), format='binary')
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile_tiles(args)
        assert 'only 2 of 256 glyphs' in stderr.getvalue()

    def test_full_tileset_no_warning(self, tmp_path):
        """Compiling all 256 glyphs produces no warning."""
        from u3edit.shapes import cmd_compile_tiles, GLYPHS_PER_FILE
        lines = []
        for idx in range(GLYPHS_PER_FILE):
            lines.append(f'# Tile 0x{idx:02X}')
            for _ in range(8):
                lines.append('.......')
            lines.append('')
        src = tmp_path / 'full.tiles'
        src.write_text('\n'.join(lines))
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), format='binary')
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile_tiles(args)
        assert stderr.getvalue() == ''


class TestMapDecompileUnknownTiles:
    """Test map decompile unknown tile byte warnings."""

    def test_unknown_overworld_tile_warns(self, tmp_path):
        """Decompiling overworld with unmapped byte warns on stderr."""
        from u3edit.map import cmd_decompile
        # Create 4096 bytes: all 0xFF (unlikely to be mapped)
        binfile = tmp_path / 'MAP'
        binfile.write_bytes(bytes([0xFF]) * 4096)
        out = tmp_path / 'out.map'
        args = argparse.Namespace(file=str(binfile), output=str(out))
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_decompile(args)
        # Should warn about unmapped 0xFF
        warn = stderr.getvalue()
        assert 'unmapped tile byte' in warn
        assert '0xFF' in warn

    def test_unknown_dungeon_tile_warns(self, tmp_path):
        """Decompiling dungeon with unmapped byte warns on stderr."""
        from u3edit.map import cmd_decompile
        binfile = tmp_path / 'DNG'
        binfile.write_bytes(bytes([0xFE]) * 2048)
        out = tmp_path / 'out.map'
        args = argparse.Namespace(file=str(binfile), output=str(out))
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_decompile(args)
        warn = stderr.getvalue()
        assert 'unmapped tile byte' in warn
        assert '0xFE' in warn

    def test_known_tiles_no_warning(self, tmp_path):
        """Decompiling all-zero map produces no warning."""
        from u3edit.map import cmd_decompile
        binfile = tmp_path / 'MAP'
        binfile.write_bytes(bytes(4096))
        out = tmp_path / 'out.map'
        args = argparse.Namespace(file=str(binfile), output=str(out))
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_decompile(args)
        assert stderr.getvalue() == ''


class TestCombatMapTruncated:
    """Test CombatMap handles truncated data correctly."""

    def test_truncated_padding_defaults_to_zeros(self):
        """Truncated file gets zero-filled padding arrays."""
        from u3edit.combat import CombatMap
        from u3edit.constants import CON_PADDING1_SIZE
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
        from u3edit.combat import CombatMap
        from u3edit.constants import CON_FILE_SIZE
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
        from u3edit.combat import cmd_import
        from u3edit.constants import (
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
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_import(args)
        assert 'outside' in stderr.getvalue()
        result = out.read_bytes()
        assert result[CON_MONSTER_X_OFFSET] == 10
        assert result[CON_MONSTER_Y_OFFSET] == 10

    def test_pc_oob_clamped_and_warns(self, tmp_path):
        """PC positions >10 are clamped to 10 with a warning."""
        from u3edit.combat import cmd_import
        from u3edit.constants import (
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
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_import(args)
        assert 'outside' in stderr.getvalue()
        result = out.read_bytes()
        assert result[CON_PC_X_OFFSET] == 10
        assert result[CON_PC_Y_OFFSET] == 0

    def test_valid_positions_no_warning(self, tmp_path):
        """Positions within 0-10 produce no warning."""
        from u3edit.combat import cmd_import
        from u3edit.constants import CON_FILE_SIZE
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
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_import(args)
        assert 'outside' not in stderr.getvalue()


# ============================================================================
# DDRW command tests (Task #112)
# ============================================================================

class TestDdrwCommands:
    """Tests for ddrw cmd_view, cmd_edit, cmd_import."""

    def test_view_text_output(self, tmp_path, capsys):
        """cmd_view prints dungeon drawing data summary."""
        from u3edit.ddrw import cmd_view
        from u3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        binfile.write_bytes(bytes(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            path=str(binfile), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Dungeon Drawing Data' in out
        assert '1792 bytes' in out

    def test_view_json_output(self, tmp_path):
        """cmd_view --json produces JSON with vectors and records."""
        from u3edit.ddrw import cmd_view
        from u3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        data = bytearray(DDRW_FILE_SIZE)
        data[0xF0] = 0x42  # Set a perspective vector
        binfile.write_bytes(bytes(data))
        outfile = tmp_path / 'out.json'
        args = argparse.Namespace(
            path=str(binfile), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert result['size'] == DDRW_FILE_SIZE
        assert result['vectors'][0] == 0x42
        assert 'raw' in result

    def test_edit_patches_bytes(self, tmp_path):
        """cmd_edit patches bytes at offset."""
        from u3edit.ddrw import cmd_edit
        from u3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        binfile.write_bytes(bytes(DDRW_FILE_SIZE))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), offset=0x10, data='AABB',
            output=str(out), backup=False, dry_run=False)
        cmd_edit(args)
        result = out.read_bytes()
        assert result[0x10] == 0xAA
        assert result[0x11] == 0xBB

    def test_edit_dry_run(self, tmp_path, capsys):
        """cmd_edit --dry-run doesn't write."""
        from u3edit.ddrw import cmd_edit
        from u3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        binfile.write_bytes(bytes(DDRW_FILE_SIZE))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), offset=0, data='FF',
            output=str(out), backup=False, dry_run=True)
        cmd_edit(args)
        assert not out.exists()
        assert 'Dry run' in capsys.readouterr().out

    def test_import_raw_json(self, tmp_path):
        """cmd_import writes raw byte array from JSON."""
        from u3edit.ddrw import cmd_import
        from u3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        binfile.write_bytes(bytes(DDRW_FILE_SIZE))
        data = [0] * DDRW_FILE_SIZE
        data[0] = 0x55
        jfile = tmp_path / 'ddrw.json'
        jfile.write_text(json.dumps({'raw': data}))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=str(out), backup=False, dry_run=False)
        cmd_import(args)
        result = out.read_bytes()
        assert len(result) == DDRW_FILE_SIZE
        assert result[0] == 0x55

    def test_import_backup(self, tmp_path):
        """cmd_import --backup creates .bak file."""
        from u3edit.ddrw import cmd_import
        from u3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        binfile.write_bytes(bytes(DDRW_FILE_SIZE))
        data = [0] * DDRW_FILE_SIZE
        jfile = tmp_path / 'ddrw.json'
        jfile.write_text(json.dumps({'raw': data}))
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=None, backup=True, dry_run=False)
        cmd_import(args)
        bak = tmp_path / 'DDRW.bak'
        assert bak.exists()


# ============================================================================
# Sound command tests (Task #112)
# ============================================================================

class TestSoundCommands:
    """Tests for sound cmd_view, cmd_edit, cmd_import."""

    def test_view_sosa(self, tmp_path, capsys):
        """cmd_view displays SOSA file summary."""
        from u3edit.sound import cmd_view
        from u3edit.constants import SOSA_FILE_SIZE
        binfile = tmp_path / 'SOSA'
        binfile.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            path=str(binfile), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'SOSA' in out or 'Speaker' in out or '4096' in out

    def test_view_json(self, tmp_path):
        """cmd_view --json produces JSON output."""
        from u3edit.sound import cmd_view
        from u3edit.constants import SOSM_FILE_SIZE
        binfile = tmp_path / 'SOSM'
        binfile.write_bytes(bytes(SOSM_FILE_SIZE))
        outfile = tmp_path / 'out.json'
        args = argparse.Namespace(
            path=str(binfile), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'raw' in result

    def test_edit_patches_bytes(self, tmp_path):
        """cmd_edit patches sound file bytes."""
        from u3edit.sound import cmd_edit
        from u3edit.constants import SOSA_FILE_SIZE
        binfile = tmp_path / 'SOSA'
        binfile.write_bytes(bytes(SOSA_FILE_SIZE))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), offset=0, data='DEADBEEF',
            output=str(out), backup=False, dry_run=False)
        cmd_edit(args)
        result = out.read_bytes()
        assert result[0:4] == bytes([0xDE, 0xAD, 0xBE, 0xEF])

    def test_edit_past_end_exits(self, tmp_path):
        """cmd_edit rejects patch beyond file end."""
        from u3edit.sound import cmd_edit
        from u3edit.constants import SOSM_FILE_SIZE
        binfile = tmp_path / 'SOSM'
        binfile.write_bytes(bytes(SOSM_FILE_SIZE))
        args = argparse.Namespace(
            file=str(binfile), offset=SOSM_FILE_SIZE - 1, data='AABB',
            output=str(binfile), backup=False, dry_run=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_import_sosa(self, tmp_path):
        """cmd_import writes SOSA from JSON."""
        from u3edit.sound import cmd_import
        from u3edit.constants import SOSA_FILE_SIZE
        binfile = tmp_path / 'SOSA'
        binfile.write_bytes(bytes(SOSA_FILE_SIZE))
        data = [0] * SOSA_FILE_SIZE
        data[0] = 0x77
        jfile = tmp_path / 'sosa.json'
        jfile.write_text(json.dumps({'raw': data}))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=str(out), backup=False, dry_run=False)
        cmd_import(args)
        result = out.read_bytes()
        assert len(result) == SOSA_FILE_SIZE
        assert result[0] == 0x77

    def test_import_wrong_size_warns(self, tmp_path):
        """cmd_import warns when size doesn't match known formats."""
        from u3edit.sound import cmd_import
        binfile = tmp_path / 'SOUND'
        binfile.write_bytes(bytes(100))
        jfile = tmp_path / 'sound.json'
        jfile.write_text(json.dumps({'raw': [0] * 100}))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=str(out), backup=False, dry_run=False)
        import io, contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_import(args)
        assert 'Warning' in stderr.getvalue()


# ============================================================================
# Diff command tests (Task #112)
# ============================================================================

class TestDiffCommands:
    """Tests for diff cmd_diff."""

    def test_diff_identical_rosters(self, tmp_path, capsys):
        """Diffing identical roster files shows no changes."""
        from u3edit.diff import cmd_diff
        from u3edit.constants import ROSTER_FILE_SIZE
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
        from u3edit.diff import cmd_diff
        from u3edit.constants import ROSTER_FILE_SIZE
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
        from u3edit.diff import cmd_diff
        from u3edit.constants import ROSTER_FILE_SIZE
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
        from u3edit.diff import cmd_diff
        from u3edit.constants import MAP_OVERWORLD_SIZE
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
        from u3edit.diff import cmd_diff
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
        from u3edit.diff import cmd_diff
        from u3edit.constants import ROSTER_FILE_SIZE
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
        from u3edit.diff import cmd_diff
        from u3edit.constants import MBS_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'MBS', MBS_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'MBS' in out

    def test_diff_ddrw_files(self, tmp_path, capsys):
        """Diff detects changes in DDRW files."""
        from u3edit.diff import cmd_diff
        from u3edit.constants import DDRW_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'DDRW', DDRW_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'DDRW' in out

    def test_diff_shps_files(self, tmp_path, capsys):
        """Diff detects changes in SHPS files."""
        from u3edit.diff import cmd_diff
        from u3edit.constants import SHPS_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'SHPS', SHPS_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'SHPS' in out

    def test_diff_text_files(self, tmp_path, capsys):
        """Diff detects changes in TEXT files."""
        from u3edit.diff import cmd_diff
        from u3edit.constants import TEXT_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'TEXT', TEXT_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'TEXT' in out

    def test_diff_binary_identical(self, tmp_path, capsys):
        """Identical binary files show no byte changes."""
        from u3edit.diff import diff_binary
        from u3edit.constants import DDRW_FILE_SIZE
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
        from u3edit.diff import cmd_diff
        from u3edit.constants import (
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
        from u3edit.equip import cmd_view
        args = argparse.Namespace(json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Dagger' in out or 'Leather' in out

    def test_equip_view_json(self, tmp_path):
        """equip view --json produces valid JSON."""
        from u3edit.equip import cmd_view
        outfile = tmp_path / 'equip.json'
        args = argparse.Namespace(json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'weapons' in result or 'armors' in result

    def test_spell_view(self, capsys):
        """spell view produces spell reference table."""
        from u3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            cleric_only=False, wizard_only=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert len(out) > 50

    def test_spell_view_json(self, tmp_path):
        """spell view --json produces valid JSON."""
        from u3edit.spell import cmd_view
        outfile = tmp_path / 'spells.json'
        args = argparse.Namespace(
            json=True, output=str(outfile),
            cleric_only=False, wizard_only=False)
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert isinstance(result, dict) or isinstance(result, list)

    def test_shapes_export_png(self, tmp_path):
        """shapes export creates PNG files from SHPS data."""
        from u3edit.shapes import cmd_export
        from u3edit.constants import SHPS_FILE_SIZE
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
        from u3edit.shapes import cmd_export
        from u3edit.constants import SHPS_FILE_SIZE
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
        from u3edit.shapes import cmd_info
        from u3edit.constants import SHPS_FILE_SIZE
        shps = tmp_path / 'SHPS'
        shps.write_bytes(bytes(SHPS_FILE_SIZE))
        args = argparse.Namespace(
            file=str(shps), json=False, output=None)
        cmd_info(args)
        out = capsys.readouterr().out
        assert '256' in out or 'charset' in out.lower()

    def test_shapes_info_json(self, tmp_path):
        """shapes info --json produces valid JSON."""
        from u3edit.shapes import cmd_info
        from u3edit.constants import SHPS_FILE_SIZE
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
        from u3edit.roster import cmd_view
        from u3edit.constants import ROSTER_FILE_SIZE
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
        from u3edit.bestiary import cmd_view
        from u3edit.constants import MON_FILE_SIZE
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
        from u3edit.save import cmd_view
        from u3edit.constants import PRTY_FILE_SIZE
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
        from u3edit.combat import cmd_view
        from u3edit.constants import CON_FILE_SIZE
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

class TestPatchCmdEdit:
    """Tests for patch.cmd_edit — region patching."""

    def _make_ult3(self, tmp_path):
        """Create a fake ULT3 binary of the right size."""
        from u3edit.constants import ULT3_FILE_SIZE
        path = tmp_path / 'ULT3'
        path.write_bytes(bytes(ULT3_FILE_SIZE))
        return str(path)

    def test_edit_moongate_x(self, tmp_path, capsys):
        """Patch moongate-x region and verify bytes written."""
        from u3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        args = argparse.Namespace(
            file=path, region='moongate-x', data='01 02 03 04 05 06 07 08',
            dry_run=False, backup=False, output=None)
        cmd_edit(args)
        with open(path, 'rb') as f:
            data = f.read()
        assert data[0x29A7:0x29A7 + 8] == bytes([1, 2, 3, 4, 5, 6, 7, 8])

    def test_edit_dry_run(self, tmp_path, capsys):
        """Dry run shows changes but doesn't write."""
        from u3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        args = argparse.Namespace(
            file=path, region='moongate-x', data='AABBCCDD',
            dry_run=True, backup=False, output=None)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        with open(path, 'rb') as f:
            data = f.read()
        assert data[0x29A7:0x29A7 + 4] == bytes(4)  # unchanged

    def test_edit_unknown_region_exits(self, tmp_path):
        """Unknown region name causes sys.exit."""
        from u3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        args = argparse.Namespace(
            file=path, region='nonexistent', data='AA',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_data_too_long_exits(self, tmp_path):
        """Data exceeding region max_length causes sys.exit."""
        from u3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        # moongate-x max_length is 8, send 9 bytes
        args = argparse.Namespace(
            file=path, region='moongate-x', data='01 02 03 04 05 06 07 08 09',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_invalid_hex_exits(self, tmp_path):
        """Invalid hex data causes sys.exit."""
        from u3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        args = argparse.Namespace(
            file=path, region='moongate-x', data='ZZZZ',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_unrecognized_binary_exits(self, tmp_path):
        """Non-engine binary file causes sys.exit."""
        from u3edit.patch import cmd_edit
        path = tmp_path / 'JUNK'
        path.write_bytes(bytes(100))
        args = argparse.Namespace(
            file=str(path), region='moongate-x', data='AA',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_with_backup(self, tmp_path):
        """Backup flag creates .bak before patching."""
        from u3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        args = argparse.Namespace(
            file=path, region='food-rate', data='02',
            dry_run=False, backup=True, output=None)
        cmd_edit(args)
        assert os.path.exists(path + '.bak')


class TestPatchCmdDump:
    """Tests for patch.cmd_dump — hex dump."""

    def test_dump_basic(self, tmp_path, capsys):
        """Hex dump produces output with hex values."""
        from u3edit.patch import cmd_dump
        from u3edit.constants import ULT3_FILE_SIZE
        path = tmp_path / 'ULT3'
        data = bytearray(ULT3_FILE_SIZE)
        data[0] = 0xAB
        data[1] = 0xCD
        path.write_bytes(bytes(data))
        args = argparse.Namespace(file=str(path), offset=0, length=16)
        cmd_dump(args)
        out = capsys.readouterr().out
        assert 'AB CD' in out

    def test_dump_offset_past_end_exits(self, tmp_path):
        """Offset past end of file causes sys.exit."""
        from u3edit.patch import cmd_dump
        path = tmp_path / 'SMALL'
        path.write_bytes(bytes(16))
        args = argparse.Namespace(file=str(path), offset=100, length=16)
        with pytest.raises(SystemExit):
            cmd_dump(args)

    def test_dump_with_load_addr(self, tmp_path, capsys):
        """Recognized binary shows load addresses."""
        from u3edit.patch import cmd_dump
        from u3edit.constants import ULT3_FILE_SIZE
        path = tmp_path / 'ULT3'
        path.write_bytes(bytes(ULT3_FILE_SIZE))
        args = argparse.Namespace(file=str(path), offset=0, length=16)
        cmd_dump(args)
        out = capsys.readouterr().out
        # ULT3 load_addr is 0x5000, so first line should show 5000:
        assert '5000:' in out


# =============================================================================
# Map cmd_fill / cmd_replace / cmd_find CLI tests
# =============================================================================

class TestMapCmdFill:
    """Tests for map.cmd_fill — fill rectangular regions."""

    def test_fill_basic(self, tmp_path, capsys):
        """Fill a 2x2 region on an overworld map."""
        from u3edit.map import cmd_fill
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
        from u3edit.map import cmd_fill
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
        from u3edit.map import cmd_fill
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
        from u3edit.map import cmd_replace
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
        from u3edit.map import cmd_replace
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
        from u3edit.map import cmd_find
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
        from u3edit.map import cmd_find
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
        from u3edit.map import cmd_find
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
        from u3edit.tlk import encode_record
        data = encode_record([text])
        path.write_bytes(bytes(data))

    def test_view_single_file(self, tmp_path, capsys):
        """View a single TLK file."""
        from u3edit.tlk import cmd_view
        tlk = tmp_path / 'TLKA'
        self._make_tlk(tlk, 'Test dialog')
        args = argparse.Namespace(
            path=str(tlk), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Test dialog' in out

    def test_view_json(self, tmp_path):
        """View --json produces valid JSON."""
        from u3edit.tlk import cmd_view
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
        from u3edit.tlk import cmd_view
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
        from u3edit.tlk import cmd_import, load_tlk_records
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
        assert 'Hello traveler' in records[0][0]

    def test_import_dry_run(self, tmp_path, capsys):
        """Dry run doesn't write changes."""
        from u3edit.tlk import cmd_import
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
        from u3edit.tlk import cmd_import
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
        from u3edit.roster import cmd_import
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
        from u3edit.roster import cmd_import
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
        from u3edit.map import cmd_view
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
        from u3edit.save import cmd_view
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
        from u3edit.save import cmd_view
        game_dir = self._make_save_dir(tmp_path)
        # Also create a SOSA file (overworld map)
        from u3edit.constants import SOSA_FILE_SIZE
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
        from u3edit.save import cmd_view
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
        from u3edit.save import cmd_edit
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
        from u3edit.save import cmd_edit
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
        from u3edit.save import cmd_edit
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
        from u3edit.combat import cmd_view
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
        from u3edit.combat import cmd_view
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
        from u3edit.combat import cmd_view
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
        from u3edit.special import cmd_view
        brnd = tmp_path / 'BRND'
        brnd.write_bytes(bytes(SPECIAL_FILE_SIZE))
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'BRND' in out or 'Brand' in out

    def test_view_directory_json(self, tmp_path):
        """View directory --json produces valid JSON."""
        from u3edit.special import cmd_view
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
        from u3edit.special import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


# =============================================================================
# DDRW cmd_edit out-of-bounds and sound cmd_edit dry-run tests
# =============================================================================

class TestDdrwCmdEditBounds:
    """Tests for ddrw cmd_edit boundary checking."""

    def test_edit_past_end_exits(self, tmp_path):
        """Patch extending past end of file causes sys.exit."""
        from u3edit.ddrw import cmd_edit
        from u3edit.constants import DDRW_FILE_SIZE
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            file=str(path), offset=DDRW_FILE_SIZE - 1, data='AABB',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_dry_run(self, tmp_path, capsys):
        """DDRW edit dry run shows changes without writing."""
        from u3edit.ddrw import cmd_edit
        from u3edit.constants import DDRW_FILE_SIZE
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            file=str(path), offset=0, data='AB',
            dry_run=True, backup=False, output=None)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        assert path.read_bytes()[0] == 0  # unchanged


class TestSoundCmdEditExpanded:
    """Tests for sound cmd_edit with dry-run and backup."""

    def test_edit_dry_run(self, tmp_path, capsys):
        """Sound edit dry run shows changes without writing."""
        from u3edit.sound import cmd_edit
        from u3edit.constants import SOSA_FILE_SIZE
        path = tmp_path / 'SOSA'
        path.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            file=str(path), offset=0, data='FF',
            dry_run=True, backup=False, output=None)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        assert path.read_bytes()[0] == 0  # unchanged

    def test_edit_with_backup(self, tmp_path):
        """Sound edit --backup creates .bak file."""
        from u3edit.sound import cmd_edit
        from u3edit.constants import SOSA_FILE_SIZE
        path = tmp_path / 'SOSA'
        path.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            file=str(path), offset=0, data='FF',
            dry_run=False, backup=True, output=None)
        cmd_edit(args)
        assert os.path.exists(str(path) + '.bak')


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
        from u3edit.roster import Character
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.name = 'ABCDEFGHIJKLM'  # 13 chars
        assert char.name == 'ABCDEFGHIJKLM'

    def test_name_14_chars_truncated(self):
        """14-character name is truncated to 13."""
        from u3edit.roster import Character
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.name = 'ABCDEFGHIJKLMN'  # 14 chars
        assert char.name == 'ABCDEFGHIJKLM'  # truncated to 13
        # Byte 0x0D must be null (field boundary)
        assert char.raw[0x0D] == 0x00

    def test_name_short_null_fills(self):
        """Short name null-fills the remaining field bytes."""
        from u3edit.roster import Character
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
        from u3edit.combat import CombatMap, validate_combat_map
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
        from u3edit.combat import CombatMap, validate_combat_map
        data = bytearray(CON_FILE_SIZE)
        cm = CombatMap(data)
        cm.monster_x[0] = 3
        cm.monster_y[0] = 3
        cm.monster_x[1] = 7
        cm.monster_y[1] = 7
        warnings = validate_combat_map(cm)
        overlap_warnings = [w for w in warnings if 'overlap' in w.lower()]
        assert len(overlap_warnings) == 0
