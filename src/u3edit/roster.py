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
import json
import os
import sys

from .bcd import bcd_to_int, bcd16_to_int, int_to_bcd, int_to_bcd16, is_valid_bcd
from .constants import (
    CHAR_RECORD_SIZE, CHAR_MAX_SLOTS, ROSTER_FILE_SIZE,
    RACES, RACE_CODES, CLASSES, CLASS_CODES, GENDERS, STATUS_CODES,
    WEAPONS, ARMORS, MARKS_BITS, CARDS_BITS, RACE_MAX_STATS,
    CLASS_MAX_WEAPON, CLASS_MAX_ARMOR,
    CHAR_NAME_OFFSET, CHAR_NAME_LENGTH, CHAR_NAME_MAX, CHAR_NAME_FIELD,
    CHAR_MARKS_CARDS, CHAR_TORCHES,
    CHAR_IN_PARTY, CHAR_STATUS, CHAR_STR, CHAR_DEX, CHAR_INT, CHAR_WIS,
    CHAR_RACE, CHAR_CLASS, CHAR_GENDER, CHAR_MP,
    CHAR_HP_HI, CHAR_HP_LO, CHAR_MAX_HP_HI, CHAR_MAX_HP_LO,
    CHAR_EXP_HI, CHAR_EXP_LO, CHAR_SUB_MORSELS,
    CHAR_FOOD_HI, CHAR_FOOD_LO, CHAR_GOLD_HI, CHAR_GOLD_LO,
    CHAR_GEMS, CHAR_KEYS, CHAR_POWDERS,
    CHAR_WORN_ARMOR, CHAR_ARMOR_START,
    CHAR_READIED_WEAPON, CHAR_WEAPON_START,
)
from .fileutil import decode_high_ascii, encode_high_ascii, backup_file
from .json_export import export_json


