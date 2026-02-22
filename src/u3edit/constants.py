"""Ultima III: Exodus - Complete game data constants.

Single source of truth for all tile tables, character record layouts,
item names, map names, monster names, and file format specifications.
"""

# =============================================================================
# Overworld / Town Tile Table
# =============================================================================
# Tile IDs are multiples of 4. Low 2 bits are animation frame.
# Use (tile_byte & 0xFC) to get the canonical tile ID.
# Format: tile_id -> (display_char, name)

TILES = {
    0x00: ('~', 'Water'),
    0x04: ('.', 'Grass'),
    0x08: ('"', 'Brush'),
    0x0C: ('T', 'Forest'),
    0x10: ('^', 'Mountains'),
    0x14: ('D', 'Dungeon'),
    0x18: ('#', 'Town'),
    0x1C: ('@', 'Castle'),
    0x20: ('_', 'Floor'),
    0x24: ('$', 'Chest'),
    0x28: ('h', 'Horse'),
    0x2C: ('S', 'Ship'),
    0x30: ('O', 'Whirlpool'),
    0x34: ('s', 'Serpent'),
    0x38: ('W', 'Man-o-War'),
    0x3C: ('P', 'Pirate Ship'),
    0x40: ('M', 'Merchant'),
    0x44: ('J', 'Jester'),
    0x48: ('G', 'Guard'),
    0x4C: ('L', 'Lord British'),
    0x50: ('F', 'Fighter'),
    0x54: ('C', 'Cleric'),
    0x58: ('w', 'Wizard'),
    0x5C: ('t', 'Thief'),
    0x60: ('o', 'Orc'),
    0x64: ('k', 'Skeleton'),
    0x68: ('g', 'Giant'),
    0x6C: ('d', 'Daemon'),
    0x70: ('p', 'Pincher'),
    0x74: ('R', 'Dragon'),
    0x78: ('B', 'Balron'),
    0x7C: ('X', 'Exodus'),
    0x80: ('!', 'Force Field'),
    0x84: ('*', 'Lava'),
    0x88: ('0', 'Moongate'),
    0x8C: ('|', 'Wall'),
    0x90: (' ', 'Void'),
    0x94: (':', 'Brick'),
    0x98: ('-', 'Bridge'),
    0x9C: ('=', 'Sign'),
    0xA0: ('c', 'Counter'),
    0xA4: ('b', 'Bed'),
    0xA8: ('%', 'Ankh'),
    0xAC: ('/', 'Door North'),
    0xB0: ('\\', 'Door East'),
    0xF0: ('+', 'Magic Effect'),
    0xF4: ('f', 'Fire Effect'),
    0xFC: ('?', 'Hidden'),
}


def tile_char(byte_val: int, is_dungeon: bool = False) -> str:
    """Get the display character for a tile byte value."""
    if is_dungeon:
        entry = DUNGEON_TILES.get(byte_val & 0x0F)
        return entry[0] if entry else '?'
    entry = TILES.get(byte_val & 0xFC)
    return entry[0] if entry else '?'


def tile_name(byte_val: int, is_dungeon: bool = False) -> str:
    """Get the human-readable name for a tile byte value."""
    if is_dungeon:
        entry = DUNGEON_TILES.get(byte_val & 0x0F)
        return entry[1] if entry else f'Unknown(${byte_val:02X})'
    entry = TILES.get(byte_val & 0xFC)
    return entry[1] if entry else f'Unknown(${byte_val:02X})'


# Reverse lookup: display char -> canonical tile byte (for map import)
TILE_CHARS_REVERSE = {ch: tile_id for tile_id, (ch, _) in TILES.items()}
TILE_NAMES_REVERSE = {name.lower(): tile_id for tile_id, (_, name) in TILES.items()}

# =============================================================================
# Dungeon Tile Table
# =============================================================================
# Dungeon tiles use a separate encoding (lower nibble only).

