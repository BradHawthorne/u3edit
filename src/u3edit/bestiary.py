"""Ultima III: Exodus - Monster Bestiary Viewer/Editor.

Reads MON* files (256 bytes each, columnar format: 16 monsters x 10 attributes).
Each MON file represents monsters for a terrain/encounter type (A-L, Z).

Bug fixes from prototype:
  B-1: Replaced sparse/wrong TILE_NAMES with constants.MONSTER_NAMES + TILES lookup
  B-2: Removed dead code FLAG1_BITS dict
"""

import argparse
import json
import os
import sys

from .constants import (
    MON_FILE_SIZE, MON_ATTR_COUNT, MON_MONSTERS_PER_FILE, MON_ATTR_NAMES,
    MON_ATTR_TILE1, MON_ATTR_TILE2, MON_ATTR_FLAGS1, MON_ATTR_FLAGS2,
    MON_ATTR_HP, MON_ATTR_ATTACK, MON_ATTR_DEFENSE, MON_ATTR_SPEED,
    MON_ATTR_ABILITY1, MON_ATTR_ABILITY2,
    MON_FLAG1_UNDEAD, MON_FLAG1_RANGED, MON_FLAG1_MAGIC_USER, MON_FLAG1_BOSS,
    MON_ABIL1_POISON, MON_ABIL1_SLEEP, MON_ABIL1_NEGATE,
    MON_ABIL1_TELEPORT, MON_ABIL1_DIVIDE,
    MON_ABIL2_RESISTANT,
    MON_TERRAIN, MON_LETTERS, MONSTER_NAMES, MONSTER_NAMES_REVERSE,
    MON_GROUP_NAMES, TILES,
)
from .fileutil import resolve_game_file, backup_file
from .json_export import export_json


class Monster:
    """A single monster extracted from columnar MON data."""

    def __init__(self, attrs: list[int], index: int, file_letter: str = ''):
        self.index = index
        self.file_letter = file_letter
        self.tile1 = attrs[MON_ATTR_TILE1]
        self.tile2 = attrs[MON_ATTR_TILE2]
        self.flags1 = attrs[MON_ATTR_FLAGS1]
        self.flags2 = attrs[MON_ATTR_FLAGS2]
        self.hp = attrs[MON_ATTR_HP]
        self.attack = attrs[MON_ATTR_ATTACK]
        self.defense = attrs[MON_ATTR_DEFENSE]
        self.speed = attrs[MON_ATTR_SPEED]
        self.ability1 = attrs[MON_ATTR_ABILITY1]
        self.ability2 = attrs[MON_ATTR_ABILITY2]

    @property
    def is_empty(self) -> bool:
        return self.tile1 == 0 and self.hp == 0

    @property
    def name(self) -> str:
        n = MONSTER_NAMES.get(self.tile1)
        if n:
            return n
        entry = TILES.get(self.tile1 & 0xFC)
        if entry:
            return entry[1]
        return f'Creature ${self.tile1:02X}'

    @property
    def flag_desc(self) -> str:
        desc = []
        f1 = self.flags1
        if f1 & 0x0C == MON_FLAG1_MAGIC_USER:
            desc.append('Magic User')
        else:
            if f1 & MON_FLAG1_UNDEAD:
                desc.append('Undead')
            if f1 & MON_FLAG1_RANGED:
                desc.append('Ranged')
        if f1 & MON_FLAG1_BOSS:
            desc.append('Boss')
        return ', '.join(desc) if desc else '-'

    @property
    def ability_desc(self) -> str:
        desc = []
        a1 = self.ability1
        if a1 & MON_ABIL1_POISON:
            desc.append('Poison')
        if a1 & MON_ABIL1_SLEEP:
            desc.append('Sleep')
        if a1 & MON_ABIL1_NEGATE:
            desc.append('Negate')
        if a1 & MON_ABIL1_TELEPORT:
            desc.append('Teleport')
        if a1 & MON_ABIL1_DIVIDE:
            desc.append('Divide')
        a2 = self.ability2
        if a2 & MON_ABIL2_RESISTANT:
            desc.append('Resistant')
        return ', '.join(desc) if desc else '-'

    def to_dict(self) -> dict:
        return {
            'index': self.index,
            'name': self.name,
            'tile1': self.tile1,
            'tile2': self.tile2,
            'hp': self.hp,
            'attack': self.attack,
            'defense': self.defense,
            'speed': self.speed,
            'flags1': self.flags1,
            'flags2': self.flags2,
            'ability1': self.ability1,
            'ability2': self.ability2,
            'flags': self.flag_desc,
            'abilities': self.ability_desc,
        }

    def display(self, compact: bool = False) -> None:
        if self.is_empty:
            return
        if compact:
            print(f"    [{self.index:2d}] ${self.tile1:02X} {self.name:<16s}  "
                  f"HP:{self.hp:3d}  ATK:{self.attack:3d}  DEF:{self.defense:3d}  "
                  f"SPD:{self.speed:3d}  {self.flag_desc}")
        else:
            print(f"    Monster #{self.index}")
            print(f"      Type:     {self.name} (tile ${self.tile1:02X}/${self.tile2:02X})")
            print(f"      HP:       {self.hp}")
            print(f"      Attack:   {self.attack}")
            print(f"      Defense:  {self.defense}")
            print(f"      Speed:    {self.speed}")
            print(f"      Flags:    {self.flag_desc} (${self.flags1:02X}/${self.flags2:02X})")
            print(f"      Ability:  {self.ability_desc} (${self.ability1:02X}/${self.ability2:02X})")
            print()


