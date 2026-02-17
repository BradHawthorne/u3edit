"""Ultima III: Exodus - Character Roster Viewer/Editor.

Reads and edits ROST files (20 character slots, 64 bytes each = 1280 bytes).
All numeric fields use BCD encoding. Names are high-bit ASCII.

Bug fixes from prototype:
  R-1: Removed fake "Lv" display (was reading food byte 0x21 as level)
  R-2: Fixed marks/cards bitmask (high nibble = marks, low nibble = cards)
  R-3: Removed unused import struct
  R-4: Decodes offset 0x20 as sub-morsels (food fraction)
"""

import argparse
import os
import sys

from .bcd import bcd_to_int, bcd16_to_int, int_to_bcd, int_to_bcd16
from .constants import (
    CHAR_RECORD_SIZE, CHAR_MAX_SLOTS, ROSTER_FILE_SIZE,
    RACES, RACE_CODES, CLASSES, CLASS_CODES, GENDERS, STATUS_CODES,
    WEAPONS, ARMORS, MARKS_BITS, CARDS_BITS, RACE_MAX_STATS,
    CHAR_NAME_OFFSET, CHAR_NAME_LENGTH, CHAR_MARKS_CARDS, CHAR_TORCHES,
    CHAR_IN_PARTY, CHAR_STATUS, CHAR_STR, CHAR_DEX, CHAR_INT, CHAR_WIS,
    CHAR_RACE, CHAR_CLASS, CHAR_GENDER, CHAR_MP,
    CHAR_HP_HI, CHAR_HP_LO, CHAR_MAX_HP_HI, CHAR_MAX_HP_LO,
    CHAR_EXP_HI, CHAR_EXP_LO, CHAR_SUB_MORSELS,
    CHAR_FOOD_HI, CHAR_FOOD_LO, CHAR_GOLD_HI, CHAR_GOLD_LO,
    CHAR_GEMS, CHAR_KEYS, CHAR_POWDERS,
    CHAR_WORN_ARMOR, CHAR_ARMOR_START,
    CHAR_READIED_WEAPON, CHAR_WEAPON_START,
)
from .fileutil import decode_high_ascii, encode_high_ascii
from .json_export import export_json