DUNGEON_TILES = {
    0x00: ('.', 'Open'),
    0x01: ('#', 'Wall'),
    0x02: ('D', 'Door'),
    0x03: ('>', 'Secret Door'),
    0x04: ('$', 'Chest'),
    0x05: ('V', 'Ladder Down'),
    0x06: ('^', 'Ladder Up'),
    0x07: ('B', 'Ladder Both'),
    0x08: ('T', 'Trap'),
    0x09: ('F', 'Fountain'),
    0x0A: ('M', 'Mark'),
    0x0B: ('W', 'Wind'),
    0x0C: ('G', 'Gremlins'),
    0x0D: ('O', 'Orb'),
    0x0E: ('P', 'Pit'),
    0x0F: ('?', 'Unknown'),
}

DUNGEON_TILE_CHARS_REVERSE = {ch: tile_id for tile_id, (ch, _) in DUNGEON_TILES.items()}
DUNGEON_TILE_NAMES_REVERSE = {name.lower(): tile_id for tile_id, (_, name) in DUNGEON_TILES.items()}

# =============================================================================
# Character Races and Classes
# =============================================================================

RACES = {
    ord('H'): 'Human',
    ord('E'): 'Elf',
    ord('D'): 'Dwarf',
    ord('B'): 'Bobbit',
    ord('F'): 'Fuzzy',
}
RACE_CODES = {v[0].upper(): k for k, v in RACES.items()}

CLASSES = {
    ord('F'): 'Fighter',
    ord('C'): 'Cleric',
    ord('W'): 'Wizard',
    ord('T'): 'Thief',
    ord('L'): 'Lark',
    ord('I'): 'Illusionist',
    ord('D'): 'Druid',
    ord('A'): 'Alchemist',
    ord('R'): 'Ranger',
    ord('P'): 'Paladin',
    ord('B'): 'Barbarian',
}
CLASS_CODES = {v[0].upper(): k for k, v in CLASSES.items()}

GENDERS = {ord('M'): 'Male', ord('F'): 'Female', ord('O'): 'Other'}

STATUS_CODES = {
    ord('G'): 'Good',
    ord('P'): 'Poisoned',
    ord('D'): 'Dead',
    ord('A'): 'Ashes',
}

# Race stat maximums: (STR, DEX, INT, WIS)
RACE_MAX_STATS = {
    'Human':  (75, 75, 75, 75),
    'Elf':    (75, 99, 75, 50),
    'Dwarf':  (99, 75, 50, 75),
    'Bobbit': (75, 50, 75, 99),
    'Fuzzy':  (25, 99, 99, 75),
}

# =============================================================================
# Weapons and Armor
# =============================================================================

WEAPONS = [
    'Hands', 'Dagger', 'Mace', 'Sling', 'Axe', 'Bow', 'Sword',
    '2H Sword', '+2 Axe', '+2 Bow', '+2 Sword', 'Gloves',
    '+4 Axe', '+4 Bow', '+4 Sword', 'Exotic',
]

# Weapon base damage and price (index matches WEAPONS)
WEAPON_DAMAGE = [0, 4, 8, 4, 12, 8, 16, 20, 18, 14, 22, 24, 24, 20, 28, 30]
WEAPON_PRICE = [0, 20, 50, 30, 100, 80, 150, 200, 300, 280, 350, 500, 500, 480, 550, 9999]

ARMORS = [
    'Skin', 'Cloth', 'Leather', 'Chain', 'Plate',
    '+2 Chain', '+2 Plate', 'Exotic',
]

# Armor evasion percentage (index matches ARMORS)
ARMOR_EVASION = [50.0, 51.2, 53.1, 56.2, 59.4, 60.9, 63.3, 65.2]

# Class maximum weapon/armor tier (index into WEAPONS/ARMORS)
CLASS_MAX_WEAPON = {
    'Fighter': 15, 'Cleric': 2, 'Wizard': 1, 'Thief': 6,
    'Lark': 6, 'Illusionist': 6, 'Druid': 2, 'Alchemist': 6,
    'Ranger': 15, 'Paladin': 15, 'Barbarian': 15,
}
CLASS_MAX_ARMOR = {
    'Fighter': 7, 'Cleric': 5, 'Wizard': 1, 'Thief': 2,
    'Lark': 2, 'Illusionist': 2, 'Druid': 2, 'Alchemist': 2,
    'Ranger': 7, 'Paladin': 7, 'Barbarian': 7,
}

# =============================================================================
# Marks and Cards (byte 0x0E bitmask)
# =============================================================================
# High nibble = Marks, Low nibble = Cards

