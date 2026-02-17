"""Ultima III: Exodus - TLK Dialog Extractor/Builder/Viewer.

TLK files contain NPC dialog text in high-bit ASCII.
Format: 0xFF = line break within record, 0x00 = record terminator.
19 TLK files (A-S) correspond to game locations.
"""

import argparse
import os
import sys
from pathlib import Path

from .constants import TLK_LETTERS, TLK_NAMES, TLK_LINE_BREAK, TLK_RECORD_END
from .fileutil import resolve_game_file, decode_high_ascii
from .json_export import export_json


def decode_record(data: bytes) -> list[str]:
    """Decode a single TLK record into a list of text lines."""
    lines: list[str] = []
    cur: list[str] = []
    for b in data:
        if b == TLK_LINE_BREAK:
            lines.append(''.join(cur))
            cur = []
            continue
        if b == TLK_RECORD_END:
            break
        ch = chr(b & 0x7F)
        cur.append(ch)
    if cur or not lines:
        lines.append(''.join(cur))
    return lines


def encode_record(lines: list[str]) -> bytes:
    """Encode text lines into a TLK binary record."""
    out = bytearray()
    for idx, line in enumerate(lines):
        if idx > 0:
            out.append(TLK_LINE_BREAK)
        for ch in line:
            out.append((ord(ch) & 0x7F) | 0x80)
    out.append(TLK_RECORD_END)
    return bytes(out)


def load_tlk_records(path: str) -> list[list[str]]:
    """Load a TLK file and return list of decoded records."""
    with open(path, 'rb') as f:
        data = f.read()

    records = []
    parts = data.split(bytes([TLK_RECORD_END]))
    for part in parts:
        if not part:
            continue
        records.append(decode_record(part + bytes([TLK_RECORD_END])))
    return records


def cmd_view(args) -> None:
    """View TLK dialog records."""
    path_or_dir = args.path

    if os.path.isdir(path_or_dir):
        # Batch view all TLK files
        tlk_files = []
        for letter in TLK_LETTERS:
            path = resolve_game_file(path_or_dir, 'TLK', letter)
            if path:
                tlk_files.append((letter, path))

        if not tlk_files:
            print(f"Error: No TLK files found in {path_or_dir}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            result = {}
            for letter, path in tlk_files:
                records = load_tlk_records(path)
                result[f'TLK{letter}'] = {
                    'location': TLK_NAMES.get(letter, 'Unknown'),
                    'records': [{'index': i, 'lines': rec} for i, rec in enumerate(records)],
                }
            export_json(result, args.output)
            return

        print(f"\n=== Ultima III Dialogs ({len(tlk_files)} files) ===\n")
        for letter, path in tlk_files:
            location = TLK_NAMES.get(letter, 'Unknown')
            records = load_tlk_records(path)
            print(f"  TLK{letter} - {location} ({len(records)} records)")
            for i, rec in enumerate(records):
                text = ' / '.join(rec)
                if len(text) > 72:
                    text = text[:69] + '...'
                print(f"    [{i:2d}] {text}")
            print()
    else:
        # Single file view
        records = load_tlk_records(path_or_dir)
        filename = os.path.basename(path_or_dir)

        if args.json:
            result = {'file': filename, 'records': [
                {'index': i, 'lines': rec} for i, rec in enumerate(records)
            ]}
            export_json(result, args.output)
            return

        print(f"\n=== TLK Dialog: {filename} ({len(records)} records) ===\n")
        for i, rec in enumerate(records):
            print(f"  Record {i}:")
            for line in rec:
                print(f"    {line}")
            print()


def cmd_extract(args) -> None:
    """Extract TLK binary to editable text file."""
    records = load_tlk_records(args.input)
    lines: list[str] = []
    for i, rec in enumerate(records):
        lines.append(f'# Record {i}')
        lines.extend(rec)
        lines.append('---')

    if lines and lines[-1] == '---':
        lines.pop()

    output = args.output
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"Extracted {len(records)} records to {output}")


def cmd_build(args) -> None:
    """Build TLK binary from editable text file."""
    with open(args.input, 'r', encoding='utf-8') as f:
        text = f.read()

    blocks = [b.strip() for b in text.split('\n---\n')]
    out = bytearray()

    for block in blocks:
        if not block:
            continue
        lines = []
        for line in block.splitlines():
            if line.strip().startswith('#'):
                continue
            lines.append(line.rstrip('\n'))
        out.extend(encode_record(lines))

    output = args.output
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'wb') as f:
        f.write(bytes(out))
    print(f"Built TLK ({len(out)} bytes) to {output}")


def cmd_edit(args) -> None:
    """Edit a specific record in-place."""
    records = load_tlk_records(args.file)

    if args.record < 0 or args.record >= len(records):
        print(f"Error: Record {args.record} out of range (0-{len(records)-1})",
              file=sys.stderr)
        sys.exit(1)

    records[args.record] = args.text.split('\\n')

    # Rebuild binary
    out = bytearray()
    for rec in records:
        out.extend(encode_record(rec))

    output = args.output if args.output else args.file
    with open(output, 'wb') as f:
        f.write(bytes(out))
    print(f"Updated record {args.record} in {output}")


def register_parser(subparsers) -> None:
    """Register tlk subcommands on a CLI subparser group."""
    p = subparsers.add_parser('tlk', help='Dialog text viewer/editor')
    sub = p.add_subparsers(dest='tlk_command')

    p_view = sub.add_parser('view', help='View dialog records')
    p_view.add_argument('path', help='TLK file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_extract = sub.add_parser('extract', help='Extract TLK to text')
    p_extract.add_argument('input', help='TLK binary file')
    p_extract.add_argument('output', help='Output text file')

    p_build = sub.add_parser('build', help='Build TLK from text')
    p_build.add_argument('input', help='Input text file')
    p_build.add_argument('output', help='Output TLK binary file')

    p_edit = sub.add_parser('edit', help='Edit a record in-place')
    p_edit.add_argument('file', help='TLK file')
    p_edit.add_argument('--record', type=int, required=True, help='Record index')
    p_edit.add_argument('--text', required=True, help='New text (use \\n for line breaks)')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite)')


def dispatch(args) -> None:
    """Dispatch tlk subcommand."""
    if args.tlk_command == 'view':
        cmd_view(args)
    elif args.tlk_command == 'extract':
        cmd_extract(args)
    elif args.tlk_command == 'build':
        cmd_build(args)
    elif args.tlk_command == 'edit':
        cmd_edit(args)
    else:
        print("Usage: u3edit tlk {view|extract|build|edit} ...", file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Dialog Text Viewer/Editor')
    sub = parser.add_subparsers(dest='tlk_command')

    p_view = sub.add_parser('view', help='View dialog records')
    p_view.add_argument('path', help='TLK file or GAME directory')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    p_extract = sub.add_parser('extract', help='Extract TLK to text')
    p_extract.add_argument('input', help='TLK binary file')
    p_extract.add_argument('output', help='Output text file')

    p_build = sub.add_parser('build', help='Build TLK from text')
    p_build.add_argument('input', help='Input text file')
    p_build.add_argument('output', help='Output TLK binary file')

    p_edit = sub.add_parser('edit', help='Edit a record in-place')
    p_edit.add_argument('file', help='TLK file')
    p_edit.add_argument('--record', type=int, required=True)
    p_edit.add_argument('--text', required=True)
    p_edit.add_argument('--output', '-o')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
