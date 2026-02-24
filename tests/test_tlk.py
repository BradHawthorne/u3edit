"""Tests for TLK dialog tool."""

import argparse
import json
import os

import pytest

from ult3edit.tlk import (decode_record, encode_record, load_tlk_records, _match_line,
                         is_text_record, cmd_edit, cmd_search)
from ult3edit.tui.dialog_editor import DialogEditor
from ult3edit.constants import TLK_RECORD_END


class TestDecodeRecord:
    def test_single_line(self):
        # "HELLO" in high-bit ASCII + null terminator
        data = bytes([0xC8, 0xC5, 0xCC, 0xCC, 0xCF, 0x00])
        lines = decode_record(data)
        assert lines == ['HELLO']

    def test_multi_line(self):
        # "HI" + 0xFF + "THERE" + 0x00
        data = bytes([0xC8, 0xC9, 0xFF, 0xD4, 0xC8, 0xC5, 0xD2, 0xC5, 0x00])
        lines = decode_record(data)
        assert lines == ['HI', 'THERE']

    def test_empty(self):
        data = bytes([0x00])
        lines = decode_record(data)
        assert lines == ['']


class TestEncodeRecord:
    def test_single_line(self):
        result = encode_record(['HELLO'])
        assert result[-1] == 0x00  # null terminated
        # All bytes should have high bit set
        for b in result[:-1]:
            assert b & 0x80

    def test_multi_line(self):
        result = encode_record(['HI', 'THERE'])
        assert 0xFF in result  # line break present
        assert result[-1] == 0x00


class TestRoundTrip:
    def test_single(self):
        original = ['HELLO WORLD']
        encoded = encode_record(original)
        decoded = decode_record(encoded)
        assert decoded == original

    def test_multi(self):
        original = ['LINE ONE', 'LINE TWO', 'LINE THREE']
        encoded = encode_record(original)
        decoded = decode_record(encoded)
        assert decoded == original


class TestLoadTlkRecords:
    def test_load(self, sample_tlk_file):
        records = load_tlk_records(sample_tlk_file)
        assert len(records) == 2
        assert records[0] == ['HELLO ADVENTURER']
        assert records[1] == ['WELCOME', 'TO MY SHOP']


class TestCmdEdit:
    def test_edit_record(self, sample_tlk_file, tmp_dir):
        out = os.path.join(tmp_dir, 'TLKA_OUT')
        args = argparse.Namespace(
            file=sample_tlk_file, record=0,
            text='GOODBYE ADVENTURER', output=out,
        )
        cmd_edit(args)
        records = load_tlk_records(out)
        assert records[0] == ['GOODBYE ADVENTURER']
        assert records[1] == ['WELCOME', 'TO MY SHOP']  # Other record preserved

    def test_edit_multiline(self, sample_tlk_file, tmp_dir):
        out = os.path.join(tmp_dir, 'TLKA_OUT')
        args = argparse.Namespace(
            file=sample_tlk_file, record=1,
            text='FAREWELL\\nSAFE TRAVELS', output=out,
        )
        cmd_edit(args)
        records = load_tlk_records(out)
        assert records[1] == ['FAREWELL', 'SAFE TRAVELS']
        assert records[0] == ['HELLO ADVENTURER']  # Other record preserved


