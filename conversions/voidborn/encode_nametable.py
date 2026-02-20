#!/usr/bin/env python3
"""Generate hex-encoded name-table data for the Voidborn total conversion.

The ULT3 name-table is 921 bytes of null-terminated high-ASCII strings at
offset $397A. This script encodes all replacement names and outputs the hex
string suitable for: u3edit patch edit ULT3 --region name-table --data <HEX>

The last ~25 bytes of the vanilla name-table contain "BLOAD DDRW" and a
code fragment used by the disk loader. This script preserves them by reading
the original file if provided, or padding with nulls otherwise.

Usage:
    python encode_nametable.py                    # Output hex (nulls for tail)
    python encode_nametable.py /path/to/ULT3      # Preserve BLOAD DDRW tail
    python encode_nametable.py --apply /path/to/ULT3  # Apply directly
"""

import sys
import os

# Add project root to path for u3edit imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from u3edit.patch import encode_text_region, parse_text_region

MAX_LENGTH = 921
NAME_TABLE_OFFSET = 0x397A

# ============================================================================
# Voidborn replacement names — same order as vanilla engine lookup indices
# ============================================================================

# Group 1: Terrain and NPC "look" text (strings 0-38)
TERRAIN_NAMES = [
    "",             # 0: null/empty (ground)
    "BRINE",        # 1: was WATER
    "ASH",          # 2: was GRASS
    "THORNS",       # 3: was BRUSH
    "MYCELIUM",     # 4: was FOREST
    "SPIRES",       # 5: was MOUNTAINS
    "ABYSS",        # 6: was DUNGEON
    "HAVEN",        # 7: was TOWNE
    "BASTION",      # 8: was CASTLE
    "SLAB",         # 9: was FLOOR
    "CACHE",        # 10: was CHEST
    "BEAST",        # 11: was HORSE
    "RAFT",         # 12: was FRIGATE
    "MAELSTROM",    # 13: was WHIRLPOOL
    "KRAKEN",       # 14: was SERPENT
    "LEVIATHAN",    # 15: was MAN-O-WAR
    "RAIDER",       # 16: was PIRATE
    "TRADER",       # 17: was MERCHANT
    "MADMAN",       # 18: was JESTER
    "WARDEN",       # 19: was GUARD
    "THE PROPHET",  # 20: was LORD BRITISH
    "SLAYER",       # 21: was FIGHTER (NPC appearance)
    "PRIEST",       # 22: was CLERIC (NPC appearance)
    "SEER",         # 23: was WIZARD (NPC appearance)
    "SHADE",        # 24: was THIEF (NPC appearance)
    "THRALL",       # 25: was ORC
    "HUSK",         # 26: was SKELETON
    "BRUTE",        # 27: was GIANT
    "HORROR",       # 28: was DAEMON
    "LURKER",       # 29: was PINCHER
    "WATCHER",      # 30: was DRAGON
    "ABYSSAL",      # 31: was BALRON
    "VOIDBORN",     # 32: was EXODUS
    "NULL FIELD",   # 33: was FORCE FIELD
    "ICHOR",        # 34: was LAVA
    "RIFT",         # 35: was MOON GATE
    "RUIN",         # 36: was WALL
    "VOID",         # 37: was VOID
    "RUIN",         # 38: was WALL (second)
]

# Group 2: Single-char map letter codes (A-T + composites)
# These are engine-internal lookups — DO NOT CHANGE
MAP_CODES = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "U", "Y",
    "L", "M", "N", "O", "P", "W", "R", "S", "T",
    "SNAKE", "SNAKE", "MAGIC", "FIRE", "SHRINE", "RANGER",
]

# Group 3: Weapon names (16, indexed 0-15)
WEAPONS = [
    "FIST",         # 0: was HAND
    "SHIV",         # 1: was DAGGER
    "CLUB",         # 2: was MACE
    "SLING",        # 3: was SLING
    "AXE",          # 4: was AXE
    "BOW",          # 5: was BOW
    "BLADE",        # 6: was SWORD
    "GLAIVE",       # 7: was 2-H-SWD
    "V-AXE",        # 8: was +2 AXE (Void-touched)
    "V-BOW",        # 9: was +2 BOW
    "V-SWD",        # 10: was +2 SWD
    "TALONS",       # 11: was GLOVES
    "D-AXE",        # 12: was +4 AXE (Doom)
    "D-BOW",        # 13: was +4 BOW
    "D-SWD",        # 14: was +4 SWD
    "NULL",         # 15: was EXOTIC
]

# Group 4: Armor names (8, indexed 0-7)
ARMORS = [
    "SKIN",         # 0: was SKIN
    "RAGS",         # 1: was CLOTH
    "HIDE",         # 2: was LEATHER
    "LINKS",        # 3: was CHAIN
    "PLATE",        # 4: was PLATE
    "V-LINKS",      # 5: was +2 CHAIN (Void-warded)
    "V-PLATE",      # 6: was +2 PLATE
    "WARD",         # 7: was EXOTIC
]

