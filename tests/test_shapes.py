"""Tests for the shapes module: glyph rendering, HGR encoding, overlay strings,
tile compilation, SHPS code guard, and CLI subcommands (compile/decompile/edit/import/view)."""

import argparse
import json
import os
import subprocess
import sys

import pytest

from ult3edit.shapes import (
    render_glyph_ascii, render_glyph_grid, glyph_to_dict, tile_to_dict,
    detect_format, glyph_to_pixels, render_hgr_row, write_png,
    GLYPH_SIZE, GLYPH_WIDTH, GLYPH_HEIGHT, SHPS_FILE_SIZE,
)
from ult3edit.shapes import (
    encode_overlay_string, replace_overlay_string,
    extract_overlay_strings,
)

_JSR_46BA_BYTES = bytes([0x20, 0xBA, 0x46])


def _help_output(module: str, subcmd: str) -> str:
    """Get --help output from a standalone module entry point."""
    result = subprocess.run(
        [sys.executable, '-m', f'ult3edit.{module}', subcmd, '--help'],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout + result.stderr


# =============================================================================
# Shapes glyph rendering
# =============================================================================

class TestShapesGlyphRendering:
    def _make_shps(self, glyphs=256):
        """Create a synthetic SHPS file."""
        data = bytearray(glyphs * GLYPH_SIZE)
        # Put a recognizable pattern in glyph 0: checkerboard
        data[0] = 0x55  # .#.#.#.
        data[1] = 0x2A  # .#.#.#. (inverted)
        data[2] = 0x55
        data[3] = 0x2A
        data[4] = 0x55
        data[5] = 0x2A
        data[6] = 0x55
        data[7] = 0x2A
        # Put a solid block in glyph 1
        for i in range(8, 16):
            data[i] = 0x7F  # #######
        return bytes(data)

    def test_render_glyph_ascii(self):
        data = self._make_shps()
        lines = render_glyph_ascii(data, 0)
        assert len(lines) == GLYPH_HEIGHT
        assert all(len(line) == GLYPH_WIDTH for line in lines)
        # Glyph 0 has alternating pattern
        assert '#' in lines[0]
        assert '.' in lines[0]

    def test_render_solid_glyph(self):
        data = self._make_shps()
        lines = render_glyph_ascii(data, GLYPH_SIZE)  # glyph 1
        assert all(line == '#######' for line in lines)

    def test_render_glyph_grid(self):
        data = self._make_shps()
        grid = render_glyph_grid(data, 0)
        assert len(grid) == GLYPH_HEIGHT
        assert all(len(row) == GLYPH_WIDTH for row in grid)

    def test_glyph_to_dict(self):
        data = self._make_shps()
        d = glyph_to_dict(data, 0)
        assert d['index'] == 0
        assert len(d['raw']) == GLYPH_SIZE
        assert '55' in d['hex'].upper()

    def test_tile_to_dict(self):
        data = self._make_shps()
        d = tile_to_dict(data, 0)
        assert d['tile_id'] == 0
        assert d['name'] == 'Water'
        assert len(d['frames']) == 4

    def test_detect_charset(self):
        data = self._make_shps()
        fmt = detect_format(data, 'SHPS#060800')
        assert fmt['type'] == 'charset'
        assert fmt['glyphs'] == 256
        assert fmt['tiles'] == 64

    def test_detect_overlay(self):
        data = bytes(960)
        fmt = detect_format(data, 'SHP0#069400')
        assert fmt['type'] == 'overlay'

    def test_glyph_to_pixels(self):
        data = self._make_shps()
        pixels = glyph_to_pixels(data, GLYPH_SIZE)  # solid glyph 1
        assert len(pixels) == GLYPH_WIDTH * GLYPH_HEIGHT
        # All pixels should be white (fg) for a solid glyph
        assert all(p == (255, 255, 255) for p in pixels)


# =============================================================================
# Shapes HGR rendering
# =============================================================================

class TestShapesHGR:
    def test_render_hgr_row_all_black(self):
        row = bytes([0x00, 0x00])
        pixels = render_hgr_row(row)
        assert len(pixels) == 14  # 2 bytes x 7 pixels
        assert all(p == (0, 0, 0) for p in pixels)

    def test_render_hgr_row_all_white(self):
        row = bytes([0x7F, 0x7F])
        pixels = render_hgr_row(row)
        assert len(pixels) == 14
        assert all(p == (255, 255, 255) for p in pixels)

    def test_render_hgr_row_palette_colors(self):
        # Single isolated bit at position 0, palette 0 -> purple
        row = bytes([0x01])
        pixels = render_hgr_row(row)
        assert pixels[0] == (255, 68, 253)  # purple (even col, palette 0)

    def test_render_hgr_row_palette_1(self):
        # Bit 7 set = palette 1, single bit at position 0 -> blue
        row = bytes([0x81])
        pixels = render_hgr_row(row)
        assert pixels[0] == (20, 207, 253)  # blue (even col, palette 1)


# =============================================================================
# Shapes file operations
# =============================================================================

class TestShapesFileOps:
    def test_edit_glyph(self, tmp_path):
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)

        # Simulate editing glyph 0
        with open(path, 'rb') as f:
            data = bytearray(f.read())
        new_bytes = bytes([0xFF] * 8)
        data[0:8] = new_bytes
        with open(path, 'wb') as f:
            f.write(data)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0:8] == new_bytes

    def test_json_round_trip(self, tmp_path):
        data = bytearray(SHPS_FILE_SIZE)
        data[0] = 0x55  # pattern in glyph 0
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)

        # Export to dict
        d = glyph_to_dict(data, 0)
        assert d['raw'][0] == 0x55

        # Import back
        import_data = bytearray(SHPS_FILE_SIZE)
        import_data[0:8] = bytes(d['raw'])
        assert import_data[0] == 0x55

    def test_write_png(self, tmp_path):
        pixels = [(255, 0, 0)] * (7 * 8)  # red
        out = str(tmp_path / 'test.png')
        write_png(out, pixels, 7, 8)
        assert os.path.exists(out)
        with open(out, 'rb') as f:
            header = f.read(8)
        assert header[:4] == b'\x89PNG'


# =============================================================================
# Shapes overlay string extraction
# =============================================================================

class TestShapesOverlay:
    def test_extract_overlay_strings(self):
        from ult3edit.shapes import extract_overlay_strings
        # Build a fake overlay with JSR $46BA + inline text
        data = bytearray(64)
        # JSR $46BA at offset 0
        data[0] = 0x20
        data[1] = 0xBA
        data[2] = 0x46
        # Inline high-ASCII text "HELLO" + null
        for i, ch in enumerate('HELLO'):
            data[3 + i] = ord(ch) | 0x80
        data[8] = 0x00  # terminator
        strings = extract_overlay_strings(data)
        assert len(strings) == 1
        assert strings[0]['text'] == 'HELLO'
        assert strings[0]['text_offset'] == 3

    def test_extract_multiple_strings(self):
        from ult3edit.shapes import extract_overlay_strings
        data = bytearray(64)
        # First string at offset 0
        data[0:3] = bytes([0x20, 0xBA, 0x46])
        data[3] = ord('A') | 0x80
        data[4] = 0x00
        # Some code bytes
        data[5] = 0xA9
        data[6] = 0x00
        # Second string at offset 7
        data[7:10] = bytes([0x20, 0xBA, 0x46])
        data[10] = ord('B') | 0x80
        data[11] = ord('C') | 0x80
        data[12] = 0x00
        strings = extract_overlay_strings(data)
        assert len(strings) == 2
        assert strings[0]['text'] == 'A'
        assert strings[1]['text'] == 'BC'

    def test_overlay_with_newline(self):
        from ult3edit.shapes import extract_overlay_strings
        data = bytearray(32)
        data[0:3] = bytes([0x20, 0xBA, 0x46])
        data[3] = ord('H') | 0x80
        data[4] = ord('I') | 0x80
        data[5] = 0xFF  # line break
        data[6] = ord('!') | 0x80
        data[7] = 0x00
        strings = extract_overlay_strings(data)
        assert len(strings) == 1
        assert strings[0]['text'] == 'HI\n!'

    def test_detect_overlay_shop_type(self):
        from ult3edit.shapes import detect_format
        data = bytes(960)
        fmt = detect_format(data, 'SHP3#069400')
        assert fmt['type'] == 'overlay'
        assert fmt['shop_type'] == 'Pub/Tavern'

    def test_detect_text_as_hgr_bitmap(self):
        from ult3edit.shapes import detect_format
        data = bytes(1024)
        fmt = detect_format(data, 'TEXT#061000')
        assert fmt['type'] == 'hgr_bitmap'
        assert 'title screen' in fmt['description']


# =============================================================================
# SHPS code guard
# =============================================================================

