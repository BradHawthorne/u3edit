"""Tests for bestiary tool."""

import os
import pytest

from u3edit.bestiary import Monster, load_mon_file, save_mon_file
from u3edit.constants import MON_FILE_SIZE, MON_MONSTERS_PER_FILE


class TestMonster:
    def test_name_fighter(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert monsters[0].name == 'Fighter'

    def test_name_dragon(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert monsters[1].name == 'Dragon'

    def test_name_skeleton(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert monsters[2].name == 'Skeleton'

    def test_hp(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert monsters[0].hp == 50
        assert monsters[1].hp == 200

    def test_boss_flag(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert 'Boss' in monsters[1].flag_desc

    def test_undead_flag(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert 'Undead' in monsters[2].flag_desc

    def test_empty(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert monsters[3].is_empty
        assert not monsters[0].is_empty


class TestToDict:
    def test_keys(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        d = monsters[0].to_dict()
        assert 'name' in d
        assert 'hp' in d
        assert 'attack' in d
        assert 'defense' in d


class TestLoadSave:
    def test_load(self, sample_mon_file):
        monsters = load_mon_file(sample_mon_file)
        assert len(monsters) == 16
        assert monsters[0].name == 'Fighter'

    def test_roundtrip(self, sample_mon_file, tmp_dir):
        monsters = load_mon_file(sample_mon_file)
        monsters[0].hp = 99
        output = os.path.join(tmp_dir, 'MONA_OUT')
        save_mon_file(output, monsters)

        monsters2 = load_mon_file(output)
        assert monsters2[0].hp == 99
        assert monsters2[1].name == 'Dragon'  # Other monsters preserved


def load_mon_file_from_bytes(data: bytes):
    """Helper to load monsters directly from bytes without a file."""
    from u3edit.bestiary import Monster
    from u3edit.constants import MON_ATTR_COUNT, MON_MONSTERS_PER_FILE

    monsters = []
    for i in range(MON_MONSTERS_PER_FILE):
        attrs = []
        for row in range(MON_ATTR_COUNT):
            offset = row * MON_MONSTERS_PER_FILE + i
            attrs.append(data[offset] if offset < len(data) else 0)
        monsters.append(Monster(attrs, i))
    return monsters
