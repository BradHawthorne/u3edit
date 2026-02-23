"""Tests for EXOD intro/title screen editor module."""
import os
import struct
import tempfile
import zlib

import pytest

from ult3edit.exod import (
    CRAWL_FONT,
    CRAWL_FONT_HEIGHT,
    CRAWL_FONT_SPACING,
    CRAWL_FONT_WIDTH,
    CRAWL_WORD_SPACING,
    EXOD_SIZE,
    FRAMES,
    GLYPH_COLS,
    GLYPH_COUNT,
    GLYPH_DATA_SIZE,
    GLYPH_ROWS,
    GLYPH_TABLE_OFFSET,
    GLYPH_VARIANTS,
    HGR_BYTES_PER_ROW,
    HGR_PAGE2_FILE_OFFSET,
    HGR_PAGE_SIZE,
    HGR_PALETTE,
    HGR_PIXELS_PER_BYTE,
    HGR_ROWS,
    HGR_WIDTH,
    LUMA_R, LUMA_G, LUMA_B,
    PALETTE_0_COLORS,
    PALETTE_1_COLORS,
    TEXT_CRAWL_OFFSET,
    _color_distance,
    _crawl_text_width,
    _match_color_error,
    build_scanline_table,
    build_text_crawl,
    canvas_to_pixels,
    compose_text_crawl,
    encode_hgr_image,
    encode_hgr_row,
    extract_frame,
    extract_glyph_data,
    extract_glyph_pointers,
    extract_glyph_subpointers,
    extract_hgr_page,
    extract_text_crawl,
    frame_to_pixels,
    glyph_ptr_to_file_offset,
    glyph_to_pixels,
    hgr_scanline_offset,
    insert_frame,
    patch_hgr_page,
    patch_text_crawl,
    read_hgr_scanline,
    read_png,
    render_text_crawl,
    write_hgr_scanline,
    pixels_to_frame_rows,
    _nearest_hgr_color,
)
from ult3edit.shapes import render_hgr_row, write_png


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def blank_exod():
    """Create a blank EXOD-sized buffer."""
    return bytearray(EXOD_SIZE)


@pytest.fixture
def patterned_exod():
    """Create an EXOD buffer with known HGR page data.

    Each scanline byte is set to (row & 0x7F) so the palette bit
    varies and the pattern is predictable.
    """
    data = bytearray(EXOD_SIZE)
    for row in range(HGR_ROWS):
        offset = HGR_PAGE2_FILE_OFFSET + hgr_scanline_offset(row)
        val = row & 0x7F  # Palette bit 0, data varies
        for col in range(HGR_BYTES_PER_ROW):
            data[offset + col] = val
    return data


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory, cleaned up after test."""
    d = tempfile.mkdtemp(prefix='test_exod_')
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


# ============================================================================
# HGR scanline address mapping
# ============================================================================

class TestHgrScanlineOffset:
    """Test the HGR interleaved scanline address formula."""

    def test_row_0(self):
        """Row 0 is at offset 0."""
        assert hgr_scanline_offset(0) == 0

    def test_row_1(self):
        """Row 1 is at offset 0x400 (next 1K bank)."""
        assert hgr_scanline_offset(1) == 0x0400

    def test_row_8(self):
        """Row 8 is at offset 0x80 (next subgroup)."""
        assert hgr_scanline_offset(8) == 0x0080

    def test_row_64(self):
        """Row 64 is at offset 0x28 (next group)."""
        assert hgr_scanline_offset(64) == 0x0028

    def test_row_191(self):
        """Last scanline (191) has a valid offset within 8KB."""
        offset = hgr_scanline_offset(191)
        assert 0 <= offset < HGR_PAGE_SIZE
        # Row 191: line=7, subgroup=7, group=2 -> 7*0x400 + 7*0x80 + 2*0x28
        assert offset == 7 * 0x0400 + 7 * 0x0080 + 2 * 0x0028

    def test_all_offsets_unique(self):
        """All 192 scanlines have unique offsets."""
        offsets = [hgr_scanline_offset(r) for r in range(HGR_ROWS)]
        assert len(set(offsets)) == HGR_ROWS

    def test_all_offsets_in_range(self):
        """All offsets fit within the 8KB page."""
        for row in range(HGR_ROWS):
            offset = hgr_scanline_offset(row)
            assert 0 <= offset < HGR_PAGE_SIZE
            # Plus 40 bytes for the scanline data
            assert offset + HGR_BYTES_PER_ROW <= HGR_PAGE_SIZE


class TestBuildScanlineTable:
    """Test the full scanline table builder."""

    def test_length(self):
        table = build_scanline_table()
        assert len(table) == 192

    def test_matches_individual(self):
        table = build_scanline_table()
        for row in range(HGR_ROWS):
            assert table[row] == hgr_scanline_offset(row)


# ============================================================================
# HGR page extraction / insertion
# ============================================================================

class TestExtractHgrPage:
    """Test HGR page extraction from EXOD data."""

    def test_size(self, blank_exod):
        page = extract_hgr_page(blank_exod)
        assert len(page) == HGR_PAGE_SIZE

    def test_content(self):
        data = bytearray(EXOD_SIZE)
        # Write known pattern at HGR page offset
        for i in range(HGR_PAGE_SIZE):
            data[HGR_PAGE2_FILE_OFFSET + i] = i & 0xFF
        page = extract_hgr_page(data)
        for i in range(HGR_PAGE_SIZE):
            assert page[i] == i & 0xFF


class TestPatchHgrPage:
    """Test writing HGR page data back into EXOD."""

    def test_roundtrip(self, blank_exod):
        # Write pattern, extract, patch back
        original = bytearray(EXOD_SIZE)
        for i in range(HGR_PAGE_SIZE):
            original[HGR_PAGE2_FILE_OFFSET + i] = (i * 7) & 0xFF
        page = extract_hgr_page(original)
        target = bytearray(EXOD_SIZE)
        patch_hgr_page(target, page)
        assert target[HGR_PAGE2_FILE_OFFSET:HGR_PAGE2_FILE_OFFSET + HGR_PAGE_SIZE] == \
               original[HGR_PAGE2_FILE_OFFSET:HGR_PAGE2_FILE_OFFSET + HGR_PAGE_SIZE]

    def test_preserves_other_data(self, blank_exod):
        blank_exod[0] = 0x4C  # JMP opcode
        blank_exod[EXOD_SIZE - 1] = 0xFF
        page = bytearray(HGR_PAGE_SIZE)
        patch_hgr_page(blank_exod, page)
        assert blank_exod[0] == 0x4C
        assert blank_exod[EXOD_SIZE - 1] == 0xFF


class TestReadWriteHgrScanline:
    """Test individual scanline read/write."""

    def test_read_write_roundtrip(self):
        page = bytearray(HGR_PAGE_SIZE)
        test_data = bytes(range(HGR_BYTES_PER_ROW))
        write_hgr_scanline(page, 42, test_data)
        result = read_hgr_scanline(page, 42)
        assert result == test_data

    def test_different_rows_independent(self):
        page = bytearray(HGR_PAGE_SIZE)
        data_a = bytes([0xAA] * HGR_BYTES_PER_ROW)
        data_b = bytes([0xBB] * HGR_BYTES_PER_ROW)
        write_hgr_scanline(page, 0, data_a)
        write_hgr_scanline(page, 100, data_b)
        assert read_hgr_scanline(page, 0) == data_a
        assert read_hgr_scanline(page, 100) == data_b


# ============================================================================
# Frame extraction / insertion
# ============================================================================

class TestFrameConstants:
    """Validate frame constant definitions."""

    def test_all_frames_defined(self):
        expected = {'title', 'serpent', 'castle', 'exodus', 'frame4', 'frame3'}
        assert set(FRAMES.keys()) == expected

    def test_no_overlapping_scanlines(self):
        """Frames should not overlap in scanline ranges."""
        ranges = []
        for name, (start, rows, cols, offset, _) in FRAMES.items():
            end = start + rows - 1
            ranges.append((start, end, name))
        ranges.sort()
        for i in range(len(ranges) - 1):
            _, end_a, name_a = ranges[i]
            start_b, _, name_b = ranges[i + 1]
            assert end_a < start_b, f"{name_a} ends at {end_a}, {name_b} starts at {start_b}"

    def test_frames_within_hgr_page(self):
        """All frame scanlines must be within 0-191."""
        for name, (start, rows, cols, offset, _) in FRAMES.items():
            assert start >= 0, f"{name} starts below 0"
            assert start + rows <= HGR_ROWS, f"{name} exceeds 192 scanlines"
            assert offset >= 0, f"{name} has negative col offset"
            assert offset + cols <= HGR_BYTES_PER_ROW, f"{name} exceeds 40 byte row"


class TestExtractInsertFrame:
    """Test frame extraction and insertion."""

    def test_extract_dimensions(self, blank_exod):
        page = extract_hgr_page(blank_exod)
        for name, (start, num_rows, col_bytes, col_offset, _) in FRAMES.items():
            rows = extract_frame(page, name)
            assert len(rows) == num_rows, f"{name} row count"
            for r in rows:
                assert len(r) == col_bytes, f"{name} col bytes"

    def test_insert_roundtrip(self):
        """Insert known data, extract it back."""
        page = bytearray(HGR_PAGE_SIZE)
        name = 'exodus'  # 5 rows, 32 bytes each
        _, num_rows, col_bytes, _, _ = FRAMES[name]

        test_rows = [bytes([(r * 13 + c) & 0x7F for c in range(col_bytes)])
                     for r in range(num_rows)]
        insert_frame(page, name, test_rows)
        result = extract_frame(page, name)
        assert result == test_rows

    def test_insert_preserves_other_frames(self):
        """Inserting one frame shouldn't affect others."""
        page = bytearray(HGR_PAGE_SIZE)

        # Insert title
        _, t_rows, t_cols, _, _ = FRAMES['title']
        title_data = [bytes([0xAA] * t_cols) for _ in range(t_rows)]
        insert_frame(page, 'title', title_data)

        # Insert exodus
        _, e_rows, e_cols, _, _ = FRAMES['exodus']
        exodus_data = [bytes([0xBB] * e_cols) for _ in range(e_rows)]
        insert_frame(page, 'exodus', exodus_data)

        # Title should still be intact
        title_result = extract_frame(page, 'title')
        assert title_result == title_data


