"""Ultima III: Exodus - Tile Shape / Character Set Viewer/Editor.

SHPS file: 2048 bytes = 256 glyphs x 8 bytes each.
Each glyph is 8x8 pixels (7 visible in Apple II text mode), 1 bit per pixel.
Tile IDs use multiples of 4 — the low 2 bits select animation frame (0-3),
so each tile is a group of 4 consecutive glyphs.

HGR tile rendering is also supported for arbitrary binary sprite data,
using Apple II NTSC artifact color logic.
"""

import argparse
import json
import os
import re
import struct
import sys
import zlib
from pathlib import Path

from .constants import TILES
from .fileutil import resolve_single_file, backup_file, hex_int
from .json_export import export_json

# ============================================================================
# Constants
# ============================================================================

SHPS_FILE_SIZE = 2048
GLYPH_SIZE = 8         # 8 bytes per glyph (8 rows x 1 byte)
GLYPH_WIDTH = 7        # 7 visible pixels per row (bits 0-6)
GLYPH_HEIGHT = 8
GLYPHS_PER_FILE = 256  # SHPS has 256 glyphs
FRAMES_PER_TILE = 4    # 4 animation frames per tile

# SHP overlay files are code+text, not tile shapes
SHP_OVERLAY_LETTERS = '01234567'

# SHPS has an embedded code routine at offset $9F9 ($0800 + $1F9 = $09F9)
# This 7-byte region must be preserved when editing glyphs
SHPS_CODE_OFFSET = 0x01F9  # File offset within SHPS (glyph 63, partial)
SHPS_CODE_SIZE = 7

# SHP overlay shop type mappings (SHP0–SHP7 at $9400)
SHP_SHOP_TYPES = {
    '0': 'Weapons Shop',
    '1': 'Armour Shop',
    '2': 'Grocery',
    '3': 'Pub/Tavern',
    '4': 'Healer/Temple',
    '5': 'Guild',
    '6': 'Oracle',
    '7': 'Horse Trader',
}

# JSR $46BA inline string pattern (Apple II)
_JSR_46BA = bytes([0x20, 0xBA, 0x46])

# Apple II NTSC artifact colors for HGR rendering
HGR_COLORS = {
    'black':  (0, 0, 0),
    'purple': (255, 68, 253),
    'green':  (20, 245, 60),
    'blue':   (20, 207, 253),
    'orange': (255, 106, 60),
    'white':  (255, 255, 255),
}

# ASCII art characters for monochrome glyph rendering
GLYPH_ON = '#'
GLYPH_OFF = '.'

# ASCII art characters for HGR color rendering
HGR_ASCII_MAP = {
    HGR_COLORS['black']:  ' ',
    HGR_COLORS['white']:  '#',
    HGR_COLORS['purple']: 'P',
    HGR_COLORS['green']:  'G',
    HGR_COLORS['blue']:   'B',
    HGR_COLORS['orange']: 'O',
}


# ============================================================================
# Glyph rendering (character set / text-mode tiles)
# ============================================================================

def render_glyph_ascii(data: bytes, offset: int = 0) -> list[str]:
    """Render one 8x8 glyph as ASCII art lines.

    Each byte = 1 row. Bits 0-6 = 7 pixels (bit 0 = leftmost).
    """
    lines = []
    for row in range(GLYPH_HEIGHT):
        b = data[offset + row] if offset + row < len(data) else 0
        pixels = ''.join(
            GLYPH_ON if (b >> bit) & 1 else GLYPH_OFF
            for bit in range(GLYPH_WIDTH)
        )
        lines.append(pixels)
    return lines


def render_glyph_grid(data: bytes, offset: int = 0) -> list[list[int]]:
    """Render one glyph as a 2D grid of 0/1 values."""
    grid = []
    for row in range(GLYPH_HEIGHT):
        b = data[offset + row] if offset + row < len(data) else 0
        grid.append([(b >> bit) & 1 for bit in range(GLYPH_WIDTH)])
    return grid


def glyph_to_dict(data: bytes, index: int) -> dict:
    """Convert a single glyph to a JSON-serializable dict."""
    offset = index * GLYPH_SIZE
    raw = list(data[offset:offset + GLYPH_SIZE])
    return {
        'index': index,
        'raw': raw,
        'hex': ' '.join(f'{b:02X}' for b in raw),
    }


def tile_to_dict(data: bytes, tile_id: int) -> dict:
    """Convert a 4-frame tile group to a dict."""
    frames = []
    for frame in range(FRAMES_PER_TILE):
        idx = tile_id + frame
        frames.append(glyph_to_dict(data, idx))

    tile_entry = TILES.get(tile_id & 0xFC)
    name = tile_entry[1] if tile_entry else f'Tile 0x{tile_id:02X}'

    return {
        'tile_id': tile_id,
        'name': name,
        'frames': frames,
    }


# ============================================================================
# HGR rendering (Apple II hi-res graphics)
# ============================================================================

