"""Ultima III: Exodus - Equipment Reference Tool.

Displays weapon and armor stats including damage, prices, evasion rates,
and class equipment restrictions.
"""

import argparse
import sys

from .constants import (
    WEAPONS, ARMORS, WEAPON_DAMAGE, WEAPON_PRICE, ARMOR_EVASION,
    CLASS_MAX_WEAPON, CLASS_MAX_ARMOR, CLASSES,
)
from .json_export import export_json


def cmd_view(args) -> None:
    """Display equipment reference."""
    if args.json:
        result = {
            'weapons': [
                {'index': i, 'name': n, 'damage': WEAPON_DAMAGE[i], 'price': WEAPON_PRICE[i]}
                for i, n in enumerate(WEAPONS)
            ],
            'armors': [
                {'index': i, 'name': n, 'evasion': ARMOR_EVASION[i]}
                for i, n in enumerate(ARMORS)
            ],
            'class_restrictions': {
                cls: {'max_weapon': WEAPONS[CLASS_MAX_WEAPON[cls]],
                      'max_armor': ARMORS[CLASS_MAX_ARMOR[cls]]}
                for cls in CLASSES.values()
            },
        }
        export_json(result, args.output)
        return

    print("\n=== Weapons ===\n")
    print(f"  {'#':>2s}  {'Name':<12s}  {'Dmg':>3s}  {'Price':>5s}")
    print(f"  {'--':>2s}  {'----':<12s}  {'---':>3s}  {'-----':>5s}")
    for i, name in enumerate(WEAPONS):
        print(f"  {i:2d}  {name:<12s}  {WEAPON_DAMAGE[i]:3d}  {WEAPON_PRICE[i]:5d}")

    print("\n=== Armor ===\n")
    print(f"  {'#':>2s}  {'Name':<12s}  {'Evasion':>7s}")
    print(f"  {'--':>2s}  {'----':<12s}  {'-------':>7s}")
    for i, name in enumerate(ARMORS):
        print(f"  {i:2d}  {name:<12s}  {ARMOR_EVASION[i]:5.1f}%")

    print("\n=== Class Equipment Restrictions ===\n")
    print(f"  {'Class':<12s}  {'Best Weapon':<12s}  {'Best Armor':<12s}")
    print(f"  {'-----':<12s}  {'-----------':<12s}  {'----------':<12s}")
    for cls in CLASSES.values():
        best_wpn = WEAPONS[CLASS_MAX_WEAPON[cls]]
        best_arm = ARMORS[CLASS_MAX_ARMOR[cls]]
        print(f"  {cls:<12s}  {best_wpn:<12s}  {best_arm:<12s}")

    print()


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('equip', help='Equipment reference')
    sub = p.add_subparsers(dest='equip_command')

    p_view = sub.add_parser('view', help='View equipment stats and class restrictions')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')


def dispatch(args) -> None:
    if args.equip_command == 'view':
        cmd_view(args)
    else:
        print("Usage: u3edit equip view", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Equipment Reference')
    sub = parser.add_subparsers(dest='equip_command')

    p_view = sub.add_parser('view', help='View equipment stats')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
