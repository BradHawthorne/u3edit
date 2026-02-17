"""Ultima III: Exodus - Game Text Viewer.

TEXT file: 1024 bytes of high-bit ASCII strings, null-terminated records.
Contains in-game text strings used by the engine.
"""

import argparse
import os
import sys

from .constants import TEXT_FILE_SIZE
from .fileutil import decode_high_ascii
from .json_export import export_json


def load_text_records(path: str) -> list[str]:
    """Load TEXT file and split into null-terminated string records."""
    with open(path, 'rb') as f:
        data = f.read()

    records = []
    parts = data.split(b'\x00')
    for part in parts:
        if not part:
            continue
        text = decode_high_ascii(part)
        if text.strip():
            records.append(text)
    return records


def cmd_view(args) -> None:
    records = load_text_records(args.file)
    filename = os.path.basename(args.file)

    if args.json:
        result = {
            'file': filename,
            'records': [{'index': i, 'text': rec} for i, rec in enumerate(records)],
        }
        export_json(result, args.output)
        return

    print(f"\n=== Ultima III Game Text: {filename} ({len(records)} strings) ===\n")
    for i, rec in enumerate(records):
        print(f"  [{i:3d}] {rec}")
    print()


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('text', help='Game text viewer')
    sub = p.add_subparsers(dest='text_command')

    p_view = sub.add_parser('view', help='View game text strings')
    p_view.add_argument('file', help='TEXT file path')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')


def dispatch(args) -> None:
    if args.text_command == 'view':
        cmd_view(args)
    else:
        print("Usage: u3edit text view ...", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Game Text Viewer')
    sub = parser.add_subparsers(dest='text_command')

    p_view = sub.add_parser('view', help='View game text strings')
    p_view.add_argument('file', help='TEXT file path')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