def render_hgr_row(row_bytes: bytes) -> list[tuple[int, int, int]]:
    """Render one row of HGR data to (r,g,b) pixel tuples.

    Each byte = 7 pixels (bits 0-6). Bit 7 = palette selector.
    Adjacent set bits -> white. Isolated set bit -> color by palette + column.
    """
    num_bytes = len(row_bytes)
    num_pixels = num_bytes * 7
    bits = [0] * num_pixels
    palettes = [0] * num_pixels

    for byte_idx in range(num_bytes):
        byte_val = row_bytes[byte_idx]
        palette = (byte_val >> 7) & 1
        for bit in range(7):
            col = byte_idx * 7 + bit
            bits[col] = (byte_val >> bit) & 1
            palettes[col] = palette

    pixels = []
    for col in range(num_pixels):
        if bits[col] == 0:
            pixels.append(HGR_COLORS['black'])
            continue
        left_set = col > 0 and bits[col - 1] == 1
        right_set = col < num_pixels - 1 and bits[col + 1] == 1
        if left_set or right_set:
            pixels.append(HGR_COLORS['white'])
        else:
            pal = palettes[col]
            if pal == 0:
                pixels.append(HGR_COLORS['purple'] if col % 2 == 0
                              else HGR_COLORS['green'])
            else:
                pixels.append(HGR_COLORS['blue'] if col % 2 == 0
                              else HGR_COLORS['orange'])
    return pixels


def render_hgr_sprite(data: bytes, width_bytes: int, height: int,
                      offset: int = 0) -> list[tuple[int, int, int]]:
    """Render an HGR sprite to a flat pixel list."""
    pixels = []
    for row in range(height):
        start = offset + row * width_bytes
        row_data = data[start:start + width_bytes]
        if len(row_data) < width_bytes:
            row_data = row_data + bytes(width_bytes - len(row_data))
        pixels.extend(render_hgr_row(row_data))
    return pixels


def hgr_ascii_preview(pixels: list[tuple[int, int, int]],
                      width: int, height: int) -> str:
    """Convert HGR pixel data to ASCII art."""
    lines = []
    for y in range(height):
        row = ''.join(
            HGR_ASCII_MAP.get(pixels[y * width + x], '?')
            for x in range(width)
        )
        lines.append(row)
    return '\n'.join(lines)


# ============================================================================
# PNG output (stdlib only, no Pillow required)
# ============================================================================