def load_mon_file(path: str, file_letter: str = '') -> list[Monster]:
    """Load a MON file and extract 16 monsters from columnar format."""
    with open(path, 'rb') as f:
        data = f.read()

    if len(data) < MON_ATTR_COUNT * MON_MONSTERS_PER_FILE:
        print(f"Warning: MON file too small ({len(data)} bytes)", file=sys.stderr)
        return []

    monsters = []
    for i in range(MON_MONSTERS_PER_FILE):
        attrs = []
        for row in range(MON_ATTR_COUNT):
            offset = row * MON_MONSTERS_PER_FILE + i
            attrs.append(data[offset] if offset < len(data) else 0)
        monsters.append(Monster(attrs, i, file_letter))
    return monsters


def save_mon_file(path: str, monsters: list[Monster],
                   original_data: bytes | None = None) -> None:
    """Write monsters back to columnar MON format, preserving unknown rows."""
    data = bytearray(original_data) if original_data else bytearray(MON_FILE_SIZE)
    for m in monsters:
        attrs = [m.tile1, m.tile2, m.flags1, m.flags2,
                 m.hp, m.attack, m.defense, m.speed,
                 m.ability1, m.ability2]
        for row, val in enumerate(attrs):
            data[row * MON_MONSTERS_PER_FILE + m.index] = val
    with open(path, 'wb') as f:
        f.write(data)
    print(f"Saved to {path}")


