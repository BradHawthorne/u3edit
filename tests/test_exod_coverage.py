"""Additional coverage tests for EXOD intro/title screen editor module.

Covers uncovered lines: PNG filter types (Sub/Up/Average/Paeth), HGR
encoding edge cases, glyph pointer operations, cmd_* CLI functions,
dispatch routing, and main() standalone entry point.
"""

import argparse
import json
import os
import struct
import sys
import zlib

import pytest

from ult3edit.exod import (
    EXOD_SIZE,
    FRAMES,
    GLYPH_COLS,
    GLYPH_COUNT,
    GLYPH_DATA_SIZE,
    GLYPH_ROWS,
    GLYPH_TABLE_OFFSET,
    GLYPH_VARIANTS,
    HGR_PIXELS_PER_BYTE,
    build_text_crawl,
    cmd_crawl_compose,
    cmd_crawl_export,
    cmd_crawl_import,
    cmd_crawl_render,
    cmd_crawl_view,
    cmd_export,
    cmd_glyph_export,
    cmd_glyph_import,
    cmd_glyph_view,
    cmd_import,
    cmd_view,
    dispatch,
    encode_hgr_image,
    encode_hgr_row,
    extract_glyph_subpointers,
    extract_text_crawl,
    glyph_to_pixels,
    main,
    patch_text_crawl,
    pixels_to_frame_rows,
    read_png,
    _dispatch_crawl,
    _dispatch_glyph,
)


# ============================================================================
# Helpers
# ============================================================================

def _make_chunk(chunk_type, data):
    """Build a PNG chunk with CRC."""
    chunk = chunk_type + data
    crc = zlib.crc32(chunk) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)


def make_test_png(width, height, filter_byte=0, color=(128, 0, 0)):
    """Build a minimal valid RGB PNG file with a specific filter type."""
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = _make_chunk(b'IHDR', ihdr_data)
    raw = b''
    prev_row = b'\x00' * (width * 3)
    for y in range(height):
        row = bytes(color) * width
        if filter_byte == 0:
            raw += b'\x00' + row
        elif filter_byte == 1:  # Sub
            filtered = bytearray()
            for i in range(len(row)):
                a = row[i - 3] if i >= 3 else 0
                filtered.append((row[i] - a) & 0xFF)
            raw += b'\x01' + bytes(filtered)
        elif filter_byte == 2:  # Up
            filtered = bytearray()
            for i in range(len(row)):
                b_val = prev_row[i]
                filtered.append((row[i] - b_val) & 0xFF)
            raw += b'\x02' + bytes(filtered)
        elif filter_byte == 3:  # Average
            filtered = bytearray()
            for i in range(len(row)):
                a = row[i - 3] if i >= 3 else 0
                b_val = prev_row[i]
                filtered.append((row[i] - ((a + b_val) >> 1)) & 0xFF)
            raw += b'\x03' + bytes(filtered)
        elif filter_byte == 4:  # Paeth
            filtered = bytearray()
            for i in range(len(row)):
                a = row[i - 3] if i >= 3 else 0
                b_val = prev_row[i]
                c = prev_row[i - 3] if i >= 3 else 0
                p = a + b_val - c
                pa, pb, pc = abs(p - a), abs(p - b_val), abs(p - c)
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b_val
                else:
                    pr = c
                filtered.append((row[i] - pr) & 0xFF)
            raw += b'\x04' + bytes(filtered)
        prev_row = row
    idat = _make_chunk(b'IDAT', zlib.compress(raw))
    iend = _make_chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


def make_exod_with_crawl(coords):
    """Build an EXOD binary with text crawl data."""
    data = bytearray(EXOD_SIZE)
    crawl_bytes = build_text_crawl(coords)
    patch_text_crawl(data, crawl_bytes)
    return data


def make_exod_with_glyph_chain(glyph_idx=0, variant_idx=0):
    """Build an EXOD binary with a valid glyph pointer chain."""
    data = bytearray(EXOD_SIZE)
    # Main pointer table at $0400: glyph_idx -> sub-pointer table
    sub_table_addr = 0x0500 + glyph_idx * 0x100
    struct.pack_into('<H', data, GLYPH_TABLE_OFFSET + glyph_idx * 2,
                     sub_table_addr)
    # Sub-pointer table: all variants -> data blocks
    for v in range(GLYPH_VARIANTS):
        data_addr = sub_table_addr + GLYPH_VARIANTS * 2 + v * GLYPH_DATA_SIZE
        struct.pack_into('<H', data, sub_table_addr + v * 2, data_addr)
        # Write some pattern data
        for i in range(GLYPH_DATA_SIZE):
            if data_addr + i < len(data):
                data[data_addr + i] = (i * 7 + v) & 0xFF
    return data


def write_exod_file(tmp_path, data=None):
    """Write an EXOD binary to a temp file."""
    if data is None:
        data = bytearray(EXOD_SIZE)
    path = os.path.join(str(tmp_path), 'EXOD')
    with open(path, 'wb') as f:
        f.write(data)
    return path


# ============================================================================
# PNG filter types (lines 249-273)
# ============================================================================