class Character:
    """A single Ultima III character record (64 bytes)."""

    def __init__(self, data: bytes | bytearray):
        assert len(data) == CHAR_RECORD_SIZE
        self.raw = bytearray(data)

    @property
    def is_empty(self) -> bool:
        return all(b == 0 for b in self.raw)

    # --- Name ---
    @property
    def name(self) -> str:
        return decode_high_ascii(self.raw[CHAR_NAME_OFFSET:CHAR_NAME_OFFSET + CHAR_NAME_LENGTH])

    @name.setter
    def name(self, val: str) -> None:
        self.raw[CHAR_NAME_OFFSET:CHAR_NAME_OFFSET + CHAR_NAME_LENGTH] = \
            encode_high_ascii(val, CHAR_NAME_LENGTH)

    # --- Marks and Cards (byte 0x0E) ---
    # R-2 FIX: High nibble = marks (bits 7-4), low nibble = cards (bits 3-0)
    @property
    def marks(self) -> list[str]:
        b = self.raw[CHAR_MARKS_CARDS]
        return [name for bit, name in MARKS_BITS.items() if b & (1 << bit)]

    @marks.setter
    def marks(self, names: list[str]) -> None:
        b = self.raw[CHAR_MARKS_CARDS] & 0x0F  # Keep cards
        for bit, name in MARKS_BITS.items():
            if name in names:
                b |= (1 << bit)
        self.raw[CHAR_MARKS_CARDS] = b

    @property
    def cards(self) -> list[str]:
        b = self.raw[CHAR_MARKS_CARDS]
        return [name for bit, name in CARDS_BITS.items() if b & (1 << bit)]

    @cards.setter
    def cards(self, names: list[str]) -> None:
        b = self.raw[CHAR_MARKS_CARDS] & 0xF0  # Keep marks
        for bit, name in CARDS_BITS.items():
            if name in names:
                b |= (1 << bit)
        self.raw[CHAR_MARKS_CARDS] = b

    @property
    def marks_cards(self) -> list[str]:
        return self.marks + self.cards

    # --- Simple BCD fields ---
    @property
    def torches(self) -> int:
        return bcd_to_int(self.raw[CHAR_TORCHES])

    @torches.setter
    def torches(self, val: int) -> None:
        self.raw[CHAR_TORCHES] = int_to_bcd(val)

    @property
    def in_party(self) -> bool:
        return self.raw[CHAR_IN_PARTY] == 0xFF

    @property
    def status(self) -> str:
        return STATUS_CODES.get(self.raw[CHAR_STATUS], f'?({self.raw[CHAR_STATUS]:02X})')

    @status.setter
    def status(self, code: str) -> None:
        code = code.upper()
        for k, v in STATUS_CODES.items():
            if v[0].upper() == code or v.upper() == code:
                self.raw[CHAR_STATUS] = k
                return

    @property
    def strength(self) -> int:
        return bcd_to_int(self.raw[CHAR_STR])

    @strength.setter
    def strength(self, val: int) -> None:
        self.raw[CHAR_STR] = int_to_bcd(val)

    @property
    def dexterity(self) -> int:
        return bcd_to_int(self.raw[CHAR_DEX])

    @dexterity.setter
    def dexterity(self, val: int) -> None:
        self.raw[CHAR_DEX] = int_to_bcd(val)

    @property
    def intelligence(self) -> int:
        return bcd_to_int(self.raw[CHAR_INT])

    @intelligence.setter
    def intelligence(self, val: int) -> None:
        self.raw[CHAR_INT] = int_to_bcd(val)

    @property
    def wisdom(self) -> int:
        return bcd_to_int(self.raw[CHAR_WIS])

    @wisdom.setter
    def wisdom(self, val: int) -> None:
        self.raw[CHAR_WIS] = int_to_bcd(val)

    @property
    def race(self) -> str:
        return RACES.get(self.raw[CHAR_RACE], f'?({self.raw[CHAR_RACE]:02X})')

    @race.setter
    def race(self, code: str) -> None:
        code = code.upper()
        if code in RACE_CODES:
            self.raw[CHAR_RACE] = RACE_CODES[code]

    @property
    def char_class(self) -> str:
        return CLASSES.get(self.raw[CHAR_CLASS], f'?({self.raw[CHAR_CLASS]:02X})')

    @char_class.setter
    def char_class(self, code: str) -> None:
        code = code.upper()
        if code in CLASS_CODES:
            self.raw[CHAR_CLASS] = CLASS_CODES[code]

    @property
    def gender(self) -> str:
        return GENDERS.get(self.raw[CHAR_GENDER], f'?({self.raw[CHAR_GENDER]:02X})')

    @gender.setter
    def gender(self, code: str) -> None:
        code = code.upper()
        for k, v in GENDERS.items():
            if v[0].upper() == code or v.upper() == code:
                self.raw[CHAR_GENDER] = k
                return

    @property
    def mp(self) -> int:
        return bcd_to_int(self.raw[CHAR_MP])

    @mp.setter
    def mp(self, val: int) -> None:
        self.raw[CHAR_MP] = int_to_bcd(val)

    # --- 16-bit BCD fields ---
    @property
    def hp(self) -> int:
        return bcd16_to_int(self.raw[CHAR_HP_HI], self.raw[CHAR_HP_LO])

    @hp.setter
    def hp(self, val: int) -> None:
        self.raw[CHAR_HP_HI], self.raw[CHAR_HP_LO] = int_to_bcd16(val)

    @property
    def max_hp(self) -> int:
        return bcd16_to_int(self.raw[CHAR_MAX_HP_HI], self.raw[CHAR_MAX_HP_LO])

    @max_hp.setter
    def max_hp(self, val: int) -> None:
        self.raw[CHAR_MAX_HP_HI], self.raw[CHAR_MAX_HP_LO] = int_to_bcd16(val)

    @property
    def exp(self) -> int:
        return bcd16_to_int(self.raw[CHAR_EXP_HI], self.raw[CHAR_EXP_LO])

    @exp.setter
    def exp(self, val: int) -> None:
        self.raw[CHAR_EXP_HI], self.raw[CHAR_EXP_LO] = int_to_bcd16(val)

    # R-4 FIX: Decode sub-morsels (food fraction at offset 0x20)
    @property
    def sub_morsels(self) -> int:
        return bcd_to_int(self.raw[CHAR_SUB_MORSELS])

    @property
    def food(self) -> int:
        return bcd16_to_int(self.raw[CHAR_FOOD_HI], self.raw[CHAR_FOOD_LO])

    @food.setter
    def food(self, val: int) -> None:
        self.raw[CHAR_FOOD_HI], self.raw[CHAR_FOOD_LO] = int_to_bcd16(val)

    @property
    def gold(self) -> int:
        return bcd16_to_int(self.raw[CHAR_GOLD_HI], self.raw[CHAR_GOLD_LO])

    @gold.setter
    def gold(self, val: int) -> None:
        self.raw[CHAR_GOLD_HI], self.raw[CHAR_GOLD_LO] = int_to_bcd16(val)

    @property
    def gems(self) -> int:
        return bcd_to_int(self.raw[CHAR_GEMS])

    @gems.setter
    def gems(self, val: int) -> None:
        self.raw[CHAR_GEMS] = int_to_bcd(val)

    @property
    def keys(self) -> int:
        return bcd_to_int(self.raw[CHAR_KEYS])

    @keys.setter
    def keys(self, val: int) -> None:
        self.raw[CHAR_KEYS] = int_to_bcd(val)

    @property
    def powders(self) -> int:
        return bcd_to_int(self.raw[CHAR_POWDERS])

    @powders.setter
    def powders(self, val: int) -> None:
        self.raw[CHAR_POWDERS] = int_to_bcd(val)

    # --- Equipment ---
    @property
    def equipped_armor(self) -> str:
        idx = self.raw[CHAR_WORN_ARMOR]
        return ARMORS[idx] if idx < len(ARMORS) else f'?({idx})'

    @equipped_armor.setter
    def equipped_armor(self, val: int) -> None:
        self.raw[CHAR_WORN_ARMOR] = max(0, min(len(ARMORS) - 1, val))

    @property
    def equipped_weapon(self) -> str:
        idx = self.raw[CHAR_READIED_WEAPON]
        return WEAPONS[idx] if idx < len(WEAPONS) else f'?({idx})'

    @equipped_weapon.setter
    def equipped_weapon(self, val: int) -> None:
        self.raw[CHAR_READIED_WEAPON] = max(0, min(len(WEAPONS) - 1, val))

    @property
    def armor_inventory(self) -> dict[str, int]:
        inv = {}
        for i in range(len(ARMORS) - 1):  # 7 armor counts (Cloth..Exotic)
            count = bcd_to_int(self.raw[CHAR_ARMOR_START + i])
            if count > 0:
                inv[ARMORS[i + 1]] = count
        return inv

    @property
    def weapon_inventory(self) -> dict[str, int]:
        inv = {}
        for i in range(len(WEAPONS) - 1):  # 15 weapon counts (Dagger..Exotic)
            count = bcd_to_int(self.raw[CHAR_WEAPON_START + i])
            if count > 0:
                inv[WEAPONS[i + 1]] = count
        return inv

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            'name': self.name,
            'race': self.race,
            'class': self.char_class,
            'gender': self.gender,
            'status': self.status,
            'in_party': self.in_party,
            'stats': {
                'str': self.strength, 'dex': self.dexterity,
                'int': self.intelligence, 'wis': self.wisdom,
            },
            'hp': self.hp, 'max_hp': self.max_hp,
            'mp': self.mp, 'exp': self.exp,
            'gold': self.gold, 'food': self.food,
            'gems': self.gems, 'keys': self.keys,
            'powders': self.powders, 'torches': self.torches,
            'marks': self.marks, 'cards': self.cards,
            'weapon': self.equipped_weapon,
            'armor': self.equipped_armor,
            'weapons': self.weapon_inventory,
            'armors': self.armor_inventory,
        }

    # R-1 FIX: Removed fake "Lv" display (was reading food byte as level)
    def display(self, slot: int = -1) -> None:
        """Print character summary to stdout."""
        if self.is_empty:
            if slot >= 0:
                print(f"  Slot {slot:2d}: (empty)")
            return

        header = f"  Slot {slot:2d}: " if slot >= 0 else "  "
        party_mark = " [IN PARTY]" if self.in_party else ""
        print(f"{header}{self.name:<12s}  {self.race} {self.char_class} ({self.gender}){party_mark}")
        mc = self.marks_cards
        print(f"           Status: {self.status}   Marks/Cards: {', '.join(mc) if mc else 'None'}")
        print(f"           STR {self.strength:2d}  DEX {self.dexterity:2d}  INT {self.intelligence:2d}  WIS {self.wisdom:2d}")
        print(f"           HP {self.hp:4d}/{self.max_hp:4d}  MP {self.mp:2d}  EXP {self.exp:5d}")
        print(f"           Gold {self.gold:5d}  Food {self.food:5d}  Gems {self.gems:2d}  Keys {self.keys:2d}  Powders {self.powders:2d}  Torches {self.torches:2d}")
        print(f"           Weapon: {self.equipped_weapon}  Armor: {self.equipped_armor}")

        weapons = self.weapon_inventory
        if weapons:
            items = ', '.join(f"{name} x{count}" for name, count in weapons.items())
            print(f"           Weapons: {items}")

        armors = self.armor_inventory
        if armors:
            items = ', '.join(f"{name} x{count}" for name, count in armors.items())
            print(f"           Armors:  {items}")
        print()