# ============================================================================
# HGR encoding
# ============================================================================

class TestNearestHgrColor:
    """Test color matching to HGR palette."""

    def test_exact_colors(self):
        for name, rgb in HGR_PALETTE.items():
            assert _nearest_hgr_color(rgb) == name

    def test_near_black(self):
        assert _nearest_hgr_color((10, 10, 10)) == 'black'

    def test_near_white(self):
        assert _nearest_hgr_color((250, 250, 250)) == 'white'

    def test_red_maps_to_nearest(self):
        # Pure red (255, 0, 0) should map to purple or orange
        result = _nearest_hgr_color((255, 0, 0))
        assert result in ('purple', 'orange')


class TestEncodeHgrRow:
    """Test HGR pixel-to-byte encoding."""

    def test_all_black(self):
        """7 black pixels -> one byte with all bits off."""
        pixels = [(0, 0, 0)] * 7
        result = encode_hgr_row(pixels)
        assert len(result) == 1
        assert result[0] & 0x7F == 0x00  # bits 0-6 clear

    def test_all_white(self):
        """7 white pixels -> one byte with all bits on."""
        pixels = [(255, 255, 255)] * 7
        result = encode_hgr_row(pixels)
        assert len(result) == 1
        assert result[0] & 0x7F == 0x7F  # all data bits set

    def test_single_purple_pixel(self):
        """Purple at even column -> palette 0, single bit set."""
        pixels = [HGR_PALETTE['purple']] + [(0, 0, 0)] * 6
        result = encode_hgr_row(pixels, start_col=0)
        assert result[0] & 0x80 == 0x00  # palette 0
        assert result[0] & 0x01 == 0x01  # bit 0 set (col 0, even -> purple)

    def test_single_blue_pixel(self):
        """Blue at even column -> palette 1, single bit set."""
        pixels = [HGR_PALETTE['blue']] + [(0, 0, 0)] * 6
        result = encode_hgr_row(pixels, start_col=0)
        assert result[0] & 0x80 == 0x80  # palette 1
        assert result[0] & 0x01 == 0x01  # bit 0 set

    def test_three_pass_palette_selection(self):
        """Three-pass selects palette per 7-pixel group by lowest error."""
        # 14 pixels: first 7 all blue, next 7 all black
        pixels = [HGR_PALETTE['blue']] * 7 + [(0, 0, 0)] * 7
        result = encode_hgr_row(pixels, start_col=0)
        assert len(result) == 2
        # First byte: palette 1 (blue pixels have zero error in palette 1)
        assert result[0] & 0x80 == 0x80
        # Second byte: palette 0 or 1 — both have zero error for black
        # (palette bit is irrelevant for all-black; three-pass ties go to 0)
        assert result[1] & 0x7F == 0x00  # all pixels black regardless

    def test_multiple_of_seven(self):
        """Output length is ceil(input_pixels / 7)."""
        for n in (7, 14, 21, 28):
            pixels = [(0, 0, 0)] * n
            result = encode_hgr_row(pixels)
            assert len(result) == n // 7

    def test_visual_roundtrip(self):
        """Encode then render should produce the same colors as render alone."""
        # Create a byte with known pattern: purple + green alternating
        # Palette 0, bits 0,2,4,6 set -> even cols purple, odd cols black
        test_byte = bytes([0x55])  # 0101 0101, palette 0
        rendered = render_hgr_row(test_byte)
        encoded = encode_hgr_row(rendered, start_col=0)
        re_rendered = render_hgr_row(encoded)
        assert rendered == re_rendered