class Character:
    """A single Ultima III character record (64 bytes)."""

    def __init__(self, data: bytes | bytearray):
        if len(data) != CHAR_RECORD_SIZE:
            raise ValueError(f"Character record must be {CHAR_RECORD_SIZE} bytes, got {len(data)}")
        self.raw = bytearray(data)

    @property
    def is_empty(self) -> bool:
        return all(b == 0 for b in self.raw)

    # --- Name (14-byte field: up to 13 chars + null terminator at 0x0D) ---
    # Engine BOOT.s input loop: CPY #$0D limits name to 13 characters.
    # Display routine in SUBS.s ($46F9) reads until null byte.
    @property
    def name(self) -> str:
        return decode_high_ascii(self.raw[CHAR_NAME_OFFSET:CHAR_NAME_OFFSET + CHAR_NAME_FIELD])

    @name.setter
    def name(self, val: str) -> None:
        # Null-fill the full 14-byte field, then write name chars.
        # This matches the engine's character creation behavior (zero-fill
        # then overwrite with typed characters, null-terminated).
        field = bytearray(CHAR_NAME_FIELD)  # all zeros
        for i, ch in enumerate(val[:CHAR_NAME_MAX].upper()):
            field[i] = ord(ch) | 0x80
        self.raw[CHAR_NAME_OFFSET:CHAR_NAME_OFFSET + CHAR_NAME_FIELD] = field

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

    @in_party.setter
    def in_party(self, val: bool) -> None:
        self.raw[CHAR_IN_PARTY] = 0xFF if val else 0x00

    @property
    def status(self) -> str:
        return STATUS_CODES.get(self.raw[CHAR_STATUS], f'?({self.raw[CHAR_STATUS]:02X})')

    @status.setter
    def status(self, code) -> None:
        if isinstance(code, int):
            self.raw[CHAR_STATUS] = code & 0xFF
            return
        code_str = str(code).upper()
        for k, v in STATUS_CODES.items():
            if v[0].upper() == code_str or v.upper() == code_str:
                self.raw[CHAR_STATUS] = k
                return
        # Raw int/hex string fallback for total conversions
        try:
            self.raw[CHAR_STATUS] = int(str(code), 0) & 0xFF
            return
        except ValueError:
            pass
        raise ValueError(f'Unknown status: {code}')

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
    def race(self, code) -> None:
        if isinstance(code, int):
            self.raw[CHAR_RACE] = code & 0xFF
            return
        code_str = str(code).upper()
        if code_str in RACE_CODES:
            self.raw[CHAR_RACE] = RACE_CODES[code_str]
            return
        for k, v in RACES.items():
            if v.upper() == code_str:
                self.raw[CHAR_RACE] = k
                return
        # Raw int/hex string fallback for total conversions
        try:
            self.raw[CHAR_RACE] = int(str(code), 0) & 0xFF
            return
        except ValueError:
            pass
        raise ValueError(f'Unknown race: {code}')

    @property
    def char_class(self) -> str:
        return CLASSES.get(self.raw[CHAR_CLASS], f'?({self.raw[CHAR_CLASS]:02X})')

    @char_class.setter
    def char_class(self, code) -> None:
        if isinstance(code, int):
            self.raw[CHAR_CLASS] = code & 0xFF
            return
        code_str = str(code).upper()
        if code_str in CLASS_CODES:
            self.raw[CHAR_CLASS] = CLASS_CODES[code_str]
            return
        for k, v in CLASSES.items():
            if v.upper() == code_str:
                self.raw[CHAR_CLASS] = k
                return
        # Raw int/hex string fallback for total conversions
        try:
            self.raw[CHAR_CLASS] = int(str(code), 0) & 0xFF
            return
        except ValueError:
            pass
        raise ValueError(f'Unknown class: {code}')

    @property
    def gender(self) -> str:
        return GENDERS.get(self.raw[CHAR_GENDER], f'?({self.raw[CHAR_GENDER]:02X})')

    @gender.setter
    def gender(self, code) -> None:
        if isinstance(code, int):
            self.raw[CHAR_GENDER] = code & 0xFF
            return
        code_str = str(code).upper()
        for k, v in GENDERS.items():
            if v[0].upper() == code_str or v.upper() == code_str:
                self.raw[CHAR_GENDER] = k
                return
        # Raw int/hex string fallback for total conversions
        try:
            self.raw[CHAR_GENDER] = int(str(code), 0) & 0xFF
            return
        except ValueError:
            pass
        raise ValueError(f'Unknown gender: {code}')

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

    @sub_morsels.setter
    def sub_morsels(self, val: int) -> None:
        self.raw[CHAR_SUB_MORSELS] = int_to_bcd(val)

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
    def equipped_armor(self, val) -> None:
        if isinstance(val, int):
            self.raw[CHAR_WORN_ARMOR] = max(0, min(255, val))
            return
        name = str(val)
        for i, a in enumerate(ARMORS):
            if a.upper() == name.upper():
                self.raw[CHAR_WORN_ARMOR] = i
                return
        # Raw hex string fallback for total conversions
        try:
            self.raw[CHAR_WORN_ARMOR] = max(0, min(255, int(name, 0)))
            return
        except ValueError:
            pass
        raise ValueError(f'Unknown armor: {val}')

    @property
    def equipped_weapon(self) -> str:
        idx = self.raw[CHAR_READIED_WEAPON]
        return WEAPONS[idx] if idx < len(WEAPONS) else f'?({idx})'

    @equipped_weapon.setter
    def equipped_weapon(self, val) -> None:
        if isinstance(val, int):
            self.raw[CHAR_READIED_WEAPON] = max(0, min(255, val))
            return
        name = str(val)
        for i, w in enumerate(WEAPONS):
            if w.upper() == name.upper():
                self.raw[CHAR_READIED_WEAPON] = i
                return
        # Raw hex string fallback for total conversions
        try:
            self.raw[CHAR_READIED_WEAPON] = max(0, min(255, int(name, 0)))
            return
        except ValueError:
            pass
        raise ValueError(f'Unknown weapon: {val}')

    @property
    def armor_inventory(self) -> dict[str, int]:
        inv = {}
        for i in range(len(ARMORS) - 1):  # 7 armor counts (Cloth..Exotic)
            count = bcd_to_int(self.raw[CHAR_ARMOR_START + i])
            if count > 0:
                inv[ARMORS[i + 1]] = count
        return inv

    def set_armor_count(self, index: int, count: int) -> None:
        """Set inventory count for armor at index (1-7, skipping Skin)."""
        if 1 <= index < len(ARMORS):
            self.raw[CHAR_ARMOR_START + index - 1] = int_to_bcd(count)

    @property
    def weapon_inventory(self) -> dict[str, int]:
        inv = {}
        for i in range(len(WEAPONS) - 1):  # 15 weapon counts (Dagger..Exotic)
            count = bcd_to_int(self.raw[CHAR_WEAPON_START + i])
            if count > 0:
                inv[WEAPONS[i + 1]] = count
        return inv

    def set_weapon_count(self, index: int, count: int) -> None:
        """Set inventory count for weapon at index (1-15, skipping Hands)."""
        if 1 <= index < len(WEAPONS):
            self.raw[CHAR_WEAPON_START + index - 1] = int_to_bcd(count)

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
            'sub_morsels': self.sub_morsels,
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
        raise ValueError(
            f"Roster file too small ({len(data)} bytes, need at least {CHAR_RECORD_SIZE})"
        )

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


