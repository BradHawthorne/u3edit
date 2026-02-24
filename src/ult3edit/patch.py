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

from .constants import JSR_46BA
from .fileutil import backup_file, hex_int
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
        # CIDAR-verified at address $772C (word_772C)
        # Default value $04 — decremented each step, triggers food loss at 0
        'food-rate': {
            'offset': 0x272C,
            'max_length': 1,
            'description': 'Food depletion counter (default $04, lower=faster)',
            'data_type': 'bytes',
        },
    },
    # EXOD has no verified patchable data regions — previously documented
    # addresses ($35E1, $35F9, $384D) are actually animation frame data.
}


def get_regions(binary_name: str) -> dict:
    """Get patchable regions for a binary."""
    return PATCHABLE_REGIONS.get(binary_name, {})


# ============================================================================
# Data type parsers
# ============================================================================

def parse_text_region(data: bytes, offset: int, length: int) -> list[str]:
    """Parse null-terminated string table from binary.

    Preserves empty strings (consecutive null terminators) within the content
    region. Trailing null padding is stripped.
    """
    end = min(offset + length, len(data))
    region = data[offset:end]

    # Find end of content: last non-null byte + its null terminator
    content_end = len(region)
    while content_end > 0 and region[content_end - 1] == 0x00:
        content_end -= 1
    if content_end < len(region):
        content_end += 1  # include final null terminator

    strings = []
    current = []
    for i in range(content_end):
        b = region[i]
        if b == 0x00:
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


def encode_coord_region(coords: list[dict], max_length: int) -> bytes:
    """Encode XY coordinate pairs as raw bytes."""
    out = bytearray()
    for c in coords:
        out.append(c['x'] & 0xFF)
        out.append(c['y'] & 0xFF)
    if len(out) > max_length:
        raise ValueError(f"Encoded coords ({len(out)} bytes) exceeds max "
                         f"region size ({max_length} bytes)")
    # Pad with nulls
    while len(out) < max_length:
        out.append(0x00)
    return bytes(out)


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
        print("Error: Not a recognized engine binary", file=sys.stderr)
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


def _encode_region(reg: dict, data_value) -> bytes:
    """Encode a region's data based on its data type."""
    if reg['data_type'] == 'text':
        return encode_text_region(data_value, reg['max_length'])
    elif reg['data_type'] == 'coords':
        return encode_coord_region(data_value, reg['max_length'])
    else:
        # 'bytes' — accept list of ints
        raw = bytes(data_value)
        if len(raw) > reg['max_length']:
            raise ValueError(f"Data ({len(raw)} bytes) exceeds max "
                             f"region size ({reg['max_length']} bytes)")
        # Pad with nulls
        raw = raw + b'\x00' * (reg['max_length'] - len(raw))
        return raw


