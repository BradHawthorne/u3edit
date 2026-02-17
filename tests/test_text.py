"""Tests for game text tool."""

import os
import pytest

from u3edit.text import load_text_records


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