class TestShpsCodeGuard:
    def test_check_code_region_empty(self):
        from ult3edit.shapes import check_shps_code_region, SHPS_FILE_SIZE
        data = bytearray(SHPS_FILE_SIZE)
        assert not check_shps_code_region(data)

    def test_check_code_region_populated(self):
        from ult3edit.shapes import (
            check_shps_code_region, SHPS_CODE_OFFSET, SHPS_FILE_SIZE,
        )
        data = bytearray(SHPS_FILE_SIZE)
        data[SHPS_CODE_OFFSET] = 0x4C  # JMP instruction
        data[SHPS_CODE_OFFSET + 1] = 0x00
        data[SHPS_CODE_OFFSET + 2] = 0x08
        assert check_shps_code_region(data)


# =============================================================================
# Overlay string encode / replace / round-trip
# =============================================================================

class TestEncodeOverlayString:
    def test_basic(self):
        encoded = encode_overlay_string('HI')
        assert encoded == bytearray([ord('H') | 0x80, ord('I') | 0x80, 0x00])

    def test_newline(self):
        encoded = encode_overlay_string('A\nB')
        assert encoded == bytearray([ord('A') | 0x80, 0xFF, ord('B') | 0x80, 0x00])


class TestReplaceOverlayString:
    def _make_shp(self, text_bytes):
        """Build minimal SHP-like data with one inline string."""
        # JSR $46BA + text + $00 + padding code byte
        data = bytearray(b'\x00\x00')  # prefix
        data += _JSR_46BA_BYTES
        data += text_bytes
        data += bytearray(b'\x00')  # terminator
        data += bytearray(b'\xEA\xEA')  # NOP code after string
        return data

    def test_exact_fit(self):
        original_text = bytearray([ord('H') | 0x80, ord('I') | 0x80])
        data = self._make_shp(original_text)
        strings = extract_overlay_strings(data)
        assert len(strings) == 1
        s = strings[0]
        result = replace_overlay_string(data, s['text_offset'], s['text_end'], 'AB')
        new_strings = extract_overlay_strings(result)
        assert new_strings[0]['text'] == 'AB'

    def test_shorter_pads_with_null(self):
        original_text = bytearray([ord('H') | 0x80, ord('E') | 0x80,
                                   ord('L') | 0x80])
        data = self._make_shp(original_text)
        strings = extract_overlay_strings(data)
        s = strings[0]
        result = replace_overlay_string(data, s['text_offset'], s['text_end'], 'A')
        # The original region should have A + nulls, code bytes preserved
        assert result[s['text_offset']] == ord('A') | 0x80
        assert result[s['text_offset'] + 1] == 0x00
        # Code bytes after string region should be untouched
        assert result[-2:] == bytearray(b'\xEA\xEA')

    def test_too_long_raises(self):
        original_text = bytearray([ord('H') | 0x80, ord('I') | 0x80])
        data = self._make_shp(original_text)
        strings = extract_overlay_strings(data)
        s = strings[0]
        with pytest.raises(ValueError, match='exceeds available space'):
            replace_overlay_string(
                data, s['text_offset'], s['text_end'], 'TOOLONGTEXT')


class TestOverlayStringRoundTrip:
    def test_extract_replace_extract(self):
        # Build SHP with "SHOP" inline string
        data = bytearray(b'\xEA')  # prefix
        data += _JSR_46BA_BYTES
        for ch in 'SHOP':
            data.append(ord(ch) | 0x80)
        data.append(0x00)  # terminator
        data += bytearray(b'\x60')  # RTS after

        strings = extract_overlay_strings(data)
        assert strings[0]['text'] == 'SHOP'

        s = strings[0]
        data = replace_overlay_string(data, s['text_offset'], s['text_end'], 'ARMS')
        strings2 = extract_overlay_strings(data)
        assert strings2[0]['text'] == 'ARMS'
        # RTS preserved
        assert data[-1] == 0x60


# =============================================================================
# CLI parity for edit-string
# =============================================================================

