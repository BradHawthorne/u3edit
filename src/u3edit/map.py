"""Ultima III: Exodus - Map Viewer.

Renders MAP* files as text-art maps. Supports overworld (64x64, 4096 bytes)
and dungeon (16x16 per level, 2048 bytes = 8 levels) formats.

Bug fixes from prototype:
  M-1: Replaced 0x00-0x1F paired tile table with full constants.TILES using &0xFC masking.
       Now correctly renders all tile types including town interiors.
"""

import argparse
import os
import sys

from .constants import (
    MAP_NAMES, MAP_LETTERS, MAP_OVERWORLD_SIZE, MAP_DUNGEON_SIZE,
    tile_char, tile_name, TILES, DUNGEON_TILES,
)
from .fileutil import resolve_game_file
from .json_export import export_json


def render_map(data: bytes, width: int, height: int,
               is_dungeon: bool = False, crop: tuple | None = None) -> str:
    """Render a tile map as text art."""
    lines = []
    y_start, y_end = 0, height
    x_start, x_end = 0, width

    if crop:
        x_start, y_start, x_end, y_end = crop
        x_start = max(0, min(x_start, width))
        y_start = max(0, min(y_start, height))
        x_end = max(x_start, min(x_end, width))
        y_end = max(y_start, min(y_end, height))

    # Column header
    header = '     '
    for x in range(x_start, x_end, 10):
        header += f'{x:<10d}'
    lines.append(header)

    for y in range(y_start, y_end):
        row_chars = []
        for x in range(x_start, x_end):
            offset = y * width + x
            if offset < len(data):
                row_chars.append(tile_char(data[offset], is_dungeon))
            else:
                row_chars.append(' ')
        lines.append(f'  {y:3d} {"".join(row_chars)}')
    return '\n'.join(lines)


def map_to_grid(data: bytes, width: int, height: int,
                is_dungeon: bool = False) -> list[list[str]]:
    """Convert map data to a 2D grid of tile names (for JSON)."""
    grid = []
    for y in range(height):
        row = []
        for x in range(width):
            offset = y * width + x
            if offset < len(data):
                row.append(tile_name(data[offset], is_dungeon))
            else:
                row.append('Unknown')
        grid.append(row)
    return grid


def cmd_view(args) -> None:
    with open(args.file, 'rb') as f:
        data = f.read()

    filename = os.path.basename(args.file)
    size = len(data)

    is_dungeon = size <= MAP_DUNGEON_SIZE
    crop = None
    if args.crop:
        parts = args.crop.split(',')
        if len(parts) == 4:
            crop = tuple(int(x) for x in parts)

    if args.json:
        if is_dungeon:
            levels = []
            num_levels = size // 256
            for level in range(num_levels):
                level_data = data[level * 256:(level + 1) * 256]
                levels.append({
                    'level': level + 1,
                    'tiles': map_to_grid(level_data, 16, 16, is_dungeon=True),
                })
            result = {'type': 'dungeon', 'levels': levels}
        else:
            width = 64
            height = size // width
            result = {
                'type': 'overworld' if size == MAP_OVERWORLD_SIZE else 'town',
                'width': width, 'height': height,
                'tiles': map_to_grid(data, width, height),
            }
        export_json(result, args.output)
        return

    print(f"\n=== Ultima III Map: {filename} ({size} bytes) ===\n")

    if is_dungeon:
        num_levels = size // 256
        print(f"  Type: Dungeon ({num_levels} levels, 16x16 each)\n")
        for level in range(num_levels):
            level_data = data[level * 256:(level + 1) * 256]
            print(f"  --- Level {level + 1} ---")
            print(render_map(level_data, 16, 16, is_dungeon=True, crop=crop))
            print()
    else:
        width = 64
        height = size // width
        mtype = 'Overworld' if size == MAP_OVERWORLD_SIZE else 'Town'
        print(f"  Type: {mtype} ({width}x{height})\n")
        print(render_map(data, width, height, crop=crop))

    print()


