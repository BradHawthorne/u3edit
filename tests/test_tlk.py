"""Tests for TLK dialog tool."""

import os
import pytest

from u3edit.tlk import decode_record, encode_record, load_tlk_records


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
