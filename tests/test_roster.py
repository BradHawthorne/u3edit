"""Tests for roster tool."""

import argparse
import os
import pytest

from u3edit.roster import Character, load_roster, save_roster, cmd_edit, cmd_create
from u3edit.constants import CHAR_RECORD_SIZE, CHAR_MARKS_CARDS


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