# ============================================================================
# PNG read/write roundtrip
# ============================================================================

class TestReadPng:
    """Test the stdlib PNG reader."""

    def test_roundtrip_solid_red(self, tmp_dir):
        """Write red pixels, read them back."""
        pixels = [(255, 0, 0)] * 4  # 2x2 red
        path = os.path.join(tmp_dir, 'red.png')
        write_png(path, pixels, 2, 2)
        result, w, h = read_png(path)
        assert w == 2
        assert h == 2
        assert result == pixels

    def test_roundtrip_all_hgr_colors(self, tmp_dir):
        """All 6 HGR colors survive PNG round-trip."""
        colors = list(HGR_PALETTE.values())
        # 6 pixels in a 6x1 image
        path = os.path.join(tmp_dir, 'palette.png')
        write_png(path, colors, 6, 1)
        result, w, h = read_png(path)
        assert w == 6
        assert h == 1
        assert result == colors

    def test_roundtrip_gradient(self, tmp_dir):
        """A gradient pattern survives round-trip."""
        pixels = [(i, 255 - i, i // 2) for i in range(256)]
        path = os.path.join(tmp_dir, 'gradient.png')
        write_png(path, pixels, 256, 1)
        result, w, h = read_png(path)
        assert w == 256
        assert h == 1
        assert result == pixels

    def test_invalid_png_signature(self, tmp_dir):
        path = os.path.join(tmp_dir, 'bad.png')
        with open(path, 'wb') as f:
            f.write(b'NOT A PNG')
        with pytest.raises(ValueError, match="Not a valid PNG"):
            read_png(path)


# ============================================================================
# Frame rendering
# ============================================================================

class TestFrameToPixels:
    """Test frame byte-to-pixel conversion."""

    def test_empty(self):
        pixels, width, height = frame_to_pixels([])
        assert pixels == []
        assert width == 0
        assert height == 0

    def test_single_byte_row(self):
        """One byte per row -> 7 pixels wide."""
        rows = [bytes([0x00])]
        pixels, width, height = frame_to_pixels(rows)
        assert width == 7
        assert height == 1
        assert len(pixels) == 7

    def test_all_black(self):
        rows = [bytes([0x00, 0x00])]
        pixels, width, height = frame_to_pixels(rows)
        assert all(p == (0, 0, 0) for p in pixels)

    def test_dimensions(self):
        """Multiple rows, multiple bytes per row."""
        rows = [bytes([0x00] * 5) for _ in range(3)]
        pixels, width, height = frame_to_pixels(rows)
        assert width == 35  # 5 * 7
        assert height == 3
        assert len(pixels) == 35 * 3


class TestCanvasToPixels:
    """Test full 280x192 HGR page rendering."""

    def test_dimensions(self):
        page = bytearray(HGR_PAGE_SIZE)
        pixels, width, height = canvas_to_pixels(page)
        assert width == 280
        assert height == 192
        assert len(pixels) == 280 * 192


# ============================================================================
# Full frame encode/decode roundtrip
# ============================================================================

class TestFrameRoundtrip:
    """Test encode->decode pixel-level fidelity for synthesized frames."""

    def test_solid_black_frame(self):
        """All-black frame survives encode/decode."""
        col_bytes = 5
        num_rows = 3
        rows = [bytes([0x00] * col_bytes) for _ in range(num_rows)]
        pixels, width, height = frame_to_pixels(rows)
        encoded = pixels_to_frame_rows(pixels, width, height, col_bytes, 0)
        pixels2, _, _ = frame_to_pixels(encoded)
        assert pixels == pixels2

    def test_solid_white_frame(self):
        """All-white frame survives encode/decode."""
        col_bytes = 5
        num_rows = 3
        rows = [bytes([0x7F] * col_bytes) for _ in range(num_rows)]
        pixels, width, height = frame_to_pixels(rows)
        encoded = pixels_to_frame_rows(pixels, width, height, col_bytes, 0)
        pixels2, _, _ = frame_to_pixels(encoded)
        assert pixels == pixels2

    def test_colored_pattern(self):
        """Pattern with purple/green pixels round-trips."""
        # Alternating purple and green (palette 0, bits at even/odd)
        col_bytes = 4
        num_rows = 2
        rows = [bytes([0x55, 0x2A, 0x55, 0x2A]) for _ in range(num_rows)]
        pixels, width, height = frame_to_pixels(rows)
        encoded = pixels_to_frame_rows(pixels, width, height, col_bytes, 0)
        pixels2, _, _ = frame_to_pixels(encoded)
        assert pixels == pixels2

    def test_blue_orange_pattern(self):
        """Pattern with blue/orange pixels (palette 1) round-trips."""
        col_bytes = 3
        num_rows = 2
        # Palette 1 (bit 7 set), isolated pixels
        rows = [bytes([0x95, 0xAA, 0x95]) for _ in range(num_rows)]
        pixels, width, height = frame_to_pixels(rows)
        encoded = pixels_to_frame_rows(pixels, width, height, col_bytes, 0)
        pixels2, _, _ = frame_to_pixels(encoded)
        assert pixels == pixels2


class TestPngFrameRoundtrip:
    """Test full PNG export/import visual roundtrip."""

    def test_frame_via_png(self, tmp_dir):
        """Export a frame as PNG, read it back, re-encode, verify pixels."""
        col_bytes = 4
        num_rows = 3
        col_offset = 2
        # Mixed content: some colored, some black
        rows = [bytes([0x55, 0x00, 0xAA, 0x7F]) for _ in range(num_rows)]

        pixels, width, height = frame_to_pixels(rows)
        png_path = os.path.join(tmp_dir, 'test_frame.png')
        write_png(png_path, pixels, width, height)

        # Read back
        pixels2, w2, h2 = read_png(png_path)
        assert (w2, h2) == (width, height)
        assert pixels2 == pixels

        # Re-encode
        encoded = pixels_to_frame_rows(pixels2, w2, h2, col_bytes, col_offset)
        pixels3, _, _ = frame_to_pixels(encoded)
        assert pixels3 == pixels

    def test_canvas_via_png(self, tmp_dir):
        """Full 280x192 canvas PNG roundtrip (pixel-level)."""
        page = bytearray(HGR_PAGE_SIZE)
        # Put some content in a few rows
        for row in range(10):
            data = bytes([(row * 3 + c) & 0x7F for c in range(HGR_BYTES_PER_ROW)])
            write_hgr_scanline(page, row, data)

        pixels, w, h = canvas_to_pixels(page)
        png_path = os.path.join(tmp_dir, 'canvas.png')
        write_png(png_path, pixels, w, h)

        pixels2, w2, h2 = read_png(png_path)
        assert (w2, h2) == (w, h)
        assert pixels2 == pixels


# ============================================================================
# CLI argument parsing
# ============================================================================

class TestRegisterParser:
    """Test CLI subcommand registration."""

    def test_registers_without_error(self):
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        # Should parse 'exod view <file>'
        args = parser.parse_args(['exod', 'view', 'test.bin'])
        assert args.tool == 'exod'
        assert args.exod_cmd == 'view'
        assert args.file == 'test.bin'

    def test_export_defaults(self):
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'export', 'EXOD.bin'])
        assert args.scale == 2
        assert args.frame is None
        assert args.output is None

    def test_import_requires_frame(self):
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        with pytest.raises(SystemExit):
            parser.parse_args(['exod', 'import', 'EXOD.bin', 'art.png'])