def validate_character(char: Character) -> list[str]:
    """Check a character for game-rule violations and data integrity issues.

    Returns a list of warning strings (empty if everything is valid).
    """
    warnings = []
    if char.is_empty:
        return warnings

    # BCD integrity checks
    bcd_fields = [
        (CHAR_STR, 'Strength'), (CHAR_DEX, 'Dexterity'),
        (CHAR_INT, 'Intelligence'), (CHAR_WIS, 'Wisdom'),
        (CHAR_MP, 'MP'), (CHAR_GEMS, 'Gems'),
        (CHAR_KEYS, 'Keys'), (CHAR_POWDERS, 'Powders'),
        (CHAR_TORCHES, 'Torches'), (CHAR_SUB_MORSELS, 'Sub-morsels'),
        (CHAR_HP_HI, 'HP high'), (CHAR_HP_LO, 'HP low'),
        (CHAR_MAX_HP_HI, 'MaxHP high'), (CHAR_MAX_HP_LO, 'MaxHP low'),
        (CHAR_EXP_HI, 'Exp high'), (CHAR_EXP_LO, 'Exp low'),
        (CHAR_FOOD_HI, 'Food high'), (CHAR_FOOD_LO, 'Food low'),
        (CHAR_GOLD_HI, 'Gold high'), (CHAR_GOLD_LO, 'Gold low'),
    ]
    for offset, label in bcd_fields:
        if not is_valid_bcd(char.raw[offset]):
            warnings.append(f"Invalid BCD in {label}: ${char.raw[offset]:02X}")

    # HP vs Max HP
    if char.hp > char.max_hp:
        warnings.append(f"HP {char.hp} exceeds Max HP {char.max_hp}")

    # Race stat maximums
    race = char.race
    if race in RACE_MAX_STATS:
        max_str, max_dex, max_int, max_wis = RACE_MAX_STATS[race]
        if char.strength > max_str:
            warnings.append(f"STR {char.strength} exceeds {race} max {max_str}")
        if char.dexterity > max_dex:
            warnings.append(f"DEX {char.dexterity} exceeds {race} max {max_dex}")
        if char.intelligence > max_int:
            warnings.append(f"INT {char.intelligence} exceeds {race} max {max_int}")
        if char.wisdom > max_wis:
            warnings.append(f"WIS {char.wisdom} exceeds {race} max {max_wis}")

    # Class equipment restrictions
    cls = char.char_class
    weapon_idx = char.raw[CHAR_READIED_WEAPON]
    armor_idx = char.raw[CHAR_WORN_ARMOR]
    if cls in CLASS_MAX_WEAPON and weapon_idx > CLASS_MAX_WEAPON[cls]:
        warnings.append(
            f"Weapon {WEAPONS[weapon_idx] if weapon_idx < len(WEAPONS) else weapon_idx} "
            f"exceeds {cls} max ({WEAPONS[CLASS_MAX_WEAPON[cls]]})")
    if cls in CLASS_MAX_ARMOR and armor_idx > CLASS_MAX_ARMOR[cls]:
        warnings.append(
            f"Armor {ARMORS[armor_idx] if armor_idx < len(ARMORS) else armor_idx} "
            f"exceeds {cls} max ({ARMORS[CLASS_MAX_ARMOR[cls]]})")

    return warnings


