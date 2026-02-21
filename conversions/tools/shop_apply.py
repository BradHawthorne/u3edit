#!/usr/bin/env python3
"""Apply shop overlay string replacements by matching vanilla text.

Reads a shop_strings.json source file and applies string replacements
to SHP0-SHP7 overlay binaries. Unlike shapes import (which requires
exact byte offsets), this tool discovers inline strings at runtime by
scanning for the JSR $46BA pattern, then matches by vanilla text.

Usage:
    python3 shop_apply.py sources/shop_strings.json /path/to/GAME/
    python3 shop_apply.py sources/shop_strings.json /path/to/GAME/ --dry-run
    python3 shop_apply.py sources/shop_strings.json /path/to/GAME/ --backup
"""

import argparse
import glob
import json
import os
import shutil
import sys

# Add src to path so we can import u3edit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from u3edit.shapes import (
    extract_overlay_strings,
    replace_overlay_string,
)


def find_shp_file(game_dir, shp_name):
    """Find a SHP file, handling ProDOS #hash suffixes."""
    pattern = os.path.join(game_dir, shp_name + '#*')
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    plain = os.path.join(game_dir, shp_name)
    if os.path.exists(plain):
        return plain
    return None


def apply_shop_strings(json_path, game_dir, dry_run=False, backup=False):
    """Apply shop string replacements from JSON source to SHP files."""
    with open(json_path, 'r', encoding='utf-8') as f:
        source = json.load(f)

    shops = source.get('shops', {})
    total_replaced = 0
    total_skipped = 0

    for shp_name, shop_data in sorted(shops.items()):
        shp_path = find_shp_file(game_dir, shp_name)
        if shp_path is None:
            print(f"  {shp_name}: file not found, skipping")
            continue

        with open(shp_path, 'rb') as f:
            data = bytearray(f.read())

        # Discover all inline strings in this SHP
        found_strings = extract_overlay_strings(data)
        # Build lookup by text content (case-insensitive)
        text_map = {}
        for s in found_strings:
            text_map[s['text'].upper()] = s

        replaced = 0
        entries = shop_data.get('strings', [])
        shop_label = shop_data.get('name', shp_name)

        for entry in entries:
            vanilla = entry.get('vanilla', '')
            voidborn = entry.get('voidborn', '')
            if not vanilla or not voidborn:
                continue

            match = text_map.get(vanilla.upper())
            if match is None:
                print(f"  {shp_name} ({shop_label}): '{vanilla}' not found "
                      f"in binary, skipping", file=sys.stderr)
                total_skipped += 1
                continue

            try:
                data = replace_overlay_string(
                    data, match['text_offset'], match['text_end'], voidborn)
                replaced += 1
                total_replaced += 1
            except ValueError as e:
                print(f"  {shp_name} ({shop_label}): '{vanilla}' -> "
                      f"'{voidborn}': {e}", file=sys.stderr)
                total_skipped += 1

        if replaced > 0:
            print(f"  {shp_name} ({shop_label}): {replaced} string(s) replaced")
            if not dry_run:
                if backup:
                    bak = shp_path + '.bak'
                    if not os.path.exists(bak):
                        shutil.copy2(shp_path, bak)
                with open(shp_path, 'wb') as f:
                    f.write(bytes(data))

    if dry_run:
        print(f"\nDry run: {total_replaced} replacement(s) would be applied, "
              f"{total_skipped} skipped")
    else:
        print(f"\nApplied {total_replaced} replacement(s), "
              f"{total_skipped} skipped")

    return total_replaced, total_skipped


def main():
    parser = argparse.ArgumentParser(
        description='Apply shop overlay string replacements by text matching')
    parser.add_argument('json_file',
                        help='Path to shop_strings.json source file')
    parser.add_argument('game_dir',
                        help='Path to game directory containing SHP files')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be changed without writing')
    parser.add_argument('--backup', action='store_true',
                        help='Create .bak backup before modifying')
    args = parser.parse_args()

    if not os.path.isfile(args.json_file):
        print(f"Error: {args.json_file} not found", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(args.game_dir):
        print(f"Error: {args.game_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    apply_shop_strings(args.json_file, args.game_dir,
                       dry_run=args.dry_run, backup=args.backup)


if __name__ == '__main__':
    main()
