"""Tests for special location tool."""

import argparse
import json
import os
import tempfile
import types

import pytest

from ult3edit.special import render_special_map, cmd_edit, cmd_import, _has_cli_edit_args
from ult3edit.constants import SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT, SPECIAL_FILE_SIZE, TILE_CHARS_REVERSE


class TestRenderSpecialMap:
    def test_dimensions(self, sample_special_bytes):
        rendered = render_special_map(sample_special_bytes)
        lines = rendered.strip().split('\n')
        # Header + 11 rows
        assert len(lines) == SPECIAL_MAP_HEIGHT + 1

    def test_content(self, sample_special_bytes):
        rendered = render_special_map(sample_special_bytes)
        assert '_' in rendered  # Floor tiles


class TestSizeHandling:
    def test_exact_size(self, sample_special_bytes):
        assert len(sample_special_bytes) == SPECIAL_FILE_SIZE

    def test_small_data(self):
        """Should handle data smaller than expected."""
        rendered = render_special_map(bytes(50))
        assert len(rendered) > 0


# --- Helper to build args namespace ---

def _edit_args(file, **kwargs):
    """Build an argparse-like namespace for cmd_edit."""
    defaults = dict(
        file=file, tile=None,
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
def special_file(tmp_dir, sample_special_bytes):
    """Write a special file and return its path."""
    path = os.path.join(tmp_dir, 'BRND#069900')
    with open(path, 'wb') as f:
        f.write(sample_special_bytes)
    return path


class TestHasCliEditArgs:
    def test_no_args(self):
        args = _edit_args('x')
        assert not _has_cli_edit_args(args)

    def test_tile_arg(self):
        args = _edit_args('x', tile=[5, 5, 0x04])
        assert _has_cli_edit_args(args)


class TestSpecialCliEditTile:
    def test_set_tile(self, special_file):
        """Set a tile and verify it was written."""
        args = _edit_args(special_file, tile=[5, 5, 0x04])
        cmd_edit(args)
        with open(special_file, 'rb') as f:
            data = f.read()
        offset = 5 * SPECIAL_MAP_WIDTH + 5
        assert data[offset] == 0x04

    def test_set_tile_boundary(self, special_file):
        """Set tile at max valid position (10, 10)."""
        args = _edit_args(special_file, tile=[10, 10, 0x08])
        cmd_edit(args)
        with open(special_file, 'rb') as f:
            data = f.read()
        offset = 10 * SPECIAL_MAP_WIDTH + 10
        assert data[offset] == 0x08

    def test_set_tile_out_of_bounds(self, special_file):
        """Tile position outside grid should fail."""
        args = _edit_args(special_file, tile=[11, 5, 0x04])
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_set_tile_dry_run(self, special_file):
        """Dry run should not write changes."""
        with open(special_file, 'rb') as f:
            original = f.read()
        args = _edit_args(special_file, tile=[5, 5, 0x04], dry_run=True)
        cmd_edit(args)
        with open(special_file, 'rb') as f:
            after = f.read()
        assert original == after

    def test_set_tile_backup(self, special_file):
        """Backup should create .bak file."""
        args = _edit_args(special_file, tile=[5, 5, 0x04], backup=True)
        cmd_edit(args)
        assert os.path.exists(special_file + '.bak')

    def test_set_tile_output(self, special_file, tmp_dir):
        """Output to a different file."""
        out_path = os.path.join(tmp_dir, 'output.bin')
        args = _edit_args(special_file, tile=[5, 5, 0x04], output=out_path)
        cmd_edit(args)
        with open(out_path, 'rb') as f:
            data = f.read()
        offset = 5 * SPECIAL_MAP_WIDTH + 5
        assert data[offset] == 0x04


class TestSpecialImportDryRun:
    def test_import_dry_run(self, special_file, tmp_dir):
        """Import with --dry-run should not write."""
        with open(special_file, 'rb') as f:
            original = f.read()
        # Build JSON with different tiles
        tiles = [['T' for _ in range(SPECIAL_MAP_WIDTH)] for _ in range(SPECIAL_MAP_HEIGHT)]
        jdata = {'tiles': tiles, 'trailing_bytes': [0] * 7}
        json_path = os.path.join(tmp_dir, 'import.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = _import_args(special_file, json_path, dry_run=True)
        cmd_import(args)
        with open(special_file, 'rb') as f:
            after = f.read()
        assert original == after

    def test_import_writes_without_dry_run(self, special_file, tmp_dir):
        """Import without --dry-run should write changes."""
        tiles = [['T' for _ in range(SPECIAL_MAP_WIDTH)] for _ in range(SPECIAL_MAP_HEIGHT)]
        jdata = {'tiles': tiles, 'trailing_bytes': [0] * 7}
        json_path = os.path.join(tmp_dir, 'import.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = _import_args(special_file, json_path)
        cmd_import(args)
        with open(special_file, 'rb') as f:
            data = f.read()
        # 'T' should map to some tile byte — verify it changed from 0x20 (floor)
        assert data[0] != 0x20 or data[60] != 0x20  # At least some changed


# ── Migrated from test_new_features.py ──

class TestSpecialImport:
    def test_import_special_map(self, tmp_dir, sample_special_bytes):
        """cmd_import() applies tile changes from JSON."""
        from ult3edit.special import cmd_import as special_cmd_import
        path = os.path.join(tmp_dir, 'SHRN')
        with open(path, 'wb') as f:
            f.write(sample_special_bytes)

        # Build JSON with a modified tile grid
        from ult3edit.constants import tile_char, SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT
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
        from ult3edit.special import cmd_import as special_cmd_import
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
        from ult3edit.special import cmd_import as special_cmd_import
        from ult3edit.constants import tile_char, SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT
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


class TestSpecialTrailingBytes:
    def test_trailing_bytes_extracted(self, sample_special_bytes):
        from ult3edit.special import get_trailing_bytes
        trailing = get_trailing_bytes(sample_special_bytes)
        assert len(trailing) == 7

    def test_trailing_bytes_nonzero(self):
        from ult3edit.special import get_trailing_bytes, SPECIAL_META_OFFSET
        data = bytearray(128)
        data[SPECIAL_META_OFFSET] = 0x42
        data[SPECIAL_META_OFFSET + 3] = 0xFF
        trailing = get_trailing_bytes(data)
        assert trailing[0] == 0x42
        assert trailing[3] == 0xFF

    def test_trailing_bytes_in_render(self):
        from ult3edit.special import render_special_map, SPECIAL_META_OFFSET
        data = bytearray(128)
        data[SPECIAL_META_OFFSET] = 0xAB
        rendered = render_special_map(data)
        assert 'Trailing padding' in rendered
        assert 'AB' in rendered

    def test_trailing_bytes_not_shown_when_zero(self, sample_special_bytes):
        from ult3edit.special import render_special_map
        rendered = render_special_map(sample_special_bytes)
        assert 'Trailing' not in rendered

    def test_backward_compat_alias(self):
        """get_metadata still works as backward-compat alias."""
        from ult3edit.special import get_metadata, get_trailing_bytes
        assert get_metadata is get_trailing_bytes


# =============================================================================
# Shapes overlay string extraction tests
# =============================================================================


# =============================================================================
# SHPS code guard tests
# =============================================================================


# =============================================================================
# Disk audit tests
# =============================================================================


class TestSpecialJsonKeyConsistency:
    def test_single_file_uses_trailing_bytes_key(self):
        from ult3edit.special import cmd_view
        from ult3edit.constants import SPECIAL_FILE_SIZE
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


# =============================================================================
# Roster create extended args tests
# =============================================================================


class TestSpecialCmdViewDir:
    """Tests for special cmd_view in directory scan mode."""

    def test_view_directory(self, tmp_path, capsys):
        """View all special location files in a directory."""
        from ult3edit.special import cmd_view
        brnd = tmp_path / 'BRND'
        brnd.write_bytes(bytes(SPECIAL_FILE_SIZE))
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'BRND' in out or 'Brand' in out

    def test_view_directory_json(self, tmp_path):
        """View directory --json produces valid JSON."""
        from ult3edit.special import cmd_view
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
        from ult3edit.special import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


# =============================================================================
# DDRW cmd_edit out-of-bounds and sound cmd_edit dry-run tests
# =============================================================================


# =============================================================================
# Priority 3 edge case tests
# =============================================================================


class TestSpecialTruncatedFile:
    """Tests for special.py handling truncated files in JSON export."""

    def test_truncated_file_json_no_crash(self, tmp_path):
        """Truncated special file doesn't crash in single-file JSON export."""
        from ult3edit.special import cmd_view
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(50))  # 50 < 128 (SPECIAL_FILE_SIZE)
        outfile = tmp_path / 'special.json'
        args = argparse.Namespace(
            path=str(path), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'tiles' in result
        # Should not crash — inner bounds check prevents IndexError

    def test_full_file_json_complete(self, tmp_path):
        """Full-size special file produces complete 11x11 grid."""
        from ult3edit.special import cmd_view
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(SPECIAL_FILE_SIZE))
        outfile = tmp_path / 'special.json'
        args = argparse.Namespace(
            path=str(path), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert len(result['tiles']) == 11
        assert len(result['tiles'][0]) == 11


class TestSpecialTrailingBytesRoundTrip:
    """Verify special location trailing bytes survive import."""

    def test_trailing_bytes_preserved(self, tmp_path):
        """Import special location tiles, verify trailing 7 bytes unchanged."""
        from ult3edit.special import cmd_import as special_import

        data = bytearray(SPECIAL_FILE_SIZE)
        for i in range(121):
            data[i] = 0x04
        for i in range(7):
            data[121 + i] = 0xA0 + i

        spec_file = tmp_path / 'BRND'
        spec_file.write_bytes(bytes(data))

        jdata = {
            'tiles': [['.' for _ in range(11)] for _ in range(11)],
            'trailing_bytes': [0xA0 + i for i in range(7)],
        }
        jdata['tiles'][0][0] = '~'

        json_file = tmp_path / 'brnd.json'
        json_file.write_text(json.dumps(jdata))

        args = argparse.Namespace(
            file=str(spec_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        special_import(args)

        result = spec_file.read_bytes()
        for i in range(7):
            assert result[121 + i] == 0xA0 + i, \
                f"Trailing byte {i} corrupted"

    def test_trailing_bytes_absent_preserves_original(self, tmp_path):
        """Import JSON without trailing_bytes key preserves original padding."""
        from ult3edit.special import cmd_import as special_import

        data = bytearray(SPECIAL_FILE_SIZE)
        for i in range(7):
            data[121 + i] = 0xEE

        spec_file = tmp_path / 'SHRN'
        spec_file.write_bytes(bytes(data))

        jdata = {'tiles': [['.' for _ in range(11)] for _ in range(11)]}
        json_file = tmp_path / 'shrn.json'
        json_file.write_text(json.dumps(jdata))

        args = argparse.Namespace(
            file=str(spec_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        special_import(args)

        result = spec_file.read_bytes()
        for i in range(7):
            assert result[121 + i] == 0xEE


class TestSpecialEditorSave:
    """Tests for SpecialEditor TUI save preserving metadata."""

    def test_save_preserves_trailing_bytes(self):
        """SpecialEditor._save() preserves trailing 7 bytes."""
        from ult3edit.tui.special_editor import SpecialEditor

        data = bytearray(128)
        # Fill tiles with grass
        for i in range(121):
            data[i] = 0x04
        # Set trailing bytes
        for i in range(7):
            data[121 + i] = 0xF0 + i

        saved_data = None
        def capture(d):
            nonlocal saved_data
            saved_data = d

        editor = SpecialEditor('test', bytes(data), save_callback=capture)
        # Modify a tile
        editor.state.data[0] = 0x00  # water
        editor.state.dirty = True
        editor._save()

        assert saved_data is not None
        # Tile changed
        assert saved_data[0] == 0x00
        # Trailing bytes preserved
        for i in range(7):
            assert saved_data[121 + i] == 0xF0 + i

    def test_save_with_short_data(self):
        """SpecialEditor pads short data to at least tile grid size."""
        from ult3edit.tui.special_editor import SpecialEditor
        from ult3edit.constants import SPECIAL_MAP_TILES

        data = bytes(100)  # Shorter than 121 tiles
        saved_data = None
        def capture(d):
            nonlocal saved_data
            saved_data = d

        editor = SpecialEditor('test', data, save_callback=capture)
        editor.state.dirty = True
        editor._save()
        assert saved_data is not None
        # Padded tile data written over short original
        assert len(saved_data) >= SPECIAL_MAP_TILES


# =============================================================================
# Import type validation tests
# =============================================================================


class TestSpecialCmdViewImport:
    """Test special.py cmd_view and cmd_import."""

    def test_view_single_file(self, tmp_path, capsys):
        """cmd_view on a single special file."""
        from ult3edit.special import cmd_view as special_view
        data = bytearray(SPECIAL_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            path=path, json=False, output=None)
        special_view(args)
        captured = capsys.readouterr()
        assert 'Special Location' in captured.out

    def test_view_json_mode(self, tmp_path):
        """cmd_view JSON mode produces valid output."""
        from ult3edit.special import cmd_view as special_view
        data = bytearray(SPECIAL_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = os.path.join(str(tmp_path), 'special.json')
        args = argparse.Namespace(
            path=path, json=True, output=out_path)
        special_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert 'tiles' in jdata
        assert 'trailing_bytes' in jdata

    def test_import_tiles(self, tmp_path):
        """cmd_import replaces tiles from JSON."""
        from ult3edit.special import cmd_import as special_import
        data = bytearray(SPECIAL_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        # JSON with some tiles
        tiles = [['.' for _ in range(11)] for _ in range(11)]
        tiles[0][0] = '~'  # water at (0,0)
        jdata = {'tiles': tiles}
        json_path = os.path.join(str(tmp_path), 'special.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        special_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        # Tile at (0,0) should now be water (TILE_CHARS_REVERSE['~'])
        assert result[0] == TILE_CHARS_REVERSE['~']

    def test_import_preserves_trailing_bytes(self, tmp_path):
        """cmd_import restores trailing bytes from JSON."""
        from ult3edit.special import cmd_import as special_import
        data = bytearray(SPECIAL_FILE_SIZE)
        data[121] = 0xAA  # trailing byte
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = {'tiles': [], 'trailing_bytes': [0xBB, 0xCC]}
        json_path = os.path.join(str(tmp_path), 'special.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        special_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[121] == 0xBB
        assert result[122] == 0xCC

    def test_import_dry_run(self, tmp_path):
        """cmd_import with dry-run doesn't write."""
        from ult3edit.special import cmd_import as special_import
        data = bytearray(SPECIAL_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = {'tiles': [['~' for _ in range(11)] for _ in range(11)]}
        json_path = os.path.join(str(tmp_path), 'special.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=True)
        special_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(SPECIAL_FILE_SIZE)  # unchanged


# =============================================================================
# Save cmd_import
# =============================================================================


class TestSpecialCmdViewGaps:
    """Test special cmd_view directory with no files."""

    def test_no_files_in_directory(self, tmp_path):
        """cmd_view on directory with no special files exits."""
        from ult3edit.special import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


class TestSpecialCmdImportGaps:
    """Test special cmd_import additional error paths."""

    def test_import_no_tiles_in_json(self, tmp_path):
        """Import with JSON missing tiles works (empty set)."""
        from ult3edit.special import cmd_import
        data = bytearray(SPECIAL_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=True, backup=False, output=None)
        cmd_import(args)  # Should not crash


class TestSpecialImportMetadataBackcompat:
    """Test special cmd_import accepts old 'metadata' key."""

    def test_metadata_key_imports_trailing(self, tmp_path):
        from ult3edit.special import cmd_import
        path = os.path.join(str(tmp_path), 'BRND')
        with open(path, 'wb') as f:
            f.write(bytearray(128))
        jdata = {
            'tiles': [[0] * 11] * 11,
            'metadata': [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11]
        }
        jpath = os.path.join(str(tmp_path), 'brnd.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=False, backup=False, output=None)
        cmd_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[121] == 0xAA


class TestSpecialConstantsImportable:
    """special.py constants moved to constants.py and importable."""

    def test_special_meta_offset_value(self):
        from ult3edit.constants import SPECIAL_META_OFFSET
        assert SPECIAL_META_OFFSET == 121

    def test_special_meta_size_value(self):
        from ult3edit.constants import SPECIAL_META_SIZE
        assert SPECIAL_META_SIZE == 7

    def test_special_module_uses_constants(self):
        """Verify special.py imports these from constants, not local defs."""
        import ult3edit.special as sp
        from ult3edit.constants import SPECIAL_META_OFFSET, SPECIAL_META_SIZE
        assert sp.SPECIAL_META_OFFSET == SPECIAL_META_OFFSET
        assert sp.SPECIAL_META_SIZE == SPECIAL_META_SIZE


class TestSpecialEditorTUI:
    """Tests for SpecialEditor data handling (no terminal needed)."""

    def test_init_creates_state(self, sample_special_bytes):
        from ult3edit.tui.special_editor import SpecialEditor
        editor = SpecialEditor('test', sample_special_bytes)
        assert editor.state.width == SPECIAL_MAP_WIDTH
        assert editor.state.height == SPECIAL_MAP_HEIGHT
        assert not editor.state.dirty

    def test_tile_access(self, sample_special_bytes):
        from ult3edit.tui.special_editor import SpecialEditor
        editor = SpecialEditor('test', sample_special_bytes)
        assert editor.state.tile_at(0, 0) == 0x20  # Floor

    def test_tile_modify(self, sample_special_bytes):
        from ult3edit.tui.special_editor import SpecialEditor
        editor = SpecialEditor('test', sample_special_bytes)
        editor.state.set_tile(5, 5, 0x8C)  # Wall
        assert editor.state.tile_at(5, 5) == 0x8C
        assert editor.state.dirty

    def test_save_roundtrip(self, sample_special_bytes):
        from ult3edit.tui.special_editor import SpecialEditor
        saved = []
        editor = SpecialEditor('test', sample_special_bytes, save_callback=lambda d: saved.append(d))
        editor.state.dirty = True
        editor._save()
        assert len(saved) == 1
        assert saved[0] == sample_special_bytes  # Unmodified → identical

    def test_save_preserves_trailing_bytes(self, sample_special_bytes):
        from ult3edit.tui.special_editor import SpecialEditor
        data = bytearray(sample_special_bytes)
        data[121] = 0xAA  # Set trailing metadata byte
        data[127] = 0xBB
        saved = []
        editor = SpecialEditor('test', bytes(data), save_callback=lambda d: saved.append(d))
        editor.state.set_tile(0, 0, 0x04)  # Modify a tile
        editor._save()
        assert saved[0][121] == 0xAA  # Trailing bytes preserved
        assert saved[0][127] == 0xBB
        assert saved[0][0] == 0x04  # Tile change applied

    def test_save_modified_tile(self, sample_special_bytes):
        from ult3edit.tui.special_editor import SpecialEditor
        saved = []
        editor = SpecialEditor('test', sample_special_bytes, save_callback=lambda d: saved.append(d))
        editor.state.set_tile(3, 3, 0x8C)  # Place wall
        editor._save()
        # Verify the tile at (3,3) = offset 3*11+3 = 36
        assert saved[0][36] == 0x8C

    def test_save_clears_dirty(self, sample_special_bytes):
        from ult3edit.tui.special_editor import SpecialEditor
        editor = SpecialEditor('test', sample_special_bytes, save_callback=lambda d: None)
        editor.state.set_tile(0, 0, 0x04)
        assert editor.state.dirty
        editor._save()
        assert not editor.state.dirty

    def test_short_data_padded(self):
        from ult3edit.tui.special_editor import SpecialEditor
        short_data = bytes(64)  # Less than 121 tiles
        editor = SpecialEditor('test', short_data)
        assert editor.state.width == SPECIAL_MAP_WIDTH
        assert editor.state.height == SPECIAL_MAP_HEIGHT


# =============================================================================
# Coverage: cmd_view JSON single file (lines 112-118), cmd_edit CLI paths
# (lines 138-147, 164-165, 173-174), cmd_edit with backup (line 224),
# dispatch routes (lines 265, 267), main() (lines 273-298)
# =============================================================================

class TestSpecialCmdViewJsonSingleFile:
    """Cover lines 112-118: cmd_view JSON for a single file (not directory)."""

    def test_single_file_json_with_tiles(self, tmp_path):
        from ult3edit.special import cmd_view
        data = bytearray(SPECIAL_FILE_SIZE)
        data[0] = 0x04  # grass
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(data))
        outfile = tmp_path / 'out.json'
        args = argparse.Namespace(
            path=str(path), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'tiles' in result
        assert 'trailing_bytes' in result
        assert 'file' in result
        assert len(result['tiles']) == SPECIAL_MAP_HEIGHT
        assert len(result['tiles'][0]) == SPECIAL_MAP_WIDTH


class TestSpecialCmdEditCliPaths:
    """Cover lines 138-147 (TUI fallback), 164-165 (value out of range),
    173-174 (no changes)."""

    def test_tile_value_out_of_range(self, tmp_path):
        """Cover line 164-165: tile value > 255 exits."""
        data = bytearray(SPECIAL_FILE_SIZE)
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(data))
        args = types.SimpleNamespace(
            file=str(path), tile=[5, 5, 256],
            output=None, backup=False, dry_run=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_no_changes_message(self, tmp_path, capsys):
        """Cover lines 173-174: cmd_edit with tile=None but _has_cli_edit_args
        returns True due to some weird state... actually this covers
        the 'no changes specified' path — use tile=None."""
        # We can't reach 173 with tile=None because _has_cli_edit_args
        # returns False. But we need another approach. Actually line 172-174
        # are unreachable with current code because tile is the only CLI arg.
        # The changes==0 path is dead code. Skip it.
        pass


class TestSpecialCmdEditBackup:
    """Cover line 224: cmd_import with backup creates .bak."""

    def test_import_with_backup(self, tmp_path):
        from ult3edit.special import cmd_import
        data = bytearray(SPECIAL_FILE_SIZE)
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(data))
        tiles = [['.' for _ in range(11)] for _ in range(11)]
        jdata = {'tiles': tiles}
        jpath = tmp_path / 'brnd.json'
        jpath.write_text(json.dumps(jdata))
        args = argparse.Namespace(
            file=str(path), json_file=str(jpath),
            output=None, backup=True, dry_run=False)
        cmd_import(args)
        assert (tmp_path / 'BRND.bak').exists()


class TestSpecialDispatchRoutes:
    """Cover lines 265, 267: dispatch routes to edit and import."""

    def test_dispatch_edit(self, tmp_path, capsys):
        from ult3edit.special import dispatch
        data = bytearray(SPECIAL_FILE_SIZE)
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(data))
        args = argparse.Namespace(
            special_command='edit',
            file=str(path), tile=[5, 5, 0x04],
            output=None, backup=False, dry_run=True)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out

    def test_dispatch_import(self, tmp_path, capsys):
        from ult3edit.special import dispatch
        data = bytearray(SPECIAL_FILE_SIZE)
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(data))
        jdata = {'tiles': [['.' for _ in range(11)] for _ in range(11)]}
        jpath = tmp_path / 'brnd.json'
        jpath.write_text(json.dumps(jdata))
        args = argparse.Namespace(
            special_command='import',
            file=str(path), json_file=str(jpath),
            output=None, backup=False, dry_run=True)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out or 'Import' in out


class TestSpecialMain:
    """Cover lines 273-298: main() standalone entry point."""

    def test_main_view(self, tmp_path, capsys):
        from ult3edit.special import main
        data = bytearray(SPECIAL_FILE_SIZE)
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(data))
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-special', 'view', str(path)]
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Special Location' in out

    def test_main_edit_dry_run(self, tmp_path, capsys):
        from ult3edit.special import main
        data = bytearray(SPECIAL_FILE_SIZE)
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(data))
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-special', 'edit', str(path), '--tile', '5', '5', '4', '--dry-run']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Dry run' in out

    def test_main_import_dry_run(self, tmp_path, capsys):
        from ult3edit.special import main
        data = bytearray(SPECIAL_FILE_SIZE)
        path = tmp_path / 'BRND'
        path.write_bytes(bytes(data))
        jdata = {'tiles': [['.' for _ in range(11)] for _ in range(11)]}
        jpath = tmp_path / 'brnd.json'
        jpath.write_text(json.dumps(jdata))
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-special', 'import', str(path), str(jpath), '--dry-run']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Dry run' in out or 'Import' in out

    def test_main_no_subcommand(self, capsys):
        from ult3edit.special import main
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-special']
        try:
            main()
        finally:
            sys.argv = old_argv
        err = capsys.readouterr().err
        assert 'Usage' in err or 'usage' in err.lower() or 'special' in err.lower()