def _apply_edits(char: Character, args) -> bool:
    """Apply CLI edit flags to a character. Returns True if anything changed."""
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
    if args.race is not None:
        char.race = args.race; modified = True
    if args.class_ is not None:
        char.char_class = args.class_; modified = True
    if args.gender is not None:
        char.gender = args.gender; modified = True
    if args.weapon is not None:
        char.equipped_weapon = args.weapon; modified = True
    if args.armor is not None:
        char.equipped_armor = args.armor; modified = True
    if args.give_weapon is not None:
        idx, count = args.give_weapon
        char.set_weapon_count(idx, count); modified = True
    if args.give_armor is not None:
        idx, count = args.give_armor
        char.set_armor_count(idx, count); modified = True
    if args.marks is not None:
        char.marks = [m.strip() for m in args.marks.split(',')]; modified = True
    if args.cards is not None:
        char.cards = [c.strip() for c in args.cards.split(',')]; modified = True
    if getattr(args, 'in_party', None):
        char.in_party = True; modified = True
    if getattr(args, 'not_in_party', None):
        char.in_party = False; modified = True
    if getattr(args, 'sub_morsels', None) is not None:
        char.sub_morsels = args.sub_morsels; modified = True
    return modified


def cmd_view(args) -> None:
    chars, _ = load_roster(args.file)
    filename = os.path.basename(args.file)

    do_validate = getattr(args, 'validate', False)

    if args.json:
        roster = []
        for i, char in enumerate(chars):
            if not char.is_empty:
                d = char.to_dict()
                d['slot'] = i
                if do_validate:
                    d['warnings'] = validate_character(char)
                roster.append(d)
        export_json(roster, args.output)
        return

    print(f"\n=== Ultima III Roster: {filename} ({len(chars)} slots) ===\n")

    if args.slot is not None:
        if args.slot < 0 or args.slot >= len(chars):
            print(f"Error: Slot {args.slot} out of range (0-{len(chars)-1})", file=sys.stderr)
            sys.exit(1)
        chars[args.slot].display(args.slot)
        if do_validate:
            for w in validate_character(chars[args.slot]):
                print(f"  WARNING: {w}", file=sys.stderr)
    else:
        found = False
        for i, char in enumerate(chars):
            if not char.is_empty:
                char.display(i)
                if do_validate:
                    for w in validate_character(char):
                        print(f"  WARNING: Slot {i}: {w}", file=sys.stderr)
                found = True
        if not found:
            print("  (All slots empty)")
    print()


def cmd_edit(args) -> None:
    chars, original = load_roster(args.file)
    do_validate = getattr(args, 'validate', False)
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)
    edit_all = getattr(args, 'all', False)

    if edit_all:
        # Bulk edit: apply to all non-empty slots
        modified = False
        for i, char in enumerate(chars):
            if not char.is_empty:
                if _apply_edits(char, args):
                    print(f"Modified slot {i}:")
                    char.display(i)
                    if do_validate:
                        for w in validate_character(char):
                            print(f"  WARNING: {w}", file=sys.stderr)
                    modified = True
        if not modified:
            print("No modifications specified.")
            return
    else:
        if args.slot is None:
            print("Error: --slot or --all required", file=sys.stderr)
            sys.exit(1)
        if args.slot < 0 or args.slot >= len(chars):
            print(f"Error: Slot {args.slot} out of range", file=sys.stderr)
            sys.exit(1)

        char = chars[args.slot]
        if char.is_empty:
            print(f"Error: Slot {args.slot} is empty. Use 'create' to make a new character.",
                  file=sys.stderr)
            sys.exit(1)

        if not _apply_edits(char, args):
            print("No modifications specified.")
            return
        print(f"Modified slot {args.slot}:")
        char.display(args.slot)
        if do_validate:
            for w in validate_character(char):
                print(f"  WARNING: {w}", file=sys.stderr)

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    save_roster(output, chars, original)


def cmd_create(args) -> None:
    chars, original = load_roster(args.file)
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)

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

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    save_roster(output, chars, original)


