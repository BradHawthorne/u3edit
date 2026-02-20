"""Ultima III: Exodus - Special Location Viewer.

BRND/SHRN/FNTN/TIME files: 128 bytes each, loaded at $9900.
First 121 bytes = 11x11 tile map (same grid as CON files).
Trailing 7 bytes (121-127) are unused padding — engine only reads the
tile grid. The padding contains residual disk data (text fragments like
"DECFOOD", "CLRBD", "! THAT'" from adjacent memory at creation time).
Preserved for round-trip fidelity but not meaningful game data.
"""

SPECIAL_META_OFFSET = 121  # Offset of 7 trailing padding bytes
SPECIAL_META_SIZE = 7

import argparse
import json
import os
import sys

from .constants import (
    SPECIAL_NAMES, SPECIAL_FILE_SIZE,
    SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT, SPECIAL_MAP_TILES,
    tile_char, TILE_CHARS_REVERSE,
)
from .fileutil import resolve_single_file, backup_file, hex_int
from .json_export import export_json


def get_trailing_bytes(data: bytes) -> list[int]:
    """Extract the 7 trailing padding bytes after the 11x11 tile map.

    These bytes are unused by the engine (disk residue) but preserved
    for round-trip fidelity.
    """
    result = []
    for i in range(SPECIAL_META_SIZE):
        off = SPECIAL_META_OFFSET + i
        result.append(data[off] if off < len(data) else 0)
    return result


# Backward compatibility alias
get_metadata = get_trailing_bytes


def render_special_map(data: bytes) -> str:
    """Render 11x11 special location map as text art."""
    lines = ['     ' + ''.join(f'{x % 10}' for x in range(SPECIAL_MAP_WIDTH))]
    for y in range(SPECIAL_MAP_HEIGHT):
        row = []
        for x in range(SPECIAL_MAP_WIDTH):
            offset = y * SPECIAL_MAP_WIDTH + x
            if offset < len(data):
                row.append(tile_char(data[offset]))
            else:
                row.append(' ')
        lines.append(f'  {y:2d}  {"".join(row)}')

    # Show trailing padding bytes if non-zero (disk residue, not game data)
    trailing = get_trailing_bytes(data)
    if any(trailing):
        hex_str = ' '.join(f'{b:02X}' for b in trailing)
        lines.append(f'  Trailing padding (0x79): {hex_str}')

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
                                for x in range(SPECIAL_MAP_WIDTH)
                                if y * SPECIAL_MAP_WIDTH + x < len(data)]
                               for y in range(SPECIAL_MAP_HEIGHT)
                               if y * SPECIAL_MAP_WIDTH < len(data)],
                    'trailing_bytes': get_trailing_bytes(data),
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
                'trailing_bytes': get_trailing_bytes(data),
            }
            export_json(result, args.output)
            return

        print(f"\n=== Special Location: {filename} - {name} ({len(data)} bytes) ===\n")
        print(render_special_map(data))
        print()


def _has_cli_edit_args(args) -> bool:
    """Check if any CLI editing flags were provided."""
    return getattr(args, 'tile', None) is not None


def cmd_edit(args) -> None:
    """Edit a special location via CLI args or TUI fallback."""
    if not _has_cli_edit_args(args):
        # No CLI args — launch TUI editor
        from .tui import require_prompt_toolkit
        require_prompt_toolkit()
        from .tui.special_editor import SpecialEditor

        with open(args.file, 'rb') as f:
            data = f.read()

        editor = SpecialEditor(args.file, data)
        editor.run()
        return

    # CLI editing mode
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)
    changes = 0

    # --tile X Y VALUE
    if getattr(args, 'tile', None) is not None:
        tx, ty, tval = args.tile
        if not (0 <= tx < SPECIAL_MAP_WIDTH and 0 <= ty < SPECIAL_MAP_HEIGHT):
            print(f"Error: tile ({tx}, {ty}) out of bounds (0-{SPECIAL_MAP_WIDTH - 1})",
                  file=sys.stderr)
            sys.exit(1)
        if not (0 <= tval <= 255):
            print(f"Error: tile value {tval} out of range (0-255)", file=sys.stderr)
            sys.exit(1)
        offset = ty * SPECIAL_MAP_WIDTH + tx
        old_val = data[offset]
        data[offset] = tval
        print(f"Tile ({tx}, {ty}): ${old_val:02X} -> ${tval:02X}")
        changes += 1

    if changes == 0:
        print("No changes specified.")
        return

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = getattr(args, 'output', None) or args.file
    if do_backup and (not getattr(args, 'output', None) or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Saved to {output}")


def cmd_import(args) -> None:
    """Import a special location map from JSON."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())
    do_backup = getattr(args, 'backup', False)
    dry_run = getattr(args, 'dry_run', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    tile_changes = 0
    tiles = jdata.get('tiles', [])
    for y, row in enumerate(tiles[:SPECIAL_MAP_HEIGHT]):
        for x, ch in enumerate(row[:SPECIAL_MAP_WIDTH]):
            offset = y * SPECIAL_MAP_WIDTH + x
            if offset < len(data):
                new_val = TILE_CHARS_REVERSE.get(ch, 0x20)
                if data[offset] != new_val:
                    tile_changes += 1
                data[offset] = new_val

    # Import trailing padding bytes (accept both old and new key)
    trailing = jdata.get('trailing_bytes', jdata.get('metadata', []))
    for i, b in enumerate(trailing[:SPECIAL_META_SIZE]):
        off = SPECIAL_META_OFFSET + i
        if off < len(data):
            data[off] = b

    print(f"Import: {tile_changes} tile(s) changed")

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Imported special map to {output}")


def _add_special_write_args(p) -> None:
    """Add common write arguments for special edit commands."""
    p.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p.add_argument('--dry-run', action='store_true', help='Show changes without writing')


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('special', help='Special location viewer/editor')
    sub = p.add_subparsers(dest='special_command')

    p_view = sub.add_parser('view', help='View special locations')
    p_view.add_argument('path', help='Special file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Edit a special location (CLI or TUI)')
    p_edit.add_argument('file', help='Special location file path')
    p_edit.add_argument('--tile', type=hex_int, nargs=3, metavar=('X', 'Y', 'VALUE'),
                        help='Set tile at (X, Y) to VALUE')
    _add_special_write_args(p_edit)

    p_import = sub.add_parser('import', help='Import special map from JSON')
    p_import.add_argument('file', help='Special location file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true', help='Show changes without writing')


def dispatch(args) -> None:
    cmd = args.special_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: u3edit special {view|edit|import} ...", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Special Location Viewer')
    sub = parser.add_subparsers(dest='special_command')

    p_view = sub.add_parser('view', help='View special locations')
    p_view.add_argument('path', help='Special file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Edit a special location (CLI or TUI)')
    p_edit.add_argument('file', help='Special location file path')
    p_edit.add_argument('--tile', type=hex_int, nargs=3, metavar=('X', 'Y', 'VALUE'),
                        help='Set tile at (X, Y) to VALUE')
    _add_special_write_args(p_edit)

    p_import = sub.add_parser('import', help='Import special map from JSON')
    p_import.add_argument('file', help='Special location file path')
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
