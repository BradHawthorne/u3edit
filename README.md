# u3edit

A complete data toolkit for **Ultima III: Exodus** (Apple II, 1983).

View, edit, and export all game data formats: character rosters, monster bestiaries, overworld and dungeon maps, NPC dialog, combat battlefields, save states, spells, equipment stats, and more. Works with extracted files or directly with ProDOS disk images.

## Installation

```bash
pip install -e .

# With development dependencies (pytest)
pip install -e ".[dev]"

# With TUI support (prompt_toolkit)
pip install -e ".[tui]"
```

Requires Python 3.10+. No runtime dependencies.

## Quick Start

```bash
# Interactive TUI editor (requires prompt_toolkit)
u3edit edit game.po

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

## Unified TUI Editor

The interactive text-based editor provides a tabbed interface for editing all game data in one session. Requires `prompt_toolkit`:

```bash
pip install -e ".[tui]"

# Edit a ProDOS disk image directly
u3edit edit game.po

# Edit extracted files in a directory
u3edit edit path/to/GAME/
```

The TUI supports tile painting for maps, form editing for character stats and monster attributes, and in-place dialog editing. Changes are written back to the disk image or directory on save.

## Disk Image Support

If you have [diskiigs](https://github.com/BradHawthorne/rosetta) on your PATH (or set `DISKIIGS_PATH`), u3edit can work directly with ProDOS disk images:

```bash
u3edit disk info game.po
u3edit disk list game.po
```

## Tools

| Tool | Description | Commands |
|------|-------------|----------|
| `roster` | Character roster viewer/editor | `view`, `edit`, `create`, `import`, `check-progress` |
| `bestiary` | Monster bestiary viewer/editor | `view`, `dump`, `edit`, `import` |
| `map` | Overworld, town, and dungeon map viewer/editor | `view`, `overview`, `legend`, `edit`, `set`, `fill`, `replace`, `find`, `import` |
| `tlk` | NPC dialog viewer/editor | `view`, `extract`, `build`, `edit`, `search`, `import` |
| `combat` | Combat battlefield viewer/editor | `view`, `edit`, `import` |
| `save` | Save state viewer/editor | `view`, `edit`, `import` |
| `special` | Special location viewer/editor (shrines, fountains) | `view`, `edit`, `import` |
| `text` | Game text string viewer/editor | `view`, `edit`, `import` |
| `spell` | Spell reference (wizard + cleric) | `view` |
| `equip` | Equipment stats and class restrictions | `view` |
| `shapes` | Tile graphics / character set editor | `view`, `export`, `edit`, `import`, `info` |
| `sound` | Sound data editor (SOSA, SOSM, MBS) | `view`, `edit`, `import` |
| `patch` | Engine binary patcher (CIDAR offsets) | `view`, `edit`, `dump` |
| `ddrw` | Dungeon drawing data editor | `view`, `edit`, `import` |
| `diff` | Game data comparison tool | (compares two files or directories) |
| `disk` | ProDOS disk image operations | `info`, `list`, `extract`, `audit` |

Each tool is also available standalone: `u3-roster`, `u3-bestiary`, `u3-map`, etc.

## Editing Characters

```bash
# Edit a character's stats
u3edit roster edit ROST#069500 --slot 0 --str 99 --hp 9999 --gold 9999

# Give all marks and cards
u3edit roster edit ROST#069500 --slot 0 --marks "Kings,Snake,Fire,Force" --cards "Death,Sol,Love,Moons"

# Bulk edit all characters at once
u3edit roster edit ROST#069500 --all --gold 9999 --food 9999

# Create a new character
u3edit roster create ROST#069500 --slot 5 --name "WIZARD" --race E --class W --gender F

# Validate roster for game-rule violations
u3edit roster view ROST#069500 --validate

# Check endgame readiness
u3edit roster check-progress ROST#069500
```

## Editing Monsters

```bash
# Make monster #0 in MONA tougher
u3edit bestiary edit MONA#069900 --monster 0 --hp 200 --attack 80
```

## Editing Maps

```bash
# Set a single tile
u3edit map set MAPA#061000 --x 10 --y 20 --tile 0x04

# Fill a rectangular region with grass
u3edit map fill MAPA#061000 --x1 0 --y1 0 --x2 5 --y2 5 --tile 0x04

