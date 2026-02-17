"""Ultima III: Exodus - Special Location Viewer.

BRND/SHRN/FNTN/TIME files: 128 bytes each.
First 121 bytes = 11x11 tile map, remaining 7 bytes = metadata.
"""

import argparse
import os
import sys

from .constants import (
    SPECIAL_NAMES, SPECIAL_FILE_SIZE,
    SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT, SPECIAL_MAP_TILES,
    tile_char,
)
from .fileutil import resolve_single_file
from .json_export import export_json


def render_special_map(data: bytes) -> str:
    """Render 11x11 special location map as text art."""
    lines = ['     ' + ''.join(f'{x}' for x in range(SPECIAL_MAP_WIDTH))]
    for y in range(SPECIAL_MAP_HEIGHT):
        row = []
        for x in range(SPECIAL_MAP_WIDTH):
            offset = y * SPECIAL_MAP_WIDTH + x
            if offset < len(data):
                row.append(tile_char(data[offset]))
            else:
                row.append(' ')
        lines.append(f'  {y:2d}  {"".join(row)}')
    return '\n'.join(lines)


def cmd_view(args) -> None:
    path_or_dir = args.path

    if os.path.isdir(path_or_dir):
        found = []
        for prefix in SPECIAL_NAMES:
            path = resolve_single_file(path_or_dir, prefix)
            if path:
                found.append((prefix, path))

        if not found:
            print(f"Error: No special location files found in {path_or_dir}",
                  file=sys.stderr)
            sys.exit(1)

        if args.json:
            result = {}
            for prefix, path in found:
                with open(path, 'rb') as f:
                    data = f.read()
                result[prefix] = {
                    'name': SPECIAL_NAMES.get(prefix, 'Unknown'),
                    'tiles': [[tile_char(data[y * SPECIAL_MAP_WIDTH + x])
                                for x in range(SPECIAL_MAP_WIDTH)]
                               for y in range(SPECIAL_MAP_HEIGHT)
                               if y * SPECIAL_MAP_WIDTH < len(data)],
                }
            export_json(result, args.output)
            return

        print(f"\n=== Ultima III Special Locations ({len(found)} files) ===\n")
        for prefix, path in found:
            name = SPECIAL_NAMES.get(prefix, 'Unknown')
            with open(path, 'rb') as f:
                data = f.read()
            print(f"  {prefix} - {name} ({len(data)} bytes)")
            print(render_special_map(data))
            print()
    else:
        with open(path_or_dir, 'rb') as f:
            data = f.read()
        filename = os.path.basename(path_or_dir)
        # Try to identify from filename
        prefix = filename.split('#')[0].upper()
        name = SPECIAL_NAMES.get(prefix, 'Unknown')

        if args.json:
            result = {
                'file': filename, 'name': name,
                'tiles': [[tile_char(data[y * SPECIAL_MAP_WIDTH + x])
                            for x in range(SPECIAL_MAP_WIDTH)]
                           for y in range(SPECIAL_MAP_HEIGHT)
                           if y * SPECIAL_MAP_WIDTH < len(data)],
            }
            export_json(result, args.output)
            return

        print(f"\n=== Special Location: {filename} - {name} ({len(data)} bytes) ===\n")
        print(render_special_map(data))
        print()


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('special', help='Special location viewer')
    sub = p.add_subparsers(dest='special_command')

    p_view = sub.add_parser('view', help='View special locations')
    p_view.add_argument('path', help='Special file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')


def dispatch(args) -> None:
    if args.special_command == 'view':
        cmd_view(args)
    else:
        print("Usage: u3edit special view ...", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Special Location Viewer')
    sub = parser.add_subparsers(dest='special_command')

    p_view = sub.add_parser('view', help='View special locations')
    p_view.add_argument('path', help='Special file or GAME directory')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
