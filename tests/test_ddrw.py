"""Tests for the ddrw module: dungeon drawing data (DDRW) view, edit, import, and parsing."""

import argparse
import json
import os

import pytest

from ult3edit.ddrw import (
    DDRW_FILE_SIZE, parse_vectors, parse_tile_records,
    DDRW_VECTOR_OFFSET, DDRW_VECTOR_COUNT,
    DDRW_TILE_OFFSET, DDRW_TILE_RECORD_SIZE, DDRW_TILE_RECORD_FIELDS,
)


class TestDDRW:
    def test_ddrw_constants(self):
        assert DDRW_FILE_SIZE == 1792

    def test_ddrw_json_round_trip(self, tmp_path):
        data = bytearray(DDRW_FILE_SIZE)
        data[0] = 0xAB
        data[100] = 0xCD
        path = str(tmp_path / 'DDRW')
        with open(path, 'wb') as f:
            f.write(data)

        # Export as JSON
        raw = list(data)
        jdata = {'raw': raw, 'size': len(data)}

        json_path = str(tmp_path / 'ddrw.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        # Import back
        with open(json_path, 'r') as f:
            imported = json.load(f)
        result = bytes(imported['raw'])
        assert result[0] == 0xAB
        assert result[100] == 0xCD
        assert len(result) == DDRW_FILE_SIZE

    def test_ddrw_edit_round_trip(self, tmp_path):
        data = bytearray(DDRW_FILE_SIZE)
        path = str(tmp_path / 'DDRW')
        with open(path, 'wb') as f:
            f.write(data)

        # Patch offset 0x10
        with open(path, 'rb') as f:
            edit_data = bytearray(f.read())
        edit_data[0x10] = 0xFF
        with open(path, 'wb') as f:
            f.write(edit_data)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x10] == 0xFF

    def test_parse_vectors(self):
        data = bytearray(DDRW_FILE_SIZE)
        for i in range(DDRW_VECTOR_COUNT):
            data[DDRW_VECTOR_OFFSET + i] = i * 3
        vectors = parse_vectors(data)
        assert len(vectors) == DDRW_VECTOR_COUNT
        assert vectors[0] == 0
        assert vectors[1] == 3
        assert vectors[10] == 30

    def test_parse_tile_records(self):
        data = bytearray(DDRW_FILE_SIZE)
        # Write a tile record at offset $400
        data[DDRW_TILE_OFFSET + 0] = 0x10  # col_start
        data[DDRW_TILE_OFFSET + 1] = 0x20  # col_end
        data[DDRW_TILE_OFFSET + 2] = 0x02  # step
        data[DDRW_TILE_OFFSET + 3] = 0x01  # flags
        data[DDRW_TILE_OFFSET + 4] = 0x80  # bright_lo
        data[DDRW_TILE_OFFSET + 5] = 0xFF  # bright_hi
        data[DDRW_TILE_OFFSET + 6] = 0x00  # reserved
        records = parse_tile_records(data)
        assert len(records) > 0
        assert records[0]['col_start'] == 0x10
        assert records[0]['col_end'] == 0x20
        assert records[0]['bright_hi'] == 0xFF

    def test_tile_record_field_names(self):
        assert len(DDRW_TILE_RECORD_FIELDS) == DDRW_TILE_RECORD_SIZE