# Replace all water tiles with grass
u3edit map replace MAPA#061000 --from 0x00 --to 0x04

# Find all town tiles
u3edit map find MAPA#061000 --tile 0x18

# Dungeon editing (specify level 0-7)
u3edit map set MAPM#061000 --x 5 --y 5 --tile 0x02 --level 3
```

## Editing Combat Battlefields

```bash
# Set a tile in a combat map
u3edit combat edit CONA#069900 --tile 5 5 0x04

# Move monster 0 start position
u3edit combat edit CONA#069900 --monster-pos 0 7 3

# Move PC 0 start position
u3edit combat edit CONA#069900 --pc-pos 0 2 8

# Validate combat map for issues
u3edit combat view CONA#069900 --validate
```

## Editing Special Locations

```bash
# Set a tile in a special location (shrine, fountain, etc.)
u3edit special edit SHRN#069900 --tile 5 5 0x8C
```

## Searching Dialog

```bash
# Search all TLK files for a keyword
u3edit tlk search path/to/GAME/ "exodus"

# Regex search
u3edit tlk search path/to/GAME/ "exo.*us" --regex

# Export search results as JSON
u3edit tlk search path/to/GAME/ "mark" --json -o results.json
```

## Find and Replace in Dialog

```bash
# Replace text across all records in a TLK file
u3edit tlk edit TLKA#060000 --find "EXODUS" --replace "DARKNESS"

# Case-insensitive find and replace
u3edit tlk edit TLKA#060000 --find "exodus" --replace "DARKNESS" --ignore-case

# Preview replacements without writing
u3edit tlk edit TLKA#060000 --find "EXODUS" --replace "DARKNESS" --dry-run
```

## Editing Game Text

```bash
# Edit a text record by index
u3edit text edit TEXT#061000 --record 0 --text "NEW TITLE"

# Preview without writing
u3edit text edit TEXT#061000 --record 0 --text "NEW TITLE" --dry-run
```

## Editing Save State

```bash
# Teleport the party
u3edit save edit path/to/GAME/ --x 32 --y 32 --transport horse

# Edit active party characters
u3edit save edit path/to/GAME/ --plrs-slot 0 --hp 9999 --gold 9999
```

## JSON Import/Export

All editable data types support round-trip JSON:

```bash
# Export to JSON
u3edit roster view ROST#069500 --json -o roster.json

# Edit the JSON externally, then import back
u3edit roster import ROST#069500 roster.json --backup

# Same pattern for all modules
u3edit bestiary view MONA#069900 --json -o monsters.json
u3edit bestiary import MONA#069900 monsters.json --backup
```

## Safety Features

```bash
# Preview changes without writing (dry run)
u3edit roster edit ROST#069500 --slot 0 --hp 9999 --dry-run

# Create a .bak backup before overwriting
u3edit roster edit ROST#069500 --slot 0 --hp 9999 --backup

# Validate data integrity (roster, bestiary, save, combat)
u3edit roster view ROST#069500 --validate
u3edit bestiary view MONA#069900 --validate
u3edit save view path/to/GAME/ --validate
u3edit combat view CONA#069900 --validate
```

`--backup` and `--dry-run` are available on all edit and import commands.

## Editing Tile Graphics

```bash
# View all tile glyphs in SHPS character set
u3edit shapes view path/to/GAME/

# View a specific tile (by tile ID)
u3edit shapes view SHPS#060800 --tile 0

# Export all glyphs as PNG files (scaled 4x)
u3edit shapes export SHPS#060800 --output-dir tiles/ --scale 4 --sheet

# Edit a glyph's raw bytes
u3edit shapes edit SHPS#060800 --glyph 0 --data "55 2A 55 2A 55 2A 55 2A"

# Show file format info
u3edit shapes info SHPS#060800
```

SHPS is a 2048-byte character set (256 glyphs x 8 bytes). Tile IDs use multiples of 4 — the low 2 bits select animation frame, so each tile is 4 consecutive glyphs.

## Editing Sound Data

```bash
# View all sound files in a directory
u3edit sound view path/to/GAME/

# View a specific sound file with hex dump
u3edit sound view SOSA#061000

# Patch bytes in a sound file
u3edit sound edit MBS#069a00 --offset 0x10 --data "00 42 08 0F" --backup