def cmd_import(args) -> None:
    """Import region data from JSON."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())

    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)

    info = identify_binary(data, args.file)
    if not info:
        print("Error: Not a recognized engine binary", file=sys.stderr)
        sys.exit(1)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    regions = get_regions(info['name'])
    if not regions:
        print(f"Error: No patchable regions for {info['name']}",
              file=sys.stderr)
        sys.exit(1)

    # Accept both top-level {"regions": {...}} and flat {"region-name": {...}}
    if 'regions' in jdata and isinstance(jdata['regions'], dict):
        import_regions = jdata['regions']
    else:
        import_regions = jdata

    region_filter = getattr(args, 'region', None)
    patched = 0

    for name, reg in regions.items():
        if region_filter and name != region_filter:
            continue
        if name not in import_regions:
            continue

        entry = import_regions[name]
        # Accept either {"data": [...]} or just the raw list
        if isinstance(entry, dict) and 'data' in entry:
            data_value = entry['data']
        elif isinstance(entry, list):
            data_value = entry
        else:
            print(f"Warning: Skipping '{name}' — unexpected format",
                  file=sys.stderr)
            continue

        try:
            new_bytes = _encode_region(reg, data_value)
        except (ValueError, TypeError) as e:
            print(f"Error encoding '{name}': {e}", file=sys.stderr)
            sys.exit(1)

        offset = reg['offset']
        old_bytes = bytes(data[offset:offset + len(new_bytes)])

        print(f"Region: {name} ({reg['description']})")
        print(f"  Offset: 0x{offset:04X}, Length: {len(new_bytes)} bytes")
        if old_bytes == new_bytes:
            print("  (no change)")
        else:
            print("  Updated")

        data[offset:offset + len(new_bytes)] = new_bytes  # Local buffer only
        patched += 1

    if patched == 0:
        print("No matching regions found in JSON.", file=sys.stderr)
        sys.exit(1)

    if dry_run:  # Buffer mutations above are discarded — no file written
        print(f"Dry run — {patched} region(s) would be updated.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)

    with open(output, 'wb') as f:
        f.write(bytes(data))
    print(f"Imported {patched} region(s) into {output}")


# ============================================================================
# Inline string catalog
# ============================================================================

_JSR_46BA = JSR_46BA


def _extract_inline_strings(data: bytes, org: int = 0):
    """Extract JSR $46BA inline strings from binary data.

    Embedded implementation — same algorithm as engine/tools/string_catalog.py
    but integrated into the ult3edit package (no external dependency).
    """
    strings = []
    i = 0
    idx = 0
    while i < len(data) - 3:
        if data[i:i + 3] == _JSR_46BA:
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
                text = ''.join(chars)
                byte_count = j - text_start + 1  # including null
                strings.append({
                    'index': idx,
                    'address': org + i,
                    'text': text,
                    'byte_count': byte_count,
                    'text_offset': text_start,
                    'text_end': j,
                })
                idx += 1
            i = j + 1
        else:
            i += 1
    return strings


def _encode_high_ascii(text: str) -> bytearray:
    """Encode text as high-ASCII bytes with $FF for newlines."""
    result = bytearray()
    for ch in text:
        if ch == '\n':
            result.append(0xFF)
        else:
            result.append(ord(ch.upper()) | 0x80)
    return result


def _patch_inline_string(data: bytearray, string_info: dict,
                         new_text: str) -> tuple:
    """Patch a single inline string in-place.

    Returns (success: bool, message: str).
    """
    text_offset = string_info['text_offset']
    text_end = string_info['text_end']
    max_bytes = text_end - text_offset  # space before null terminator

    encoded = _encode_high_ascii(new_text)

    if len(encoded) > max_bytes:
        return False, (f"String too long: '{new_text}' needs {len(encoded)} "
                       f"bytes, only {max_bytes} available "
                       f"(original: '{string_info['text']}')")

    # Write encoded text
    for i, b in enumerate(encoded):
        data[text_offset + i] = b

    # Null-fill remaining space
    for i in range(len(encoded), max_bytes + 1):
        data[text_offset + i] = 0x00

    return True, (f"[{string_info['index']:3d}] "
                  f"'{string_info['text']}' -> '{new_text}'")


def _resolve_string_target(strings, index=None, vanilla=None, address=None):
    """Find a string entry by index, vanilla text, or address.

    Returns list of matching string_info dicts.
    """
    if index is not None:
        return [s for s in strings if s['index'] == index]
    elif vanilla is not None:
        key = vanilla.strip().strip('\n').upper()
        return [s for s in strings
                if s['text'].strip().strip('\n').upper() == key]
    elif address is not None:
        return [s for s in strings if s['address'] == address]
    return []


def cmd_strings_edit(args) -> None:
    """Edit an inline string in an engine binary (in-place)."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())

    info = identify_binary(data, args.file)
    org = info['load_addr'] if info else 0

    strings = _extract_inline_strings(bytes(data), org)
    if not strings:
        print("No inline strings found", file=sys.stderr)
        sys.exit(1)

    # Find the target string
    idx = getattr(args, 'index', None)
    vanilla = getattr(args, 'vanilla', None)
    addr = getattr(args, 'address', None)
    new_text = args.text

    if idx is None and vanilla is None and addr is None:
        print("Error: specify --index, --vanilla, or --address",
              file=sys.stderr)
        sys.exit(1)

    targets = _resolve_string_target(strings, index=idx, vanilla=vanilla,
                                     address=addr)
    if not targets:
        print("Error: no matching string found", file=sys.stderr)
        sys.exit(1)

    success_count = 0
    for target in targets:
        ok, msg = _patch_inline_string(data, target, new_text)
        if ok:
            print(f"  Patched {msg}")
            success_count += 1
        else:
            print(f"  ERROR: {msg}", file=sys.stderr)

    if success_count == 0:
        sys.exit(1)

    if getattr(args, 'dry_run', False):
        print(f"\nDry run — {success_count} string(s) would be patched.")
        return

    output = getattr(args, 'output', None) or args.file
    if getattr(args, 'backup', False) and output == args.file:
        backup_file(args.file)

    with open(output, 'wb') as f:
        f.write(data)
    print(f"Patched {success_count} string(s) in {output}")