class TestDdrwImportIntegration:
    """Integration tests for ddrw cmd_import()."""

    def test_import_ddrw_raw(self, tmp_path):
        """cmd_import() writes raw byte array from JSON."""
        from ult3edit.ddrw import cmd_import as ddrw_cmd_import
        path = str(tmp_path / 'DDRW')
        original = bytes(256)
        with open(path, 'wb') as f:
            f.write(original)

        new_data = list(range(256))
        jdata = {'raw': new_data}
        json_path = str(tmp_path / 'ddrw.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        ddrw_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result) == new_data

    def test_import_ddrw_dry_run(self, tmp_path):
        """cmd_import() with dry_run does not modify file."""
        from ult3edit.ddrw import cmd_import as ddrw_cmd_import
        path = str(tmp_path / 'DDRW')
        original = bytes(128)
        with open(path, 'wb') as f:
            f.write(original)

        jdata = {'raw': [0xFF] * 128}
        json_path = str(tmp_path / 'ddrw.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        ddrw_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == original


class TestDdrwSource:
    """Validate DDRW source JSON file."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_ddrw_json_valid(self):
        """DDRW source has correct structure and size."""
        path = os.path.join(self.SOURCES_DIR, 'ddrw.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'raw' in data
        assert len(data['raw']) == 1792
        assert all(0 <= b <= 255 for b in data['raw'])


class TestDdrwImportSizeValidation:
    """DDRW import should warn on wrong file size."""

    def test_correct_size_no_warning(self, tmp_path, capsys):
        """Importing 1792 bytes should produce no warning."""
        from ult3edit.ddrw import cmd_import, DDRW_FILE_SIZE
        json_file = tmp_path / 'ddrw.json'
        json_file.write_text(json.dumps({'raw': [0] * DDRW_FILE_SIZE}))
        out_file = tmp_path / 'DDRW'
        out_file.write_bytes(b'\x00' * DDRW_FILE_SIZE)
        args = type('A', (), {
            'file': str(out_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        assert 'Warning' not in capsys.readouterr().err

    def test_wrong_size_warns(self, tmp_path, capsys):
        """Importing wrong size should produce a warning."""
        from ult3edit.ddrw import cmd_import, DDRW_FILE_SIZE
        json_file = tmp_path / 'ddrw.json'
        json_file.write_text(json.dumps({'raw': [0] * 100}))
        out_file = tmp_path / 'DDRW'
        out_file.write_bytes(b'\x00' * DDRW_FILE_SIZE)
        args = type('A', (), {
            'file': str(out_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        err = capsys.readouterr().err
        assert 'Warning' in err
        assert '1792' in err


class TestDdrwCommands:
    """Tests for ddrw cmd_view, cmd_edit, cmd_import."""

    def test_view_text_output(self, tmp_path, capsys):
        """cmd_view prints dungeon drawing data summary."""
        from ult3edit.ddrw import cmd_view
        from ult3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        binfile.write_bytes(bytes(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            path=str(binfile), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Dungeon Drawing Data' in out
        assert '1792 bytes' in out

    def test_view_json_output(self, tmp_path):
        """cmd_view --json produces JSON with vectors and records."""
        from ult3edit.ddrw import cmd_view
        from ult3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        data = bytearray(DDRW_FILE_SIZE)
        data[0xF0] = 0x42  # Set a perspective vector
        binfile.write_bytes(bytes(data))
        outfile = tmp_path / 'out.json'
        args = argparse.Namespace(
            path=str(binfile), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert result['size'] == DDRW_FILE_SIZE
        assert result['vectors'][0] == 0x42
        assert 'raw' in result

    def test_edit_patches_bytes(self, tmp_path):
        """cmd_edit patches bytes at offset."""
        from ult3edit.ddrw import cmd_edit
        from ult3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        binfile.write_bytes(bytes(DDRW_FILE_SIZE))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), offset=0x10, data='AABB',
            output=str(out), backup=False, dry_run=False)
        cmd_edit(args)
        result = out.read_bytes()
        assert result[0x10] == 0xAA
        assert result[0x11] == 0xBB

    def test_edit_dry_run(self, tmp_path, capsys):
        """cmd_edit --dry-run doesn't write."""
        from ult3edit.ddrw import cmd_edit
        from ult3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        binfile.write_bytes(bytes(DDRW_FILE_SIZE))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), offset=0, data='FF',
            output=str(out), backup=False, dry_run=True)
        cmd_edit(args)
        assert not out.exists()
        assert 'Dry run' in capsys.readouterr().out

    def test_import_raw_json(self, tmp_path):
        """cmd_import writes raw byte array from JSON."""
        from ult3edit.ddrw import cmd_import
        from ult3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        binfile.write_bytes(bytes(DDRW_FILE_SIZE))
        data = [0] * DDRW_FILE_SIZE
        data[0] = 0x55
        jfile = tmp_path / 'ddrw.json'
        jfile.write_text(json.dumps({'raw': data}))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=str(out), backup=False, dry_run=False)
        cmd_import(args)
        result = out.read_bytes()
        assert len(result) == DDRW_FILE_SIZE
        assert result[0] == 0x55

    def test_import_backup(self, tmp_path):
        """cmd_import --backup creates .bak file."""
        from ult3edit.ddrw import cmd_import
        from ult3edit.constants import DDRW_FILE_SIZE
        binfile = tmp_path / 'DDRW'
        binfile.write_bytes(bytes(DDRW_FILE_SIZE))
        data = [0] * DDRW_FILE_SIZE
        jfile = tmp_path / 'ddrw.json'
        jfile.write_text(json.dumps({'raw': data}))
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=None, backup=True, dry_run=False)
        cmd_import(args)
        bak = tmp_path / 'DDRW.bak'
        assert bak.exists()


