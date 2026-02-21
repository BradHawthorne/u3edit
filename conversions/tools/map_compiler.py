#!/usr/bin/env python3
"""Map Compiler — Convert text-art maps to/from game binary format.

Source format (.map files):
    # MAPA - Sosaria (64x64)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ~~..............^^..............................................~~
    ~~...T..T...^^.......@.........................................~~

Uses display characters from the TILES / DUNGEON_TILES tables in constants.py.

Compile: text-art -> JSON for `u3edit map import`
Decompile: binary map -> text-art for editing
"""

import argparse
import json
import sys
from pathlib import Path

# Overworld map dimensions
OVERWORLD_WIDTH = 64
OVERWORLD_HEIGHT = 64
OVERWORLD_SIZE = OVERWORLD_WIDTH * OVERWORLD_HEIGHT  # 4096

# Dungeon map dimensions
DUNGEON_WIDTH = 16
DUNGEON_HEIGHT = 16
DUNGEON_LEVEL_SIZE = DUNGEON_WIDTH * DUNGEON_HEIGHT  # 256
DUNGEON_LEVELS = 8
DUNGEON_SIZE = DUNGEON_LEVEL_SIZE * DUNGEON_LEVELS  # 2048


def _load_tile_tables():
    """Load tile character tables from constants.py or use built-in defaults."""
    try:
        from u3edit.constants import (
            TILE_CHARS_REVERSE, DUNGEON_TILE_CHARS_REVERSE,
            TILES, DUNGEON_TILES,
        )
        # Build char->byte for overworld
        overworld_reverse = dict(TILE_CHARS_REVERSE)
        # Build byte->char for overworld
        overworld_forward = {tile_id: ch for tile_id, (ch, _) in TILES.items()}
        # Dungeon
        dungeon_reverse = dict(DUNGEON_TILE_CHARS_REVERSE)
        dungeon_forward = {tile_id: ch for tile_id, (ch, _) in DUNGEON_TILES.items()}
        return (overworld_forward, overworld_reverse,
                dungeon_forward, dungeon_reverse)
    except ImportError:
        # Minimal fallback
        return ({}, {}, {}, {})


def parse_map_file(text, is_dungeon=False):
    """Parse a .map text file into grid data.

    Args:
        text: Text content of the .map file
        is_dungeon: If True, parse as dungeon format (16x16, 8 levels)

    Returns:
        For overworld: list of list of tile bytes (64x64)
        For dungeon: list of 8 levels, each a list of list of tile bytes (16x16)
    """
    _, overworld_reverse, _, dungeon_reverse = _load_tile_tables()
    char_map = dungeon_reverse if is_dungeon else overworld_reverse

    lines = text.split('\n')
    grid_lines = []
    level_grids = []
    current_level = []

    for line in lines:
        stripped = line.rstrip()

        # Comment or header
        if stripped.startswith('#') or not stripped:
            # Level separator for dungeons
            if is_dungeon and current_level:
                if stripped.startswith('# Level') or stripped.startswith('# ---'):
                    level_grids.append(current_level)
                    current_level = []
            continue

        # Parse row of tile characters
        row = []
        for ch in stripped:
            if ch in char_map:
                row.append(char_map[ch])
            else:
                row.append(0)  # Default to first tile type

        if is_dungeon:
            width = DUNGEON_WIDTH
        else:
            width = OVERWORLD_WIDTH

        # Pad or trim to correct width
        if len(row) < width:
            row.extend([0] * (width - len(row)))
        elif len(row) > width:
            row = row[:width]

        current_level.append(row)

    if is_dungeon:
        # Flush final level
        if current_level:
            level_grids.append(current_level)

        # Pad to 8 levels
        while len(level_grids) < DUNGEON_LEVELS:
            empty_level = [[0] * DUNGEON_WIDTH for _ in range(DUNGEON_HEIGHT)]
            level_grids.append(empty_level)

        # Pad each level to correct height
        for level in level_grids:
            while len(level) < DUNGEON_HEIGHT:
                level.append([0] * DUNGEON_WIDTH)

        return level_grids
    else:
        grid_lines = current_level if not grid_lines else grid_lines
        if not grid_lines:
            grid_lines = current_level

        # Pad to correct height
        while len(grid_lines) < OVERWORLD_HEIGHT:
            grid_lines.append([0] * OVERWORLD_WIDTH)

        return grid_lines