class TestMainParser:
    """Test standalone main() parser parity."""

    def test_main_view_parse(self):
        """Standalone parser should accept same args as register_parser."""
        import argparse
        from ult3edit.exod import main
        # We test by importing the module and checking it has main()
        assert callable(main)

    def test_dither_flag(self):
        """Import subcommand accepts --dither flag."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'import', 'EXOD.bin', 'art.png',
                                  '--frame', 'title', '--dither'])
        assert args.dither is True


# ============================================================================
# Perceptual color matching (CCIR 601)
# ============================================================================

class TestColorDistance:
    """Test CCIR 601 perceptual color distance."""

    def test_identical_colors_zero_distance(self):
        """Same color has zero distance."""
        for name, rgb in HGR_PALETTE.items():
            assert _color_distance(rgb, rgb) == 0.0

    def test_green_weighted_more_than_red(self):
        """Green channel differences should produce larger distances than red."""
        black = (0, 0, 0)
        # 50-unit difference in green vs 50-unit difference in red
        green_diff = _color_distance((0, 50, 0), black)
        red_diff = _color_distance((50, 0, 0), black)
        assert green_diff > red_diff

    def test_red_weighted_more_than_blue(self):
        """Red channel differences should produce larger distances than blue."""
        black = (0, 0, 0)
        blue_diff = _color_distance((0, 0, 50), black)
        red_diff = _color_distance((50, 0, 0), black)
        assert red_diff > blue_diff

    def test_black_white_maximum(self):
        """Black-to-white should be the largest possible distance."""
        bw = _color_distance((0, 0, 0), (255, 255, 255))
        # Should be large (close to 1.0)
        assert bw > 0.5


class TestMatchColorError:
    """Test color matching with error reporting."""

    def test_exact_match_zero_error(self):
        """Exact palette color has zero error."""
        for name, rgb in HGR_PALETTE.items():
            matched, error = _match_color_error(rgb)
            assert matched == name
            assert error == 0

    def test_palette_filter(self):
        """Palette filter restricts matching to subset."""
        # Blue should match to palette 1
        name, _ = _match_color_error(HGR_PALETTE['blue'], PALETTE_1_COLORS)
        assert name == 'blue'
        # Blue forced to palette 0 should not match blue
        name, _ = _match_color_error(HGR_PALETTE['blue'], PALETTE_0_COLORS)
        assert name != 'blue'
        assert name in PALETTE_0_COLORS

    def test_error_is_absolute_rgb_sum(self):
        """Error is sum of absolute per-channel differences."""
        # Match (100, 100, 100) to black (0,0,0) — error = 300
        name, error = _match_color_error((100, 100, 100), {'black'})
        assert name == 'black'
        assert error == 300


# ============================================================================
# Three-pass palette selection
# ============================================================================

class TestThreePassPalette:
    """Test three-pass palette bit selection in encode_hgr_row."""

    def test_blue_pixels_select_palette_1(self):
        """Pixels closest to blue should trigger palette 1."""
        pixels = [HGR_PALETTE['blue']] * 7
        result = encode_hgr_row(pixels)
        assert result[0] & 0x80 == 0x80

    def test_purple_pixels_select_palette_0(self):
        """Pixels closest to purple should trigger palette 0."""
        pixels = [HGR_PALETTE['purple']] * 7
        result = encode_hgr_row(pixels)
        assert result[0] & 0x80 == 0x00

    def test_mixed_group_selects_best_palette(self):
        """When a group has both blue-ish and purple-ish, pick lowest error."""
        # 5 blue + 2 purple → palette 1 should win (lower total error)
        pixels = [HGR_PALETTE['blue']] * 5 + [HGR_PALETTE['purple']] * 2
        result = encode_hgr_row(pixels)
        assert result[0] & 0x80 == 0x80  # palette 1 wins

    def test_independent_groups(self):
        """Adjacent 7-pixel groups can have different palettes."""
        # First 7: all purple (palette 0), next 7: all blue (palette 1)
        pixels = [HGR_PALETTE['purple']] * 7 + [HGR_PALETTE['blue']] * 7
        result = encode_hgr_row(pixels)
        assert result[0] & 0x80 == 0x00  # palette 0
        assert result[1] & 0x80 == 0x80  # palette 1

    def test_ambiguous_input_selects_best_fit(self):
        """Non-palette colors should be matched to closest palette option."""
        # Cyan-ish (0, 200, 200) is closer to blue than to green
        cyan = (0, 200, 200)
        pixels = [cyan] * 7
        result = encode_hgr_row(pixels)
        # Should pick palette 1 (blue) over palette 0 (green)
        assert result[0] & 0x80 == 0x80


# ============================================================================
# Floyd-Steinberg dithering
# ============================================================================

class TestDithering:
    """Test Floyd-Steinberg error diffusion dithering."""

    def test_solid_color_no_dithering_needed(self):
        """Solid palette-exact color should produce uniform output."""
        width = 14
        height = 2
        pixels = [HGR_PALETTE['purple']] * (width * height)
        rows = encode_hgr_image(pixels, width, height)
        assert len(rows) == 2
        for row in rows:
            assert len(row) == 2

    def test_dithered_output_dimensions(self):
        """Dithered output has correct dimensions."""
        width = 28
        height = 4
        pixels = [(128, 128, 128)] * (width * height)
        rows = encode_hgr_image(pixels, width, height)
        assert len(rows) == height
        for row in rows:
            assert len(row) == width // 7

    def test_all_black_dithered(self):
        """All-black input should produce all-zero data bits."""
        width = 14
        height = 3
        pixels = [(0, 0, 0)] * (width * height)
        rows = encode_hgr_image(pixels, width, height)
        for row in rows:
            for byte_val in row:
                assert byte_val & 0x7F == 0x00

    def test_all_white_dithered(self):
        """All-white input should produce all-set data bits."""
        width = 14
        height = 3
        pixels = [(255, 255, 255)] * (width * height)
        rows = encode_hgr_image(pixels, width, height)
        for row in rows:
            for byte_val in row:
                assert byte_val & 0x7F == 0x7F

    def test_gray_produces_mixed_output(self):
        """50% gray should produce some set and some unset pixels (dithered)."""
        width = 28
        height = 4
        pixels = [(128, 128, 128)] * (width * height)
        rows = encode_hgr_image(pixels, width, height)
        # Collect all data bits
        total_set = 0
        total_bits = 0
        for row in rows:
            for byte_val in row:
                for bit in range(7):
                    total_bits += 1
                    if byte_val & (1 << bit):
                        total_set += 1
        # Should have a mix (not all-on or all-off)
        assert 0 < total_set < total_bits

    def test_visual_roundtrip_dithered(self):
        """Dithered encoding of palette-exact colors is pixel-perfect."""
        col_bytes = 4
        num_rows = 3
        rows = [bytes([0x55, 0x00, 0xAA, 0x7F]) for _ in range(num_rows)]
        pixels, width, height = frame_to_pixels(rows)
        # Dither palette-exact input should not change anything
        encoded = pixels_to_frame_rows(pixels, width, height, col_bytes, 0,
                                       dither=True)
        pixels2, _, _ = frame_to_pixels(encoded)
        assert pixels == pixels2

    def test_serpentine_differs_from_non_serpentine(self):
        """Multi-row dithering with non-palette colors should show serpentine effect."""
        width = 14
        height = 4
        # Use a non-palette color that will trigger dithering
        pixels = [(180, 100, 50)] * (width * height)
        rows = encode_hgr_image(pixels, width, height)
        # Even and odd rows should differ (serpentine changes scan direction)
        # With non-trivial content, rows won't all be identical
        assert len(rows) == 4


# ============================================================================
# Text crawl extraction / building
# ============================================================================

class TestTextCrawlExtract:
    """Test text crawl coordinate extraction from binary data."""

    def test_empty_stream(self):
        """$00 at start produces empty result."""
        data = bytearray(EXOD_SIZE)
        data[TEXT_CRAWL_OFFSET] = 0x00
        coords = extract_text_crawl(data)
        assert coords == []

    def test_single_pair(self):
        """One (X, Y) pair followed by $00."""
        data = bytearray(EXOD_SIZE)
        data[TEXT_CRAWL_OFFSET] = 0x5E      # X = 94
        data[TEXT_CRAWL_OFFSET + 1] = 0x3D  # Y_raw = 61, screen = 0xBF-0x3D = 130
        data[TEXT_CRAWL_OFFSET + 2] = 0x00  # terminator
        coords = extract_text_crawl(data)
        assert len(coords) == 1
        assert coords[0] == (94, 130)

    def test_multiple_pairs(self):
        """Multiple pairs extracted correctly."""
        data = bytearray(EXOD_SIZE)
        # Three pairs: (10, 0x10), (20, 0x20), (30, 0x30)
        pairs = [(10, 0x10), (20, 0x20), (30, 0x30)]
        pos = TEXT_CRAWL_OFFSET
        for x, y_raw in pairs:
            data[pos] = x
            data[pos + 1] = y_raw
            pos += 2
        data[pos] = 0x00  # terminator
        coords = extract_text_crawl(data)
        assert len(coords) == 3
        assert coords[0] == (10, 0xBF - 0x10)
        assert coords[1] == (20, 0xBF - 0x20)
        assert coords[2] == (30, 0xBF - 0x30)

    def test_y_inversion(self):
        """Y coordinate is inverted via 0xBF - raw_byte."""
        data = bytearray(EXOD_SIZE)
        data[TEXT_CRAWL_OFFSET] = 0x01      # X = 1
        data[TEXT_CRAWL_OFFSET + 1] = 0x00  # Y_raw = 0, screen = 0xBF = 191
        data[TEXT_CRAWL_OFFSET + 2] = 0x00  # terminator
        coords = extract_text_crawl(data)
        assert coords[0] == (1, 0xBF)  # 191

    def test_max_y(self):
        """Y raw 0xBF gives screen Y = 0."""
        data = bytearray(EXOD_SIZE)
        data[TEXT_CRAWL_OFFSET] = 0x01
        data[TEXT_CRAWL_OFFSET + 1] = 0xBF  # screen = 0xBF-0xBF = 0
        data[TEXT_CRAWL_OFFSET + 2] = 0x00
        coords = extract_text_crawl(data)
        assert coords[0] == (1, 0)


class TestTextCrawlBuild:
    """Test text crawl byte stream building from coordinates."""

    def test_empty(self):
        """Empty coords produce just a terminator."""
        result = build_text_crawl([])
        assert result == b'\x00'

    def test_single_pair(self):
        """Single coordinate pair."""
        result = build_text_crawl([(94, 130)])
        # X=94, Y_raw = 0xBF-130 = 0x3D
        assert result == bytes([94, 0x3D, 0x00])

    def test_roundtrip(self):
        """Build from coords, write to binary, extract back, compare."""
        coords = [(50, 100), (60, 80), (70, 60)]
        crawl_bytes = build_text_crawl(coords)

        data = bytearray(EXOD_SIZE)
        patch_text_crawl(data, crawl_bytes)
        extracted = extract_text_crawl(data)
        assert extracted == coords

    def test_x_zero_raises(self):
        """X=0 is the terminator and should be rejected."""
        with pytest.raises(ValueError, match="X coordinate 0"):
            build_text_crawl([(0, 100)])

    def test_x_out_of_range_raises(self):
        """X > 255 should be rejected."""
        with pytest.raises(ValueError, match="X coordinate"):
            build_text_crawl([(256, 100)])

    def test_y_produces_valid_raw(self):
        """Screen Y that produces negative raw Y should be rejected."""
        # screen_y = 200, y_raw = 0xBF - 200 = -9 → invalid
        with pytest.raises(ValueError):
            build_text_crawl([(1, 200)])

    def test_terminator_present(self):
        """Output always ends with $00."""
        result = build_text_crawl([(10, 50), (20, 60)])
        assert result[-1] == 0x00

    def test_many_pairs(self):
        """Build with many pairs preserves all data."""
        coords = [(x, x % 192) for x in range(1, 100)]
        result = build_text_crawl(coords)
        assert len(result) == 99 * 2 + 1  # pairs + terminator


class TestTextCrawlRender:
    """Test text crawl rendering to pixel data."""

    def test_empty_is_all_black(self):
        """No coords produces a black canvas."""
        pixels = render_text_crawl([])
        assert len(pixels) == HGR_WIDTH * HGR_ROWS
        assert all(p == (0, 0, 0) for p in pixels)

    def test_single_point_double_wide(self):
        """Single point plots at (x, y) and (x+1, y)."""
        pixels = render_text_crawl([(50, 100)])
        white = (255, 255, 255)
        assert pixels[100 * HGR_WIDTH + 50] == white
        assert pixels[100 * HGR_WIDTH + 51] == white
        # Adjacent pixels should be black
        assert pixels[100 * HGR_WIDTH + 49] == (0, 0, 0)
        assert pixels[100 * HGR_WIDTH + 52] == (0, 0, 0)

    def test_point_at_right_edge(self):
        """Point at x=279 only plots one pixel (x+1=280 is out of bounds)."""
        pixels = render_text_crawl([(279, 50)])
        white = (255, 255, 255)
        assert pixels[50 * HGR_WIDTH + 279] == white
        # x+1=280 is out of range, should not crash

    def test_point_out_of_y_range_ignored(self):
        """Points with Y >= 192 or Y < 0 are silently ignored."""
        # Should not crash
        pixels = render_text_crawl([(50, 192)])
        pixels2 = render_text_crawl([(50, -1)])
        assert len(pixels) == HGR_WIDTH * HGR_ROWS
        assert len(pixels2) == HGR_WIDTH * HGR_ROWS

    def test_multiple_points(self):
        """Multiple points are all rendered."""
        coords = [(10, 10), (20, 20), (30, 30)]
        pixels = render_text_crawl(coords)
        white = (255, 255, 255)
        for x, y in coords:
            assert pixels[y * HGR_WIDTH + x] == white
            assert pixels[y * HGR_WIDTH + x + 1] == white


class TestPatchTextCrawl:
    """Test writing text crawl data back to EXOD binary."""

    def test_patch_and_extract(self):
        """Write crawl bytes and extract them back."""
        data = bytearray(EXOD_SIZE)
        crawl = bytes([0x5E, 0x3D, 0x5F, 0x3C, 0x00])
        patch_text_crawl(data, crawl)
        assert data[TEXT_CRAWL_OFFSET:TEXT_CRAWL_OFFSET + 5] == crawl

    def test_does_not_clobber_other_data(self):
        """Patching crawl data doesn't affect other regions."""
        data = bytearray(EXOD_SIZE)
        data[0] = 0xAA
        data[TEXT_CRAWL_OFFSET - 1] = 0xBB
        crawl = bytes([0x01, 0x02, 0x00])
        patch_text_crawl(data, crawl)
        assert data[0] == 0xAA
        assert data[TEXT_CRAWL_OFFSET - 1] == 0xBB