# Export/import via JSON
u3edit sound view SOSA#061000 --json -o sosa.json
u3edit sound import SOSA#061000 sosa.json --backup
```

Sound files: SOSA (4096 bytes, speaker patterns), SOSM (256 bytes, sound map), MBS (5456 bytes, Mockingboard AY-3-8910 sequences). All are external BLOAD data files.

## Engine Binary Patching

```bash
# View patchable regions in ULT3 engine binary
u3edit patch view ULT3#065000

# View a specific region (e.g., tile name strings)
u3edit patch view ULT3#065000 --region look-text

# Patch a data region
u3edit patch edit ULT3#065000 --region look-text --data "D7C1D4C5D200" --backup

# Raw hex dump of any offset
u3edit patch dump ULT3#065000 --offset 0x1566 --length 128
```

Targeted binary patches at CIDAR-identified offsets in ULT3/EXOD engine binaries.

ULT3 regions: `name-table` (921 bytes — terrain, monster, weapon, armor, spell names), `moongate-x`/`moongate-y` (8 bytes each — coordinates per phase), `food-rate` (1 byte — depletion counter, default $04).

EXOD regions: `town-coords`, `dungeon-coords` (entrance XY pairs), `moongate-coords` (phase positions).

## Comparing Game Data

```bash
# Compare two roster files
u3edit diff ROST_original#069500 ROST_modified#069500

# Compare two game directories
u3edit diff path/to/GAME1/ path/to/GAME2/

# Summary counts only
u3edit diff ROST1 ROST2 --summary

# JSON output
u3edit diff ROST1 ROST2 --json -o diff.json
```

Auto-detects file types and compares across all data formats (roster, bestiary, combat, save, maps, special, TLK).

## Disk Image Operations

```bash
# Show disk image info
u3edit disk info game.po

# List files on disk image
u3edit disk list game.po

# Extract all files
u3edit disk extract game.po -o output_dir/

# Audit disk space usage
u3edit disk audit game.po

# Detailed per-file allocation
u3edit disk audit game.po --detail

# JSON output for scripting
u3edit disk audit game.po --json -o audit.json
```

Requires [diskiigs](https://github.com/BradHawthorne/rosetta) on your PATH (or set `DISKIIGS_PATH`).

## File Formats

### Character Record (ROST, 64 bytes per slot, 20 slots)

| Offset | Size | Field | Encoding |
|--------|------|-------|----------|
| 0x00-0x0D | 14 | Name | High-bit ASCII, null-terminated (max 13 chars + null at 0x0D) |
| 0x0E | 1 | Marks/Cards | Bitmask (hi nibble=marks, lo nibble=cards) |
| 0x0F | 1 | Torches | Count |
| 0x10 | 1 | In-Party | $FF=active, $00=not |
| 0x11 | 1 | Status | ASCII: G/P/D/A |
| 0x12-0x15 | 4 | STR/DEX/INT/WIS | BCD (0-99 each) |
| 0x16-0x18 | 3 | Race/Class/Gender | ASCII codes |
| 0x19 | 1 | MP | BCD (0-99) |
| 0x1A-0x1B | 2 | HP | BCD16 (0-9999) |
| 0x1C-0x1D | 2 | Max HP | BCD16 (0-9999) |
| 0x1E-0x1F | 2 | EXP | BCD16 (0-9999) |
| 0x20 | 1 | Sub-morsels | Food fraction |
| 0x21-0x22 | 2 | Food | BCD16 (0-9999) |
| 0x23-0x24 | 2 | Gold | BCD16 (0-9999) |
| 0x25-0x27 | 3 | Gems/Keys/Powders | BCD (0-99 each) |
| 0x28 | 1 | Worn armor | Index (0-7) |
| 0x29-0x2F | 7 | Armor inventory | Count of each type (Cloth..Exotic) |
| 0x30 | 1 | Readied weapon | Index (0-15) |
| 0x31-0x3F | 15 | Weapon inventory | Count of each type (Dagger..Exotic) |

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

595 tests covering all modules with synthesized game data (no real game files needed).

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
| S-1 | save | Fixed PRTY field mapping — party_size/location_type/x/y were at wrong byte offsets |

## License

MIT
