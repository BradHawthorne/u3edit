# ult3edit

[![Tests](https://github.com/BradHawthorne/ult3edit/actions/workflows/tests.yml/badge.svg)](https://github.com/BradHawthorne/ult3edit/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/ult3edit)](https://pypi.org/project/ult3edit/)

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
ult3edit edit game.po

# View characters
ult3edit roster view path/to/GAME/ROST#069500

# View all monsters
ult3edit bestiary view path/to/GAME/

# View the overworld map
ult3edit map view path/to/GAME/MAPA#061000

# Overview of all maps with preview
ult3edit map overview path/to/GAME/ --preview

# View NPC dialog
ult3edit tlk view path/to/GAME/

# View combat battlefields
ult3edit combat view path/to/GAME/

# View save state
ult3edit save view path/to/GAME/

# Spell reference
ult3edit spell view

# Equipment stats and class restrictions
ult3edit equip view

# Export anything to JSON
ult3edit roster view path/to/ROST#069500 --json -o roster.json
```

## Unified TUI Editor

The interactive text-based editor provides a tabbed interface for editing all game data in one session. Requires `prompt_toolkit`:

```bash
pip install -e ".[tui]"

# Edit a ProDOS disk image directly
ult3edit edit game.po

# Edit extracted files in a directory
ult3edit edit path/to/GAME/
```

The TUI supports tile painting for maps, form editing for character stats (including sub-morsels, in-party, marks, and cards) and monster attributes, party state (including location type and sentinel), and in-place dialog editing. Changes are written back to the disk image or directory on save.

**Keybindings:**

| Key | Action |
|-----|--------|
| F5 / Ctrl+Left | Previous tab |
| F6 / Ctrl+Right | Next tab |
| Arrow keys | Navigate / move cursor |
| Space | Paint tile (map/combat/special editors) |
| `[` / `]` | Previous / next tile in palette |
| Ctrl+S | Save changes |
| Ctrl+Q | Quit |
| Escape | Close current editor / cancel |

## Disk Image Support

ult3edit includes a native ProDOS disk image builder and can work directly with `.po` disk images:

```bash
ult3edit disk info game.po
ult3edit disk list game.po
```

## Tools

| Tool | Description | Commands |
|------|-------------|----------|
| `roster` | Character roster viewer/editor | `view`, `edit`, `create`, `import`, `check-progress` |
| `bestiary` | Monster bestiary viewer/editor | `view`, `dump`, `edit`, `import` |
| `map` | Overworld, town, and dungeon map viewer/editor | `view`, `overview`, `legend`, `edit`, `set`, `fill`, `replace`, `find`, `import`, `compile`, `decompile` |
| `tlk` | NPC dialog viewer/editor | `view`, `extract`, `build`, `edit`, `search`, `import` |
| `combat` | Combat battlefield viewer/editor | `view`, `edit`, `import` |
| `save` | Save state viewer/editor | `view`, `edit`, `import` |
| `special` | Special location viewer/editor (shrines, fountains) | `view`, `edit`, `import` |
| `text` | Game text string viewer/editor | `view`, `edit`, `import` |
| `spell` | Spell reference (wizard + cleric) | `view` |
| `equip` | Equipment stats and class restrictions | `view` |
| `shapes` | Tile graphics / character set editor | `view`, `export`, `edit`, `edit-string`, `import`, `info`, `compile`, `decompile` |
| `sound` | Sound data editor (SOSA, SOSM, MBS) | `view`, `edit`, `import` |
| `patch` | Engine binary patcher (CIDAR offsets) | `view`, `edit`, `dump`, `import`, `strings`, `strings-edit`, `strings-import`, `compile-names`, `decompile-names`, `validate-names` |
| `ddrw` | Dungeon drawing data editor | `view`, `edit`, `import` |
| `exod` | Intro/title screen graphics editor | `view`, `export`, `import`, `crawl {view,export,import,render,compose}`, `glyph {view,export}` |
| `diff` | Game data comparison tool | (compares two files or directories) |
| `disk` | ProDOS disk image operations | `info`, `list`, `extract`, `audit` |

Each tool is also available standalone: `ult3-roster`, `ult3-bestiary`, `ult3-map`, etc.

## Editing Characters

```bash
# Edit a character's stats
ult3edit roster edit ROST#069500 --slot 0 --str 99 --hp 9999 --gold 9999

# Give all marks and cards
ult3edit roster edit ROST#069500 --slot 0 --marks "Kings,Snake,Fire,Force" --cards "Death,Sol,Love,Moons"

# Bulk edit all characters at once
ult3edit roster edit ROST#069500 --all --gold 9999 --food 9999

# Create a new character
ult3edit roster create ROST#069500 --slot 5 --name "WIZARD" --race E --class W --gender F

# Validate roster for game-rule violations
ult3edit roster view ROST#069500 --validate

# Check endgame readiness
ult3edit roster check-progress ROST#069500

# Toggle party membership
ult3edit roster edit ROST#069500 --slot 0 --in-party
ult3edit roster edit ROST#069500 --slot 0 --not-in-party

# Set sub-morsels (food fraction)
ult3edit roster edit ROST#069500 --slot 0 --sub-morsels 50
```

## Editing Monsters

```bash
# Make monster #0 in MONA tougher
ult3edit bestiary edit MONA#069900 --monster 0 --hp 200 --attack 80
```

## Editing Maps

```bash
# Set a single tile
ult3edit map set MAPA#061000 --x 10 --y 20 --tile 0x04

# Fill a rectangular region with grass
ult3edit map fill MAPA#061000 --x1 0 --y1 0 --x2 5 --y2 5 --tile 0x04

# Replace all water tiles with grass
ult3edit map replace MAPA#061000 --from 0x00 --to 0x04

# Find all town tiles
ult3edit map find MAPA#061000 --tile 0x18

# Dungeon editing (specify level 0-7)
ult3edit map set MAPM#061000 --x 5 --y 5 --tile 0x02 --level 3
```

## Editing Combat Battlefields

```bash
# Set a tile in a combat map
ult3edit combat edit CONA#069900 --tile 5 5 0x04

# Move monster 0 start position
ult3edit combat edit CONA#069900 --monster-pos 0 7 3

# Move PC 0 start position
ult3edit combat edit CONA#069900 --pc-pos 0 2 8

# Validate combat map for issues
ult3edit combat view CONA#069900 --validate
```

## Editing Special Locations

```bash
# Set a tile in a special location (shrine, fountain, etc.)
ult3edit special edit SHRN#069900 --tile 5 5 0x8C
```

## Searching Dialog

```bash
# Search all TLK files for a keyword
ult3edit tlk search path/to/GAME/ "exodus"

# Regex search
ult3edit tlk search path/to/GAME/ "exo.*us" --regex

# Export search results as JSON
ult3edit tlk search path/to/GAME/ "mark" --json -o results.json
```

## Find and Replace in Dialog

```bash
# Replace text across all records in a TLK file
ult3edit tlk edit TLKA#060000 --find "EXODUS" --replace "DARKNESS"

# Case-insensitive find and replace
ult3edit tlk edit TLKA#060000 --find "exodus" --replace "DARKNESS" --ignore-case

# Preview replacements without writing
ult3edit tlk edit TLKA#060000 --find "EXODUS" --replace "DARKNESS" --dry-run
```

## Editing Game Text

```bash
# Edit a text record by index
ult3edit text edit TEXT#061000 --record 0 --text "NEW TITLE"

# Preview without writing
ult3edit text edit TEXT#061000 --record 0 --text "NEW TITLE" --dry-run
```

## Editing Save State

```bash
# Teleport the party
ult3edit save edit path/to/GAME/ --x 32 --y 32 --transport horse

# Set location type
ult3edit save edit path/to/GAME/ --location dungeon

# Edit active party characters (all character fields supported)
ult3edit save edit path/to/GAME/ --plrs-slot 0 --hp 9999 --gold 9999
ult3edit save edit path/to/GAME/ --plrs-slot 0 --str 99 --status G --race E --class W
ult3edit save edit path/to/GAME/ --plrs-slot 0 --gems 50 --keys 25 --weapon 5 --armor 3

# Set party sentinel (0xFF=active, 0x00=inactive)
ult3edit save edit path/to/GAME/ --sentinel 255

# Transport and location accept names or raw hex (for total conversions)
ult3edit save edit path/to/GAME/ --transport 0x0A
ult3edit save edit path/to/GAME/ --location 0x80
```

## JSON Import/Export

All editable data types support round-trip JSON:

```bash
# Export to JSON
ult3edit roster view ROST#069500 --json -o roster.json

# Edit the JSON externally, then import back
ult3edit roster import ROST#069500 roster.json --backup

# Same pattern for all modules
ult3edit bestiary view MONA#069900 --json -o monsters.json
ult3edit bestiary import MONA#069900 monsters.json --backup

# Maps use full tile names for round-trip fidelity
ult3edit map view MAPA#061000 --json -o map.json
ult3edit map import MAPA#061000 map.json --backup
```

All JSON exports use human-readable tile names (e.g., "Grass", "Water", "Town") that round-trip correctly on import.

## Safety Features

```bash
# Preview changes without writing (dry run)
ult3edit roster edit ROST#069500 --slot 0 --hp 9999 --dry-run

# Create a .bak backup before overwriting
ult3edit roster edit ROST#069500 --slot 0 --hp 9999 --backup

# Validate data integrity (roster, bestiary, save, combat)
ult3edit roster view ROST#069500 --validate
ult3edit bestiary view MONA#069900 --validate
ult3edit save view path/to/GAME/ --validate
ult3edit combat view CONA#069900 --validate

# Validate after editing (bestiary, combat)
ult3edit bestiary edit MONA#069900 --monster 0 --hp 200 --validate
ult3edit combat edit CONA#069900 --tile 5 5 0x04 --validate
```

`--backup` and `--dry-run` are available on all edit and import commands.

## Total Conversion Support

Enum-like setters (status, race, class, gender, transport, location, equipment) follow a **named-first, raw-fallback** pattern:

```bash
# Named values (friendly)
ult3edit roster edit ROST --slot 0 --status G --race H --class F

# Raw int/hex values (for mods with custom values beyond vanilla)
ult3edit roster edit ROST --slot 0 --status 0x47 --race 0x58
ult3edit save edit path/to/GAME/ --transport 0x0A --location 0x80
```

Equipment indices accept the full byte range (0-255), not just vanilla game limits. Validation via `--validate` is advisory (warnings, not errors).

## Editing Tile Graphics

```bash
# View all tile glyphs in SHPS character set
ult3edit shapes view path/to/GAME/

# View a specific tile (by tile ID)
ult3edit shapes view SHPS#060800 --tile 0

# Export all glyphs as PNG files (scaled 4x)
ult3edit shapes export SHPS#060800 --output-dir tiles/ --scale 4 --sheet

# Edit a glyph's raw bytes
ult3edit shapes edit SHPS#060800 --glyph 0 --data "55 2A 55 2A 55 2A 55 2A"

# Edit an inline string in SHP overlay files
ult3edit shapes edit-string SHP#060800 --offset 0x100 --text "NEW TEXT"

# Show file format info
ult3edit shapes info SHPS#060800
```

SHPS is a 2048-byte character set (256 glyphs x 8 bytes). Tile IDs use multiples of 4 — the low 2 bits select animation frame, so each tile is 4 consecutive glyphs.

## Editing Sound Data

```bash
# View all sound files in a directory
ult3edit sound view path/to/GAME/

# View a specific sound file with hex dump
ult3edit sound view SOSA#061000

# Patch bytes in a sound file
ult3edit sound edit MBS#069a00 --offset 0x10 --data "00 42 08 0F" --backup

# Export/import via JSON
ult3edit sound view SOSA#061000 --json -o sosa.json
ult3edit sound import SOSA#061000 sosa.json --backup
```

Sound-related files: SOSA (4096 bytes, overworld map state — dynamic copy of MAPA), SOSM (256 bytes, overworld monster positions), MBS (5456 bytes, Mockingboard AY-3-8910 music sequences). Note: SOSA and SOSM are save-state files despite being managed by the `sound` subcommand.

## Engine Binary Patching

```bash
# View patchable regions in ULT3 engine binary
ult3edit patch view ULT3#065000

# View a specific region (e.g., name table strings)
ult3edit patch view ULT3#065000 --region name-table

# Patch a data region
ult3edit patch edit ULT3#065000 --region name-table --data "D7C1D4C5D200" --backup

# Raw hex dump of any offset
ult3edit patch dump ULT3#065000 --offset 0x1566 --length 128

# Export regions as JSON, edit, import back (round-trip)
ult3edit patch view ULT3#065000 --json -o regions.json
ult3edit patch import ULT3#065000 regions.json --backup
```

Targeted binary patches at CIDAR-identified offsets in the ULT3 engine binary.

ULT3 regions: `name-table` (921 bytes — terrain, monster, weapon, armor, spell names), `moongate-x`/`moongate-y` (8 bytes each — coordinates per phase), `food-rate` (1 byte — depletion counter, default $04).

### Inline String Editing (245 strings in ULT3)

```bash
# List all inline JSR $46BA strings
ult3edit patch strings ULT3#065000

# Search for specific strings
ult3edit patch strings ULT3#065000 --search "CARD"

# Export full catalog as JSON
ult3edit patch strings ULT3#065000 --json -o catalog.json

# Edit a single string (by vanilla text match)
ult3edit patch strings-edit ULT3#065000 --vanilla "CARD OF DEATH" --text "SHARD OF VOID" --backup

# Edit by index (from strings catalog)
ult3edit patch strings-edit ULT3#065000 --index 142 --text "SHARD OF VOID"

# Edit by engine address
ult3edit patch strings-edit ULT3#065000 --address 0x6C48 --text "SHARD OF VOID"

# Bulk import from JSON patch file
ult3edit patch strings-import ULT3#065000 patches.json --backup
```

The ULT3 engine binary contains 245 inline text strings displayed via `JSR $46BA`. These cover quest items, combat messages, movement prompts, magic, equipment, shops, and UI text. In-place binary patching replaces strings within their original byte allocation.

For replacements that exceed the original length, use the source-level pipeline (see Engine SDK below).

## Engine SDK

The engine SDK provides byte-identical reassembly of all three engine binaries from CIDAR disassembly source, enabling source-level modifications with no length constraints. All 864 labels are fully symbolicated with semantic names, and every code function has academic-level annotations documenting algorithms, Apple II hardware techniques (HGR double-buffering, speaker synthesis, BCD arithmetic), self-modifying code patterns, and historical context — making this the most thoroughly documented Ultima III engine source available.

```bash
# Verify byte-identical round-trip assembly
bash engine/build.sh

# Build a scenario with custom strings (source-level, no length limits)
bash engine/scenario_build.sh conversions/voidborn/

# Apply scenario to game directory
bash engine/scenario_build.sh conversions/voidborn/ --apply-to /path/to/GAME/
```

### Two-Tier String Patching

| Approach | Tool | Constraints | Requires |
|----------|------|-------------|----------|
| Binary (in-place) | `ult3edit patch strings-edit` | Must fit original space | Python only |
| Source (reassembly) | `source_patcher.py` + `asmiigs` | No length limits | asmiigs assembler |

The `scenario_build.sh` script automatically selects source-level patching when `asmiigs` is available, falling back to binary patching otherwise.

### Engine Binaries

| Binary | Size | Origin | Labels | Content |
|--------|------|--------|--------|---------|
| ULT3 | 17,408 bytes | $5000 | 351 | Main engine — `game_main_loop`, `combat_*`, `magic_*`, `render_*` |
| EXOD | 26,208 bytes | $2000 | 372 | Boot/intro — `intro_*`, `anim_data_*` (87% animation data) |
| SUBS | 3,584 bytes | $4100 | 141 | Shared library — `print_inline_str`, `setup_char_ptr`, `play_sfx` |

### Scenario Template

See `engine/SCENARIO_TEMPLATE.md` for the engine-level scenario author guide (inline string patching, reassembly). For full total conversions (all game assets), see `conversions/TEMPLATE/` which provides `CHECKLIST.md`, `STORY_TEMPLATE.md`, and `apply_template.sh`.

## Comparing Game Data

```bash
# Compare two roster files
ult3edit diff ROST_original#069500 ROST_modified#069500

# Compare two game directories
ult3edit diff path/to/GAME1/ path/to/GAME2/

# Summary counts only
ult3edit diff ROST1 ROST2 --summary

# JSON output
ult3edit diff ROST1 ROST2 --json -o diff.json
```

Auto-detects file types and compares across all data formats (roster, bestiary, combat, save, maps, special, TLK, sound, shapes, DDRW, TEXT).

## Disk Image Operations

```bash
# Show disk image info
ult3edit disk info game.po

# List files on disk image
ult3edit disk list game.po

# Extract all files
ult3edit disk extract game.po -o output_dir/

# Audit disk space usage
ult3edit disk audit game.po

# Detailed per-file allocation
ult3edit disk audit game.po --detail

# JSON output for scripting
ult3edit disk audit game.po --json -o audit.json
```

Uses the native ProDOS disk image builder (no external tools required).

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

1696 tests covering all modules with synthesized game data (no real game files needed).

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
| S-2 | save | Fixed transport setter silent no-op on unknown values (now raises ValueError) |
| S-3 | save | Expanded PLRS import to handle all Character fields (was dropping ~15) |
| S-4 | save | Guard against --output when editing both PRTY and PLRS simultaneously |
| M-2 | map | Fixed JSON round-trip data destruction (import now handles full tile names) |
| C-1 | combat | Fixed to_dict() filtering out monsters at position (0,0) |
| R-5 | roster | Fixed gender setter crash on raw int input |
| R-6 | roster | Added HP > max_hp validation check |

## Total Conversion Pipeline

ult3edit includes a complete framework for building total game conversions — replacing every asset (graphics, maps, dialog, monsters, sound) with original content.

### Getting Started

```bash
# Copy the template to start a new conversion
cp -r conversions/TEMPLATE conversions/my-game

# Follow the checklist
cat conversions/TEMPLATE/CHECKLIST.md

# Write your story using the template
cat conversions/TEMPLATE/STORY_TEMPLATE.md
```

### Pipeline Tools

**Tile Compiler** — text-art tile definitions to SHPS binary:

```bash
# Decompile existing tiles to editable text-art
ult3edit shapes decompile SHPS --output tiles.tiles

# Edit tiles.tiles (7x8 pixel grids, '#'=on '.'=off)
# Compile back to binary
ult3edit shapes compile tiles.tiles --output SHPS
# Or compile to JSON for shapes import
ult3edit shapes compile tiles.tiles --format json --output tiles.json
```

**Map Compiler** — text-art maps to game binary:

```bash
# Decompile a map to editable text-art
ult3edit map decompile MAPA --output mapa.map

# Edit mapa.map (single-char tiles: ~=water .=grass ^=mountain etc.)
# Compile back to binary
ult3edit map compile mapa.map --output MAPA
# Dungeon maps: 8 levels x 16x16
ult3edit map compile mapm.map --dungeon --output MAPM
```

**Dialog** — round-trip text editing:

```bash
ult3edit tlk extract TLKA tlka.txt    # Decompile to plain text
# Edit tlka.txt with any editor
ult3edit tlk build tlka.txt TLKA      # Compile back to binary
```

**Name Compiler** — text-first name table editor:

```bash
# Decompile current names from engine binary
ult3edit patch decompile-names ULT3 --output names.names

# Edit names.names (one name per line, # comments for groups)
# Validate budget (891 usable bytes)
ult3edit patch validate-names names.names

# Compile to JSON and apply
ult3edit patch compile-names names.names --output names.json
ult3edit patch import ULT3 names.json
```

**Verification** — confirm all assets were replaced:

```bash
python conversions/tools/verify.py path/to/GAME/ --vanilla path/to/ORIGINAL/
```

### Applying a Conversion

Each conversion includes an `apply.sh` script that runs all phases:

```bash
bash conversions/voidborn/apply.sh path/to/game.po
```

### Voidborn Reference Implementation

`conversions/voidborn/` contains a complete total conversion ("Voidborn: Ashes of Sosaria") with text-first source files for every game asset:

- **13 bestiary** JSON files (monsters for all encounter zones)
- **9 combat** JSON files (themed 11x11 battlefields)
- **19 dialog** TXT files (town + dungeon NPC text)
- **20 map** files (13 surface 64x64 + 7 dungeon 8x16x16)
- **256 tile** pixel art definitions
- **Name table** with all custom terrain/monster/weapon/armor/spell names
- **4 special** location JSON files (shrines, fountains)
- **3 sound** JSON files (SOSA, SOSM, MBS)
- **Shop overlay** strings JSON (weapon/armor/item shop text)
- **DDRW** dungeon drawing data JSON
- **Title** screen text
- **Text crawl** coordinate data (composed via bitmap font)

## License

MIT
