"""EXOD intro/title screen editor for Ultima III: Exodus.

EXOD is the boot loader and title sequence (26,208 bytes at $2000).
87% animation data (HGR frames), 13% code. This module provides
view/export/import tools for the HGR animation frames that make up
the intro sequence.

Memory layout:
  $2000-$2003  Entry — JMP to init code at $8220+
  $2003-$81FF  Data — HGR animation frames (~25 KB)
  $8220-$86FF  Code — Title sequence, animation engine, audio

The blit engine reads all source frames from HGR page 2 ($4000-$5FFF),
which corresponds to EXOD file offsets $2000-$3FFF. The 6 animation
frames occupy non-overlapping scanline ranges within this 8KB page.
"""

import argparse
import json
import math
import os
import struct
import sys
import zlib

from .shapes import HGR_COLORS, render_hgr_row, write_png, scale_pixels

# ============================================================================
# Constants
# ============================================================================

EXOD_SIZE = 26208       # Expected EXOD file size
EXOD_ORG = 0x2000       # Load address
HGR_PAGE_SIZE = 8192    # One HGR page (40 bytes x 192 scanlines)
HGR_BYTES_PER_ROW = 40  # 40 bytes per HGR scanline = 280 pixels
HGR_ROWS = 192          # 192 scanlines per HGR page
HGR_PIXELS_PER_BYTE = 7 # 7 pixels per byte (bit 7 = palette)
HGR_WIDTH = HGR_BYTES_PER_ROW * HGR_PIXELS_PER_BYTE  # 280 pixels

# HGR page 2 in EXOD: memory $4000-$5FFF = file offsets $2000-$3FFF
HGR_PAGE2_FILE_OFFSET = 0x2000

# Frame definitions: (name, start_scanline, num_rows, col_bytes, col_offset, description)
FRAMES = {
    'title':   (8,   77, 38, 1,  '"ULTIMA III" title art'),
    'serpent':  (85,  43, 31, 5,  'Sea serpent graphic'),
    'castle':   (132,  9,  3, 8,  'Castle scene'),
    'exodus':   (146,  5, 32, 4,  '"EXODUS" text graphic'),
    'frame4':   (152, 16, 13, 14, 'Dramatic reveal frame 4'),
    'frame3':   (168, 16, 13, 14, 'Dramatic reveal frame 3'),
}

# Color palette for user reference
HGR_PALETTE = {
    'black':  (0, 0, 0),
    'white':  (255, 255, 255),
    'purple': (255, 68, 253),
    'green':  (20, 245, 60),
    'blue':   (20, 207, 253),
    'orange': (255, 106, 60),
}


# ============================================================================
# HGR scanline address mapping
# ============================================================================

def hgr_scanline_offset(row: int) -> int:
    """Return byte offset within an 8KB HGR page for the given scanline (0-191).

    Apple II HGR memory layout uses interleaved scanlines:
      address = base + (row % 8) * 0x400 + ((row % 64) // 8) * 0x80 + (row // 64) * 0x28
    """
    line = row % 8
    subgroup = (row % 64) // 8
    group = row // 64
    return line * 0x0400 + subgroup * 0x0080 + group * 0x0028


def build_scanline_table() -> list:
    """Build the full 192-entry scanline offset table."""
    return [hgr_scanline_offset(row) for row in range(HGR_ROWS)]


# ============================================================================
# HGR page extraction / insertion
# ============================================================================

def extract_hgr_page(exod_data: bytes) -> bytearray:
    """Extract the 8KB HGR page 2 data from EXOD file data.

    Returns a deinterleaved 8192-byte buffer.
    """
    return bytearray(exod_data[HGR_PAGE2_FILE_OFFSET:HGR_PAGE2_FILE_OFFSET + HGR_PAGE_SIZE])


def patch_hgr_page(exod_data: bytearray, hgr_page: bytes) -> None:
    """Write 8KB HGR page data back into EXOD file data."""
    exod_data[HGR_PAGE2_FILE_OFFSET:HGR_PAGE2_FILE_OFFSET + HGR_PAGE_SIZE] = hgr_page[:HGR_PAGE_SIZE]


