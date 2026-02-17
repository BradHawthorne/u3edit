"""Tests for roster tool."""

import os
import pytest

from u3edit.roster import Character, load_roster, save_roster
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
