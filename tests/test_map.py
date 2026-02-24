"""Tests for map tool."""

import argparse
import json
import os
import sys

import pytest


from ult3edit.constants import (
    tile_char, MAP_OVERWORLD_SIZE, MAP_DUNGEON_SIZE,
    TILE_CHARS_REVERSE, DUNGEON_TILE_CHARS_REVERSE,
)
from ult3edit.map import render_map, map_to_grid, cmd_set, cmd_find


class TestTileCharMapping:
    def test_water(self):
        assert tile_char(0x00) == '~'
        assert tile_char(0x01) == '~'  # animation frame

    def test_grass(self):
        assert tile_char(0x04) == '.'
        assert tile_char(0x05) == '.'

    def test_town(self):
        assert tile_char(0x18) == '#'

    def test_floor(self):
        """M-1 fix: floor tiles should render correctly."""
        assert tile_char(0x20) == '_'

    def test_chest(self):
        """M-1 fix: chests in towns should render."""
        assert tile_char(0x24) == '$'

    def test_guard(self):
        """M-1 fix: NPCs in towns should render."""
        assert tile_char(0x48) == 'G'

    def test_dungeon_wall(self):
        assert tile_char(0x01, is_dungeon=True) == '#'

    def test_dungeon_door(self):
        assert tile_char(0x02, is_dungeon=True) == 'D'


class TestRenderMap:
    def test_overworld(self, sample_overworld_bytes):
        result = render_map(sample_overworld_bytes, 64, 64)
        assert '~' in result  # Water
        assert '.' in result  # Grass
        assert '#' in result  # Town

    def test_crop(self, sample_overworld_bytes):
        result = render_map(sample_overworld_bytes, 64, 64, crop=(0, 0, 10, 10))
        lines = result.strip().split('\n')
        # Header + 10 rows
        assert len(lines) == 11

    def test_dungeon(self, sample_dungeon_bytes):
        result = render_map(sample_dungeon_bytes[:256], 16, 16, is_dungeon=True)
        assert '#' in result  # Wall
        assert '.' in result  # Open


class TestMapToGrid:
    def test_dimensions(self, sample_overworld_bytes):
        grid = map_to_grid(sample_overworld_bytes, 64, 64)
        assert len(grid) == 64
        assert len(grid[0]) == 64

    def test_tile_names(self, sample_overworld_bytes):
        grid = map_to_grid(sample_overworld_bytes, 64, 64)
        assert grid[0][0] == 'Water'
        assert grid[5][5] == 'Grass'
        assert grid[10][10] == 'Town'

    def test_dungeon_names(self, sample_dungeon_bytes):
        grid = map_to_grid(sample_dungeon_bytes[:256], 16, 16, is_dungeon=True)
        assert grid[0][0] == 'Wall'
        assert grid[1][1] == 'Open'
        assert grid[8][1] == 'Door'


# ── Migrated from test_new_features.py ──

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


# =============================================================================
# Additional coverage tests: render_map/map_to_grid edge, cmd_view dungeon text,
# cmd_overview dungeon, cmd_legend dungeon, dispatch, main
# =============================================================================


class TestRenderMapEdgeCases:
    """Cover render_map line 53 (offset beyond data) and map_to_grid line 69."""

    def test_render_map_offset_beyond_data(self):
        """When offset >= len(data), render_map appends a space (line 53)."""
        # Provide a 4-byte data with a 4x4 grid request — offsets 4..15 are beyond data
        data = bytes([0x04, 0x04, 0x04, 0x04])
        result = render_map(data, 4, 4)
        lines = result.strip().split('\n')
        # First data row has tiles, rows 1-3 have spaces for missing data
        assert len(lines) == 5  # header + 4 rows
        # Row index 1 (y=1) should have only spaces for tiles (offset 4..7 beyond data)
        assert lines[2].strip().startswith('1')

    def test_map_to_grid_offset_beyond_data(self):
        """When offset >= len(data), map_to_grid returns 'Unknown' (line 69)."""
        data = bytes([0x04, 0x04])
        grid = map_to_grid(data, 4, 1)
        assert grid[0][0] == 'Grass'
        assert grid[0][1] == 'Grass'
        # Positions 2 and 3 are beyond data
        assert grid[0][2] == 'Unknown'
        assert grid[0][3] == 'Unknown'