def load_roster(path: str) -> tuple[list[Character], bytes]:
    """Load a roster file and return list of Character objects + raw data."""
    with open(path, 'rb') as f:
        data = f.read()

    if len(data) < CHAR_RECORD_SIZE:
        print(f"Error: File too small ({len(data)} bytes, need at least {CHAR_RECORD_SIZE})",
              file=sys.stderr)
        sys.exit(1)

    num_slots = len(data) // CHAR_RECORD_SIZE
    chars = []
    for i in range(num_slots):
        offset = i * CHAR_RECORD_SIZE
        chars.append(Character(data[offset:offset + CHAR_RECORD_SIZE]))
    return chars, data


def save_roster(path: str, chars: list[Character], original_data: bytes) -> None:
    """Save modified characters back to roster file."""
    data = bytearray(original_data)
    for i, char in enumerate(chars):
        offset = i * CHAR_RECORD_SIZE
        data[offset:offset + CHAR_RECORD_SIZE] = char.raw
    with open(path, 'wb') as f:
        f.write(data)
    print(f"Saved to {path}")


def cmd_view(args) -> None:
    chars, _ = load_roster(args.file)
    filename = os.path.basename(args.file)

    if args.json:
        roster = []
        for i, char in enumerate(chars):
            if not char.is_empty:
                d = char.to_dict()
                d['slot'] = i
                roster.append(d)
        export_json(roster, args.output)
        return

    print(f"\n=== Ultima III Roster: {filename} ({len(chars)} slots) ===\n")

    if args.slot is not None:
        if args.slot < 0 or args.slot >= len(chars):
            print(f"Error: Slot {args.slot} out of range (0-{len(chars)-1})", file=sys.stderr)
            sys.exit(1)
        chars[args.slot].display(args.slot)
    else:
        found = False
        for i, char in enumerate(chars):
            if not char.is_empty:
                char.display(i)
                found = True
        if not found:
            print("  (All slots empty)")
    print()