class TestCliParityShapesEditString:
    def test_help_shows_edit_string(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit.shapes', 'edit-string', '--help'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert '--offset' in result.stdout
        assert '--text' in result.stdout


# =============================================================================
# cmd_edit_string functional tests
# =============================================================================

class TestCmdEditStringFunctional:
    """Functional tests for shapes edit-string on synthesized SHP overlay."""

    def _make_shp_overlay(self):
        """Create a synthetic SHP overlay with a JSR $46BA inline string."""
        data = bytearray(256)
        # Put JSR $46BA at offset 10
        data[10] = 0x20  # JSR
        data[11] = 0xBA
        data[12] = 0x46
        # Inline high-ASCII string "HELLO" + null terminator at offset 13
        hello = [0xC8, 0xC5, 0xCC, 0xCC, 0xCF, 0x00]
        data[13:13 + len(hello)] = hello
        # Another JSR $46BA at offset 30
        data[30] = 0x20
        data[31] = 0xBA
        data[32] = 0x46
        # Inline "BYE" + null at offset 33
        bye = [0xC2, 0xD9, 0xC5, 0x00]
        data[33:33 + len(bye)] = bye
        return data

    def test_edit_string_replaces_text(self, tmp_path):
        from ult3edit.shapes import cmd_edit_string
        data = self._make_shp_overlay()
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)

        args = type('Args', (), {
            'file': path,
            'offset': 13,  # text_offset of "HELLO"
            'text': 'HI',
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        cmd_edit_string(args)

        with open(path, 'rb') as f:
            result = f.read()
        # "HI" encoded as high-ASCII: 0xC8 0xC9 + null
        assert result[13] == 0xC8  # H
        assert result[14] == 0xC9  # I
        assert result[15] == 0x00  # null terminator
        # Remaining bytes null-padded
        assert result[16] == 0x00
        assert result[17] == 0x00

    def test_edit_string_dry_run(self, tmp_path):
        from ult3edit.shapes import cmd_edit_string
        data = self._make_shp_overlay()
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)

        args = type('Args', (), {
            'file': path,
            'offset': 13,
            'text': 'HI',
            'output': None,
            'backup': False,
            'dry_run': True,
        })()
        cmd_edit_string(args)

        # File unchanged
        with open(path, 'rb') as f:
            result = f.read()
        assert result[13] == 0xC8  # Still 'H' from HELLO
        assert result[14] == 0xC5  # Still 'E' from HELLO

    def test_edit_string_output_file(self, tmp_path):
        from ult3edit.shapes import cmd_edit_string
        data = self._make_shp_overlay()
        path = str(tmp_path / 'SHP0')
        out_path = str(tmp_path / 'SHP0_out')
        with open(path, 'wb') as f:
            f.write(data)

        args = type('Args', (), {
            'file': path,
            'offset': 33,  # text_offset of "BYE"
            'text': 'NO',
            'output': out_path,
            'backup': False,
            'dry_run': False,
        })()
        cmd_edit_string(args)

        # Original unchanged
        with open(path, 'rb') as f:
            assert f.read()[33] == 0xC2  # B
        # Output has new value
        with open(out_path, 'rb') as f:
            result = f.read()
        assert result[33] == 0xCE  # N
        assert result[34] == 0xCF  # O

    def test_edit_string_bad_offset_exits(self, tmp_path):
        from ult3edit.shapes import cmd_edit_string
        data = self._make_shp_overlay()
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)

        args = type('Args', (), {
            'file': path,
            'offset': 99,  # No string here
            'text': 'X',
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        with pytest.raises(SystemExit):
            cmd_edit_string(args)


# =============================================================================
# Shapes cmd_edit integration
# =============================================================================

class TestShapesEditIntegration:
    """Integration tests for shapes cmd_edit()."""

    def _make_shps(self, tmp_path):
        """Create a synthetic 2048-byte SHPS file."""
        data = bytearray(2048)
        # Fill glyph 0 with a known pattern
        for i in range(8):
            data[i] = 0x55
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        return path, data

    def test_edit_glyph(self, tmp_path):
        """cmd_edit() updates a glyph's raw bytes."""
        from ult3edit.shapes import cmd_edit as shapes_cmd_edit
        path, original = self._make_shps(tmp_path)

        args = type('Args', (), {
            'file': path, 'glyph': 0,
            'data': 'FF FF FF FF FF FF FF FF',
            'output': None, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_edit(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result[0:8]) == [0xFF] * 8

    def test_edit_glyph_dry_run(self, tmp_path):
        """cmd_edit() with dry_run does not modify file."""
        from ult3edit.shapes import cmd_edit as shapes_cmd_edit
        path, original = self._make_shps(tmp_path)

        args = type('Args', (), {
            'file': path, 'glyph': 0,
            'data': 'AA AA AA AA AA AA AA AA',
            'output': None, 'backup': False, 'dry_run': True,
        })()
        shapes_cmd_edit(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(original)

    def test_edit_glyph_output_file(self, tmp_path):
        """cmd_edit() writes to --output file."""
        from ult3edit.shapes import cmd_edit as shapes_cmd_edit
        path, _ = self._make_shps(tmp_path)
        out_path = str(tmp_path / 'SHPS_OUT')

        args = type('Args', (), {
            'file': path, 'glyph': 1,
            'data': '01 02 03 04 05 06 07 08',
            'output': out_path, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_edit(args)

        with open(out_path, 'rb') as f:
            result = f.read()
        assert list(result[8:16]) == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_edit_backup_skipped_with_output(self, tmp_path):
        """cmd_edit() with --output and --backup should NOT create .bak of input."""
        from ult3edit.shapes import cmd_edit as shapes_cmd_edit
        path, _ = self._make_shps(tmp_path)
        out_path = str(tmp_path / 'SHPS_OUT')

        args = type('Args', (), {
            'file': path, 'glyph': 0,
            'data': 'FF FF FF FF FF FF FF FF',
            'output': out_path, 'backup': True, 'dry_run': False,
        })()
        shapes_cmd_edit(args)

        assert os.path.exists(out_path), "output file should exist"
        assert not os.path.exists(path + '.bak'), \
            "backup should not be created when --output is a different file"


# =============================================================================
# Shapes cmd_import integration
# =============================================================================

class TestShapesImportIntegration:
    """Integration tests for shapes cmd_import()."""

    def _make_shps(self, tmp_path):
        """Create a synthetic 2048-byte SHPS file."""
        data = bytearray(2048)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        return path, data

    def test_import_glyph_list(self, tmp_path):
        """cmd_import() updates glyphs from flat list format."""
        from ult3edit.shapes import cmd_import as shapes_cmd_import
        path, _ = self._make_shps(tmp_path)

        jdata = [
            {'index': 0, 'raw': [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]},
            {'index': 2, 'raw': [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00, 0x11]},
        ]
        json_path = str(tmp_path / 'glyphs.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result[0:8]) == [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]
        assert list(result[16:24]) == [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00, 0x11]
        # Glyph 1 should be unchanged (zeros)
        assert list(result[8:16]) == [0] * 8

    def test_import_tiles_format(self, tmp_path):
        """cmd_import() updates glyphs from tiles dict format."""
        from ult3edit.shapes import cmd_import as shapes_cmd_import
        path, _ = self._make_shps(tmp_path)

        jdata = {
            'tiles': [{
                'tile_id': 0,
                'frames': [
                    {'index': 0, 'raw': [0xFF] * 8},
                    {'index': 1, 'raw': [0xAA] * 8},
                ]
            }]
        }
        json_path = str(tmp_path / 'tiles.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result[0:8]) == [0xFF] * 8
        assert list(result[8:16]) == [0xAA] * 8

    def test_import_dry_run(self, tmp_path):
        """cmd_import() with dry_run does not modify file."""
        from ult3edit.shapes import cmd_import as shapes_cmd_import
        path, original = self._make_shps(tmp_path)

        jdata = [{'index': 0, 'raw': [0xFF] * 8}]
        json_path = str(tmp_path / 'glyphs.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        shapes_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == bytes(original)


# =============================================================================
# Shapes cmd_import malformed JSON
# =============================================================================

class TestShapesImportMalformedJson:
    """Verify shapes cmd_import() handles missing keys gracefully."""

    def _make_shps(self, tmp_path):
        data = bytearray(2048)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        return path, data

    def test_missing_index_in_list(self, tmp_path):
        """Entries missing 'index' key should be skipped, not crash."""
        from ult3edit.shapes import cmd_import as shapes_cmd_import
        path, _ = self._make_shps(tmp_path)
        jdata = [
            {'raw': [0xFF] * 8},  # missing 'index'
            {'index': 1, 'raw': [0xAA] * 8},  # valid
        ]
        json_path = str(tmp_path / 'glyphs.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_import(args)  # should not raise KeyError
        with open(path, 'rb') as f:
            result = f.read()
        # Glyph 0 untouched (missing index skipped), glyph 1 updated
        assert list(result[0:8]) == [0] * 8
        assert list(result[8:16]) == [0xAA] * 8

    def test_missing_raw_in_tiles(self, tmp_path):
        """Frames missing 'raw' key should be skipped, not crash."""
        from ult3edit.shapes import cmd_import as shapes_cmd_import
        path, _ = self._make_shps(tmp_path)
        jdata = {
            'tiles': [{
                'frames': [
                    {'index': 0},  # missing 'raw'
                    {'index': 1, 'raw': [0xBB] * 8},  # valid
                ]
            }]
        }
        json_path = str(tmp_path / 'tiles.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        shapes_cmd_import(args)  # should not raise KeyError
        with open(path, 'rb') as f:
            result = f.read()
        assert list(result[0:8]) == [0] * 8
        assert list(result[8:16]) == [0xBB] * 8


# =============================================================================
# Tile compiler parsing
# =============================================================================

class TestTileCompilerParsing:
    """Test tile_compiler.py text-art parsing."""

    def test_parse_single_tile(self):
        """Parse a single tile definition."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = (
            '# Tile 0x00: Test\n'
            '#######\n'
            '.......\n'
            '#.#.#.#\n'
            '.#.#.#.\n'
            '#.#.#.#\n'
            '.......\n'
            '#######\n'
            '.......\n'
        )
        tiles = parse_tiles_file(text)
        assert len(tiles) == 1
        idx, data = tiles[0]
        assert idx == 0
        assert len(data) == 8
        assert data[0] == 0x7F  # All 7 bits set = 1111111 = 0x7F

    def test_parse_multiple_tiles(self):
        """Parse two tiles separated by blank line."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = ('# Tile 0x00: First\n'
                + '#######\n' * 8
                + '\n'
                + '# Tile 0x01: Second\n'
                + '.......\n' * 8)
        tiles = parse_tiles_file(text)
        assert len(tiles) == 2
        assert tiles[0][0] == 0
        assert tiles[1][0] == 1

    def test_parse_hex_index(self):
        """Parse a tile with hex index."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = '# Tile 0x1A: Test\n' + '.......\n' * 8
        tiles = parse_tiles_file(text)
        assert tiles[0][0] == 0x1A

    def test_parse_decimal_index(self):
        """Parse a tile with decimal index."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = '# Tile 42: Test\n' + '.......\n' * 8
        tiles = parse_tiles_file(text)
        assert tiles[0][0] == 42


class TestTileCompilerBitEncoding:
    """Test tile_compiler.py pixel->bit encoding."""

    def test_all_on(self):
        """All pixels on = 0x7F per row."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = '# Tile 0x00: All on\n' + '#######\n' * 8
        tiles = parse_tiles_file(text)
        _, data = tiles[0]
        for b in data:
            assert b == 0x7F

    def test_all_off(self):
        """All pixels off = 0x00 per row."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        text = '# Tile 0x00: All off\n' + '.......\n' * 8
        tiles = parse_tiles_file(text)
        _, data = tiles[0]
        for b in data:
            assert b == 0x00

    def test_bit_order(self):
        """First char = bit 0, last char = bit 6."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file
        # Only leftmost pixel on
        text = '# Tile 0x00: Bit 0\n' + ('#......\n') * 8
        tiles = parse_tiles_file(text)
        _, data = tiles[0]
        assert data[0] == 0x01  # Bit 0 only

        # Only rightmost pixel on
        text2 = '# Tile 0x00: Bit 6\n' + ('......#\n') * 8
        tiles2 = parse_tiles_file(text2)
        _, data2 = tiles2[0]
        assert data2[0] == 0x40  # Bit 6 only


class TestTileCompilerRoundTrip:
    """Test tile_compiler.py compile -> decompile round-trip."""

    def test_round_trip(self, tmp_path):
        """Decompile SHPS data then compile back should reproduce bytes."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import decompile_shps, parse_tiles_file

        # Create a known SHPS binary (just first 3 tiles)
        data = bytearray(2048)
        data[0:8] = bytes([0x7F, 0x41, 0x41, 0x41, 0x41, 0x41, 0x7F, 0x00])
        data[8:16] = bytes([0x00, 0x3E, 0x22, 0x22, 0x22, 0x3E, 0x00, 0x00])

        # Decompile
        text = decompile_shps(bytes(data))

        # Parse back
        tiles = parse_tiles_file(text)
        assert len(tiles) == 256

        # First tile should match
        _, recompiled = tiles[0]
        assert recompiled == bytes(data[0:8])

        # Second tile should match
        _, recompiled2 = tiles[1]
        assert recompiled2 == bytes(data[8:16])

    def test_compile_to_json(self):
        """Compile tiles to JSON format."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file, compile_to_json
        text = '# Tile 0x05: Test\n' + '#......\n' * 8
        tiles = parse_tiles_file(text)
        result = compile_to_json(tiles)
        assert 'tiles' in result
        assert result['tiles'][0]['frames'][0]['index'] == 5
        assert result['tiles'][0]['frames'][0]['raw'] == [1] * 8

    def test_compile_to_script(self):
        """Compile tiles to shell script format."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from tile_compiler import parse_tiles_file, compile_to_script
        text = '# Tile 0x00: Test\n' + '.......\n' * 8
        tiles = parse_tiles_file(text)
        script = compile_to_script(tiles)
        assert 'ult3edit shapes edit' in script
        assert '--glyph 0' in script
        assert '--backup' in script


# =============================================================================
# Tile compiler edge cases
# =============================================================================

class TestTileCompilerEdgeCases:
    """Edge case tests for tile_compiler.py."""

    TOOLS_DIR = os.path.join(os.path.dirname(__file__),
                              '..', 'conversions', 'tools')

    def _get_mod(self):
        mod_path = os.path.join(self.TOOLS_DIR, 'tile_compiler.py')
        import importlib.util
        spec = importlib.util.spec_from_file_location('tile_compiler', mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_parse_tile_dimensions(self):
        """Tile parser requires exactly 8 rows of 7 columns per glyph."""
        mod = self._get_mod()
        # Build a minimal .tiles source for one glyph
        lines = ['# Tile 0x00: Test']
        for _ in range(8):
            lines.append('#' * 7)
        text = '\n'.join(lines) + '\n'
        tiles = mod.parse_tiles_file(text)
        assert len(tiles) >= 1
        # parse_tiles_file returns list of (index, bytes) tuples
        assert tiles[0][0] == 0  # index
        assert len(tiles[0][1]) == 8  # 8 bytes per glyph

    def test_decompile_then_compile_matches(self):
        """Decompile binary -> compile back produces identical bytes."""
        mod = self._get_mod()
        # Create a 2048-byte SHPS with one known glyph at index 0
        shps = bytearray(2048)
        original = bytes([0b1010101, 0b0101010, 0b1111111, 0b0000000,
                          0b1100110, 0b0011001, 0b1111000, 0b0001111])
        shps[0:8] = original
        # Decompile to text
        text = mod.decompile_shps(bytes(shps))
        # Parse the text back
        tiles = mod.parse_tiles_file(text)
        # Find tile index 0
        glyph_bytes = None
        for idx, data in tiles:
            if idx == 0:
                glyph_bytes = data
                break
        assert glyph_bytes is not None
        assert glyph_bytes == original


# =============================================================================
# Shapes compile/decompile CLI subcommands
# =============================================================================

class TestShapesCompileSubcommand:
    """Test ult3edit shapes compile/decompile CLI subcommands."""

    def _make_tiles_source(self, path, count=2):
        """Create a .tiles source with test glyphs."""
        lines = []
        for i in range(count):
            lines.append(f'# Tile 0x{i:02X}: Test{i}')
            for row in range(8):
                # Alternating pattern
                if row % 2 == 0:
                    lines.append('#.#.#.#')
                else:
                    lines.append('.#.#.#.')
            lines.append('')
        with open(path, 'w') as f:
            f.write('\n'.join(lines))

    def test_compile_binary(self, tmp_dir):
        """Compile .tiles to 2048-byte SHPS binary."""
        from ult3edit.shapes import cmd_compile_tiles
        src = os.path.join(tmp_dir, 'test.tiles')
        self._make_tiles_source(src)
        out = os.path.join(tmp_dir, 'test.bin')
        args = argparse.Namespace(source=src, output=out, format='binary')
        cmd_compile_tiles(args)
        with open(out, 'rb') as f:
            data = f.read()
        assert len(data) == 2048
        # Tile 0 should have non-zero data
        assert data[0] != 0

    def test_compile_json(self, tmp_dir):
        """Compile .tiles to JSON format."""
        from ult3edit.shapes import cmd_compile_tiles
        src = os.path.join(tmp_dir, 'test.tiles')
        self._make_tiles_source(src, count=3)
        out = os.path.join(tmp_dir, 'test.json')
        args = argparse.Namespace(source=src, output=out, format='json')
        cmd_compile_tiles(args)
        with open(out, 'r') as f:
            result = json.load(f)
        assert 'tiles' in result
        assert len(result['tiles'][0]['frames']) == 3

    def test_decompile(self, tmp_dir):
        """Decompile SHPS binary to text-art."""
        from ult3edit.shapes import cmd_decompile_tiles
        # Create 2048-byte SHPS binary
        data = bytearray(2048)
        # Put a pattern in tile 0: alternating rows
        data[0] = 0b0101010  # #.#.#.#
        data[1] = 0b0101010
        bin_path = os.path.join(tmp_dir, 'test.bin')
        with open(bin_path, 'wb') as f:
            f.write(data)
        out = os.path.join(tmp_dir, 'test.tiles')
        args = argparse.Namespace(file=bin_path, output=out)
        cmd_decompile_tiles(args)
        with open(out, 'r') as f:
            text = f.read()
        assert '# Tile 0x00' in text
        assert '#' in text  # pixel-on chars present

    def test_compile_decompile_roundtrip(self, tmp_dir):
        """Compile then decompile preserves glyph pixel data."""
        from ult3edit.shapes import cmd_compile_tiles, cmd_decompile_tiles, \
            parse_tiles_text
        src = os.path.join(tmp_dir, 'orig.tiles')
        self._make_tiles_source(src, count=4)
        # Read original
        with open(src, 'r') as f:
            orig_tiles = parse_tiles_text(f.read())
        # Compile
        bin_path = os.path.join(tmp_dir, 'test.bin')
        args = argparse.Namespace(source=src, output=bin_path, format='binary')
        cmd_compile_tiles(args)
        # Decompile
        out = os.path.join(tmp_dir, 'decomp.tiles')
        args2 = argparse.Namespace(file=bin_path, output=out)
        cmd_decompile_tiles(args2)
        # Re-parse decompiled
        with open(out, 'r') as f:
            decomp_tiles = parse_tiles_text(f.read())
        # Find our original tiles in the decompiled output
        decomp_map = {idx: data for idx, data in decomp_tiles}
        for idx, orig_data in orig_tiles:
            assert idx in decomp_map
            assert decomp_map[idx] == orig_data

    def test_compile_no_output_prints_count(self, tmp_dir, capsys):
        """Compile without --output prints tile count."""
        from ult3edit.shapes import cmd_compile_tiles
        src = os.path.join(tmp_dir, 'test.tiles')
        self._make_tiles_source(src, count=5)
        args = argparse.Namespace(source=src, output=None, format='binary')
        cmd_compile_tiles(args)
        captured = capsys.readouterr()
        assert '5 tiles' in captured.out

    def test_parse_tiles_text_auto_index(self, tmp_dir):
        """Tiles without headers get auto-assigned sequential indices."""
        from ult3edit.shapes import parse_tiles_text
        text = '# Tile 0x10: Start\n'
        for _ in range(8):
            text += '#######\n'
        text += '\n'
        for _ in range(8):
            text += '.......\n'
        text += '\n'
        tiles = parse_tiles_text(text)
        assert len(tiles) == 2
        assert tiles[0][0] == 0x10
        assert tiles[1][0] == 0x11  # auto-assigned


# =============================================================================
# Shapes compile warnings
# =============================================================================

class TestShapesCompileWarnings:
    """Test shapes compile partial glyph set warning."""

    def test_partial_tileset_warns(self, tmp_path):
        """Compiling fewer than 256 glyphs warns on stderr."""
        from ult3edit.shapes import cmd_compile_tiles
        # Source with only 2 tiles
        lines = []
        for idx in range(2):
            lines.append(f'# Tile 0x{idx:02X}')
            for _ in range(8):
                lines.append('#......')
            lines.append('')
        src = tmp_path / 'partial.tiles'
        src.write_text('\n'.join(lines))
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), format='binary')
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile_tiles(args)
        assert 'only 2 of 256 glyphs' in stderr.getvalue()

    def test_full_tileset_no_warning(self, tmp_path):
        """Compiling all 256 glyphs produces no warning."""
        from ult3edit.shapes import cmd_compile_tiles, GLYPHS_PER_FILE
        lines = []
        for idx in range(GLYPHS_PER_FILE):
            lines.append(f'# Tile 0x{idx:02X}')
            for _ in range(8):
                lines.append('.......')
            lines.append('')
        src = tmp_path / 'full.tiles'
        src.write_text('\n'.join(lines))
        out = tmp_path / 'out.bin'
        args = argparse.Namespace(
            source=str(src), output=str(out), format='binary')
        import io
        import contextlib
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_compile_tiles(args)
        assert stderr.getvalue() == ''


# =============================================================================
# Shapes overlay bounds fix
# =============================================================================

class TestShapesOverlayBoundsFix:
    """Tests for shapes.py extract_overlay_strings off-by-one fix."""

    def test_string_at_end_of_data(self):
        """JSR $46BA pattern at the last possible position is found."""
        from ult3edit.shapes import extract_overlay_strings
        # Build data where JSR $46BA + inline string starts at len-3
        prefix = bytes(10)  # 10 zero bytes
        jsr = bytes([0x20, 0xBA, 0x46])  # JSR $46BA
        text = bytes([0xC8, 0xC9, 0x00])  # "HI" + null terminator
        data = prefix + jsr + text
        strings = extract_overlay_strings(data)
        assert len(strings) == 1
        assert strings[0]['text'] == 'HI'
        assert strings[0]['jsr_offset'] == 10

    def test_string_at_exact_boundary(self):
        """JSR $46BA pattern exactly at data end (no text following) found."""
        from ult3edit.shapes import extract_overlay_strings
        # JSR pattern at end with only null terminator after
        prefix = bytes(5)
        jsr = bytes([0x20, 0xBA, 0x46])
        term = bytes([0x00])  # null only -- empty string
        data = prefix + jsr + term
        strings = extract_overlay_strings(data)
        # Empty string should not be added (chars check filters it)
        assert len(strings) == 0


# =============================================================================
# Shapes pixel helpers
# =============================================================================

class TestShapesPixelHelpers:
    """Tests for shapes.py pixel scaling and rendering helpers."""

    def test_scale_pixels_noop(self):
        """Scale factor 1 returns pixels unchanged."""
        from ult3edit.shapes import scale_pixels
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        result, w, h = scale_pixels(pixels, 2, 2, 1)
        assert result == pixels
        assert w == 2
        assert h == 2

    def test_scale_pixels_2x(self):
        """Scale factor 2 doubles each dimension."""
        from ult3edit.shapes import scale_pixels
        pixels = [(255, 0, 0), (0, 255, 0),
                  (0, 0, 255), (255, 255, 0)]
        result, w, h = scale_pixels(pixels, 2, 2, 2)
        assert w == 4
        assert h == 4
        assert len(result) == 16
        # Top-left 2x2 block should be red
        assert result[0] == (255, 0, 0)
        assert result[1] == (255, 0, 0)
        assert result[4] == (255, 0, 0)
        assert result[5] == (255, 0, 0)

    def test_render_hgr_sprite_basic(self):
        """render_hgr_sprite produces correct pixel count."""
        from ult3edit.shapes import render_hgr_sprite
        # 1 byte wide, 2 rows tall
        data = bytes([0x00, 0x7F])
        pixels = render_hgr_sprite(data, width_bytes=1, height=2, offset=0)
        # Each byte produces 7 pixels (HGR)
        assert len(pixels) == 14  # 7 * 2

    def test_hgr_ascii_preview_basic(self):
        """hgr_ascii_preview produces text representation."""
        from ult3edit.shapes import hgr_ascii_preview
        # Create simple 2x2 pixel data
        black = (0, 0, 0)
        white = (255, 255, 255)
        pixels = [black, white, white, black]
        result = hgr_ascii_preview(pixels, 2, 2)
        assert len(result.split('\n')) == 2


# =============================================================================
# SHPS code region
# =============================================================================

class TestShpsCodeRegion:
    """Tests for check_shps_code_region function."""

    def test_data_too_short(self):
        """Returns False when data is shorter than code region offset."""
        from ult3edit.shapes import check_shps_code_region
        data = bytes(100)  # Way shorter than SHPS_CODE_OFFSET (0x1F9)
        assert check_shps_code_region(data) is False

    def test_code_region_all_zeros(self):
        """Returns False when code region is all zeros."""
        from ult3edit.shapes import check_shps_code_region, SHPS_CODE_OFFSET, SHPS_CODE_SIZE
        data = bytes(SHPS_CODE_OFFSET + SHPS_CODE_SIZE + 100)
        assert check_shps_code_region(data) is False

    def test_code_region_has_code(self):
        """Returns True when code region has non-zero bytes."""
        from ult3edit.shapes import check_shps_code_region, SHPS_CODE_OFFSET, SHPS_CODE_SIZE
        data = bytearray(SHPS_CODE_OFFSET + SHPS_CODE_SIZE + 100)
        data[SHPS_CODE_OFFSET] = 0x60  # RTS opcode
        assert check_shps_code_region(data) is True

    def test_code_region_last_byte_nonzero(self):
        """Returns True when only last byte of code region is non-zero."""
        from ult3edit.shapes import check_shps_code_region, SHPS_CODE_OFFSET, SHPS_CODE_SIZE
        data = bytearray(SHPS_CODE_OFFSET + SHPS_CODE_SIZE + 100)
        data[SHPS_CODE_OFFSET + SHPS_CODE_SIZE - 1] = 0x01
        assert check_shps_code_region(data) is True


# =============================================================================
# Shapes cmd_view / cmd_gaps
# =============================================================================

class TestShapesCmdGaps:
    """Test shapes command edge cases."""

    def test_cmd_view_no_file_in_dir(self, tmp_path):
        """cmd_view on directory with no SHPS files works or exits."""
        from ult3edit.shapes import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None,
            tile=None, glyph=True, color=False)
        try:
            cmd_view(args)
        except SystemExit:
            pass  # Expected if no files found


class TestShapesCmdEditGaps:
    """Test shapes cmd_edit error paths."""

    def test_edit_no_file_in_dir(self, tmp_path):
        """cmd_edit on directory with no SHPS file exits or falls through."""
        from ult3edit.shapes import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None,
            tile=None, glyph=True, color=False)
        try:
            cmd_view(args)
        except SystemExit:
            pass  # Expected


# =============================================================================
# Shapes import overlay strings
# =============================================================================

class TestShapesImportOverlayStrings:
    """Test shapes cmd_import with overlay strings JSON format."""

    def test_import_overlay_strings(self, tmp_path, capsys):
        from ult3edit.shapes import cmd_import
        # Build an SHP overlay with inline string "WEAPONS"
        data = bytearray(b'\x60' * 16)
        data += bytes([0x20, 0xBA, 0x46])  # JSR $46BA
        for ch in 'WEAPONS':
            data.append(ord(ch) | 0x80)
        data.append(0x00)  # null terminator
        data += bytearray(b'\x60' * 16)
        path = os.path.join(str(tmp_path), 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)
        # JSON with 'strings' key
        jdata = {
            'strings': [
                {'offset': 19, 'text': 'ARMS'}  # text_offset = 16 + 3 = 19
            ]
        }
        jpath = os.path.join(str(tmp_path), 'strings.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=False, backup=False, output=None)
        cmd_import(args)
        out = capsys.readouterr().out
        assert '1 string(s)' in out


class TestShapesImportUnrecognizedJSON:
    """Test shapes cmd_import rejects unrecognized JSON format."""

    def test_unrecognized_json_exits(self, tmp_path):
        from ult3edit.shapes import cmd_import
        path = os.path.join(str(tmp_path), 'SHPS')
        with open(path, 'wb') as f:
            f.write(bytearray(2048))
        jpath = os.path.join(str(tmp_path), 'bad.json')
        with open(jpath, 'w') as f:
            json.dump({'random_key': 123}, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_import(args)


# =============================================================================
# Shapes edit-string error paths
# =============================================================================

class TestShapesEditStringErrors:
    """Test shapes cmd_edit_string error paths."""

    def _make_overlay(self, tmp_path, text='HELLO'):
        data = bytearray(b'\x60' * 16)
        data += bytes([0x20, 0xBA, 0x46])
        for ch in text:
            data.append(ord(ch) | 0x80)
        data.append(0x00)
        data += bytearray(b'\x60' * 16)
        path = os.path.join(str(tmp_path), 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_non_overlay_exits(self, tmp_path):
        """cmd_edit_string on a SHPS file exits with error."""
        from ult3edit.shapes import cmd_edit_string
        path = os.path.join(str(tmp_path), 'SHPS')
        with open(path, 'wb') as f:
            f.write(bytearray(2048))
        args = argparse.Namespace(file=path, offset=0, text='X',
                                  dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit_string(args)

    def test_bad_offset_exits(self, tmp_path):
        """cmd_edit_string with nonexistent offset exits."""
        from ult3edit.shapes import cmd_edit_string
        path = self._make_overlay(tmp_path)
        args = argparse.Namespace(file=path, offset=9999, text='X',
                                  dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit_string(args)

    def test_text_too_long_exits(self, tmp_path):
        """cmd_edit_string with text longer than slot exits."""
        from ult3edit.shapes import cmd_edit_string
        path = self._make_overlay(tmp_path, text='HI')
        args = argparse.Namespace(file=path, offset=19, text='THIS IS WAY TOO LONG',
                                  dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit_string(args)


# =============================================================================
# Shapes compile no tiles
# =============================================================================

class TestShapesCompileNoTiles:
    """Test shapes cmd_compile_tiles exits when .tiles file has no tiles."""

    def test_empty_source_exits(self, tmp_path):
        from ult3edit.shapes import cmd_compile_tiles
        src = os.path.join(str(tmp_path), 'empty.tiles')
        with open(src, 'w') as f:
            f.write('# Just a comment\n')
        args = argparse.Namespace(source=src, output=None, format='binary')
        with pytest.raises(SystemExit):
            cmd_compile_tiles(args)


# =============================================================================
# Shapes cmd_view --tile
# =============================================================================

class TestShapesCmdViewTile:
    """Test shapes cmd_view with --tile N on a charset file."""

    def test_view_single_tile(self, tmp_path, capsys):
        from ult3edit.shapes import cmd_view
        path = os.path.join(str(tmp_path), 'SHPS')
        # Create a valid SHPS file (2048 bytes)
        data = bytearray(2048)
        # Put some nonzero data in tile 0 (glyphs 0-3, each 8 bytes)
        for i in range(32):
            data[i] = 0xAA
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            path=path, json=False, output=None, tile=0)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Tile' in out or 'tile' in out


# =============================================================================
# Shapes decompile too small
# =============================================================================

class TestShapesDecompileTooSmall:
    """Test decompile_shps raises ValueError for too-small file."""

    def test_truncated_raises(self):
        from ult3edit.shapes import decompile_shps
        with pytest.raises(ValueError, match='too small'):
            decompile_shps(bytes(1024))

    def test_exact_size_ok(self):
        from ult3edit.shapes import decompile_shps
        result = decompile_shps(bytes(2048))
        assert '# Tile' in result


# =============================================================================
# Shapes cmd_view binary format
# =============================================================================

class TestShapesCmdViewBinaryFormat:
    """Test shapes cmd_view on a non-charset, non-overlay file (binary hex dump)."""

    def test_binary_hex_dump(self, tmp_path, capsys):
        from ult3edit.shapes import cmd_view
        # Create a file that doesn't match any known format
        # Size not 2048 (SHPS), name not SHP0-7, not TEXT/1024
        path = os.path.join(str(tmp_path), 'UNKNOWN')
        with open(path, 'wb') as f:
            f.write(bytearray(512))
        args = argparse.Namespace(
            path=path, json=False, output=None, tile=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Binary' in out or '00' in out


# =============================================================================
# Shapes parse header ambiguity
# =============================================================================

class TestShapesParseHeaderAmbiguity:
    """Test that _TILE_HEADER_RE matches before comment skip in parse_tiles_text."""

    def test_tile_header_comment_treated_as_header(self):
        from ult3edit.shapes import parse_tiles_text
        # A comment that looks like a tile header is treated as a header
        text = '# Tile 0x10: Some comment\n'
        # Add 8 pixel rows for tile 0x10 (GLYPH_HEIGHT=8)
        for _ in range(8):
            text += '........\n'
        tiles = parse_tiles_text(text)
        # The comment is parsed as a header for tile 0x10
        indices = [idx for idx, _ in tiles]
        assert 0x10 in indices


# =============================================================================
# Shapes compile JSON structure
# =============================================================================

class TestShapesCompileJsonStructure:
    """shapes.py: compile JSON groups glyphs by tile (4 frames per tile)."""

    def test_compile_json_has_tile_groups(self, tmp_path):
        """Compile 8 glyphs -> 2 tiles, verify JSON has tile_id and frames."""
        from ult3edit.shapes import cmd_compile_tiles
        # Create a .tiles file with 2 tiles (8 glyphs, indices 0-7)
        lines = []
        for idx in range(8):
            lines.append(f'# Glyph 0x{idx:02X}')
            for row in range(8):
                lines.append('#.#.#.#' if row % 2 == 0 else '.#.#.#.')
            lines.append('')
        src = tmp_path / 'test.tiles'
        src.write_text('\n'.join(lines))
        out = tmp_path / 'tiles.json'
        args = argparse.Namespace(
            source=str(src), output=str(out), format='json')
        cmd_compile_tiles(args)
        data = json.loads(out.read_text())
        assert 'tiles' in data
        # Should have 2 tile groups (0x00 and 0x04)
        assert len(data['tiles']) == 2
        # Each tile has tile_id, name, and frames
        t0 = data['tiles'][0]
        assert 'tile_id' in t0
        assert 'name' in t0
        assert 'frames' in t0
        assert t0['tile_id'] == 0
        assert len(t0['frames']) == 4  # 4 animation frames per tile

    def test_compile_json_frame_indices(self, tmp_path):
        """Verify frame indices are sequential within each tile group."""
        from ult3edit.shapes import cmd_compile_tiles
        lines = []
        for idx in range(4):
            lines.append(f'# Glyph 0x{idx:02X}')
            for _ in range(8):
                lines.append('#######')
            lines.append('')
        src = tmp_path / 'test.tiles'
        src.write_text('\n'.join(lines))
        out = tmp_path / 'tiles.json'
        args = argparse.Namespace(
            source=str(src), output=str(out), format='json')
        cmd_compile_tiles(args)
        data = json.loads(out.read_text())
        frames = data['tiles'][0]['frames']
        indices = [f['index'] for f in frames]
        assert indices == [0, 1, 2, 3]


# =============================================================================
# Coverage tests: cmd_export() PNG generation
# =============================================================================

class TestCmdExport:
    """Tests for cmd_export() PNG generation — single glyph, sheet, scaling."""

    def _make_shps_file(self, tmp_path, pattern=0x55):
        """Create a synthetic SHPS file with a known pattern."""
        data = bytearray(SHPS_FILE_SIZE)
        for i in range(0, SHPS_FILE_SIZE, GLYPH_SIZE):
            data[i] = pattern
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_export_creates_glyph_pngs(self, tmp_path):
        """cmd_export() creates individual glyph PNG files."""
        from ult3edit.shapes import cmd_export
        shps_path = self._make_shps_file(tmp_path)
        out_dir = str(tmp_path / 'export')
        args = argparse.Namespace(
            file=shps_path, output_dir=out_dir, scale=1, sheet=False)
        cmd_export(args)
        # Should create 256 PNG files
        assert os.path.exists(os.path.join(out_dir, 'glyph_000.png'))
        assert os.path.exists(os.path.join(out_dir, 'glyph_255.png'))

    def test_export_with_scaling(self, tmp_path):
        """cmd_export() with scale factor produces larger PNGs."""
        from ult3edit.shapes import cmd_export
        shps_path = self._make_shps_file(tmp_path)
        out_dir = str(tmp_path / 'export')
        args = argparse.Namespace(
            file=shps_path, output_dir=out_dir, scale=2, sheet=False)
        cmd_export(args)
        # PNGs should exist and be valid
        png_path = os.path.join(out_dir, 'glyph_000.png')
        assert os.path.exists(png_path)
        with open(png_path, 'rb') as f:
            header = f.read(8)
        assert header[:4] == b'\x89PNG'

    def test_export_with_sheet(self, tmp_path, capsys):
        """cmd_export() with --sheet generates a sprite sheet."""
        from ult3edit.shapes import cmd_export
        shps_path = self._make_shps_file(tmp_path)
        out_dir = str(tmp_path / 'export')
        args = argparse.Namespace(
            file=shps_path, output_dir=out_dir, scale=1, sheet=True)
        cmd_export(args)
        sheet_path = os.path.join(out_dir, 'glyph_sheet.png')
        assert os.path.exists(sheet_path)
        captured = capsys.readouterr()
        assert 'sprite sheet' in captured.out

    def test_export_non_charset_exits(self, tmp_path):
        """cmd_export() on non-charset file exits with error."""
        from ult3edit.shapes import cmd_export
        # Create a non-SHPS file (not 2048 bytes)
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(bytearray(512))
        out_dir = str(tmp_path / 'export')
        args = argparse.Namespace(
            file=path, output_dir=out_dir, scale=4, sheet=False)
        with pytest.raises(SystemExit):
            cmd_export(args)

    def test_export_default_scale(self, tmp_path):
        """cmd_export() defaults to scale=4 via getattr."""
        from ult3edit.shapes import cmd_export
        shps_path = self._make_shps_file(tmp_path)
        out_dir = str(tmp_path / 'export')
        # Namespace without 'scale' attribute — getattr fallback to 4
        args = argparse.Namespace(file=shps_path, output_dir=out_dir, sheet=False)
        cmd_export(args)
        assert os.path.exists(os.path.join(out_dir, 'glyph_000.png'))


# =============================================================================
# Coverage tests: cmd_edit() glyph editing error paths
# =============================================================================

class TestCmdEditCoverage:
    """Tests for cmd_edit() uncovered error paths."""

    def test_edit_glyph_out_of_range(self, tmp_path):
        """cmd_edit() with glyph index past file end exits."""
        from ult3edit.shapes import cmd_edit as shapes_cmd_edit
        # Create a small file (only 8 glyphs)
        data = bytearray(64)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, glyph=100,
            data='FF FF FF FF FF FF FF FF',
            output=None, backup=False, dry_run=False)
        with pytest.raises(SystemExit):
            shapes_cmd_edit(args)

    def test_edit_invalid_hex_data(self, tmp_path):
        """cmd_edit() with invalid hex data exits."""
        from ult3edit.shapes import cmd_edit as shapes_cmd_edit
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, glyph=0, data='ZZZZ',
            output=None, backup=False, dry_run=False)
        with pytest.raises(SystemExit):
            shapes_cmd_edit(args)

    def test_edit_wrong_byte_count(self, tmp_path):
        """cmd_edit() with wrong number of hex bytes exits."""
        from ult3edit.shapes import cmd_edit as shapes_cmd_edit
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, glyph=0, data='FF FF',
            output=None, backup=False, dry_run=False)
        with pytest.raises(SystemExit):
            shapes_cmd_edit(args)

    def test_edit_overlaps_code_region_warns(self, tmp_path, capsys):
        """cmd_edit() warns when editing overlaps embedded code region."""
        from ult3edit.shapes import cmd_edit as shapes_cmd_edit
        from ult3edit.shapes import SHPS_CODE_OFFSET
        data = bytearray(SHPS_FILE_SIZE)
        # Populate the code region so check_shps_code_region returns True
        data[SHPS_CODE_OFFSET] = 0x4C  # JMP instruction
        data[SHPS_CODE_OFFSET + 1] = 0x00
        data[SHPS_CODE_OFFSET + 2] = 0x08
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        # Glyph 63 overlaps the code region at 0x1F9 (63*8 = 0x1F8)
        out_path = str(tmp_path / 'SHPS_out')
        args = argparse.Namespace(
            file=path, glyph=63,
            data='AA BB CC DD EE FF 00 11',
            output=out_path, backup=False, dry_run=False)
        shapes_cmd_edit(args)
        captured = capsys.readouterr()
        assert 'overlaps embedded code' in captured.err

    def test_edit_backup_same_file(self, tmp_path):
        """cmd_edit() with --backup and no --output creates .bak."""
        from ult3edit.shapes import cmd_edit as shapes_cmd_edit
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, glyph=0,
            data='FF FF FF FF FF FF FF FF',
            output=None, backup=True, dry_run=False)
        shapes_cmd_edit(args)
        assert os.path.exists(path + '.bak')


# =============================================================================
# Coverage tests: cmd_import() overlay string and JSON import
# =============================================================================

class TestCmdImportCoverage:
    """Tests for cmd_import() uncovered paths."""

    def test_import_overlay_skip_missing_offset(self, tmp_path, capsys):
        """cmd_import() overlay string with bad offset produces warning."""
        from ult3edit.shapes import cmd_import
        # Build an SHP overlay with inline string
        data = bytearray(b'\x60' * 16)
        data += bytes([0x20, 0xBA, 0x46])  # JSR $46BA
        for ch in 'HELLO':
            data.append(ord(ch) | 0x80)
        data.append(0x00)
        data += bytearray(b'\x60' * 16)
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)
        # JSON with bad offset
        jdata = {'strings': [{'offset': 9999, 'text': 'NOPE'}]}
        jpath = str(tmp_path / 'strings.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=jpath,
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert 'No string at offset' in captured.err

    def test_import_overlay_skip_missing_keys(self, tmp_path, capsys):
        """cmd_import() overlay string entry missing offset/text is skipped."""
        from ult3edit.shapes import cmd_import
        data = bytearray(b'\x60' * 16)
        data += bytes([0x20, 0xBA, 0x46])
        for ch in 'HI':
            data.append(ord(ch) | 0x80)
        data.append(0x00)
        data += bytearray(b'\x60' * 16)
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)
        # Missing 'text' key
        jdata = {'strings': [{'offset': 19}]}
        jpath = str(tmp_path / 'strings.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=jpath,
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert '0 string(s)' in captured.out

    def test_import_overlay_too_long_warns(self, tmp_path, capsys):
        """cmd_import() overlay string too long produces warning."""
        from ult3edit.shapes import cmd_import
        data = bytearray(b'\x60' * 16)
        data += bytes([0x20, 0xBA, 0x46])
        for ch in 'HI':
            data.append(ord(ch) | 0x80)
        data.append(0x00)
        data += bytearray(b'\x60' * 16)
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)
        # String too long for 2-char slot
        jdata = {'strings': [{'offset': 19, 'text': 'THIS IS WAY TOO LONG'}]}
        jpath = str(tmp_path / 'strings.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=jpath,
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert 'exceeds available space' in captured.err

    def test_import_backup_existing_file(self, tmp_path):
        """cmd_import() with --backup creates .bak when writing in-place."""
        from ult3edit.shapes import cmd_import
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'index': 0, 'raw': [0xFF] * 8}]
        jpath = str(tmp_path / 'glyphs.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            file=path, json_file=jpath,
            output=None, backup=True, dry_run=False)
        cmd_import(args)
        assert os.path.exists(path + '.bak')


# =============================================================================
# Coverage tests: cmd_edit_string() additional paths
# =============================================================================

class TestCmdEditStringCoverage:
    """Additional cmd_edit_string tests for backup path."""

    def _make_overlay(self, tmp_path, text='HELLO'):
        data = bytearray(b'\x60' * 16)
        data += bytes([0x20, 0xBA, 0x46])
        for ch in text:
            data.append(ord(ch) | 0x80)
        data.append(0x00)
        data += bytearray(b'\x60' * 16)
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_edit_string_with_backup(self, tmp_path):
        """cmd_edit_string with --backup creates .bak file."""
        from ult3edit.shapes import cmd_edit_string
        path = self._make_overlay(tmp_path)
        args = argparse.Namespace(
            file=path, offset=19, text='HI',
            output=None, backup=True, dry_run=False)
        cmd_edit_string(args)
        assert os.path.exists(path + '.bak')


# =============================================================================
# Coverage tests: cmd_view() various format branches
# =============================================================================

class TestCmdViewCoverage:
    """Tests for cmd_view() uncovered branches."""

    def test_view_charset_json(self, tmp_path, capsys):
        """cmd_view() on a charset file with --json."""
        from ult3edit.shapes import cmd_view
        data = bytearray(SHPS_FILE_SIZE)
        data[0] = 0x55
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = str(tmp_path / 'out.json')
        args = argparse.Namespace(
            path=path, json=True, output=out_path, tile=None)
        cmd_view(args)
        with open(out_path, 'r') as f:
            result = json.load(f)
        assert 'tiles' in result
        assert result['format']['type'] == 'charset'

    def test_view_overlay_json(self, tmp_path):
        """cmd_view() on overlay file with --json."""
        from ult3edit.shapes import cmd_view
        data = bytearray(b'\x60' * 16)
        data += bytes([0x20, 0xBA, 0x46])
        for ch in 'SHOP':
            data.append(ord(ch) | 0x80)
        data.append(0x00)
        data += bytearray(b'\x60' * 16)
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = str(tmp_path / 'out.json')
        args = argparse.Namespace(
            path=path, json=True, output=out_path, tile=None)
        cmd_view(args)
        with open(out_path, 'r') as f:
            result = json.load(f)
        assert 'strings' in result

    def test_view_overlay_text(self, tmp_path, capsys):
        """cmd_view() on overlay file shows text output."""
        from ult3edit.shapes import cmd_view
        data = bytearray(b'\x60' * 16)
        data += bytes([0x20, 0xBA, 0x46])
        for ch in 'SHOP':
            data.append(ord(ch) | 0x80)
        data.append(0x00)
        data += bytearray(b'\x60' * 16)
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            path=path, json=False, output=None, tile=None)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'SHOP' in captured.out
        assert 'overlay' in captured.out.lower()

    def test_view_hgr_bitmap_json(self, tmp_path):
        """cmd_view() on HGR bitmap with --json."""
        from ult3edit.shapes import cmd_view
        data = bytearray(1024)
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = str(tmp_path / 'out.json')
        args = argparse.Namespace(
            path=path, json=True, output=out_path, tile=None)
        cmd_view(args)
        with open(out_path, 'r') as f:
            result = json.load(f)
        assert result['format']['type'] == 'hgr_bitmap'

    def test_view_hgr_bitmap_text(self, tmp_path, capsys):
        """cmd_view() on HGR bitmap shows text output."""
        from ult3edit.shapes import cmd_view
        data = bytearray(1024)
        path = str(tmp_path / 'TEXT')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            path=path, json=False, output=None, tile=None)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'HGR bitmap' in captured.out

    def test_view_binary_json(self, tmp_path):
        """cmd_view() on generic binary file with --json."""
        from ult3edit.shapes import cmd_view
        data = bytearray(512)
        path = str(tmp_path / 'UNKNOWN')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = str(tmp_path / 'out.json')
        args = argparse.Namespace(
            path=path, json=True, output=out_path, tile=None)
        cmd_view(args)
        with open(out_path, 'r') as f:
            result = json.load(f)
        assert result['format']['type'] == 'binary'

    def test_view_charset_all_tiles(self, tmp_path, capsys):
        """cmd_view() without --tile shows all tiles."""
        from ult3edit.shapes import cmd_view
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            path=path, json=False, output=None, tile=None)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Water' in captured.out or 'Tile' in captured.out

    def test_view_dir_with_shps_json(self, tmp_path):
        """cmd_view() on directory with SHPS and --json."""
        from ult3edit.shapes import cmd_view
        data = bytearray(SHPS_FILE_SIZE)
        shps_path = str(tmp_path / 'SHPS')
        with open(shps_path, 'wb') as f:
            f.write(data)
        out_path = str(tmp_path / 'out.json')
        args = argparse.Namespace(
            path=str(tmp_path), json=True, output=out_path, tile=None)
        cmd_view(args)
        with open(out_path, 'r') as f:
            result = json.load(f)
        assert 'tiles' in result

    def test_view_dir_with_specific_tile(self, tmp_path, capsys):
        """cmd_view() on directory with --tile shows one tile."""
        from ult3edit.shapes import cmd_view
        data = bytearray(SHPS_FILE_SIZE)
        data[0] = 0x7F
        shps_path = str(tmp_path / 'SHPS')
        with open(shps_path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None, tile=0)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Tile 0x00' in captured.out

    def test_view_dir_all_tiles(self, tmp_path, capsys):
        """cmd_view() on directory without --tile shows all tiles."""
        from ult3edit.shapes import cmd_view
        data = bytearray(SHPS_FILE_SIZE)
        shps_path = str(tmp_path / 'SHPS')
        with open(shps_path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None, tile=None)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Tile' in captured.out


# =============================================================================
# Coverage tests: cmd_compile_tiles() / cmd_decompile_tiles() edges
# =============================================================================

class TestCompileDecompileCoverage:
    """Additional coverage for compile/decompile edge cases."""

    def test_compile_json_no_output(self, tmp_path, capsys):
        """cmd_compile_tiles() JSON with no --output prints to stdout."""
        from ult3edit.shapes import cmd_compile_tiles
        lines = []
        for idx in range(4):
            lines.append(f'# Tile 0x{idx:02X}')
            for _ in range(8):
                lines.append('#.#.#.#')
            lines.append('')
        src = str(tmp_path / 'test.tiles')
        with open(src, 'w') as f:
            f.write('\n'.join(lines))
        args = argparse.Namespace(source=src, output=None, format='json')
        cmd_compile_tiles(args)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert 'tiles' in result

    def test_decompile_no_output_prints(self, tmp_path, capsys):
        """cmd_decompile_tiles() with no --output prints to stdout."""
        from ult3edit.shapes import cmd_decompile_tiles
        data = bytearray(SHPS_FILE_SIZE)
        data[0] = 0x7F
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(file=path, output=None)
        cmd_decompile_tiles(args)
        captured = capsys.readouterr()
        assert '# Tile 0x00' in captured.out


# =============================================================================
# Coverage tests: render_hgr_sprite short row padding (line 191)
# =============================================================================

class TestRenderHgrSpritePadding:
    """Test render_hgr_sprite with truncated row data."""

    def test_short_data_padded(self):
        """render_hgr_sprite pads short row data with zeros."""
        from ult3edit.shapes import render_hgr_sprite
        # Data shorter than expected: request 2 bytes/row x 2 rows
        # but only provide 3 bytes total (1 byte short on last row)
        data = bytes([0x7F, 0x7F, 0x01])
        pixels = render_hgr_sprite(data, width_bytes=2, height=2, offset=0)
        # Should have 2 rows x (2*7) = 28 pixels total
        assert len(pixels) == 28


# =============================================================================
# Coverage tests: parse_tiles_text error paths (lines 883-917)
# =============================================================================

class TestParseTilesTextErrors:
    """Test parse_tiles_text error paths."""

    def test_incomplete_tile_raises(self):
        """Tile with fewer than 8 rows raises ValueError."""
        from ult3edit.shapes import parse_tiles_text
        text = '# Tile 0x00: Test\n'
        text += '#######\n' * 5  # Only 5 rows, need 8
        with pytest.raises(ValueError, match='expected 8 rows, got 5'):
            parse_tiles_text(text)

    def test_incomplete_tile_at_eof_raises(self):
        """Tile with fewer than 8 rows at end of file raises ValueError."""
        from ult3edit.shapes import parse_tiles_text
        text = '# Tile 0x00: Complete\n'
        text += '#######\n' * 8
        text += '\n'
        text += '# Tile 0x01: Incomplete\n'
        text += '#######\n' * 3
        with pytest.raises(ValueError, match='expected 8 rows, got 3'):
            parse_tiles_text(text)


# =============================================================================
# Coverage tests: dispatch() and main() entry points
# =============================================================================

class TestShapesDispatch:
    """Tests for shapes dispatch() and main() entry points."""

    def test_dispatch_view(self, tmp_path, capsys):
        """dispatch() routes 'view' to cmd_view."""
        from ult3edit.shapes import dispatch
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            shapes_command='view', path=path,
            json=False, output=None, tile=0)
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Tile' in captured.out

    def test_dispatch_export(self, tmp_path, capsys):
        """dispatch() routes 'export' to cmd_export."""
        from ult3edit.shapes import dispatch
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        out_dir = str(tmp_path / 'out')
        args = argparse.Namespace(
            shapes_command='export', file=path,
            output_dir=out_dir, scale=1, sheet=False)
        dispatch(args)
        assert os.path.exists(os.path.join(out_dir, 'glyph_000.png'))

    def test_dispatch_edit(self, tmp_path, capsys):
        """dispatch() routes 'edit' to cmd_edit."""
        from ult3edit.shapes import dispatch
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            shapes_command='edit', file=path, glyph=0,
            data='FF FF FF FF FF FF FF FF',
            output=None, backup=False, dry_run=True)
        dispatch(args)

    def test_dispatch_import(self, tmp_path, capsys):
        """dispatch() routes 'import' to cmd_import."""
        from ult3edit.shapes import dispatch
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        jdata = [{'index': 0, 'raw': [0xFF] * 8}]
        jpath = str(tmp_path / 'g.json')
        with open(jpath, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            shapes_command='import', file=path, json_file=jpath,
            output=None, backup=False, dry_run=True)
        dispatch(args)

    def test_dispatch_info(self, tmp_path, capsys):
        """dispatch() routes 'info' to cmd_info."""
        from ult3edit.shapes import dispatch
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            shapes_command='info', file=path,
            json=False, output=None)
        dispatch(args)

    def test_dispatch_edit_string(self, tmp_path, capsys):
        """dispatch() routes 'edit-string' to cmd_edit_string."""
        from ult3edit.shapes import dispatch
        data = bytearray(b'\x60' * 16)
        data += bytes([0x20, 0xBA, 0x46])
        for ch in 'HELLO':
            data.append(ord(ch) | 0x80)
        data.append(0x00)
        data += bytearray(b'\x60' * 16)
        path = str(tmp_path / 'SHP0')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            shapes_command='edit-string', file=path,
            offset=19, text='HI',
            output=None, backup=False, dry_run=True)
        dispatch(args)

    def test_dispatch_compile(self, tmp_path, capsys):
        """dispatch() routes 'compile' to cmd_compile_tiles."""
        from ult3edit.shapes import dispatch
        lines = ['# Tile 0x00']
        for _ in range(8):
            lines.append('#######')
        lines.append('')
        src = str(tmp_path / 'test.tiles')
        with open(src, 'w') as f:
            f.write('\n'.join(lines))
        args = argparse.Namespace(
            shapes_command='compile', source=src,
            output=None, format='binary')
        dispatch(args)

    def test_dispatch_decompile(self, tmp_path, capsys):
        """dispatch() routes 'decompile' to cmd_decompile_tiles."""
        from ult3edit.shapes import dispatch
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            shapes_command='decompile', file=path, output=None)
        dispatch(args)

    def test_dispatch_unknown_command(self, capsys):
        """dispatch() with unknown command prints usage."""
        from ult3edit.shapes import dispatch
        args = argparse.Namespace(shapes_command=None)
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err

    def test_main_no_args(self):
        """main() with no args dispatches (prints usage or exits)."""
        from ult3edit.shapes import main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ['ult3-shapes']
            # No subcommand -> dispatches with None, prints usage
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv

    def test_main_view_subcommand(self, tmp_path, capsys):
        """main() with 'view' subcommand works."""
        from ult3edit.shapes import main
        import sys
        data = bytearray(SHPS_FILE_SIZE)
        path = str(tmp_path / 'SHPS')
        with open(path, 'wb') as f:
            f.write(data)
        old_argv = sys.argv
        try:
            sys.argv = ['ult3-shapes', 'view', path, '--tile', '0']
            main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
        captured = capsys.readouterr()
        assert 'Tile' in captured.out
