"""Ultima III: Exodus - Dungeon Drawing Data Viewer/Editor.

DDRW file: 1792 bytes loaded at $1800.
Contains dungeon wall/corridor rendering data for the 3D perspective view.
"""

import argparse
import json
import os
import sys

from .constants import DDRW_FILE_SIZE
from .fileutil import resolve_single_file, backup_file, hex_int
from .json_export import export_json

# ============================================================================
# Constants
# ============================================================================

DDRW_LOAD_ADDR = 0x1800

# Structured regions within DDRW (offsets relative to file start)
# Perspective projection vectors: 32 slots at offset $F0
DDRW_VECTOR_OFFSET = 0x00F0
DDRW_VECTOR_COUNT = 32
DDRW_VECTOR_SIZE = 1  # Each slot is 1 byte

# Tile rendering records: 7 bytes each at offset $400 ($1C00 in memory)
DDRW_TILE_OFFSET = 0x0400
DDRW_TILE_RECORD_SIZE = 7
DDRW_TILE_RECORD_FIELDS = [
    'col_start', 'col_end', 'step', 'flags',
    'bright_lo', 'bright_hi', 'reserved',
]


# ============================================================================
# Structured parsing
# ============================================================================

def parse_vectors(data: bytes) -> list[int]:
    """Parse perspective projection vector slots."""
    result = []
    for i in range(DDRW_VECTOR_COUNT):
        off = DDRW_VECTOR_OFFSET + i
        if off < len(data):
            result.append(data[off])
        else:
            result.append(0)
    return result


def parse_tile_records(data: bytes) -> list[dict]:
    """Parse tile rendering records at offset $400.

    Each record is 7 bytes:
      col_start, col_end, step, flags, bright_lo, bright_hi, reserved
    """
    records = []
    i = DDRW_TILE_OFFSET
    while i + DDRW_TILE_RECORD_SIZE <= len(data):
        rec = {}
        for j, field in enumerate(DDRW_TILE_RECORD_FIELDS):
            rec[field] = data[i + j]
        rec['offset'] = i
        records.append(rec)
        i += DDRW_TILE_RECORD_SIZE
    return records


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_view(args) -> None:
    """View dungeon drawing data."""
    path_or_dir = args.path

    if os.path.isdir(path_or_dir):
        path = resolve_single_file(path_or_dir, 'DDRW')
        if not path:
            print(f"Error: No DDRW file found in {path_or_dir}",
                  file=sys.stderr)
            sys.exit(1)
    else:
        path = path_or_dir

    with open(path, 'rb') as f:
        data = f.read()

    filename = os.path.basename(path)

    if args.json:
        result = {
            'file': filename,
            'size': len(data),
            'load_addr': f'${DDRW_LOAD_ADDR:04X}',
            'vectors': parse_vectors(data),
            'tile_records': parse_tile_records(data),
            'raw': list(data),
        }
        export_json(result, args.output)
        return

    print(f"\n=== {filename}: Dungeon Drawing Data "
          f"({len(data)} bytes, ${DDRW_LOAD_ADDR:04X}) ===\n")

    # Perspective vectors
    vectors = parse_vectors(data)
    non_zero = sum(1 for v in vectors if v)
    if non_zero:
        print(f"  Perspective vectors (offset $F0, {DDRW_VECTOR_COUNT} slots, "
              f"{non_zero} active):")
        for i in range(0, DDRW_VECTOR_COUNT, 8):
            vals = vectors[i:i + 8]
            hex_vals = ' '.join(f'{v:02X}' for v in vals)
            print(f"    [{i:2d}-{i+len(vals)-1:2d}] {hex_vals}")
        print()

    # Tile records
    if DDRW_TILE_OFFSET < len(data):
        records = parse_tile_records(data)
        if records:
            print(f"  Tile records (offset $400, {len(records)} records "
                  f"x {DDRW_TILE_RECORD_SIZE} bytes):")
            print(f"    {'#':>3s}  {'Start':>5s} {'End':>5s} {'Step':>4s} "
                  f"{'Flags':>5s} {'BrLo':>4s} {'BrHi':>4s} {'Rsv':>3s}")
            for idx, rec in enumerate(records):
                if not any(rec[f] for f in DDRW_TILE_RECORD_FIELDS):
                    continue  # Skip all-zero records
                print(f"    {idx:3d}  "
                      f"${rec['col_start']:02X}  "
                      f"${rec['col_end']:02X}  "
                      f"${rec['step']:02X}   "
                      f"${rec['flags']:02X}  "
                      f"${rec['bright_lo']:02X}  "
                      f"${rec['bright_hi']:02X}  "
                      f"${rec['reserved']:02X}")
            print()

    # Hex dump
    for i in range(0, len(data), 16):
        row = data[i:min(i + 16, len(data))]
        addr = DDRW_LOAD_ADDR + i
        hex_part = ' '.join(f'{b:02X}' for b in row)
        ascii_part = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in row)
        print(f"  {addr:04X}: {hex_part:<48s}  {ascii_part}")
    print()