def cmd_edit(args) -> None:
    chars, original = load_roster(args.file)
    if args.slot < 0 or args.slot >= len(chars):
        print(f"Error: Slot {args.slot} out of range", file=sys.stderr)
        sys.exit(1)

    char = chars[args.slot]
    if char.is_empty:
        print(f"Error: Slot {args.slot} is empty. Use 'create' to make a new character.",
              file=sys.stderr)
        sys.exit(1)

    modified = False
    if args.name is not None:
        char.name = args.name; modified = True
    if args.str is not None:
        char.strength = args.str; modified = True
    if args.dex is not None:
        char.dexterity = args.dex; modified = True
    if args.int_ is not None:
        char.intelligence = args.int_; modified = True
    if args.wis is not None:
        char.wisdom = args.wis; modified = True
    if args.hp is not None:
        char.hp = args.hp
        char.max_hp = max(char.max_hp, args.hp)
        modified = True
    if args.max_hp is not None:
        char.max_hp = args.max_hp; modified = True
    if args.mp is not None:
        char.mp = args.mp; modified = True
    if args.gold is not None:
        char.gold = args.gold; modified = True
    if args.exp is not None:
        char.exp = args.exp; modified = True
    if args.food is not None:
        char.food = args.food; modified = True
    if args.gems is not None:
        char.gems = args.gems; modified = True
    if args.keys is not None:
        char.keys = args.keys; modified = True
    if args.powders is not None:
        char.powders = args.powders; modified = True
    if args.torches is not None:
        char.torches = args.torches; modified = True
    if args.status is not None:
        char.status = args.status; modified = True
    if args.gender is not None:
        char.gender = args.gender; modified = True
    if args.weapon is not None:
        char.equipped_weapon = args.weapon; modified = True
    if args.armor is not None:
        char.equipped_armor = args.armor; modified = True
    if args.marks is not None:
        char.marks = [m.strip() for m in args.marks.split(',')]; modified = True
    if args.cards is not None:
        char.cards = [c.strip() for c in args.cards.split(',')]; modified = True

    if modified:
        print(f"Modified slot {args.slot}:")
        char.display(args.slot)
        output = args.output if args.output else args.file
        save_roster(output, chars, original)
    else:
        print("No modifications specified.")