MARKS_BITS = {
    7: 'Kings',
    6: 'Snake',
    5: 'Fire',
    4: 'Force',
}

CARDS_BITS = {
    3: 'Death',
    2: 'Moons',
    1: 'Sol',
    0: 'Love',
}

# =============================================================================
# Spells
# =============================================================================

WIZARD_SPELLS = [
    ('Repond', 5), ('Mittar', 5), ('Lorum', 10), ('Dumapic', 15),
    ('Calfo', 20), ('Morlis', 25), ('Pontori', 30), ('Bolatu', 35),
    ('Malor', 40), ('Lakanito', 45), ('Nacal', 50), ('Appar Unem', 55),
    ('Zilwan', 60), ('Excuun', 65), ('Lorto', 70), ('Mani', 75),
]

CLERIC_SPELLS = [
    ('Sanctu', 5), ('Luminae', 5), ('Dag Acron', 10), ('Alcort', 15),
    ('Sequitu', 20), ('Sominae', 25), ('Sanctu Mani', 30), ('Zxkuqyb', 35),
    ('Anju Sermani', 40), ('Noxum', 45), ('Decorp', 50), ('Altair', 55),
    ('Dag Lificina', 60), ('Lava', 65), ('Pontori', 70), ('Xen Corp', 75),
]

# =============================================================================
# Character Record Layout (64 bytes per character)
# =============================================================================

CHAR_RECORD_SIZE = 64
CHAR_MAX_SLOTS = 20

# Field offsets
CHAR_NAME_OFFSET = 0x00
CHAR_NAME_LENGTH = 10       # Legacy: visible columns in roster display
CHAR_NAME_MAX = 13           # Max input chars (engine CPY #$0D loop in BOOT.s)
CHAR_NAME_FIELD = 14         # Full field: 13 chars + guaranteed null at 0x0D
CHAR_MARKS_CARDS = 0x0E
CHAR_TORCHES = 0x0F
CHAR_IN_PARTY = 0x10
CHAR_STATUS = 0x11
CHAR_STR = 0x12
CHAR_DEX = 0x13
CHAR_INT = 0x14
CHAR_WIS = 0x15
CHAR_RACE = 0x16
CHAR_CLASS = 0x17
CHAR_GENDER = 0x18
CHAR_MP = 0x19
CHAR_HP_HI = 0x1A
CHAR_HP_LO = 0x1B
CHAR_MAX_HP_HI = 0x1C
CHAR_MAX_HP_LO = 0x1D
CHAR_EXP_HI = 0x1E
CHAR_EXP_LO = 0x1F
CHAR_SUB_MORSELS = 0x20
CHAR_FOOD_HI = 0x21
CHAR_FOOD_LO = 0x22
CHAR_GOLD_HI = 0x23
CHAR_GOLD_LO = 0x24
CHAR_GEMS = 0x25
CHAR_KEYS = 0x26
CHAR_POWDERS = 0x27
CHAR_WORN_ARMOR = 0x28
CHAR_ARMOR_START = 0x29  # 7 armor counts (Cloth..Exotic)
CHAR_READIED_WEAPON = 0x30
CHAR_WEAPON_START = 0x31  # 15 weapon counts (Dagger..Exotic)

# =============================================================================
# Monster Attributes (MON file columnar layout)
# =============================================================================
# Each MON file: 256 bytes = 16 rows x 16 monsters (columnar)
# Row N, Monster M = file[N * 16 + M]
#
# At runtime ($4F00), the engine repurposes rows 0-9 as five 32-entry
# parallel arrays for overworld creature tracking:
#   $4F00,X: creature tile/sprite     $4F20,X: animation frame
#   $4F40,X: creature X coordinate    $4F60,X: creature Y coordinate
#   $4F80,X: status flags ($C0=active)
#
# Rows 10-14 + most of row 15 are unused padding (92 bytes).
# Last 4 bytes ($4FFC-$4FFF) are runtime ship navigation workspace:
#   $4FFC: ship X position    $4FFD: ship Y position
#   $4FFE: X velocity         $4FFF: Y velocity