def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a PNG chunk."""
    chunk = chunk_type + data
    return (struct.pack('>I', len(data)) + chunk +
            struct.pack('>I', zlib.crc32(chunk) & 0xFFFFFFFF))


def write_png(filepath: str, pixels: list[tuple[int, int, int]],
              width: int, height: int) -> None:
    """Write an RGB PNG file from pixel data (stdlib, no Pillow)."""
    raw_rows = bytearray()
    for y in range(height):
        raw_rows.append(0)  # filter byte: None
        for x in range(width):
            r, g, b = pixels[y * width + x]
            raw_rows.extend([r, g, b])

    compressed = zlib.compress(bytes(raw_rows))

    with open(filepath, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        f.write(_png_chunk(b'IHDR', ihdr_data))
        f.write(_png_chunk(b'IDAT', compressed))
        f.write(_png_chunk(b'IEND', b''))


def scale_pixels(pixels: list[tuple[int, int, int]],
                 width: int, height: int,
                 scale: int) -> tuple[list[tuple[int, int, int]], int, int]:
    """Scale pixel data by an integer factor (nearest-neighbor)."""
    if scale <= 1:
        return pixels, width, height
    new_w = width * scale
    new_h = height * scale
    scaled = []
    for y in range(new_h):
        src_y = y // scale
        for x in range(new_w):
            src_x = x // scale
            scaled.append(pixels[src_y * width + src_x])
    return scaled, new_w, new_h


def glyph_to_pixels(data: bytes, offset: int = 0,
                    fg: tuple[int, int, int] = (255, 255, 255),
                    bg: tuple[int, int, int] = (0, 0, 0),
                    ) -> list[tuple[int, int, int]]:
    """Convert a glyph to RGB pixel data for PNG export."""
    pixels = []
    for row in range(GLYPH_HEIGHT):
        b = data[offset + row] if offset + row < len(data) else 0
        for bit in range(GLYPH_WIDTH):
            pixels.append(fg if (b >> bit) & 1 else bg)
    return pixels


# ============================================================================
# SHP overlay inline string extraction
# ============================================================================

def extract_overlay_strings(data: bytes) -> list[dict]:
    """Extract inline text strings from SHP overlay code.

    SHP0-SHP7 are code overlays that use JSR $46BA followed by inline
    high-ASCII text terminated by $00. This finds all such strings.
    """
    strings = []
    i = 0
    while i < len(data) - 3:
        if data[i:i + 3] == _JSR_46BA:
            # Found JSR $46BA — extract inline text starting at i+3
            text_start = i + 3
            chars = []
            j = text_start
            while j < len(data) and data[j] != 0x00:
                b = data[j]
                if b == 0xFF:
                    chars.append('\n')
                else:
                    ch = b & 0x7F
                    if 0x20 <= ch < 0x7F:
                        chars.append(chr(ch))
                j += 1
            if chars:
                strings.append({
                    'jsr_offset': i,
                    'text_offset': text_start,
                    'text_end': j,
                    'text': ''.join(chars),
                })
            i = j + 1
        else:
            i += 1
    return strings


def encode_overlay_string(text: str) -> bytearray:
    """Encode ASCII text as high-ASCII bytes for SHP overlay inline strings.

    Newlines (\\n) become $FF (Apple II line break).
    Terminates with $00.
    """
    result = bytearray()
    for ch in text:
        if ch == '\n':
            result.append(0xFF)
        else:
            result.append(ord(ch.upper()) | 0x80)
    result.append(0x00)  # null terminator
    return result


def replace_overlay_string(data: bytearray, text_offset: int, text_end: int,
                           new_text: str) -> bytearray:
    """Replace an inline string in SHP overlay code.

    The new encoded text (including null terminator) must fit within the
    original text region [text_offset, text_end]. If shorter, pads with $00.
    If longer, raises ValueError showing the maximum length.

    Returns the modified data.
    """
    # text_end points at the original $00 terminator
    max_bytes = text_end - text_offset + 1
    encoded = encode_overlay_string(new_text)

    if len(encoded) > max_bytes:
        max_chars = max_bytes - 1  # subtract null terminator
        raise ValueError(
            f"New text ({len(encoded)} bytes incl. terminator) exceeds "
            f"available space ({max_bytes} bytes at offset "
            f"0x{text_offset:04X}). Maximum ~{max_chars} characters."
        )

    result = bytearray(data)
    # Write encoded text
    result[text_offset:text_offset + len(encoded)] = encoded
    # Null-pad remaining space
    for i in range(text_offset + len(encoded), text_end + 1):
        if i < len(result):
            result[i] = 0x00
    return result


def check_shps_code_region(data: bytes) -> bool:
    """Check if the SHPS embedded code region at $9F9 is non-zero."""
    if len(data) < SHPS_CODE_OFFSET + SHPS_CODE_SIZE:
        return False
    return any(data[SHPS_CODE_OFFSET:SHPS_CODE_OFFSET + SHPS_CODE_SIZE])


# ============================================================================
# File format detection
# ============================================================================

def detect_format(data: bytes, filename: str = '') -> dict:
    """Detect the shape file format based on size and name."""
    name_upper = os.path.basename(filename).upper().split('#')[0]
    size = len(data)

    if name_upper == 'SHPS' or size == SHPS_FILE_SIZE:
        return {
            'type': 'charset',
            'glyphs': size // GLYPH_SIZE,
            'glyph_width': GLYPH_WIDTH,
            'glyph_height': GLYPH_HEIGHT,
            'tiles': (size // GLYPH_SIZE) // FRAMES_PER_TILE,
            'description': f'Character set ({size // GLYPH_SIZE} glyphs, '
                           f'{(size // GLYPH_SIZE) // FRAMES_PER_TILE} tiles)',
        }

    # SHP0-SHP7 are code+text overlays, not tile shapes
    if name_upper.startswith('SHP') and len(name_upper) == 4:
        letter = name_upper[3:]
        shop = SHP_SHOP_TYPES.get(letter, 'Unknown')
        return {
            'type': 'overlay',
            'size': size,
            'letter': letter,
            'shop_type': shop,
            'description': f'Shop overlay: {shop} ({size} bytes)',
        }

    # TEXT file is raw HGR bitmap data (title screen), not editable text
    if name_upper == 'TEXT' or (size == 1024 and name_upper != 'SHPS'):
        return {
            'type': 'hgr_bitmap',
            'size': size,
            'description': f'HGR bitmap data ({size} bytes, likely title screen)',
        }

    # Generic binary — try HGR tile interpretation
    tiles_32 = size // 32  # 2 bytes/row x 16 rows
    tiles_16 = size // 16  # 1 byte/row x 16 rows
    return {
        'type': 'binary',
        'size': size,
        'tiles_32b': tiles_32,
        'tiles_16b': tiles_16,
        'description': f'Binary data ({size} bytes)',
    }


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_view(args) -> None:
    """View tile shapes / character set glyphs."""
    path_or_dir = args.path

    if os.path.isdir(path_or_dir):
        # Directory mode: find SHPS and show info about all shape files
        shps_path = resolve_single_file(path_or_dir, 'SHPS')
        if not shps_path:
            print(f"Error: No SHPS file found in {path_or_dir}", file=sys.stderr)
            sys.exit(1)

        with open(shps_path, 'rb') as f:
            data = f.read()

        fmt = detect_format(data, shps_path)

        if args.json:
            tiles = []
            for tile_id in range(0, fmt['glyphs'], FRAMES_PER_TILE):
                tiles.append(tile_to_dict(data, tile_id))
            result = {
                'file': os.path.basename(shps_path),
                'format': fmt,
                'tiles': tiles,
            }
            export_json(result, args.output)
            return

        print(f"\n=== SHPS Character Set ({fmt['glyphs']} glyphs, "
              f"{fmt['tiles']} tiles) ===\n")

        tile_idx = getattr(args, 'tile', None)
        if tile_idx is not None:
            _show_tile(data, tile_idx)
        else:
            _show_all_tiles(data, fmt)
        return

    # Single file mode
    with open(path_or_dir, 'rb') as f:
        data = f.read()

    fmt = detect_format(data, path_or_dir)
    filename = os.path.basename(path_or_dir)

    if fmt['type'] == 'overlay':
        strings = extract_overlay_strings(data)
        if args.json:
            export_json({'file': filename, 'format': fmt,
                         'strings': [{'offset': s['text_offset'],
                                      'text': s['text']}
                                     for s in strings],
                         'raw': list(data)}, args.output)
            return
        print(f"\n=== {filename}: {fmt['description']} ===")
        print(f"  Type: Shop overlay ({fmt.get('shop_type', 'Unknown')})")
        print(f"  Size: {fmt['size']} bytes")
        if strings:
            print(f"\n  Inline text strings ({len(strings)} found):")
            for s in strings:
                text = s['text'].replace('\n', ' / ')
                print(f"    [0x{s['text_offset']:04X}] {text}")
        print()
        return

    if fmt['type'] == 'hgr_bitmap':
        if args.json:
            export_json({'file': filename, 'format': fmt,
                         'raw': list(data)}, args.output)
            return
        print(f"\n=== {filename}: {fmt['description']} ===")
        print("  (HGR bitmap data — not editable text)")
        print(f"  Size: {fmt['size']} bytes")
        print()
        return

    if args.json:
        if fmt['type'] == 'charset':
            tiles = []
            for tile_id in range(0, fmt['glyphs'], FRAMES_PER_TILE):
                tiles.append(tile_to_dict(data, tile_id))
            result = {'file': filename, 'format': fmt, 'tiles': tiles}
        else:
            result = {'file': filename, 'format': fmt, 'raw': list(data)}
        export_json(result, args.output)
        return

    print(f"\n=== {filename}: {fmt['description']} ===\n")

    if fmt['type'] == 'charset':
        tile_idx = getattr(args, 'tile', None)
        if tile_idx is not None:
            _show_tile(data, tile_idx)
        else:
            _show_all_tiles(data, fmt)
    else:
        # Binary data — hex dump
        _hex_dump(data, 0, len(data))


def _show_tile(data: bytes, tile_id: int) -> None:
    """Show a single tile (4 animation frames) as ASCII art."""
    tile_entry = TILES.get(tile_id & 0xFC)
    name = tile_entry[1] if tile_entry else f'Tile 0x{tile_id:02X}'
    print(f"  Tile 0x{tile_id:02X} ({name}):")

    # Show all 4 frames side by side
    frame_lines = []
    for frame in range(FRAMES_PER_TILE):
        idx = tile_id + frame
        offset = idx * GLYPH_SIZE
        lines = render_glyph_ascii(data, offset)
        frame_lines.append(lines)

    print(f"  {'Frame 0':9s} {'Frame 1':9s} {'Frame 2':9s} {'Frame 3':9s}")
    for row in range(GLYPH_HEIGHT):
        parts = [frame_lines[f][row] for f in range(FRAMES_PER_TILE)]
        print(f"  {'  '.join(parts)}")
    print()


def _show_all_tiles(data: bytes, fmt: dict) -> None:
    """Show all tiles with their names."""
    num_tiles = fmt.get('tiles', 0)
    for i in range(num_tiles):
        tile_id = i * FRAMES_PER_TILE
        _show_tile(data, tile_id)


def cmd_export(args) -> None:
    """Export tiles as PNG files."""
    with open(args.file, 'rb') as f:
        data = f.read()

    fmt = detect_format(data, args.file)
    if fmt['type'] != 'charset':
        print(f"Error: PNG export only supported for charset files",
              file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scale = getattr(args, 'scale', 4)

    num_glyphs = fmt['glyphs']
    exported = 0

    for i in range(num_glyphs):
        offset = i * GLYPH_SIZE
        pixels = glyph_to_pixels(data, offset)
        scaled, sw, sh = scale_pixels(pixels, GLYPH_WIDTH, GLYPH_HEIGHT, scale)
        out_path = out_dir / f'glyph_{i:03d}.png'
        write_png(str(out_path), scaled, sw, sh)
        exported += 1

    print(f"Exported {exported} glyphs to {out_dir}/")

    if getattr(args, 'sheet', False):
        _export_sheet(data, fmt, out_dir, scale)


def _export_sheet(data: bytes, fmt: dict, out_dir: Path, scale: int) -> None:
    """Export a sprite sheet with all glyphs in a grid."""
    num_glyphs = fmt['glyphs']
    cols = 16  # 16 glyphs per row
    rows = (num_glyphs + cols - 1) // cols
    padding = 1

    sheet_w = cols * (GLYPH_WIDTH + padding) - padding
    sheet_h = rows * (GLYPH_HEIGHT + padding) - padding

    sheet = [(0, 0, 0)] * (sheet_w * sheet_h)

    for i in range(num_glyphs):
        gx = (i % cols) * (GLYPH_WIDTH + padding)
        gy = (i // cols) * (GLYPH_HEIGHT + padding)
        pixels = glyph_to_pixels(data, i * GLYPH_SIZE)
        for y in range(GLYPH_HEIGHT):
            for x in range(GLYPH_WIDTH):
                sx, sy = gx + x, gy + y
                if 0 <= sx < sheet_w and 0 <= sy < sheet_h:
                    sheet[sy * sheet_w + sx] = pixels[y * GLYPH_WIDTH + x]

    scaled, sw, sh = scale_pixels(sheet, sheet_w, sheet_h, scale)
    sheet_path = out_dir / 'glyph_sheet.png'
    write_png(str(sheet_path), scaled, sw, sh)
    print(f"Exported sprite sheet: {sheet_path} ({sw}x{sh})")


def cmd_edit(args) -> None:
    """Edit a glyph's raw bytes."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())

    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)

    glyph_idx = args.glyph
    offset = glyph_idx * GLYPH_SIZE
    if offset + GLYPH_SIZE > len(data):
        print(f"Error: Glyph {glyph_idx} out of range (file has "
              f"{len(data) // GLYPH_SIZE} glyphs)", file=sys.stderr)
        sys.exit(1)

    # Parse hex data
    hex_str = args.data.replace(' ', '').replace(',', '')
    try:
        new_bytes = bytes.fromhex(hex_str)
    except ValueError:
        print(f"Error: Invalid hex data: {args.data}", file=sys.stderr)
        sys.exit(1)

    if len(new_bytes) != GLYPH_SIZE:
        print(f"Error: Expected {GLYPH_SIZE} bytes, got {len(new_bytes)}",
              file=sys.stderr)
        sys.exit(1)

    # Warn if editing overlaps the embedded code region in SHPS
    code_start = SHPS_CODE_OFFSET
    code_end = SHPS_CODE_OFFSET + SHPS_CODE_SIZE
    if offset < code_end and offset + GLYPH_SIZE > code_start:
        if check_shps_code_region(data):
            print(f"Warning: Glyph {glyph_idx} overlaps embedded code "
                  f"region at 0x{code_start:04X}-0x{code_end:04X}",
                  file=sys.stderr)
            print(f"  This region contains executable code that must be "
                  f"preserved.", file=sys.stderr)

    old_bytes = bytes(data[offset:offset + GLYPH_SIZE])
    print(f"Glyph {glyph_idx} (offset 0x{offset:04X}):")
    print(f"  Old: {' '.join(f'{b:02X}' for b in old_bytes)}")
    print(f"  New: {' '.join(f'{b:02X}' for b in new_bytes)}")

    if dry_run:
        print("Dry run — no changes written.")
        return

    data[offset:offset + GLYPH_SIZE] = new_bytes

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(bytes(data))
    print(f"Updated glyph {glyph_idx} in {output}")