def grid_to_json(grid, is_dungeon=False):
    """Convert parsed grid to JSON for `u3edit map import`.

    Args:
        grid: Overworld grid (list of rows) or dungeon levels (list of levels)
        is_dungeon: Whether this is dungeon format

    Returns:
        JSON-serializable dict
    """
    if is_dungeon:
        # Output format matches map.py cmd_import expectations:
        # {"levels": [{"level": 1, "tiles": [["#",".",...],...]}, ...]}
        _, _, dungeon_forward, _ = _load_tile_tables()
        levels = []
        for level_idx, level_grid in enumerate(grid):
            tile_rows = []
            for row in level_grid:
                tile_row = []
                for tile_byte in row:
                    ch = dungeon_forward.get(tile_byte & 0x0F, '?')
                    tile_row.append(ch)
                tile_rows.append(tile_row)
            levels.append({'level': level_idx + 1, 'tiles': tile_rows})
        return {'levels': levels}
    else:
        # Flat grid format - export as character grid
        # Key is 'tiles' to match map.py cmd_import expectations
        overworld_forward, _, _, _ = _load_tile_tables()

        rows = []
        for row in grid:
            row_chars = []
            for tile_byte in row:
                ch = overworld_forward.get(tile_byte & 0xFC, '?')
                row_chars.append(ch)
            rows.append(''.join(row_chars))
        return {'tiles': rows}


def decompile_map(data, is_dungeon=False):
    """Convert binary map data to text-art format.

    Args:
        data: Raw binary map data
        is_dungeon: Whether this is dungeon format

    Returns:
        Text-art string
    """
    overworld_forward, _, dungeon_forward, _ = _load_tile_tables()

    lines = []

    if is_dungeon:
        if len(data) < DUNGEON_SIZE:
            raise ValueError(
                f'Dungeon file too small: {len(data)} bytes '
                f'(expected {DUNGEON_SIZE})'
            )
        for level in range(DUNGEON_LEVELS):
            lines.append(f'# Level {level}')
            for y in range(DUNGEON_HEIGHT):
                offset = level * DUNGEON_LEVEL_SIZE + y * DUNGEON_WIDTH
                row_chars = []
                for x in range(DUNGEON_WIDTH):
                    byte_val = data[offset + x]
                    ch = dungeon_forward.get(byte_val & 0x0F, '?')
                    row_chars.append(ch)
                lines.append(''.join(row_chars))
            lines.append('')
    else:
        if len(data) < OVERWORLD_SIZE:
            raise ValueError(
                f'Map file too small: {len(data)} bytes '
                f'(expected {OVERWORLD_SIZE})'
            )
        lines.append('# Overworld map')
        for y in range(OVERWORLD_HEIGHT):
            offset = y * OVERWORLD_WIDTH
            row_chars = []
            for x in range(OVERWORLD_WIDTH):
                byte_val = data[offset + x]
                ch = overworld_forward.get(byte_val & 0xFC, '?')
                row_chars.append(ch)
            lines.append(''.join(row_chars))

    return '\n'.join(lines) + '\n'


def cmd_compile(args):
    """Compile a .map file to JSON."""
    text = Path(args.input).read_text(encoding='utf-8')
    grid = parse_map_file(text, is_dungeon=args.dungeon)
    result = grid_to_json(grid, is_dungeon=args.dungeon)

    output = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
        print(f'Compiled map to {args.output}', file=sys.stderr)
    else:
        print(output)


def cmd_decompile(args):
    """Decompile a binary map to text-art format."""
    data = Path(args.input).read_bytes()
    is_dungeon = args.dungeon or len(data) == DUNGEON_SIZE

    text = decompile_map(data, is_dungeon=is_dungeon)

    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
        print(f'Decompiled {len(data)} bytes to {args.output}',
              file=sys.stderr)
    else:
        print(text)


def main():
    parser = argparse.ArgumentParser(
        description='Map compiler: convert text-art maps to/from game binary'
    )
    sub = parser.add_subparsers(dest='command')

    # compile
    p_compile = sub.add_parser(
        'compile', help='Compile .map text-art to JSON for map import'
    )
    p_compile.add_argument('input', help='Input .map file')
    p_compile.add_argument('--output', '-o', help='Output JSON file (default: stdout)')
    p_compile.add_argument(
        '--dungeon', action='store_true',
        help='Parse as dungeon format (16x16 x 8 levels)'
    )

    # decompile
    p_decompile = sub.add_parser(
        'decompile', help='Decompile binary map to text-art'
    )
    p_decompile.add_argument('input', help='Input binary map file')
    p_decompile.add_argument('--output', '-o', help='Output .map file (default: stdout)')
    p_decompile.add_argument(
        '--dungeon', action='store_true',
        help='Decompile as dungeon format (auto-detected from file size)'
    )

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
