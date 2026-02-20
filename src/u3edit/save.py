"""Ultima III: Exodus - Save State Viewer/Editor.

Reads multiple save files from a GAME directory:
  SOSA (4096 bytes) - Overworld map state (64x64 tiles)
  PRTY (16 bytes) - Party state at zero-page $E0-$EF:
    $E0: transport mode, $E1: party size (0-4), $E2: location type,
    $E3: saved overworld X, $E4: saved overworld Y, $E5: sentinel,
    $E6-$E9: roster slot IDs
  PLRS (256 bytes) - 4 active character records (4x64 bytes)
  SOSM (256 bytes) - Overworld monster positions
"""

import argparse
import json
import os
import sys

from .constants import (
    PRTY_TRANSPORT, PRTY_TRANSPORT_CODES,
    PRTY_LOCATION_TYPE, PRTY_LOCATION_CODES,
    PRTY_OFF_TRANSPORT, PRTY_OFF_PARTY_SIZE, PRTY_OFF_LOCATION,
    PRTY_OFF_SAVED_X, PRTY_OFF_SAVED_Y, PRTY_OFF_SENTINEL,
    PRTY_OFF_SLOT_IDS,
    PRTY_FILE_SIZE, PLRS_FILE_SIZE, SOSA_FILE_SIZE, SOSM_FILE_SIZE,
    CHAR_RECORD_SIZE, tile_char,
    WEAPONS, ARMORS,
)
from .fileutil import resolve_single_file, backup_file
from .roster import Character
from .json_export import export_json


class PartyState:
    """Party state from PRTY file (16 bytes)."""

    def __init__(self, data: bytes):
        if len(data) < PRTY_FILE_SIZE:
            raise ValueError(f"PRTY data too small: {len(data)} bytes (need {PRTY_FILE_SIZE})")
        self.raw = bytearray(data[:PRTY_FILE_SIZE])

    @property
    def transport(self) -> str:
        return PRTY_TRANSPORT.get(self.raw[PRTY_OFF_TRANSPORT],
                                  f'Unknown(${self.raw[PRTY_OFF_TRANSPORT]:02X})')

    @transport.setter
    def transport(self, name_or_code) -> None:
        if isinstance(name_or_code, int):
            self.raw[PRTY_OFF_TRANSPORT] = name_or_code & 0xFF
            return
        name = str(name_or_code)
        code = PRTY_TRANSPORT_CODES.get(name.lower())
        if code is not None:
            self.raw[PRTY_OFF_TRANSPORT] = code
            return
        # Raw int/hex string fallback for total conversions
        try:
            self.raw[PRTY_OFF_TRANSPORT] = int(name, 0) & 0xFF
            return
        except ValueError:
            pass
        raise ValueError(f"Unknown transport: {name_or_code!r} "
                         f"(valid: {', '.join(PRTY_TRANSPORT_CODES.keys())}, "
                         f"or raw int/hex)")

    @property
    def party_size(self) -> int:
        return self.raw[PRTY_OFF_PARTY_SIZE]

    @party_size.setter
    def party_size(self, val: int) -> None:
        self.raw[PRTY_OFF_PARTY_SIZE] = max(0, min(4, val))

    @property
    def location_type(self) -> str:
        return PRTY_LOCATION_TYPE.get(self.raw[PRTY_OFF_LOCATION],
                                      f'Unknown(${self.raw[PRTY_OFF_LOCATION]:02X})')

    @property
    def location_code(self) -> int:
        return self.raw[PRTY_OFF_LOCATION]

    @location_code.setter
    def location_code(self, val: int) -> None:
        self.raw[PRTY_OFF_LOCATION] = val & 0xFF

    @location_type.setter
    def location_type(self, name_or_code) -> None:
        if isinstance(name_or_code, int):
            self.raw[PRTY_OFF_LOCATION] = name_or_code & 0xFF
            return
        name = str(name_or_code)
        code = PRTY_LOCATION_CODES.get(name.lower())
        if code is not None:
            self.raw[PRTY_OFF_LOCATION] = code
            return
        # Raw int/hex string fallback for total conversions
        try:
            self.raw[PRTY_OFF_LOCATION] = int(name, 0) & 0xFF
            return
        except ValueError:
            pass
        raise ValueError(f"Unknown location type: {name_or_code!r} "
                         f"(valid: {', '.join(PRTY_LOCATION_CODES.keys())}, "
                         f"or raw int/hex)")

    @property
    def x(self) -> int:
        return self.raw[PRTY_OFF_SAVED_X]

    @x.setter
    def x(self, val: int) -> None:
        self.raw[PRTY_OFF_SAVED_X] = max(0, min(63, val))

    @property
    def y(self) -> int:
        return self.raw[PRTY_OFF_SAVED_Y]

    @y.setter
    def y(self, val: int) -> None:
        self.raw[PRTY_OFF_SAVED_Y] = max(0, min(63, val))

    @property
    def sentinel(self) -> int:
        return self.raw[PRTY_OFF_SENTINEL]

    @sentinel.setter
    def sentinel(self, val: int) -> None:
        self.raw[PRTY_OFF_SENTINEL] = val & 0xFF

    @property
    def slot_ids(self) -> list[int]:
        return [self.raw[PRTY_OFF_SLOT_IDS + i] for i in range(4)]

    @slot_ids.setter
    def slot_ids(self, ids: list[int]) -> None:
        for i, sid in enumerate(ids[:4]):
            self.raw[PRTY_OFF_SLOT_IDS + i] = max(0, min(19, sid))

    def to_dict(self) -> dict:
        return {
            'transport': self.transport,
            'party_size': self.party_size,
            'location_type': self.location_type,
            'x': self.x, 'y': self.y,
            'sentinel': self.sentinel,
            'slot_ids': self.slot_ids,
        }

    def display(self) -> None:
        print(f"  Transport:     {self.transport}")
        print(f"  Party size:    {self.party_size}")
        print(f"  Location:      {self.location_type}")
        print(f"  Coordinates:   ({self.x}, {self.y})")
        sentinel_note = (" (active)" if self.sentinel == 0xFF else
                         " (inactive)" if self.sentinel == 0x00 else
                         " (non-standard)")
        print(f"  Sentinel:      ${self.sentinel:02X}{sentinel_note}")
        print(f"  Roster slots:  {self.slot_ids}")


