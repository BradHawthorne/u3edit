"""Ultima III: Exodus - Map Viewer.

Renders MAP* files as text-art maps. Supports overworld (64x64, 4096 bytes)
and dungeon (16x16 per level, 2048 bytes = 8 levels) formats.

Bug fixes from prototype:
  M-1: Replaced 0x00-0x1F paired tile table with full constants.TILES using &0xFC masking.
       Now correctly renders all tile types including town interiors.
"""

import argparse
import json
import os
import sys

from .constants import (
    MAP_NAMES, MAP_LETTERS, MAP_OVERWORLD_SIZE, MAP_DUNGEON_SIZE,
    tile_char, tile_name, TILES, DUNGEON_TILES,
    TILE_CHARS_REVERSE, DUNGEON_TILE_CHARS_REVERSE,
    TILE_NAMES_REVERSE, DUNGEON_TILE_NAMES_REVERSE,
)
from .fileutil import resolve_game_file, backup_file, hex_int
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


def cmd_edit(args) -> None:
    """Launch TUI map editor."""
    from .tui import require_prompt_toolkit
    require_prompt_toolkit()
    from .tui.map_editor import MapEditor

    with open(args.file, 'rb') as f:
        data = f.read()

    is_dungeon = len(data) <= MAP_DUNGEON_SIZE
    editor = MapEditor(args.file, data, is_dungeon)
    editor.run()


def _get_map_slice(data: bytearray, is_dungeon: bool, level: int | None):
    """Return (slice_data, offset, width, height) for the working region."""
    if is_dungeon:
        lvl = level if level is not None else 0
        base = lvl * 256
        return data[base:base + 256], base, 16, 16
    return data, 0, 64, len(data) // 64


def cmd_set(args) -> None:
    """Set a single tile at (x, y)."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())
    is_dungeon = len(data) <= MAP_DUNGEON_SIZE
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)

    _, base, width, height = _get_map_slice(data, is_dungeon, getattr(args, 'level', None))

    if not (0 <= args.x < width and 0 <= args.y < height):
        print(f"Error: ({args.x}, {args.y}) out of bounds ({width}x{height})", file=sys.stderr)
        sys.exit(1)

    offset = base + args.y * width + args.x
    old_val = data[offset]
    data[offset] = args.tile
    print(f"Set ({args.x}, {args.y}): ${old_val:02X} -> ${args.tile:02X}")

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Saved to {output}")


def cmd_fill(args) -> None:
    """Fill a rectangular region with a tile value."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())
    is_dungeon = len(data) <= MAP_DUNGEON_SIZE
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)

    _, base, width, height = _get_map_slice(data, is_dungeon, getattr(args, 'level', None))

    x1 = max(0, min(args.x1, width - 1))
    y1 = max(0, min(args.y1, height - 1))
    x2 = max(x1, min(args.x2, width - 1))
    y2 = max(y1, min(args.y2, height - 1))

    count = 0
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            data[base + y * width + x] = args.tile
            count += 1
    print(f"Filled {count} tiles in ({x1},{y1})-({x2},{y2}) with ${args.tile:02X}")

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Saved to {output}")


