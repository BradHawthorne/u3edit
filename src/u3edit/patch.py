"""Ultima III: Exodus - Engine Binary Patcher.

Targeted binary patches at CIDAR-identified offsets in the ULT3 and EXOD
engine binaries. Does NOT reassemble — just overwrites known data regions.

Known engine binaries:
  ULT3 (17408 bytes, $5000) — Main game engine
  EXOD (26208 bytes, $2000) — Exodus engine/content
  SUBS (3584 bytes, $4100)  — Subroutine library
"""

import argparse
import json
import os
import sys

from .fileutil import backup_file
from .json_export import export_json

# ============================================================================
# Engine binary identification
# ============================================================================

ENGINE_BINARIES = {
    'ULT3': {'size': 17408, 'load_addr': 0x5000},
    'EXOD': {'size': 26208, 'load_addr': 0x2000},
    # SUBS is a shared subroutine library (BCD math, string routines, etc.).
    # No known data regions — all executable code. Listed for identification only.
    'SUBS': {'size': 3584, 'load_addr': 0x4100},
}


def identify_binary(data: bytes, filename: str = '') -> dict | None:
    """Identify which engine binary this is."""
    name_upper = os.path.basename(filename).upper().split('#')[0]
    size = len(data)

    for name, info in ENGINE_BINARIES.items():
        if name_upper == name or size == info['size']:
            return {'name': name, **info}
    return None


# ============================================================================
# Patchable regions — CIDAR-identified data offsets
# ============================================================================

# Each region: (file_offset, max_length, description, data_type)
# file_offset is relative to the start of the binary file
# data_type: 'text' = null-terminated strings, 'bytes' = raw,
#            'coords' = XY coordinate pairs

PATCHABLE_REGIONS: dict[str, dict[str, list]] = {
    'ULT3': {
        # Master name table: terrain, monster, weapon, armor, spell names
        # CIDAR-verified at address $897A (after draw_hgr function rts)
        # 921 bytes of null-terminated high-ASCII strings
        'name-table': {
            'offset': 0x397A,
            'max_length': 921,
            'description': 'Master name table (terrain/monster/weapon/armor/spell)',
            'data_type': 'text',
        },
        # Moon gate X coordinates (8 phases)
        # CIDAR-verified at address $79A7 (arr_79A7)
        'moongate-x': {
            'offset': 0x29A7,
            'max_length': 8,
            'description': 'Moon gate X coordinates (8 phases)',
            'data_type': 'bytes',
        },
        # Moon gate Y coordinates (8 phases)
        # CIDAR-verified at address $79AF (arr_79AF)
        'moongate-y': {
            'offset': 0x29AF,
            'max_length': 8,
            'description': 'Moon gate Y coordinates (8 phases)',
            'data_type': 'bytes',
        },
        # Food depletion rate counter
        # CIDAR-verified at address $772C (word_732C)
        # Default value $04 — decremented each step, triggers food loss at 0
        'food-rate': {
            'offset': 0x272C,
            'max_length': 1,
            'description': 'Food depletion counter (default $04, lower=faster)',
            'data_type': 'bytes',
        },
    },
    'EXOD': {
        # Town/castle entrance coordinates (from CIDAR analysis)
        'town-coords': {
            'offset': 0x35E1,
            'max_length': 32,
            'description': 'Town/castle entrance XY coordinates',
            'data_type': 'coords',
        },
        # Dungeon entrance coordinates
        'dungeon-coords': {
            'offset': 0x35F9,
            'max_length': 32,
            'description': 'Dungeon entrance XY coordinates',
            'data_type': 'coords',
        },
        # Moongate coordinates (EXOD copy)
        'moongate-coords': {
            'offset': 0x384D,
            'max_length': 16,
            'description': 'Moongate XY positions by phase',
            'data_type': 'coords',
        },
    },
}


def get_regions(binary_name: str) -> dict:
    """Get patchable regions for a binary."""
    return PATCHABLE_REGIONS.get(binary_name, {})


# ============================================================================
# Data type parsers
# ============================================================================