def validate_party_state(party: PartyState) -> list[str]:
    """Check party state for data integrity issues.

    Returns a list of warning strings (empty if valid).
    """
    warnings = []

    # Transport should be a known value
    if party.raw[PRTY_OFF_TRANSPORT] not in PRTY_TRANSPORT:
        warnings.append(f"Unknown transport code: ${party.raw[PRTY_OFF_TRANSPORT]:02X}")

    # Party size 0-4
    if party.party_size > 4:
        warnings.append(f"Party size {party.party_size} exceeds maximum 4")

    # Location type should be known
    if party.raw[PRTY_OFF_LOCATION] not in PRTY_LOCATION_TYPE:
        warnings.append(f"Unknown location type: ${party.raw[PRTY_OFF_LOCATION]:02X}")

    # Coordinates should be in map bounds (0-63)
    if party.x > 63:
        warnings.append(f"X coordinate {party.x} out of bounds (0-63)")
    if party.y > 63:
        warnings.append(f"Y coordinate {party.y} out of bounds (0-63)")

    # Sentinel should be $FF for active party
    if party.sentinel != 0xFF and party.sentinel != 0x00:
        warnings.append(f"Unexpected sentinel: ${party.sentinel:02X} (expected $FF or $00)")

    # Slot IDs should be valid roster indices (0-19)
    for i, sid in enumerate(party.slot_ids[:party.party_size]):
        if sid > 19:
            warnings.append(f"Slot {i} references invalid roster index {sid} (max 19)")

    return warnings