def cmd_import(args) -> None:
    """Import character data from a JSON file into a roster."""
    chars, original = load_roster(args.file)
    do_backup = getattr(args, 'backup', False)
    dry_run = getattr(args, 'dry_run', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("Error: JSON must be a list of character objects (with 'slot' field)", file=sys.stderr)
        sys.exit(1)

    count = 0
    for entry in data:
        slot = entry.get('slot')
        if slot is None or not (0 <= slot < len(chars)):
            continue
        char = chars[slot]
        if char.is_empty:
            char = Character(bytearray(CHAR_RECORD_SIZE))
            chars[slot] = char
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
        if 'marks' in entry:
            char.marks = entry['marks']
        if 'cards' in entry:
            char.cards = entry['cards']
        if 'in_party' in entry:
            char.in_party = entry['in_party']
        if 'sub_morsels' in entry:
            char.sub_morsels = entry['sub_morsels']
        if 'weapon' in entry:
            try:
                char.equipped_weapon = entry['weapon']
            except ValueError:
                print(f"  Warning: Unknown weapon '{entry['weapon']}' in slot {slot}, skipping",
                      file=sys.stderr)
        if 'armor' in entry:
            try:
                char.equipped_armor = entry['armor']
            except ValueError:
                print(f"  Warning: Unknown armor '{entry['armor']}' in slot {slot}, skipping",
                      file=sys.stderr)
        if 'weapons' in entry:
            for wname, wcount in entry['weapons'].items():
                try:
                    char.set_weapon_count(WEAPONS.index(wname), wcount)
                except ValueError:
                    print(f"  Warning: Unknown weapon '{wname}' in slot {slot} inventory, skipping",
                          file=sys.stderr)
        if 'armors' in entry:
            for aname, acount in entry['armors'].items():
                try:
                    char.set_armor_count(ARMORS.index(aname), acount)
                except ValueError:
                    print(f"  Warning: Unknown armor '{aname}' in slot {slot} inventory, skipping",
                          file=sys.stderr)
        count += 1

    print(f"Import: {count} character(s) to update")

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    save_roster(output, chars, original)
    print(f"Imported {count} character(s)")


def check_progress(chars: list[Character]) -> dict:
    """Analyze a roster for endgame readiness.

    Returns a dict with completion status for victory conditions:
    - All 4 marks (Kings, Snake, Fire, Force)
    - All 4 cards (Death, Sol, Love, Moons)
    - Exotic weapon equipped on at least one character
    - Exotic armor equipped on at least one character
    - Party of 4 non-dead characters
    """
    all_marks = {'Kings', 'Snake', 'Fire', 'Force'}
    all_cards = {'Death', 'Sol', 'Love', 'Moons'}

    active = [c for c in chars if not c.is_empty and c.status != 'Dead' and c.status != 'Ashes']

    # Collect marks and cards across all characters
    marks_found = set()
    cards_found = set()
    has_exotic_weapon = False
    has_exotic_armor = False

    for char in chars:
        if char.is_empty:
            continue
        marks_found.update(char.marks)
        cards_found.update(char.cards)
        if char.raw[CHAR_READIED_WEAPON] == 15:  # Exotic weapon index
            has_exotic_weapon = True
        if char.raw[CHAR_WORN_ARMOR] == 7:  # Exotic armor index
            has_exotic_armor = True

    marks_missing = all_marks - marks_found
    cards_missing = all_cards - cards_found

    return {
        'party_alive': len(active),
        'party_ready': len(active) >= 4,
        'marks_found': sorted(marks_found),
        'marks_missing': sorted(marks_missing),
        'marks_complete': len(marks_missing) == 0,
        'cards_found': sorted(cards_found),
        'cards_missing': sorted(cards_missing),
        'cards_complete': len(cards_missing) == 0,
        'has_exotic_weapon': has_exotic_weapon,
        'has_exotic_armor': has_exotic_armor,
        'exodus_ready': (
            len(marks_missing) == 0
            and len(cards_missing) == 0
            and has_exotic_weapon
            and has_exotic_armor
            and len(active) >= 4
        ),
    }


def cmd_check_progress(args) -> None:
    """Check roster for endgame readiness."""
    chars, _ = load_roster(args.file)

    progress = check_progress(chars)

    if getattr(args, 'json', False):
        export_json(progress, getattr(args, 'output', None))
        return

    print(f"\n=== Exodus Endgame Readiness ===\n")

    # Party status
    status = "READY" if progress['party_ready'] else "NOT READY"
    print(f"  Party:          {progress['party_alive']}/4 alive ({status})")

    # Marks
    status = "COMPLETE" if progress['marks_complete'] else "INCOMPLETE"
    print(f"  Marks:          {', '.join(progress['marks_found']) or 'None'} ({status})")
    if progress['marks_missing']:
        print(f"    Missing:      {', '.join(progress['marks_missing'])}")

    # Cards
    status = "COMPLETE" if progress['cards_complete'] else "INCOMPLETE"
    print(f"  Cards:          {', '.join(progress['cards_found']) or 'None'} ({status})")
    if progress['cards_missing']:
        print(f"    Missing:      {', '.join(progress['cards_missing'])}")

    # Exotic gear
    w = "Yes" if progress['has_exotic_weapon'] else "No"
    a = "Yes" if progress['has_exotic_armor'] else "No"
    print(f"  Exotic Weapon:  {w}")
    print(f"  Exotic Armor:   {a}")

    # Verdict
    print()
    if progress['exodus_ready']:
        print("  >>> READY TO FACE EXODUS <<<")
    else:
        print("  Not yet ready for Exodus. Requirements:")
        if not progress['party_ready']:
            print(f"    - Need 4 alive characters (have {progress['party_alive']})")
        if progress['marks_missing']:
            print(f"    - Missing marks: {', '.join(progress['marks_missing'])}")
        if progress['cards_missing']:
            print(f"    - Missing cards: {', '.join(progress['cards_missing'])}")
        if not progress['has_exotic_weapon']:
            print("    - Need Exotic weapon equipped")
        if not progress['has_exotic_armor']:
            print("    - Need Exotic armor equipped")
    print()


def _add_edit_args(p) -> None:
    """Add common character edit arguments to a parser."""
    p.add_argument('--name', help='Character name (max 9 chars)')
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
    p.add_argument('--race', help='Race: H(uman) E(lf) D(warf) B(obbit) F(uzzy)')
    p.add_argument('--class', dest='class_', help='Class: F C W T L I D A R P B')
    p.add_argument('--status', help='Status: G(ood) P(oisoned) D(ead) A(shes)')
    p.add_argument('--gender', help='Gender: M(ale) F(emale) O(ther)')
    p.add_argument('--weapon', type=int, help='Equipped weapon index (0-15)')
    p.add_argument('--armor', type=int, help='Equipped armor index (0-7)')
    p.add_argument('--give-weapon', type=int, nargs=2, metavar=('INDEX', 'COUNT'),
                   help='Set weapon inventory count (index 1-15, count 0-99)')
    p.add_argument('--give-armor', type=int, nargs=2, metavar=('INDEX', 'COUNT'),
                   help='Set armor inventory count (index 1-7, count 0-99)')
    p.add_argument('--marks', help='Marks (comma-separated: Kings,Snake,Fire,Force)')
    p.add_argument('--cards', help='Cards (comma-separated: Death,Sol,Love,Moons)')
    party_group = p.add_mutually_exclusive_group()
    party_group.add_argument('--in-party', action='store_true', default=None,
                             help='Set character as in-party')
    party_group.add_argument('--not-in-party', action='store_true', default=None,
                             help='Remove character from party')
    p.add_argument('--sub-morsels', type=int, help='Sub-morsels food fraction (0-99)')


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
    p_view.add_argument('--validate', action='store_true', help='Check game-rule violations')

    # Edit
    p_edit = sub.add_parser('edit', help='Edit a character')
    p_edit.add_argument('file', help='ROST file path')
    slot_group = p_edit.add_mutually_exclusive_group(required=True)
    slot_group.add_argument('--slot', type=int, help='Slot number (0-19)')
    slot_group.add_argument('--all', action='store_true', help='Edit all non-empty slots')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_edit.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    p_edit.add_argument('--validate', action='store_true', help='Check game-rule violations')
    _add_edit_args(p_edit)

    # Create
    p_create = sub.add_parser('create', help='Create a new character')
    p_create.add_argument('file', help='ROST file path')
    p_create.add_argument('--slot', type=int, required=True, help='Slot number (0-19)')
    p_create.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_create.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_create.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    p_create.add_argument('--name', help='Character name (default: HERO)')
    p_create.add_argument('--race', help='Race: H(uman) E(lf) D(warf) B(obbit) F(uzzy)')
    p_create.add_argument('--class', dest='class_', help='Class: F C W T L I D A R P B')
    p_create.add_argument('--gender', help='Gender: M(ale) F(emale) O(ther)')
    p_create.add_argument('--str', type=int, help='Strength')
    p_create.add_argument('--dex', type=int, help='Dexterity')
    p_create.add_argument('--int', type=int, dest='int_', help='Intelligence')
    p_create.add_argument('--wis', type=int, help='Wisdom')
    p_create.add_argument('--force', action='store_true', help='Overwrite existing')

    # Import
    p_import = sub.add_parser('import', help='Import characters from JSON')
    p_import.add_argument('file', help='ROST file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true', help='Show changes without writing')

    # Check progress
    p_progress = sub.add_parser('check-progress', help='Check endgame readiness')
    p_progress.add_argument('file', help='ROST file path')
    p_progress.add_argument('--json', action='store_true', help='Output as JSON')
    p_progress.add_argument('--output', '-o', help='Output file (for --json)')


def dispatch(args) -> None:
    """Dispatch roster subcommand."""
    if args.roster_command == 'view':
        cmd_view(args)
    elif args.roster_command == 'edit':
        cmd_edit(args)
    elif args.roster_command == 'create':
        cmd_create(args)
    elif args.roster_command == 'import':
        cmd_import(args)
    elif args.roster_command == 'check-progress':
        cmd_check_progress(args)
    else:
        print("Usage: u3edit roster {view|edit|create|import|check-progress} ...", file=sys.stderr)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Character Roster Viewer/Editor')
    sub = parser.add_subparsers(dest='roster_command')

    p_view = sub.add_parser('view', help='View roster contents')
    p_view.add_argument('file', help='ROST file path')
    p_view.add_argument('--slot', type=int, help='View specific slot (0-19)')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')
    p_view.add_argument('--validate', action='store_true', help='Check game-rule violations')

    p_edit = sub.add_parser('edit', help='Edit a character')
    p_edit.add_argument('file', help='ROST file path')
    slot_group = p_edit.add_mutually_exclusive_group(required=True)
    slot_group.add_argument('--slot', type=int, help='Slot number (0-19)')
    slot_group.add_argument('--all', action='store_true', help='Edit all non-empty slots')
    p_edit.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_edit.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_edit.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    p_edit.add_argument('--validate', action='store_true', help='Check game-rule violations')
    _add_edit_args(p_edit)

    p_create = sub.add_parser('create', help='Create a new character')
    p_create.add_argument('file', help='ROST file path')
    p_create.add_argument('--slot', type=int, required=True, help='Slot number (0-19)')
    p_create.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_create.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_create.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    p_create.add_argument('--name', help='Character name (default: HERO)')
    p_create.add_argument('--race', help='Race: H(uman) E(lf) D(warf) B(obbit) F(uzzy)')
    p_create.add_argument('--class', dest='class_', help='Class: F C W T L I D A R P B')
    p_create.add_argument('--gender', help='Gender: M(ale) F(emale) O(ther)')
    p_create.add_argument('--str', type=int, help='Strength')
    p_create.add_argument('--dex', type=int, help='Dexterity')
    p_create.add_argument('--int', type=int, dest='int_', help='Intelligence')
    p_create.add_argument('--wis', type=int, help='Wisdom')
    p_create.add_argument('--force', action='store_true', help='Overwrite existing')

    p_import = sub.add_parser('import', help='Import characters from JSON')
    p_import.add_argument('file', help='ROST file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true', help='Show changes without writing')

    p_progress = sub.add_parser('check-progress', help='Check endgame readiness')
    p_progress.add_argument('file', help='ROST file path')
    p_progress.add_argument('--json', action='store_true', help='Output as JSON')
    p_progress.add_argument('--output', '-o', help='Output file (for --json)')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