def cmd_view(args) -> None:
    game_dir = args.game_dir

    mon_files = []
    for letter in MON_LETTERS:
        path = resolve_game_file(game_dir, 'MON', letter)
        if path:
            mon_files.append((letter, path))

    if not mon_files:
        print(f"Error: No MON files found in {game_dir}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        result = {}
        for letter, path in mon_files:
            if args.file and args.file.upper() != f'MON{letter}':
                continue
            monsters = load_mon_file(path, letter)
            result[f'MON{letter}'] = {
                'terrain': MON_TERRAIN.get(letter, 'Unknown'),
                'monsters': [m.to_dict() for m in monsters if not m.is_empty],
            }
        export_json(result, args.output)
        return

    print(f"\n=== Ultima III Bestiary ({len(mon_files)} encounter files) ===\n")

    total_monsters = 0
    for letter, path in mon_files:
        terrain = MON_TERRAIN.get(letter, 'Unknown')
        if args.file and args.file.upper() != f'MON{letter}':
            continue

        monsters = load_mon_file(path, letter)
        active = [m for m in monsters if not m.is_empty]
        total_monsters += len(active)

        print(f"  MON{letter} - {terrain} ({len(active)} monsters)")
        print(f"  {'':4s}{'#':>4s} {'Tile':4s} {'Type':<16s}  {'HP':>3s}  {'ATK':>3s}  {'DEF':>3s}  {'SPD':>3s}  Flags")
        print(f"  {'':4s}{'---':>4s} {'----':4s} {'----':<16s}  {'---':>3s}  {'---':>3s}  {'---':>3s}  {'---':>3s}  -----")

        for m in monsters:
            if not m.is_empty:
                m.display(compact=True)
        print()

    if not args.file:
        print(f"  Total: {total_monsters} monsters across {len(mon_files)} encounter types\n")


def cmd_dump(args) -> None:
    """Raw hex dump of a MON file."""
    monsters = load_mon_file(args.file)
    filename = os.path.basename(args.file)

    with open(args.file, 'rb') as f:
        data = f.read()

    print(f"\n=== MON File Dump: {filename} ===\n")
    print("  Columnar view (rows = attributes, columns = monsters):\n")

    for row in range(min(MON_ATTR_COUNT, len(data) // MON_MONSTERS_PER_FILE)):
        offset = row * MON_MONSTERS_PER_FILE
        hex_str = ' '.join(f'{data[offset+i]:02X}' for i in range(MON_MONSTERS_PER_FILE))
        print(f"    {MON_ATTR_NAMES[row]:>10s}: {hex_str}")

    print(f"\n  Per-monster view:\n")
    for m in monsters:
        m.display(compact=False)


def _apply_edits(monster: Monster, args) -> bool:
    """Apply CLI edit flags to a monster. Returns True if anything changed."""
    modified = False

    # Basic numeric attributes
    if getattr(args, 'hp', None) is not None:
        monster.hp = max(0, min(255, args.hp)); modified = True
    if getattr(args, 'attack', None) is not None:
        monster.attack = max(0, min(255, args.attack)); modified = True
    if getattr(args, 'defense', None) is not None:
        monster.defense = max(0, min(255, args.defense)); modified = True
    if getattr(args, 'speed', None) is not None:
        monster.speed = max(0, min(255, args.speed)); modified = True
    if getattr(args, 'tile1', None) is not None:
        monster.tile1 = max(0, min(255, args.tile1)); modified = True
    if getattr(args, 'tile2', None) is not None:
        monster.tile2 = max(0, min(255, args.tile2)); modified = True
    if getattr(args, 'flags1', None) is not None:
        monster.flags1 = max(0, min(255, args.flags1)); modified = True
    if getattr(args, 'flags2', None) is not None:
        monster.flags2 = max(0, min(255, args.flags2)); modified = True
    if getattr(args, 'ability1', None) is not None:
        monster.ability1 = max(0, min(255, args.ability1)); modified = True
    if getattr(args, 'ability2', None) is not None:
        monster.ability2 = max(0, min(255, args.ability2)); modified = True

    # Monster type by name (--type Dragon)
    type_name = getattr(args, 'type', None)
    if type_name is not None:
        tile = MONSTER_NAMES_REVERSE.get(type_name.lower())
        if tile is not None:
            monster.tile1 = tile
            monster.tile2 = tile
            modified = True
        else:
            print(f"Warning: Unknown monster type '{type_name}'", file=sys.stderr)

    # Named flag toggles (flags1 byte, bits 2-3 are mutually exclusive)
    if getattr(args, 'undead', False):
        monster.flags1 = (monster.flags1 & ~0x0C) | MON_FLAG1_UNDEAD; modified = True
    if getattr(args, 'ranged', False):
        monster.flags1 = (monster.flags1 & ~0x0C) | MON_FLAG1_RANGED; modified = True
    if getattr(args, 'magic_user', False):
        monster.flags1 = (monster.flags1 & ~0x0C) | MON_FLAG1_MAGIC_USER; modified = True
    if getattr(args, 'boss', False):
        monster.flags1 |= MON_FLAG1_BOSS; modified = True
    if getattr(args, 'no_boss', False):
        monster.flags1 &= ~MON_FLAG1_BOSS; modified = True

    # Named ability toggles (ability1 byte)
    if getattr(args, 'poison', False):
        monster.ability1 |= MON_ABIL1_POISON; modified = True
    if getattr(args, 'no_poison', False):
        monster.ability1 &= ~MON_ABIL1_POISON; modified = True
    if getattr(args, 'sleep', False):
        monster.ability1 |= MON_ABIL1_SLEEP; modified = True
    if getattr(args, 'no_sleep', False):
        monster.ability1 &= ~MON_ABIL1_SLEEP; modified = True
    if getattr(args, 'negate', False):
        monster.ability1 |= MON_ABIL1_NEGATE; modified = True
    if getattr(args, 'no_negate', False):
        monster.ability1 &= ~MON_ABIL1_NEGATE; modified = True
    if getattr(args, 'teleport', False):
        monster.ability1 |= MON_ABIL1_TELEPORT; modified = True
    if getattr(args, 'no_teleport', False):
        monster.ability1 &= ~MON_ABIL1_TELEPORT; modified = True
    if getattr(args, 'divide', False):
        monster.ability1 |= MON_ABIL1_DIVIDE; modified = True
    if getattr(args, 'no_divide', False):
        monster.ability1 &= ~MON_ABIL1_DIVIDE; modified = True

    # Named ability toggle (ability2 byte)
    if getattr(args, 'resistant', False):
        monster.ability2 |= MON_ABIL2_RESISTANT; modified = True
    if getattr(args, 'no_resistant', False):
        monster.ability2 &= ~MON_ABIL2_RESISTANT; modified = True

    return modified


def cmd_edit(args) -> None:
    """Edit monster attributes in a MON file."""
    with open(args.file, 'rb') as f:
        original_data = f.read()
    monsters = load_mon_file(args.file)
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)
    edit_all = getattr(args, 'all', False)

    if edit_all:
        modified = False
        for m in monsters:
            if not m.is_empty:
                if _apply_edits(m, args):
                    print(f"Modified monster #{m.index}:")
                    m.display(compact=False)
                    modified = True
        if not modified:
            print("No modifications specified.")
            return
    else:
        monster_idx = getattr(args, 'monster', None)
        if monster_idx is None:
            print("Error: --monster or --all required", file=sys.stderr)
            sys.exit(1)
        if monster_idx < 0 or monster_idx >= MON_MONSTERS_PER_FILE:
            print("Error: Monster index must be 0-15", file=sys.stderr)
            sys.exit(1)

        m = monsters[monster_idx]
        if not _apply_edits(m, args):
            print("No modifications specified.")
            return
        print(f"Modified monster #{monster_idx}:")
        m.display(compact=False)

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    save_mon_file(output, monsters, original_data)


def cmd_import(args) -> None:
    """Import monster data from JSON into a MON file."""
    with open(args.file, 'rb') as f:
        original_data = f.read()
    monsters = load_mon_file(args.file)
    do_backup = getattr(args, 'backup', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Accept either a list of monsters or a dict with 'monsters' key
    mon_list = data if isinstance(data, list) else data.get('monsters', [])
    count = 0
    for entry in mon_list:
        idx = entry.get('index')
        if idx is None or not (0 <= idx < MON_MONSTERS_PER_FILE):
            continue
        m = monsters[idx]
        for attr in ('tile1', 'tile2', 'hp', 'attack', 'defense', 'speed',
                     'flags1', 'flags2', 'ability1', 'ability2'):
            if attr in entry:
                setattr(m, attr, max(0, min(255, entry[attr])))
        count += 1

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    save_mon_file(output, monsters, original_data)
    print(f"Imported {count} monster(s)")


def _add_mon_edit_args(p) -> None:
    """Add common monster edit arguments to a parser."""
    p.add_argument('--hp', type=int, help='Hit points (0-255)')
    p.add_argument('--attack', type=int, help='Attack value (0-255)')
    p.add_argument('--defense', type=int, help='Defense value (0-255)')
    p.add_argument('--speed', type=int, help='Speed value (0-255)')
    p.add_argument('--tile1', type=int, help='Tile/sprite byte 1 (0-255)')
    p.add_argument('--tile2', type=int, help='Tile/sprite byte 2 (0-255)')
    p.add_argument('--flags1', type=int, help='Flags byte 1 raw (0-255)')
    p.add_argument('--flags2', type=int, help='Flags byte 2 raw (0-255)')
    p.add_argument('--ability1', type=int, help='Ability byte 1 raw (0-255)')
    p.add_argument('--ability2', type=int, help='Ability byte 2 raw (0-255)')
    p.add_argument('--type', help='Monster type by name (e.g., Dragon, Skeleton)')


def _add_mon_flag_args(p) -> None:
    """Add named flag/ability toggle arguments to a parser."""
    # Flags1 bits 2-3: mutually exclusive undead/ranged/magic-user
    flag_group = p.add_mutually_exclusive_group()
    flag_group.add_argument('--undead', action='store_true', help='Set Undead flag')
    flag_group.add_argument('--ranged', action='store_true', help='Set Ranged flag')
    flag_group.add_argument('--magic-user', action='store_true', dest='magic_user',
                            help='Set Magic User flag')
    p.add_argument('--boss', action='store_true', help='Set Boss flag')
    p.add_argument('--no-boss', action='store_true', dest='no_boss', help='Clear Boss flag')
    # Ability1 toggles
    p.add_argument('--poison', action='store_true', help='Set Poison ability')
    p.add_argument('--no-poison', action='store_true', dest='no_poison', help='Clear Poison')
    p.add_argument('--sleep', action='store_true', help='Set Sleep ability')
    p.add_argument('--no-sleep', action='store_true', dest='no_sleep', help='Clear Sleep')
    p.add_argument('--negate', action='store_true', help='Set Negate ability')
    p.add_argument('--no-negate', action='store_true', dest='no_negate', help='Clear Negate')
    p.add_argument('--teleport', action='store_true', help='Set Teleport ability')
    p.add_argument('--no-teleport', action='store_true', dest='no_teleport', help='Clear Teleport')
    p.add_argument('--divide', action='store_true', help='Set Divide ability')
    p.add_argument('--no-divide', action='store_true', dest='no_divide', help='Clear Divide')
    # Ability2 toggles
    p.add_argument('--resistant', action='store_true', help='Set Resistant ability')
    p.add_argument('--no-resistant', action='store_true', dest='no_resistant',
                   help='Clear Resistant')


def register_parser(subparsers) -> None:
    """Register bestiary subcommands on a CLI subparser group."""
    p = subparsers.add_parser('bestiary', help='Monster bestiary viewer/editor')
    sub = p.add_subparsers(dest='bestiary_command')

    p_view = sub.add_parser('view', help='View all monsters')
    p_view.add_argument('game_dir', help='GAME directory containing MON* files')
    p_view.add_argument('--file', help='Show only specific MON file (e.g., MONA)')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_dump = sub.add_parser('dump', help='Raw dump of a MON file')
    p_dump.add_argument('file', help='MON file path')

    p_edit = sub.add_parser('edit', help='Edit a monster')
    p_edit.add_argument('file', help='MON file path')
    mon_group = p_edit.add_mutually_exclusive_group(required=True)
    mon_group.add_argument('--monster', type=int, help='Monster index (0-15)')
    mon_group.add_argument('--all', action='store_true', help='Edit all non-empty monsters')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_edit.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    _add_mon_edit_args(p_edit)
    _add_mon_flag_args(p_edit)

    p_import = sub.add_parser('import', help='Import monsters from JSON')
    p_import.add_argument('file', help='MON file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')


def dispatch(args) -> None:
    """Dispatch bestiary subcommand."""
    if args.bestiary_command == 'view':
        cmd_view(args)
    elif args.bestiary_command == 'dump':
        cmd_dump(args)
    elif args.bestiary_command == 'edit':
        cmd_edit(args)
    elif args.bestiary_command == 'import':
        cmd_import(args)
    else:
        print("Usage: u3edit bestiary {view|dump|edit|import} ...", file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Monster Bestiary Viewer/Editor')
    sub = parser.add_subparsers(dest='bestiary_command')

    p_view = sub.add_parser('view', help='View all monsters')
    p_view.add_argument('game_dir', help='GAME directory containing MON* files')
    p_view.add_argument('--file', help='Show only specific MON file')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    p_dump = sub.add_parser('dump', help='Raw dump of a MON file')
    p_dump.add_argument('file', help='MON file path')

    p_edit = sub.add_parser('edit', help='Edit a monster')
    p_edit.add_argument('file', help='MON file path')
    mon_group = p_edit.add_mutually_exclusive_group(required=True)
    mon_group.add_argument('--monster', type=int, help='Monster index (0-15)')
    mon_group.add_argument('--all', action='store_true', help='Edit all non-empty monsters')
    p_edit.add_argument('--output', '-o')
    p_edit.add_argument('--backup', action='store_true')
    p_edit.add_argument('--dry-run', action='store_true')
    _add_mon_edit_args(p_edit)
    _add_mon_flag_args(p_edit)

    p_import = sub.add_parser('import', help='Import monsters from JSON')
    p_import.add_argument('file', help='MON file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o')
    p_import.add_argument('--backup', action='store_true')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
