#!/usr/bin/env python3
"""Name table compiler for Ultima III total conversions.

Converts human-readable .names text files to/from the 921-byte name table
in the ULT3 engine binary. Text-first pipeline: edit names in a text file,
compile to hex or JSON, apply via u3edit patch.

Source format (.names file):
    # Group: Terrain
    BRINE
    ASH
    THORNS
    ...
    # Group: Weapons
    FIST
    ...

Lines starting with '# ' are comments/group headers (preserved on decompile).
Empty lines produce empty strings (null terminators) in the encoded output.
Blank lines between groups are ignored.

Usage:
    name_compiler.py compile names.names              # Output hex string
    name_compiler.py compile names.names --format json  # JSON for patch import
    name_compiler.py decompile ULT3 --output names.names
    name_compiler.py validate names.names             # Check 921-byte budget
"""

import argparse
import json
import os
import sys

# Add project root for u3edit imports
_project_root = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from u3edit.patch import parse_text_region, encode_text_region

NAME_TABLE_OFFSET = 0x397A
NAME_TABLE_SIZE = 921
TAIL_RESERVE = 30  # BLOAD DDRW tail bytes


def parse_names_file(text):
    """Parse a .names text file into a list of name strings.

    Args:
        text: Contents of the .names file

    Returns:
        List of name strings (empty strings preserved)
    """
    names = []
    for line in text.splitlines():
        stripped = line.strip()
        # Skip comment/header lines
        if stripped.startswith('# ') or stripped == '#':
            continue
        # Skip blank lines (visual separators between groups)
        if not stripped:
            continue
        # A line of just "" or '' means explicit empty string
        if stripped in ('""', "''"):
            names.append('')
        else:
            names.append(stripped)
    return names


def decompile_names(data, offset=NAME_TABLE_OFFSET, length=NAME_TABLE_SIZE):
    """Extract name table from ULT3 binary as .names text.

    Args:
        data: Full ULT3 binary data
        offset: Name table offset (default 0x397A)
        length: Name table length (default 921)

    Returns:
        Text content in .names format with group headers
    """
    strings = parse_text_region(data, offset, length)

    # Known group boundaries (from engine analysis)
    groups = [
        (0, 39, 'Terrain and NPC Types'),
        (39, 65, 'Map Codes'),
        (65, 81, 'Weapons'),
        (81, 89, 'Armor'),
        (89, 104, 'Wizard Spells'),
        (104, 105, 'Separator'),
        (105, 121, 'Cleric Spells'),
        (121, None, 'Monster Alternates'),
    ]

    lines = ['# Ultima III Name Table']
    lines.append(f'# {len(strings)} strings extracted')
    lines.append('')

    idx = 0
    for start, end, label in groups:
        if idx >= len(strings):
            break
        actual_end = end if end is not None else len(strings)
        if idx < start:
            # Add any strings between groups
            for i in range(idx, min(start, len(strings))):
                lines.append(strings[i] if strings[i] else '""')
            idx = start
        lines.append(f'# Group: {label}')
        for i in range(start, min(actual_end, len(strings))):
            lines.append(strings[i] if strings[i] else '""')
        lines.append('')
        idx = actual_end

    # Any remaining strings
    if idx < len(strings):
        lines.append('# Group: Extra')
        for i in range(idx, len(strings)):
            lines.append(strings[i] if strings[i] else '""')

    return '\n'.join(lines) + '\n'


def compile_names(names, tail_data=None):
    """Encode name list as 921-byte name table.

    Args:
        names: List of name strings
        tail_data: Optional tail bytes to preserve (from original ULT3)

    Returns:
        921-byte encoded name table
    """
    # Encode the names portion
    encoded = bytearray()
    for s in names:
        for ch in s:
            encoded.append((ord(ch) & 0x7F) | 0x80)
        encoded.append(0x00)

    if tail_data:
        # Preserve tail from original
        if len(encoded) + len(tail_data) > NAME_TABLE_SIZE:
            raise ValueError(
                f"Names ({len(encoded)} bytes) + tail ({len(tail_data)} bytes) "
                f"exceeds {NAME_TABLE_SIZE}-byte budget"
            )
        result = encoded + tail_data
        # Pad to exact size
        while len(result) < NAME_TABLE_SIZE:
            result.append(0x00)
        return bytes(result[:NAME_TABLE_SIZE])
    else:
        budget = NAME_TABLE_SIZE - TAIL_RESERVE
        if len(encoded) > budget:
            raise ValueError(
                f"Names ({len(encoded)} bytes) exceeds budget "
                f"({budget} bytes, {TAIL_RESERVE} reserved for BLOAD tail)"
            )
        # Pad with nulls
        while len(encoded) < NAME_TABLE_SIZE:
            encoded.append(0x00)
        return bytes(encoded[:NAME_TABLE_SIZE])


