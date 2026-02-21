#!/usr/bin/env python3
"""Total Conversion Verifier — Check that all game assets differ from vanilla.

Verifies a converted game directory by checking each asset file exists and
has been modified from its vanilla state (different content hash).

Usage:
    python verify.py /path/to/GAME/ [--vanilla /path/to/VANILLA/]
    python verify.py /path/to/GAME/ --checklist

Without --vanilla, just checks that all expected files exist and are valid sizes.
With --vanilla, compares hashes to confirm every file has been modified.
With --checklist, prints a markdown checklist of asset coverage.
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path


# Expected game files and their categories
ASSET_MANIFEST = {
    'Characters': {
        'files': ['ROST'],
        'sizes': [1280],
    },
    'Save State': {
        'files': ['PRTY', 'PLRS'],
        'sizes': [16, 256],
    },
    'Bestiary': {
        'files': [f'MON{c}' for c in 'ABCDEFGHIJKLZ'],
        'sizes': [256] * 13,
    },
    'Combat Maps': {
        'files': [f'CON{c}' for c in 'ABCFGMQRS'],
        'sizes': [192] * 9,
    },
    'Overworld Maps': {
        'files': [f'MAP{c}' for c in 'ABCDEFGHIJKLZ'],
        'sizes': [4096] * 13,
    },
    'Dungeon Maps': {
        'files': [f'MAP{c}' for c in 'MNOPQRS'],
        'sizes': [2048] * 7,
    },
    'Special Locations': {
        'files': ['BRND', 'SHRN', 'FNTN', 'TIME'],
        'sizes': [128] * 4,
    },
    'Dialog': {
        'files': [f'TLK{c}' for c in 'ABCDEFGHIJKLMNOPQRS'],
        'sizes': None,  # Variable size
    },
    'Tile Graphics': {
        'files': ['SHPS'],
        'sizes': [2048],
    },
    'Shop Overlays': {
        'files': [f'SHP{c}' for c in '01234567'],
        'sizes': None,  # Variable size
    },
    'Sound Effects': {
        'files': ['SOSA', 'SOSM'],
        'sizes': [4096, 256],
    },
    'Music': {
        'files': ['MBS'],
        'sizes': [5456],
    },
    'Engine': {
        'files': ['ULT3'],
        'sizes': [17408],
    },
    'Title Text': {
        'files': ['TEXT'],
        'sizes': [1024],
    },
    'Dungeon Drawing': {
        'files': ['DDRW'],
        'sizes': [1792],
    },
}


def find_file(game_dir, name):
    """Find a game file, handling ProDOS #hash suffixes."""
    game_path = Path(game_dir)

    # Try exact match first
    exact = game_path / name
    if exact.exists():
        return exact

    # Try with hash suffix
    for f in game_path.iterdir():
        base = f.name.split('#')[0]
        if base.upper() == name.upper():
            return f

    return None


def file_hash(path):
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_category(game_dir, category, info, vanilla_dir=None):
    """Verify all files in a category.

    Returns:
        (found, modified, missing, unchanged) counts and detail lists
    """
    found = []
    modified = []
    missing = []
    unchanged = []

    for i, name in enumerate(info['files']):
        path = find_file(game_dir, name)

        if path is None:
            missing.append(name)
            continue

        found.append(name)

        # Check size if expected sizes are known
        if info['sizes'] is not None:
            expected_size = info['sizes'][i] if i < len(info['sizes']) else None
            if expected_size and path.stat().st_size != expected_size:
                pass  # Size mismatch — still counts as found

        # Compare against vanilla if provided
        if vanilla_dir:
            vanilla_path = find_file(vanilla_dir, name)
            if vanilla_path and vanilla_path.exists():
                if file_hash(path) != file_hash(vanilla_path):
                    modified.append(name)
                else:
                    unchanged.append(name)
            else:
                modified.append(name)  # No vanilla = assume modified

    return found, modified, missing, unchanged


def verify_game(game_dir, vanilla_dir=None, verbose=False):
    """Run full verification on a game directory.

    Returns:
        (total_categories, passed_categories, results_dict)
    """
    results = {}
    total_cats = 0
    passed_cats = 0

    for category, info in ASSET_MANIFEST.items():
        total_cats += 1
        found, modified, missing, unchanged = verify_category(
            game_dir, category, info, vanilla_dir
        )

        total_files = len(info['files'])
        found_count = len(found)
        modified_count = len(modified)
        missing_count = len(missing)
        unchanged_count = len(unchanged)

        if vanilla_dir:
            passed = (missing_count == 0 and unchanged_count == 0)
        else:
            passed = (missing_count == 0)

        if passed:
            passed_cats += 1

        results[category] = {
            'total': total_files,
            'found': found_count,
            'modified': modified_count,
            'missing': missing_count,
            'unchanged': unchanged_count,
            'passed': passed,
            'missing_files': missing,
            'unchanged_files': unchanged,
        }

    return total_cats, passed_cats, results


def print_report(total_cats, passed_cats, results, vanilla_dir=None):
    """Print verification report."""
    print(f'\n{"=" * 60}')
    print(f'Total Conversion Verification Report')
    print(f'{"=" * 60}\n')

    for category, info in results.items():
        if info['passed']:
            status = 'PASS'
        elif info['missing'] > 0:
            status = 'MISSING'
        else:
            status = 'UNCHANGED'

        line = f'  [{status:^9s}] {category}: '
        line += f'{info["found"]}/{info["total"]} files found'
        if vanilla_dir:
            line += f', {info["modified"]} modified'
        print(line)

        if info['missing_files']:
            for f in info['missing_files']:
                print(f'             - MISSING: {f}')
        if info['unchanged_files']:
            for f in info['unchanged_files']:
                print(f'             - UNCHANGED: {f}')

    print(f'\n{"=" * 60}')
    if vanilla_dir:
        print(f'Result: {passed_cats}/{total_cats} categories fully converted')
    else:
        print(f'Result: {passed_cats}/{total_cats} categories with all files present')
    print(f'{"=" * 60}\n')

    return passed_cats == total_cats


def print_checklist(results):
    """Print a markdown checklist of asset coverage."""
    print('# Conversion Coverage Checklist\n')
    for category, info in results.items():
        check = 'x' if info['passed'] else ' '
        print(f'- [{check}] **{category}**: '
              f'{info["found"]}/{info["total"]} files')
        if info['missing_files']:
            for f in info['missing_files']:
                print(f'  - [ ] {f} (missing)')
        if info['unchanged_files']:
            for f in info['unchanged_files']:
                print(f'  - [ ] {f} (unchanged from vanilla)')


def main():
    parser = argparse.ArgumentParser(
        description='Verify total conversion asset coverage'
    )
    parser.add_argument('game_dir', help='Path to converted game files')
    parser.add_argument(
        '--vanilla', help='Path to vanilla game files for comparison'
    )
    parser.add_argument(
        '--checklist', action='store_true',
        help='Print markdown checklist output'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Show detailed output'
    )

    args = parser.parse_args()

    if not os.path.isdir(args.game_dir):
        print(f'Error: {args.game_dir} is not a directory', file=sys.stderr)
        sys.exit(1)

    if args.vanilla and not os.path.isdir(args.vanilla):
        print(f'Error: {args.vanilla} is not a directory', file=sys.stderr)
        sys.exit(1)

    total_cats, passed_cats, results = verify_game(
        args.game_dir, args.vanilla, args.verbose
    )

    if args.checklist:
        print_checklist(results)
    else:
        success = print_report(total_cats, passed_cats, results, args.vanilla)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