class TestDdrwCmdEditBounds:
    """Tests for ddrw cmd_edit boundary checking."""

    def test_edit_past_end_exits(self, tmp_path):
        """Patch extending past end of file causes sys.exit."""
        from ult3edit.ddrw import cmd_edit
        from ult3edit.constants import DDRW_FILE_SIZE
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            file=str(path), offset=DDRW_FILE_SIZE - 1, data='AABB',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_dry_run(self, tmp_path, capsys):
        """DDRW edit dry run shows changes without writing."""
        from ult3edit.ddrw import cmd_edit
        from ult3edit.constants import DDRW_FILE_SIZE
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            file=str(path), offset=0, data='AB',
            dry_run=True, backup=False, output=None)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        assert path.read_bytes()[0] == 0  # unchanged


class TestDdrwParsing:
    """Tests for DDRW structured parsing functions."""

    def test_parse_vectors_full(self):
        """parse_vectors reads 32 bytes at vector offset."""
        from ult3edit.ddrw import parse_vectors, DDRW_VECTOR_OFFSET
        data = bytearray(1792)
        for i in range(32):
            data[DDRW_VECTOR_OFFSET + i] = i + 1
        result = parse_vectors(data)
        assert len(result) == 32
        assert result[0] == 1
        assert result[31] == 32

    def test_parse_vectors_truncated(self):
        """parse_vectors pads with zeros for truncated data."""
        from ult3edit.ddrw import parse_vectors
        data = bytes(100)  # Too short for vector offset
        result = parse_vectors(data)
        assert len(result) == 32
        assert all(v == 0 for v in result)

    def test_parse_tile_records(self):
        """parse_tile_records reads 7-byte records at tile offset."""
        from ult3edit.ddrw import (parse_tile_records, DDRW_TILE_OFFSET)
        data = bytearray(1792)
        # Write 2 tile records at offset
        for j in range(7):
            data[DDRW_TILE_OFFSET + j] = j + 10
        for j in range(7):
            data[DDRW_TILE_OFFSET + 7 + j] = j + 20
        result = parse_tile_records(data)
        assert len(result) >= 2
        assert result[0]['col_start'] == 10
        assert result[1]['col_start'] == 20

    def test_cmd_edit_dry_run(self, tmp_path):
        """ddrw cmd_edit --dry-run doesn't modify file."""
        from ult3edit.ddrw import cmd_edit
        ddrw_file = tmp_path / 'DDRW'
        original = bytes(1792)
        ddrw_file.write_bytes(original)
        args = argparse.Namespace(
            file=str(ddrw_file), offset=0x10, data='AABB',
            dry_run=True, backup=False, output=None)
        cmd_edit(args)
        assert ddrw_file.read_bytes() == original

    def test_cmd_edit_writes_bytes(self, tmp_path):
        """ddrw cmd_edit patches bytes at offset."""
        from ult3edit.ddrw import cmd_edit
        ddrw_file = tmp_path / 'DDRW'
        ddrw_file.write_bytes(bytes(1792))
        args = argparse.Namespace(
            file=str(ddrw_file), offset=0x10, data='DEADBEEF',
            dry_run=False, backup=False, output=None)
        cmd_edit(args)
        result = ddrw_file.read_bytes()
        assert result[0x10:0x14] == bytes([0xDE, 0xAD, 0xBE, 0xEF])

    def test_cmd_edit_past_end_exits(self, tmp_path):
        """ddrw cmd_edit past end of file exits with error."""
        from ult3edit.ddrw import cmd_edit
        ddrw_file = tmp_path / 'DDRW'
        ddrw_file.write_bytes(bytes(10))
        args = argparse.Namespace(
            file=str(ddrw_file), offset=8, data='AABBCCDD',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestDdrwCmdGaps:
    """Test DDRW command error paths."""

    def test_cmd_view_no_file_in_dir(self, tmp_path):
        """cmd_view on directory with no DDRW file exits."""
        from ult3edit.ddrw import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_cmd_import_no_raw_array(self, tmp_path):
        """cmd_import with JSON missing 'raw' array exits."""
        from ult3edit.ddrw import cmd_import
        from ult3edit.constants import DDRW_FILE_SIZE
        path = os.path.join(str(tmp_path), 'DDRW')
        with open(path, 'wb') as f:
            f.write(bytearray(DDRW_FILE_SIZE))
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'description': 'no raw field'}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_import(args)

    def test_cmd_import_invalid_byte_values(self, tmp_path):
        """cmd_import with out-of-range values in raw array exits."""
        from ult3edit.ddrw import cmd_import
        from ult3edit.constants import DDRW_FILE_SIZE
        path = os.path.join(str(tmp_path), 'DDRW')
        with open(path, 'wb') as f:
            f.write(bytearray(DDRW_FILE_SIZE))
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'raw': [999, -1, 'abc']}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_import(args)