def cmd_overview(args) -> None:
    """Show summary of all MAP files in a directory."""
    game_dir = args.game_dir

    map_files = []
    for letter in MAP_LETTERS:
        path = resolve_game_file(game_dir, 'MAP', letter)
        if path:
            map_files.append((letter, path))

    if not map_files:
        print(f"Error: No MAP files found in {game_dir}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        result = {}
        for letter, path in map_files:
            size = os.path.getsize(path)
            result[f'MAP{letter}'] = {
                'name': MAP_NAMES.get(letter, 'Unknown'),
                'size': size,
                'type': 'dungeon' if size <= MAP_DUNGEON_SIZE else 'overworld',
            }
        export_json(result, args.output)
        return

    print(f"\n=== Ultima III Maps ({len(map_files)} files) ===\n")
    print(f"  {'File':<8s} {'Name':<30s} {'Size':>6s}  {'Type':<20s} {'Dimensions'}")
    print(f"  {'----':<8s} {'----':<30s} {'----':>6s}  {'----':<20s} {'----------'}")

    for letter, path in map_files:
        size = os.path.getsize(path)
        name = MAP_NAMES.get(letter, 'Unknown')
        if size <= MAP_DUNGEON_SIZE:
            mtype = 'Dungeon'
            dims = f'{size // 256} levels x 16x16'
        else:
            mtype = 'Overworld/Town'
            dims = f'64x{size // 64}'
        print(f"  MAP{letter:<4s} {name:<30s} {size:6d}  {mtype:<20s} {dims}")

    # Mini overworld preview
    if args.preview:
        mapa = None
        for letter, path in map_files:
            if letter == 'A':
                mapa = path
                break
        if mapa:
            with open(mapa, 'rb') as f:
                data = f.read()
            print(f"\n  --- Sosaria Overworld (scaled 4:1) ---\n")
            for y in range(0, 64, 4):
                row = '  '
                for x in range(0, 64, 2):
                    offset = y * 64 + x
                    row += tile_char(data[offset]) if offset < len(data) else ' '
                print(row)

    print()


def cmd_legend(args) -> None:
    """Print tile legend."""
    print("\n=== Tile Legend ===\n")
    print("  Overworld/Town Tiles:")
    for val in sorted(TILES.keys()):
        ch, name = TILES[val]
        print(f"    {ch}  = {name} (${val:02X})")

    if not getattr(args, 'json', False):
        print("\n  Dungeon Tiles:")
        for val in sorted(DUNGEON_TILES.keys()):
            ch, name = DUNGEON_TILES[val]
            print(f"    {ch}  = {name} (${val:02X})")
    print()


def register_parser(subparsers) -> None:
    """Register map subcommands on a CLI subparser group."""
    p = subparsers.add_parser('map', help='Map viewer')
    sub = p.add_subparsers(dest='map_command')

    p_view = sub.add_parser('view', help='View a map file')
    p_view.add_argument('file', help='MAP file path')
    p_view.add_argument('--crop', help='Crop region: x1,y1,x2,y2')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_over = sub.add_parser('overview', help='Overview of all maps')
    p_over.add_argument('game_dir', help='GAME directory containing MAP* files')
    p_over.add_argument('--preview', action='store_true', help='Show scaled overworld preview')
    p_over.add_argument('--json', action='store_true', help='Output as JSON')
    p_over.add_argument('--output', '-o', help='Output file (for --json)')

    sub.add_parser('legend', help='Print tile legend')


def dispatch(args) -> None:
    """Dispatch map subcommand."""
    if args.map_command == 'view':
        cmd_view(args)
    elif args.map_command == 'overview':
        cmd_overview(args)
    elif args.map_command == 'legend':
        cmd_legend(args)
    else:
        print("Usage: u3edit map {view|overview|legend} ...", file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Map Viewer')
    sub = parser.add_subparsers(dest='map_command')

    p_view = sub.add_parser('view', help='View a map file')
    p_view.add_argument('file', help='MAP file path')
    p_view.add_argument('--crop', help='Crop region: x1,y1,x2,y2')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    p_over = sub.add_parser('overview', help='Overview of all maps')
    p_over.add_argument('game_dir', help='GAME directory')
    p_over.add_argument('--preview', action='store_true')
    p_over.add_argument('--json', action='store_true')
    p_over.add_argument('--output', '-o')

    sub.add_parser('legend', help='Print tile legend')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