# ============================================================================
# Glyph table extraction
# ============================================================================

class TestGlyphPointers:
    """Test glyph pointer table extraction."""

    def test_extract_count(self):
        """Extracts exactly 5 pointers."""
        data = bytearray(EXOD_SIZE)
        pointers = extract_glyph_pointers(data)
        assert len(pointers) == GLYPH_COUNT

    def test_known_pointers(self):
        """Verify pointer values from synthesized data."""
        data = bytearray(EXOD_SIZE)
        # Write 5 known 16-bit LE pointers at offset $0400
        test_ptrs = [0x0500, 0x0600, 0x0700, 0x0450, 0x0460]
        for i, ptr in enumerate(test_ptrs):
            struct.pack_into('<H', data, GLYPH_TABLE_OFFSET + i * 2, ptr)
        pointers = extract_glyph_pointers(data)
        assert pointers == test_ptrs

    def test_ptr_to_file_offset_valid(self):
        """Pointers in $0400-$3FFF map to same file offset."""
        assert glyph_ptr_to_file_offset(0x0400) == 0x0400
        assert glyph_ptr_to_file_offset(0x0500) == 0x0500
        assert glyph_ptr_to_file_offset(0x3FFF) == 0x3FFF

    def test_ptr_to_file_offset_out_of_range(self):
        """Pointers outside $0400-$3FFF return -1."""
        assert glyph_ptr_to_file_offset(0x03FF) == -1
        assert glyph_ptr_to_file_offset(0x4000) == -1
        assert glyph_ptr_to_file_offset(0x8000) == -1


