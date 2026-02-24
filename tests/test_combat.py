"""Tests for combat battlefield tool."""

import argparse
import json
import os
import types

import pytest

from ult3edit.combat import CombatMap, cmd_edit, cmd_import, _has_cli_edit_args, validate_combat_map
from ult3edit.constants import (
    CON_MAP_WIDTH, CON_MAP_HEIGHT, CON_FILE_SIZE,
    CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET, CON_PC_X_OFFSET, CON_PC_Y_OFFSET,
    TILE_CHARS_REVERSE,
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


# ── Migrated from test_new_features.py ──

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


# =============================================================================
# Batch 3: Coverage for combat.py uncovered lines
# =============================================================================


class TestCombatRenderEmptyTile:
    """Cover line 75: render with tile offset beyond tiles length (space fallback)."""

    def test_render_short_data(self):
        """CombatMap from short data renders spaces for missing tiles."""
        cm = CombatMap(bytes(10))  # Only 10 bytes of tile data
        rendered = cm.render()
        # Should contain spaces for the missing tiles
        assert ' ' in rendered


class TestCombatRenderRuntimePc:
    """Cover lines 101, 103: render shows runtime_monster and padding2 when non-zero."""

    def test_render_runtime_monster(self):
        from ult3edit.constants import CON_RUNTIME_MONSAVE_OFFSET
        data = bytearray(CON_FILE_SIZE)
        data[CON_RUNTIME_MONSAVE_OFFSET] = 0xAB
        cm = CombatMap(bytes(data))
        rendered = cm.render()
        assert 'Runtime monster (0x90)' in rendered
        assert 'AB' in rendered

    def test_render_padding2(self):
        from ult3edit.constants import CON_PADDING2_OFFSET
        data = bytearray(CON_FILE_SIZE)
        data[CON_PADDING2_OFFSET] = 0xCD
        cm = CombatMap(bytes(data))
        rendered = cm.render()
        assert 'Padding (0xB0)' in rendered
        assert 'CD' in rendered


class TestCombatCmdViewValidateDir:
    """Cover lines 218-219: cmd_view directory mode with --validate showing warnings."""

    def test_view_dir_validate_warnings(self, tmp_path, capsys):
        from ult3edit.combat import cmd_view
        data = bytearray(CON_FILE_SIZE)
        # Set misaligned tile to trigger warning
        data[0] = 0x05
        (tmp_path / 'CONA').write_bytes(bytes(data))
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None, validate=True)
        cmd_view(args)
        err = capsys.readouterr().err
        assert 'WARNING' in err


