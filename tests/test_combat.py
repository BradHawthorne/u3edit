"""Tests for combat battlefield tool."""

import json
import os
import types

import pytest

from ult3edit.combat import CombatMap, cmd_edit, cmd_import, _has_cli_edit_args, validate_combat_map
from ult3edit.constants import (
    CON_MAP_WIDTH, CON_MAP_HEIGHT, CON_FILE_SIZE,
    CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET, CON_PC_X_OFFSET, CON_PC_Y_OFFSET,
)


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


# --- Helper to build args namespace ---

def _edit_args(file, **kwargs):
    """Build an argparse-like namespace for cmd_edit."""
    defaults = dict(
        file=file, tile=None, monster_pos=None, pc_pos=None,
        output=None, backup=False, dry_run=False,
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _import_args(file, json_file, **kwargs):
    """Build an argparse-like namespace for cmd_import."""
    defaults = dict(
        file=file, json_file=json_file,
        output=None, backup=False, dry_run=False,
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


@pytest.fixture
def con_file(tmp_dir, sample_con_bytes):
    """Write a CON file and return its path."""
    path = os.path.join(tmp_dir, 'CONA#069900')
    with open(path, 'wb') as f:
        f.write(sample_con_bytes)
    return path


class TestHasCliEditArgs:
    def test_no_args(self):
        args = _edit_args('x')
        assert not _has_cli_edit_args(args)

    def test_tile_arg(self):
        args = _edit_args('x', tile=[5, 5, 0x04])
        assert _has_cli_edit_args(args)

    def test_monster_pos_arg(self):
        args = _edit_args('x', monster_pos=[0, 3, 3])
        assert _has_cli_edit_args(args)

    def test_pc_pos_arg(self):
        args = _edit_args('x', pc_pos=[0, 1, 1])
        assert _has_cli_edit_args(args)


class TestCombatCliEditTile:
    def test_set_tile(self, con_file):
        """Set a tile and verify it was written."""
        args = _edit_args(con_file, tile=[5, 5, 0x04])
        cmd_edit(args)
        with open(con_file, 'rb') as f:
            data = f.read()
        offset = 5 * CON_MAP_WIDTH + 5
        assert data[offset] == 0x04

    def test_set_tile_boundary(self, con_file):
        """Set tile at max valid position (10, 10)."""
        args = _edit_args(con_file, tile=[10, 10, 0x08])
        cmd_edit(args)
        with open(con_file, 'rb') as f:
            data = f.read()
        offset = 10 * CON_MAP_WIDTH + 10
        assert data[offset] == 0x08

    def test_set_tile_out_of_bounds(self, con_file):
        """Tile position outside grid should fail."""
        args = _edit_args(con_file, tile=[11, 5, 0x04])
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_set_tile_dry_run(self, con_file):
        """Dry run should not write changes."""
        with open(con_file, 'rb') as f:
            original = f.read()
        args = _edit_args(con_file, tile=[5, 5, 0x04], dry_run=True)
        cmd_edit(args)
        with open(con_file, 'rb') as f:
            after = f.read()
        assert original == after

    def test_set_tile_backup(self, con_file):
        """Backup should create .bak file."""
        args = _edit_args(con_file, tile=[5, 5, 0x04], backup=True)
        cmd_edit(args)
        assert os.path.exists(con_file + '.bak')

    def test_set_tile_output(self, con_file, tmp_dir):
        """Output to a different file."""
        out_path = os.path.join(tmp_dir, 'output.bin')
        args = _edit_args(con_file, tile=[5, 5, 0x04], output=out_path)
        cmd_edit(args)
        with open(out_path, 'rb') as f:
            data = f.read()
        offset = 5 * CON_MAP_WIDTH + 5
        assert data[offset] == 0x04


class TestCombatCliEditMonsterPos:
    def test_set_monster_pos(self, con_file):
        """Set monster 0 position."""
        args = _edit_args(con_file, monster_pos=[0, 7, 7])
        cmd_edit(args)
        with open(con_file, 'rb') as f:
            data = f.read()
        assert data[CON_MONSTER_X_OFFSET + 0] == 7
        assert data[CON_MONSTER_Y_OFFSET + 0] == 7

    def test_set_monster_pos_out_of_range(self, con_file):
        """Monster index out of range should fail."""
        args = _edit_args(con_file, monster_pos=[8, 5, 5])
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_set_monster_pos_coords_out_of_bounds(self, con_file):
        """Monster position outside grid should fail."""
        args = _edit_args(con_file, monster_pos=[0, 11, 5])
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_set_monster_pos_dry_run(self, con_file):
        """Dry run should not write monster position changes."""
        with open(con_file, 'rb') as f:
            original = f.read()
        args = _edit_args(con_file, monster_pos=[0, 7, 7], dry_run=True)
        cmd_edit(args)
        with open(con_file, 'rb') as f:
            after = f.read()
        assert original == after


class TestCombatCliEditPcPos:
    def test_set_pc_pos(self, con_file):
        """Set PC 0 position."""
        args = _edit_args(con_file, pc_pos=[0, 4, 4])
        cmd_edit(args)
        with open(con_file, 'rb') as f:
            data = f.read()
        assert data[CON_PC_X_OFFSET + 0] == 4
        assert data[CON_PC_Y_OFFSET + 0] == 4

    def test_set_pc_pos_out_of_range(self, con_file):
        """PC index out of range should fail."""
        args = _edit_args(con_file, pc_pos=[4, 5, 5])
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_set_pc_pos_coords_out_of_bounds(self, con_file):
        """PC position outside grid should fail."""
        args = _edit_args(con_file, pc_pos=[0, 5, 11])
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestCombatImportDryRun:
    def test_import_dry_run(self, con_file, tmp_dir):
        """Import with --dry-run should not write."""
        with open(con_file, 'rb') as f:
            original = f.read()
        # Build JSON with different tiles
        cm = CombatMap(original)
        d = cm.to_dict()
        # Change a tile in the dict
        d['tiles'][5][5] = 'T'
        json_path = os.path.join(tmp_dir, 'import.json')
        with open(json_path, 'w') as f:
            json.dump(d, f)
        args = _import_args(con_file, json_path, dry_run=True)
        cmd_import(args)
        with open(con_file, 'rb') as f:
            after = f.read()
        assert original == after

    def test_import_writes_without_dry_run(self, con_file, tmp_dir):
        """Import without --dry-run should write changes."""
        with open(con_file, 'rb') as f:
            original = f.read()
        cm = CombatMap(original)
        d = cm.to_dict()
        d['pcs'] = [{'x': 1, 'y': 1}, {'x': 2, 'y': 2}, {'x': 3, 'y': 3}, {'x': 4, 'y': 4}]
        json_path = os.path.join(tmp_dir, 'import.json')
        with open(json_path, 'w') as f:
            json.dump(d, f)
        args = _import_args(con_file, json_path)
        cmd_import(args)
        with open(con_file, 'rb') as f:
            data = f.read()
        assert data[CON_PC_X_OFFSET] == 1
        assert data[CON_PC_Y_OFFSET] == 1


class TestValidateCombatMap:
    def test_valid_map(self, sample_con_bytes):
        """Valid map should produce no warnings."""
        cm = CombatMap(sample_con_bytes)
        assert validate_combat_map(cm) == []

    def test_misaligned_tiles(self):
        """Tiles not aligned to 4-byte boundary should warn."""
        data = bytearray(CON_FILE_SIZE)
        data[0] = 0x05  # Not a multiple of 4
        cm = CombatMap(bytes(data))
        warnings = validate_combat_map(cm)
        assert any('aligned' in w for w in warnings)

    def test_monster_out_of_bounds(self):
        """Monster position outside grid should warn."""
        data = bytearray(CON_FILE_SIZE)
        data[CON_MONSTER_X_OFFSET] = 15  # Out of 11x11 bounds
        data[CON_MONSTER_Y_OFFSET] = 5
        cm = CombatMap(bytes(data))
        warnings = validate_combat_map(cm)
        assert any('Monster 0' in w and 'out of bounds' in w for w in warnings)

    def test_pc_out_of_bounds(self):
        """PC position outside grid should warn."""
        data = bytearray(CON_FILE_SIZE)
        data[CON_PC_X_OFFSET] = 11  # Out of bounds
        data[CON_PC_Y_OFFSET] = 5
        cm = CombatMap(bytes(data))
        warnings = validate_combat_map(cm)
        assert any('PC 0' in w and 'out of bounds' in w for w in warnings)

    def test_overlapping_positions(self):
        """Overlapping start positions should warn."""
        data = bytearray(CON_FILE_SIZE)
        # Monster 0 and PC 0 at same position
        data[CON_MONSTER_X_OFFSET] = 5
        data[CON_MONSTER_Y_OFFSET] = 5
        data[CON_PC_X_OFFSET] = 5
        data[CON_PC_Y_OFFSET] = 5
        cm = CombatMap(bytes(data))
        warnings = validate_combat_map(cm)
        assert any('overlaps' in w for w in warnings)