def cmd_import(args) -> None:
    """Import glyphs or overlay strings from JSON."""
    do_backup = getattr(args, 'backup', False)
    dry_run = getattr(args, 'dry_run', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    # Read existing file to patch into
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())

    count = 0

    # Overlay string replacement
    if isinstance(jdata, dict) and 'strings' in jdata:
        strings_in_file = extract_overlay_strings(data)
        offset_map = {s['text_offset']: s for s in strings_in_file}
        for entry in jdata['strings']:
            offset = entry.get('offset')
            new_text = entry.get('text')
            if offset is None or new_text is None:
                continue
            if offset not in offset_map:
                print(f"Warning: No string at offset 0x{offset:04X}, skipping",
                      file=sys.stderr)
                continue
            s = offset_map[offset]
            try:
                data = replace_overlay_string(
                    data, s['text_offset'], s['text_end'], new_text)
                count += 1
            except ValueError as e:
                print(f"Warning: {e}, skipping", file=sys.stderr)
        print(f"Import: {count} string(s) updated")

    # Glyph import — 'tiles' list or direct glyph list
    elif isinstance(jdata, dict) and 'tiles' in jdata:
        for tile in jdata['tiles']:
            for frame in tile.get('frames', []):
                idx = frame.get('index')
                raw = frame.get('raw')
                if idx is None or raw is None:
                    continue
                offset = idx * GLYPH_SIZE
                if offset + GLYPH_SIZE <= len(data):
                    data[offset:offset + GLYPH_SIZE] = bytes(raw)
                    count += 1
        print(f"Import: {count} glyph(s) updated")
    elif isinstance(jdata, list):
        for entry in jdata:
            idx = entry.get('index')
            raw = entry.get('raw')
            if idx is None or raw is None:
                continue
            offset = idx * GLYPH_SIZE
            if offset + GLYPH_SIZE <= len(data):
                data[offset:offset + GLYPH_SIZE] = bytes(raw)
                count += 1
        print(f"Import: {count} glyph(s) updated")
    else:
        print("Error: Unrecognized JSON format", file=sys.stderr)
        sys.exit(1)

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and os.path.exists(args.file) and (
            not args.output or args.output == args.file):
        backup_file(args.file)

    with open(output, 'wb') as f:
        f.write(bytes(data))
    print(f"Imported to {output}")


