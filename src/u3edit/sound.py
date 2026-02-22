"""Ultima III: Exodus - Sound Data Viewer/Editor.

Sound files are separate data files loaded via BLOAD:
  SOSA (4096 bytes, $1000) — Apple II speaker sound patterns
  SOSM (256 bytes, $4F00)  — Sound map/parameter table
  MBS  (5456 bytes, $9A00) — Mockingboard AY-3-8910 register sequences
"""

import argparse
import json
import os
import sys

from .constants import SOSA_FILE_SIZE, SOSM_FILE_SIZE, MBS_FILE_SIZE
from .fileutil import resolve_single_file, backup_file, hex_int
from .json_export import export_json

SOUND_FILES = {
    'SOSA': {'size': SOSA_FILE_SIZE, 'load_addr': 0x1000,
             'description': 'Speaker sound patterns'},
    'SOSM': {'size': SOSM_FILE_SIZE, 'load_addr': 0x4F00,
             'description': 'Sound map/parameters'},
    'MBS':  {'size': MBS_FILE_SIZE, 'load_addr': 0x9A00,
             'description': 'Mockingboard AY-3-8910 sequences'},
}

# AY-3-8910 register names for structured MBS display
AY_REGISTERS = {
    0: 'Ch A Freq Lo',
    1: 'Ch A Freq Hi',
    2: 'Ch B Freq Lo',
    3: 'Ch B Freq Hi',
    4: 'Ch C Freq Lo',
    5: 'Ch C Freq Hi',
    6: 'Noise Period',
    7: 'Mixer Control',
    8: 'Ch A Volume',
    9: 'Ch B Volume',
    10: 'Ch C Volume',
    11: 'Envelope Freq Lo',
    12: 'Envelope Freq Hi',
    13: 'Envelope Shape',
}


# MBS music stream opcodes (Mockingboard AY-3-8910 driver)
# Values $00-$3F are note pitch indices
MBS_OPCODES = {
    0x80: ('LOOP', 'Loop start/repeat'),
    0x81: ('JUMP', 'Jump to address'),
    0x82: ('END', 'End of stream'),
    0x83: ('WRITE', 'Write AY register'),
    0x84: ('TEMPO', 'Set playback tempo'),
    0x85: ('MIXER', 'Set mixer control'),
}

# Approximate note names for pitch indices (chromatic scale, 4 octaves)
_NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def mbs_note_name(pitch: int) -> str:
    """Convert a pitch index ($00-$3F) to a note name."""
    if pitch == 0:
        return 'REST'
    octave = (pitch - 1) // 12
    note = (pitch - 1) % 12
    return f'{_NOTE_NAMES[note]}{octave + 1}'


# ============================================================================
# Sound data analysis
# ============================================================================

def identify_sound_file(data: bytes, filename: str = '') -> dict | None:
    """Identify which sound file type this is."""
    name_upper = os.path.basename(filename).upper().split('#')[0]
    size = len(data)

    for name, info in SOUND_FILES.items():
        if name_upper == name or size == info['size']:
            return {
                'name': name,
                'size': info['size'],
                'load_addr': info['load_addr'],
                'description': info['description'],
            }
    return None


def hex_dump(data: bytes, offset: int = 0, length: int | None = None,
             base_addr: int = 0) -> list[str]:
    """Generate hex dump lines."""
    if length is None:
        length = len(data) - offset
    end = min(offset + length, len(data))
    lines = []
    for i in range(offset, end, 16):
        row = data[i:min(i + 16, end)]
        addr = base_addr + i
        hex_part = ' '.join(f'{b:02X}' for b in row)
        ascii_part = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in row)
        lines.append(f'{addr:04X}: {hex_part:<48s}  {ascii_part}')
    return lines


def analyze_mbs(data: bytes) -> list[dict]:
    """Attempt to parse MBS as AY-3-8910 register sequences.

    Returns a list of register write events.
    """
    events = []
    i = 0
    while i + 1 < len(data):
        reg = data[i]
        val = data[i + 1]
        if reg > 13:
            # Not a valid AY register — likely end of sequence or different format
            break
        reg_name = AY_REGISTERS.get(reg, f'Reg {reg}')
        events.append({
            'offset': i,
            'register': reg,
            'register_name': reg_name,
            'value': val,
        })
        i += 2

    return events


