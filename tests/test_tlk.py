"""Tests for TLK dialog tool."""

import argparse
import os
import pytest

from u3edit.tlk import (decode_record, encode_record, load_tlk_records,
                         is_text_record, cmd_edit)
from u3edit.tui.dialog_editor import DialogEditor
from u3edit.constants import TLK_RECORD_END


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
