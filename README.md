# u3edit

A complete data toolkit for **Ultima III: Exodus** (Apple II, 1983).

View, edit, and export all game data formats: character rosters, monster bestiaries, overworld and dungeon maps, NPC dialog, combat battlefields, save states, spells, equipment stats, and more. Works with extracted files or directly with ProDOS disk images.

## Installation

```bash
pip install -e .

# With development dependencies (pytest)
pip install -e ".[dev]"
```

Requires Python 3.10+. No runtime dependencies.

## Quick Start

```bash
# View characters
u3edit roster view path/to/GAME/ROST#069500

# View all monsters
u3edit bestiary view path/to/GAME/

# View the overworld map
u3edit map view path/to/GAME/MAPA#061000

# Overview of all maps with preview
u3edit map overview path/to/GAME/ --preview

# View NPC dialog
u3edit tlk view path/to/GAME/

# View combat battlefields
u3edit combat view path/to/GAME/

# View save state
u3edit save view path/to/GAME/

# Spell reference
u3edit spell view

# Equipment stats and class restrictions
u3edit equip view

# Export anything to JSON
u3edit roster view path/to/ROST#069500 --json -o roster.json
```

## Disk Image Support

If you have [diskiigs](https://github.com/BradHawthorne/rosetta) on your PATH (or set `DISKIIGS_PATH`), u3edit can work directly with ProDOS disk images:

```bash
u3edit disk info game.po
u3edit disk list game.po
```

## Tools

| Tool | Description | Commands |
|------|-------------|----------|
| `roster` | Character roster viewer/editor | `view`, `edit`, `create` |
| `bestiary` | Monster bestiary viewer/editor | `view`, `dump`, `edit` |
| `map` | Overworld, town, and dungeon map viewer | `view`, `overview`, `legend` |
| `tlk` | NPC dialog viewer/editor | `view`, `extract`, `build`, `edit` |
| `combat` | Combat battlefield viewer | `view` |
| `save` | Save state viewer/editor | `view`, `edit` |
| `special` | Special location viewer (shrines, fountains) | `view` |
| `text` | Game text string viewer | `view` |
| `spell` | Spell reference (wizard + cleric) | `view` |
| `equip` | Equipment stats and class restrictions | `view` |

Each tool is also available standalone: `u3-roster`, `u3-bestiary`, `u3-map`, etc.

## Editing Characters

```bash
# Edit a character's stats
u3edit roster edit ROST#069500 --slot 0 --str 99 --hp 9999 --gold 9999

# Give all marks and cards
u3edit roster edit ROST#069500 --slot 0 --marks "Kings,Snake,Fire,Force" --cards "Death,Sol,Love,Moons"

# Create a new character
u3edit roster create ROST#069500 --slot 5 --name "WIZARD" --race E --class W --gender F
```

## Editing Monsters

```bash
# Make monster #0 in MONA tougher
u3edit bestiary edit MONA#069900 --monster 0 --hp 200 --attack 80
```

## Editing Save State

```bash
# Teleport the party
u3edit save edit path/to/GAME/ --x 32 --y 32 --transport horse
```

## File Formats

### Character Record (ROST, 64 bytes per slot, 20 slots)

| Offset | Size | Field | Encoding |
|--------|------|-------|----------|
| 0x00 | 10 | Name | High-bit ASCII |
| 0x0E | 1 | Marks/Cards | Bitmask (hi=marks, lo=cards) |
| 0x0F | 1 | Torches | Count |
| 0x11 | 1 | Status | ASCII: G/P/D/A |
| 0x12-0x15 | 4 | STR/DEX/INT/WIS | BCD (0-99 each) |
| 0x16-0x18 | 3 | Race/Class/Gender | ASCII codes |
| 0x19 | 1 | MP | Raw byte |
| 0x1A-0x1B | 2 | HP | BCD16 (0-9999) |
| 0x1C-0x1D | 2 | Max HP | BCD16 (0-9999) |
| 0x1E-0x1F | 2 | EXP | BCD16 (0-9999) |
| 0x20 | 1 | Sub-morsels | Food fraction |
| 0x21-0x22 | 2 | Food | BCD16 (0-9999) |
| 0x23-0x24 | 2 | Gold | BCD16 (0-9999) |
| 0x25-0x27 | 3 | Gems/Keys/Powders | BCD (0-99 each) |
| 0x28 | 1 | Worn armor | Index (0-7) |
| 0x30 | 1 | Readied weapon | Index (0-15) |

### Monster Record (MON, columnar: 16 rows x 16 monsters)

| Row | Attribute |
|-----|-----------|
| 0 | Tile/sprite 1 |
| 1 | Tile/sprite 2 |
| 2 | Flags 1 (undead/ranged/magic/boss) |
| 3 | Flags 2 |
| 4 | HP (0-255) |
| 5 | Attack (0-255) |
| 6 | Defense (0-255) |
| 7 | Speed (0-255) |
| 8-9 | Ability flags |

### Overworld/Town Map (MAP, 4096 bytes = 64x64)

Tile IDs are multiples of 4; low 2 bits are animation frame. Use `& 0xFC` for canonical ID.

### Dungeon Map (MAP, 2048 bytes = 8 levels x 16x16)

Lower nibble encodes tile type (0=open, 1=wall, 2=door, etc.).

### TLK Dialog (variable length)

High-bit ASCII text. `0xFF` = line break, `0x00` = record terminator. Binary data (embedded code) is automatically filtered.

### Combat Map (CON, 192 bytes)

11x11 tile grid + monster/PC start positions.

## ProDOS Filename Convention

Extracted ProDOS files use a `#TTAAAA` suffix encoding file type and aux type:
- `ROST#069500` = type $06 (BIN), aux $9500 (load address)
- `MAPA#061000` = type $06 (BIN), aux $1000

## Running Tests

```bash
pip install -e ".[dev]"
pytest -v
```

163 tests covering all modules with synthesized game data (no real game files needed).

## Bug Fixes from Prototype

| ID | Module | Fix |
|----|--------|-----|
| R-1 | roster | Removed fake "Lv" display (was reading food byte as level) |
| R-2 | roster | Fixed marks/cards bitmask (high nibble = marks, low nibble = cards) |
| R-3 | roster | Removed unused import |
| R-4 | roster | Decode offset 0x20 as sub-morsels (food fraction) |
| B-1 | bestiary | Replaced wrong TILE_NAMES dict with correct MONSTER_NAMES + TILES |
| B-2 | bestiary | Removed dead FLAG1_BITS dict |
| M-1 | map | Full tile table with &0xFC masking (was 0x00-0x1F only) |

## License

MIT