def cmd_create(args) -> None:
    chars, original = load_roster(args.file)
    if args.slot < 0 or args.slot >= len(chars):
        print(f"Error: Slot {args.slot} out of range", file=sys.stderr)
        sys.exit(1)

    if not chars[args.slot].is_empty and not args.force:
        print(f"Error: Slot {args.slot} occupied by {chars[args.slot].name}. Use --force to overwrite.",
              file=sys.stderr)
        sys.exit(1)

    char = Character(bytearray(CHAR_RECORD_SIZE))
    char.name = args.name or "HERO"
    char.race = (args.race or 'H').upper()
    char.char_class = (args.class_ or 'F').upper()
    char.gender = (args.gender or 'M').upper()
    char.raw[CHAR_STATUS] = ord('G')  # Good status
    char.strength = args.str or 15
    char.dexterity = args.dex or 15
    char.intelligence = args.int_ or 15
    char.wisdom = args.wis or 15
    char.hp = 150
    char.max_hp = 150
    char.food = 200
    char.gold = 100

    chars[args.slot] = char
    print(f"Created character in slot {args.slot}:")
    char.display(args.slot)
    output = args.output if args.output else args.file
    save_roster(output, chars, original)


def register_parser(subparsers) -> None:
    """Register roster subcommands on a CLI subparser group."""
    p = subparsers.add_parser('roster', help='Character roster viewer/editor')
    sub = p.add_subparsers(dest='roster_command')

    # View
    p_view = sub.add_parser('view', help='View roster contents')
    p_view.add_argument('file', help='ROST file path')
    p_view.add_argument('--slot', type=int, help='View specific slot (0-19)')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    # Edit
    p_edit = sub.add_parser('edit', help='Edit a character')
    p_edit.add_argument('file', help='ROST file path')
    p_edit.add_argument('--slot', type=int, required=True, help='Slot number (0-19)')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_edit.add_argument('--name', help='Character name (max 9 chars)')
    p_edit.add_argument('--str', type=int, help='Strength (0-99)')
    p_edit.add_argument('--dex', type=int, help='Dexterity (0-99)')
    p_edit.add_argument('--int', type=int, dest='int_', help='Intelligence (0-99)')
    p_edit.add_argument('--wis', type=int, help='Wisdom (0-99)')
    p_edit.add_argument('--hp', type=int, help='Hit points (0-9999)')
    p_edit.add_argument('--max-hp', type=int, help='Max HP (0-9999)')
    p_edit.add_argument('--mp', type=int, help='Magic points (0-99)')
    p_edit.add_argument('--gold', type=int, help='Gold (0-9999)')
    p_edit.add_argument('--exp', type=int, help='Experience (0-9999)')
    p_edit.add_argument('--food', type=int, help='Food (0-9999)')
    p_edit.add_argument('--gems', type=int, help='Gems (0-99)')
    p_edit.add_argument('--keys', type=int, help='Keys (0-99)')
    p_edit.add_argument('--powders', type=int, help='Powders (0-99)')
    p_edit.add_argument('--torches', type=int, help='Torches (0-99)')
    p_edit.add_argument('--status', help='Status: G(ood) P(oisoned) D(ead) A(shes)')
    p_edit.add_argument('--gender', help='Gender: M(ale) F(emale) O(ther)')
    p_edit.add_argument('--weapon', type=int, help='Weapon index (0-15)')
    p_edit.add_argument('--armor', type=int, help='Armor index (0-7)')
    p_edit.add_argument('--marks', help='Marks (comma-separated: Kings,Snake,Fire,Force)')
    p_edit.add_argument('--cards', help='Cards (comma-separated: Death,Sol,Love,Moons)')

    # Create
    p_create = sub.add_parser('create', help='Create a new character')
    p_create.add_argument('file', help='ROST file path')
    p_create.add_argument('--slot', type=int, required=True, help='Slot number (0-19)')
    p_create.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_create.add_argument('--name', help='Character name (default: HERO)')
    p_create.add_argument('--race', help='Race: H(uman) E(lf) D(warf) B(obbit) F(uzzy)')
    p_create.add_argument('--class', dest='class_', help='Class: F C W T L I D A R P B')
    p_create.add_argument('--gender', help='Gender: M(ale) F(emale) O(ther)')
    p_create.add_argument('--str', type=int, help='Strength')
    p_create.add_argument('--dex', type=int, help='Dexterity')
    p_create.add_argument('--int', type=int, dest='int_', help='Intelligence')
    p_create.add_argument('--wis', type=int, help='Wisdom')
    p_create.add_argument('--force', action='store_true', help='Overwrite existing')


