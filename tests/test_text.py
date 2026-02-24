"""Tests for game text tool."""

import os

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