def cmd_edit_string(args) -> None:
    """Edit an inline string in an SHP overlay file."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())

    fmt = detect_format(data, args.file)
    if fmt['type'] != 'overlay':
        print(f"Error: {os.path.basename(args.file)} is not an SHP overlay file",
              file=sys.stderr)
        sys.exit(1)

    strings = extract_overlay_strings(data)
    target = None
    for s in strings:
        if s['text_offset'] == args.offset:
            target = s
            break

    if target is None:
        print(f"Error: No inline string at offset 0x{args.offset:04X}",
              file=sys.stderr)
        offsets = ', '.join(f'0x{s["text_offset"]:04X}' for s in strings)
        print(f"  Available offsets: {offsets}", file=sys.stderr)
        sys.exit(1)

    old_text = target['text'].replace('\n', ' / ')
    print(f"String at 0x{args.offset:04X}:")
    print(f"  Old: {old_text}")
    print(f"  New: {args.text}")

    try:
        data = replace_overlay_string(
            data, target['text_offset'], target['text_end'], args.text)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, 'dry_run', False):
        print("Dry run - no changes written.")
        return

    if getattr(args, 'backup', False):
        backup_file(args.file)

    output = args.output if args.output else args.file
    with open(output, 'wb') as f:
        f.write(bytes(data))
    print(f"Updated string in {output}")


def cmd_info(args) -> None:
    """Show shape file metadata."""
    with open(args.file, 'rb') as f:
        data = f.read()

    fmt = detect_format(data, args.file)
    filename = os.path.basename(args.file)

    if args.json:
        export_json({'file': filename, 'size': len(data), 'format': fmt},
                    args.output)
        return

    print(f"\n=== {filename} ===")
    print(f"  Size: {len(data)} bytes (0x{len(data):04X})")
    print(f"  Type: {fmt['type']}")
    print(f"  {fmt['description']}")

    if fmt['type'] == 'charset':
        print(f"  Glyphs: {fmt['glyphs']}")
        print(f"  Tiles: {fmt['tiles']} ({FRAMES_PER_TILE} frames each)")
        print(f"  Glyph size: {GLYPH_WIDTH}x{GLYPH_HEIGHT} pixels")
    print()


def _hex_dump(data: bytes, offset: int, length: int) -> None:
    """Print a hex dump."""
    end = min(offset + length, len(data))
    for i in range(offset, end, 16):
        row = data[i:min(i + 16, end)]
        hex_part = ' '.join(f'{b:02X}' for b in row)
        ascii_part = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in row)
        print(f"  {i:04X}: {hex_part:<48s}  {ascii_part}")


# ============================================================================
# Tile compile / decompile
# ============================================================================

# Characters recognized as "pixel on" in .tiles text-art
_TILE_ON_CHARS = set('#*XO@')

_TILE_HEADER_RE = re.compile(
    r'^#\s*[Tt]ile\s+(0x[0-9A-Fa-f]+|\d+)\s*[:\-]?\s*(.*)')


def _rows_to_glyph(rows: list[str]) -> bytes:
    """Convert 8 text rows to 8-byte glyph data.

    Bit 0 = leftmost pixel, bit 6 = rightmost pixel. Bit 7 always 0.
    """
    result = bytearray(GLYPH_SIZE)
    for r, row in enumerate(rows):
        byte_val = 0
        for c in range(GLYPH_WIDTH):
            ch = row[c] if c < len(row) else '.'
            if ch in _TILE_ON_CHARS:
                byte_val |= (1 << c)
        result[r] = byte_val
    return bytes(result)


def _glyph_to_rows(data: bytes, offset: int = 0) -> list[str]:
    """Convert 8 bytes of glyph data to 8 text rows."""
    rows = []
    for r in range(GLYPH_HEIGHT):
        b = data[offset + r] if offset + r < len(data) else 0
        row = ''
        for c in range(GLYPH_WIDTH):
            row += '#' if (b >> c) & 1 else '.'
        rows.append(row)
    return rows


def parse_tiles_text(text: str) -> list[tuple[int, bytes]]:
    """Parse a .tiles text file into (index, glyph_bytes) tuples."""
    tiles = []
    lines = text.split('\n')
    current_index = None
    current_rows = []

    for line in lines:
        stripped = line.rstrip()

        header_match = _TILE_HEADER_RE.match(stripped)
        if header_match:
            if current_index is not None and len(current_rows) == GLYPH_HEIGHT:
                tiles.append((current_index, _rows_to_glyph(current_rows)))
            elif current_index is not None and current_rows:
                raise ValueError(
                    f'Tile 0x{current_index:02X}: expected {GLYPH_HEIGHT} '
                    f'rows, got {len(current_rows)}')
            current_index = int(header_match.group(1), 0)
            current_rows = []
            continue

        if stripped.startswith('# ') or stripped == '#':
            continue

        if not stripped:
            if current_index is not None and len(current_rows) == GLYPH_HEIGHT:
                tiles.append((current_index, _rows_to_glyph(current_rows)))
                current_index = None
                current_rows = []
            continue

        row_chars = stripped
        if len(row_chars) < GLYPH_WIDTH:
            row_chars = row_chars.ljust(GLYPH_WIDTH, '.')
        elif len(row_chars) > GLYPH_WIDTH:
            row_chars = row_chars[:GLYPH_WIDTH]

        if current_index is None:
            current_index = tiles[-1][0] + 1 if tiles else 0
            current_rows = []

        current_rows.append(row_chars)

    if current_index is not None and len(current_rows) == GLYPH_HEIGHT:
        tiles.append((current_index, _rows_to_glyph(current_rows)))
    elif current_index is not None and current_rows:
        raise ValueError(
            f'Tile 0x{current_index:02X}: expected {GLYPH_HEIGHT} '
            f'rows, got {len(current_rows)}')

    return tiles


def decompile_shps(data: bytes) -> str:
    """Convert SHPS binary data to text-art format."""
    if len(data) < SHPS_FILE_SIZE:
        raise ValueError(
            f'SHPS file too small: {len(data)} bytes '
            f'(expected {SHPS_FILE_SIZE})')

    lines = []
    tile_names = {}
    for tile_id, (char, name) in TILES.items():
        for frame in range(FRAMES_PER_TILE):
            idx = (tile_id + frame) & 0xFF
            suffix = f' (frame {frame})' if frame else ''
            tile_names[idx] = f'{name}{suffix}'

    for idx in range(GLYPHS_PER_FILE):
        name = f': {tile_names[idx]}' if idx in tile_names else ''
        lines.append(f'# Tile 0x{idx:02X}{name}')
        for row_str in _glyph_to_rows(data, idx * GLYPH_SIZE):
            lines.append(row_str)
        lines.append('')

    return '\n'.join(lines)


def cmd_compile_tiles(args) -> None:
    """Compile a .tiles text-art file to SHPS binary or JSON."""
    with open(args.source, 'r', encoding='utf-8') as f:
        text = f.read()

    tiles = parse_tiles_text(text)
    if not tiles:
        print("No tiles found in source file.", file=sys.stderr)
        sys.exit(1)

    fmt = getattr(args, 'format', 'binary')

    if fmt == 'json':
        tile_list = [{'index': idx, 'raw': list(glyph)}
                     for idx, glyph in tiles]
        result = json.dumps({'tiles': [{'frames': tile_list}]}, indent=2)
        output = getattr(args, 'output', None)
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                f.write(result + '\n')
            print(f"Compiled {len(tiles)} tiles to JSON: {output}")
        else:
            print(result)
        return

    # Binary output: produce full 2048-byte SHPS
    data = bytearray(SHPS_FILE_SIZE)
    for idx, glyph in tiles:
        if 0 <= idx < GLYPHS_PER_FILE:
            offset = idx * GLYPH_SIZE
            data[offset:offset + GLYPH_SIZE] = glyph

    output = getattr(args, 'output', None)
    if not output:
        print(f"Compiled {len(tiles)} tiles ({SHPS_FILE_SIZE} bytes)")
        return

    with open(output, 'wb') as f:
        f.write(data)
    print(f"Compiled {len(tiles)} tiles ({SHPS_FILE_SIZE} bytes) to {output}")


def cmd_decompile_tiles(args) -> None:
    """Decompile SHPS binary to text-art .tiles format."""
    with open(args.file, 'rb') as f:
        data = f.read()

    text = decompile_shps(data)
    output = getattr(args, 'output', None)
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        print(f"Decompiled {len(data)} bytes to {output}")
    else:
        print(text)


# ============================================================================
# Parser registration
# ============================================================================

def register_parser(subparsers) -> None:
    """Register shapes subcommands on a CLI subparser group."""
    p = subparsers.add_parser('shapes', help='Tile shapes / character set editor')
    sub = p.add_subparsers(dest='shapes_command')

    p_view = sub.add_parser('view', help='View tile shapes')
    p_view.add_argument('path', help='SHPS file or GAME directory')
    p_view.add_argument('--tile', type=hex_int, help='View specific tile ID (hex OK)')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_export = sub.add_parser('export', help='Export tiles as PNG')
    p_export.add_argument('file', help='SHPS file')
    p_export.add_argument('--output-dir', default='.', help='Output directory')
    p_export.add_argument('--scale', type=int, default=4, help='Scale factor')
    p_export.add_argument('--sheet', action='store_true',
                          help='Also generate sprite sheet')

    p_edit = sub.add_parser('edit', help='Edit a glyph')
    p_edit.add_argument('file', help='SHPS file')
    p_edit.add_argument('--glyph', type=hex_int, required=True,
                        help='Glyph index (0-255)')
    p_edit.add_argument('--data', required=True,
                        help='New glyph data as hex bytes (8 bytes)')
    p_edit.add_argument('--output', '-o', help='Output file')
    p_edit.add_argument('--backup', action='store_true')
    p_edit.add_argument('--dry-run', action='store_true')

    p_import = sub.add_parser('import', help='Import glyphs from JSON')
    p_import.add_argument('file', help='SHPS file')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file')
    p_import.add_argument('--backup', action='store_true')
    p_import.add_argument('--dry-run', action='store_true', help='Show changes without writing')

    p_info = sub.add_parser('info', help='Show file metadata')
    p_info.add_argument('file', help='Shape file')
    p_info.add_argument('--json', action='store_true')
    p_info.add_argument('--output', '-o', help='Output file')

    p_estr = sub.add_parser('edit-string',
                            help='Edit inline string in SHP overlay')
    p_estr.add_argument('file', help='SHP overlay file (SHP0-SHP7)')
    p_estr.add_argument('--offset', type=hex_int, required=True,
                        help='Text offset (hex OK, e.g., 0x1A)')
    p_estr.add_argument('--text', required=True, help='New text string')
    p_estr.add_argument('--output', '-o', help='Output file')
    p_estr.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_estr.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')

    p_compile = sub.add_parser('compile',
                               help='Compile text-art .tiles to SHPS binary')
    p_compile.add_argument('source', help='Text-art .tiles source file')
    p_compile.add_argument('--output', '-o', help='Output file')
    p_compile.add_argument('--format', choices=['binary', 'json'],
                           default='binary', help='Output format')

    p_decompile = sub.add_parser('decompile',
                                 help='Decompile SHPS binary to text-art')
    p_decompile.add_argument('file', help='SHPS binary file')
    p_decompile.add_argument('--output', '-o', help='Output .tiles file')


def dispatch(args) -> None:
    """Dispatch shapes subcommand."""
    cmd = args.shapes_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'export':
        cmd_export(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'import':
        cmd_import(args)
    elif cmd == 'info':
        cmd_info(args)
    elif cmd == 'edit-string':
        cmd_edit_string(args)
    elif cmd == 'compile':
        cmd_compile_tiles(args)
    elif cmd == 'decompile':
        cmd_decompile_tiles(args)
    else:
        print("Usage: u3edit shapes "
              "{view|export|edit|import|info|edit-string|compile|decompile} ...",
              file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Tile Shape Editor')
    sub = parser.add_subparsers(dest='shapes_command')

    p_view = sub.add_parser('view', help='View tile shapes')
    p_view.add_argument('path', help='SHPS file or GAME directory')
    p_view.add_argument('--tile', type=hex_int, help='View specific tile ID (hex OK)')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_export = sub.add_parser('export', help='Export tiles as PNG')
    p_export.add_argument('file', help='SHPS file')
    p_export.add_argument('--output-dir', default='.', help='Output directory')
    p_export.add_argument('--scale', type=int, default=4, help='Scale factor')
    p_export.add_argument('--sheet', action='store_true',
                          help='Also generate sprite sheet')

    p_edit = sub.add_parser('edit', help='Edit a glyph')
    p_edit.add_argument('file', help='SHPS file')
    p_edit.add_argument('--glyph', type=hex_int, required=True,
                        help='Glyph index (0-255)')
    p_edit.add_argument('--data', required=True,
                        help='New glyph data as hex bytes (8 bytes)')
    p_edit.add_argument('--output', '-o', help='Output file')
    p_edit.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')

    p_import = sub.add_parser('import', help='Import glyphs from JSON')
    p_import.add_argument('file', help='SHPS file')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file')
    p_import.add_argument('--backup', action='store_true',
                          help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true',
                          help='Show changes without writing')

    p_info = sub.add_parser('info', help='Show file metadata')
    p_info.add_argument('file', help='Shape file')
    p_info.add_argument('--json', action='store_true', help='Output as JSON')
    p_info.add_argument('--output', '-o', help='Output file')

    p_estr = sub.add_parser('edit-string',
                            help='Edit inline string in SHP overlay')
    p_estr.add_argument('file', help='SHP overlay file (SHP0-SHP7)')
    p_estr.add_argument('--offset', type=hex_int, required=True,
                        help='Text offset (hex OK, e.g., 0x1A)')
    p_estr.add_argument('--text', required=True, help='New text string')
    p_estr.add_argument('--output', '-o', help='Output file')
    p_estr.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_estr.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')

    p_compile = sub.add_parser('compile',
                               help='Compile text-art .tiles to SHPS binary')
    p_compile.add_argument('source', help='Text-art .tiles source file')
    p_compile.add_argument('--output', '-o', help='Output file')
    p_compile.add_argument('--format', choices=['binary', 'json'],
                           default='binary', help='Output format')

    p_decompile = sub.add_parser('decompile',
                                 help='Decompile SHPS binary to text-art')
    p_decompile.add_argument('file', help='SHPS binary file')
    p_decompile.add_argument('--output', '-o', help='Output .tiles file')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