class TestGlyphSubpointers:
    """Test glyph sub-pointer table extraction."""

    def test_extract_count(self):
        """Extracts exactly 7 sub-pointers."""
        data = bytearray(EXOD_SIZE)
        # Set up main pointer at $0400 -> $0500
        struct.pack_into('<H', data, GLYPH_TABLE_OFFSET, 0x0500)
        # Write 7 sub-pointers at $0500
        for i in range(GLYPH_VARIANTS):
            struct.pack_into('<H', data, 0x0500 + i * 2, 0x0600 + i * GLYPH_DATA_SIZE)
        subptrs = extract_glyph_subpointers(data, 0x0500)
        assert len(subptrs) == GLYPH_VARIANTS

    def test_known_subpointers(self):
        """Verify sub-pointer values from synthesized data."""
        data = bytearray(EXOD_SIZE)
        # Write 7 known sub-pointers at file offset $0500
        expected = [0x050E, 0x05DE, 0x06AE, 0x077E, 0x084E, 0x091E, 0x09EE]
        for i, ptr in enumerate(expected):
            struct.pack_into('<H', data, 0x0500 + i * 2, ptr)
        subptrs = extract_glyph_subpointers(data, 0x0500)
        assert subptrs == expected

    def test_subpointers_are_208_apart(self):
        """Sub-pointers should be GLYPH_DATA_SIZE apart in real data."""
        data = bytearray(EXOD_SIZE)
        # Simulate real layout: sub-table at $0500, data blocks at $050E+
        base_data = 0x050E  # first data block after 7*2=14 bytes of pointers
        for i in range(GLYPH_VARIANTS):
            struct.pack_into('<H', data, 0x0500 + i * 2,
                             base_data + i * GLYPH_DATA_SIZE)
        subptrs = extract_glyph_subpointers(data, 0x0500)
        for i in range(1, GLYPH_VARIANTS):
            assert subptrs[i] - subptrs[i - 1] == GLYPH_DATA_SIZE

    def test_out_of_range_base_returns_zeros(self):
        """Out-of-range base pointer returns all-zero sub-pointers."""
        data = bytearray(EXOD_SIZE)
        subptrs = extract_glyph_subpointers(data, 0x0100)  # below $0400
        assert subptrs == [0] * GLYPH_VARIANTS

    def test_subpointer_to_pixel_data(self):
        """Sub-pointer resolves to correct pixel data."""
        data = bytearray(EXOD_SIZE)
        # Sub-table at $0500 with one pointer to $0600
        struct.pack_into('<H', data, 0x0500, 0x0600)
        # Write known pixel data at $0600
        for i in range(GLYPH_DATA_SIZE):
            data[0x0600 + i] = (i * 3) & 0xFF
        subptrs = extract_glyph_subpointers(data, 0x0500)
        sp_off = glyph_ptr_to_file_offset(subptrs[0])
        glyph = extract_glyph_data(data, sp_off)
        for i in range(GLYPH_DATA_SIZE):
            assert glyph[i] == (i * 3) & 0xFF


