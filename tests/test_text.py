"""Tests for game text tool."""

import argparse
import json
import os

import pytest

from ult3edit.constants import TEXT_FILE_SIZE
from ult3edit.text import load_text_records
from ult3edit.tui.text_editor import parse_text_records, rebuild_text_data


class TestLoadTextRecords:
    def test_load(self, tmp_dir, sample_text_bytes):
        path = os.path.join(tmp_dir, 'TEXT#060800')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)
        records = load_text_records(path)
        assert len(records) == 3
        assert records[0] == 'ULTIMA III'
        assert records[1] == 'EXODUS'
        assert records[2] == 'PRESS ANY KEY'


class TestHighAsciiDecode:
    def test_strips_high_bit(self, tmp_dir):
        data = bytearray(32)
        for i, ch in enumerate('TEST'):
            data[i] = ord(ch) | 0x80
        data[4] = 0x00
        path = os.path.join(tmp_dir, 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        records = load_text_records(path)
        assert records[0] == 'TEST'


class TestParseAndRebuild:
    def test_parse_records(self, sample_text_bytes):
        records = parse_text_records(sample_text_bytes)
        texts = [r.text for r in records]
        assert 'ULTIMA III' in texts
        assert 'EXODUS' in texts
        assert 'PRESS ANY KEY' in texts

    def test_rebuild_roundtrip(self, sample_text_bytes):
        records = parse_text_records(sample_text_bytes)
        rebuilt = rebuild_text_data(records, len(sample_text_bytes))
        assert bytes(rebuilt) == sample_text_bytes

    def test_rebuild_shorter_text_padded(self):
        """Editing a record to be shorter should pad with 0xA0 (space)."""
        # Build: "HELLO\x00" (5 chars + null) in 16 bytes
        data = bytearray(16)
        for i, ch in enumerate('HELLO'):
            data[i] = ord(ch) | 0x80
        data[5] = 0x00
        records = parse_text_records(bytes(data))
        assert len(records) == 1
        assert records[0].max_len == 5
        # Edit to shorter text
        records[0].text = 'HI'
        rebuilt = rebuild_text_data(records, 16)
        # First 2 bytes: H, I in high-ASCII
        assert rebuilt[0] == ord('H') | 0x80
        assert rebuilt[1] == ord('I') | 0x80
        # Remaining 3 bytes of the 5-byte field: 0xA0 padding
        assert rebuilt[2] == 0xA0
        assert rebuilt[3] == 0xA0
        assert rebuilt[4] == 0xA0
        # Null terminator
        assert rebuilt[5] == 0x00

    def test_consistent_with_cli(self, sample_text_bytes):
        """TUI parser and CLI parser should return same text content."""
        import os
        import tempfile
        tui_records = parse_text_records(sample_text_bytes)
        tui_texts = [r.text for r in tui_records]
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(sample_text_bytes)
            tmp = f.name
        try:
            cli_records = load_text_records(tmp)
            assert tui_texts == cli_records
        finally:
            os.unlink(tmp)


# ── Migrated from test_new_features.py ──

class TestTextImport:
    def test_import_text_records(self, tmp_dir, sample_text_bytes):
        """cmd_import() applies text records from JSON."""
        from ult3edit.text import cmd_import as text_cmd_import
        path = os.path.join(tmp_dir, 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)

        records = load_text_records(path)
        assert len(records) >= 3
        assert records[0] == 'ULTIMA III'

        # Import via cmd_import
        jdata = [{'text': 'MODIFIED'}, {'text': 'RECORDS'}, {'text': 'HERE'}]
        json_path = os.path.join(tmp_dir, 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        text_cmd_import(args)

        records2 = load_text_records(path)
        assert records2[0] == 'MODIFIED'
        assert records2[1] == 'RECORDS'
        assert records2[2] == 'HERE'

    def test_import_text_dry_run(self, tmp_dir, sample_text_bytes):
        """cmd_import() with dry_run does not modify file."""
        from ult3edit.text import cmd_import as text_cmd_import
        path = os.path.join(tmp_dir, 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)

        jdata = [{'text': 'CHANGED'}]
        json_path = os.path.join(tmp_dir, 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        text_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == sample_text_bytes


# =============================================================================
# Text per-record CLI editing
# =============================================================================


class TestTextCliEdit:
    def _write_text(self, tmp_dir, sample_text_bytes):
        path = os.path.join(tmp_dir, 'TEXT#061000')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)
        return path

    def test_edit_single_record(self, tmp_dir, sample_text_bytes):
        """Edit record 0 via CLI."""
        import types
        from ult3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        out = os.path.join(tmp_dir, 'TEXT_OUT')
        args = types.SimpleNamespace(
            file=path, record=0, text='CHANGED',
            output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_text_records(out)
        assert records[0] == 'CHANGED'
        assert records[1] == 'EXODUS'  # Unchanged

    def test_edit_record_out_of_range(self, tmp_dir, sample_text_bytes):
        """Out-of-range record index should fail."""
        import types
        from ult3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        args = types.SimpleNamespace(
            file=path, record=99, text='NOPE',
            output=None, backup=False, dry_run=False,
        )
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_dry_run(self, tmp_dir, sample_text_bytes):
        """Dry run should not write."""
        import types
        from ult3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        with open(path, 'rb') as f:
            original = f.read()
        args = types.SimpleNamespace(
            file=path, record=0, text='CHANGED',
            output=None, backup=False, dry_run=True,
        )
        cmd_edit(args)
        with open(path, 'rb') as f:
            after = f.read()
        assert original == after

    def test_edit_backup(self, tmp_dir, sample_text_bytes):
        """Backup should create .bak."""
        import types
        from ult3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        args = types.SimpleNamespace(
            file=path, record=0, text='CHANGED',
            output=None, backup=True, dry_run=False,
        )
        cmd_edit(args)
        assert os.path.exists(path + '.bak')

    def test_edit_output_file(self, tmp_dir, sample_text_bytes):
        """Output to different file."""
        import types
        from ult3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        out = os.path.join(tmp_dir, 'TEXT_OUT')
        args = types.SimpleNamespace(
            file=path, record=1, text='hello',
            output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_text_records(out)
        assert records[1] == 'HELLO'  # Uppercased, fits in 6-char field

    def test_edit_uppercases(self, tmp_dir, sample_text_bytes):
        """Text should be uppercased to match engine convention."""
        import types
        from ult3edit.text import cmd_edit
        path = self._write_text(tmp_dir, sample_text_bytes)
        out = os.path.join(tmp_dir, 'TEXT_OUT')
        args = types.SimpleNamespace(
            file=path, record=0, text='lowercase',
            output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_text_records(out)
        assert records[0] == 'LOWERCASE'


# =============================================================================
# Tile reverse lookups
# =============================================================================


class TestTextImportDryRun:
    """Behavioral test: text import --dry-run should not write."""

    def test_import_dry_run_no_write(self, tmp_dir):
        from ult3edit.text import cmd_import as text_import
        import types

        # Build a TEXT file with known content
        data = bytearray(TEXT_FILE_SIZE)
        text = 'HELLO'
        for i, ch in enumerate(text):
            data[i] = ord(ch) | 0x80
        data[len(text)] = 0x00
        text_path = os.path.join(tmp_dir, 'TEXT#061000')
        with open(text_path, 'wb') as f:
            f.write(data)

        # Write JSON with different content
        jdata = [{'text': 'CHANGED'}]
        json_path = os.path.join(tmp_dir, 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        # Import with dry-run
        args = types.SimpleNamespace(
            file=text_path, json_file=json_path,
            output=None, backup=False, dry_run=True,
        )
        text_import(args)

        # Verify file unchanged
        with open(text_path, 'rb') as f:
            after = f.read()
        assert after == bytes(data)

    def test_import_writes_without_dry_run(self, tmp_dir):
        from ult3edit.text import cmd_import as text_import
        import types

        data = bytearray(TEXT_FILE_SIZE)
        text = 'HELLO'
        for i, ch in enumerate(text):
            data[i] = ord(ch) | 0x80
        data[len(text)] = 0x00
        text_path = os.path.join(tmp_dir, 'TEXT#061000')
        with open(text_path, 'wb') as f:
            f.write(data)

        jdata = [{'text': 'WORLD'}]
        json_path = os.path.join(tmp_dir, 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = types.SimpleNamespace(
            file=text_path, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        text_import(args)

        with open(text_path, 'rb') as f:
            after = f.read()
        # First bytes should now be "WORLD" in high-ASCII
        assert after[0] == ord('W') | 0x80


# =============================================================================
# Fix 1: roster.py — in_party, sub_morsels setters + total conversion
# =============================================================================


class TestTextImportOverflow:
    """Text import should report actual records written, not total in JSON."""

    def test_reports_actual_count(self, tmp_path, capsys):
        """When file is too small, report count of records actually written."""
        from ult3edit.text import cmd_import
        # Create a tiny 20-byte TEXT file
        text_file = tmp_path / 'TEXT'
        text_file.write_bytes(b'\x00' * 20)
        # Create JSON with many long records that won't all fit
        records = [{'text': 'ABCDEFGHIJ'} for _ in range(10)]  # 10 records, ~11 bytes each
        json_file = tmp_path / 'text.json'
        json_file.write_text(json.dumps(records))
        args = type('A', (), {
            'file': str(text_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        out = capsys.readouterr()
        # Should report fewer than 10 records
        assert 'Import: 1 text record(s)' in out.out
        assert 'Warning' in out.err
        assert 'wrote 1 of 10' in out.err

    def test_all_fit_no_warning(self, tmp_path, capsys):
        """When all records fit, report total count and no warning."""
        from ult3edit.text import cmd_import
        text_file = tmp_path / 'TEXT'
        text_file.write_bytes(b'\x00' * 200)
        records = [{'text': 'HI'}, {'text': 'BYE'}]  # 3+4=7 bytes
        json_file = tmp_path / 'text.json'
        json_file.write_text(json.dumps(records))
        args = type('A', (), {
            'file': str(text_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        out = capsys.readouterr()
        assert 'Import: 2 text record(s)' in out.out
        assert 'Warning' not in out.err


# =============================================================================
# Engine SDK: Round-trip assembly verification
# =============================================================================


# =============================================================================
# String patcher tests
# =============================================================================


# =============================================================================
# Source-level string patcher tests
# =============================================================================


# =============================================================================
# Integrated inline string catalog (patch.py cmd_strings)
# =============================================================================


# =============================================================================
# Inline string editing (patch.py cmd_strings_edit / cmd_strings_import)
# =============================================================================


# =============================================================================
# Compiler subcommands — map, shapes, patch
# =============================================================================


class TestTextImportNoPhantomRecords:
    """Tests for text.cmd_import zeroing stale bytes."""

    def test_import_shorter_records_no_phantoms(self, tmp_path, capsys):
        """Importing fewer/shorter records doesn't leave stale data."""
        from ult3edit.text import cmd_import, load_text_records
        from ult3edit.fileutil import encode_high_ascii
        # Build a TEXT file with 3 original records
        data = bytearray(TEXT_FILE_SIZE)
        offset = 0
        for text in ['ULTIMA III', 'EXODUS', 'PRESS ANY KEY']:
            enc = encode_high_ascii(text, len(text))
            data[offset:offset + len(enc)] = enc
            data[offset + len(enc)] = 0x00
            offset += len(enc) + 1
        path = tmp_path / 'TEXT'
        path.write_bytes(bytes(data))
        # Import only 2 shorter records
        json_path = tmp_path / 'text.json'
        json_path.write_text(json.dumps([
            {'text': 'SHORT'},
            {'text': 'TWO'},
        ]))
        args = argparse.Namespace(
            file=str(path), json_file=str(json_path),
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        records = load_text_records(str(path))
        assert len(records) == 2
        assert records[0] == 'SHORT'
        assert records[1] == 'TWO'

    def test_import_same_count_exact(self, tmp_path, capsys):
        """Importing same number of records produces exact count."""
        from ult3edit.text import cmd_import, load_text_records
        from ult3edit.fileutil import encode_high_ascii
        data = bytearray(TEXT_FILE_SIZE)
        offset = 0
        for text in ['AAA', 'BBB']:
            enc = encode_high_ascii(text, len(text))
            data[offset:offset + len(enc)] = enc
            data[offset + len(enc)] = 0x00
            offset += len(enc) + 1
        path = tmp_path / 'TEXT'
        path.write_bytes(bytes(data))
        json_path = tmp_path / 'text.json'
        json_path.write_text(json.dumps([
            {'text': 'CCC'},
            {'text': 'DDD'},
        ]))
        args = argparse.Namespace(
            file=str(path), json_file=str(json_path),
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        records = load_text_records(str(path))
        assert len(records) == 2

    def test_stale_bytes_zeroed(self, tmp_path, capsys):
        """Bytes after final record are zeroed."""
        from ult3edit.text import cmd_import
        # Fill file with 0xFF to detect stale data
        data = bytearray([0xFF] * TEXT_FILE_SIZE)
        path = tmp_path / 'TEXT'
        path.write_bytes(bytes(data))
        json_path = tmp_path / 'text.json'
        json_path.write_text(json.dumps([{'text': 'HI'}]))
        args = argparse.Namespace(
            file=str(path), json_file=str(json_path),
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        result = path.read_bytes()
        # 'HI' = 2 high-ASCII bytes + null = 3 bytes at offset 0
        # Everything after offset 3 should be zeroed
        assert all(b == 0 for b in result[3:])


class TestTextCmdErrors:
    """Test text.py command error paths."""

    def test_text_edit_record_out_of_range(self, tmp_path):
        """text cmd_edit with record index beyond count exits."""
        from ult3edit.text import cmd_edit as text_cmd_edit
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(bytes(TEXT_FILE_SIZE))
        args = argparse.Namespace(
            file=path, record=999, text='HELLO',
            output=None, dry_run=True, backup=False)
        with pytest.raises(SystemExit):
            text_cmd_edit(args)

    def test_text_load_records(self, tmp_path):
        """load_text_records splits on null terminators."""
        path = os.path.join(str(tmp_path), 'TEXT')
        data = bytearray(TEXT_FILE_SIZE)
        # Put 3 null-terminated high-ASCII strings at start
        off = 0
        for s in ('HELLO', 'WORLD', 'TEST'):
            for ch in s:
                data[off] = ord(ch) | 0x80
                off += 1
            data[off] = 0x00
            off += 1
        with open(path, 'wb') as f:
            f.write(data)
        records = load_text_records(path)
        assert records[:3] == ['HELLO', 'WORLD', 'TEST']


# =============================================================================
# Equipment reference (equip.py)
# =============================================================================


class TestTextCmdImport:
    """Test text.py cmd_import."""

    def test_import_list_format(self, tmp_path):
        """Import text from JSON list of strings."""
        from ult3edit.text import cmd_import as text_import
        data = bytearray(TEXT_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'text': 'HELLO'}, {'text': 'WORLD'}]
        json_path = os.path.join(str(tmp_path), 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        text_import(args)
        records = load_text_records(path)
        assert records[0] == 'HELLO'
        assert records[1] == 'WORLD'

    def test_import_dict_format(self, tmp_path):
        """Import text from JSON with 'records' key."""
        from ult3edit.text import cmd_import as text_import
        data = bytearray(TEXT_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = {'records': [{'text': 'TEST'}]}
        json_path = os.path.join(str(tmp_path), 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        text_import(args)
        records = load_text_records(path)
        assert records[0] == 'TEST'

    def test_import_dry_run(self, tmp_path):
        """Import with dry-run doesn't write."""
        from ult3edit.text import cmd_import as text_import
        data = bytearray(TEXT_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'text': 'NOPE'}]
        json_path = os.path.join(str(tmp_path), 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=True)
        text_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(TEXT_FILE_SIZE)  # unchanged

    def test_import_zeros_remaining(self, tmp_path):
        """Import clears stale data after last record."""
        from ult3edit.text import cmd_import as text_import
        # Fill with non-zero bytes first
        data = bytearray(b'\xAA' * TEXT_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'text': 'A'}]
        json_path = os.path.join(str(tmp_path), 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        text_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        # After 'A' + null (2 bytes), everything should be zero
        assert all(b == 0 for b in result[2:])


# =============================================================================
# TLK find-replace
# =============================================================================


class TestTextCmdEditGaps:
    """Test text cmd_edit argument validation."""

    def test_record_without_text_exits(self, tmp_path):
        """cmd_edit with --record but no --text exits."""
        from ult3edit.text import cmd_edit
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(bytearray(TEXT_FILE_SIZE))
        args = argparse.Namespace(
            file=path, record=0, text=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_text_without_record_exits(self, tmp_path):
        """cmd_edit with --text but no --record exits."""
        from ult3edit.text import cmd_edit
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(bytearray(TEXT_FILE_SIZE))
        args = argparse.Namespace(
            file=path, record=None, text='HELLO',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_import_overflow_truncation(self, tmp_path, capsys):
        """Import with too many records for file size warns."""
        from ult3edit.text import cmd_import
        # Small file (32 bytes)
        path = os.path.join(str(tmp_path), 'TEXT')
        with open(path, 'wb') as f:
            f.write(bytearray(32))
        # Import many long records
        json_path = os.path.join(str(tmp_path), 'import.json')
        records = ['A' * 20, 'B' * 20, 'C' * 20]
        with open(json_path, 'w') as f:
            json.dump(records, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=True, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert 'too small' in captured.err or 'Warning' in captured.err


# =============================================================================
# Batch 3: Coverage for text.py uncovered lines
# =============================================================================


class TestTextCmdView:
    """Cover lines 32-46: cmd_view text and JSON output."""

    def test_view_text_output(self, tmp_path, capsys, sample_text_bytes):
        from ult3edit.text import cmd_view
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)
        args = argparse.Namespace(file=path, json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Ultima III Game Text' in out
        assert 'ULTIMA III' in out
        assert 'EXODUS' in out
        assert 'PRESS ANY KEY' in out
        # Check record index format [  0]
        assert '[  0]' in out

    def test_view_json_output(self, tmp_path, sample_text_bytes):
        from ult3edit.text import cmd_view
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)
        outfile = str(tmp_path / 'text.json')
        args = argparse.Namespace(file=path, json=True, output=outfile)
        cmd_view(args)
        with open(outfile) as f:
            result = json.load(f)
        assert 'file' in result
        assert 'records' in result
        assert result['records'][0]['text'] == 'ULTIMA III'
        assert result['records'][0]['index'] == 0


class TestTextCmdEditPartialArgs:
    """Cover lines 58-60, 63-71: cmd_edit with partial args exits,
    and TUI fallback path (mocked)."""

    def test_record_without_text_exits(self, tmp_path):
        from ult3edit.text import cmd_edit
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(bytearray(TEXT_FILE_SIZE))
        args = argparse.Namespace(
            file=path, record=0, text=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_text_without_record_exits(self, tmp_path):
        from ult3edit.text import cmd_edit
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(bytearray(TEXT_FILE_SIZE))
        args = argparse.Namespace(
            file=path, record=None, text='HELLO',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestTextCmdImportBackup:
    """Cover line 145: cmd_import with --backup flag."""

    def test_import_creates_backup(self, tmp_path):
        from ult3edit.text import cmd_import
        data = bytearray(TEXT_FILE_SIZE)
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'text': 'BACKED UP'}]
        json_path = str(tmp_path / 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            output=None, backup=True, dry_run=False)
        cmd_import(args)
        assert os.path.exists(path + '.bak')


class TestTextDispatch:
    """Cover lines 179-183: dispatch routes to all subcommands."""

    def test_dispatch_view(self, tmp_path, capsys, sample_text_bytes):
        from ult3edit.text import dispatch
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)
        args = argparse.Namespace(
            text_command='view', file=path, json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'ULTIMA III' in out

    def test_dispatch_edit(self, tmp_path, capsys, sample_text_bytes):
        from ult3edit.text import dispatch
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)
        out_path = str(tmp_path / 'OUT')
        args = argparse.Namespace(
            text_command='edit', file=path, record=0, text='CHANGED',
            output=out_path, backup=False, dry_run=False)
        dispatch(args)
        records = load_text_records(out_path)
        assert records[0] == 'CHANGED'

    def test_dispatch_import(self, tmp_path, capsys):
        from ult3edit.text import dispatch
        data = bytearray(TEXT_FILE_SIZE)
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'text': 'DISPATCHED'}]
        json_path = str(tmp_path / 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            text_command='import', file=path, json_file=json_path,
            output=None, backup=False, dry_run=False)
        dispatch(args)
        records = load_text_records(path)
        assert records[0] == 'DISPATCHED'

    def test_dispatch_unknown(self, capsys):
        from ult3edit.text import dispatch
        args = argparse.Namespace(text_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err


class TestTextMain:
    """Cover lines 189-218: main() standalone entry point."""

    def test_main_view(self, tmp_path, capsys, monkeypatch, sample_text_bytes):
        import sys
        from ult3edit.text import main
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)
        monkeypatch.setattr(sys, 'argv', ['ult3-text', 'view', path])
        main()
        out = capsys.readouterr().out
        assert 'ULTIMA III' in out

    def test_main_view_json(self, tmp_path, capsys, monkeypatch, sample_text_bytes):
        import sys
        from ult3edit.text import main
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)
        outfile = str(tmp_path / 'text.json')
        monkeypatch.setattr(sys, 'argv', [
            'ult3-text', 'view', path, '--json', '-o', outfile])
        main()
        with open(outfile) as f:
            result = json.load(f)
        assert 'records' in result

    def test_main_edit(self, tmp_path, capsys, monkeypatch, sample_text_bytes):
        import sys
        from ult3edit.text import main
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(sample_text_bytes)
        out_path = str(tmp_path / 'OUT')
        monkeypatch.setattr(sys, 'argv', [
            'ult3-text', 'edit', path, '--record', '0',
            '--text', 'VIA MAIN', '-o', out_path])
        main()
        records = load_text_records(out_path)
        assert records[0] == 'VIA MAIN'

    def test_main_import(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.text import main
        data = bytearray(TEXT_FILE_SIZE)
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'text': 'MAIN IMPORT'}]
        json_path = str(tmp_path / 'text.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        monkeypatch.setattr(sys, 'argv', [
            'ult3-text', 'import', path, json_path, '--dry-run'])
        main()
        out = capsys.readouterr().out
        assert 'Dry run' in out

    def test_main_no_command(self, capsys, monkeypatch):
        import sys
        from ult3edit.text import main
        monkeypatch.setattr(sys, 'argv', ['ult3-text'])
        main()
        err = capsys.readouterr().err
        assert 'Usage' in err