def cmd_edit(args) -> None:
    """Patch bytes at a specific offset."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())

    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)

    offset = args.offset
    hex_str = args.data.replace(' ', '').replace(',', '')
    try:
        new_bytes = bytes.fromhex(hex_str)
    except ValueError:
        print(f"Error: Invalid hex data: {args.data}", file=sys.stderr)
        sys.exit(1)

    if offset + len(new_bytes) > len(data):
        print("Error: Patch extends past end of file", file=sys.stderr)
        sys.exit(1)

    old_bytes = bytes(data[offset:offset + len(new_bytes)])
    print(f"Offset 0x{offset:04X} ({len(new_bytes)} bytes):")
    print(f"  Old: {' '.join(f'{b:02X}' for b in old_bytes)}")
    print(f"  New: {' '.join(f'{b:02X}' for b in new_bytes)}")

    if dry_run:
        print("Dry run — no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)

    data[offset:offset + len(new_bytes)] = new_bytes
    with open(output, 'wb') as f:
        f.write(bytes(data))
    print(f"Updated {output}")


def cmd_import(args) -> None:
    """Import dungeon drawing data from JSON."""
    do_backup = getattr(args, 'backup', False)
    dry_run = getattr(args, 'dry_run', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    raw = jdata.get('raw', jdata) if isinstance(jdata, dict) else jdata
    if not isinstance(raw, list):
        print("Error: JSON must contain a 'raw' byte array", file=sys.stderr)
        sys.exit(1)

    try:
        data = bytes(raw)
    except (TypeError, ValueError) as e:
        print(f"Error: Invalid byte values in 'raw' array: {e}", file=sys.stderr)
        sys.exit(1)

    if len(data) != DDRW_FILE_SIZE:
        print(f"  Warning: expected {DDRW_FILE_SIZE} bytes, got {len(data)}",
              file=sys.stderr)

    print(f"Import: {len(data)} bytes")

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and os.path.exists(args.file) and (
            not args.output or args.output == args.file):
        backup_file(args.file)

    with open(output, 'wb') as f:
        f.write(data)
    print(f"Imported {len(data)} bytes to {output}")


# ============================================================================
# Parser registration
# ============================================================================

def register_parser(subparsers) -> None:
    """Register ddrw subcommands."""
    p = subparsers.add_parser('ddrw', help='Dungeon drawing data viewer/editor')
    sub = p.add_subparsers(dest='ddrw_command')

    p_view = sub.add_parser('view', help='View dungeon drawing data')
    p_view.add_argument('path', help='DDRW file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Patch bytes')
    p_edit.add_argument('file', help='DDRW file')
    p_edit.add_argument('--offset', type=hex_int, required=True, help='Byte offset')
    p_edit.add_argument('--data', required=True, help='New data as hex bytes')
    p_edit.add_argument('--output', '-o', help='Output file')
    p_edit.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')

    p_import = sub.add_parser('import', help='Import from JSON')
    p_import.add_argument('file', help='DDRW file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file')
    p_import.add_argument('--backup', action='store_true',
                          help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true',
                          help='Show changes without writing')


def dispatch(args) -> None:
    """Dispatch ddrw subcommand."""
    cmd = args.ddrw_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: ult3edit ddrw {view|edit|import} ...", file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Dungeon Drawing Data Editor')
    sub = parser.add_subparsers(dest='ddrw_command')

    p_view = sub.add_parser('view', help='View dungeon drawing data')
    p_view.add_argument('path', help='DDRW file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Patch bytes')
    p_edit.add_argument('file', help='DDRW file')
    p_edit.add_argument('--offset', type=hex_int, required=True, help='Byte offset')
    p_edit.add_argument('--data', required=True, help='New data as hex bytes')
    p_edit.add_argument('--output', '-o', help='Output file')
    p_edit.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')

    p_import = sub.add_parser('import', help='Import from JSON')
    p_import.add_argument('file', help='DDRW file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file')
    p_import.add_argument('--backup', action='store_true',
                          help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true',
                          help='Show changes without writing')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