def dispatch(args) -> None:
    """Dispatch roster subcommand."""
    if args.roster_command == 'view':
        cmd_view(args)
    elif args.roster_command == 'edit':
        cmd_edit(args)
    elif args.roster_command == 'create':
        cmd_create(args)
    else:
        print("Usage: u3edit roster {view|edit|create} ...", file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Character Roster Viewer/Editor')
    sub = parser.add_subparsers(dest='roster_command')

    # Reuse registration but directly on our parser
    p_view = sub.add_parser('view', help='View roster contents')
    p_view.add_argument('file', help='ROST file path')
    p_view.add_argument('--slot', type=int, help='View specific slot (0-19)')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')

    p_edit = sub.add_parser('edit', help='Edit a character')
    p_edit.add_argument('file', help='ROST file path')
    p_edit.add_argument('--slot', type=int, required=True)
    p_edit.add_argument('--output', '-o')
    for flag in ['--name', '--str', '--dex', '--wis', '--hp', '--max-hp',
                 '--mp', '--gold', '--exp', '--food', '--gems', '--keys',
                 '--powders', '--torches', '--status', '--gender', '--marks', '--cards']:
        if flag in ('--str', '--dex', '--wis', '--hp', '--max-hp', '--mp',
                     '--gold', '--exp', '--food', '--gems', '--keys',
                     '--powders', '--torches'):
            p_edit.add_argument(flag, type=int)
        elif flag == '--weapon':
            p_edit.add_argument(flag, type=int)
        elif flag == '--armor':
            p_edit.add_argument(flag, type=int)
        else:
            dest = 'int_' if flag == '--int' else None
            if dest:
                p_edit.add_argument(flag, dest=dest)
            else:
                p_edit.add_argument(flag)
    p_edit.add_argument('--int', type=int, dest='int_')
    p_edit.add_argument('--weapon', type=int)
    p_edit.add_argument('--armor', type=int)

    p_create = sub.add_parser('create', help='Create a new character')
    p_create.add_argument('file')
    p_create.add_argument('--slot', type=int, required=True)
    p_create.add_argument('--output', '-o')
    p_create.add_argument('--name')
    p_create.add_argument('--race')
    p_create.add_argument('--class', dest='class_')
    p_create.add_argument('--gender')
    p_create.add_argument('--str', type=int)
    p_create.add_argument('--dex', type=int)
    p_create.add_argument('--int', type=int, dest='int_')
    p_create.add_argument('--wis', type=int)
    p_create.add_argument('--force', action='store_true')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
