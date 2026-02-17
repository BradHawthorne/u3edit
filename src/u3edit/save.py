"""Ultima III: Exodus - Save State Viewer/Editor.

Reads multiple save files from a GAME directory:
  SOSA (4096 bytes) - Overworld map state (64x64 tiles)
  PRTY (16 bytes) - Transport, location type, coordinates, party size, slot IDs
  PLRS (256 bytes) - 4 active character records (4x64 bytes)
  SOSM (256 bytes) - Overworld monster positions
"""

import argparse
import os
import sys

from .constants import (
    PRTY_TRANSPORT, PRTY_TRANSPORT_CODES, PRTY_LOCATION_TYPE,
    PRTY_FILE_SIZE, PLRS_FILE_SIZE, SOSA_FILE_SIZE, SOSM_FILE_SIZE,
    CHAR_RECORD_SIZE, tile_char,
)
from .fileutil import resolve_game_file
from .roster import Character
from .json_export import export_json


class PartyState:
    """Party state from PRTY file (16 bytes)."""

    def __init__(self, data: bytes):
        assert len(data) >= PRTY_FILE_SIZE
        self.raw = bytearray(data[:PRTY_FILE_SIZE])

    @property
    def transport(self) -> str:
        return PRTY_TRANSPORT.get(self.raw[0], f'Unknown(${self.raw[0]:02X})')

    @transport.setter
    def transport(self, name: str) -> None:
        code = PRTY_TRANSPORT_CODES.get(name.lower())
        if code is not None:
            self.raw[0] = code

    @property
    def location_type(self) -> str:
        return PRTY_LOCATION_TYPE.get(self.raw[1], f'Unknown(${self.raw[1]:02X})')

    @property
    def x(self) -> int:
        return self.raw[2]

    @x.setter
    def x(self, val: int) -> None:
        self.raw[2] = max(0, min(63, val))

    @property
    def y(self) -> int:
        return self.raw[3]

    @y.setter
    def y(self, val: int) -> None:
        self.raw[3] = max(0, min(63, val))

    @property
    def party_size(self) -> int:
        return self.raw[4]

    @property
    def slot_ids(self) -> list[int]:
        return [self.raw[5 + i] for i in range(4)]

    def to_dict(self) -> dict:
        return {
            'transport': self.transport,
            'location_type': self.location_type,
            'x': self.x, 'y': self.y,
            'party_size': self.party_size,
            'slot_ids': self.slot_ids,
        }

    def display(self) -> None:
        print(f"  Transport:     {self.transport}")
        print(f"  Location:      {self.location_type}")
        print(f"  Coordinates:   ({self.x}, {self.y})")
        print(f"  Party size:    {self.party_size}")
        print(f"  Roster slots:  {self.slot_ids}")