MON_ATTR_TILE1 = 0
MON_ATTR_TILE2 = 1
MON_ATTR_FLAGS1 = 2
MON_ATTR_FLAGS2 = 3
MON_ATTR_HP = 4
MON_ATTR_ATTACK = 5
MON_ATTR_DEFENSE = 6
MON_ATTR_SPEED = 7
MON_ATTR_ABILITY1 = 8
MON_ATTR_ABILITY2 = 9
MON_ATTR_COUNT = 10       # Only 10 meaningful attribute rows
MON_TOTAL_ROWS = 16       # Rows 10-15 are padding/runtime workspace
MON_MONSTERS_PER_FILE = 16

MON_ATTR_NAMES = [
    'Tile 1', 'Tile 2', 'Flags 1', 'Flags 2',
    'HP', 'Attack', 'Defense', 'Speed',
    'Ability 1', 'Ability 2',
]

# Flag bitmasks (flags1 byte, row 2)
# Bits 2-3 encode a 3-way type: 0x04=Undead, 0x08=Ranged, 0x0C=Magic User
MON_FLAG1_UNDEAD = 0x04
MON_FLAG1_RANGED = 0x08
MON_FLAG1_MAGIC_USER = 0x0C  # bits 2+3 both set
MON_FLAG1_BOSS = 0x80

# Ability bitmasks (ability1 byte, row 8)
MON_ABIL1_POISON = 0x01
MON_ABIL1_SLEEP = 0x02
MON_ABIL1_NEGATE = 0x04
MON_ABIL1_TELEPORT = 0x40
MON_ABIL1_DIVIDE = 0x80

# Ability bitmasks (ability2 byte, row 9)
MON_ABIL2_RESISTANT = 0xC0

# Monster sprite names by tile ID (tile1 value from MON file).
# In Ultima III, monster identity is determined by the tile sprite index.
# Encounter groups may share the same sprite for all members.
MONSTER_NAMES = {
    0x20: 'Invisible',
    0x24: 'Mimic',
    0x28: 'Phantom',
    0x2C: 'Frigate',
    0x34: 'Sea Serpent',
    0x38: "Man-o'-War",
    0x3C: 'Pirate Ship',
    0x40: 'Brigand',
    0x44: 'Floor Devil',
    0x48: 'Fighter',
    0x4C: 'Dark Knight',
    0x50: 'Ranger',
    0x54: 'Cleric',
    0x58: 'Wizard',
    0x5C: 'Thief',
    0x60: 'Orc',
    0x64: 'Skeleton',
    0x68: 'Giant',
    0x6C: 'Daemon',
    0x70: 'Pincher',
    0x74: 'Dragon',
    0x78: 'Balron',
    0x7C: 'Exodus',
    0xFC: 'Devil',
}

# Reverse lookup: name -> tile1 value (for --type name editing)
MONSTER_NAMES_REVERSE = {name.lower(): tile for tile, name in MONSTER_NAMES.items()}

# Context-aware monster group names for each MON encounter file.
# These provide better names when the same sprite tile is used for all
# monsters in a file. Key: MON file letter. Value: group description.
MON_GROUP_NAMES = {
    'A': 'Grassland',
    'B': 'Forest',
    'C': 'Mountain',
    'D': 'Ocean',
    'E': 'Town Guard',
    'F': 'Dungeon L1-2',
    'G': 'Dungeon L3-4',
    'H': 'Dungeon L5-6',
    'I': 'Dungeon L7-8',
    'J': 'Castle',
    'K': 'Ambrosia',
    'L': 'Special',
    'Z': 'Boss',
}

# =============================================================================
# Map Names
# =============================================================================

MAP_NAMES = {
    'A': 'Sosaria (Overworld)',
    'B': 'Lord British Castle',
    'C': 'Castle of Death',
    'D': 'Town of Dawn',
    'E': 'Town of Fawn',
    'F': 'Town of Grey',
    'G': 'Town of Moon',
    'H': 'Town of Yew',
    'I': 'Town of Montor East',
    'J': 'Town of Montor West',
    'K': 'Town of Devil Guard',
    'L': 'Ambrosia',
    'M': 'Dungeon of Fire',
    'N': 'Dungeon of Doom',
    'O': 'Dungeon of Snake',
    'P': 'Dungeon of Perinian',
    'Q': 'Dungeon of Time',
    'R': 'Dungeon of Mine',
    'S': 'Dungeon of Darkling',
    'Z': 'Exodus Castle Interior',
}