class TestCmdFindReplace:
    """Tests for --find/--replace search-and-replace mode."""

    def test_single_replacement(self, sample_tlk_file, tmp_dir):
        """Replace a word in one record."""
        out = os.path.join(tmp_dir, 'TLKA_OUT')
        args = argparse.Namespace(
            file=sample_tlk_file, record=None, text=None,
            find='HELLO', replace='GREETINGS',
            ignore_case=False, output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_tlk_records(out)
        assert records[0] == ['GREETINGS ADVENTURER']
        assert records[1] == ['WELCOME', 'TO MY SHOP']  # Unchanged

    def test_multiple_records(self, tmp_dir):
        """Replace text that appears in multiple records."""
        # Build TLK with "THE" in two records
        rec0 = encode_record(['THE CASTLE'])
        rec1 = encode_record(['THE DUNGEON'])
        path = os.path.join(tmp_dir, 'TLK_MULTI')
        with open(path, 'wb') as f:
            f.write(rec0 + rec1)
        out = os.path.join(tmp_dir, 'TLK_MULTI_OUT')
        args = argparse.Namespace(
            file=path, record=None, text=None,
            find='THE', replace='A',
            ignore_case=False, output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_tlk_records(out)
        assert records[0] == ['A CASTLE']
        assert records[1] == ['A DUNGEON']

    def test_no_match(self, sample_tlk_file, tmp_dir):
        """No matches should leave file unchanged."""
        out = os.path.join(tmp_dir, 'TLKA_OUT')
        args = argparse.Namespace(
            file=sample_tlk_file, record=None, text=None,
            find='ZZZZZ', replace='AAAAA',
            ignore_case=False, output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        # No output written when zero replacements
        assert not os.path.exists(out)

    def test_dry_run(self, sample_tlk_file):
        """Dry run should not write changes."""
        with open(sample_tlk_file, 'rb') as f:
            original = f.read()
        args = argparse.Namespace(
            file=sample_tlk_file, record=None, text=None,
            find='HELLO', replace='GOODBYE',
            ignore_case=False, output=None, backup=False, dry_run=True,
        )
        cmd_edit(args)
        with open(sample_tlk_file, 'rb') as f:
            after = f.read()
        assert original == after

    def test_case_sensitive_default(self, sample_tlk_file, tmp_dir):
        """Default is case-sensitive: 'hello' should not match 'HELLO'."""
        out = os.path.join(tmp_dir, 'TLKA_OUT')
        args = argparse.Namespace(
            file=sample_tlk_file, record=None, text=None,
            find='hello', replace='goodbye',
            ignore_case=False, output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        # No match, no output
        assert not os.path.exists(out)

    def test_ignore_case(self, sample_tlk_file, tmp_dir):
        """--ignore-case should match regardless of case."""
        out = os.path.join(tmp_dir, 'TLKA_OUT')
        args = argparse.Namespace(
            file=sample_tlk_file, record=None, text=None,
            find='hello', replace='GOODBYE',
            ignore_case=True, output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_tlk_records(out)
        assert records[0] == ['GOODBYE ADVENTURER']

    def test_multiple_occurrences_in_line(self, tmp_dir):
        """Multiple occurrences in a single line should all be replaced."""
        rec = encode_record(['GO GO GO'])
        path = os.path.join(tmp_dir, 'TLK_REPEAT')
        with open(path, 'wb') as f:
            f.write(rec)
        out = os.path.join(tmp_dir, 'TLK_REPEAT_OUT')
        args = argparse.Namespace(
            file=path, record=None, text=None,
            find='GO', replace='STOP',
            ignore_case=False, output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_tlk_records(out)
        assert records[0] == ['STOP STOP STOP']

    def test_multiline_record(self, sample_tlk_file, tmp_dir):
        """Replace in a multi-line record."""
        out = os.path.join(tmp_dir, 'TLKA_OUT')
        args = argparse.Namespace(
            file=sample_tlk_file, record=None, text=None,
            find='MY', replace='THE',
            ignore_case=False, output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_tlk_records(out)
        assert records[1] == ['WELCOME', 'TO THE SHOP']

    def test_backup(self, sample_tlk_file):
        """--backup should create .bak before overwriting."""
        args = argparse.Namespace(
            file=sample_tlk_file, record=None, text=None,
            find='HELLO', replace='GOODBYE',
            ignore_case=False, output=None, backup=True, dry_run=False,
        )
        cmd_edit(args)
        assert os.path.exists(sample_tlk_file + '.bak')
        records = load_tlk_records(sample_tlk_file)
        assert records[0] == ['GOODBYE ADVENTURER']

    def test_empty_replacement(self, sample_tlk_file, tmp_dir):
        """Replacing with empty string should delete the matched text."""
        out = os.path.join(tmp_dir, 'TLKA_OUT')
        args = argparse.Namespace(
            file=sample_tlk_file, record=None, text=None,
            find='HELLO ', replace='',
            ignore_case=False, output=out, backup=False, dry_run=False,
        )
        cmd_edit(args)
        records = load_tlk_records(out)
        assert records[0] == ['ADVENTURER']


class TestBinaryPreservation:
    """Tests that binary (non-text) records are preserved during editing."""

    def _make_mixed_data(self):
        """Build TLK data with a text record, a binary record, and another text record."""
        # Text record: "HELLO"
        text1 = bytearray()
        for ch in 'HELLO':
            text1.append(ord(ch) | 0x80)
        text1.append(TLK_RECORD_END)
        # Binary record: low bytes (code/data, not high-ASCII)
        binary = bytearray([0x20, 0x30, 0x4C, 0x10, 0x08, TLK_RECORD_END])
        # Text record: "WORLD"
        text2 = bytearray()
        for ch in 'WORLD':
            text2.append(ord(ch) | 0x80)
        text2.append(TLK_RECORD_END)
        return bytes(text1 + binary + text2)

    def test_binary_record_detected(self):
        binary_part = bytes([0x20, 0x30, 0x4C, 0x10, 0x08])
        assert not is_text_record(binary_part)

    def test_text_record_detected(self):
        text_part = bytearray()
        for ch in 'HELLO':
            text_part.append(ord(ch) | 0x80)
        assert is_text_record(bytes(text_part))

    def test_dialog_editor_preserves_binary(self):
        data = self._make_mixed_data()
        saved = []
        editor = DialogEditor('test', data, save_callback=lambda d: saved.append(d))
        # Should only see the 2 text records
        assert len(editor.records) == 2
        assert editor.records[0] == ['HELLO']
        assert editor.records[1] == ['WORLD']
        # Modify first text record (mark as modified, as the UI does)
        editor.records[0] = ['GOODBYE']
        editor._modified_records.add(0)
        editor.dirty = True
        editor._save()
        # Binary record should be preserved in the output
        result = saved[0]
        # The binary bytes (0x20, 0x30, 0x4C, 0x10, 0x08) should still be present
        assert bytes([0x20, 0x30, 0x4C, 0x10, 0x08]) in result
        # And the modified text should be there
        assert (ord('G') | 0x80) in result

    def test_dialog_editor_roundtrip_unmodified(self):
        data = self._make_mixed_data()
        saved = []
        editor = DialogEditor('test', data, save_callback=lambda d: saved.append(d))
        editor.dirty = True
        editor._save()
        # Unmodified save should produce identical output
        assert saved[0] == data


# ── Migrated from test_new_features.py ──

class TestTlkSearch:
    def test_search_finds_match(self, tmp_dir, sample_tlk_bytes):
        path = os.path.join(tmp_dir, 'TLKA')
        with open(path, 'wb') as f:
            f.write(sample_tlk_bytes)

        records = load_tlk_records(path)
        # Search for "HELLO" in records
        matches = []
        for i, rec in enumerate(records):
            for line in rec:
                if 'hello' in line.lower():
                    matches.append((i, line))
        assert len(matches) == 1
        assert 'HELLO' in matches[0][1]

    def test_search_no_match(self, tmp_dir, sample_tlk_bytes):
        path = os.path.join(tmp_dir, 'TLKA')
        with open(path, 'wb') as f:
            f.write(sample_tlk_bytes)

        records = load_tlk_records(path)
        matches = []
        for i, rec in enumerate(records):
            for line in rec:
                if 'zzzzz' in line.lower():
                    matches.append((i, line))
        assert len(matches) == 0


# =============================================================================
# TLK import
# =============================================================================


class TestTlkImport:
    def test_import_roundtrip(self, tmp_dir, sample_tlk_bytes):
        path = os.path.join(tmp_dir, 'TLKA')
        with open(path, 'wb') as f:
            f.write(sample_tlk_bytes)

        # Load and export
        records = load_tlk_records(path)
        json_data = [{'lines': rec} for rec in records]

        # Re-encode from JSON
        out = bytearray()
        for entry in json_data:
            out.extend(encode_record(entry['lines']))

        # Write back
        out_path = os.path.join(tmp_dir, 'TLKA_imported')
        with open(out_path, 'wb') as f:
            f.write(bytes(out))

        # Verify
        records2 = load_tlk_records(out_path)
        assert len(records2) == len(records)
        for r1, r2 in zip(records, records2):
            assert r1 == r2


class TestTlkExtractBuild:
    """Integration tests for tlk extract → build round-trip."""

    def test_extract_build_roundtrip(self, tmp_path, sample_tlk_bytes):
        """extract → build produces identical binary."""
        from ult3edit.tlk import cmd_extract, cmd_build
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(sample_tlk_bytes)

        # Extract to text
        txt_path = str(tmp_path / 'tlk.txt')
        args = type('Args', (), {'input': tlk_path, 'output': txt_path})()
        cmd_extract(args)
        assert os.path.exists(txt_path)

        # Build back to binary
        out_path = str(tmp_path / 'TLKA_REBUILT')
        args = type('Args', (), {'input': txt_path, 'output': out_path})()
        cmd_build(args)

        # Verify binary matches original
        with open(out_path, 'rb') as f:
            rebuilt = f.read()
        assert rebuilt == sample_tlk_bytes

    def test_extract_format(self, tmp_path, sample_tlk_bytes):
        """Extract produces readable text with record headers and separators."""
        from ult3edit.tlk import cmd_extract
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(sample_tlk_bytes)

        txt_path = str(tmp_path / 'tlk.txt')
        args = type('Args', (), {'input': tlk_path, 'output': txt_path})()
        cmd_extract(args)

        with open(txt_path, 'r') as f:
            text = f.read()
        assert '# Record 0' in text
        assert 'HELLO ADVENTURER' in text
        assert '---' in text  # Record separator
        assert 'WELCOME' in text
        assert 'TO MY SHOP' in text

    def test_build_multiline_records(self, tmp_path):
        """Build correctly encodes multi-line records with $FF line breaks."""
        from ult3edit.tlk import cmd_build
        txt_path = str(tmp_path / 'tlk.txt')
        with open(txt_path, 'w') as f:
            f.write('# Record 0\nLINE ONE\nLINE TWO\n---\n# Record 1\nSINGLE\n')

        out_path = str(tmp_path / 'TLK_OUT')
        args = type('Args', (), {'input': txt_path, 'output': out_path})()
        cmd_build(args)

        with open(out_path, 'rb') as f:
            data = f.read()
        # Record 0: "LINE ONE" + $FF + "LINE TWO" + $00
        assert data[0] == ord('L') | 0x80
        assert 0xFF in data  # Line break between records
        assert data[-1] == 0x00  # Final record terminator


# =============================================================================
# Save PLRS editing
# =============================================================================


class TestTlkRegexSearch:
    def test_regex_match(self):
        assert _match_line("HELLO WORLD", r"HEL+O", True)

    def test_regex_no_match(self):
        assert not _match_line("HELLO WORLD", r"^WORLD", True)

    def test_regex_case_insensitive(self):
        assert _match_line("Hello World", r"hello", True)

    def test_plain_match_still_works(self):
        assert _match_line("HELLO WORLD", "hello", False)

    def test_plain_no_match(self):
        assert not _match_line("HELLO WORLD", "zzz", False)

    def test_regex_pattern_groups(self):
        assert _match_line("LOOK FOR THE MARK OF FIRE", r"MARK.*FIRE", True)

    def test_regex_alternation(self):
        assert _match_line("THE CASTLE", r"castle|town", True)
        assert _match_line("THE TOWN", r"castle|town", True)
        assert not _match_line("THE DUNGEON", r"castle|town", True)


# =============================================================================
# Progression checker
# =============================================================================


class TestTlkCmdView:
    """Tests for tlk.cmd_view — dialog viewing."""

    def _make_tlk(self, path, text='Hello'):
        """Create a single-record TLK file."""
        data = encode_record([text])
        path.write_bytes(bytes(data))

    def test_view_single_file(self, tmp_path, capsys):
        """View a single TLK file."""
        from ult3edit.tlk import cmd_view
        tlk = tmp_path / 'TLKA'
        self._make_tlk(tlk, 'TEST DIALOG')
        args = argparse.Namespace(
            path=str(tlk), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'TEST DIALOG' in out

    def test_view_json(self, tmp_path):
        """View --json produces valid JSON."""
        from ult3edit.tlk import cmd_view
        tlk = tmp_path / 'TLKA'
        self._make_tlk(tlk, 'JSON dialog')
        outfile = tmp_path / 'tlk.json'
        args = argparse.Namespace(
            path=str(tlk), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'records' in result

    def test_view_directory(self, tmp_path, capsys):
        """View all TLK files in a directory."""
        from ult3edit.tlk import cmd_view
        tlk = tmp_path / 'TLKA'
        self._make_tlk(tlk, 'Town dialog')
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'TLKA' in out or 'Town dialog' in out or len(out) > 0


class TestTlkCmdImport:
    """Tests for tlk.cmd_import — dialog import from JSON."""

    def test_import_roundtrip(self, tmp_path, capsys):
        """Import from JSON writes correct TLK data."""
        from ult3edit.tlk import cmd_import, load_tlk_records
        tlk_path = tmp_path / 'TLKA'
        tlk_path.write_bytes(bytes(64))  # placeholder
        json_path = tmp_path / 'dialog.json'
        json_path.write_text(json.dumps({
            'records': [
                {'lines': ['Hello traveler', 'Welcome!']},
                {'lines': ['Goodbye']},
            ]
        }))
        args = argparse.Namespace(
            file=str(tlk_path), json_file=str(json_path),
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        records = load_tlk_records(str(tlk_path))
        assert len(records) == 2
        assert 'HELLO TRAVELER' in records[0][0]

    def test_import_dry_run(self, tmp_path, capsys):
        """Dry run doesn't write changes."""
        from ult3edit.tlk import cmd_import
        tlk_path = tmp_path / 'TLKA'
        original = bytes(64)
        tlk_path.write_bytes(original)
        json_path = tmp_path / 'dialog.json'
        json_path.write_text(json.dumps({'records': [{'lines': ['Test']}]}))
        args = argparse.Namespace(
            file=str(tlk_path), json_file=str(json_path),
            dry_run=True, backup=False, output=None)
        cmd_import(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        assert tlk_path.read_bytes() == original  # unchanged

    def test_import_with_backup(self, tmp_path, capsys):
        """Import with --backup creates .bak file."""
        from ult3edit.tlk import cmd_import
        tlk_path = tmp_path / 'TLKA'
        tlk_path.write_bytes(bytes(64))
        json_path = tmp_path / 'dialog.json'
        json_path.write_text(json.dumps({'records': [{'lines': ['Backed up']}]}))
        args = argparse.Namespace(
            file=str(tlk_path), json_file=str(json_path),
            dry_run=False, backup=True, output=None)
        cmd_import(args)
        assert os.path.exists(str(tlk_path) + '.bak')


# =============================================================================
# Import TypeError bug fix tests
# =============================================================================


class TestTlkEncodeRecordCase:
    """Tests for TLK encode_record uppercase forcing."""

    def test_encode_forces_uppercase(self):
        """encode_record converts lowercase to uppercase high-ASCII."""
        data = encode_record(['hello'])
        # Each char should be uppercase: H=0xC8, E=0xC5, L=0xCC, L=0xCC, O=0xCF
        assert data[0] == 0xC8  # H
        assert data[1] == 0xC5  # E
        assert data[2] == 0xCC  # L
        assert data[3] == 0xCC  # L
        assert data[4] == 0xCF  # O
        assert data[5] == 0x00  # TLK_RECORD_END

    def test_encode_preserves_uppercase(self):
        """encode_record keeps already-uppercase text unchanged."""
        data = encode_record(['HELLO'])
        assert data[0] == 0xC8  # H
        assert data[4] == 0xCF  # O

    def test_encode_mixed_case(self):
        """encode_record normalizes mixed case to uppercase."""
        data = encode_record(['HeLLo'])
        assert data[0] == 0xC8  # H
        assert data[1] == 0xC5  # E (was lowercase e)
        assert data[4] == 0xCF  # O (was lowercase o)


class TestTlkFindReplaceError:
    """Tests for TLK --find without --replace error message."""

    def test_find_without_replace_exits(self, tmp_path, capsys):
        """--find without --replace gives correct error message."""
        from ult3edit.tlk import cmd_edit
        tlk = tmp_path / 'TLKA'
        tlk.write_bytes(bytes(64))
        args = argparse.Namespace(
            file=str(tlk), find='hello', replace=None,
            record=None, text=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)
        err = capsys.readouterr().err
        assert 'must be used together' in err

    def test_replace_without_find_exits(self, tmp_path, capsys):
        """--replace without --find gives correct error message."""
        from ult3edit.tlk import cmd_edit
        tlk = tmp_path / 'TLKA'
        tlk.write_bytes(bytes(64))
        args = argparse.Namespace(
            file=str(tlk), find=None, replace='world',
            record=None, text=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)
        err = capsys.readouterr().err
        assert 'must be used together' in err


# =============================================================================
# Special truncated file, DiskContext leak, TUI fixes
# =============================================================================


class TestTlkErrorPaths:
    """Tests for tlk cmd_view/cmd_edit error exits."""

    def test_view_no_tlk_files(self, tmp_path):
        """cmd_view on empty directory exits."""
        from ult3edit.tlk import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_edit_no_args_exits(self, tmp_path):
        """cmd_edit with no --record/--text and no --find/--replace exits."""
        from ult3edit.tlk import cmd_edit
        tlk = tmp_path / 'TLKA'
        tlk.write_bytes(encode_record(['TEST']))
        args = argparse.Namespace(
            file=str(tlk), find=None, replace=None,
            record=None, text=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)


# =============================================================================
# Round-trip integrity tests
# =============================================================================


class TestTlkMultilineRoundTrip:
    """Verify TLK multi-line dialog records survive encode→decode."""

    def test_multiline_encode_decode(self):
        """Multi-line records round-trip through encode→decode."""
        from ult3edit.tlk import decode_record
        lines = ['HELLO TRAVELER', 'WELCOME TO TOWN', 'FAREWELL']
        encoded = encode_record(lines)
        decoded = decode_record(encoded)
        assert decoded == lines

    def test_single_line_roundtrip(self):
        """Single-line record round-trips correctly."""
        from ult3edit.tlk import decode_record
        lines = ['GOOD DAY']
        encoded = encode_record(lines)
        decoded = decode_record(encoded)
        assert decoded == lines

    def test_empty_string_in_lines(self):
        """Records with empty lines survive round-trip."""
        from ult3edit.tlk import decode_record
        lines = ['START', '', 'END']
        encoded = encode_record(lines)
        decoded = decode_record(encoded)
        assert decoded == lines


# =============================================================================
# Bug fix tests: MBS parsing and shapes overlay extraction
# =============================================================================


# =============================================================================
# FileUtil coverage
# =============================================================================


class TestTlkCmdErrors:
    """Test TLK command error paths."""

    def _make_tlk_file(self, tmp_path, records=None):
        """Create a TLK file with simple text records."""
        data = bytearray()
        if records is None:
            records = [['HELLO WORLD'], ['GOODBYE']]
        for rec in records:
            data.extend(encode_record(rec))
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_search_invalid_regex(self, tmp_path):
        """cmd_search with malformed regex exits."""
        path = self._make_tlk_file(tmp_path)
        args = argparse.Namespace(
            path=path, pattern='[unclosed', regex=True, json=False,
            output=None)
        with pytest.raises(SystemExit):
            cmd_search(args)

    def test_search_finds_text(self, tmp_path):
        """cmd_search with valid pattern finds results."""
        path = self._make_tlk_file(tmp_path)
        args = argparse.Namespace(
            path=path, pattern='HELLO', regex=False, json=False,
            output=None)
        # Should not raise
        cmd_search(args)

    def test_edit_record_out_of_range(self, tmp_path):
        """cmd_edit with record index beyond count exits."""
        from ult3edit.tlk import cmd_edit as tlk_cmd_edit
        path = self._make_tlk_file(tmp_path)
        args = argparse.Namespace(
            file=path, record=99, text='NEW TEXT',
            output=None, dry_run=True, backup=False)
        with pytest.raises(SystemExit):
            tlk_cmd_edit(args)

    def test_match_line_case_insensitive(self):
        """_match_line plain text is case-insensitive."""
        assert _match_line('Hello World', 'hello', False)
        assert _match_line('HELLO WORLD', 'hello', False)

    def test_match_line_regex(self):
        """_match_line with regex pattern."""
        assert _match_line('Hello World 123', r'\d+', True)
        assert not _match_line('Hello World', r'\d+', True)


# =============================================================================
# Diff module: detect_file_type
# =============================================================================


class TestTlkFindReplace:
    """Test TLK _cmd_find_replace."""

    def _make_tlk(self, tmp_path, text_records):
        """Create a TLK file with given text records."""
        data = bytearray()
        for rec in text_records:
            data.extend(encode_record(rec))
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_find_replace_basic(self, tmp_path):
        """Basic find-replace across records."""
        from ult3edit.tlk import _cmd_find_replace
        path = self._make_tlk(tmp_path, [['HELLO WORLD'], ['HELLO AGAIN']])
        args = argparse.Namespace(
            file=path, output=None, dry_run=False, backup=False,
            ignore_case=False)
        _cmd_find_replace(args, 'HELLO', 'GREETINGS')
        records = load_tlk_records(path)
        assert 'GREETINGS WORLD' in records[0]
        assert 'GREETINGS AGAIN' in records[1]

    def test_find_replace_case_insensitive(self, tmp_path):
        """Case-insensitive find-replace."""
        from ult3edit.tlk import _cmd_find_replace
        path = self._make_tlk(tmp_path, [['hello world']])
        args = argparse.Namespace(
            file=path, output=None, dry_run=False, backup=False,
            ignore_case=True)
        _cmd_find_replace(args, 'HELLO', 'HI')
        records = load_tlk_records(path)
        assert 'HI' in records[0][0]

    def test_find_replace_no_match(self, tmp_path, capsys):
        """No matches found — no write."""
        from ult3edit.tlk import _cmd_find_replace
        path = self._make_tlk(tmp_path, [['HELLO WORLD']])
        args = argparse.Namespace(
            file=path, output=None, dry_run=False, backup=False,
            ignore_case=False)
        _cmd_find_replace(args, 'XXXXX', 'YYYYY')
        captured = capsys.readouterr()
        assert '0 replacement' in captured.out

    def test_find_replace_dry_run(self, tmp_path):
        """Dry-run doesn't write changes."""
        from ult3edit.tlk import _cmd_find_replace
        path = self._make_tlk(tmp_path, [['HELLO WORLD']])
        with open(path, 'rb') as f:
            original = f.read()
        args = argparse.Namespace(
            file=path, output=None, dry_run=True, backup=False,
            ignore_case=False)
        _cmd_find_replace(args, 'HELLO', 'BYE')
        with open(path, 'rb') as f:
            after = f.read()
        assert after == original


# =============================================================================
# Roster _apply_edits coverage
# =============================================================================


class TestTlkCmdGaps:
    """Test TLK command gaps."""

    def test_cmd_view_no_files_in_dir(self, tmp_path):
        """cmd_view on directory with no TLK files exits."""
        from ult3edit.tlk import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_cmd_edit_find_without_replace(self, tmp_path):
        """cmd_edit with --find but no --replace exits."""
        from ult3edit.tlk import cmd_edit
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(b'\xC8\xC5\xCC\xCC\xCF\xFF')  # HELLO + end marker
        args = argparse.Namespace(
            file=path, find='HELLO', replace=None,
            record=None, text=None,
            dry_run=False, backup=False, output=None,
            case_sensitive=False, regex=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_cmd_edit_replace_without_find(self, tmp_path):
        """cmd_edit with --replace but no --find exits."""
        from ult3edit.tlk import cmd_edit
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(b'\xC8\xC5\xCC\xCC\xCF\xFF')
        args = argparse.Namespace(
            file=path, find=None, replace='WORLD',
            record=None, text=None,
            dry_run=False, backup=False, output=None,
            case_sensitive=False, regex=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_cmd_edit_record_out_of_range(self, tmp_path):
        """cmd_edit with record index past end of file exits."""
        from ult3edit.tlk import cmd_edit
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(b'\xC8\xC5\xCC\xCC\xCF\xFF')  # 1 record
        args = argparse.Namespace(
            file=path, find=None, replace=None,
            record=99, text='NEW TEXT',
            dry_run=False, backup=False, output=None,
            case_sensitive=False, regex=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestTlkSearchInvalidRegex:
    """Test tlk cmd_search exits on invalid regex."""

    def test_bad_regex_exits(self, tmp_path):
        from ult3edit.tlk import cmd_search
        args = argparse.Namespace(path=str(tmp_path), pattern='[unclosed',
                                  regex=True, ignore_case=False)
        with pytest.raises(SystemExit):
            cmd_search(args)


class TestTlkImportDestroysBinaryLeader:
    """Test that tlk cmd_import discards binary leader sections."""

    def test_binary_leader_not_preserved(self, tmp_path, capsys):
        from ult3edit.tlk import cmd_import
        # Create TLK with binary leader (non-text bytes) then text record
        binary_leader = bytearray([0x01, 0x02, 0x03])  # not high-ASCII text
        separator = bytearray([0x00])
        text_rec = bytearray([ord('H') | 0x80, ord('I') | 0x80])
        tlk_data = binary_leader + separator + text_rec + separator
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(tlk_data)
        # Import JSON with just the text record
        jdata = [{'lines': ['HELLO']}]
        jpath = os.path.join(str(tmp_path), 'tlk.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=False, backup=False, output=None)
        cmd_import(args)
        # After import, binary leader is gone — only the imported text remains
        with open(path, 'rb') as f:
            result = f.read()
        # The binary leader bytes should NOT be present
        assert result[:3] != bytes([0x01, 0x02, 0x03])


class TestTlkEditZeroTextRecords:
    """Test tlk cmd_edit error message when file has zero text records."""

    def test_zero_text_count_exits(self, tmp_path):
        from ult3edit.tlk import cmd_edit
        # Create TLK with only binary (non-text) content
        binary_data = bytearray([0x01, 0x02, 0x03, 0x00])
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(binary_data)
        args = argparse.Namespace(
            file=path, record=0, text='HI', find=None, replace=None,
            dry_run=False, backup=False, output=None, ignore_case=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestTlkFindWithoutReplace:
    """tlk cmd_edit with --find only (no --replace) exits with error."""

    def test_find_without_replace_exits(self, tmp_path, capsys):
        from ult3edit.tlk import cmd_edit
        tlk_path = os.path.join(str(tmp_path), 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(b'\xC8\xC5\xCC\xCC\xCF\x00')  # "HELLO" in high-ASCII
        args = argparse.Namespace(
            file=tlk_path, find='HELLO', replace=None,
            dry_run=False, backup=False, output=None,
            record=None, text=None, ignore_case=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_replace_without_find_exits(self, tmp_path, capsys):
        from ult3edit.tlk import cmd_edit
        tlk_path = os.path.join(str(tmp_path), 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(b'\xC8\xC5\xCC\xCC\xCF\x00')
        args = argparse.Namespace(
            file=tlk_path, find=None, replace='WORLD',
            dry_run=False, backup=False, output=None,
            record=None, text=None, ignore_case=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestTlkIsTextRecordEdgeCases:
    """Edge cases for is_text_record threshold logic."""

    def test_all_separators_returns_false(self):
        """Record with only line breaks has content_bytes=0 → False."""
        from ult3edit.tlk import is_text_record, TLK_LINE_BREAK
        data = bytes([TLK_LINE_BREAK, TLK_LINE_BREAK, TLK_LINE_BREAK])
        assert is_text_record(data) is False

    def test_exactly_70_percent_returns_false(self):
        """Exactly 70% high-ASCII returns False (threshold is > 0.7)."""
        from ult3edit.tlk import is_text_record
        # 7 high-ASCII + 3 low bytes = 70% exactly
        data = bytes([0xC1] * 7 + [0x10] * 3)
        assert is_text_record(data) is False

    def test_71_percent_returns_true(self):
        """Just above 70% threshold returns True."""
        from ult3edit.tlk import is_text_record
        # 8 high-ASCII + 3 low bytes = 72.7%
        data = bytes([0xC1] * 8 + [0x10] * 3)
        assert is_text_record(data) is True


# ── Migrated from test_new_features.py ──

class TestDialogEditorEmptyRecord:
    """Tests for DialogEditor save with empty records."""

    def test_encode_empty_lines_produces_nonzero(self):
        """encode_record(['']) produces at least 1 byte before stripping."""
        result = encode_record([''])
        # Empty line should produce just TLK_RECORD_END (0x00)
        assert len(result) >= 1
        # After stripping (encoded[:-1]), should not be empty
        # The dialog editor now guards against this
        stripped = result[:-1] if len(result) > 1 else result
        assert len(stripped) >= 1

    def test_dialog_editor_save_preserves_records(self):
        """DialogEditor save doesn't collapse null separators."""
        from ult3edit.tui.dialog_editor import DialogEditor
        from ult3edit.constants import TLK_RECORD_END
        # Build a TLK-like blob with 3 records
        records = [
            encode_record(['HELLO'])[:-1],  # strip trailing null
            encode_record(['WORLD'])[:-1],
            encode_record(['END'])[:-1],
        ]
        data = bytes([TLK_RECORD_END]).join(records)
        saved_data = []
        editor = DialogEditor('test', data, save_callback=lambda d: saved_data.append(d))
        assert len(editor.records) == 3
        # Mark record 0 as modified and save
        editor._modified_records.add(0)
        editor.dirty = True
        editor._save()
        # Should still produce valid data with 3 records
        assert len(saved_data) == 1
        # Re-parse should yield 3 records
        reloaded = DialogEditor('test', saved_data[0])
        assert len(reloaded.records) == 3


# =============================================================================
# Dialog editor TUI tests
# =============================================================================


class TestDialogEditorTUI:
    """Tests for DialogEditor from tui/dialog_editor.py."""

    def test_record_count(self, sample_tlk_bytes):
        """DialogEditor should parse 2 records from sample TLK data."""
        editor = DialogEditor('test', sample_tlk_bytes)
        assert len(editor.records) == 2

    def test_record_0_contains_hello(self, sample_tlk_bytes):
        """Record 0 text should contain 'HELLO'."""
        editor = DialogEditor('test', sample_tlk_bytes)
        text = ' '.join(editor.records[0])
        assert 'HELLO' in text

    def test_record_1_contains_welcome(self, sample_tlk_bytes):
        """Record 1 text should contain 'WELCOME'."""
        editor = DialogEditor('test', sample_tlk_bytes)
        text = ' '.join(editor.records[1])
        assert 'WELCOME' in text

    def test_modify_and_save(self, sample_tlk_bytes):
        """Modifying a record and saving produces valid data via callback."""
        saved = []
        editor = DialogEditor('test', sample_tlk_bytes,
                              save_callback=lambda d: saved.append(d))
        editor.records[0] = ['GOODBYE TRAVELER']
        editor._modified_records.add(0)
        editor.dirty = True
        editor._save()
        assert len(saved) == 1
        # Re-parse and verify modification
        editor2 = DialogEditor('test', saved[0])
        assert editor2.records[0] == ['GOODBYE TRAVELER']
        # Record 1 should be preserved
        assert 'WELCOME' in editor2.records[1][0]

    def test_selected_index_starts_at_zero(self, sample_tlk_bytes):
        """selected_index should start at 0."""
        editor = DialogEditor('test', sample_tlk_bytes)
        assert editor.selected_index == 0


# =============================================================================
# TLK extract/build additional tests
# =============================================================================


class TestTlkExtractBuildAdditional:
    """Additional tests for cmd_extract and cmd_build round-trip."""

    def test_extract_produces_text_file(self, tmp_path, sample_tlk_bytes):
        """cmd_extract should produce a text file from TLK binary."""
        from ult3edit.tlk import cmd_extract
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(sample_tlk_bytes)
        txt_path = str(tmp_path / 'tlk.txt')
        args = type('Args', (), {'input': tlk_path, 'output': txt_path})()
        cmd_extract(args)
        assert os.path.exists(txt_path)
        assert os.path.getsize(txt_path) > 0

    def test_extracted_file_contains_text(self, tmp_path, sample_tlk_bytes):
        """Extracted text file should contain record text."""
        from ult3edit.tlk import cmd_extract
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(sample_tlk_bytes)
        txt_path = str(tmp_path / 'tlk.txt')
        args = type('Args', (), {'input': tlk_path, 'output': txt_path})()
        cmd_extract(args)
        with open(txt_path, 'r', encoding='utf-8') as f:
            text = f.read()
        assert 'HELLO' in text
        assert 'WELCOME' in text

    def test_build_produces_binary(self, tmp_path):
        """cmd_build should produce a TLK binary from text file."""
        from ult3edit.tlk import cmd_build
        txt_path = str(tmp_path / 'tlk.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write('# Record 0\nHELLO WORLD\n---\n# Record 1\nGOODBYE\n')
        out_path = str(tmp_path / 'TLK_OUT')
        args = type('Args', (), {'input': txt_path, 'output': out_path})()
        cmd_build(args)
        assert os.path.exists(out_path)
        with open(out_path, 'rb') as f:
            data = f.read()
        assert len(data) > 0
        # Verify it contains valid TLK records
        records = load_tlk_records(out_path)
        assert len(records) == 2
        assert records[0] == ['HELLO WORLD']
        assert records[1] == ['GOODBYE']

    def test_extract_build_roundtrip_preserves_content(self, tmp_path, sample_tlk_bytes):
        """Extract then build should produce binary with same decoded content."""
        from ult3edit.tlk import cmd_extract, cmd_build
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(sample_tlk_bytes)
        # Extract
        txt_path = str(tmp_path / 'tlk.txt')
        args_extract = type('Args', (), {'input': tlk_path, 'output': txt_path})()
        cmd_extract(args_extract)
        # Build
        rebuilt_path = str(tmp_path / 'TLKA_REBUILT')
        args_build = type('Args', (), {'input': txt_path, 'output': rebuilt_path})()
        cmd_build(args_build)
        # Compare decoded content
        original_records = load_tlk_records(tlk_path)
        rebuilt_records = load_tlk_records(rebuilt_path)
        assert len(rebuilt_records) == len(original_records)
        for orig, rebuilt in zip(original_records, rebuilt_records):
            assert orig == rebuilt


# =============================================================================
# Batch 3: Coverage for tlk.py uncovered lines
# =============================================================================


class TestIsTextRecordEmpty:
    """Cover line 28: is_text_record returns False for empty data."""

    def test_empty_bytes(self):
        assert is_text_record(b'') is False


class TestLoadTlkSkipBinaryFalse:
    """Cover line 89: load_tlk_records with skip_binary=False."""

    def test_binary_records_included(self, tmp_path):
        """Binary records are included when skip_binary=False."""
        # Build a TLK file with a binary record and a text record
        binary_part = bytearray([0x20, 0x30, 0x4C, 0x10, 0x08, 0x00])
        text_part = bytearray()
        for ch in 'HELLO':
            text_part.append(ord(ch) | 0x80)
        text_part.append(0x00)
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytes(binary_part + text_part))
        # With skip_binary=True (default), binary record is excluded
        recs_skip = load_tlk_records(path, skip_binary=True)
        assert len(recs_skip) == 1
        # With skip_binary=False, binary record is included
        recs_all = load_tlk_records(path, skip_binary=False)
        assert len(recs_all) == 2


class TestCmdViewDirJson:
    """Cover lines 111-119: cmd_view directory mode with --json."""

    def test_view_dir_json_output(self, tmp_path):
        from ult3edit.tlk import cmd_view
        # Create a TLK file in the directory
        rec = encode_record(['TEST DIALOG'])
        (tmp_path / 'TLKA').write_bytes(bytes(rec))
        outfile = tmp_path / 'output.json'
        args = argparse.Namespace(
            path=str(tmp_path), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'TLKA' in result
        assert 'location' in result['TLKA']
        assert 'records' in result['TLKA']


class TestCmdViewTruncation:
    """Cover line 129: cmd_view truncates long text to 72 chars."""

    def test_long_text_truncated(self, tmp_path, capsys):
        from ult3edit.tlk import cmd_view
        long_text = 'A' * 100
        rec = encode_record([long_text])
        (tmp_path / 'TLKA').write_bytes(bytes(rec))
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert '...' in out


class TestCmdBuildEmptyBlock:
    """Cover line 181: cmd_build skips empty blocks."""

    def test_build_with_empty_block(self, tmp_path):
        from ult3edit.tlk import cmd_build
        txt = '# Record 0\nHELLO\n---\n\n---\n# Record 1\nWORLD\n'
        txt_path = str(tmp_path / 'tlk.txt')
        with open(txt_path, 'w') as f:
            f.write(txt)
        out_path = str(tmp_path / 'TLK_OUT')
        args = type('Args', (), {'input': txt_path, 'output': out_path})()
        cmd_build(args)
        records = load_tlk_records(out_path)
        assert len(records) == 2
        assert records[0] == ['HELLO']
        assert records[1] == ['WORLD']


class TestCmdEditWritePath:
    """Cover lines 251-257: cmd_edit writing to output file."""

    def test_edit_record_writes(self, tmp_path, capsys):
        from ult3edit.tlk import cmd_edit
        rec = encode_record(['HELLO WORLD']) + encode_record(['GOODBYE'])
        tlk_path = tmp_path / 'TLKA'
        tlk_path.write_bytes(bytes(rec))
        out_path = str(tmp_path / 'TLKA_OUT')
        args = argparse.Namespace(
            file=str(tlk_path), record=0, text='HI THERE',
            find=None, replace=None, ignore_case=False,
            output=out_path, backup=False, dry_run=False)
        cmd_edit(args)
        records = load_tlk_records(out_path)
        assert records[0] == ['HI THERE']
        assert records[1] == ['GOODBYE']
        out = capsys.readouterr().out
        assert 'Updated record 0' in out


class TestCmdSearchSingleFileRegex:
    """Cover line 350: cmd_search on single file with regex match."""

    def test_search_regex_single_file(self, tmp_path, capsys):
        rec = encode_record(['LOOK FOR MARK OF FIRE'])
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytes(rec))
        args = argparse.Namespace(
            path=path, pattern=r'MARK.*FIRE', regex=True,
            json=False, output=None)
        cmd_search(args)
        out = capsys.readouterr().out
        assert 'MARK OF FIRE' in out

    def test_search_no_results(self, tmp_path, capsys):
        rec = encode_record(['HELLO WORLD'])
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytes(rec))
        args = argparse.Namespace(
            path=path, pattern='ZZZZZ', regex=False,
            json=False, output=None)
        cmd_search(args)
        out = capsys.readouterr().out
        assert 'No matches' in out


class TestTlkDispatchAll:
    """Cover lines 462-472: dispatch routes to all subcommands."""

    def test_dispatch_view(self, tmp_path, capsys):
        from ult3edit.tlk import dispatch
        rec = encode_record(['TEST'])
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytes(rec))
        args = argparse.Namespace(
            tlk_command='view', path=path, json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'TEST' in out

    def test_dispatch_extract(self, tmp_path, capsys):
        from ult3edit.tlk import dispatch
        rec = encode_record(['DATA'])
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(bytes(rec))
        txt_path = str(tmp_path / 'out.txt')
        args = argparse.Namespace(
            tlk_command='extract', input=tlk_path, output=txt_path)
        dispatch(args)
        assert os.path.exists(txt_path)

    def test_dispatch_build(self, tmp_path, capsys):
        from ult3edit.tlk import dispatch
        txt_path = str(tmp_path / 'in.txt')
        with open(txt_path, 'w') as f:
            f.write('# Record 0\nBUILD TEST\n')
        out_path = str(tmp_path / 'TLK_OUT')
        args = argparse.Namespace(
            tlk_command='build', input=txt_path, output=out_path)
        dispatch(args)
        assert os.path.exists(out_path)

    def test_dispatch_edit(self, tmp_path, capsys):
        from ult3edit.tlk import dispatch
        rec = encode_record(['BEFORE'])
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytes(rec))
        out_path = str(tmp_path / 'OUT')
        args = argparse.Namespace(
            tlk_command='edit', file=path, record=0, text='AFTER',
            find=None, replace=None, ignore_case=False,
            output=out_path, backup=False, dry_run=False)
        dispatch(args)
        records = load_tlk_records(out_path)
        assert records[0] == ['AFTER']

    def test_dispatch_search(self, tmp_path, capsys):
        from ult3edit.tlk import dispatch
        rec = encode_record(['HELLO'])
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytes(rec))
        args = argparse.Namespace(
            tlk_command='search', path=path, pattern='HELLO',
            regex=False, json=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'HELLO' in out

    def test_dispatch_import(self, tmp_path, capsys):
        from ult3edit.tlk import dispatch
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(bytes(64))
        json_path = str(tmp_path / 'dlg.json')
        with open(json_path, 'w') as f:
            json.dump({'records': [{'lines': ['IMPORTED']}]}, f)
        args = argparse.Namespace(
            tlk_command='import', file=tlk_path, json_file=json_path,
            output=None, backup=False, dry_run=False)
        dispatch(args)
        records = load_tlk_records(tlk_path)
        assert records[0] == ['IMPORTED']

    def test_dispatch_unknown(self, capsys):
        from ult3edit.tlk import dispatch
        args = argparse.Namespace(tlk_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err


class TestTlkMain:
    """Cover lines 479-528: main() standalone entry point."""

    def test_main_view(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.tlk import main
        rec = encode_record(['MAIN TEST'])
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytes(rec))
        monkeypatch.setattr(sys, 'argv', ['ult3-tlk', 'view', path])
        main()
        out = capsys.readouterr().out
        assert 'MAIN TEST' in out

    def test_main_search(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.tlk import main
        rec = encode_record(['FIND ME'])
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytes(rec))
        monkeypatch.setattr(sys, 'argv', ['ult3-tlk', 'search', path, 'FIND'])
        main()
        out = capsys.readouterr().out
        assert 'FIND ME' in out

    def test_main_extract_build(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.tlk import main
        rec = encode_record(['ROUNDTRIP'])
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(bytes(rec))
        txt_path = str(tmp_path / 'out.txt')
        monkeypatch.setattr(sys, 'argv', ['ult3-tlk', 'extract', tlk_path, txt_path])
        main()
        assert os.path.exists(txt_path)

    def test_main_edit(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.tlk import main
        rec = encode_record(['ORIGINAL'])
        path = str(tmp_path / 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytes(rec))
        out_path = str(tmp_path / 'OUT')
        monkeypatch.setattr(sys, 'argv', [
            'ult3-tlk', 'edit', path, '--record', '0',
            '--text', 'EDITED', '-o', out_path])
        main()
        records = load_tlk_records(out_path)
        assert records[0] == ['EDITED']

    def test_main_import(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.tlk import main
        tlk_path = str(tmp_path / 'TLKA')
        with open(tlk_path, 'wb') as f:
            f.write(bytes(64))
        json_path = str(tmp_path / 'dlg.json')
        with open(json_path, 'w') as f:
            json.dump([{'lines': ['VIA MAIN']}], f)
        monkeypatch.setattr(sys, 'argv', ['ult3-tlk', 'import', tlk_path, json_path])
        main()
        records = load_tlk_records(tlk_path)
        assert records[0] == ['VIA MAIN']

    def test_main_no_command(self, capsys, monkeypatch):
        import sys
        from ult3edit.tlk import main
        monkeypatch.setattr(sys, 'argv', ['ult3-tlk'])
        main()
        err = capsys.readouterr().err
        assert 'Usage' in err