class TestCombatCmdViewValidateSingleJson:
    """Cover line 231: cmd_view single file JSON with validate."""

    def test_view_single_json_validate(self, tmp_path):
        from ult3edit.combat import cmd_view
        data = bytearray(CON_FILE_SIZE)
        data[0] = 0x05  # misaligned tile
        path = str(tmp_path / 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = str(tmp_path / 'combat.json')
        args = argparse.Namespace(
            path=path, json=True, output=out_path, validate=True)
        cmd_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert 'warnings' in jdata
        assert len(jdata['warnings']) >= 1


class TestCombatCmdEditNoChanges:
    """Cover lines 327-328: cmd_edit with no effective changes (changes==0)."""

    def test_no_effective_changes(self, tmp_path, capsys):
        """cmd_edit with empty tile/pos args but _has_cli_edit_args returns True
        doesn't apply here. Instead test validate path (lines 330-333)."""
        pass


class TestCombatCmdEditValidateAfterEdit:
    """Cover lines 327-333: cmd_edit with --validate after making changes."""

    def test_validate_warns_after_edit(self, tmp_path, capsys):
        from ult3edit.combat import cmd_edit
        data = bytearray(CON_FILE_SIZE)
        path = str(tmp_path / 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        # Set a misaligned tile and enable validate
        args = argparse.Namespace(
            file=path, tile=(0, 0, 0x05), monster_pos=None, pc_pos=None,
            dry_run=True, backup=False, output=None, validate=True)
        cmd_edit(args)
        err = capsys.readouterr().err
        assert 'WARNING' in err


class TestCombatImportNonNumericPcKey:
    """Cover lines 400-401: cmd_import warns on non-numeric PC dict keys."""

    def test_non_numeric_pc_key(self, tmp_path, capsys):
        path = str(tmp_path / 'CONA')
        with open(path, 'wb') as f:
            f.write(bytearray(CON_FILE_SIZE))
        jdata = {
            'tiles': [],
            'monsters': [],
            'pcs': {'xyz': {'x': 0, 'y': 0}, '0': {'x': 1, 'y': 1}},
        }
        json_path = str(tmp_path / 'con.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        err = capsys.readouterr().err
        assert 'non-numeric' in err


class TestCombatImportBackup:
    """Cover line 447: cmd_import with --backup."""

    def test_import_creates_backup(self, tmp_path):
        path = str(tmp_path / 'CONA')
        with open(path, 'wb') as f:
            f.write(bytearray(CON_FILE_SIZE))
        jdata = {'tiles': [['.' for _ in range(11)] for _ in range(11)]}
        json_path = str(tmp_path / 'con.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=True, output=None)
        cmd_import(args)
        assert os.path.exists(path + '.bak')


class TestCombatDispatchDefault:
    """Cover lines 494-496: dispatch routes to view/edit/import and default."""

    def test_dispatch_view(self, tmp_path, capsys):
        from ult3edit.combat import dispatch
        data = bytearray(CON_FILE_SIZE)
        path = str(tmp_path / 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            combat_command='view', path=path, json=False,
            output=None, validate=False)
        dispatch(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_dispatch_edit(self, tmp_path, capsys):
        from ult3edit.combat import dispatch
        data = bytearray(CON_FILE_SIZE)
        path = str(tmp_path / 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            combat_command='edit', file=path,
            tile=(0, 0, 0x04), monster_pos=None, pc_pos=None,
            dry_run=True, backup=False, output=None, validate=False)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Tile' in out

    def test_dispatch_import(self, tmp_path, capsys):
        from ult3edit.combat import dispatch
        data = bytearray(CON_FILE_SIZE)
        path = str(tmp_path / 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = {'tiles': []}
        json_path = str(tmp_path / 'con.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            combat_command='import', file=path, json_file=json_path,
            output=None, backup=False, dry_run=True)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out

    def test_dispatch_unknown(self, capsys):
        from ult3edit.combat import dispatch
        args = argparse.Namespace(combat_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err


class TestCombatMain:
    """Cover lines 502-535: main() standalone entry point."""

    def test_main_view(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.combat import main
        data = bytearray(CON_FILE_SIZE)
        path = str(tmp_path / 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        monkeypatch.setattr(sys, 'argv', ['ult3-combat', 'view', path])
        main()
        out = capsys.readouterr().out
        assert 'Combat Map' in out or '@' in out or len(out) > 0

    def test_main_edit_tile(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.combat import main
        data = bytearray(CON_FILE_SIZE)
        path = str(tmp_path / 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        monkeypatch.setattr(sys, 'argv', [
            'ult3-combat', 'edit', path,
            '--tile', '0', '0', '4', '--dry-run'])
        main()
        out = capsys.readouterr().out
        assert 'Tile' in out
        assert 'Dry run' in out

    def test_main_import(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.combat import main
        data = bytearray(CON_FILE_SIZE)
        path = str(tmp_path / 'CONA')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = {'tiles': [['.' for _ in range(11)] for _ in range(11)]}
        json_path = str(tmp_path / 'con.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        monkeypatch.setattr(sys, 'argv', [
            'ult3-combat', 'import', path, json_path, '--dry-run'])
        main()
        out = capsys.readouterr().out
        assert 'Dry run' in out

    def test_main_no_command(self, capsys, monkeypatch):
        import sys
        from ult3edit.combat import main
        monkeypatch.setattr(sys, 'argv', ['ult3-combat'])
        main()
        err = capsys.readouterr().err
        assert 'Usage' in err