def cmd_replace(args) -> None:
    """Replace all occurrences of one tile with another."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())
    is_dungeon = len(data) <= MAP_DUNGEON_SIZE
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)
    from_tile = getattr(args, 'from_tile')
    to_tile = getattr(args, 'to_tile')

    _, base, width, height = _get_map_slice(data, is_dungeon, getattr(args, 'level', None))

    count = 0
    for y in range(height):
        for x in range(width):
            offset = base + y * width + x
            if data[offset] == from_tile:
                data[offset] = to_tile
                count += 1
    print(f"Replaced {count} tiles: ${from_tile:02X} -> ${to_tile:02X}")

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Saved to {output}")


def cmd_find(args) -> None:
    """Find all locations of a tile type."""
    with open(args.file, 'rb') as f:
        data = f.read()
    is_dungeon = len(data) <= MAP_DUNGEON_SIZE

    _, base, width, height = _get_map_slice(data, is_dungeon, getattr(args, 'level', None))

    locations = []
    for y in range(height):
        for x in range(width):
            offset = base + y * width + x
            if data[offset] == args.tile:
                locations.append((x, y))

    if getattr(args, 'json', False):
        result = {
            'tile': args.tile,
            'tile_name': tile_name(args.tile, is_dungeon),
            'count': len(locations),
            'locations': [{'x': x, 'y': y} for x, y in locations],
        }
        export_json(result, getattr(args, 'output', None))
        return

    name = tile_name(args.tile, is_dungeon)
    print(f"\nTile ${args.tile:02X} ({name}): {len(locations)} found\n")
    for x, y in locations:
        print(f"  ({x}, {y})")
    print()


def cmd_import(args) -> None:
    """Import a map from JSON (tile char grid)."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())
    is_dungeon = len(data) <= MAP_DUNGEON_SIZE
    do_backup = getattr(args, 'backup', False)
    dry_run = getattr(args, 'dry_run', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    char_reverse = DUNGEON_TILE_CHARS_REVERSE if is_dungeon else TILE_CHARS_REVERSE
    name_reverse = DUNGEON_TILE_NAMES_REVERSE if is_dungeon else TILE_NAMES_REVERSE
    default_tile = 0 if is_dungeon else 0x04

    def resolve_tile(name):
        """Resolve a tile name or display char to a byte value."""
        if len(name) == 1:
            return char_reverse.get(name, default_tile)
        return name_reverse.get(name.lower(), default_tile)

    if is_dungeon and 'levels' in jdata:
        for level_data in jdata['levels']:
            lvl = level_data.get('level', 1) - 1
            if lvl < 0 or lvl >= len(data) // 256:
                continue
            tiles = level_data.get('tiles', [])
            base = lvl * 256
            for y, row in enumerate(tiles[:16]):
                for x, name in enumerate(row[:16]):
                    offset = base + y * 16 + x
                    if offset < len(data):
                        data[offset] = resolve_tile(name)
    else:
        tiles = jdata.get('tiles', [])
        width = jdata.get('width', 64)
        # Validate width against file size
        expected_height = len(data) // width if width > 0 else 0
        if width > 0 and len(data) % width != 0:
            print(f"  Warning: file size {len(data)} not divisible by "
                  f"width {width}", file=sys.stderr)
        for y, row in enumerate(tiles):
            for x, name in enumerate(row):
                offset = y * width + x
                if offset < len(data):
                    data[offset] = resolve_tile(name)

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Imported map to {output}")


def _add_map_write_args(p) -> None:
    """Add common write arguments for map edit commands."""
    p.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    p.add_argument('--level', type=int, help='Dungeon level (0-7, default: 0)')


def register_parser(subparsers) -> None:
    """Register map subcommands on a CLI subparser group."""
    p = subparsers.add_parser('map', help='Map viewer/editor')
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

    p_edit = sub.add_parser('edit', help='Edit a map (TUI)')
    p_edit.add_argument('file', help='MAP file path')

    p_set = sub.add_parser('set', help='Set a single tile')
    p_set.add_argument('file', help='MAP file path')
    p_set.add_argument('--x', type=int, required=True, help='X coordinate')
    p_set.add_argument('--y', type=int, required=True, help='Y coordinate')
    p_set.add_argument('--tile', type=hex_int, required=True, help='Tile byte value')
    _add_map_write_args(p_set)

    p_fill = sub.add_parser('fill', help='Fill a rectangular region')
    p_fill.add_argument('file', help='MAP file path')
    p_fill.add_argument('--x1', type=int, required=True, help='Start X')
    p_fill.add_argument('--y1', type=int, required=True, help='Start Y')
    p_fill.add_argument('--x2', type=int, required=True, help='End X')
    p_fill.add_argument('--y2', type=int, required=True, help='End Y')
    p_fill.add_argument('--tile', type=hex_int, required=True, help='Tile byte value')
    _add_map_write_args(p_fill)

    p_replace = sub.add_parser('replace', help='Replace all occurrences of a tile')
    p_replace.add_argument('file', help='MAP file path')
    p_replace.add_argument('--from', type=hex_int, required=True, dest='from_tile', help='Tile to replace')
    p_replace.add_argument('--to', type=hex_int, required=True, dest='to_tile', help='Replacement tile')
    _add_map_write_args(p_replace)

    p_find = sub.add_parser('find', help='Find all locations of a tile type')
    p_find.add_argument('file', help='MAP file path')
    p_find.add_argument('--tile', type=hex_int, required=True, help='Tile byte value to find')
    p_find.add_argument('--level', type=int, help='Dungeon level (0-7)')
    p_find.add_argument('--json', action='store_true', help='Output as JSON')
    p_find.add_argument('--output', '-o', help='Output file (for --json)')

    p_import = sub.add_parser('import', help='Import map from JSON')
    p_import.add_argument('file', help='MAP file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true', help='Show changes without writing')


def dispatch(args) -> None:
    """Dispatch map subcommand."""
    cmd = args.map_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'overview':
        cmd_overview(args)
    elif cmd == 'legend':
        cmd_legend(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'set':
        cmd_set(args)
    elif cmd == 'fill':
        cmd_fill(args)
    elif cmd == 'replace':
        cmd_replace(args)
    elif cmd == 'find':
        cmd_find(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: u3edit map {view|overview|legend|edit|set|fill|replace|find|import} ...",
              file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Map Viewer')
    sub = parser.add_subparsers(dest='map_command')

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

    p_edit = sub.add_parser('edit', help='Edit a map (TUI)')
    p_edit.add_argument('file', help='MAP file path')

    p_set = sub.add_parser('set', help='Set a single tile')
    p_set.add_argument('file', help='MAP file path')
    p_set.add_argument('--x', type=int, required=True, help='X coordinate')
    p_set.add_argument('--y', type=int, required=True, help='Y coordinate')
    p_set.add_argument('--tile', type=hex_int, required=True, help='Tile byte value')
    _add_map_write_args(p_set)

    p_fill = sub.add_parser('fill', help='Fill a rectangular region')
    p_fill.add_argument('file', help='MAP file path')
    p_fill.add_argument('--x1', type=int, required=True, help='Start X')
    p_fill.add_argument('--y1', type=int, required=True, help='Start Y')
    p_fill.add_argument('--x2', type=int, required=True, help='End X')
    p_fill.add_argument('--y2', type=int, required=True, help='End Y')
    p_fill.add_argument('--tile', type=hex_int, required=True, help='Tile byte value')
    _add_map_write_args(p_fill)

    p_replace = sub.add_parser('replace', help='Replace all occurrences of a tile')
    p_replace.add_argument('file', help='MAP file path')
    p_replace.add_argument('--from', type=hex_int, required=True, dest='from_tile',
                           help='Tile to replace')
    p_replace.add_argument('--to', type=hex_int, required=True, dest='to_tile',
                           help='Replacement tile')
    _add_map_write_args(p_replace)

    p_find = sub.add_parser('find', help='Find all locations of a tile type')
    p_find.add_argument('file', help='MAP file path')
    p_find.add_argument('--tile', type=hex_int, required=True, help='Tile byte value to find')
    p_find.add_argument('--level', type=int, help='Dungeon level (0-7)')
    p_find.add_argument('--json', action='store_true', help='Output as JSON')
    p_find.add_argument('--output', '-o', help='Output file (for --json)')

    p_import = sub.add_parser('import', help='Import map from JSON')
    p_import.add_argument('file', help='MAP file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true',
                          help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true',
                          help='Show changes without writing')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
