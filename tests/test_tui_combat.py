"""Tests for CombatEditor data handling (no terminal needed)."""

from ult3edit.constants import (
    CON_FILE_SIZE, CON_MAP_WIDTH,
    CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET, CON_MONSTER_COUNT,
    CON_PC_X_OFFSET, CON_PC_Y_OFFSET, CON_PC_COUNT,
)
from ult3edit.tui.combat_editor import CombatEditor


class TestPositionExtraction:
    def test_monster_positions(self, sample_con_bytes):
        editor = CombatEditor.__new__(CombatEditor)
        data = bytearray(sample_con_bytes)
        editor.full_data = data
        editor.monster_x = [data[CON_MONSTER_X_OFFSET + i] for i in range(CON_MONSTER_COUNT)]
        editor.monster_y = [data[CON_MONSTER_Y_OFFSET + i] for i in range(CON_MONSTER_COUNT)]
        assert editor.monster_x[0] == 5
        assert editor.monster_y[0] == 3

    def test_pc_positions(self, sample_con_bytes):
        editor = CombatEditor.__new__(CombatEditor)
        data = bytearray(sample_con_bytes)
        editor.full_data = data
        editor.pc_x = [data[CON_PC_X_OFFSET + i] for i in range(CON_PC_COUNT)]
        editor.pc_y = [data[CON_PC_Y_OFFSET + i] for i in range(CON_PC_COUNT)]
        assert editor.pc_x[0] == 2
        assert editor.pc_y[0] == 8


class TestSerialization:
    def test_save_roundtrip(self, sample_con_bytes, tmp_dir):
        import os
        path = os.path.join(tmp_dir, 'test_con')
        with open(path, 'wb') as f:
            f.write(sample_con_bytes)

        editor = CombatEditor(path, sample_con_bytes)
        # Modify a tile
        editor.state.set_tile(5, 5, 0x04)
        # Modify monster position
        editor.monster_x[2] = 7
        editor.monster_y[2] = 9
        editor._save()

        with open(path, 'rb') as f:
            saved = f.read()
        assert len(saved) == CON_FILE_SIZE
        assert saved[5 * CON_MAP_WIDTH + 5] == 0x04
        assert saved[CON_MONSTER_X_OFFSET + 2] == 7
        assert saved[CON_MONSTER_Y_OFFSET + 2] == 9

    def test_preserves_padding(self, sample_con_bytes, tmp_dir):
        import os
        # Set some padding bytes to non-zero
        data = bytearray(sample_con_bytes)
        data[0x79] = 0xAB  # Padding between tiles and monster pos
        path = os.path.join(tmp_dir, 'test_con2')
        with open(path, 'wb') as f:
            f.write(data)

        editor = CombatEditor(path, bytes(data))
        editor._save()

        with open(path, 'rb') as f:
            saved = f.read()
        assert saved[0x79] == 0xAB  # Padding preserved