def parse_text_region(data: bytes, offset: int, length: int) -> list[str]:
    """Parse null-terminated string table from binary."""
    strings = []
    end = min(offset + length, len(data))
    current = []
    for i in range(offset, end):
        b = data[i]
        if b == 0x00:
            if current:
                strings.append(''.join(current))
                current = []
        else:
            ch = b & 0x7F
            if 0x20 <= ch < 0x7F:
                current.append(chr(ch))
    if current:
        strings.append(''.join(current))
    return strings


def parse_coord_region(data: bytes, offset: int,
                       length: int) -> list[dict]:
    """Parse XY coordinate pairs."""
    coords = []
    end = min(offset + length, len(data))
    for i in range(offset, end, 2):
        if i + 1 < len(data):
            coords.append({'x': data[i], 'y': data[i + 1]})
    return coords


def encode_text_region(strings: list[str], max_length: int) -> bytes:
    """Encode strings as null-terminated high-ASCII text."""
    out = bytearray()
    for s in strings:
        for ch in s:
            out.append((ord(ch) & 0x7F) | 0x80)
        out.append(0x00)
    if len(out) > max_length:
        raise ValueError(f"Encoded text ({len(out)} bytes) exceeds max "
                         f"region size ({max_length} bytes)")
    # Pad with nulls
    while len(out) < max_length:
        out.append(0x00)
    return bytes(out)


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_view(args) -> None:
    """Show patchable regions and their current values."""
    with open(args.file, 'rb') as f:
        data = f.read()

    info = identify_binary(data, args.file)
    filename = os.path.basename(args.file)

    if not info:
        print(f"Warning: {filename} not recognized as a known engine binary",
              file=sys.stderr)
        print(f"  Size: {len(data)} bytes")
        if args.json:
            export_json({'file': filename, 'size': len(data),
                         'recognized': False}, args.output)
        return

    regions = get_regions(info['name'])
    region_name = getattr(args, 'region', None)

    if region_name:
        if region_name not in regions:
            available = ', '.join(regions.keys()) if regions else '(none)'
            print(f"Error: Unknown region '{region_name}'. "
                  f"Available: {available}", file=sys.stderr)
            sys.exit(1)
        regions = {region_name: regions[region_name]}

    if args.json:
        result = {
            'file': filename,
            'binary': info['name'],
            'size': len(data),
            'load_addr': f'${info["load_addr"]:04X}',
            'regions': {},
        }
        for name, reg in regions.items():
            parsed = _parse_region(data, reg)
            result['regions'][name] = {
                'offset': f'0x{reg["offset"]:04X}',
                'max_length': reg['max_length'],
                'description': reg['description'],
                'data_type': reg['data_type'],
                'data': parsed,
            }
        export_json(result, args.output)
        return

    print(f"\n=== {filename}: {info['name']} "
          f"(${info['load_addr']:04X}, {len(data)} bytes) ===\n")

    if not regions:
        print("  No known patchable regions for this binary.")
        print("  (Run CIDAR to discover more regions)")
        print()
        return

    for name, reg in regions.items():
        print(f"  [{name}] {reg['description']}")
        print(f"    Offset: 0x{reg['offset']:04X}, "
              f"Max: {reg['max_length']} bytes, "
              f"Type: {reg['data_type']}")

        parsed = _parse_region(data, reg)
        if reg['data_type'] == 'text':
            for i, s in enumerate(parsed):
                print(f"    [{i:2d}] {s}")
        elif reg['data_type'] == 'coords':
            for i, c in enumerate(parsed):
                print(f"    [{i:2d}] X={c['x']:3d} Y={c['y']:3d}")
        else:
            hex_str = ' '.join(f'{b:02X}' for b in parsed)
            print(f"    {hex_str}")
        print()


def _parse_region(data: bytes, reg: dict):
    """Parse a region based on its data type."""
    if reg['data_type'] == 'text':
        return parse_text_region(data, reg['offset'], reg['max_length'])
    elif reg['data_type'] == 'coords':
        return parse_coord_region(data, reg['offset'], reg['max_length'])
    else:
        end = min(reg['offset'] + reg['max_length'], len(data))
        return list(data[reg['offset']:end])