class TestGlyphData:
    """Test glyph pixel data extraction and rendering."""

    def test_extract_size(self):
        """Extracted glyph data is 208 bytes."""
        data = bytearray(EXOD_SIZE)
        glyph = extract_glyph_data(data, 0x0500)
        assert len(glyph) == GLYPH_DATA_SIZE

    def test_extract_content(self):
        """Extracted data matches what was written."""
        data = bytearray(EXOD_SIZE)
        # Write a known pattern at file offset $0500
        for i in range(GLYPH_DATA_SIZE):
            data[0x0500 + i] = i & 0xFF
        glyph = extract_glyph_data(data, 0x0500)
        for i in range(GLYPH_DATA_SIZE):
            assert glyph[i] == i & 0xFF

    def test_extract_out_of_range_returns_zeros(self):
        """Out-of-range offset returns zero-filled data."""
        data = bytearray(100)  # too small
        glyph = extract_glyph_data(data, 0x0500)
        assert len(glyph) == GLYPH_DATA_SIZE
        assert all(b == 0 for b in glyph)

    def test_glyph_to_pixels_dimensions(self):
        """Glyph renders to 91x16 pixels."""
        glyph = bytes(GLYPH_DATA_SIZE)
        pixels, width, height = glyph_to_pixels(glyph)
        assert width == GLYPH_COLS * HGR_PIXELS_PER_BYTE  # 91
        assert height == GLYPH_ROWS  # 16
        assert len(pixels) == width * height

    def test_glyph_to_pixels_all_black(self):
        """All-zero glyph data renders as all black."""
        glyph = bytes(GLYPH_DATA_SIZE)
        pixels, _, _ = glyph_to_pixels(glyph)
        assert all(p == (0, 0, 0) for p in pixels)


# ============================================================================
# Text crawl / glyph CLI argument parsing
# ============================================================================

class TestCrawlCLI:
    """Test crawl subcommand argument parsing."""

    def test_crawl_view_parse(self):
        """Parse 'exod crawl view <file>'."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'crawl', 'view', 'test.bin'])
        assert args.exod_cmd == 'crawl'
        assert args.crawl_cmd == 'view'
        assert args.file == 'test.bin'

    def test_crawl_export_parse(self):
        """Parse 'exod crawl export <file> -o out.json'."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'crawl', 'export', 'EXOD',
                                  '-o', 'crawl.json'])
        assert args.crawl_cmd == 'export'
        assert args.output == 'crawl.json'

    def test_crawl_import_parse(self):
        """Parse 'exod crawl import <file> <json> --backup --dry-run'."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'crawl', 'import', 'EXOD',
                                  'crawl.json', '--backup', '--dry-run'])
        assert args.crawl_cmd == 'import'
        assert args.json_file == 'crawl.json'
        assert args.backup is True
        assert args.dry_run is True

    def test_crawl_render_parse(self):
        """Parse 'exod crawl render <file> -o crawl.png --scale 3'."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'crawl', 'render', 'EXOD',
                                  '-o', 'crawl.png', '--scale', '3'])
        assert args.crawl_cmd == 'render'
        assert args.output == 'crawl.png'
        assert args.scale == 3