class TestReadPngFilterTypes:
    """Test PNG read with different row filter types."""

    def test_filter_none(self, tmp_path):
        """Filter type 0 (None) — raw bytes, no reconstruction needed."""
        color = (200, 100, 50)
        png_data = make_test_png(4, 3, filter_byte=0, color=color)
        path = os.path.join(str(tmp_path), 'none.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        pixels, w, h = read_png(path)
        assert w == 4
        assert h == 3
        assert all(p == color for p in pixels)

    def test_filter_sub(self, tmp_path):
        """Filter type 1 (Sub) — reconstructs using left neighbor."""
        color = (200, 100, 50)
        png_data = make_test_png(4, 3, filter_byte=1, color=color)
        path = os.path.join(str(tmp_path), 'sub.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        pixels, w, h = read_png(path)
        assert w == 4
        assert h == 3
        assert all(p == color for p in pixels)

    def test_filter_up(self, tmp_path):
        """Filter type 2 (Up) — reconstructs using row above."""
        color = (100, 200, 150)
        png_data = make_test_png(4, 3, filter_byte=2, color=color)
        path = os.path.join(str(tmp_path), 'up.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        pixels, w, h = read_png(path)
        assert w == 4
        assert h == 3
        assert all(p == color for p in pixels)

    def test_filter_average(self, tmp_path):
        """Filter type 3 (Average) — reconstructs using left + above average."""
        color = (50, 150, 250)
        png_data = make_test_png(4, 3, filter_byte=3, color=color)
        path = os.path.join(str(tmp_path), 'average.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        pixels, w, h = read_png(path)
        assert w == 4
        assert h == 3
        assert all(p == color for p in pixels)

    def test_filter_paeth(self, tmp_path):
        """Filter type 4 (Paeth) — reconstructs using Paeth predictor."""
        color = (255, 128, 64)
        png_data = make_test_png(4, 3, filter_byte=4, color=color)
        path = os.path.join(str(tmp_path), 'paeth.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        pixels, w, h = read_png(path)
        assert w == 4
        assert h == 3
        assert all(p == color for p in pixels)

    def test_filter_sub_single_pixel_wide(self, tmp_path):
        """Sub filter with 1-pixel width (no left neighbor)."""
        color = (10, 20, 30)
        png_data = make_test_png(1, 2, filter_byte=1, color=color)
        path = os.path.join(str(tmp_path), 'sub_1px.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        pixels, w, h = read_png(path)
        assert w == 1
        assert h == 2
        assert all(p == color for p in pixels)

    def test_filter_paeth_multirow(self, tmp_path):
        """Paeth filter with multiple rows (tests c = prev_row[i-bpp])."""
        color = (33, 66, 99)
        png_data = make_test_png(5, 5, filter_byte=4, color=color)
        path = os.path.join(str(tmp_path), 'paeth_multi.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        pixels, w, h = read_png(path)
        assert w == 5
        assert h == 5
        assert all(p == color for p in pixels)

    def test_filter_average_first_row(self, tmp_path):
        """Average filter on first row (prev_row is all zeros)."""
        color = (200, 200, 200)
        png_data = make_test_png(3, 1, filter_byte=3, color=color)
        path = os.path.join(str(tmp_path), 'avg_first.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        pixels, w, h = read_png(path)
        assert w == 3
        assert h == 1
        assert all(p == color for p in pixels)


class TestReadPngErrors:
    """Test read_png error handling for unsupported formats."""

    def test_unsupported_bit_depth(self, tmp_path):
        """PNG with 16-bit depth raises ValueError."""
        sig = b'\x89PNG\r\n\x1a\n'
        # bit_depth=16, color_type=2
        ihdr_data = struct.pack('>IIBBBBB', 1, 1, 16, 2, 0, 0, 0)
        ihdr = _make_chunk(b'IHDR', ihdr_data)
        iend = _make_chunk(b'IEND', b'')
        png_data = sig + ihdr + iend
        path = os.path.join(str(tmp_path), 'bad_depth.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        with pytest.raises(ValueError, match="Unsupported bit depth"):
            read_png(path)

    def test_unsupported_color_type(self, tmp_path):
        """PNG with grayscale (color_type=0) raises ValueError."""
        sig = b'\x89PNG\r\n\x1a\n'
        # bit_depth=8, color_type=0 (grayscale)
        ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 0, 0, 0, 0)
        ihdr = _make_chunk(b'IHDR', ihdr_data)
        iend = _make_chunk(b'IEND', b'')
        png_data = sig + ihdr + iend
        path = os.path.join(str(tmp_path), 'bad_color.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        with pytest.raises(ValueError, match="Unsupported color type"):
            read_png(path)

    def test_rgba_png_strips_alpha(self, tmp_path):
        """RGBA PNG (color_type=6) is read with alpha discarded."""
        sig = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack('>IIBBBBB', 2, 2, 8, 6, 0, 0, 0)
        ihdr = _make_chunk(b'IHDR', ihdr_data)
        # 2x2 RGBA pixels: filter=0, then RGBA bytes
        raw = b''
        for y in range(2):
            raw += b'\x00'  # filter None
            for x in range(2):
                raw += bytes([100, 150, 200, 255])  # RGBA
        idat = _make_chunk(b'IDAT', zlib.compress(raw))
        iend = _make_chunk(b'IEND', b'')
        png_data = sig + ihdr + idat + iend
        path = os.path.join(str(tmp_path), 'rgba.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        pixels, w, h = read_png(path)
        assert w == 2 and h == 2
        assert all(p == (100, 150, 200) for p in pixels)


# ============================================================================
# HGR encoding edge cases (lines 365, 400, 558, 591)
# ============================================================================

class TestEncodeHgrRowEdgeCases:
    """Test encode_hgr_row with non-multiple-of-7 pixel counts."""

    def test_non_multiple_of_7_pixels(self):
        """Pixel count not multiple of 7 produces ceil(n/7) bytes (line 365)."""
        pixels = [(0, 0, 0)] * 10  # 10 pixels -> 2 bytes
        result = encode_hgr_row(pixels)
        assert len(result) == 2

    def test_one_pixel(self):
        """Single pixel produces 1 byte."""
        pixels = [(255, 255, 255)]
        result = encode_hgr_row(pixels)
        assert len(result) == 1
        # bit 0 should be set (white pixel)
        assert result[0] & 0x01 == 0x01

    def test_partial_last_byte_black(self):
        """Partial last byte with black pixels has no data bits (line 400 break)."""
        pixels = [(0, 0, 0)] * 8  # 8 pixels -> 2 bytes, second has 1 pixel
        result = encode_hgr_row(pixels)
        assert len(result) == 2
        assert result[1] & 0x7F == 0x00

    def test_partial_last_byte_white(self):
        """Partial last byte with white pixel has bit 0 set."""
        pixels = [(0, 0, 0)] * 7 + [(255, 255, 255)]  # 8 pixels
        result = encode_hgr_row(pixels)
        assert len(result) == 2
        assert result[1] & 0x01 == 0x01  # bit 0 of second byte


class TestEncodeHgrImageEdgeCases:
    """Test encode_hgr_image break at pix_idx >= width (line 558)."""

    def test_encode_image_width_not_multiple_of_7(self):
        """encode_hgr_image with a width that requires padding bytes.

        The width must actually be a multiple of 7 for encode_hgr_image
        (num_bytes = width // 7). But the inner loop hits break at line 558
        when encoding partial bytes in standard operation (pix_idx >= width).
        We test that it works correctly.
        """
        # width=7 is the minimal valid case
        width = 7
        height = 2
        pixels = [(128, 128, 128)] * (width * height)
        rows = encode_hgr_image(pixels, width, height)
        assert len(rows) == 2
        for row in rows:
            assert len(row) == 1


class TestPixelsToFrameRowsEdgeCases:
    """Test pixels_to_frame_rows padding (line 591)."""

    def test_narrow_image_padded(self):
        """Image narrower than expected width is padded with black."""
        # Frame expects col_bytes=4 -> 28 pixels wide
        # Provide a 14-pixel wide image (only half)
        col_bytes = 4
        height = 2
        narrow_width = 14
        pixels = [(255, 255, 255)] * (narrow_width * height)
        rows = pixels_to_frame_rows(pixels, narrow_width, height,
                                    col_bytes, col_offset=0)
        assert len(rows) == 2
        for row in rows:
            assert len(row) == col_bytes

    def test_exact_width_no_padding(self):
        """Image exactly matching expected width needs no padding."""
        col_bytes = 3
        height = 1
        width = col_bytes * HGR_PIXELS_PER_BYTE  # 21
        pixels = [(0, 0, 0)] * (width * height)
        rows = pixels_to_frame_rows(pixels, width, height,
                                    col_bytes, col_offset=0)
        assert len(rows) == 1
        assert len(rows[0]) == col_bytes


# ============================================================================
# Glyph pointer edge cases (lines 1060, 1098, 1174)
# ============================================================================

class TestGlyphSubpointerEdgeCases:
    """Test glyph sub-pointer edge cases for truncated data."""

    def test_subpointer_beyond_file_end(self):
        """Sub-pointer read beyond file end returns 0 (line 1060)."""
        # Create data just barely too short for the last sub-pointer
        data = bytearray(0x0500 + GLYPH_VARIANTS * 2 - 1)
        # Fill the pointer table so that the last entry is truncated
        for i in range(GLYPH_VARIANTS - 1):
            struct.pack_into('<H', data, 0x0500 + i * 2, 0x0600)
        subptrs = extract_glyph_subpointers(data, 0x0500)
        assert len(subptrs) == GLYPH_VARIANTS
        # Last entry should be 0 since there isn't enough data
        assert subptrs[GLYPH_VARIANTS - 1] == 0


class TestGlyphToPixelsEdgeCases:
    """Test glyph_to_pixels with short data (line 1098)."""

    def test_short_glyph_data_padded(self):
        """Glyph data shorter than GLYPH_COLS per row is zero-padded."""
        # Provide only 5 bytes (less than GLYPH_COLS=13)
        short_data = bytes([0x7F] * 5)
        pixels, width, height = glyph_to_pixels(short_data)
        assert width == GLYPH_COLS * HGR_PIXELS_PER_BYTE
        assert height == GLYPH_ROWS
        assert len(pixels) == width * height


class TestPatchGlyphDataBeyondEnd:
    """Test patch_glyph_data when data extends beyond file (line 1174)."""

    def test_data_extends_beyond_file_raises(self):
        """Glyph data at offset near file end raises ValueError."""
        # Create a small file where the pointer chain resolves to an offset
        # near the end so data extends beyond
        data = bytearray(0x0700)
        # Main pointer -> $0500
        struct.pack_into('<H', data, GLYPH_TABLE_OFFSET, 0x0500)
        # Sub-pointer -> $0600 (close to end of our 0x0700-byte file)
        # GLYPH_DATA_SIZE = 208 = 0xD0, so 0x0600 + 0xD0 = 0x06D0 > 0x0700? No.
        # 0x0600 + 208 = 0x06D0. File is 0x0700. Still fits.
        # Use 0x0650 instead: 0x0650 + 208 = 0x0720 > 0x0700
        struct.pack_into('<H', data, 0x0500, 0x0650)
        glyph_bytes = bytes(GLYPH_DATA_SIZE)
        with pytest.raises(ValueError, match="extends beyond file end"):
            from ult3edit.exod import patch_glyph_data
            patch_glyph_data(data, 0, 0, glyph_bytes)


# ============================================================================
# cmd_view (lines 1188-1241)
# ============================================================================

class TestCmdView:
    """Test cmd_view function."""

    def test_basic_view(self, tmp_path, capsys):
        """cmd_view prints frame structure info."""
        path = write_exod_file(tmp_path)
        args = argparse.Namespace(file=path, json=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'EXOD' in out
        assert 'title' in out
        assert 'serpent' in out
        assert 'Palette' in out

    def test_view_json(self, tmp_path, capsys):
        """cmd_view with --json prints JSON data."""
        path = write_exod_file(tmp_path)
        args = argparse.Namespace(file=path, json=True)
        cmd_view(args)
        out = capsys.readouterr().out
        assert '"frames"' in out
        # Verify JSON contains frame data
        assert '"title"' in out

    def test_view_file_not_found(self, tmp_path):
        """cmd_view exits 1 for missing file."""
        args = argparse.Namespace(
            file=os.path.join(str(tmp_path), 'NONEXISTENT'), json=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_view(args)
        assert exc_info.value.code == 1


# ============================================================================
# cmd_export (lines 1246-1296)
# ============================================================================

class TestCmdExport:
    """Test cmd_export function."""

    def test_export_all_frames(self, tmp_path, capsys):
        """Export all frames (no --frame)."""
        path = write_exod_file(tmp_path)
        out_dir = os.path.join(str(tmp_path), 'export')
        args = argparse.Namespace(file=path, output=out_dir,
                                  frame=None, scale=1)
        cmd_export(args)
        out = capsys.readouterr().out
        assert 'Exported title' in out
        assert 'Exported canvas' in out
        # Check files exist
        assert os.path.isfile(os.path.join(out_dir, 'title.png'))
        assert os.path.isfile(os.path.join(out_dir, 'canvas.png'))

    def test_export_single_frame(self, tmp_path, capsys):
        """Export a single named frame."""
        path = write_exod_file(tmp_path)
        out_dir = os.path.join(str(tmp_path), 'export_single')
        args = argparse.Namespace(file=path, output=out_dir,
                                  frame='title', scale=1)
        cmd_export(args)
        out = capsys.readouterr().out
        assert 'Exported title' in out
        assert os.path.isfile(os.path.join(out_dir, 'title.png'))

    def test_export_canvas_only(self, tmp_path, capsys):
        """Export canvas only (--frame canvas)."""
        path = write_exod_file(tmp_path)
        out_dir = os.path.join(str(tmp_path), 'export_canvas')
        args = argparse.Namespace(file=path, output=out_dir,
                                  frame='canvas', scale=1)
        cmd_export(args)
        out = capsys.readouterr().out
        assert 'Exported canvas' in out
        assert 'Exported title' not in out

    def test_export_scaled(self, tmp_path, capsys):
        """Export with scale > 1."""
        path = write_exod_file(tmp_path)
        out_dir = os.path.join(str(tmp_path), 'export_scaled')
        args = argparse.Namespace(file=path, output=out_dir,
                                  frame='title', scale=2)
        cmd_export(args)
        assert os.path.isfile(os.path.join(out_dir, 'title.png'))

    def test_export_unknown_frame(self, tmp_path):
        """Export unknown frame name exits 1."""
        path = write_exod_file(tmp_path)
        args = argparse.Namespace(file=path, output=str(tmp_path),
                                  frame='nonexistent', scale=1)
        with pytest.raises(SystemExit) as exc_info:
            cmd_export(args)
        assert exc_info.value.code == 1

    def test_export_file_not_found(self, tmp_path):
        """Export missing file exits 1."""
        args = argparse.Namespace(
            file=os.path.join(str(tmp_path), 'MISSING'), output='.',
            frame=None, scale=1)
        with pytest.raises(SystemExit) as exc_info:
            cmd_export(args)
        assert exc_info.value.code == 1


# ============================================================================
# cmd_import (lines 1301-1375)
# ============================================================================

class TestCmdImport:
    """Test cmd_import function."""

    def test_import_frame_dry_run(self, tmp_path, capsys):
        """Import a PNG frame in dry-run mode."""
        exod_path = write_exod_file(tmp_path)
        _, num_rows, col_bytes, col_offset, _ = FRAMES['exodus']
        width = col_bytes * HGR_PIXELS_PER_BYTE
        height = num_rows
        # Make a valid PNG of the right dimensions
        png_data = make_test_png(width, height, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'exodus.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  frame='exodus', dither=False,
                                  dry_run=True, backup=False)
        cmd_import(args)
        out = capsys.readouterr().out
        assert 'Imported exodus' in out
        assert 'dry run' in out

    def test_import_frame_write(self, tmp_path, capsys):
        """Import a PNG frame with actual write."""
        exod_path = write_exod_file(tmp_path)
        _, num_rows, col_bytes, col_offset, _ = FRAMES['serpent']
        width = col_bytes * HGR_PIXELS_PER_BYTE
        height = num_rows
        png_data = make_test_png(width, height, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'serpent.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  frame='serpent', dither=False,
                                  dry_run=False, backup=False)
        cmd_import(args)
        out = capsys.readouterr().out
        assert 'Imported serpent' in out
        assert 'Written' in out

    def test_import_canvas(self, tmp_path, capsys):
        """Import full canvas PNG."""
        exod_path = write_exod_file(tmp_path)
        png_data = make_test_png(280, 192, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'canvas.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  frame='canvas', dither=False,
                                  dry_run=True, backup=False)
        cmd_import(args)
        out = capsys.readouterr().out
        assert 'Imported canvas' in out

    def test_import_canvas_dithered(self, tmp_path, capsys):
        """Import canvas with dithering enabled."""
        exod_path = write_exod_file(tmp_path)
        png_data = make_test_png(280, 192, filter_byte=0, color=(128, 128, 128))
        png_path = os.path.join(str(tmp_path), 'canvas_dither.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  frame='canvas', dither=True,
                                  dry_run=True, backup=False)
        cmd_import(args)
        out = capsys.readouterr().out
        assert 'dithered' in out

    def test_import_canvas_wrong_size(self, tmp_path):
        """Import canvas with wrong dimensions exits 1."""
        exod_path = write_exod_file(tmp_path)
        png_data = make_test_png(100, 100, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'small.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  frame='canvas', dither=False,
                                  dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_import(args)
        assert exc_info.value.code == 1

    def test_import_frame_wrong_size(self, tmp_path):
        """Import frame with wrong dimensions exits 1."""
        exod_path = write_exod_file(tmp_path)
        png_data = make_test_png(10, 10, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'wrong.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  frame='title', dither=False,
                                  dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_import(args)
        assert exc_info.value.code == 1

    def test_import_unknown_frame(self, tmp_path):
        """Import with unknown frame name exits 1."""
        exod_path = write_exod_file(tmp_path)
        png_path = os.path.join(str(tmp_path), 'dummy.png')
        with open(png_path, 'wb') as f:
            f.write(make_test_png(1, 1))
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  frame='badname', dither=False,
                                  dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_import(args)
        assert exc_info.value.code == 1

    def test_import_exod_not_found(self, tmp_path):
        """Import with missing EXOD file exits 1."""
        png_path = os.path.join(str(tmp_path), 'dummy.png')
        with open(png_path, 'wb') as f:
            f.write(make_test_png(1, 1))
        args = argparse.Namespace(
            file=os.path.join(str(tmp_path), 'MISSING'),
            png=png_path, frame='title', dither=False,
            dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_import(args)
        assert exc_info.value.code == 1

    def test_import_png_not_found(self, tmp_path):
        """Import with missing PNG file exits 1."""
        exod_path = write_exod_file(tmp_path)
        args = argparse.Namespace(file=exod_path,
                                  png=os.path.join(str(tmp_path), 'MISSING.png'),
                                  frame='title', dither=False,
                                  dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_import(args)
        assert exc_info.value.code == 1

    def test_import_with_backup(self, tmp_path, capsys):
        """Import with --backup creates .bak file."""
        exod_path = write_exod_file(tmp_path)
        _, num_rows, col_bytes, col_offset, _ = FRAMES['exodus']
        width = col_bytes * HGR_PIXELS_PER_BYTE
        height = num_rows
        png_data = make_test_png(width, height, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'exodus.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  frame='exodus', dither=False,
                                  dry_run=False, backup=True)
        cmd_import(args)
        assert os.path.isfile(exod_path + '.bak')


# ============================================================================
# cmd_crawl_view (lines 1384-1411)
# ============================================================================

class TestCmdCrawlView:
    """Test cmd_crawl_view function."""

    def test_basic_view(self, tmp_path, capsys):
        """Crawl view displays coordinate table."""
        data = make_exod_with_crawl([(50, 100), (60, 110)])
        path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(file=path, json=False)
        cmd_crawl_view(args)
        out = capsys.readouterr().out
        assert 'Text Crawl' in out
        assert 'Points: 2' in out

    def test_view_json(self, tmp_path, capsys):
        """Crawl view with --json outputs JSON."""
        data = make_exod_with_crawl([(50, 100)])
        path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(file=path, json=True)
        cmd_crawl_view(args)
        out = capsys.readouterr().out
        assert '"points"' in out
        # Parse the JSON portion
        json_start = out.index('{')
        parsed = json.loads(out[json_start:])
        assert parsed['points'] == [[50, 100]]

    def test_view_file_not_found(self, tmp_path):
        """Crawl view exits 1 for missing file."""
        args = argparse.Namespace(
            file=os.path.join(str(tmp_path), 'MISSING'), json=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_crawl_view(args)
        assert exc_info.value.code == 1


# ============================================================================
# cmd_crawl_export (lines 1417-1441)
# ============================================================================

class TestCmdCrawlExport:
    """Test cmd_crawl_export function."""

    def test_export_to_file(self, tmp_path, capsys):
        """Export crawl to JSON file."""
        data = make_exod_with_crawl([(50, 100), (60, 110)])
        exod_path = write_exod_file(tmp_path, data)
        out_path = os.path.join(str(tmp_path), 'crawl.json')
        args = argparse.Namespace(file=exod_path, output=out_path)
        cmd_crawl_export(args)
        out = capsys.readouterr().out
        assert 'Exported 2 points' in out
        with open(out_path) as f:
            parsed = json.load(f)
        assert len(parsed['points']) == 2

    def test_export_to_stdout(self, tmp_path, capsys):
        """Export crawl to stdout when no output path."""
        data = make_exod_with_crawl([(50, 100)])
        exod_path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(file=exod_path, output=None)
        cmd_crawl_export(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed['points'] == [[50, 100]]

    def test_export_file_not_found(self, tmp_path):
        """Export exits 1 for missing file."""
        args = argparse.Namespace(
            file=os.path.join(str(tmp_path), 'MISSING'), output=None)
        with pytest.raises(SystemExit) as exc_info:
            cmd_crawl_export(args)
        assert exc_info.value.code == 1


# ============================================================================
# cmd_crawl_import (lines 1446-1480)
# ============================================================================

class TestCmdCrawlImport:
    """Test cmd_crawl_import function."""

    def test_import_dry_run(self, tmp_path, capsys):
        """Import crawl data in dry-run mode."""
        exod_path = write_exod_file(tmp_path)
        json_data = {
            'points': [[50, 100], [60, 110]]
        }
        json_path = os.path.join(str(tmp_path), 'crawl.json')
        with open(json_path, 'w') as f:
            json.dump(json_data, f)
        args = argparse.Namespace(file=exod_path, json_file=json_path,
                                  dry_run=True, backup=False)
        cmd_crawl_import(args)
        out = capsys.readouterr().out
        assert 'Importing 2 points' in out
        assert 'dry run' in out

    def test_import_write(self, tmp_path, capsys):
        """Import crawl data with actual write."""
        exod_path = write_exod_file(tmp_path)
        json_data = {
            'points': [[50, 100], [60, 110]]
        }
        json_path = os.path.join(str(tmp_path), 'crawl.json')
        with open(json_path, 'w') as f:
            json.dump(json_data, f)
        args = argparse.Namespace(file=exod_path, json_file=json_path,
                                  dry_run=False, backup=False)
        cmd_crawl_import(args)
        out = capsys.readouterr().out
        assert 'Written' in out
        # Verify the data was written
        with open(exod_path, 'rb') as f:
            data = f.read()
        coords = extract_text_crawl(data)
        assert coords == [(50, 100), (60, 110)]

    def test_import_with_backup(self, tmp_path, capsys):
        """Import with --backup creates .bak file."""
        exod_path = write_exod_file(tmp_path)
        json_data = {'points': [[50, 100]]}
        json_path = os.path.join(str(tmp_path), 'crawl.json')
        with open(json_path, 'w') as f:
            json.dump(json_data, f)
        args = argparse.Namespace(file=exod_path, json_file=json_path,
                                  dry_run=False, backup=True)
        cmd_crawl_import(args)
        assert os.path.isfile(exod_path + '.bak')

    def test_import_exod_not_found(self, tmp_path):
        """Import exits 1 for missing EXOD file."""
        json_path = os.path.join(str(tmp_path), 'crawl.json')
        with open(json_path, 'w') as f:
            json.dump({'points': []}, f)
        args = argparse.Namespace(
            file=os.path.join(str(tmp_path), 'MISSING'),
            json_file=json_path, dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_crawl_import(args)
        assert exc_info.value.code == 1

    def test_import_json_not_found(self, tmp_path):
        """Import exits 1 for missing JSON file."""
        exod_path = write_exod_file(tmp_path)
        args = argparse.Namespace(file=exod_path,
                                  json_file=os.path.join(str(tmp_path), 'MISSING.json'),
                                  dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_crawl_import(args)
        assert exc_info.value.code == 1


# ============================================================================
# cmd_crawl_render (lines 1485-1503)
# ============================================================================

class TestCmdCrawlRender:
    """Test cmd_crawl_render function."""

    def test_render_basic(self, tmp_path, capsys):
        """Render crawl coordinates as PNG."""
        data = make_exod_with_crawl([(50, 100), (60, 110)])
        exod_path = write_exod_file(tmp_path, data)
        out_path = os.path.join(str(tmp_path), 'crawl.png')
        args = argparse.Namespace(file=exod_path, output=out_path, scale=1)
        cmd_crawl_render(args)
        out = capsys.readouterr().out
        assert 'Rendered' in out
        assert os.path.isfile(out_path)

    def test_render_scaled(self, tmp_path, capsys):
        """Render with scale > 1."""
        data = make_exod_with_crawl([(50, 100)])
        exod_path = write_exod_file(tmp_path, data)
        out_path = os.path.join(str(tmp_path), 'crawl2x.png')
        args = argparse.Namespace(file=exod_path, output=out_path, scale=2)
        cmd_crawl_render(args)
        assert os.path.isfile(out_path)

    def test_render_default_output(self, tmp_path, capsys, monkeypatch):
        """Render with no output path uses default 'crawl.png'."""
        data = make_exod_with_crawl([(50, 100)])
        exod_path = write_exod_file(tmp_path, data)
        # Change to tmp_path so default output goes there
        monkeypatch.chdir(str(tmp_path))
        args = argparse.Namespace(file=exod_path, output=None, scale=1)
        cmd_crawl_render(args)
        assert os.path.isfile(os.path.join(str(tmp_path), 'crawl.png'))

    def test_render_file_not_found(self, tmp_path):
        """Render exits 1 for missing file."""
        args = argparse.Namespace(
            file=os.path.join(str(tmp_path), 'MISSING'),
            output='out.png', scale=1)
        with pytest.raises(SystemExit) as exc_info:
            cmd_crawl_render(args)
        assert exc_info.value.code == 1


# ============================================================================
# cmd_crawl_compose (lines 1509-1561)
# ============================================================================

class TestCmdCrawlCompose:
    """Test cmd_crawl_compose function."""

    def test_compose_to_stdout(self, tmp_path, capsys):
        """Compose text and print JSON to stdout."""
        args = argparse.Namespace(text='HI', x=None, y=None,
                                  spacing=1, output=None,
                                  render=None, scale=2)
        cmd_crawl_compose(args)
        out = capsys.readouterr().out
        assert '"points"' in out
        assert 'Text: "HI"' in out

    def test_compose_to_file(self, tmp_path, capsys):
        """Compose text and write JSON to file."""
        out_path = os.path.join(str(tmp_path), 'composed.json')
        args = argparse.Namespace(text='AB', x=100, y=100,
                                  spacing=1, output=out_path,
                                  render=None, scale=2)
        cmd_crawl_compose(args)
        out = capsys.readouterr().out
        assert 'Written' in out
        with open(out_path) as f:
            parsed = json.load(f)
        assert len(parsed['points']) > 0

    def test_compose_with_render(self, tmp_path, capsys):
        """Compose text with render preview."""
        out_json = os.path.join(str(tmp_path), 'composed.json')
        render_path = os.path.join(str(tmp_path), 'preview.png')
        args = argparse.Namespace(text='TEST', x=100, y=100,
                                  spacing=1, output=out_json,
                                  render=render_path, scale=1)
        cmd_crawl_compose(args)
        out = capsys.readouterr().out
        assert 'Rendered' in out
        assert os.path.isfile(render_path)

    def test_compose_empty_text(self, tmp_path, capsys):
        """Compose empty text produces warning."""
        args = argparse.Namespace(text='', x=100, y=100,
                                  spacing=1, output=None,
                                  render=None, scale=2)
        cmd_crawl_compose(args)
        err = capsys.readouterr().err
        assert 'Warning' in err or 'empty' in err.lower()

    def test_compose_with_explicit_xy(self, tmp_path, capsys):
        """Compose with explicit X and Y origins."""
        args = argparse.Namespace(text='A', x=50, y=140,
                                  spacing=2, output=None,
                                  render=None, scale=2)
        cmd_crawl_compose(args)
        out = capsys.readouterr().out
        assert 'Bounding box' in out

    def test_compose_render_scaled(self, tmp_path, capsys):
        """Compose with render at scale > 1."""
        render_path = os.path.join(str(tmp_path), 'scaled.png')
        args = argparse.Namespace(text='X', x=100, y=100,
                                  spacing=1, output=None,
                                  render=render_path, scale=3)
        cmd_crawl_compose(args)
        assert os.path.isfile(render_path)


# ============================================================================
# cmd_glyph_view (lines 1570-1640)
# ============================================================================

class TestCmdGlyphView:
    """Test cmd_glyph_view function."""

    def test_basic_view(self, tmp_path, capsys):
        """Glyph view displays pointer table."""
        data = make_exod_with_glyph_chain(0, 0)
        path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(file=path, json=False)
        cmd_glyph_view(args)
        out = capsys.readouterr().out
        assert 'Glyph Table' in out
        assert 'Entries: 5' in out

    def test_view_json(self, tmp_path, capsys):
        """Glyph view with --json outputs JSON."""
        data = make_exod_with_glyph_chain(0, 0)
        path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(file=path, json=True)
        cmd_glyph_view(args)
        out = capsys.readouterr().out
        assert '"glyphs"' in out
        # Find and parse JSON
        json_start = out.rfind('{\n  "description"')
        if json_start < 0:
            json_start = out.rfind('{')
        parsed = json.loads(out[json_start:])
        assert 'glyphs' in parsed
        assert len(parsed['glyphs']) == GLYPH_COUNT

    def test_view_file_not_found(self, tmp_path):
        """Glyph view exits 1 for missing file."""
        args = argparse.Namespace(
            file=os.path.join(str(tmp_path), 'MISSING'), json=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_glyph_view(args)
        assert exc_info.value.code == 1

    def test_view_out_of_range_pointer(self, tmp_path, capsys):
        """Glyph view handles out-of-range pointers gracefully."""
        data = bytearray(EXOD_SIZE)
        # All pointers are 0x0000 (out of range)
        path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(file=path, json=False)
        cmd_glyph_view(args)
        out = capsys.readouterr().out
        assert 'out of range' in out


# ============================================================================
# cmd_glyph_export (lines 1649-1686)
# ============================================================================

class TestCmdGlyphExport:
    """Test cmd_glyph_export function."""

    def test_export_glyphs(self, tmp_path, capsys):
        """Export glyph data as PNG files."""
        data = make_exod_with_glyph_chain(0, 0)
        exod_path = write_exod_file(tmp_path, data)
        out_dir = os.path.join(str(tmp_path), 'glyphs')
        args = argparse.Namespace(file=exod_path, output=out_dir, scale=1)
        cmd_glyph_export(args)
        out = capsys.readouterr().out
        assert 'Exported glyph 0' in out
        # Check at least one file exists
        assert os.path.isfile(os.path.join(out_dir, 'glyph_0_v0.png'))

    def test_export_scaled(self, tmp_path, capsys):
        """Export with scale > 1."""
        data = make_exod_with_glyph_chain(0, 0)
        exod_path = write_exod_file(tmp_path, data)
        out_dir = os.path.join(str(tmp_path), 'glyphs_2x')
        args = argparse.Namespace(file=exod_path, output=out_dir, scale=2)
        cmd_glyph_export(args)
        assert os.path.isfile(os.path.join(out_dir, 'glyph_0_v0.png'))

    def test_export_file_not_found(self, tmp_path):
        """Export exits 1 for missing file."""
        args = argparse.Namespace(
            file=os.path.join(str(tmp_path), 'MISSING'),
            output='.', scale=1)
        with pytest.raises(SystemExit) as exc_info:
            cmd_glyph_export(args)
        assert exc_info.value.code == 1

    def test_export_out_of_range_pointer(self, tmp_path, capsys):
        """Export with out-of-range pointer skips that glyph."""
        data = bytearray(EXOD_SIZE)
        # All pointers are zero -> out of range
        exod_path = write_exod_file(tmp_path, data)
        out_dir = os.path.join(str(tmp_path), 'glyphs_bad')
        args = argparse.Namespace(file=exod_path, output=out_dir, scale=1)
        cmd_glyph_export(args)
        out = capsys.readouterr().out
        assert 'out of range' in out


# ============================================================================
# cmd_glyph_import (lines 1692-1737)
# ============================================================================

class TestCmdGlyphImport:
    """Test cmd_glyph_import function."""

    def test_import_dry_run(self, tmp_path, capsys):
        """Import glyph in dry-run mode."""
        data = make_exod_with_glyph_chain(0, 0)
        exod_path = write_exod_file(tmp_path, data)
        # Make a 91x16 PNG
        width = GLYPH_COLS * HGR_PIXELS_PER_BYTE  # 91
        height = GLYPH_ROWS  # 16
        png_data = make_test_png(width, height, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'glyph.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  glyph=0, variant=0, dither=False,
                                  dry_run=True, backup=False)
        cmd_glyph_import(args)
        out = capsys.readouterr().out
        assert 'Imported glyph 0 variant 0' in out
        assert 'dry run' in out

    def test_import_write(self, tmp_path, capsys):
        """Import glyph with actual write."""
        data = make_exod_with_glyph_chain(0, 0)
        exod_path = write_exod_file(tmp_path, data)
        width = GLYPH_COLS * HGR_PIXELS_PER_BYTE
        height = GLYPH_ROWS
        png_data = make_test_png(width, height, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'glyph.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  glyph=0, variant=0, dither=False,
                                  dry_run=False, backup=False)
        cmd_glyph_import(args)
        out = capsys.readouterr().out
        assert 'Written' in out

    def test_import_with_backup(self, tmp_path, capsys):
        """Import with --backup creates .bak file."""
        data = make_exod_with_glyph_chain(0, 0)
        exod_path = write_exod_file(tmp_path, data)
        width = GLYPH_COLS * HGR_PIXELS_PER_BYTE
        height = GLYPH_ROWS
        png_data = make_test_png(width, height, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'glyph.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  glyph=0, variant=0, dither=False,
                                  dry_run=False, backup=True)
        cmd_glyph_import(args)
        assert os.path.isfile(exod_path + '.bak')

    def test_import_wrong_png_size(self, tmp_path):
        """Import glyph with wrong PNG size exits 1."""
        data = make_exod_with_glyph_chain(0, 0)
        exod_path = write_exod_file(tmp_path, data)
        # Wrong dimensions
        png_data = make_test_png(10, 10, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'wrong.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  glyph=0, variant=0, dither=False,
                                  dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_glyph_import(args)
        assert exc_info.value.code == 1

    def test_import_bad_pointer_chain(self, tmp_path):
        """Import glyph with invalid pointer chain exits 1."""
        data = bytearray(EXOD_SIZE)
        # All pointers are zero -> patch_glyph_data will raise
        exod_path = write_exod_file(tmp_path, data)
        width = GLYPH_COLS * HGR_PIXELS_PER_BYTE
        height = GLYPH_ROWS
        png_data = make_test_png(width, height, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'glyph.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  glyph=0, variant=0, dither=False,
                                  dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_glyph_import(args)
        assert exc_info.value.code == 1

    def test_import_exod_not_found(self, tmp_path):
        """Import exits 1 for missing EXOD file."""
        png_path = os.path.join(str(tmp_path), 'g.png')
        with open(png_path, 'wb') as f:
            f.write(make_test_png(91, 16))
        args = argparse.Namespace(
            file=os.path.join(str(tmp_path), 'MISSING'),
            png=png_path, glyph=0, variant=0, dither=False,
            dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_glyph_import(args)
        assert exc_info.value.code == 1

    def test_import_png_not_found(self, tmp_path):
        """Import exits 1 for missing PNG file."""
        data = make_exod_with_glyph_chain(0, 0)
        exod_path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(file=exod_path,
                                  png=os.path.join(str(tmp_path), 'MISSING.png'),
                                  glyph=0, variant=0, dither=False,
                                  dry_run=False, backup=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_glyph_import(args)
        assert exc_info.value.code == 1

    def test_import_dithered(self, tmp_path, capsys):
        """Import glyph with dithering enabled."""
        data = make_exod_with_glyph_chain(0, 0)
        exod_path = write_exod_file(tmp_path, data)
        width = GLYPH_COLS * HGR_PIXELS_PER_BYTE
        height = GLYPH_ROWS
        png_data = make_test_png(width, height, filter_byte=0,
                                 color=(128, 128, 128))
        png_path = os.path.join(str(tmp_path), 'glyph_dither.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(file=exod_path, png=png_path,
                                  glyph=0, variant=0, dither=True,
                                  dry_run=True, backup=False)
        cmd_glyph_import(args)
        out = capsys.readouterr().out
        assert 'dithered' in out


# ============================================================================
# dispatch routing (lines 1865-1913)
# ============================================================================

class TestDispatch:
    """Test dispatch function routing."""

    def test_dispatch_view(self, tmp_path, capsys):
        """dispatch routes 'view' to cmd_view."""
        path = write_exod_file(tmp_path)
        args = argparse.Namespace(exod_cmd='view', file=path, json=False)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'EXOD' in out

    def test_dispatch_export(self, tmp_path, capsys):
        """dispatch routes 'export' to cmd_export."""
        path = write_exod_file(tmp_path)
        out_dir = os.path.join(str(tmp_path), 'dispatch_export')
        args = argparse.Namespace(exod_cmd='export', file=path,
                                  output=out_dir, frame='canvas', scale=1)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Exported canvas' in out

    def test_dispatch_crawl(self, tmp_path, capsys):
        """dispatch routes 'crawl' to _dispatch_crawl."""
        data = make_exod_with_crawl([(50, 100)])
        path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(exod_cmd='crawl', crawl_cmd='view',
                                  file=path, json=False)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Text Crawl' in out

    def test_dispatch_glyph(self, tmp_path, capsys):
        """dispatch routes 'glyph' to _dispatch_glyph."""
        data = make_exod_with_glyph_chain(0, 0)
        path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(exod_cmd='glyph', glyph_cmd='view',
                                  file=path, json=False)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Glyph Table' in out

    def test_dispatch_no_cmd(self):
        """dispatch with no exod_cmd exits 1."""
        args = argparse.Namespace(exod_cmd=None)
        with pytest.raises(SystemExit) as exc_info:
            dispatch(args)
        assert exc_info.value.code == 1

    def test_dispatch_unknown_cmd(self):
        """dispatch with unknown cmd exits 1."""
        args = argparse.Namespace(exod_cmd='bogus')
        with pytest.raises(SystemExit) as exc_info:
            dispatch(args)
        assert exc_info.value.code == 1


class TestDispatchCrawl:
    """Test _dispatch_crawl routing."""

    def test_crawl_no_cmd(self):
        """_dispatch_crawl with no crawl_cmd exits 1."""
        args = argparse.Namespace(crawl_cmd=None)
        with pytest.raises(SystemExit) as exc_info:
            _dispatch_crawl(args)
        assert exc_info.value.code == 1

    def test_crawl_view_route(self, tmp_path, capsys):
        """_dispatch_crawl routes 'view'."""
        data = make_exod_with_crawl([(50, 100)])
        path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(crawl_cmd='view', file=path, json=False)
        _dispatch_crawl(args)
        out = capsys.readouterr().out
        assert 'Text Crawl' in out

    def test_crawl_export_route(self, tmp_path, capsys):
        """_dispatch_crawl routes 'export'."""
        data = make_exod_with_crawl([(50, 100)])
        path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(crawl_cmd='export', file=path, output=None)
        _dispatch_crawl(args)
        out = capsys.readouterr().out
        assert '"points"' in out

    def test_crawl_import_route(self, tmp_path, capsys):
        """_dispatch_crawl routes 'import'."""
        exod_path = write_exod_file(tmp_path)
        json_data = {'points': [[50, 100]]}
        json_path = os.path.join(str(tmp_path), 'crawl.json')
        with open(json_path, 'w') as f:
            json.dump(json_data, f)
        args = argparse.Namespace(crawl_cmd='import', file=exod_path,
                                  json_file=json_path, dry_run=True,
                                  backup=False)
        _dispatch_crawl(args)
        out = capsys.readouterr().out
        assert 'dry run' in out

    def test_crawl_render_route(self, tmp_path, capsys):
        """_dispatch_crawl routes 'render'."""
        data = make_exod_with_crawl([(50, 100)])
        path = write_exod_file(tmp_path, data)
        out_path = os.path.join(str(tmp_path), 'render.png')
        args = argparse.Namespace(crawl_cmd='render', file=path,
                                  output=out_path, scale=1)
        _dispatch_crawl(args)
        assert os.path.isfile(out_path)

    def test_crawl_compose_route(self, tmp_path, capsys):
        """_dispatch_crawl routes 'compose'."""
        args = argparse.Namespace(crawl_cmd='compose', text='HI',
                                  x=None, y=None, spacing=1,
                                  output=None, render=None, scale=2)
        _dispatch_crawl(args)
        out = capsys.readouterr().out
        assert '"points"' in out


class TestDispatchGlyph:
    """Test _dispatch_glyph routing."""

    def test_glyph_no_cmd(self):
        """_dispatch_glyph with no glyph_cmd exits 1."""
        args = argparse.Namespace(glyph_cmd=None)
        with pytest.raises(SystemExit) as exc_info:
            _dispatch_glyph(args)
        assert exc_info.value.code == 1

    def test_glyph_view_route(self, tmp_path, capsys):
        """_dispatch_glyph routes 'view'."""
        data = make_exod_with_glyph_chain(0, 0)
        path = write_exod_file(tmp_path, data)
        args = argparse.Namespace(glyph_cmd='view', file=path, json=False)
        _dispatch_glyph(args)
        out = capsys.readouterr().out
        assert 'Glyph Table' in out

    def test_glyph_export_route(self, tmp_path, capsys):
        """_dispatch_glyph routes 'export'."""
        data = make_exod_with_glyph_chain(0, 0)
        path = write_exod_file(tmp_path, data)
        out_dir = os.path.join(str(tmp_path), 'glyph_export')
        args = argparse.Namespace(glyph_cmd='export', file=path,
                                  output=out_dir, scale=1)
        _dispatch_glyph(args)
        out = capsys.readouterr().out
        assert 'Exported glyph' in out

    def test_glyph_import_route(self, tmp_path, capsys):
        """_dispatch_glyph routes 'import'."""
        data = make_exod_with_glyph_chain(0, 0)
        exod_path = write_exod_file(tmp_path, data)
        width = GLYPH_COLS * HGR_PIXELS_PER_BYTE
        height = GLYPH_ROWS
        png_data = make_test_png(width, height, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'g.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        args = argparse.Namespace(glyph_cmd='import', file=exod_path,
                                  png=png_path, glyph=0, variant=0,
                                  dither=False, dry_run=True, backup=False)
        _dispatch_glyph(args)
        out = capsys.readouterr().out
        assert 'dry run' in out


# ============================================================================
# main() standalone entry point (lines 1918-1953)
# ============================================================================

class TestMain:
    """Test the main() standalone entry point."""

    def test_main_no_args_prints_help(self, monkeypatch):
        """main() with no args prints help and exits 0."""
        monkeypatch.setattr(sys, 'argv', ['ult3-exod'])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_main_view(self, tmp_path, monkeypatch, capsys):
        """main() with 'view' command works."""
        path = write_exod_file(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['ult3-exod', 'view', path])
        main()
        out = capsys.readouterr().out
        assert 'EXOD' in out

    def test_main_export(self, tmp_path, monkeypatch, capsys):
        """main() with 'export' command works."""
        path = write_exod_file(tmp_path)
        out_dir = os.path.join(str(tmp_path), 'main_export')
        monkeypatch.setattr(sys, 'argv', ['ult3-exod', 'export', path,
                                           '-o', out_dir, '--frame', 'canvas',
                                           '--scale', '1'])
        main()
        out = capsys.readouterr().out
        assert 'Exported canvas' in out

    def test_main_crawl_view(self, tmp_path, monkeypatch, capsys):
        """main() routes to crawl view subcommand."""
        data = make_exod_with_crawl([(50, 100)])
        path = write_exod_file(tmp_path, data)
        monkeypatch.setattr(sys, 'argv',
                            ['ult3-exod', 'crawl', 'view', path])
        main()
        out = capsys.readouterr().out
        assert 'Text Crawl' in out

    def test_main_glyph_view(self, tmp_path, monkeypatch, capsys):
        """main() routes to glyph view subcommand."""
        data = make_exod_with_glyph_chain(0, 0)
        path = write_exod_file(tmp_path, data)
        monkeypatch.setattr(sys, 'argv',
                            ['ult3-exod', 'glyph', 'view', path])
        main()
        out = capsys.readouterr().out
        assert 'Glyph Table' in out

    def test_main_import_dry_run(self, tmp_path, monkeypatch, capsys):
        """main() with 'import' and --dry-run works."""
        exod_path = write_exod_file(tmp_path)
        _, num_rows, col_bytes, _, _ = FRAMES['exodus']
        width = col_bytes * HGR_PIXELS_PER_BYTE
        height = num_rows
        png_data = make_test_png(width, height, filter_byte=0, color=(0, 0, 0))
        png_path = os.path.join(str(tmp_path), 'exodus.png')
        with open(png_path, 'wb') as f:
            f.write(png_data)
        monkeypatch.setattr(sys, 'argv',
                            ['ult3-exod', 'import', exod_path, png_path,
                             '--frame', 'exodus', '--dry-run'])
        main()
        out = capsys.readouterr().out
        assert 'dry run' in out

    def test_main_crawl_compose(self, tmp_path, monkeypatch, capsys):
        """main() crawl compose generates coordinates."""
        monkeypatch.setattr(sys, 'argv',
                            ['ult3-exod', 'crawl', 'compose', 'HELLO'])
        main()
        out = capsys.readouterr().out
        assert '"points"' in out