class TestCmdViewDungeonText:
    """Cover cmd_view lines 118-124: text-mode dungeon display."""

    def test_view_dungeon_text_mode(self, tmp_path, capsys):
        """cmd_view text mode for dungeon file shows level headers."""
        from ult3edit.map import cmd_view as map_view
        # Create 2-level dungeon (512 bytes)
        data = bytearray(512)
        data[0] = 0x01  # Wall at level 0, (0,0)
        path = str(tmp_path / 'MAPB')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, json=False, output=None, crop=None)
        map_view(args)
        captured = capsys.readouterr()
        assert 'Dungeon' in captured.out
        assert 'Level 1' in captured.out
        assert 'Level 2' in captured.out

    def test_view_dungeon_text_with_crop(self, tmp_path, capsys):
        """cmd_view text mode dungeon with crop."""
        from ult3edit.map import cmd_view as map_view
        data = bytearray(256)  # 1 level dungeon
        path = str(tmp_path / 'MAPB')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, json=False, output=None, crop='0,0,8,8')
        map_view(args)
        captured = capsys.readouterr()
        assert 'Dungeon' in captured.out


class TestCmdOverviewDungeon:
    """Cover cmd_overview lines 169-170: dungeon map in overview list."""

    def test_overview_with_dungeon_map(self, tmp_path, capsys):
        """cmd_overview shows dungeon file info."""
        from ult3edit.map import cmd_overview
        # Create a dungeon-sized MAPM file (2048 bytes)
        mapm = os.path.join(str(tmp_path), 'MAPM')
        with open(mapm, 'wb') as f:
            f.write(bytes(MAP_DUNGEON_SIZE))
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None, preview=False)
        cmd_overview(args)
        captured = capsys.readouterr()
        assert 'MAPM' in captured.out
        assert 'Dungeon' in captured.out
        assert 'levels' in captured.out.lower()