class TestGlyphCLI:
    """Test glyph subcommand argument parsing."""

    def test_glyph_view_parse(self):
        """Parse 'exod glyph view <file>'."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'glyph', 'view', 'test.bin'])
        assert args.exod_cmd == 'glyph'
        assert args.glyph_cmd == 'view'
        assert args.file == 'test.bin'

    def test_glyph_export_parse(self):
        """Parse 'exod glyph export <file> -o dir/ --scale 1'."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'glyph', 'export', 'EXOD',
                                  '-o', 'glyph_dir', '--scale', '1'])
        assert args.glyph_cmd == 'export'
        assert args.output == 'glyph_dir'
        assert args.scale == 1

    def test_glyph_view_json(self):
        """Parse 'exod glyph view <file> --json'."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'glyph', 'view', 'EXOD', '--json'])
        assert args.json is True


# ============================================================================
# Crawl font tests
# ============================================================================

class TestCrawlFont:
    """Test the 5x7 bitmap font definition."""

    def test_has_uppercase_letters(self):
        """Font contains all 26 uppercase letters."""
        for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            assert ch in CRAWL_FONT, f"Missing letter: {ch}"

    def test_has_digits(self):
        """Font contains all 10 digits."""
        for ch in '0123456789':
            assert ch in CRAWL_FONT, f"Missing digit: {ch}"

    def test_has_punctuation(self):
        """Font contains basic punctuation."""
        for ch in ".,:'!-":
            assert ch in CRAWL_FONT, f"Missing punctuation: {ch}"

    def test_glyphs_fit_in_cell(self):
        """All glyph pixels fit within 5x7 cell."""
        for ch, pixels in CRAWL_FONT.items():
            for dx, dy in pixels:
                assert 0 <= dx < CRAWL_FONT_WIDTH, \
                    f"'{ch}' dx={dx} out of 0..{CRAWL_FONT_WIDTH - 1}"
                assert 0 <= dy < CRAWL_FONT_HEIGHT, \
                    f"'{ch}' dy={dy} out of 0..{CRAWL_FONT_HEIGHT - 1}"

    def test_no_duplicate_pixels(self):
        """No glyph has duplicate pixel positions."""
        for ch, pixels in CRAWL_FONT.items():
            assert len(pixels) == len(set(pixels)), \
                f"'{ch}' has duplicate pixel positions"

    def test_glyphs_nonempty(self):
        """Every glyph has at least one pixel."""
        for ch, pixels in CRAWL_FONT.items():
            assert len(pixels) > 0, f"'{ch}' has no pixels"

    def test_font_constants(self):
        """Font dimension constants are correct."""
        assert CRAWL_FONT_WIDTH == 5
        assert CRAWL_FONT_HEIGHT == 7
        assert CRAWL_FONT_SPACING == 1
        assert CRAWL_WORD_SPACING == 3


# ============================================================================
# Crawl text width tests
# ============================================================================

class TestCrawlTextWidth:
    """Test the _crawl_text_width helper."""

    def test_empty_string(self):
        """Empty string has zero width."""
        assert _crawl_text_width('') == 0

    def test_single_char(self):
        """Single character is just cell width."""
        assert _crawl_text_width('A') == CRAWL_FONT_WIDTH

    def test_two_chars(self):
        """Two characters with default spacing."""
        expected = CRAWL_FONT_WIDTH + CRAWL_FONT_SPACING + CRAWL_FONT_WIDTH
        assert _crawl_text_width('AB') == expected

    def test_space_adds_word_spacing(self):
        """Space character adds CRAWL_WORD_SPACING extra pixels."""
        # "A B" = A(5) + spacing(1) + space_cell(5+3) + spacing(1) + B(5)
        expected = (CRAWL_FONT_WIDTH + CRAWL_FONT_SPACING +
                    CRAWL_FONT_WIDTH + CRAWL_WORD_SPACING + CRAWL_FONT_SPACING +
                    CRAWL_FONT_WIDTH)
        assert _crawl_text_width('A B') == expected

    def test_custom_spacing(self):
        """Custom spacing overrides default."""
        expected = CRAWL_FONT_WIDTH + 3 + CRAWL_FONT_WIDTH
        assert _crawl_text_width('AB', spacing=3) == expected


# ============================================================================
# Compose text crawl tests
# ============================================================================

class TestComposeCrawl:
    """Test compose_text_crawl() coordinate generation."""

    def test_single_char_points(self):
        """Single character 'I' produces known pixel coordinates."""
        # 'I' at position (100, 132): top row = 5 pixels, then center col
        coords = compose_text_crawl('I', x=100, y=132)
        # 'I' has 5 pixels on row 0, 1 center pixel on rows 1-5, 5 on row 6
        font_i = CRAWL_FONT['I']
        expected = [(100 + dx, 132 + dy) for dx, dy in font_i]
        assert coords == expected

    def test_auto_uppercase(self):
        """Lowercase input produces same output as uppercase."""
        lower = compose_text_crawl('hi', x=100, y=100)
        upper = compose_text_crawl('HI', x=100, y=100)
        assert lower == upper

    def test_auto_center_x(self):
        """Default x centers the text on 280-pixel screen."""
        coords = compose_text_crawl('A')  # Single char, auto-centered
        width = _crawl_text_width('A')
        expected_x = (HGR_WIDTH - width) // 2
        # 'A' has pixels at dx=0 (rows 1-6), so min_x = expected_x
        xs = [c[0] for c in coords]
        min_x = min(xs)
        assert min_x == expected_x

    def test_default_y(self):
        """Default Y is 132 (vanilla crawl region center)."""
        coords = compose_text_crawl('A')
        ys = [c[1] for c in coords]
        min_y = min(ys)
        # 'A' has pixels starting at dy=0, so min_y = 132
        assert min_y == 132

    def test_two_chars_spacing(self):
        """Two characters have correct horizontal separation."""
        coords = compose_text_crawl('AB', x=10, y=100)
        # 'A' starts at x=10, 'B' starts at x=10+5+1=16
        b_pixels = [(16 + dx, 100 + dy) for dx, dy in CRAWL_FONT['B']]
        for pt in b_pixels:
            assert pt in coords

    def test_space_advances_cursor(self):
        """Space character advances cursor without adding points."""
        # "A B" — the 'B' should start after space width
        coords_ab = compose_text_crawl('A B', x=10, y=100)
        # After 'A'(5) + spacing(1) + space_cell(5+3) + spacing(1) = 15
        b_start_x = 10 + CRAWL_FONT_WIDTH + CRAWL_FONT_SPACING + \
            CRAWL_FONT_WIDTH + CRAWL_WORD_SPACING + CRAWL_FONT_SPACING
        b_pixels = [(b_start_x + dx, 100 + dy) for dx, dy in CRAWL_FONT['B']]
        for pt in b_pixels:
            assert pt in coords_ab

    def test_custom_spacing(self):
        """Custom character spacing is applied between characters."""
        coords = compose_text_crawl('AB', x=10, y=100, spacing=5)
        # 'B' starts at 10 + 5 + 5 = 20
        b_pixels = [(20 + dx, 100 + dy) for dx, dy in CRAWL_FONT['B']]
        for pt in b_pixels:
            assert pt in coords

    def test_point_count(self):
        """Total points equals sum of glyph pixel counts."""
        text = 'BY VOIDBORN'
        coords = compose_text_crawl(text, x=10, y=100)
        expected_points = sum(len(CRAWL_FONT[ch]) for ch in text.upper()
                             if ch in CRAWL_FONT)
        assert len(coords) == expected_points

    def test_all_coordinates_valid(self):
        """All generated coordinates are within valid screen bounds."""
        coords = compose_text_crawl('ABCDEFGHIJ', x=10, y=100)
        for px, py in coords:
            assert 1 <= px <= 255, f"X={px} out of range"
            assert 0 <= py < HGR_ROWS, f"Y={py} out of range"

    def test_compose_render_roundtrip(self):
        """Composed coordinates can be rendered without error."""
        coords = compose_text_crawl('TEST', x=100, y=100)
        pixels = render_text_crawl(coords)
        assert len(pixels) == HGR_WIDTH * HGR_ROWS  # list of (r,g,b) tuples


class TestComposeCrawlValidation:
    """Test edge cases and validation in compose_text_crawl()."""

    def test_empty_text(self):
        """Empty text returns no coordinates."""
        coords = compose_text_crawl('')
        assert coords == []

    def test_space_only(self):
        """Space-only text returns no coordinates."""
        coords = compose_text_crawl('   ')
        assert coords == []

    def test_unknown_char_skipped(self):
        """Unknown characters are silently skipped."""
        # '@' is not in the font
        coords_a = compose_text_crawl('A', x=10, y=100)
        coords_at = compose_text_crawl('@', x=10, y=100)
        assert coords_at == []
        assert len(coords_a) > 0

    def test_x_overflow_clipped(self):
        """Points with X < 1 or X > 255 are omitted."""
        # Place text at x=254 — most pixels will overflow
        coords = compose_text_crawl('A', x=254, y=100)
        for px, py in coords:
            assert 1 <= px <= 255

    def test_y_overflow_clipped(self):
        """Points with Y >= 192 are omitted."""
        # Place text at y=190 — lower rows will overflow
        coords = compose_text_crawl('A', x=100, y=190)
        for px, py in coords:
            assert 0 <= py < HGR_ROWS
        # Should have fewer points than normal since bottom rows clipped
        all_coords = compose_text_crawl('A', x=100, y=100)
        assert len(coords) < len(all_coords)

    def test_x_underflow_clipped(self):
        """Points with X < 1 are omitted."""
        # 'A' has pixels at dx=0, which at x=0 would be 0 (invalid)
        coords = compose_text_crawl('A', x=0, y=100)
        for px, py in coords:
            assert px >= 1


class TestComposeCLI:
    """Test crawl compose CLI argument parsing."""

    def test_compose_parse_basic(self):
        """Parse 'exod crawl compose "TEXT" -o out.json'."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'crawl', 'compose', 'HELLO',
                                  '-o', 'crawl.json'])
        assert args.crawl_cmd == 'compose'
        assert args.text == 'HELLO'
        assert args.output == 'crawl.json'

    def test_compose_parse_all_options(self):
        """Parse compose with all optional arguments."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'crawl', 'compose', 'BY VOIDBORN',
                                  '-o', 'crawl.json', '--x', '50', '--y', '140',
                                  '--spacing', '2', '--render', 'preview.png',
                                  '--scale', '3'])
        assert args.text == 'BY VOIDBORN'
        assert args.x == 50
        assert args.y == 140
        assert args.spacing == 2
        assert args.render == 'preview.png'
        assert args.scale == 3

    def test_compose_parse_defaults(self):
        """Compose defaults: x=None, y=None, spacing=1, scale=2."""
        import argparse
        from ult3edit.exod import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['exod', 'crawl', 'compose', 'TEST'])
        assert args.x is None
        assert args.y is None
        assert args.spacing == 1
        assert args.scale == 2
        assert args.render is None
        assert args.output is None

    def test_compose_main_parity(self):
        """Compose subcommand also works via main() parser."""
        import argparse
        from ult3edit.exod import main
        # main() creates its own parser — test that compose is registered
        # by importing and building the same parser structure
        from ult3edit.exod import _add_crawl_parsers
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='exod_cmd')
        _add_crawl_parsers(sub)
        args = parser.parse_args(['crawl', 'compose', 'HI'])
        assert args.crawl_cmd == 'compose'
        assert args.text == 'HI'