class TestDdrwCmdEditGaps:
    """Test DDRW cmd_edit error paths."""

    def test_edit_patch_past_end(self, tmp_path):
        """cmd_edit with patch extending past end of file exits."""
        from ult3edit.ddrw import cmd_edit
        from ult3edit.constants import DDRW_FILE_SIZE
        path = os.path.join(str(tmp_path), 'DDRW')
        with open(path, 'wb') as f:
            f.write(bytearray(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            file=path, offset=DDRW_FILE_SIZE - 1,
            data='AA BB CC DD',  # 4 bytes past end
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_invalid_hex(self, tmp_path):
        """cmd_edit with invalid hex data exits."""
        from ult3edit.ddrw import cmd_edit
        from ult3edit.constants import DDRW_FILE_SIZE
        path = os.path.join(str(tmp_path), 'DDRW')
        with open(path, 'wb') as f:
            f.write(bytearray(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            file=path, offset=0,
            data='ZZZZ',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)


# =============================================================================
# Coverage: cmd_view JSON (lines 112-118), cmd_view perspective vectors
# display (line 131), cmd_edit with backup (line 182), cmd_edit write
# (lines 269-271), dispatch routes (lines 269-271, 278-307), main()
# =============================================================================


class TestDdrwCmdViewJsonOutput:
    """Cover lines 112-118: cmd_view --json with non-zero vectors."""

    def test_view_json_has_all_fields(self, tmp_path):
        from ult3edit.ddrw import cmd_view, DDRW_VECTOR_OFFSET
        from ult3edit.constants import DDRW_FILE_SIZE
        data = bytearray(DDRW_FILE_SIZE)
        data[DDRW_VECTOR_OFFSET] = 0x10
        data[DDRW_VECTOR_OFFSET + 1] = 0x20
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(data))
        outfile = tmp_path / 'ddrw.json'
        args = argparse.Namespace(
            path=str(path), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert result['file'] == 'DDRW'
        assert result['load_addr'] == '$1800'
        assert result['vectors'][0] == 0x10
        assert 'tile_records' in result
        assert 'raw' in result


class TestDdrwCmdViewVectors:
    """Cover line 131: cmd_view text output with non-zero perspective vectors."""

    def test_view_text_with_vectors(self, tmp_path, capsys):
        from ult3edit.ddrw import cmd_view, DDRW_VECTOR_OFFSET
        from ult3edit.constants import DDRW_FILE_SIZE
        data = bytearray(DDRW_FILE_SIZE)
        # Set non-zero vectors
        for i in range(8):
            data[DDRW_VECTOR_OFFSET + i] = i + 1
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(data))
        args = argparse.Namespace(
            path=str(path), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Perspective vectors' in out
        assert '8 active' in out


class TestDdrwCmdViewTileRecords:
    """Cover line 131: cmd_view text output with non-zero tile records."""

    def test_view_text_with_tile_records(self, tmp_path, capsys):
        from ult3edit.ddrw import cmd_view, DDRW_TILE_OFFSET
        from ult3edit.constants import DDRW_FILE_SIZE
        data = bytearray(DDRW_FILE_SIZE)
        # Set a non-zero tile record at offset $400
        data[DDRW_TILE_OFFSET + 0] = 0x10  # col_start
        data[DDRW_TILE_OFFSET + 1] = 0x20  # col_end
        data[DDRW_TILE_OFFSET + 2] = 0x02  # step
        data[DDRW_TILE_OFFSET + 3] = 0x01  # flags
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(data))
        args = argparse.Namespace(
            path=str(path), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Tile records' in out
        assert '$10' in out  # col_start


class TestDdrwCmdEditBackup:
    """Cover line 182: cmd_edit with --backup creates .bak file."""

    def test_edit_with_backup(self, tmp_path):
        from ult3edit.ddrw import cmd_edit
        from ult3edit.constants import DDRW_FILE_SIZE
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            file=str(path), offset=0, data='FF',
            output=None, backup=True, dry_run=False)
        cmd_edit(args)
        assert (tmp_path / 'DDRW.bak').exists()


class TestDdrwDispatchRoutes:
    """Cover lines 269-271: dispatch routes to edit and import."""

    def test_dispatch_edit(self, tmp_path, capsys):
        from ult3edit.ddrw import dispatch
        from ult3edit.constants import DDRW_FILE_SIZE
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(DDRW_FILE_SIZE))
        args = argparse.Namespace(
            ddrw_command='edit',
            file=str(path), offset=0, data='FF',
            output=None, backup=False, dry_run=True)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out

    def test_dispatch_import(self, tmp_path, capsys):
        from ult3edit.ddrw import dispatch
        from ult3edit.constants import DDRW_FILE_SIZE
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(DDRW_FILE_SIZE))
        jfile = tmp_path / 'ddrw.json'
        jfile.write_text(json.dumps({'raw': [0] * DDRW_FILE_SIZE}))
        args = argparse.Namespace(
            ddrw_command='import',
            file=str(path), json_file=str(jfile),
            output=None, backup=False, dry_run=True)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out or 'Import' in out