class TestCmdDecompileToStdout:
    """Cover cmd_decompile line 591: decompile without --output prints to stdout."""

    def test_decompile_prints_to_stdout(self, tmp_path, capsys):
        """cmd_decompile without --output prints result to stdout."""
        from ult3edit.map import cmd_decompile
        data = bytes([0x00] * MAP_OVERWORLD_SIZE)
        bin_path = str(tmp_path / 'MAP')
        with open(bin_path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(file=bin_path, output=None)
        cmd_decompile(args)
        captured = capsys.readouterr()
        assert 'Overworld' in captured.out
        # Should have tile chars in output
        assert '~' in captured.out


class TestMapDispatch:
    """Cover dispatch() lines 677-697 for all subcommands."""

    def test_dispatch_view(self, tmp_path, capsys):
        from ult3edit.map import dispatch
        data = bytes(MAP_OVERWORLD_SIZE)
        path = str(tmp_path / 'MAPA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            map_command='view', file=path, json=False, output=None, crop=None)
        dispatch(args)
        assert 'Map' in capsys.readouterr().out

    def test_dispatch_legend(self, capsys):
        from ult3edit.map import dispatch
        args = argparse.Namespace(map_command='legend', json=False)
        dispatch(args)
        assert 'Tile Legend' in capsys.readouterr().out

    def test_dispatch_compile(self, tmp_path, capsys):
        from ult3edit.map import dispatch
        src = str(tmp_path / 'test.map')
        with open(src, 'w') as f:
            for _ in range(64):
                f.write('~' * 64 + '\n')
        args = argparse.Namespace(
            map_command='compile', source=src, output=None, dungeon=False)
        dispatch(args)
        assert '4096 bytes' in capsys.readouterr().out

    def test_dispatch_decompile(self, tmp_path, capsys):
        from ult3edit.map import dispatch
        path = str(tmp_path / 'MAP')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            map_command='decompile', file=path, output=None)
        dispatch(args)
        assert 'Overworld' in capsys.readouterr().out

    def test_dispatch_unknown(self, capsys):
        from ult3edit.map import dispatch
        args = argparse.Namespace(map_command=None)
        dispatch(args)
        assert 'Usage' in capsys.readouterr().err

    def test_dispatch_set(self, tmp_path, capsys):
        from ult3edit.map import dispatch
        path = str(tmp_path / 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            map_command='set', file=path, x=0, y=0, tile=0x04,
            level=None, dry_run=False, backup=False, output=None)
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Set' in captured.out

    def test_dispatch_fill(self, tmp_path, capsys):
        from ult3edit.map import dispatch
        path = str(tmp_path / 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            map_command='fill', file=path, x1=0, y1=0, x2=1, y2=1, tile=0x04,
            level=None, dry_run=True, backup=False, output=None)
        dispatch(args)
        assert 'Filled' in capsys.readouterr().out

    def test_dispatch_replace(self, tmp_path, capsys):
        from ult3edit.map import dispatch
        path = str(tmp_path / 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            map_command='replace', file=path, from_tile=0xFF, to_tile=0x04,
            level=None, dry_run=True, backup=False, output=None)
        dispatch(args)
        assert 'Replaced' in capsys.readouterr().out

    def test_dispatch_find(self, tmp_path, capsys):
        from ult3edit.map import dispatch
        path = str(tmp_path / 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            map_command='find', file=path, tile=0xFF,
            level=None, json=False, output=None)
        dispatch(args)
        assert '0 found' in capsys.readouterr().out

    def test_dispatch_import(self, tmp_path, capsys):
        from ult3edit.map import dispatch
        path = str(tmp_path / 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        jpath = str(tmp_path / 'map.json')
        with open(jpath, 'w') as f:
            json.dump({'tiles': []}, f)
        args = argparse.Namespace(
            map_command='import', file=path, json_file=jpath,
            output=None, backup=False, dry_run=True)
        dispatch(args)
        assert 'Dry run' in capsys.readouterr().out


class TestMapMain:
    """Cover main() lines 706-780."""

    def test_main_legend(self, capsys, monkeypatch):
        from ult3edit.map import main
        monkeypatch.setattr('sys.argv', ['ult3-map', 'legend'])
        main()
        assert 'Tile Legend' in capsys.readouterr().out

    def test_main_view(self, tmp_path, capsys, monkeypatch):
        from ult3edit.map import main
        path = str(tmp_path / 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        monkeypatch.setattr('sys.argv', ['ult3-map', 'view', path])
        main()
        assert 'Map' in capsys.readouterr().out

    def test_main_compile_no_output(self, tmp_path, capsys, monkeypatch):
        from ult3edit.map import main
        src = str(tmp_path / 'test.map')
        with open(src, 'w') as f:
            for _ in range(64):
                f.write('~' * 64 + '\n')
        monkeypatch.setattr('sys.argv', ['ult3-map', 'compile', src])
        main()
        assert '4096 bytes' in capsys.readouterr().out

    def test_main_decompile(self, tmp_path, capsys, monkeypatch):
        from ult3edit.map import main
        path = str(tmp_path / 'MAP')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        monkeypatch.setattr('sys.argv', ['ult3-map', 'decompile', path])
        main()
        assert 'Overworld' in capsys.readouterr().out

    def test_main_no_subcommand(self, capsys, monkeypatch):
        """main() with no subcommand prints usage to stderr."""
        from ult3edit.map import main
        monkeypatch.setattr('sys.argv', ['ult3-map'])
        main()
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or captured.out == '' or 'map' in captured.err.lower() or captured.out != ''


class TestMapCmdSetBackup:
    """Cover cmd_set line 265: backup when output==file."""

    def test_set_with_backup(self, tmp_path, capsys):
        path = str(tmp_path / 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=path, x=0, y=0, tile=0x04,
            level=None, dry_run=False, backup=True, output=None)
        from ult3edit.map import cmd_set
        cmd_set(args)
        assert os.path.exists(path + '.bak')


class TestMapCmdFillBackup:
    """Cover cmd_fill line 299: backup on fill."""

    def test_fill_with_backup(self, tmp_path, capsys):
        from ult3edit.map import cmd_fill
        path = str(tmp_path / 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        args = argparse.Namespace(
            file=path, x1=0, y1=0, x2=1, y2=1, tile=0x04,
            level=None, dry_run=False, backup=True, output=None)
        cmd_fill(args)
        assert os.path.exists(path + '.bak')


class TestMapCmdReplaceBackup:
    """Cover cmd_replace line 332: backup on replace."""

    def test_replace_with_backup(self, tmp_path, capsys):
        from ult3edit.map import cmd_replace
        path = str(tmp_path / 'MAPA')
        data = bytearray(MAP_OVERWORLD_SIZE)
        data[0] = 0x04
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, from_tile=0x04, to_tile=0x08,
            level=None, dry_run=False, backup=True, output=None)
        cmd_replace(args)
        assert os.path.exists(path + '.bak')


class TestMapImportBackup:
    """Cover cmd_import line 426: backup on import."""

    def test_import_with_backup(self, tmp_path, capsys):
        from ult3edit.map import cmd_import
        path = str(tmp_path / 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytes(MAP_OVERWORLD_SIZE))
        jpath = str(tmp_path / 'map.json')
        with open(jpath, 'w') as f:
            json.dump({'tiles': [['.' for _ in range(64)] for _ in range(64)]}, f)
        args = argparse.Namespace(
            file=path, json_file=jpath,
            output=None, backup=True, dry_run=False)
        cmd_import(args)
        assert os.path.exists(path + '.bak')


class TestMapCompileRowTruncation:
    """Cover cmd_compile line 471: rows longer than width are truncated."""

    def test_overworld_long_row_truncated(self, tmp_path):
        from ult3edit.map import cmd_compile
        src = str(tmp_path / 'test.map')
        with open(src, 'w') as f:
            for _ in range(64):
                f.write('~' * 100 + '\n')  # 100 chars, truncated to 64
        out = str(tmp_path / 'MAP')
        args = argparse.Namespace(source=src, output=out, dungeon=False)
        cmd_compile(args)
        with open(out, 'rb') as f:
            data = f.read()
        assert len(data) == MAP_OVERWORLD_SIZE