# Letters used for scanning MAP files
MAP_LETTERS = 'ABCDEFGHIJKLMNOPQRSZ'

# =============================================================================
# Monster Encounter Terrain Names
# =============================================================================

MON_TERRAIN = {
    'A': 'Grassland/Plains',
    'B': 'Forest/Woods',
    'C': 'Mountains',
    'D': 'Water/Ocean',
    'E': 'Town Guards',
    'F': 'Dungeon Level 1-2',
    'G': 'Dungeon Level 3-4',
    'H': 'Dungeon Level 5-6',
    'I': 'Dungeon Level 7-8',
    'J': 'Castle/Fortress',
    'K': 'Ambrosia',
    'L': 'Special Encounters',
    'Z': 'Bosses/Unique',
}

MON_LETTERS = 'ABCDEFGHIJKLZ'

# =============================================================================
# Combat / Conflict Map Names
# =============================================================================

CON_NAMES = {
    'A': 'Lord British Castle',
    'B': 'Castle of Death',
    'C': 'Castle Arena',
    'F': 'Dungeon',
    'G': 'Grassland',
    'M': 'Mountains',
    'Q': 'Water',
    'R': 'Forest',
    'S': 'Town',
}

CON_LETTERS = 'ABCFGMQRS'

# Combat map dimensions and layout (192 bytes, loaded at $9900)
# Layout verified by tracing engine code in ULT3.s:
#   0x00-0x78: 11x11 tile grid (121 bytes, accessed via lookup_add at $7E18)
#   0x79-0x7F: Unused padding (7 bytes, never read by engine)
#   0x80-0x87: Monster start X positions [0-7] (read during spawn)
#   0x88-0x8F: Monster start Y positions [0-7] (read during spawn)
#   0x90-0x97: Runtime: saved tile under monster (overwritten at combat init)
#   0x98-0x9F: Runtime: monster type/status (overwritten at combat init)
#   0xA0-0xA3: PC start X positions [0-3] (read during init)
#   0xA4-0xA7: PC start Y positions [0-3] (read during init)
#   0xA8-0xAB: Runtime: saved tile under PC (overwritten at init)
#   0xAC-0xAF: Runtime: PC appearance tile (overwritten by JSR $7F5D)
#   0xB0-0xBF: Unused tail padding (16 bytes, never read by engine)
CON_MAP_WIDTH = 11
CON_MAP_HEIGHT = 11
CON_MAP_TILES = CON_MAP_WIDTH * CON_MAP_HEIGHT  # 121 bytes
CON_PADDING1_OFFSET = 0x79   # 7 bytes unused padding after tile grid
CON_PADDING1_SIZE = 7
CON_MONSTER_X_OFFSET = 0x80
CON_MONSTER_Y_OFFSET = 0x88
CON_MONSTER_COUNT = 8
CON_RUNTIME_MONSAVE_OFFSET = 0x90  # 8 bytes: saved tile under monster (runtime)
CON_RUNTIME_MONSTATUS_OFFSET = 0x98  # 8 bytes: monster type/status (runtime)
CON_PC_X_OFFSET = 0xA0
CON_PC_Y_OFFSET = 0xA4
CON_PC_COUNT = 4
CON_RUNTIME_PCSAVE_OFFSET = 0xA8  # 4 bytes: saved tile under PC (runtime)
CON_RUNTIME_PCTILE_OFFSET = 0xAC  # 4 bytes: PC appearance tile (runtime)
CON_PADDING2_OFFSET = 0xB0   # 16 bytes unused tail padding
CON_PADDING2_SIZE = 16

# =============================================================================
# TLK (Dialog) File Constants
# =============================================================================

TLK_LETTERS = 'ABCDEFGHIJKLMNOPQRS'
TLK_LINE_BREAK = 0xFF
TLK_RECORD_END = 0x00

TLK_NAMES = {
    'A': 'Lord British Castle',
    'B': 'Castle of Death',
    'C': 'Castle Arena',
    'D': 'Town of Dawn',
    'E': 'Town of Fawn',
    'F': 'Town of Grey',
    'G': 'Town of Moon',
    'H': 'Town of Yew',
    'I': 'Town of Montor East',
    'J': 'Town of Montor West',
    'K': 'Town of Devil Guard',
    'L': 'Ambrosia',
    'M': 'Dungeon of Fire',
    'N': 'Dungeon of Doom',
    'O': 'Dungeon of Snake',
    'P': 'Dungeon of Perinian',
    'Q': 'Dungeon of Time',
    'R': 'Dungeon of Mine',
    'S': 'Dungeon of Darkling',
}