def cmd_edit(args) -> None:
    """Patch a known data region."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())

    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)

    info = identify_binary(data, args.file)
    if not info:
        print(f"Error: Not a recognized engine binary", file=sys.stderr)
        sys.exit(1)

    regions = get_regions(info['name'])
    if args.region not in regions:
        available = ', '.join(regions.keys()) if regions else '(none)'
        print(f"Error: Unknown region '{args.region}'. "
              f"Available: {available}", file=sys.stderr)
        sys.exit(1)

    reg = regions[args.region]

    # Parse the new data
    hex_str = args.data.replace(' ', '').replace(',', '')
    try:
        new_bytes = bytes.fromhex(hex_str)
    except ValueError:
        print(f"Error: Invalid hex data: {args.data}", file=sys.stderr)
        sys.exit(1)

    if len(new_bytes) > reg['max_length']:
        print(f"Error: Data ({len(new_bytes)} bytes) exceeds region max "
              f"({reg['max_length']} bytes)", file=sys.stderr)
        sys.exit(1)

    offset = reg['offset']
    old_bytes = bytes(data[offset:offset + len(new_bytes)])

    print(f"Region: {args.region} ({reg['description']})")
    print(f"Offset: 0x{offset:04X}, Length: {len(new_bytes)} bytes")
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
    print(f"Patched {output}")


def cmd_dump(args) -> None:
    """Raw hex dump of any region."""
    with open(args.file, 'rb') as f:
        data = f.read()

    info = identify_binary(data, args.file)
    base_addr = info['load_addr'] if info else 0

    offset = args.offset
    length = args.length
    end = min(offset + length, len(data))

    if offset >= len(data):
        print(f"Error: Offset 0x{offset:04X} past end of file "
              f"(size {len(data)})", file=sys.stderr)
        sys.exit(1)

    filename = os.path.basename(args.file)
    print(f"\n=== {filename} hex dump: 0x{offset:04X}–0x{end - 1:04X} ===\n")

    for i in range(offset, end, 16):
        row = data[i:min(i + 16, end)]
        addr = base_addr + i
        hex_part = ' '.join(f'{b:02X}' for b in row)
        ascii_part = ''.join(chr(b & 0x7F) if 0x20 <= (b & 0x7F) < 0x7F
                             else '.' for b in row)
        print(f"  {addr:04X}: {hex_part:<48s}  {ascii_part}")
    print()


# ============================================================================
# Parser registration
# ============================================================================

def register_parser(subparsers) -> None:
    """Register patch subcommands."""
    p = subparsers.add_parser('patch', help='Engine binary patcher')
    sub = p.add_subparsers(dest='patch_command')

    p_view = sub.add_parser('view', help='Show patchable regions')
    p_view.add_argument('file', help='Engine binary (ULT3, EXOD, SUBS)')
    p_view.add_argument('--region', help='Show specific region only')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Patch a data region')
    p_edit.add_argument('file', help='Engine binary')
    p_edit.add_argument('--region', required=True, help='Region name')
    p_edit.add_argument('--data', required=True, help='New data as hex')
    p_edit.add_argument('--output', '-o', help='Output file')
    p_edit.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')

    p_dump = sub.add_parser('dump', help='Hex dump of any offset')
    p_dump.add_argument('file', help='Engine binary')
    p_dump.add_argument('--offset', type=int, default=0, help='Start offset')
    p_dump.add_argument('--length', type=int, default=256, help='Bytes to show')


def dispatch(args) -> None:
    """Dispatch patch subcommand."""
    cmd = args.patch_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'dump':
        cmd_dump(args)
    else:
        print("Usage: u3edit patch {view|edit|dump} ...", file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Engine Binary Patcher')
    sub = parser.add_subparsers(dest='patch_command')

    p_view = sub.add_parser('view', help='Show patchable regions')
    p_view.add_argument('file', help='Engine binary (ULT3, EXOD, SUBS)')
    p_view.add_argument('--region', help='Show specific region only')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Patch a data region')
    p_edit.add_argument('file', help='Engine binary')
    p_edit.add_argument('--region', required=True, help='Region name')
    p_edit.add_argument('--data', required=True, help='New data as hex')
    p_edit.add_argument('--output', '-o', help='Output file')
    p_edit.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')

    p_dump = sub.add_parser('dump', help='Hex dump of any offset')
    p_dump.add_argument('file', help='Engine binary')
    p_dump.add_argument('--offset', type=int, default=0, help='Start offset')
    p_dump.add_argument('--length', type=int, default=256, help='Bytes to show')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
