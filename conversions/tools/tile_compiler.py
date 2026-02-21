#!/usr/bin/env python3
"""Tile Compiler — Convert text-art tile definitions to/from SHPS binary.

Source format (.tiles files):
    # Tile 0x00: Ground
    .......
    .......
    ..#.#..
    .......
    .#...#.
    .......
    ..#.#..
    .......

Each tile = 8 rows x 7 columns. '#' = pixel on, '.' = pixel off.
Lines starting with '#' followed by a space are comments/headers.
Blank lines separate tiles.

Compile: text-art -> hex bytes (JSON or shell script output)
Decompile: SHPS binary -> text-art
"""

import argparse
import json
import re
import sys
from pathlib import Path

GLYPH_SIZE = 8       # 8 bytes per glyph
GLYPH_WIDTH = 7      # 7 visible pixels per row (bits 0-6)
GLYPH_HEIGHT = 8     # 8 rows per glyph
GLYPHS_PER_FILE = 256
SHPS_FILE_SIZE = GLYPHS_PER_FILE * GLYPH_SIZE  # 2048

# Characters recognized as "pixel on"
ON_CHARS = set('#*XO@')
# Characters recognized as "pixel off"
OFF_CHARS = set('. ')


def parse_tiles_file(text):
    """Parse a .tiles text file into a list of (index, glyph_bytes) tuples.

    Returns list of (int, bytes) where int is the tile index and bytes is
    8 bytes of glyph data.
    """
    tiles = []
    lines = text.split('\n')
    current_index = None
    current_rows = []

    for line in lines:
        stripped = line.rstrip()

        # Comment/header line: "# Tile 0x1A: Name" or "# Tile 26: Name"
        header_match = re.match(
            r'^#\s*[Tt]ile\s+(0x[0-9A-Fa-f]+|\d+)\s*[:\-]?\s*(.*)', stripped
        )
        if header_match:
            # Flush previous tile if any
            if current_index is not None and len(current_rows) == GLYPH_HEIGHT:
                tiles.append((current_index, _rows_to_bytes(current_rows)))
            elif current_index is not None and current_rows:
                raise ValueError(
                    f'Tile 0x{current_index:02X}: expected {GLYPH_HEIGHT} '
                    f'rows, got {len(current_rows)}'
                )
            idx_str = header_match.group(1)
            current_index = int(idx_str, 0)
            current_rows = []
            continue

        # Skip other comment lines (# followed by space or alone, not ###### pixel data)
        if stripped.startswith('# ') or stripped == '#':
            continue

        # Blank line: flush current tile
        if not stripped:
            if current_index is not None and len(current_rows) == GLYPH_HEIGHT:
                tiles.append((current_index, _rows_to_bytes(current_rows)))
                current_index = None
                current_rows = []
            continue

        # Row data line: must be exactly GLYPH_WIDTH characters of on/off
        row_chars = stripped
        if len(row_chars) < GLYPH_WIDTH:
            row_chars = row_chars.ljust(GLYPH_WIDTH, '.')
        elif len(row_chars) > GLYPH_WIDTH:
            row_chars = row_chars[:GLYPH_WIDTH]

        if current_index is None:
            # Auto-assign index if no header was given
            if tiles:
                current_index = tiles[-1][0] + 1
            else:
                current_index = 0
            current_rows = []

        current_rows.append(row_chars)

    # Flush final tile
    if current_index is not None and len(current_rows) == GLYPH_HEIGHT:
        tiles.append((current_index, _rows_to_bytes(current_rows)))
    elif current_index is not None and current_rows:
        raise ValueError(
            f'Tile 0x{current_index:02X}: expected {GLYPH_HEIGHT} '
            f'rows, got {len(current_rows)}'
        )

    return tiles


def _rows_to_bytes(rows):
    """Convert 8 text rows to 8 bytes of glyph data.

    Bit 0 = leftmost pixel, bit 6 = rightmost pixel. Bit 7 always 0.
    """
    result = bytearray(GLYPH_SIZE)
    for r, row in enumerate(rows):
        byte_val = 0
        for c in range(GLYPH_WIDTH):
            ch = row[c] if c < len(row) else '.'
            if ch in ON_CHARS:
                byte_val |= (1 << c)
        result[r] = byte_val
    return bytes(result)


def _byte_to_row(byte_val):
    """Convert a single glyph byte to a 7-character text row."""
    chars = []
    for c in range(GLYPH_WIDTH):
        if byte_val & (1 << c):
            chars.append('#')
        else:
            chars.append('.')
    return ''.join(chars)