def read_hgr_scanline(hgr_page: bytes, row: int) -> bytes:
    """Read one 40-byte scanline from an interleaved HGR page."""
    offset = hgr_scanline_offset(row)
    return bytes(hgr_page[offset:offset + HGR_BYTES_PER_ROW])


def write_hgr_scanline(hgr_page: bytearray, row: int, data: bytes) -> None:
    """Write one 40-byte scanline to an interleaved HGR page."""
    offset = hgr_scanline_offset(row)
    hgr_page[offset:offset + HGR_BYTES_PER_ROW] = data[:HGR_BYTES_PER_ROW]


# ============================================================================
# Frame extraction / insertion
# ============================================================================

def extract_frame(hgr_page: bytes, frame_name: str) -> list:
    """Extract a frame's scanlines as a list of byte rows.

    Each row is col_bytes long, taken from the frame's column range.
    """
    start_row, num_rows, col_bytes, col_offset, _ = FRAMES[frame_name]
    rows = []
    for r in range(num_rows):
        scanline = read_hgr_scanline(hgr_page, start_row + r)
        rows.append(bytes(scanline[col_offset:col_offset + col_bytes]))
    return rows


def insert_frame(hgr_page: bytearray, frame_name: str, rows: list) -> None:
    """Insert frame data (list of byte rows) into the HGR page."""
    start_row, num_rows, col_bytes, col_offset, _ = FRAMES[frame_name]
    for r in range(min(num_rows, len(rows))):
        scanline = bytearray(read_hgr_scanline(hgr_page, start_row + r))
        row_data = rows[r][:col_bytes]
        scanline[col_offset:col_offset + len(row_data)] = row_data
        write_hgr_scanline(hgr_page, start_row + r, bytes(scanline))


# ============================================================================
# HGR rendering (frame -> pixels)
# ============================================================================

def frame_to_pixels(rows: list) -> tuple:
    """Convert frame byte rows to RGB pixel data.

    Returns (pixels, width, height) where pixels is a flat list of (r,g,b).
    """
    if not rows:
        return [], 0, 0
    width_bytes = len(rows[0])
    width = width_bytes * HGR_PIXELS_PER_BYTE
    height = len(rows)
    pixels = []
    for row_data in rows:
        pixels.extend(render_hgr_row(row_data))
    return pixels, width, height


def canvas_to_pixels(hgr_page: bytes) -> tuple:
    """Render the full 280x192 HGR page to RGB pixels.

    Returns (pixels, 280, 192).
    """
    pixels = []
    for row in range(HGR_ROWS):
        scanline = read_hgr_scanline(hgr_page, row)
        pixels.extend(render_hgr_row(scanline))
    return pixels, HGR_WIDTH, HGR_ROWS


# ============================================================================
# PNG reading (stdlib, no Pillow)
# ============================================================================

