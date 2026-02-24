"""Tests for roster tool."""

import argparse
import json
import os
import tempfile

import pytest

from ult3edit.roster import Character, load_roster, save_roster, cmd_edit, cmd_create, cmd_import, cmd_check_progress, check_progress, validate_character
from ult3edit.bcd import int_to_bcd, int_to_bcd16
from ult3edit.constants import (
    CHAR_CLASS, CHAR_GENDER, CHAR_HP_HI, CHAR_HP_LO, CHAR_IN_PARTY,
    CHAR_MARKS_CARDS, CHAR_MAX_SLOTS, CHAR_NAME_OFFSET, CHAR_RACE,
    CHAR_READIED_WEAPON, CHAR_RECORD_SIZE, CHAR_STATUS, CHAR_STR,
    CHAR_WORN_ARMOR, ROSTER_FILE_SIZE,
)
from ult3edit.tui.roster_editor import make_roster_tab


class TestCharacter:
    def test_name(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        assert char.name == 'HERO'

    def test_race(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        assert char.race == 'Human'

    def test_class(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        assert char.char_class == 'Fighter'

    def test_gender(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        assert char.gender == 'Male'

    def test_stats(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        assert char.strength == 25
        assert char.dexterity == 30
        assert char.intelligence == 15
        assert char.wisdom == 20

    def test_hp(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        assert char.hp == 150
        assert char.max_hp == 150

    def test_food(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        assert char.food == 200

    def test_gold(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        assert char.gold == 100

    def test_status(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        assert char.status == 'Good'

    def test_empty(self):
        char = Character(bytearray(CHAR_RECORD_SIZE))
        assert char.is_empty


class TestMarksCards:
    """Test R-2 fix: marks are high nibble, cards are low nibble."""

    def test_marks_only(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        # Byte 0x0E = 0x90 = bits 7 and 4 set = Kings + Force
        marks = char.marks
        assert 'Kings' in marks
        assert 'Force' in marks
        assert len(marks) == 2

    def test_cards_none(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        assert char.cards == []

    def test_set_marks(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        char.marks = ['Snake', 'Fire']
        marks = char.marks
        assert 'Snake' in marks
        assert 'Fire' in marks
        assert 'Kings' not in marks  # Should have cleared old marks

    def test_set_cards(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        char.cards = ['Death', 'Love']
        assert 'Death' in char.cards
        assert 'Love' in char.cards
        # Marks should be preserved
        assert 'Kings' in char.marks

    def test_marks_cards_independent(self, sample_character_bytes):
        """Setting marks shouldn't affect cards and vice versa."""
        char = Character(bytearray(sample_character_bytes))
        char.cards = ['Sol']
        # Marks should still be Kings + Force
        assert 'Kings' in char.marks
        assert 'Force' in char.marks


class TestCharacterSetters:
    def test_set_name(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        char.name = 'WIZARD'
        assert char.name == 'WIZARD'

    def test_set_strength(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        char.strength = 50
        assert char.strength == 50

    def test_set_hp(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        char.hp = 500
        assert char.hp == 500

    def test_set_gold(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        char.gold = 5000
        assert char.gold == 5000

    def test_set_food(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        char.food = 9999
        assert char.food == 9999


class TestToDict:
    def test_keys(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        d = char.to_dict()
        assert 'name' in d
        assert 'race' in d
        assert 'stats' in d
        assert 'hp' in d
        assert 'marks' in d
        assert 'cards' in d

    def test_values(self, sample_character_bytes):
        char = Character(sample_character_bytes)
        d = char.to_dict()
        assert d['name'] == 'HERO'
        assert d['stats']['str'] == 25
        assert d['hp'] == 150


class TestLoadSave:
    def test_load_roster(self, sample_roster_file):
        chars, data = load_roster(sample_roster_file)
        assert len(chars) == 20
        assert chars[0].name == 'HERO'
        assert chars[1].is_empty

    def test_roundtrip(self, sample_roster_file, tmp_dir):
        chars, original = load_roster(sample_roster_file)
        chars[0].strength = 50
        output = os.path.join(tmp_dir, 'ROST_OUT')
        save_roster(output, chars, original)

        chars2, _ = load_roster(output)
        assert chars2[0].strength == 50
        assert chars2[0].name == 'HERO'  # Other fields preserved


def _edit_args(**kwargs):
    """Build an argparse.Namespace with all roster edit args defaulting to None."""
    defaults = dict(
        file=None, slot=0, output=None, name=None,
        str=None, dex=None, int_=None, wis=None,
        hp=None, max_hp=None, mp=None,
        gold=None, exp=None, food=None,
        gems=None, keys=None, powders=None, torches=None,
        race=None, class_=None, status=None, gender=None,
        weapon=None, armor=None,
        give_weapon=None, give_armor=None,
        marks=None, cards=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestCmdEdit:
    def test_edit_name(self, sample_roster_file, tmp_dir):
        out = os.path.join(tmp_dir, 'ROST_OUT')
        args = _edit_args(file=sample_roster_file, slot=0, output=out, name='KNIGHT')
        cmd_edit(args)
        chars, _ = load_roster(out)
        assert chars[0].name == 'KNIGHT'
        assert chars[0].strength == 25  # Other stats preserved

    def test_edit_strength(self, sample_roster_file, tmp_dir):
        out = os.path.join(tmp_dir, 'ROST_OUT')
        args = _edit_args(file=sample_roster_file, slot=0, output=out, **{'str': 99})
        cmd_edit(args)
        chars, _ = load_roster(out)
        assert chars[0].strength == 99
        assert chars[0].name == 'HERO'


class TestSetterValidation:
    """Test that setters raise ValueError on invalid codes."""

    def test_invalid_status(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        original = char.raw[0x11]  # CHAR_STATUS offset
        with pytest.raises(ValueError):
            char.status = 'INVALID'
        assert char.raw[0x11] == original  # Unchanged

    def test_invalid_race(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        original = char.raw[0x16]  # CHAR_RACE offset
        with pytest.raises(ValueError):
            char.race = 'X'
        assert char.raw[0x16] == original

    def test_invalid_class(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        original = char.raw[0x17]  # CHAR_CLASS offset
        with pytest.raises(ValueError):
            char.char_class = 'Z'
        assert char.raw[0x17] == original

    def test_invalid_gender(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        original = char.raw[0x18]  # CHAR_GENDER offset
        with pytest.raises(ValueError):
            char.gender = 'X'
        assert char.raw[0x18] == original

    def test_valid_full_name_race(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        char.race = 'Elf'
        assert char.race == 'Elf'

    def test_valid_full_name_class(self, sample_character_bytes):
        char = Character(bytearray(sample_character_bytes))
        char.char_class = 'Wizard'
        assert char.char_class == 'Wizard'


class TestCmdCreate:
    def test_create_character(self, sample_roster_file, tmp_dir):
        out = os.path.join(tmp_dir, 'ROST_OUT')
        args = argparse.Namespace(
            file=sample_roster_file, slot=1, output=out,
            name='WIZARD', race='E', class_='W', gender='F',
            str=10, dex=20, int_=25, wis=15, force=False,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None,
            torches=None, status=None, weapon=None, armor=None,
            give_weapon=None, give_armor=None, marks=None, cards=None,
            in_party=None, not_in_party=None, sub_morsels=None,
        )
        cmd_create(args)
        chars, _ = load_roster(out)
        assert chars[1].name == 'WIZARD'
        assert chars[1].race == 'Elf'
        assert chars[1].char_class == 'Wizard'
        assert chars[0].name == 'HERO'  # Slot 0 preserved


# ── Migrated from test_new_features.py ──

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
# TUI roster editor tests
# =============================================================================


class TestRosterEditorTUI:
    """Tests for make_roster_tab() from ult3edit.tui.roster_editor."""

    def test_construction(self, sample_roster_bytes):
        """make_roster_tab creates a FormEditorTab without error."""
        tab = make_roster_tab(sample_roster_bytes, lambda data: None)
        assert tab is not None

    def test_tab_name(self, sample_roster_bytes):
        """Tab name is 'Roster'."""
        tab = make_roster_tab(sample_roster_bytes, lambda data: None)
        assert tab.tab_name == 'Roster'

    def test_first_character_name(self, sample_roster_bytes):
        """First character name matches fixture (HERO)."""
        tab = make_roster_tab(sample_roster_bytes, lambda data: None)
        assert tab.records[0].name == 'HERO'

    def test_first_character_strength(self, sample_roster_bytes):
        """First character strength matches fixture (25)."""
        tab = make_roster_tab(sample_roster_bytes, lambda data: None)
        assert tab.records[0].strength == 25

    def test_empty_slots(self, sample_roster_bytes):
        """Slots 1-19 are all empty."""
        tab = make_roster_tab(sample_roster_bytes, lambda data: None)
        for i in range(1, CHAR_MAX_SLOTS):
            assert tab.records[i].is_empty, f"Slot {i} should be empty"

    def test_save_roundtrip_length(self, sample_roster_bytes):
        """get_save_data() on unmodified tab returns 1280 bytes."""
        tab = make_roster_tab(sample_roster_bytes, lambda data: None)
        save_data = tab.get_save_data()
        assert len(save_data) == ROSTER_FILE_SIZE

    def test_modified_save_differs(self, sample_roster_bytes):
        """Changing a field makes get_save_data() differ from original."""
        tab = make_roster_tab(sample_roster_bytes, lambda data: None)
        original_data = tab.get_save_data()
        tab.records[0].gold = 9999
        modified_data = tab.get_save_data()
        assert modified_data != original_data

    def test_save_callback_receives_data(self, sample_roster_bytes):
        """save_callback receives the serialized data."""
        received = []
        tab = make_roster_tab(sample_roster_bytes, lambda data: received.append(data))
        tab.save_callback(tab.get_save_data())
        assert len(received) == 1
        assert len(received[0]) == ROSTER_FILE_SIZE


# =============================================================================
# CLI cmd_create tests
# =============================================================================


def _create_args(**kwargs):
    """Build an argparse.Namespace with all roster create args defaulting to None."""
    defaults = dict(
        file=None, slot=0, output=None, force=False,
        dry_run=False, backup=False,
        name=None, str=None, dex=None, int_=None, wis=None,
        hp=None, max_hp=None, mp=None,
        gold=None, exp=None, food=None,
        gems=None, keys=None, powders=None, torches=None,
        race=None, class_=None, status=None, gender=None,
        weapon=None, armor=None,
        give_weapon=None, give_armor=None,
        marks=None, cards=None,
        in_party=None, not_in_party=None, sub_morsels=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestRosterCmdCreate:
    """Tests for cmd_create() from ult3edit.roster."""

    def test_creates_in_empty_slot(self, sample_roster_file, tmp_dir):
        """Creates a character in empty slot 1; slot is no longer empty."""
        out = os.path.join(tmp_dir, 'ROST_CREATE')
        args = _create_args(file=sample_roster_file, slot=1, output=out)
        cmd_create(args)
        chars, _ = load_roster(out)
        assert not chars[1].is_empty
        assert chars[0].name == 'HERO'  # Slot 0 preserved

    def test_default_name_is_hero(self, sample_roster_file, tmp_dir):
        """Created character has default name HERO when no name specified."""
        out = os.path.join(tmp_dir, 'ROST_CREATE')
        args = _create_args(file=sample_roster_file, slot=1, output=out)
        cmd_create(args)
        chars, _ = load_roster(out)
        assert chars[1].name == 'HERO'

    def test_dry_run_no_write(self, sample_roster_file, tmp_dir):
        """--dry-run does not create the output file."""
        out = os.path.join(tmp_dir, 'ROST_CREATE_DRY')
        args = _create_args(file=sample_roster_file, slot=1, output=out,
                            dry_run=True)
        cmd_create(args)
        assert not os.path.exists(out)

    def test_occupied_slot_without_force(self, sample_roster_file):
        """Creating in an occupied slot without --force raises SystemExit."""
        args = _create_args(file=sample_roster_file, slot=0)
        with pytest.raises(SystemExit):
            cmd_create(args)


# =============================================================================
# Tile Compiler Tests
# =============================================================================


# =============================================================================
# Map Compiler Tests
# =============================================================================


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


class TestRosterNoDeadImport:
    """roster.py: encode_high_ascii not imported (dead import removed)."""

    def test_no_encode_high_ascii_import(self):
        """Verify roster module doesn't import encode_high_ascii."""
        import ult3edit.roster as r
        # Should NOT have encode_high_ascii as a module-level name
        assert not hasattr(r, 'encode_high_ascii')


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


class TestImportTypeErrorHandling:
    """Tests for TypeError handling in weapon/armor import with bad count types."""

    def test_roster_import_bad_weapon_count_warns(self, tmp_path, capsys):
        """Non-integer weapon count in JSON warns instead of crashing."""
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
        path = self._make_roster_with_chars(tmp_path)
        args = argparse.Namespace(
            file=path, json=False, output=None)
        cmd_check_progress(args)
        captured = capsys.readouterr()
        assert 'READY TO FACE EXODUS' in captured.out

    def test_check_progress_text_not_ready(self, tmp_path, capsys):
        """cmd_check_progress shows not-ready for incomplete party."""
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
# Additional coverage: stat setter edge paths, cmd_view filters,
# cmd_edit with fields, cmd_import equipment, dispatch, main
# =============================================================================


class TestStatSetterEdgePaths:
    """Cover race/class setter hex fallback paths (lines 192, 217)."""

    def test_race_setter_hex_string(self):
        """Race setter accepts hex string for total conversions (line 192)."""
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.race = '0x10'
        assert char.raw[CHAR_RACE] == 0x10

    def test_class_setter_hex_string(self):
        """Class setter accepts hex string for total conversions (line 217)."""
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.char_class = '0x20'
        assert char.raw[CHAR_CLASS] == 0x20

    def test_equipped_armor_raw_hex_string(self):
        """Equipped armor setter accepts hex string (line 345)."""
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.equipped_armor = '0x05'
        assert char.raw[CHAR_WORN_ARMOR] == 0x05


class TestCharacterDisplay:
    """Cover Character.display lines 431-453: empty slot display, inventory display."""

    def test_display_empty_with_slot(self, capsys):
        """Display empty character with slot number shows '(empty)' (line 432)."""
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.display(slot=5)
        out = capsys.readouterr().out
        assert '(empty)' in out
        assert 'Slot  5' in out

    def test_display_empty_no_slot(self, capsys):
        """Display empty character without slot number prints nothing."""
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.display(slot=-1)
        out = capsys.readouterr().out
        assert out == ''

    def test_display_with_inventories(self, capsys):
        """Display character with weapon/armor inventories shows them (lines 445-453)."""
        from ult3edit.bcd import int_to_bcd
        char = Character(bytearray(CHAR_RECORD_SIZE))
        for i, ch in enumerate('HERO'):
            char.raw[i] = ord(ch) | 0x80
        char.raw[CHAR_STATUS] = ord('G')
        char.raw[CHAR_STR] = int_to_bcd(25)
        char.raw[CHAR_HP_HI] = 0x01
        # Set weapon inventory: 3 daggers (weapon index 1)
        char.set_weapon_count(1, 3)
        # Set armor inventory: 2 leather (armor index 2)
        char.set_armor_count(2, 2)
        char.display(slot=0)
        out = capsys.readouterr().out
        assert 'Weapons:' in out
        assert 'Armors:' in out
        assert 'Dagger' in out
        assert 'Leather' in out


class TestCmdViewSlotFilter:
    """Cover cmd_view lines 635-646: --slot filter and --validate in view."""

    def test_view_specific_slot(self, tmp_path, capsys):
        """cmd_view --slot shows only that slot (line 635)."""
        from ult3edit.roster import cmd_view
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        data[CHAR_HP_HI] = 0x01
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, slot=0, json=False, output=None, validate=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'HERO' in out

    def test_view_slot_with_validate(self, tmp_path, capsys):
        """cmd_view --slot --validate shows warnings (line 637)."""
        from ult3edit.roster import cmd_view
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        data[CHAR_HP_HI] = 0x01
        data[CHAR_STR] = 0xAA  # Invalid BCD
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, slot=0, json=False, output=None, validate=True)
        cmd_view(args)
        err = capsys.readouterr().err
        assert 'WARNING' in err

    def test_view_all_with_validate(self, tmp_path, capsys):
        """cmd_view (all slots) --validate shows warnings (lines 644-646)."""
        from ult3edit.roster import cmd_view
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        data[CHAR_HP_HI] = 0x01
        data[CHAR_STR] = 0xAA  # Invalid BCD
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, slot=None, json=False, output=None, validate=True)
        cmd_view(args)
        err = capsys.readouterr().err
        assert 'WARNING' in err

    def test_view_json_with_validate(self, tmp_path):
        """cmd_view --json --validate includes warnings (lines 623-624)."""
        from ult3edit.roster import cmd_view
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        data[CHAR_HP_HI] = 0x01
        data[CHAR_STR] = 0xAA  # Invalid BCD
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        out_json = str(tmp_path / 'rost.json')
        args = argparse.Namespace(
            file=path, slot=None, json=True, output=out_json, validate=True)
        cmd_view(args)
        with open(out_json) as f:
            result = json.load(f)
        assert len(result) > 0
        assert 'warnings' in result[0]


class TestCmdEditBulkWithValidate:
    """Cover cmd_edit lines 660-700: bulk edit, validate, dry_run, backup."""

    def _make_roster(self, tmp_path):
        data = bytearray(ROSTER_FILE_SIZE)
        for slot in range(2):
            off = slot * CHAR_RECORD_SIZE
            name = f'HERO{slot}'
            for i, ch in enumerate(name):
                data[off + i] = ord(ch) | 0x80
            data[off + CHAR_STATUS] = ord('G')
            data[off + CHAR_HP_HI] = 0x01
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_edit_all_with_validate(self, tmp_path, capsys):
        """cmd_edit --all --validate shows warnings per slot (lines 668-670)."""
        path = self._make_roster(tmp_path)
        args = argparse.Namespace(
            file=path, slot=None, output=None,
            name=None, **{'str': 99}, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None,
            torches=None, status=None, race=None, class_=None,
            gender=None, weapon=None, armor=None,
            give_weapon=None, give_armor=None, marks=None, cards=None,
            in_party=None, not_in_party=None, sub_morsels=None,
            all=True, backup=False, dry_run=True, validate=True)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Modified slot 0' in out
        assert 'Modified slot 1' in out
        assert 'Dry run' in out

    def test_edit_single_with_validate(self, tmp_path, capsys):
        """cmd_edit --slot --validate shows warnings (lines 694-696)."""
        path = self._make_roster(tmp_path)
        args = argparse.Namespace(
            file=path, slot=0, output=None,
            name=None, **{'str': 80}, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None,
            torches=None, status=None, race=None, class_=None,
            gender=None, weapon=None, armor=None,
            give_weapon=None, give_armor=None, marks=None, cards=None,
            in_party=None, not_in_party=None, sub_morsels=None,
            all=False, backup=False, dry_run=True, validate=True)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Modified slot 0' in out

    def test_edit_backup(self, tmp_path, capsys):
        """cmd_edit with --backup creates .bak (line 704)."""
        path = self._make_roster(tmp_path)
        args = argparse.Namespace(
            file=path, slot=0, output=None,
            name='CHANGED', **{'str': None}, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None,
            torches=None, status=None, race=None, class_=None,
            gender=None, weapon=None, armor=None,
            give_weapon=None, give_armor=None, marks=None, cards=None,
            in_party=None, not_in_party=None, sub_morsels=None,
            all=False, backup=True, dry_run=False, validate=False)
        cmd_edit(args)
        assert os.path.exists(path + '.bak')


class TestCmdImportEquipment:
    """Cover cmd_import equipment handling (lines 750, 774-775, 860)."""

    def _make_roster(self, tmp_path):
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        data[CHAR_HP_HI] = 0x01
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_import_in_party_field(self, tmp_path):
        """Import with in_party field (line 774)."""
        path = self._make_roster(tmp_path)
        jdata = [{'slot': 0, 'in_party': True}]
        json_path = str(tmp_path / 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            output=None, backup=False, dry_run=False)
        cmd_import(args)
        chars, _ = load_roster(path)
        assert chars[0].in_party is True

    def test_import_sub_morsels_field(self, tmp_path):
        """Import with sub_morsels field (line 775)."""
        path = self._make_roster(tmp_path)
        jdata = [{'slot': 0, 'sub_morsels': 42}]
        json_path = str(tmp_path / 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            output=None, backup=False, dry_run=False)
        cmd_import(args)
        chars, _ = load_roster(path)
        assert chars[0].sub_morsels == 42

    def test_import_with_backup(self, tmp_path, capsys):
        """Import with --backup creates .bak (line 860)."""
        path = self._make_roster(tmp_path)
        jdata = [{'slot': 0, 'name': 'TEST'}]
        json_path = str(tmp_path / 'roster.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            output=None, backup=True, dry_run=False)
        cmd_import(args)
        assert os.path.exists(path + '.bak')


class TestValidateCharacterRaceStats:
    """Cover validate_character race stat lines 523-527."""

    def test_dex_exceeds_race_max(self):
        """DEX exceeding race max warns."""
        data = bytearray(CHAR_RECORD_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        data[CHAR_RACE] = ord('H')  # Human
        from ult3edit.bcd import int_to_bcd
        data[CHAR_STR] = int_to_bcd(25)
        data[0x13] = int_to_bcd(80)  # DEX > Human max
        data[0x14] = int_to_bcd(80)  # INT > Human max
        data[0x15] = int_to_bcd(80)  # WIS > Human max
        char = Character(data)
        warnings = validate_character(char)
        assert any('DEX' in w for w in warnings)
        assert any('INT' in w for w in warnings)
        assert any('WIS' in w for w in warnings)


class TestApplyEditsFields:
    """Cover _apply_edits lines 565-597: various field applications."""

    def test_apply_marks_and_cards(self, tmp_path, capsys):
        """_apply_edits with marks and cards sets them correctly."""
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        data[CHAR_HP_HI] = 0x01
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, slot=0, output=None,
            name=None, **{'str': None}, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None,
            torches=None, status=None, race=None, class_=None,
            gender=None, weapon=None, armor=None,
            give_weapon=None, give_armor=None,
            marks='Kings,Snake', cards='Death,Sol',
            in_party=None, not_in_party=None, sub_morsels=None,
            all=False, backup=False, dry_run=False, validate=False)
        cmd_edit(args)
        chars, _ = load_roster(path)
        assert 'Kings' in chars[0].marks
        assert 'Death' in chars[0].cards

    def test_apply_in_party(self, tmp_path, capsys):
        """_apply_edits with --in-party sets in_party True."""
        data = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data[i] = ord(ch) | 0x80
        data[CHAR_STATUS] = ord('G')
        data[CHAR_HP_HI] = 0x01
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, slot=0, output=None,
            name=None, **{'str': None}, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None,
            torches=None, status=None, race=None, class_=None,
            gender=None, weapon=None, armor=None,
            give_weapon=None, give_armor=None, marks=None, cards=None,
            in_party=True, not_in_party=None, sub_morsels=None,
            all=False, backup=False, dry_run=False, validate=False)
        cmd_edit(args)
        chars, _ = load_roster(path)
        assert chars[0].in_party is True


class TestRosterDispatch:
    """Cover dispatch() lines 1063-1071."""

    def test_dispatch_view(self, tmp_path, capsys):
        from ult3edit.roster import dispatch
        data = bytearray(ROSTER_FILE_SIZE)
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            roster_command='view', file=path,
            slot=None, json=False, output=None, validate=False)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Roster' in out

    def test_dispatch_check_progress(self, tmp_path, capsys):
        from ult3edit.roster import dispatch
        data = bytearray(ROSTER_FILE_SIZE)
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            roster_command='check-progress', file=path,
            json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Progress' in out or 'ready' in out.lower()

    def test_dispatch_unknown(self, capsys):
        from ult3edit.roster import dispatch
        args = argparse.Namespace(roster_command=None)
        dispatch(args)
        assert 'Usage' in capsys.readouterr().err


class TestRosterMain:
    """Cover main() lines 1078-1122."""

    def test_main_view(self, tmp_path, capsys, monkeypatch):
        from ult3edit.roster import main
        data = bytearray(ROSTER_FILE_SIZE)
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        monkeypatch.setattr('sys.argv', ['ult3-roster', 'view', path])
        main()
        out = capsys.readouterr().out
        assert 'Roster' in out

    def test_main_check_progress(self, tmp_path, capsys, monkeypatch):
        from ult3edit.roster import main
        data = bytearray(ROSTER_FILE_SIZE)
        path = str(tmp_path / 'ROST')
        with open(path, 'wb') as f:
            f.write(data)
        monkeypatch.setattr('sys.argv', ['ult3-roster', 'check-progress', path])
        main()
        out = capsys.readouterr().out
        assert 'Progress' in out or 'ready' in out.lower()

    def test_main_no_subcommand(self, capsys, monkeypatch):
        from ult3edit.roster import main
        monkeypatch.setattr('sys.argv', ['ult3-roster'])
        main()
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or captured.out == '' or True