class TestDdrwMain:
    """Cover lines 278-307: main() standalone entry point."""

    def test_main_view(self, tmp_path, capsys):
        from ult3edit.ddrw import main
        from ult3edit.constants import DDRW_FILE_SIZE
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(DDRW_FILE_SIZE))
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-ddrw', 'view', str(path)]
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Dungeon Drawing Data' in out

    def test_main_edit_dry_run(self, tmp_path, capsys):
        from ult3edit.ddrw import main
        from ult3edit.constants import DDRW_FILE_SIZE
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(DDRW_FILE_SIZE))
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-ddrw', 'edit', str(path), '--offset', '0', '--data', 'FF', '--dry-run']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Dry run' in out

    def test_main_import_dry_run(self, tmp_path, capsys):
        from ult3edit.ddrw import main
        from ult3edit.constants import DDRW_FILE_SIZE
        path = tmp_path / 'DDRW'
        path.write_bytes(bytes(DDRW_FILE_SIZE))
        jfile = tmp_path / 'ddrw.json'
        jfile.write_text(json.dumps({'raw': [0] * DDRW_FILE_SIZE}))
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-ddrw', 'import', str(path), str(jfile), '--dry-run']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Dry run' in out or 'Import' in out

    def test_main_no_subcommand(self, capsys):
        from ult3edit.ddrw import main
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-ddrw']
        try:
            main()
        finally:
            sys.argv = old_argv
        err = capsys.readouterr().err
        assert 'Usage' in err or 'usage' in err.lower() or 'ddrw' in err.lower()