def parse_mbs_stream(data: bytes, offset: int = 0) -> list[dict]:
    """Parse MBS music data stream starting at offset.

    The MBS format interleaves 6502 driver code with music data.
    Music stream opcodes:
      $00-$3F: Note pitch (index into frequency table)
      $80: Loop (repeat section)
      $81: Jump (to address — 2 byte operand)
      $82: End of stream
      $83: Write AY register (register + value operands)
      $84: Tempo (1 byte operand)
      $85: Mixer control (1 byte operand)
    """
    events = []
    i = offset
    while i < len(data):
        b = data[i]
        if b <= 0x3F:
            events.append({
                'offset': i,
                'type': 'NOTE',
                'value': b,
                'name': mbs_note_name(b),
            })
            i += 1
        elif b in MBS_OPCODES:
            opname, desc = MBS_OPCODES[b]
            ev = {'offset': i, 'type': opname, 'value': b, 'description': desc}
            if b == 0x82:  # END
                events.append(ev)
                break
            elif b == 0x80:  # LOOP — no operands (repeat marker)
                events.append(ev)
                i += 1
            elif b == 0x81:  # JUMP — 2 byte address operand
                if i + 2 < len(data):
                    lo, hi = data[i + 1], data[i + 2]
                    ev['target'] = (hi << 8) | lo
                else:
                    ev['truncated'] = True
                events.append(ev)
                i += 3
            elif b == 0x83:  # WRITE — register + value
                if i + 2 < len(data):
                    ev['register'] = data[i + 1]
                    ev['reg_value'] = data[i + 2]
                    reg_name = AY_REGISTERS.get(data[i + 1], f'Reg {data[i+1]}')
                    ev['register_name'] = reg_name
                else:
                    ev['truncated'] = True
                events.append(ev)
                i += 3
            elif b in (0x84, 0x85):  # TEMPO, MIXER — 1 byte operand
                if i + 1 < len(data):
                    ev['operand'] = data[i + 1]
                else:
                    ev['truncated'] = True
                events.append(ev)
                i += 2
            else:
                events.append(ev)
                i += 1
        else:
            # Unknown byte — likely driver code, not music data
            break
    return events


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_view(args) -> None:
    """View sound file data."""
    path_or_dir = args.path

    if os.path.isdir(path_or_dir):
        found = []
        for name in SOUND_FILES:
            path = resolve_single_file(path_or_dir, name)
            if path:
                found.append((name, path))

        if not found:
            print(f"Error: No sound files found in {path_or_dir}",
                  file=sys.stderr)
            sys.exit(1)

        if args.json:
            result = {}
            for name, path in found:
                with open(path, 'rb') as f:
                    data = f.read()
                info = SOUND_FILES[name]
                result[name] = {
                    'file': os.path.basename(path),
                    'size': len(data),
                    'load_addr': f'${info["load_addr"]:04X}',
                    'description': info['description'],
                    'raw': list(data),
                }
            export_json(result, args.output)
            return

        print(f"\n=== Ultima III Sound Files ({len(found)} found) ===\n")
        for name, path in found:
            with open(path, 'rb') as f:
                data = f.read()
            info = SOUND_FILES[name]
            print(f"  {name} — {info['description']}")
            print(f"    File: {os.path.basename(path)}")
            print(f"    Size: {len(data)} bytes, Load addr: ${info['load_addr']:04X}")
            # Show first few lines of hex dump
            lines = hex_dump(data, 0, min(64, len(data)), info['load_addr'])
            for line in lines:
                print(f"    {line}")
            if len(data) > 64:
                print(f"    ... ({len(data) - 64} more bytes)")
            print()
        return

    # Single file view
    with open(path_or_dir, 'rb') as f:
        data = f.read()

    info = identify_sound_file(data, path_or_dir)
    filename = os.path.basename(path_or_dir)

    if args.json:
        result = {
            'file': filename,
            'size': len(data),
            'info': info,
            'raw': list(data),
        }
        export_json(result, args.output)
        return

    base_addr = info['load_addr'] if info else 0
    desc = info['description'] if info else 'Unknown sound file'

    print(f"\n=== {filename}: {desc} ({len(data)} bytes) ===\n")

    # For MBS, try structured AY register parsing and music stream
    if info and info['name'] == 'MBS':
        events = analyze_mbs(data)
        if events:
            print(f"  AY-3-8910 register writes ({len(events)} events):\n")
            for ev in events[:32]:
                print(f"    [{ev['offset']:04X}] R{ev['register']:2d} "
                      f"({ev['register_name']:<18s}) = "
                      f"${ev['value']:02X} ({ev['value']:3d})")
            if len(events) > 32:
                print(f"    ... ({len(events) - 32} more events)")
            print()

        # Try music stream parsing at various offsets
        # MBS contains driver code first, then music data
        for try_offset in [0, 0x100, 0x200, 0x300]:
            if try_offset >= len(data):
                break
            stream = parse_mbs_stream(data, try_offset)
            if len(stream) >= 4:  # Only show if we found meaningful data
                print(f"  Music stream at offset 0x{try_offset:04X} "
                      f"({len(stream)} events):\n")
                for ev in stream[:48]:
                    if ev['type'] == 'NOTE':
                        print(f"    [{ev['offset']:04X}] {ev['name']:>5s} "
                              f"(pitch ${ev['value']:02X})")
                    elif ev['type'] == 'WRITE':
                        rn = ev.get('register_name', '?')
                        rv = ev.get('reg_value', 0)
                        print(f"    [{ev['offset']:04X}] WRITE "
                              f"R{ev.get('register', 0)} ({rn}) = ${rv:02X}")
                    elif ev['type'] in ('TEMPO', 'MIXER'):
                        print(f"    [{ev['offset']:04X}] {ev['type']} "
                              f"${ev.get('operand', 0):02X}")
                    elif ev['type'] == 'JUMP':
                        print(f"    [{ev['offset']:04X}] JUMP "
                              f"-> ${ev.get('target', 0):04X}")
                    elif ev['type'] == 'END':
                        print(f"    [{ev['offset']:04X}] END")
                    else:
                        print(f"    [{ev['offset']:04X}] {ev['type']}")
                if len(stream) > 48:
                    print(f"    ... ({len(stream) - 48} more events)")
                print()
                break  # Found a valid stream, stop trying offsets

    # Hex dump
    lines = hex_dump(data, 0, len(data), base_addr)
    for line in lines:
        print(f"  {line}")
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
        print(f"Error: Patch extends past end of file "
              f"(offset {offset} + {len(new_bytes)} > {len(data)})",
              file=sys.stderr)
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
    """Import sound data from JSON."""
    do_backup = getattr(args, 'backup', False)
    dry_run = getattr(args, 'dry_run', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    raw = jdata.get('raw', jdata) if isinstance(jdata, dict) else jdata
    if not isinstance(raw, list):
        print("Error: JSON must contain a 'raw' byte array", file=sys.stderr)
        sys.exit(1)

    data = bytes(raw)

    # Warn if size doesn't match any known sound file format
    known_sizes = {info['size']: name for name, info in SOUND_FILES.items()}
    if len(data) not in known_sizes:
        print(f"  Warning: {len(data)} bytes doesn't match any known sound file "
              f"(SOSA={SOSA_FILE_SIZE}, SOSM={SOSM_FILE_SIZE}, MBS={MBS_FILE_SIZE})",
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
    """Register sound subcommands."""
    p = subparsers.add_parser('sound', help='Sound data viewer/editor')
    sub = p.add_subparsers(dest='sound_command')

    p_view = sub.add_parser('view', help='View sound data')
    p_view.add_argument('path', help='Sound file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Patch sound data bytes')
    p_edit.add_argument('file', help='Sound file')
    p_edit.add_argument('--offset', type=hex_int, required=True,
                        help='Byte offset to patch')
    p_edit.add_argument('--data', required=True,
                        help='New data as hex bytes')
    p_edit.add_argument('--output', '-o', help='Output file')
    p_edit.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')

    p_import = sub.add_parser('import', help='Import sound from JSON')
    p_import.add_argument('file', help='Sound file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file')
    p_import.add_argument('--backup', action='store_true',
                          help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true',
                          help='Show changes without writing')


def dispatch(args) -> None:
    """Dispatch sound subcommand."""
    cmd = args.sound_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: u3edit sound {view|edit|import} ...", file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Sound Data Editor')
    sub = parser.add_subparsers(dest='sound_command')

    p_view = sub.add_parser('view', help='View sound data')
    p_view.add_argument('path', help='Sound file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Patch sound data bytes')
    p_edit.add_argument('file', help='Sound file')
    p_edit.add_argument('--offset', type=hex_int, required=True,
                        help='Byte offset to patch')
    p_edit.add_argument('--data', required=True,
                        help='New data as hex bytes')
    p_edit.add_argument('--output', '-o', help='Output file')
    p_edit.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')

    p_import = sub.add_parser('import', help='Import sound from JSON')
    p_import.add_argument('file', help='Sound file path')
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