def decompile_shps(data, tile_names=None):
    """Convert SHPS binary data to text-art format.

    Args:
        data: Raw SHPS binary (2048 bytes)
        tile_names: Optional dict mapping tile index to name string

    Returns:
        Text-art string
    """
    if len(data) < SHPS_FILE_SIZE:
        raise ValueError(
            f'SHPS file too small: {len(data)} bytes '
            f'(expected {SHPS_FILE_SIZE})'
        )

    lines = []
    for idx in range(GLYPHS_PER_FILE):
        offset = idx * GLYPH_SIZE
        glyph = data[offset:offset + GLYPH_SIZE]

        # Header
        name = ''
        if tile_names and idx in tile_names:
            name = f': {tile_names[idx]}'
        lines.append(f'# Tile 0x{idx:02X}{name}')

        # 8 rows
        for r in range(GLYPH_HEIGHT):
            lines.append(_byte_to_row(glyph[r]))

        lines.append('')  # blank separator

    return '\n'.join(lines)


def compile_to_json(tiles):
    """Convert parsed tiles to JSON format for `shapes import`.

    Args:
        tiles: list of (index, bytes) tuples

    Returns:
        JSON-serializable dict
    """
    tile_list = []
    for idx, glyph_bytes in tiles:
        tile_list.append({
            'index': idx,
            'raw': list(glyph_bytes),
        })
    return {'tiles': [{'frames': tile_list}]}


def compile_to_script(tiles, shps_path='SHPS'):
    """Convert parsed tiles to a shell script of u3edit commands.

    Args:
        tiles: list of (index, bytes) tuples
        shps_path: Path to SHPS file in the script

    Returns:
        Shell script string
    """
    lines = ['#!/usr/bin/env bash',
             '# Generated by tile_compiler.py',
             f'SHPS="${{1:-{shps_path}}}"',
             '']
    for i, (idx, glyph_bytes) in enumerate(tiles):
        hex_str = ' '.join(f'{b:02X}' for b in glyph_bytes)
        backup = ' --backup' if i == 0 else ''
        lines.append(
            f'u3edit shapes edit "$SHPS" --glyph {idx} '
            f'--data "{hex_str}"{backup}'
        )
    return '\n'.join(lines) + '\n'


def cmd_compile(args):
    """Compile a .tiles file to JSON or shell script."""
    text = Path(args.input).read_text(encoding='utf-8')
    tiles = parse_tiles_file(text)

    if not tiles:
        print('No tiles found in input file.', file=sys.stderr)
        sys.exit(1)

    if args.format == 'json':
        output = json.dumps(compile_to_json(tiles), indent=2)
    else:
        shps_path = args.shps_path if args.shps_path else 'SHPS'
        output = compile_to_script(tiles, shps_path)

    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
        print(f'Compiled {len(tiles)} tiles to {args.output}',
              file=sys.stderr)
    else:
        print(output)


def cmd_decompile(args):
    """Decompile a SHPS binary to text-art format."""
    data = Path(args.input).read_bytes()

    # Try to load tile names from constants
    tile_names = None
    try:
        from u3edit.constants import TILES
        tile_names = {}
        for tile_id, (char, name) in TILES.items():
            # Each tile ID covers 4 animation frames
            for frame in range(4):
                glyph_idx = (tile_id + frame) & 0xFF
                suffix = f' (frame {frame})' if frame else ''
                tile_names[glyph_idx] = f'{name}{suffix}'
    except ImportError:
        pass

    text = decompile_shps(data, tile_names)

    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
        print(f'Decompiled {len(data)} bytes to {args.output}',
              file=sys.stderr)
    else:
        print(text)


def main():
    parser = argparse.ArgumentParser(
        description='Tile compiler: convert text-art tiles to/from SHPS binary'
    )
    sub = parser.add_subparsers(dest='command')

    # compile
    p_compile = sub.add_parser(
        'compile', help='Compile .tiles text-art to JSON or shell script'
    )
    p_compile.add_argument('input', help='Input .tiles file')
    p_compile.add_argument(
        '--format', choices=['json', 'script'], default='json',
        help='Output format (default: json)'
    )
    p_compile.add_argument('--output', '-o', help='Output file (default: stdout)')
    p_compile.add_argument('--shps-path', help='SHPS path for script output')

    # decompile
    p_decompile = sub.add_parser(
        'decompile', help='Decompile SHPS binary to text-art'
    )
    p_decompile.add_argument('input', help='Input SHPS binary file')
    p_decompile.add_argument('--output', '-o', help='Output .tiles file (default: stdout)')

    args = parser.parse_args()

    if args.command == 'compile':
        cmd_compile(args)
    elif args.command == 'decompile':
        cmd_decompile(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
