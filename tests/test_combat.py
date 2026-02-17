"""Tests for combat battlefield tool."""

import pytest

from u3edit.combat import CombatMap
from u3edit.constants import CON_MAP_WIDTH, CON_MAP_HEIGHT, CON_FILE_SIZE


class TestCombatMap:
    def test_parse(self, sample_con_bytes):
        cm = CombatMap(sample_con_bytes)
        assert len(cm.tiles) == CON_MAP_WIDTH * CON_MAP_HEIGHT

    def test_monster_positions(self, sample_con_bytes):
        cm = CombatMap(sample_con_bytes)
        assert cm.monster_x[0] == 5
        assert cm.monster_x[1] == 6
        assert cm.monster_y[0] == 3
        assert cm.monster_y[1] == 3

    def test_pc_positions(self, sample_con_bytes):
        cm = CombatMap(sample_con_bytes)
        assert cm.pc_x[0] == 2
        assert cm.pc_x[1] == 3
        assert cm.pc_y[0] == 8
        assert cm.pc_y[1] == 8

    def test_render(self, sample_con_bytes):
        cm = CombatMap(sample_con_bytes)
        rendered = cm.render()
        assert '@' in rendered  # PC positions
        assert 'm' in rendered  # Monster positions

    def test_to_dict(self, sample_con_bytes):
        cm = CombatMap(sample_con_bytes)
        d = cm.to_dict()
        assert 'tiles' in d
        assert 'monsters' in d
        assert 'pcs' in d
        assert len(d['tiles']) == CON_MAP_HEIGHT


class TestSizeValidation:
    def test_small_file(self):
        """Should handle files smaller than expected."""
        cm = CombatMap(bytes(50))
        assert len(cm.tiles) == 50