def validate_names(names):
    """Check if names fit within the 921-byte budget.

    Returns:
        (encoded_size, budget, is_valid)
    """
    encoded = bytearray()
    for s in names:
        for ch in s:
            encoded.append((ord(ch) & 0x7F) | 0x80)
        encoded.append(0x00)
    budget = NAME_TABLE_SIZE - TAIL_RESERVE
    return len(encoded), budget, len(encoded) <= budget


def cmd_compile(args):
    """Compile .names file to hex or JSON."""
    with open(args.input, 'r', encoding='utf-8') as f:
        text = f.read()
    names = parse_names_file(text)

    tail_data = None
    if args.ult3:
        with open(args.ult3, 'rb') as f:
            data = f.read()
        # Calculate where names end to extract tail
        encoded_len = sum(len(s) + 1 for s in names)
        tail_start = NAME_TABLE_OFFSET + encoded_len
        tail_end = NAME_TABLE_OFFSET + NAME_TABLE_SIZE
        if tail_end <= len(data):
            tail_data = data[tail_start:tail_end]

    result = compile_names(names, tail_data)

    if args.format == 'json':
        output = json.dumps({
            'regions': {
                'name-table': {
                    'data': names
                }
            }
        }, indent=2)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output + '\n')
            print(f"Wrote JSON to {args.output}", file=sys.stderr)
        else:
            print(output)
    else:
        hex_str = result.hex().upper()
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(hex_str + '\n')
            print(f"Wrote hex to {args.output}", file=sys.stderr)
        else:
            print(hex_str)

    size, budget, valid = validate_names(names)
    print(f"# {len(names)} strings, {size}/{budget} bytes "
          f"({'OK' if valid else 'OVER BUDGET'})", file=sys.stderr)


def cmd_decompile(args):
    """Decompile ULT3 name table to .names format."""
    with open(args.input, 'rb') as f:
        data = f.read()

    text = decompile_names(data)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(text)


def cmd_validate(args):
    """Validate .names file against 921-byte budget."""
    with open(args.input, 'r', encoding='utf-8') as f:
        text = f.read()
    names = parse_names_file(text)
    size, budget, valid = validate_names(names)

    print(f"Strings: {len(names)}")
    print(f"Encoded: {size} bytes")
    print(f"Budget:  {budget} bytes (921 - {TAIL_RESERVE} tail reserve)")
    print(f"Free:    {budget - size} bytes")
    print(f"Status:  {'PASS' if valid else 'FAIL — over budget'}")

    if not valid:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Name table compiler for Ultima III total conversions')
    sub = parser.add_subparsers(dest='command')

    p_compile = sub.add_parser('compile', help='Compile .names to hex/JSON')
    p_compile.add_argument('input', help='.names source file')
    p_compile.add_argument('--format', choices=['hex', 'json'], default='hex',
                           help='Output format (default: hex)')
    p_compile.add_argument('--ult3', help='Original ULT3 to preserve tail')
    p_compile.add_argument('--output', '-o', help='Output file')

    p_decompile = sub.add_parser('decompile',
                                 help='Decompile ULT3 name table')
    p_decompile.add_argument('input', help='ULT3 binary file')
    p_decompile.add_argument('--output', '-o', help='Output .names file')

    p_validate = sub.add_parser('validate',
                                help='Validate .names budget')
    p_validate.add_argument('input', help='.names source file')

    args = parser.parse_args()
    if args.command == 'compile':
        cmd_compile(args)
    elif args.command == 'decompile':
        cmd_decompile(args)
    elif args.command == 'validate':
        cmd_validate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