def cmd_strings_import(args) -> None:
    """Import inline string patches from JSON."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())

    info = identify_binary(data, args.file)
    org = info['load_addr'] if info else 0

    strings = _extract_inline_strings(bytes(data), org)
    if not strings:
        print("No inline strings found", file=sys.stderr)
        sys.exit(1)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        patch_data = json.load(f)

    patches = patch_data.get('patches', [])
    if not patches:
        print("No patches found in JSON file", file=sys.stderr)
        sys.exit(1)

    success_count = 0
    error_count = 0

    for patch in patches:
        new_text = patch.get('text', '')
        idx = patch.get('index')
        vanilla = patch.get('vanilla')
        addr_str = patch.get('address')
        addr = None
        if addr_str is not None:
            addr = int(addr_str, 0) if isinstance(addr_str, str) else addr_str

        targets = _resolve_string_target(strings, index=idx, vanilla=vanilla,
                                         address=addr)
        if not targets:
            key = vanilla or (f"index {idx}" if idx is not None else
                              f"${addr:04X}" if addr else "?")
            print(f"  Warning: no match for '{key}'", file=sys.stderr)
            continue

        for target in targets:
            ok, msg = _patch_inline_string(data, target, new_text)
            if ok:
                print(f"  Patched {msg}")
                success_count += 1
            else:
                print(f"  ERROR: {msg}", file=sys.stderr)
                error_count += 1

    print(f"\nPatched {success_count} string(s), {error_count} error(s)")

    if error_count > 0:
        print("Errors detected — not writing output.", file=sys.stderr)
        sys.exit(1)

    if getattr(args, 'dry_run', False):
        print("Dry run — no changes written.")
        return

    output = getattr(args, 'output', None) or args.file
    if getattr(args, 'backup', False) and output == args.file:
        backup_file(args.file)

    with open(output, 'wb') as f:
        f.write(data)
    print(f"Wrote {output}")


def cmd_strings(args) -> None:
    """List all JSR $46BA inline strings in an engine binary."""
    with open(args.file, 'rb') as f:
        data = f.read()

    info = identify_binary(data, args.file)
    if not info:
        print(f"Warning: Unknown binary ({len(data)} bytes)", file=sys.stderr)
        org = 0
    else:
        org = info['load_addr']

    strings = _extract_inline_strings(data, org)

    if not strings:
        print(f"No inline strings found in {os.path.basename(args.file)}")
        return

    if getattr(args, 'json', False):
        result = {
            'binary': os.path.basename(args.file),
            'org': f'${org:04X}',
            'total_strings': len(strings),
            'total_bytes': sum(s['byte_count'] for s in strings),
            'strings': strings,
        }
        export_json(result, args.output)
    else:
        filename = os.path.basename(args.file)
        total = sum(s['byte_count'] for s in strings)
        print(f"\n=== Inline Strings: {filename} ===")
        print(f"Total: {len(strings)} strings, {total:,} bytes")
        print(f"Origin: ${org:04X}\n")

        # Filter by search text if specified
        search = getattr(args, 'search', None)
        display = strings
        if search:
            search_upper = search.upper()
            display = [s for s in strings if search_upper in s['text'].upper()]
            print(f"Filter: '{search}' ({len(display)} matches)\n")

        for s in display:
            text = s['text'].replace('\n', '\\n')
            print(f"  [{s['index']:3d}] ${s['address']:04X}  "
                  f"{s['byte_count']:3d}B  {text}")
        print()


# ============================================================================
# Name table compile / decompile
# ============================================================================

_NAME_TABLE_OFFSET = 0x397A
_NAME_TABLE_SIZE = 921
_NAME_TAIL_RESERVE = 30

# Known group boundaries (from engine analysis)
_NAME_GROUPS = [
    (0, 39, 'Terrain and NPC Types'),
    (39, 65, 'Map Codes'),
    (65, 81, 'Weapons'),
    (81, 89, 'Armor'),
    (89, 104, 'Wizard Spells'),
    (104, 105, 'Separator'),
    (105, 121, 'Cleric Spells'),
    (121, None, 'Monster Alternates'),
]


def _parse_names_file(text: str) -> list[str]:
    """Parse a .names text file into a list of name strings."""
    names = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('# ') or stripped == '#':
            continue
        if not stripped:
            continue
        if stripped in ('""', "''"):
            names.append('')
        else:
            names.append(stripped)
    return names


def _validate_names(names: list[str]) -> tuple[int, int, bool]:
    """Check if names fit within the 921-byte budget.

    Returns (encoded_size, budget, is_valid).
    """
    size = sum(len(s) + 1 for s in names)
    budget = _NAME_TABLE_SIZE - _NAME_TAIL_RESERVE
    return size, budget, size <= budget


def cmd_compile_names(args) -> None:
    """Compile .names file to JSON for patch import."""
    with open(args.source, 'r', encoding='utf-8') as f:
        text = f.read()

    names = _parse_names_file(text)
    if not names:
        print("No names found in source file.", file=sys.stderr)
        sys.exit(1)

    size, budget, valid = _validate_names(names)
    if not valid:
        print(f"Error: names ({size} bytes) exceed budget "
              f"({budget} bytes, {_NAME_TAIL_RESERVE} reserved for tail)",
              file=sys.stderr)
        sys.exit(1)

    result = json.dumps({
        'regions': {
            'name-table': {
                'data': names
            }
        }
    }, indent=2)

    output = getattr(args, 'output', None)
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(result + '\n')
        print(f"Compiled {len(names)} names ({size}/{budget} bytes) "
              f"to {output}")
    else:
        print(result)
    print(f"# {len(names)} names, {size}/{budget} bytes OK",
          file=sys.stderr)


def cmd_decompile_names(args) -> None:
    """Decompile ULT3 name table to .names text format."""
    with open(args.file, 'rb') as f:
        data = f.read()

    strings = parse_text_region(data, _NAME_TABLE_OFFSET, _NAME_TABLE_SIZE)

    lines = ['# Ultima III Name Table']
    lines.append(f'# {len(strings)} strings extracted')
    lines.append('')

    idx = 0
    for start, end, label in _NAME_GROUPS:
        if idx >= len(strings):
            break
        actual_end = end if end is not None else len(strings)
        if idx < start:
            for i in range(idx, min(start, len(strings))):
                lines.append(strings[i] if strings[i] else '""')
            idx = start
        lines.append(f'# Group: {label}')
        for i in range(start, min(actual_end, len(strings))):
            lines.append(strings[i] if strings[i] else '""')
        lines.append('')
        idx = actual_end

    if idx < len(strings):
        lines.append('# Group: Extra')
        for i in range(idx, len(strings)):
            lines.append(strings[i] if strings[i] else '""')

    result = '\n'.join(lines) + '\n'

    output = getattr(args, 'output', None)
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"Decompiled {len(strings)} names to {output}")
    else:
        print(result)


def cmd_validate_names(args) -> None:
    """Validate .names file against 921-byte budget."""
    with open(args.source, 'r', encoding='utf-8') as f:
        text = f.read()
    names = _parse_names_file(text)
    size, budget, valid = _validate_names(names)

    print(f"Strings: {len(names)}")
    print(f"Encoded: {size} bytes")
    print(f"Budget:  {budget} bytes (921 - {_NAME_TAIL_RESERVE} tail reserve)")
    print(f"Free:    {budget - size} bytes")
    print(f"Status:  {'PASS' if valid else 'FAIL -- over budget'}")

    if not valid:
        sys.exit(1)


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
    p_dump.add_argument('--offset', type=hex_int, default=0, help='Start offset')
    p_dump.add_argument('--length', type=hex_int, default=256, help='Bytes to show')

    p_import = sub.add_parser('import', help='Import region data from JSON')
    p_import.add_argument('file', help='Engine binary')
    p_import.add_argument('json_file', help='JSON file (from view --json)')
    p_import.add_argument('--region', help='Import specific region only')
    p_import.add_argument('--output', '-o', help='Output file')
    p_import.add_argument('--backup', action='store_true',
                          help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true',
                          help='Show changes without writing')

    p_strings = sub.add_parser('strings',
                               help='List inline JSR $46BA strings')
    p_strings.add_argument('file', help='Engine binary (ULT3)')
    p_strings.add_argument('--search', help='Filter by text (case-insensitive)')
    p_strings.add_argument('--json', action='store_true', help='Output as JSON')
    p_strings.add_argument('--output', '-o', help='Output file (for --json)')

    p_stredit = sub.add_parser('strings-edit',
                               help='Edit an inline string (in-place)')
    p_stredit.add_argument('file', help='Engine binary (ULT3)')
    p_stredit.add_argument('--text', required=True, help='Replacement text')
    match_group = p_stredit.add_mutually_exclusive_group(required=True)
    match_group.add_argument('--index', type=int,
                             help='String index (from strings command)')
    match_group.add_argument('--vanilla', help='Original text to match')
    match_group.add_argument('--address', type=hex_int,
                             help='String address (e.g. 0x6C48)')
    p_stredit.add_argument('--output', '-o', help='Output file')
    p_stredit.add_argument('--backup', action='store_true',
                           help='Create .bak backup before overwrite')
    p_stredit.add_argument('--dry-run', action='store_true',
                           help='Show changes without writing')

    p_strimport = sub.add_parser('strings-import',
                                 help='Import string patches from JSON')
    p_strimport.add_argument('file', help='Engine binary (ULT3)')
    p_strimport.add_argument('json_file', help='JSON patch file')
    p_strimport.add_argument('--output', '-o', help='Output file')
    p_strimport.add_argument('--backup', action='store_true',
                             help='Create .bak backup before overwrite')
    p_strimport.add_argument('--dry-run', action='store_true',
                             help='Show changes without writing')

    p_cnames = sub.add_parser('compile-names',
                              help='Compile .names to JSON for patch import')
    p_cnames.add_argument('source', help='.names source file')
    p_cnames.add_argument('--output', '-o', help='Output JSON file')

    p_dnames = sub.add_parser('decompile-names',
                              help='Decompile ULT3 name table to .names')
    p_dnames.add_argument('file', help='ULT3 engine binary')
    p_dnames.add_argument('--output', '-o', help='Output .names file')

    p_vnames = sub.add_parser('validate-names',
                              help='Validate .names file against budget')
    p_vnames.add_argument('source', help='.names source file')


def dispatch(args) -> None:
    """Dispatch patch subcommand."""
    cmd = args.patch_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'dump':
        cmd_dump(args)
    elif cmd == 'import':
        cmd_import(args)
    elif cmd == 'strings':
        cmd_strings(args)
    elif cmd == 'strings-edit':
        cmd_strings_edit(args)
    elif cmd == 'strings-import':
        cmd_strings_import(args)
    elif cmd == 'compile-names':
        cmd_compile_names(args)
    elif cmd == 'decompile-names':
        cmd_decompile_names(args)
    elif cmd == 'validate-names':
        cmd_validate_names(args)
    else:
        print("Usage: ult3edit patch "
              "{view|edit|dump|import|strings|strings-edit|strings-import|"
              "compile-names|decompile-names|validate-names} ...",
              file=sys.stderr)


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
    p_dump.add_argument('--offset', type=hex_int, default=0, help='Start offset')
    p_dump.add_argument('--length', type=hex_int, default=256, help='Bytes to show')

    p_import = sub.add_parser('import', help='Import region data from JSON')
    p_import.add_argument('file', help='Engine binary')
    p_import.add_argument('json_file', help='JSON file (from view --json)')
    p_import.add_argument('--region', help='Import specific region only')
    p_import.add_argument('--output', '-o', help='Output file')
    p_import.add_argument('--backup', action='store_true',
                          help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true',
                          help='Show changes without writing')

    p_strings = sub.add_parser('strings',
                               help='List inline JSR $46BA strings')
    p_strings.add_argument('file', help='Engine binary (ULT3)')
    p_strings.add_argument('--search', help='Filter by text (case-insensitive)')
    p_strings.add_argument('--json', action='store_true', help='Output as JSON')
    p_strings.add_argument('--output', '-o', help='Output file (for --json)')

    p_stredit = sub.add_parser('strings-edit',
                               help='Edit an inline string (in-place)')
    p_stredit.add_argument('file', help='Engine binary (ULT3)')
    p_stredit.add_argument('--text', required=True, help='Replacement text')
    match_group = p_stredit.add_mutually_exclusive_group(required=True)
    match_group.add_argument('--index', type=int,
                             help='String index (from strings command)')
    match_group.add_argument('--vanilla', help='Original text to match')
    match_group.add_argument('--address', type=hex_int,
                             help='String address (e.g. 0x6C48)')
    p_stredit.add_argument('--output', '-o', help='Output file')
    p_stredit.add_argument('--backup', action='store_true',
                           help='Create .bak backup before overwrite')
    p_stredit.add_argument('--dry-run', action='store_true',
                           help='Show changes without writing')

    p_strimport = sub.add_parser('strings-import',
                                 help='Import string patches from JSON')
    p_strimport.add_argument('file', help='Engine binary (ULT3)')
    p_strimport.add_argument('json_file', help='JSON patch file')
    p_strimport.add_argument('--output', '-o', help='Output file')
    p_strimport.add_argument('--backup', action='store_true',
                             help='Create .bak backup before overwrite')
    p_strimport.add_argument('--dry-run', action='store_true',
                             help='Show changes without writing')

    p_cnames = sub.add_parser('compile-names',
                              help='Compile .names to JSON for patch import')
    p_cnames.add_argument('source', help='.names source file')
    p_cnames.add_argument('--output', '-o', help='Output JSON file')

    p_dnames = sub.add_parser('decompile-names',
                              help='Decompile ULT3 name table to .names')
    p_dnames.add_argument('file', help='ULT3 engine binary')
    p_dnames.add_argument('--output', '-o', help='Output .names file')

    p_vnames = sub.add_parser('validate-names',
                              help='Validate .names file against budget')
    p_vnames.add_argument('source', help='.names source file')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