# =============================================================================
# Special Location Names
# =============================================================================

SPECIAL_NAMES = {
    'BRND': 'Brand Shrine',
    'SHRN': 'Shrines',
    'FNTN': 'Fountains',
    'TIME': 'Time Lord',
}

SPECIAL_MAP_WIDTH = 11
SPECIAL_MAP_HEIGHT = 11
SPECIAL_MAP_TILES = SPECIAL_MAP_WIDTH * SPECIAL_MAP_HEIGHT  # 121 bytes

# =============================================================================
# Save State Constants (PRTY file — 16 bytes at zero-page $E0-$EF)
# =============================================================================
# Layout verified by tracing engine code in ult3_analysis.s:
#   $E0 = transport/movement mode (SPEEDZ)
#   $E1 = party member count (0-4)
#   $E2 = location type (0=Sosaria, 1=Dungeon, 2=Town, etc.)
#   $E3 = saved overworld X coordinate
#   $E4 = saved overworld Y coordinate (ERRFLG)
#   $E5 = status sentinel ($FF when party is active)
#   $E6-$E9 = roster slot IDs for 4 party members
#   $EA-$EF = unused

PRTY_OFF_TRANSPORT = 0     # $E0 — movement/transport mode
PRTY_OFF_PARTY_SIZE = 1    # $E1 — party member count (0-4)
PRTY_OFF_LOCATION = 2      # $E2 — location type code
PRTY_OFF_SAVED_X = 3       # $E3 — saved overworld X
PRTY_OFF_SAVED_Y = 4       # $E4 — saved overworld Y
PRTY_OFF_SENTINEL = 5      # $E5 — active party flag ($FF = active)
PRTY_OFF_SLOT_IDS = 6      # $E6-$E9 — roster slot indices (4 bytes)

PRTY_TRANSPORT = {
    0x00: 'None',
    0x01: 'On Foot',
    0x0A: 'Horse',
    0x0B: 'Ship',
    0x3F: 'On Foot (Default)',
}

# Reverse mapping: prefer 0x01 for 'on foot' (0x3F is the power-on default)
PRTY_TRANSPORT_CODES = {
    'none': 0x00,
    'on foot': 0x01,
    'foot': 0x01,
    'on foot (default)': 0x3F,
    'horse': 0x0A,
    'ship': 0x0B,
}

PRTY_LOCATION_TYPE = {
    0x00: 'Sosaria',
    0x01: 'Dungeon',
    0x02: 'Town',
    0x03: 'Castle',
    0x04: 'Shrine/Fountain/Mark',
    0x80: 'Combat',
    0xF0: 'Merchant',
    0xFF: 'Ambrosia',
}

PRTY_LOCATION_CODES = {v.lower(): k for k, v in PRTY_LOCATION_TYPE.items()}

# =============================================================================
# File Size Constants (for validation)
# =============================================================================

ROSTER_FILE_SIZE = CHAR_RECORD_SIZE * CHAR_MAX_SLOTS  # 1280
MON_FILE_SIZE = 256
MAP_OVERWORLD_SIZE = 4096
MAP_DUNGEON_SIZE = 2048
CON_FILE_SIZE = 192
SPECIAL_FILE_SIZE = 128
TEXT_FILE_SIZE = 1024
PRTY_FILE_SIZE = 16
PLRS_FILE_SIZE = 256
SOSA_FILE_SIZE = 4096
SOSM_FILE_SIZE = 256
SHPS_FILE_SIZE = 2048
MBS_FILE_SIZE = 5456
DDRW_FILE_SIZE = 1792
ULT3_FILE_SIZE = 17408
EXOD_FILE_SIZE = 26208
SUBS_FILE_SIZE = 3584

# JSR $46BA inline string printer pattern (Apple II)
# Used by shapes.py (SHP overlays) and patch.py (engine strings)
JSR_46BA = bytes([0x20, 0xBA, 0x46])
