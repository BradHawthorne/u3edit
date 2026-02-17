"""Ultima III: Exodus - Spell Reference Tool.

Displays wizard and cleric spell lists with MP costs and descriptions.
"""

import argparse
import sys

from .constants import WIZARD_SPELLS, CLERIC_SPELLS
from .json_export import export_json


def cmd_view(args) -> None:
    """Display spell reference."""
    show_wizard = not args.cleric_only
    show_cleric = not args.wizard_only

    if args.json:
        result = {}
        if show_wizard:
            result['wizard'] = [{'index': i, 'name': n, 'mp': c}
                                for i, (n, c) in enumerate(WIZARD_SPELLS)]
        if show_cleric:
            result['cleric'] = [{'index': i, 'name': n, 'mp': c}
                                for i, (n, c) in enumerate(CLERIC_SPELLS)]
        export_json(result, args.output)
        return

    if show_wizard:
        print("\n=== Wizard Spells ===\n")
        print(f"  {'#':>2s}  {'Name':<16s}  {'MP':>3s}")
        print(f"  {'--':>2s}  {'----':<16s}  {'---':>3s}")
        for i, (name, cost) in enumerate(WIZARD_SPELLS):
            print(f"  {i+1:2d}  {name:<16s}  {cost:3d}")

    if show_cleric:
        print("\n=== Cleric Spells ===\n")
        print(f"  {'#':>2s}  {'Name':<16s}  {'MP':>3s}")
        print(f"  {'--':>2s}  {'----':<16s}  {'---':>3s}")
        for i, (name, cost) in enumerate(CLERIC_SPELLS):
            print(f"  {i+1:2d}  {name:<16s}  {cost:3d}")

    print()


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('spell', help='Spell reference')
    sub = p.add_subparsers(dest='spell_command')

    p_view = sub.add_parser('view', help='View spell lists')
    p_view.add_argument('--wizard-only', action='store_true', help='Show only wizard spells')
    p_view.add_argument('--cleric-only', action='store_true', help='Show only cleric spells')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')


def dispatch(args) -> None:
    if args.spell_command == 'view':
        cmd_view(args)
    else:
        print("Usage: u3edit spell view [--wizard-only|--cleric-only]", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Spell Reference')
    sub = parser.add_subparsers(dest='spell_command')

    p_view = sub.add_parser('view', help='View spell lists')
    p_view.add_argument('--wizard-only', action='store_true')
    p_view.add_argument('--cleric-only', action='store_true')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
