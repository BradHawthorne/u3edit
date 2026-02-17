"""Ultima III: Exodus - Combat Battlefield Viewer.

CON files: 192 bytes. Structure:
  0x00-0x78: 11x11 battlefield tiles (121 bytes)
  0x80-0x87: Monster start X positions (8 monsters)
  0x88-0x8F: Monster start Y positions (8 monsters)
  0xA0-0xA3: PC start X positions (4 PCs)
  0xA4-0xA7: PC start Y positions (4 PCs)
"""

import argparse
import os
import sys

from .constants import (
    CON_NAMES, CON_LETTERS, CON_FILE_SIZE,
    CON_MAP_WIDTH, CON_MAP_HEIGHT, CON_MAP_TILES,
    CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET, CON_MONSTER_COUNT,
    CON_PC_X_OFFSET, CON_PC_Y_OFFSET, CON_PC_COUNT,
    tile_char,
)
from .fileutil import resolve_game_file
from .json_export import export_json


class CombatMap:
    """A single combat battlefield."""

    def __init__(self, data: bytes):
        self.tiles = data[:CON_MAP_TILES]
        self.monster_x = [data[CON_MONSTER_X_OFFSET + i] if CON_MONSTER_X_OFFSET + i < len(data) else 0
                          for i in range(CON_MONSTER_COUNT)]
        self.monster_y = [data[CON_MONSTER_Y_OFFSET + i] if CON_MONSTER_Y_OFFSET + i < len(data) else 0
                          for i in range(CON_MONSTER_COUNT)]
        self.pc_x = [data[CON_PC_X_OFFSET + i] if CON_PC_X_OFFSET + i < len(data) else 0
                     for i in range(CON_PC_COUNT)]
        self.pc_y = [data[CON_PC_Y_OFFSET + i] if CON_PC_Y_OFFSET + i < len(data) else 0
                     for i in range(CON_PC_COUNT)]

    def render(self) -> str:
        """Render 11x11 battlefield with position overlays."""
        # Build base grid
        grid = []
        for y in range(CON_MAP_HEIGHT):
            row = []
            for x in range(CON_MAP_WIDTH):
                offset = y * CON_MAP_WIDTH + x
                if offset < len(self.tiles):
                    row.append(tile_char(self.tiles[offset]))
                else:
                    row.append(' ')
            grid.append(row)

        # Overlay monster positions
        for i in range(CON_MONSTER_COUNT):
            mx, my = self.monster_x[i], self.monster_y[i]
            if 0 <= mx < CON_MAP_WIDTH and 0 <= my < CON_MAP_HEIGHT:
                grid[my][mx] = 'm'

        # Overlay PC positions
        for i in range(CON_PC_COUNT):
            px, py = self.pc_x[i], self.pc_y[i]
            if 0 <= px < CON_MAP_WIDTH and 0 <= py < CON_MAP_HEIGHT:
                grid[py][px] = '@'

        lines = ['     ' + ''.join(f'{x}' for x in range(CON_MAP_WIDTH))]
        for y, row in enumerate(grid):
            lines.append(f'  {y:2d}  {"".join(row)}')
        return '\n'.join(lines)

    def to_dict(self) -> dict:
        return {
            'tiles': [[tile_char(self.tiles[y * CON_MAP_WIDTH + x])
                        for x in range(CON_MAP_WIDTH)]
                       for y in range(CON_MAP_HEIGHT)
                       if y * CON_MAP_WIDTH < len(self.tiles)],
            'monsters': [{'x': self.monster_x[i], 'y': self.monster_y[i]}
                         for i in range(CON_MONSTER_COUNT)
                         if self.monster_x[i] or self.monster_y[i]],
            'pcs': [{'x': self.pc_x[i], 'y': self.pc_y[i]}
                    for i in range(CON_PC_COUNT)],
        }


def cmd_view(args) -> None:
    path_or_dir = args.path

    if os.path.isdir(path_or_dir):
        con_files = []
        for letter in CON_LETTERS:
            path = resolve_game_file(path_or_dir, 'CON', letter)
            if path:
                con_files.append((letter, path))

        if not con_files:
            print(f"Error: No CON files found in {path_or_dir}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            result = {}
            for letter, path in con_files:
                with open(path, 'rb') as f:
                    data = f.read()
                cm = CombatMap(data)
                result[f'CON{letter}'] = {
                    'name': CON_NAMES.get(letter, 'Unknown'),
                    **cm.to_dict(),
                }
            export_json(result, args.output)
            return

        print(f"\n=== Ultima III Combat Maps ({len(con_files)} arenas) ===\n")
        for letter, path in con_files:
            name = CON_NAMES.get(letter, 'Unknown')
            with open(path, 'rb') as f:
                data = f.read()
            cm = CombatMap(data)
            print(f"  CON{letter} - {name}")
            print(cm.render())
            print(f"  Legend: @ = PC start, m = monster start")
            print()
    else:
        with open(path_or_dir, 'rb') as f:
            data = f.read()

        filename = os.path.basename(path_or_dir)

        if args.json:
            cm = CombatMap(data)
            result = {'file': filename, **cm.to_dict()}
            export_json(result, args.output)
            return

        cm = CombatMap(data)
        print(f"\n=== Combat Map: {filename} ({len(data)} bytes) ===\n")
        print(cm.render())
        print(f"\n  Legend: @ = PC start, m = monster start")
        print()


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('combat', help='Combat battlefield viewer')
    sub = p.add_subparsers(dest='combat_command')

    p_view = sub.add_parser('view', help='View combat maps')
    p_view.add_argument('path', help='CON file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')


def dispatch(args) -> None:
    if args.combat_command == 'view':
        cmd_view(args)
    else:
        print("Usage: u3edit combat view ...", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Combat Battlefield Viewer')
    sub = parser.add_subparsers(dest='combat_command')

    p_view = sub.add_parser('view', help='View combat maps')
    p_view.add_argument('path', help='CON file or GAME directory')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
