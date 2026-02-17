"""Tests for file utilities."""

import os
import pytest

from u3edit.fileutil import (
    resolve_game_file, find_game_files, decode_high_ascii, encode_high_ascii,
)


class TestResolveGameFile:
    def test_with_hash_suffix(self, tmp_dir):
        path = os.path.join(tmp_dir, 'MAPA#061000')
        with open(path, 'wb') as f:
            f.write(b'\x00')
        result = resolve_game_file(tmp_dir, 'MAP', 'A')
        assert result is not None
        assert 'MAPA' in result

    def test_without_hash_suffix(self, tmp_dir):
        path = os.path.join(tmp_dir, 'MAPA')
        with open(path, 'wb') as f:
            f.write(b'\x00')
        result = resolve_game_file(tmp_dir, 'MAP', 'A')
        assert result == path

    def test_not_found(self, tmp_dir):
        result = resolve_game_file(tmp_dir, 'MAP', 'Z')
        assert result is None

    def test_excludes_dproj(self, tmp_dir):
        # Create a .dproj file that should be excluded
        path = os.path.join(tmp_dir, 'MAPA#061000.dproj')
        with open(path, 'wb') as f:
            f.write(b'\x00')
        result = resolve_game_file(tmp_dir, 'MAP', 'A')
        assert result is None


class TestFindGameFiles:
    def test_finds_multiple(self, tmp_dir):
        for letter in 'ABC':
            with open(os.path.join(tmp_dir, f'MON{letter}#069900'), 'wb') as f:
                f.write(b'\x00')
        results = find_game_files(tmp_dir, 'MON', 'ABCZ')
        assert len(results) == 3
        letters = [r[0] for r in results]
        assert 'A' in letters and 'B' in letters and 'C' in letters


class TestDecodeHighAscii:
    def test_simple(self):
        data = bytes([0xC8, 0xC5, 0xCC, 0xCC, 0xCF])  # HELLO
        assert decode_high_ascii(data) == 'HELLO'

    def test_stops_at_null(self):
        data = bytes([0xC8, 0xC9, 0x00, 0xC1])
        assert decode_high_ascii(data) == 'HI'

    def test_empty(self):
        assert decode_high_ascii(b'\x00') == ''
        assert decode_high_ascii(b'') == ''

    def test_space(self):
        data = bytes([0xC8, 0xA0, 0xC9])  # 'H I'
        assert decode_high_ascii(data) == 'H I'


class TestEncodeHighAscii:
    def test_simple(self):
        result = encode_high_ascii('HERO', 10)
        assert len(result) == 10
        assert result[0] == ord('H') | 0x80
        assert result[4] == 0  # Padding

    def test_truncation(self):
        result = encode_high_ascii('VERY LONG NAME HERE', 10)
        assert len(result) == 10

    def test_uppercase(self):
        result = encode_high_ascii('hero', 4)
        assert result[0] == ord('H') | 0x80

    def test_roundtrip(self):
        original = 'HERO'
        encoded = encode_high_ascii(original, 10)
        decoded = decode_high_ascii(encoded)
        assert decoded == original