def cmd_view(args) -> None:
    game_dir = args.game_dir

    # Load PRTY
    prty_path = resolve_game_file(game_dir, 'PRTY', '')
    if not prty_path:
        # Try without letter
        prty_path = resolve_game_file(game_dir, 'PRT', 'Y')
    # Try plain name
    if not prty_path:
        candidate = os.path.join(game_dir, 'PRTY')
        if os.path.isfile(candidate):
            prty_path = candidate
    # Try with hash
    if not prty_path:
        import glob
        matches = glob.glob(os.path.join(game_dir, 'PRTY#*'))
        if matches:
            prty_path = matches[0]

    if not prty_path:
        print(f"Error: PRTY file not found in {game_dir}", file=sys.stderr)
        sys.exit(1)

    with open(prty_path, 'rb') as f:
        prty_data = f.read()
    party = PartyState(prty_data)

    # Load PLRS
    plrs_path = None
    import glob as _glob
    for pattern in ['PLRS#*', 'PLRS']:
        matches = _glob.glob(os.path.join(game_dir, pattern))
        if matches:
            plrs_path = matches[0]
            break

    active_chars = []
    if plrs_path:
        with open(plrs_path, 'rb') as f:
            plrs_data = f.read()
        for i in range(min(4, len(plrs_data) // CHAR_RECORD_SIZE)):
            offset = i * CHAR_RECORD_SIZE
            active_chars.append(Character(plrs_data[offset:offset + CHAR_RECORD_SIZE]))

    if args.json:
        result = {
            'party': party.to_dict(),
            'active_characters': [c.to_dict() for c in active_chars if not c.is_empty],
        }
        export_json(result, args.output)
        return

    print(f"\n=== Ultima III Save State ===\n")
    print(f"  --- Party Info (PRTY) ---")
    party.display()

    if active_chars:
        print(f"\n  --- Active Characters (PLRS) ---\n")
        for i, char in enumerate(active_chars):
            if not char.is_empty:
                char.display(i)

    # Load SOSA for mini-map if available
    sosa_path = None
    for pattern in ['SOSA#*', 'SOSA']:
        matches = _glob.glob(os.path.join(game_dir, pattern))
        if matches:
            sosa_path = matches[0]
            break

    if sosa_path and not args.brief:
        with open(sosa_path, 'rb') as f:
            sosa_data = f.read()
        print(f"  --- Overworld State (SOSA, scaled 4:1) ---\n")
        for y in range(0, 64, 4):
            row = '  '
            for x in range(0, 64, 2):
                offset = y * 64 + x
                if offset < len(sosa_data):
                    ch = tile_char(sosa_data[offset])
                    # Mark party position
                    if abs(x - party.x) <= 1 and abs(y - party.y) <= 1:
                        ch = '@'
                    row += ch
                else:
                    row += ' '
            print(row)

    print()


def cmd_edit(args) -> None:
    game_dir = args.game_dir

    import glob as _glob
    prty_path = None
    for pattern in ['PRTY#*', 'PRTY']:
        matches = _glob.glob(os.path.join(game_dir, pattern))
        if matches:
            prty_path = matches[0]
            break

    if not prty_path:
        print(f"Error: PRTY file not found in {game_dir}", file=sys.stderr)
        sys.exit(1)

    with open(prty_path, 'rb') as f:
        data = bytearray(f.read())
    party = PartyState(data)

    modified = False
    if args.transport is not None:
        party.transport = args.transport; modified = True
    if args.x is not None:
        party.x = args.x; modified = True
    if args.y is not None:
        party.y = args.y; modified = True

    if modified:
        output = args.output if args.output else prty_path
        with open(output, 'wb') as f:
            f.write(bytes(party.raw) + data[PRTY_FILE_SIZE:])
        print(f"Saved party state to {output}")
        party.display()
    else:
        print("No modifications specified.")


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('save', help='Save state viewer/editor')
    sub = p.add_subparsers(dest='save_command')

    p_view = sub.add_parser('view', help='View save state')
    p_view.add_argument('game_dir', help='GAME directory')
    p_view.add_argument('--brief', action='store_true', help='Skip overworld map')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Edit party state')
    p_edit.add_argument('game_dir', help='GAME directory')
    p_edit.add_argument('--transport', help='Transport: horse, ship, foot')
    p_edit.add_argument('--x', type=int, help='X coordinate (0-63)')
    p_edit.add_argument('--y', type=int, help='Y coordinate (0-63)')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite PRTY)')


def dispatch(args) -> None:
    if args.save_command == 'view':
        cmd_view(args)
    elif args.save_command == 'edit':
        cmd_edit(args)
    else:
        print("Usage: u3edit save {view|edit} ...", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Save State Viewer/Editor')
    sub = parser.add_subparsers(dest='save_command')

    p_view = sub.add_parser('view', help='View save state')
    p_view.add_argument('game_dir', help='GAME directory')
    p_view.add_argument('--brief', action='store_true')
    p_view.add_argument('--json', action='store_true')
    p_view.add_argument('--output', '-o')

    p_edit = sub.add_parser('edit', help='Edit party state')
    p_edit.add_argument('game_dir', help='GAME directory')
    p_edit.add_argument('--transport')
    p_edit.add_argument('--x', type=int)
    p_edit.add_argument('--y', type=int)
    p_edit.add_argument('--output', '-o')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