# Group 5: Spell names
# Wizard spells (15), then a null separator, then cleric spells (16)
WIZARD_SPELLS = [
    "SPARK",        # was REPOND
    "SHARD",        # was MITTAR
    "WARP",         # was LORUM
    "REND",         # was DOR ACRON
    "DRAIN",        # was SUR ACRON
    "TEAR",         # was FULGAR
    "CRUSH",        # was DAG ACRON
    "SCRY",         # was MENTAR
    "BLIGHT",       # was DAG LORUM
    "SCOUR",        # was FAL DIVI
    "TOXIN",        # was NOXUM
    "UNMAKE",       # was DECORP
    "SHIFT",        # was ALTAIR
    "RIFT",         # was DAG MENTAR
    "ANNUL",        # was NECORP
]

CLERIC_SPELLS = [
    "MEND",         # was PONTORI
    "GLOW",         # was APPAR UNEM
    "SHIELD",       # was SANCTU
    "LUMINAE",      # was LUMINAE (kept — fits theme)
    "SLOW",         # was REC SU
    "REST",         # was REC DU
    "HEAL",         # was LIB REC
    "PURGE",        # was ALCORT
    "FOLLOW",       # was SEQUITU
    "SLEEP",        # was SOMINAE
    "BLESS",        # was SANCTU MANI
    "GUIDE",        # was VIEDA
    "BANISH",       # was EXCUUN
    "CLEANSE",      # was SURMANDUM
    "VEIL",         # was ZXKUQYB
    "RESTORE",      # was ANJU SERMANI
]

# Group 6: Monster alternate names (16, used contextually)
MONSTER_ALTS = [
    "MARAUDER",     # was BRIGAND
    "PICKPKT",      # was CUTPURSE
    "GREMLIN",      # was GOBLIN
    "OGRE",         # was TROLL
    "WRAITH",       # was GHOUL
    "RISEN",        # was ZOMBIE
    "COLOSSUS",     # was GOLEM
    "TITAN",        # was TITAN (kept)
    "CHIMERA",      # was GARGOYLE
    "SPECTRE",      # was MANE
    "HARPY",        # was SNATCH
    "FIEND",        # was BRADLE
    "RAPTOR",       # was GRIFFON
    "WYRM",         # was WYVERN
    "BLIGHT",       # was ORCUS
    "DREAD",        # was DEVIL
]


def build_all_names():
    """Combine all name groups in engine lookup order."""
    names = []
    names.extend(TERRAIN_NAMES)
    names.extend(MAP_CODES)
    names.extend(WEAPONS)
    names.extend(ARMORS)
    names.extend(WIZARD_SPELLS)
    names.append("")  # null separator between wizard and cleric spells
    names.extend(CLERIC_SPELLS)
    names.extend(MONSTER_ALTS)
    return names


def encode_names(names):
    """Encode name list as high-ASCII null-terminated bytes."""
    out = bytearray()
    for s in names:
        for ch in s:
            out.append((ord(ch) & 0x7F) | 0x80)
        out.append(0x00)
    return out


def main():
    names = build_all_names()
    encoded = encode_names(names)

    # Reserve space for BLOAD DDRW tail (preserved from original)
    tail_reserve = 30  # conservative estimate
    name_budget = MAX_LENGTH - tail_reserve

    print(f"# Voidborn name-table: {len(names)} strings, "
          f"{len(encoded)} bytes encoded", file=sys.stderr)
    print(f"# Budget: {name_budget} bytes for names + "
          f"{tail_reserve} bytes reserved for BLOAD DDRW tail", file=sys.stderr)

    if len(encoded) > name_budget:
        print(f"# ERROR: Names exceed budget by "
              f"{len(encoded) - name_budget} bytes!", file=sys.stderr)
        sys.exit(1)

    print(f"# Remaining: {name_budget - len(encoded)} bytes free",
          file=sys.stderr)

    # If ULT3 file provided, preserve the tail bytes
    if len(sys.argv) >= 2 and sys.argv[1] != '--apply':
        ult3_path = sys.argv[-1]
        with open(ult3_path, 'rb') as f:
            data = f.read()
        # Extract tail bytes from original
        tail_start = NAME_TABLE_OFFSET + len(encoded)
        tail_end = NAME_TABLE_OFFSET + MAX_LENGTH
        if tail_end <= len(data):
            tail = data[tail_start:tail_end]
            full = encoded + tail
        else:
            full = encoded + bytearray(MAX_LENGTH - len(encoded))
    else:
        # Pad with nulls (will lose BLOAD DDRW tail)
        full = encoded + bytearray(MAX_LENGTH - len(encoded))

    hex_str = full.hex().upper()

    if len(sys.argv) >= 2 and sys.argv[1] == '--apply':
        # Apply directly using u3edit CLI
        import subprocess
        ult3_path = sys.argv[2]
        cmd = [
            sys.executable, '-m', 'u3edit.patch',
            'edit', ult3_path,
            '--region', 'name-table',
            '--data', hex_str,
            '--backup',
        ]
        print(f"# Applying name-table to {ult3_path}...", file=sys.stderr)
        subprocess.run(cmd, check=True)
    else:
        # Output hex for manual use
        print(hex_str)


if __name__ == '__main__':
    main()