def cmd_view(args) -> None:
    game_dir = args.game_dir

    prty_path = resolve_single_file(game_dir, 'PRTY')
    if not prty_path:
        print(f"Error: PRTY file not found in {game_dir}", file=sys.stderr)
        sys.exit(1)

    with open(prty_path, 'rb') as f:
        prty_data = f.read()
    party = PartyState(prty_data)

    plrs_path = resolve_single_file(game_dir, 'PLRS')

    active_chars = []
    if plrs_path:
        with open(plrs_path, 'rb') as f:
            plrs_data = f.read()
        for i in range(min(4, len(plrs_data) // CHAR_RECORD_SIZE)):
            offset = i * CHAR_RECORD_SIZE
            active_chars.append(Character(plrs_data[offset:offset + CHAR_RECORD_SIZE]))

    do_validate = getattr(args, 'validate', False)

    if args.json:
        party_dict = party.to_dict()
        if do_validate:
            party_dict['warnings'] = validate_party_state(party)
        result = {
            'party': party_dict,
            'active_characters': [c.to_dict() for c in active_chars if not c.is_empty],
        }
        export_json(result, args.output)
        return

    print(f"\n=== Ultima III Save State ===\n")
    print(f"  --- Party Info (PRTY) ---")
    party.display()
    if do_validate:
        for w in validate_party_state(party):
            print(f"  WARNING: {w}", file=sys.stderr)

    if active_chars:
        print(f"\n  --- Active Characters (PLRS) ---\n")
        for i, char in enumerate(active_chars):
            if not char.is_empty:
                char.display(i)

    # Load SOSA for mini-map if available
    sosa_path = resolve_single_file(game_dir, 'SOSA')

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
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)

    prty_path = resolve_single_file(game_dir, 'PRTY')
    if not prty_path:
        print(f"Error: PRTY file not found in {game_dir}", file=sys.stderr)
        sys.exit(1)

    with open(prty_path, 'rb') as f:
        data = bytearray(f.read())
    party = PartyState(data)

    prty_modified = False
    if args.transport is not None:
        try:
            party.transport = args.transport; prty_modified = True
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    if args.x is not None:
        party.x = args.x; prty_modified = True
    if args.y is not None:
        party.y = args.y; prty_modified = True
    if args.party_size is not None:
        party.party_size = args.party_size; prty_modified = True
    if args.slot_ids is not None:
        party.slot_ids = args.slot_ids; prty_modified = True
    if getattr(args, 'sentinel', None) is not None:
        party.sentinel = args.sentinel; prty_modified = True
    if getattr(args, 'location', None) is not None:
        try:
            party.location_type = args.location; prty_modified = True
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # PLRS character editing
    plrs_modified = False
    plrs_slot = getattr(args, 'plrs_slot', None)
    if plrs_slot is not None:
        plrs_path = resolve_single_file(game_dir, 'PLRS')
        if not plrs_path:
            print(f"Error: PLRS file not found in {game_dir}", file=sys.stderr)
            sys.exit(1)
        with open(plrs_path, 'rb') as f:
            plrs_data = bytearray(f.read())

        if plrs_slot < 0 or plrs_slot >= min(4, len(plrs_data) // CHAR_RECORD_SIZE):
            print(f"Error: PLRS slot {plrs_slot} out of range", file=sys.stderr)
            sys.exit(1)

        offset = plrs_slot * CHAR_RECORD_SIZE
        char = Character(plrs_data[offset:offset + CHAR_RECORD_SIZE])

        if getattr(args, 'name', None) is not None:
            char.name = args.name; plrs_modified = True
        if getattr(args, 'str', None) is not None:
            char.strength = args.str; plrs_modified = True
        if getattr(args, 'dex', None) is not None:
            char.dexterity = args.dex; plrs_modified = True
        if getattr(args, 'int_', None) is not None:
            char.intelligence = args.int_; plrs_modified = True
        if getattr(args, 'wis', None) is not None:
            char.wisdom = args.wis; plrs_modified = True
        if getattr(args, 'hp', None) is not None:
            char.hp = args.hp
            char.max_hp = max(char.max_hp, args.hp)
            plrs_modified = True
        if getattr(args, 'max_hp', None) is not None:
            char.max_hp = args.max_hp; plrs_modified = True
        if getattr(args, 'mp', None) is not None:
            char.mp = args.mp; plrs_modified = True
        if getattr(args, 'gold', None) is not None:
            char.gold = args.gold; plrs_modified = True
        if getattr(args, 'exp', None) is not None:
            char.exp = args.exp; plrs_modified = True
        if getattr(args, 'food', None) is not None:
            char.food = args.food; plrs_modified = True
        if getattr(args, 'gems', None) is not None:
            char.gems = args.gems; plrs_modified = True
        if getattr(args, 'keys', None) is not None:
            char.keys = args.keys; plrs_modified = True
        if getattr(args, 'powders', None) is not None:
            char.powders = args.powders; plrs_modified = True
        if getattr(args, 'torches', None) is not None:
            char.torches = args.torches; plrs_modified = True
        if getattr(args, 'status', None) is not None:
            char.status = args.status; plrs_modified = True
        if getattr(args, 'race', None) is not None:
            char.race = args.race; plrs_modified = True
        if getattr(args, 'class_', None) is not None:
            char.char_class = args.class_; plrs_modified = True
        if getattr(args, 'gender', None) is not None:
            char.gender = args.gender; plrs_modified = True
        if getattr(args, 'weapon', None) is not None:
            char.equipped_weapon = args.weapon; plrs_modified = True
        if getattr(args, 'armor', None) is not None:
            char.equipped_armor = args.armor; plrs_modified = True
        if getattr(args, 'marks', None) is not None:
            char.marks = [m.strip() for m in args.marks.split(',')]; plrs_modified = True
        if getattr(args, 'cards', None) is not None:
            char.cards = [c.strip() for c in args.cards.split(',')]; plrs_modified = True
        if getattr(args, 'sub_morsels', None) is not None:
            char.sub_morsels = args.sub_morsels; plrs_modified = True

        if plrs_modified:
            plrs_data[offset:offset + CHAR_RECORD_SIZE] = char.raw
            print(f"Modified PLRS slot {plrs_slot}:")
            char.display(plrs_slot)

    if not prty_modified and not plrs_modified:
        print("No modifications specified.")
        return

    if prty_modified and plrs_modified and args.output:
        print("Error: --output cannot be used when editing both party state and "
              "PLRS characters (they are separate files). Remove --output to "
              "write each file in place, or edit them in separate commands.",
              file=sys.stderr)
        sys.exit(1)

    # Write PLRS first (after conflict check above ensures --output is safe)
    if plrs_modified and not dry_run:
        plrs_output = args.output if args.output else plrs_path
        if do_backup and (not args.output or args.output == plrs_path):
            backup_file(plrs_path)
        with open(plrs_output, 'wb') as f:
            f.write(plrs_data)
        print(f"Saved PLRS to {plrs_output}")

    if prty_modified:
        do_validate = getattr(args, 'validate', False)
        if do_validate:
            for w in validate_party_state(party):
                print(f"  Warning: {w}")
        if dry_run:
            print("Dry run - no changes written.")
            party.display()
            return
        output = args.output if args.output else prty_path
        if do_backup and (not args.output or args.output == prty_path):
            backup_file(prty_path)
        with open(output, 'wb') as f:
            f.write(bytes(party.raw) + data[PRTY_FILE_SIZE:])
        print(f"Saved party state to {output}")
        party.display()
    elif dry_run:
        print("Dry run - no changes written.")


def cmd_import(args) -> None:
    """Import save state from JSON."""
    game_dir = args.game_dir
    do_backup = getattr(args, 'backup', False)
    dry_run = getattr(args, 'dry_run', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    party_data = jdata.get('party', {})
    if party_data:
        prty_path = resolve_single_file(game_dir, 'PRTY')
        if not prty_path:
            print(f"Error: PRTY file not found in {game_dir}", file=sys.stderr)
            sys.exit(1)
        with open(prty_path, 'rb') as f:
            data = bytearray(f.read())
        party = PartyState(data)

        if 'transport' in party_data:
            try:
                party.transport = party_data['transport']
            except ValueError as e:
                print(f"Warning: {e}", file=sys.stderr)
        if 'party_size' in party_data:
            party.party_size = party_data['party_size']
        if 'location_type' in party_data:
            try:
                party.location_type = party_data['location_type']
            except ValueError as e:
                print(f"Warning: {e}", file=sys.stderr)
        if 'x' in party_data:
            party.x = party_data['x']
        if 'y' in party_data:
            party.y = party_data['y']
        if 'sentinel' in party_data:
            party.sentinel = party_data['sentinel']
        if 'slot_ids' in party_data:
            party.slot_ids = party_data['slot_ids']

        print(f"Import: party state ({len(party_data)} field(s))")
        if not dry_run:
            output = args.output if args.output else prty_path
            if do_backup and (not args.output or args.output == prty_path):
                backup_file(prty_path)
            with open(output, 'wb') as f:
                f.write(bytes(party.raw) + data[PRTY_FILE_SIZE:])
            print(f"Imported party state to {output}")

    # PLRS character import
    chars_data = jdata.get('active_characters', [])
    if chars_data:
        plrs_path = resolve_single_file(game_dir, 'PLRS')
        if not plrs_path:
            print("Warning: PLRS file not found, skipping character import",
                  file=sys.stderr)
        else:
            with open(plrs_path, 'rb') as f:
                plrs_raw = bytearray(f.read())
            count = 0
            for i, entry in enumerate(chars_data):
                if i >= min(4, len(plrs_raw) // CHAR_RECORD_SIZE):
                    break
                offset = i * CHAR_RECORD_SIZE
                char = Character(plrs_raw[offset:offset + CHAR_RECORD_SIZE])
                if 'name' in entry:
                    char.name = entry['name']
                if 'race' in entry:
                    char.race = entry['race']
                if 'class' in entry:
                    char.char_class = entry['class']
                if 'gender' in entry:
                    char.gender = entry['gender']
                if 'status' in entry:
                    char.status = entry['status']
                if 'in_party' in entry:
                    char.in_party = entry['in_party']
                stats = entry.get('stats', {})
                if 'str' in stats:
                    char.strength = stats['str']
                if 'dex' in stats:
                    char.dexterity = stats['dex']
                if 'int' in stats:
                    char.intelligence = stats['int']
                if 'wis' in stats:
                    char.wisdom = stats['wis']
                if 'hp' in entry:
                    char.hp = entry['hp']
                if 'max_hp' in entry:
                    char.max_hp = entry['max_hp']
                if 'mp' in entry:
                    char.mp = entry['mp']
                if 'exp' in entry:
                    char.exp = entry['exp']
                if 'gold' in entry:
                    char.gold = entry['gold']
                if 'food' in entry:
                    char.food = entry['food']
                if 'gems' in entry:
                    char.gems = entry['gems']
                if 'keys' in entry:
                    char.keys = entry['keys']
                if 'powders' in entry:
                    char.powders = entry['powders']
                if 'torches' in entry:
                    char.torches = entry['torches']
                if 'sub_morsels' in entry:
                    char.sub_morsels = entry['sub_morsels']
                if 'marks' in entry:
                    char.marks = entry['marks']
                if 'cards' in entry:
                    char.cards = entry['cards']
                if 'weapon' in entry:
                    try:
                        char.equipped_weapon = entry['weapon']
                    except ValueError:
                        print(f"  Warning: Unknown weapon '{entry['weapon']}' in PLRS slot {i}",
                              file=sys.stderr)
                if 'armor' in entry:
                    try:
                        char.equipped_armor = entry['armor']
                    except ValueError:
                        print(f"  Warning: Unknown armor '{entry['armor']}' in PLRS slot {i}",
                              file=sys.stderr)
                if 'weapons' in entry:
                    for wname, wcount in entry['weapons'].items():
                        try:
                            char.set_weapon_count(WEAPONS.index(wname), wcount)
                        except ValueError:
                            print(f"  Warning: Unknown weapon '{wname}' in PLRS slot {i} inventory",
                                  file=sys.stderr)
                if 'armors' in entry:
                    for aname, acount in entry['armors'].items():
                        try:
                            char.set_armor_count(ARMORS.index(aname), acount)
                        except ValueError:
                            print(f"  Warning: Unknown armor '{aname}' in PLRS slot {i} inventory",
                                  file=sys.stderr)
                plrs_raw[offset:offset + CHAR_RECORD_SIZE] = char.raw
                count += 1

            print(f"Import: {count} active character(s)")
            if not dry_run:
                plrs_output = args.output if args.output else plrs_path
                if do_backup and (not args.output or args.output == plrs_path):
                    backup_file(plrs_path)
                with open(plrs_output, 'wb') as f:
                    f.write(plrs_raw)
                print(f"Imported {count} character(s) to {plrs_output}")

    if dry_run:
        print("Dry run - no changes written.")


def _add_plrs_edit_args(p) -> None:
    """Add PLRS character editing arguments."""
    p.add_argument('--plrs-slot', type=int, help='Active character slot (0-3)')
    p.add_argument('--name', help='Character name')
    p.add_argument('--str', type=int, help='Strength (0-99)')
    p.add_argument('--dex', type=int, help='Dexterity (0-99)')
    p.add_argument('--int', type=int, dest='int_', help='Intelligence (0-99)')
    p.add_argument('--wis', type=int, help='Wisdom (0-99)')
    p.add_argument('--hp', type=int, help='Hit points (0-9999)')
    p.add_argument('--max-hp', type=int, help='Max HP (0-9999)')
    p.add_argument('--mp', type=int, help='Magic points (0-99)')
    p.add_argument('--gold', type=int, help='Gold (0-9999)')
    p.add_argument('--exp', type=int, help='Experience (0-9999)')
    p.add_argument('--food', type=int, help='Food (0-9999)')
    p.add_argument('--gems', type=int, help='Gems (0-99)')
    p.add_argument('--keys', type=int, help='Keys (0-99)')
    p.add_argument('--powders', type=int, help='Powders (0-99)')
    p.add_argument('--torches', type=int, help='Torches (0-99)')
    p.add_argument('--status', help='Status: G(ood) P(oisoned) D(ead) A(shes)')
    p.add_argument('--race', help='Race: H(uman) E(lf) D(warf) B(obbit) F(uzzy)')
    p.add_argument('--class', dest='class_', help='Class: F C W T L I D A R P B')
    p.add_argument('--gender', help='Gender: M(ale) F(emale) O(ther)')
    p.add_argument('--weapon', type=int, help='Equipped weapon index (0-15)')
    p.add_argument('--armor', type=int, help='Equipped armor index (0-7)')
    p.add_argument('--marks', help='Marks (comma-separated: Kings,Snake,Fire,Force)')
    p.add_argument('--cards', help='Cards (comma-separated: Death,Sol,Love,Moons)')
    p.add_argument('--sub-morsels', type=int, help='Sub-morsels food fraction (0-99)')


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('save', help='Save state viewer/editor')
    sub = p.add_subparsers(dest='save_command')

    p_view = sub.add_parser('view', help='View save state')
    p_view.add_argument('game_dir', help='GAME directory')
    p_view.add_argument('--brief', action='store_true', help='Skip overworld map')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')
    p_view.add_argument('--validate', action='store_true', help='Check data integrity')

    p_edit = sub.add_parser('edit', help='Edit party state')
    p_edit.add_argument('game_dir', help='GAME directory')
    p_edit.add_argument('--transport',
                        help='Transport: horse, ship, foot, or raw hex (0x0A)')
    p_edit.add_argument('--x', type=int, help='X coordinate (0-63)')
    p_edit.add_argument('--y', type=int, help='Y coordinate (0-63)')
    p_edit.add_argument('--party-size', type=int, help='Party size (0-4)')
    p_edit.add_argument('--slot-ids', type=int, nargs='+', help='Roster slot IDs (e.g., 0 1 2 3)')
    p_edit.add_argument('--sentinel', type=int,
                        help='Party sentinel byte (0xFF=active, 0x00=inactive)')
    p_edit.add_argument('--location',
                        help='Location type: sosaria, dungeon, town, castle, or raw hex')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_edit.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    p_edit.add_argument('--validate', action='store_true', help='Check data integrity after edit')
    _add_plrs_edit_args(p_edit)

    p_import = sub.add_parser('import', help='Import save state from JSON')
    p_import.add_argument('game_dir', help='GAME directory')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true', help='Show changes without writing')


def dispatch(args) -> None:
    cmd = args.save_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: u3edit save {view|edit|import} ...", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Save State Viewer/Editor')
    sub = parser.add_subparsers(dest='save_command')

    p_view = sub.add_parser('view', help='View save state')
    p_view.add_argument('game_dir', help='GAME directory')
    p_view.add_argument('--brief', action='store_true', help='Skip overworld map')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')
    p_view.add_argument('--validate', action='store_true', help='Check data integrity')

    p_edit = sub.add_parser('edit', help='Edit party state')
    p_edit.add_argument('game_dir', help='GAME directory')
    p_edit.add_argument('--transport',
                        help='Transport: horse, ship, foot, or raw hex (0x0A)')
    p_edit.add_argument('--x', type=int, help='X coordinate (0-63)')
    p_edit.add_argument('--y', type=int, help='Y coordinate (0-63)')
    p_edit.add_argument('--party-size', type=int, help='Party size (0-4)')
    p_edit.add_argument('--slot-ids', type=int, nargs='+',
                        help='Roster slot IDs (e.g., 0 1 2 3)')
    p_edit.add_argument('--sentinel', type=int,
                        help='Party sentinel byte (0xFF=active, 0x00=inactive)')
    p_edit.add_argument('--location',
                        help='Location type: sosaria, dungeon, town, castle, or raw hex')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_edit.add_argument('--backup', action='store_true',
                        help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true',
                        help='Show changes without writing')
    p_edit.add_argument('--validate', action='store_true',
                        help='Check data integrity after edit')
    _add_plrs_edit_args(p_edit)

    p_import = sub.add_parser('import', help='Import save state from JSON')
    p_import.add_argument('game_dir', help='GAME directory')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true',
                          help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true',
                          help='Show changes without writing')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