def read_png(filepath: str) -> tuple:
    """Read an RGB PNG file, return (pixels, width, height).

    Supports 8-bit RGB (color type 2) and 8-bit RGBA (color type 6).
    Returns pixels as a flat list of (r, g, b) tuples.
    """
    with open(filepath, 'rb') as f:
        data = f.read()

    # Validate PNG signature
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f"Not a valid PNG file: {filepath}")

    # Parse chunks
    pos = 8
    width = height = bit_depth = color_type = 0
    idat_chunks = []

    while pos < len(data):
        chunk_len = struct.unpack('>I', data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8]
        chunk_data = data[pos + 8:pos + 8 + chunk_len]
        pos += 12 + chunk_len  # 4 len + 4 type + data + 4 crc

        if chunk_type == b'IHDR':
            width, height, bit_depth, color_type = struct.unpack('>IIBB', chunk_data[:10])
            if bit_depth != 8:
                raise ValueError(f"Unsupported bit depth: {bit_depth} (need 8)")
            if color_type not in (2, 6):
                raise ValueError(f"Unsupported color type: {color_type} (need RGB=2 or RGBA=6)")
        elif chunk_type == b'IDAT':
            idat_chunks.append(chunk_data)
        elif chunk_type == b'IEND':
            break

    # Decompress
    compressed = b''.join(idat_chunks)
    raw = zlib.decompress(compressed)

    # Determine bytes per pixel
    bpp = 3 if color_type == 2 else 4
    stride = width * bpp

    # Apply PNG row filters
    pixels = []
    prev_row = [0] * stride
    raw_pos = 0

    for y in range(height):
        filter_type = raw[raw_pos]
        raw_pos += 1
        row = list(raw[raw_pos:raw_pos + stride])
        raw_pos += stride

        if filter_type == 1:    # Sub
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + a) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(stride):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + (a + prev_row[i]) // 2) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                b = prev_row[i]
                c = prev_row[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                row[i] = (row[i] + pr) & 0xFF

        # Extract RGB pixels (discard alpha if RGBA)
        for x in range(width):
            offset = x * bpp
            pixels.append((row[offset], row[offset + 1], row[offset + 2]))

        prev_row = row

    return pixels, width, height


# ============================================================================
# HGR encoding (pixels -> bytes)
# ============================================================================

# CCIR 601 luminosity weights (matches BMP2DHR GetMedColor)
LUMA_R = 0.299
LUMA_G = 0.587
LUMA_B = 0.114

# Palette subsets for three-pass selection
PALETTE_0_COLORS = {'black', 'purple', 'green', 'white'}   # bit 7 = 0
PALETTE_1_COLORS = {'black', 'blue', 'orange', 'white'}    # bit 7 = 1


def _color_distance(pixel: tuple, palette_color: tuple) -> float:
    """CCIR 601 luminosity-weighted color distance.

    Adapted from BMP2DHR's GetMedColor(): weights RGB squared differences
    by CCIR 601 luminosity, blends 75% chrominance + 25% luminance delta.
    Green differences count ~2x red and ~5x blue, matching human vision.
    """
    dr = (pixel[0] - palette_color[0]) / 255.0
    dg = (pixel[1] - palette_color[1]) / 255.0
    db = (pixel[2] - palette_color[2]) / 255.0
    luma_src = (pixel[0] * LUMA_R + pixel[1] * LUMA_G + pixel[2] * LUMA_B) / 255.0
    luma_pal = (palette_color[0] * LUMA_R + palette_color[1] * LUMA_G
                + palette_color[2] * LUMA_B) / 255.0
    luma_diff = luma_pal - luma_src
    return (dr * dr * LUMA_R + dg * dg * LUMA_G + db * db * LUMA_B) * 0.75 \
        + luma_diff * luma_diff


def _nearest_hgr_color(pixel: tuple, palette_filter: set = None) -> str:
    """Map an RGB pixel to the nearest HGR color name.

    Uses CCIR 601 perceptual color distance. If palette_filter is given,
    only colors in that set are considered (for three-pass palette selection).
    """
    best_name = 'black'
    best_dist = float('inf')
    for name, rgb in HGR_PALETTE.items():
        if palette_filter is not None and name not in palette_filter:
            continue
        dist = _color_distance(pixel, rgb)
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


def _match_color_error(pixel: tuple, palette_filter: set = None) -> tuple:
    """Match pixel to nearest HGR color, return (color_name, abs_rgb_error).

    The absolute RGB error is the sum |dR| + |dG| + |dB| between input
    and matched palette color (used by three-pass palette selection).
    """
    name = _nearest_hgr_color(pixel, palette_filter)
    matched = HGR_PALETTE[name]
    error = abs(pixel[0] - matched[0]) + abs(pixel[1] - matched[1]) + abs(pixel[2] - matched[2])
    return name, error


def encode_hgr_row(pixels: list, start_col: int = 0) -> bytes:
    """Encode a row of RGB pixels to HGR bytes.

    pixels: list of (r,g,b) tuples, must be a multiple of 7 in length.
    start_col: the absolute pixel column of the first pixel (for even/odd
               color mapping). Default 0.

    Returns bytes where each byte = 7 pixels (bits 0-6) + palette bit (bit 7).

    Three-pass algorithm (adapted from BMP2DHR / Sheldon Simms' tohgr):
    1. Match all pixels using palette 0 (purple/green), record per-pixel error
    2. Match all pixels using palette 1 (blue/orange), record per-pixel error
    3. For each 7-pixel byte, sum errors from both passes, pick the palette
       with lower total error, then encode using the winning palette
    """
    num_pixels = len(pixels)
    num_bytes = num_pixels // 7
    if num_pixels % 7 != 0:
        num_bytes += 1

    # Pass 0: match with palette 0 (purple/green), accumulate error
    pal0_errors = [0] * num_pixels
    for i in range(num_pixels):
        _, pal0_errors[i] = _match_color_error(pixels[i], PALETTE_0_COLORS)

    # Pass 1: match with palette 1 (blue/orange), accumulate error
    pal1_errors = [0] * num_pixels
    for i in range(num_pixels):
        _, pal1_errors[i] = _match_color_error(pixels[i], PALETTE_1_COLORS)

    # Pass 2: for each byte, pick palette with lowest cumulative error
    result = bytearray(num_bytes)
    for byte_idx in range(num_bytes):
        pix_start = byte_idx * 7
        pix_end = min(pix_start + 7, num_pixels)

        # Sum errors for this 7-pixel group
        err0 = sum(pal0_errors[pix_start:pix_end])
        err1 = sum(pal1_errors[pix_start:pix_end])

        # Pick winning palette
        if err1 < err0:
            palette_bit = 1
            pal_filter = PALETTE_1_COLORS
        else:
            palette_bit = 0
            pal_filter = PALETTE_0_COLORS

        # Encode pixel bits using the winning palette
        byte_val = palette_bit << 7
        for bit in range(7):
            pix_idx = pix_start + bit
            if pix_idx >= num_pixels:
                break
            color = _nearest_hgr_color(pixels[pix_idx], pal_filter)
            if color != 'black':
                byte_val |= (1 << bit)

        result[byte_idx] = byte_val

    return bytes(result)


def encode_hgr_image(pixels: list, width: int, height: int,
                     start_col: int = 0) -> list:
    """Encode a full image to HGR byte rows with Floyd-Steinberg dithering.

    Applies error diffusion across the entire image before HGR encoding.
    Uses serpentine scanning (alternating L-to-R / R-to-L per scanline)
    and three-pass palette selection per 7-pixel group.

    pixels: flat list of (r,g,b) tuples, width * height entries.
    width: image width in pixels (must be multiple of 7).
    height: image height in pixels.
    start_col: absolute pixel column offset for palette mapping.

    Returns list of bytes objects (one per row), each width//7 bytes.

    Algorithm adapted from BMP2DHR (Bill Buckels) FloydSteinberg() with
    serpentine scanning and three-pass HGR palette selection.
    """
    num_bytes = width // 7

    # Build mutable float pixel buffer for error accumulation
    # Each pixel is [r, g, b] as floats
    buf = [[0.0, 0.0, 0.0] for _ in range(width * height)]
    for i in range(width * height):
        if i < len(pixels):
            buf[i] = [float(pixels[i][0]), float(pixels[i][1]), float(pixels[i][2])]

    rows = []
    for y in range(height):
        row_start = y * width
        serpentine = (y % 2 == 1)

        # Three-pass palette selection for this scanline
        # We need to determine the best palette per 7-pixel group BEFORE
        # dithering so the error diffusion uses the correct palette.
        # But dithered pixels affect palette choice... BMP2DHR solves this
        # with two test passes + one final pass. We do the same:

        # Snapshot current row pixels (with accumulated error from above)
        row_pixels = []
        for x in range(width):
            r = max(0.0, min(255.0, buf[row_start + x][0]))
            g = max(0.0, min(255.0, buf[row_start + x][1]))
            b = max(0.0, min(255.0, buf[row_start + x][2]))
            row_pixels.append((int(r + 0.5), int(g + 0.5), int(b + 0.5)))

        # Pass 0: test with palette 0
        pal0_errors = [0] * width
        for x in range(width):
            _, pal0_errors[x] = _match_color_error(row_pixels[x], PALETTE_0_COLORS)

        # Pass 1: test with palette 1
        pal1_errors = [0] * width
        for x in range(width):
            _, pal1_errors[x] = _match_color_error(row_pixels[x], PALETTE_1_COLORS)

        # Pass 2: determine palette per byte group
        byte_palettes = [0] * num_bytes
        for byte_idx in range(num_bytes):
            px_start = byte_idx * 7
            px_end = min(px_start + 7, width)
            err0 = sum(pal0_errors[px_start:px_end])
            err1 = sum(pal1_errors[px_start:px_end])
            byte_palettes[byte_idx] = 1 if err1 < err0 else 0

        # Now dither: process pixels with Floyd-Steinberg error diffusion
        # using the winning palette for each byte group
        if serpentine:
            x_range = range(width - 1, -1, -1)
        else:
            x_range = range(width)

        matched_colors = ['black'] * width
        for x in x_range:
            # Get pixel with accumulated error, clamp to 0-255
            r = max(0.0, min(255.0, buf[row_start + x][0]))
            g = max(0.0, min(255.0, buf[row_start + x][1]))
            b = max(0.0, min(255.0, buf[row_start + x][2]))
            pixel = (int(r + 0.5), int(g + 0.5), int(b + 0.5))

            # Determine which palette this pixel's byte uses
            byte_idx = x // 7
            if byte_palettes[byte_idx] == 1:
                pal_filter = PALETTE_1_COLORS
            else:
                pal_filter = PALETTE_0_COLORS

            # Match to nearest color in the winning palette
            color = _nearest_hgr_color(pixel, pal_filter)
            matched_colors[x] = color
            matched_rgb = HGR_PALETTE[color]

            # Compute error
            err_r = r - matched_rgb[0]
            err_g = g - matched_rgb[1]
            err_b = b - matched_rgb[2]

            # Floyd-Steinberg diffusion weights:
            #        *   7/16
            # 3/16  5/16  1/16
            # Serpentine reverses left/right
            if serpentine:
                # Right-to-left: spread error leftward
                if x > 0:
                    buf[row_start + x - 1][0] += err_r * 7.0 / 16.0
                    buf[row_start + x - 1][1] += err_g * 7.0 / 16.0
                    buf[row_start + x - 1][2] += err_b * 7.0 / 16.0
                if y + 1 < height:
                    next_row = row_start + width
                    if x < width - 1:
                        buf[next_row + x + 1][0] += err_r * 3.0 / 16.0
                        buf[next_row + x + 1][1] += err_g * 3.0 / 16.0
                        buf[next_row + x + 1][2] += err_b * 3.0 / 16.0
                    buf[next_row + x][0] += err_r * 5.0 / 16.0
                    buf[next_row + x][1] += err_g * 5.0 / 16.0
                    buf[next_row + x][2] += err_b * 5.0 / 16.0
                    if x > 0:
                        buf[next_row + x - 1][0] += err_r * 1.0 / 16.0
                        buf[next_row + x - 1][1] += err_g * 1.0 / 16.0
                        buf[next_row + x - 1][2] += err_b * 1.0 / 16.0
            else:
                # Left-to-right: spread error rightward
                if x + 1 < width:
                    buf[row_start + x + 1][0] += err_r * 7.0 / 16.0
                    buf[row_start + x + 1][1] += err_g * 7.0 / 16.0
                    buf[row_start + x + 1][2] += err_b * 7.0 / 16.0
                if y + 1 < height:
                    next_row = row_start + width
                    if x > 0:
                        buf[next_row + x - 1][0] += err_r * 3.0 / 16.0
                        buf[next_row + x - 1][1] += err_g * 3.0 / 16.0
                        buf[next_row + x - 1][2] += err_b * 3.0 / 16.0
                    buf[next_row + x][0] += err_r * 5.0 / 16.0
                    buf[next_row + x][1] += err_g * 5.0 / 16.0
                    buf[next_row + x][2] += err_b * 5.0 / 16.0
                    if x + 1 < width:
                        buf[next_row + x + 1][0] += err_r * 1.0 / 16.0
                        buf[next_row + x + 1][1] += err_g * 1.0 / 16.0
                        buf[next_row + x + 1][2] += err_b * 1.0 / 16.0

        # Encode the matched colors into HGR bytes
        row_result = bytearray(num_bytes)
        for byte_idx in range(num_bytes):
            pix_start = byte_idx * 7
            byte_val = byte_palettes[byte_idx] << 7
            for bit in range(7):
                pix_idx = pix_start + bit
                if pix_idx >= width:
                    break
                if matched_colors[pix_idx] != 'black':
                    byte_val |= (1 << bit)
            row_result[byte_idx] = byte_val

        rows.append(bytes(row_result))

    return rows


# ============================================================================
# Frame import (PNG -> HGR bytes)
# ============================================================================

def pixels_to_frame_rows(pixels: list, width: int, height: int,
                         col_bytes: int, col_offset: int,
                         dither: bool = False) -> list:
    """Convert RGB pixel data to a list of HGR byte rows for a frame.

    pixels: flat list of (r,g,b), width x height entries.
    col_bytes: number of HGR bytes per row for this frame.
    col_offset: byte offset within the scanline where frame starts.
    dither: if True, use Floyd-Steinberg error diffusion.

    Returns list of bytes objects (one per row).
    """
    expected_width = col_bytes * HGR_PIXELS_PER_BYTE

    # Normalize pixels to expected dimensions
    norm_pixels = []
    for y in range(height):
        row_pixels = pixels[y * width:y * width + min(width, expected_width)]
        while len(row_pixels) < expected_width:
            row_pixels.append((0, 0, 0))
        norm_pixels.extend(row_pixels[:expected_width])

    abs_start = col_offset * HGR_PIXELS_PER_BYTE

    if dither:
        return encode_hgr_image(norm_pixels, expected_width, height,
                                start_col=abs_start)
    else:
        rows = []
        for y in range(height):
            start = y * expected_width
            row_pixels = norm_pixels[start:start + expected_width]
            row_bytes = encode_hgr_row(row_pixels, start_col=abs_start)
            rows.append(row_bytes[:col_bytes])
        return rows


# ============================================================================
# CLI commands
# ============================================================================

def cmd_view(args) -> None:
    """Display EXOD frame structure."""
    filepath = args.file
    if not os.path.isfile(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'rb') as f:
        data = f.read()

    size = len(data)
    print(f"=== EXOD: {os.path.basename(filepath)} ===")
    print(f"  File size: {size} bytes (expected {EXOD_SIZE})")
    print(f"  Load address: ${EXOD_ORG:04X}")
    print(f"  Data region: $2003-$81FF ({size - 0x04E0} bytes, HGR frames)")
    print(f"  Code region: $8220-$86FF (~1,248 bytes)")
    print(f"  HGR page 2: file offsets $2000-$3FFF (8,192 bytes)")
    print()

    print("  Animation Frames (HGR page 2):")
    print(f"  {'Frame':<10} {'Scanlines':>12} {'Rows':>5} {'Cols':>5} "
          f"{'Pixels':>10} {'Offset':>7} {'Bytes':>6}")
    print(f"  {'-'*10} {'-'*12} {'-'*5} {'-'*5} {'-'*10} {'-'*7} {'-'*6}")

    for name in ('title', 'serpent', 'castle', 'exodus', 'frame4', 'frame3'):
        start, rows, cols, col_off, desc = FRAMES[name]
        end = start + rows - 1
        px_w = cols * HGR_PIXELS_PER_BYTE
        px_h = rows
        total_bytes = rows * cols
        print(f"  {name:<10} {start:>5}-{end:<5} {rows:>5} {cols:>5} "
              f"{px_w:>4}x{px_h:<4} {col_off:>7} {total_bytes:>6}")

    print()
    print("  Apple II HGR Palette (6 colors):")
    for name, (r, g, b) in HGR_PALETTE.items():
        print(f"    {name:<8} ({r:>3}, {g:>3}, {b:>3})  #{r:02X}{g:02X}{b:02X}")

    if getattr(args, 'json', False):
        result = {
            'file': filepath,
            'size': size,
            'frames': {},
        }
        for name, (start, rows, cols, col_off, desc) in FRAMES.items():
            result['frames'][name] = {
                'description': desc,
                'start_scanline': start,
                'num_rows': rows,
                'col_bytes': cols,
                'col_offset': col_off,
                'pixel_width': cols * HGR_PIXELS_PER_BYTE,
                'pixel_height': rows,
            }
        print()
        print(json.dumps(result, indent=2))


def cmd_export(args) -> None:
    """Export EXOD animation frames as PNG images."""
    filepath = args.file
    if not os.path.isfile(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'rb') as f:
        data = f.read()

    output_dir = getattr(args, 'output', None) or '.'
    os.makedirs(output_dir, exist_ok=True)

    hgr_page = extract_hgr_page(data)
    frame_name = getattr(args, 'frame', None)
    frame_scale = getattr(args, 'scale', 2)

    if frame_name and frame_name != 'canvas':
        if frame_name not in FRAMES:
            print(f"Error: Unknown frame '{frame_name}'. "
                  f"Valid: {', '.join(FRAMES.keys())}, canvas", file=sys.stderr)
            sys.exit(1)
        frames_to_export = [frame_name]
    elif frame_name == 'canvas':
        frames_to_export = []
    else:
        frames_to_export = list(FRAMES.keys())

    # Export individual frames
    for name in frames_to_export:
        rows = extract_frame(hgr_page, name)
        pixels, width, height = frame_to_pixels(rows)
        if frame_scale > 1:
            pixels, width, height = scale_pixels(pixels, width, height, frame_scale)
        out_path = os.path.join(output_dir, f'{name}.png')
        write_png(out_path, pixels, width, height)
        start, num_rows, cols, _, desc = FRAMES[name]
        raw_w = cols * HGR_PIXELS_PER_BYTE
        print(f"  Exported {name}: {raw_w}x{num_rows} -> {out_path}")

    # Always export canvas (full 280x192 page)
    if not frame_name or frame_name == 'canvas':
        pixels, width, height = canvas_to_pixels(hgr_page)
        if frame_scale > 1:
            pixels, width, height = scale_pixels(pixels, width, height, frame_scale)
        out_path = os.path.join(output_dir, 'canvas.png')
        write_png(out_path, pixels, width, height)
        print(f"  Exported canvas: {HGR_WIDTH}x{HGR_ROWS} -> {out_path}")

    print()
    print("  Apple II HGR Palette for drawing:")
    for name, (r, g, b) in HGR_PALETTE.items():
        print(f"    {name:<8} #{r:02X}{g:02X}{b:02X}")


def cmd_import(args) -> None:
    """Import a PNG image as an EXOD animation frame."""
    filepath = args.file
    png_path = args.png
    frame_name = args.frame
    use_dither = getattr(args, 'dither', False)

    if not os.path.isfile(filepath):
        print(f"Error: EXOD file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(png_path):
        print(f"Error: PNG file not found: {png_path}", file=sys.stderr)
        sys.exit(1)
    if frame_name != 'canvas' and frame_name not in FRAMES:
        print(f"Error: Unknown frame '{frame_name}'. "
              f"Valid: {', '.join(FRAMES.keys())}, canvas", file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'rb') as f:
        exod_data = bytearray(f.read())

    pixels, width, height = read_png(png_path)
    hgr_page = extract_hgr_page(exod_data)

    dither_label = " (dithered)" if use_dither else ""

    if frame_name == 'canvas':
        # Import full 280x192 canvas
        if width != HGR_WIDTH or height != HGR_ROWS:
            print(f"Error: Canvas must be {HGR_WIDTH}x{HGR_ROWS}, "
                  f"got {width}x{height}", file=sys.stderr)
            sys.exit(1)
        if use_dither:
            hgr_rows = encode_hgr_image(pixels, HGR_WIDTH, HGR_ROWS,
                                        start_col=0)
            for row in range(HGR_ROWS):
                scanline = bytearray(HGR_BYTES_PER_ROW)
                row_bytes = hgr_rows[row]
                scanline[:len(row_bytes)] = row_bytes[:HGR_BYTES_PER_ROW]
                write_hgr_scanline(hgr_page, row, bytes(scanline))
        else:
            for row in range(HGR_ROWS):
                row_pixels = pixels[row * HGR_WIDTH:(row + 1) * HGR_WIDTH]
                row_bytes = encode_hgr_row(row_pixels, start_col=0)
                scanline = bytearray(HGR_BYTES_PER_ROW)
                scanline[:len(row_bytes)] = row_bytes[:HGR_BYTES_PER_ROW]
                write_hgr_scanline(hgr_page, row, bytes(scanline))
        print(f"  Imported canvas: {width}x{height}{dither_label} -> full HGR page")
    else:
        # Import individual frame
        start, num_rows, col_bytes, col_offset, desc = FRAMES[frame_name]
        expected_w = col_bytes * HGR_PIXELS_PER_BYTE
        expected_h = num_rows

        if width != expected_w or height != expected_h:
            print(f"Error: Frame '{frame_name}' expects {expected_w}x{expected_h}, "
                  f"got {width}x{height}", file=sys.stderr)
            sys.exit(1)

        rows = pixels_to_frame_rows(pixels, width, height, col_bytes,
                                    col_offset, dither=use_dither)
        insert_frame(hgr_page, frame_name, rows)
        print(f"  Imported {frame_name}: {width}x{height}{dither_label}")

    if getattr(args, 'dry_run', False):
        print("  (dry run — no file written)")
        return

    # Write back
    from .fileutil import backup_file
    if getattr(args, 'backup', False):
        backup_file(filepath)

    patch_hgr_page(exod_data, hgr_page)
    with open(filepath, 'wb') as f:
        f.write(exod_data)
    print(f"  Written: {filepath}")


# ============================================================================
# CLI registration
# ============================================================================

def register_parser(subparsers) -> None:
    """Register EXOD subcommands with the CLI parser."""
    exod_parser = subparsers.add_parser(
        'exod',
        help='EXOD intro/title screen graphics editor',
    )
    exod_sub = exod_parser.add_subparsers(dest='exod_cmd', help='EXOD command')

    # view
    view_parser = exod_sub.add_parser('view', help='Show EXOD frame structure')
    view_parser.add_argument('file', help='Path to EXOD binary')
    view_parser.add_argument('--json', action='store_true', help='JSON output')

    # export
    export_parser = exod_sub.add_parser('export', help='Export frames as PNG')
    export_parser.add_argument('file', help='Path to EXOD binary')
    export_parser.add_argument('-o', '--output', help='Output directory')
    export_parser.add_argument('--frame', help='Export single frame (or "canvas")')
    export_parser.add_argument('--scale', type=int, default=2,
                               help='Scale factor for output (default: 2)')

    # import
    import_parser = exod_sub.add_parser('import', help='Import PNG as frame')
    import_parser.add_argument('file', help='Path to EXOD binary')
    import_parser.add_argument('png', help='Path to PNG image')
    import_parser.add_argument('--frame', required=True,
                               help='Frame name (title/serpent/castle/exodus/frame3/frame4/canvas)')
    import_parser.add_argument('--backup', action='store_true', help='Create .bak backup')
    import_parser.add_argument('--dry-run', action='store_true', help='Show changes only')
    import_parser.add_argument('--dither', action='store_true',
                               help='Floyd-Steinberg error diffusion dithering')


def dispatch(args) -> None:
    """Route to the correct EXOD subcommand."""
    cmd = getattr(args, 'exod_cmd', None)
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'export':
        cmd_export(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: ult3edit exod {view|export|import} ...", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Standalone entry point for ult3-exod."""
    parser = argparse.ArgumentParser(
        prog='ult3-exod',
        description='EXOD intro/title screen graphics editor',
    )
    sub = parser.add_subparsers(dest='exod_cmd', help='Command')

    view_p = sub.add_parser('view', help='Show EXOD frame structure')
    view_p.add_argument('file', help='Path to EXOD binary')
    view_p.add_argument('--json', action='store_true', help='JSON output')

    export_p = sub.add_parser('export', help='Export frames as PNG')
    export_p.add_argument('file', help='Path to EXOD binary')
    export_p.add_argument('-o', '--output', help='Output directory')
    export_p.add_argument('--frame', help='Export single frame (or "canvas")')
    export_p.add_argument('--scale', type=int, default=2,
                          help='Scale factor (default: 2)')

    import_p = sub.add_parser('import', help='Import PNG as frame')
    import_p.add_argument('file', help='Path to EXOD binary')
    import_p.add_argument('png', help='Path to PNG image')
    import_p.add_argument('--frame', required=True,
                          help='Frame name (title/serpent/castle/exodus/frame3/frame4/canvas)')
    import_p.add_argument('--backup', action='store_true', help='Create .bak backup')
    import_p.add_argument('--dry-run', action='store_true', help='Show changes only')
    import_p.add_argument('--dither', action='store_true',
                          help='Floyd-Steinberg error diffusion dithering')

    args = parser.parse_args()
    if not args.exod_cmd:
        parser.print_help()
        sys.exit(0)
    dispatch(args)


if __name__ == '__main__':
    main()
