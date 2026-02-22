# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

u3edit is a data toolkit for Ultima III: Exodus (Apple II, 1983). It provides CLI viewers, editors, and a unified TUI for all game data formats. Python 3.10+, no runtime dependencies. MIT license.

## Commands

```bash
pip install -e ".[dev]"              # Install with pytest
pip install -e ".[tui]"              # Install with prompt_toolkit for TUI editors
pytest -v                            # Run all 1374 tests
pytest tests/test_roster.py          # Run one test module
pytest -v tests/test_bcd.py::TestBcdToInt::test_zero  # Run single test
u3edit roster view path/to/ROST      # CLI usage pattern
u3edit edit game.po                  # Unified TUI editor (requires prompt_toolkit)
```

## Architecture

### Module-per-data-type pattern

Each game data type lives in `src/u3edit/{module}.py` (roster, bestiary, map, tlk, combat, save, special, text, spell, equip, shapes, sound, patch, ddrw, diff, disk). Every module follows the same contract:

- **Data class** (e.g., `Character`, `Monster`): wraps `bytearray` with `@property` accessors
- **`load_*(path)` / `save_*(path, obj)`**: File I/O
- **`cmd_view(args)`**: Text or `--json --output` rendering
- **`cmd_edit(args)`**: CLI editing with `--backup`, `--dry-run` flags
- **`cmd_import(args)`**: Import from JSON (`u3edit <module> import <binary> <json>`)
- **`register_parser(subparsers)`**: Adds CLI subcommands
- **`dispatch(args)`**: Routes to command handlers
- **`main()`**: Standalone entry point (also registered as `u3-{module}` console script). Must have full parity with `register_parser()` — same subcommands, args, and help text.

### CLI dispatcher (`cli.py`)

`cli.py:main()` creates an argparse parser, calls each module's `register_parser()`, then dispatches to the matching module's `dispatch()`. The `edit` subcommand launches the unified TUI via `GameSession` + `UnifiedApp`.

### Binary encoding conventions

- **BCD (Binary Coded Decimal)**: Most numeric fields. See `bcd.py` for `bcd_to_int()`, `int_to_bcd()`, `int_to_bcd16()`.
- **High-bit ASCII**: Text has bit 7 set (0x80–0xFE). See `fileutil.py` for `decode_high_ascii()` / `encode_high_ascii()`. Padding char is 0xA0 (high-ASCII space).
- **Columnar layout**: MON files store 16 monsters × 10 attributes column-major: `file[attr * 16 + monster_index]`.
- **Bitmask fields**: Marks/cards packed in nibbles, monster flags as bitwise combinations.

### Constants as single source of truth

`constants.py` holds all tile tables, character attributes, weapon/armor stats, spell lists, file format layouts, and map names. All modules import from here.

### Disk image integration (`disk.py`)

`DiskContext` is a context manager that extracts ProDOS disk image files to a temp directory (via external `diskiigs` tool), caches reads, stages writes, and writes back on exit. Preserves ProDOS type/aux suffixes (`ROST#069500`). Writes even if an exception occurred (prevents data loss).

### TUI architecture (`tui/`)

- **`GameSession`** wraps `DiskContext`, catalogs available files by category, provides factory methods for editors
- **`UnifiedApp`** (`app.py`): Master tabbed editor using prompt_toolkit
- **`EditorState`** (`base.py`): Pure dataclass with zero I/O — all editor logic (cursor, viewport, painting) is testable without prompt_toolkit
- **`BaseTileEditor`**: UI layer that wraps `EditorState` for rendering and key handling

### File resolution (`fileutil.py`)

`resolve_game_file()` handles ProDOS type/aux suffixes and plain filenames with fallback glob. `find_game_files()` resolves multiple files by prefix pattern.

## Testing conventions

- Tests use **synthesized binary data** — no real game files needed
- Fixtures in `tests/conftest.py` build exact binary blobs matching Ultima III formats
- Each fixture produces known values so tests can assert decoded fields directly
- Setter tests verify validation (clamping, length limits, BCD encoding)

## CLI features across modules

- **`--backup`**: Creates `.bak` copy before overwriting (edit/import commands). Uses `fileutil.backup_file()`.
- **`--dry-run`**: Shows changes without writing. Available on all `edit` and `import` commands across all modules.
- **`--validate`**: Data validation — checks for out-of-range values, invalid codes, rule violations. Available on `view` and `edit` for roster (BCD integrity, race stat caps, class equipment limits, HP > max HP), bestiary (tile validity, flag bits), save (transport, party size, coordinates, sentinel), and combat (tile alignment, position bounds, overlapping starts).
- **`--all`**: Bulk editing — applies edits to all non-empty slots/monsters (roster: `--slot`/`--all`, bestiary: `--monster`/`--all`).
- **`import`**: Every editable module supports `import <binary_file> <json_file>` to apply JSON data. Roster import handles equipment (weapon/armor names) and inventory counts. Save import handles both PRTY party state and PLRS active characters. Bestiary import accepts dict-of-dicts JSON (`{"monsters": {"0": {...}}}`) with flag shortcuts (`boss`, `poison`, `sleep`, etc.) and warns when values are clamped to byte range (0-255).
- **`map set/fill/replace/find/compile/decompile`**: Map CLI editing — set tiles, fill regions, replace tile types, search. `compile` reads `.map` text-art → binary MAP. `decompile` reads binary MAP → `.map` text-art. Supports overworld (64x64) and dungeon (--dungeon, 8x 16x16).
- **`combat edit`**: CLI editing — `--tile X Y VALUE`, `--monster-pos INDEX X Y`, `--pc-pos INDEX X Y`. Falls through to TUI when no CLI args provided.
- **`special edit`**: CLI editing — `--tile X Y VALUE`. Falls through to TUI when no CLI args provided.
- **`tlk search`**: Text search across TLK dialog files. Case-insensitive by default, `--regex` for regex patterns.
- **`tlk edit --find/--replace`**: Search-and-replace across all text records in a TLK file. `--ignore-case` for case-insensitive matching. Supports `--dry-run`.
- **`roster check-progress`**: Endgame readiness checker — marks, cards, exotic gear, party status.
- **`diff`**: Compare two game files or directories — text/JSON/summary output, auto-detects file types, supports all data formats (roster, bestiary, combat, save, maps, special, TLK, sound, shapes, DDRW, TEXT).
- **`bestiary edit`**: Named flag toggles (`--undead`, `--ranged`, `--magic-user`, `--boss`, `--poison`, `--sleep`, `--negate`, `--teleport`, `--divide`, `--resistant` + `--no-*` counterparts), `--type Name` for monster type by name, `--all` for bulk editing.
- **`save edit --plrs-slot`**: Edit active characters in PLRS file via save subcommand — supports all Character fields (stats, equipment, status, race, class, gender, marks, cards, sub-morsels). `--sentinel` sets the party sentinel byte (0xFF=active). `--location` sets location type (sosaria/dungeon/town/castle or raw hex). `--transport` accepts named values or raw int/hex for total conversions. Note: `--output` is rejected when editing both PRTY and PLRS simultaneously (they are separate files).
- **`roster edit --in-party/--not-in-party`**: Toggle character's in-party status. `--sub-morsels` sets food fraction (0-99).
- **`text edit --record/--text`**: Per-record CLI editing for TEXT game strings (uppercased to match engine). Falls through to TUI when no CLI args provided.
- **`shapes view/export/edit/edit-string/import/compile/decompile`**: SHPS character set tile graphics — glyph rendering, PNG export (stdlib, no Pillow), HGR color logic, SHP overlay inline string extraction and replacement (`edit-string --offset --text`), SHPS embedded code guard at $9F9, TEXT detection as HGR bitmap. `compile` reads `.tiles` text-art → SHPS binary or JSON. `decompile` reads SHPS binary → `.tiles` text-art.
- **`sound view/edit/import`**: SOSA/SOSM/MBS sound data files — hex dump, AY-3-8910 register parsing and music stream decoding (notes, tempo, loops) for MBS.
- **`patch view/edit/dump/import/strings/strings-edit/strings-import/compile-names/decompile-names/validate-names`**: Engine binary patcher for CIDAR-identified offsets in ULT3/EXOD — name table (921 bytes, terrain/monster/weapon/armor/spell names), moongate coordinates, food depletion rate, town/dungeon coords. `view --json` → `import` round-trips all region types (text, bytes, coords). `strings` subcommand catalogs all 245 JSR $46BA inline strings with `--search` filter and `--json` export. `strings-edit` / `strings-import` for in-place inline string editing by index/vanilla/address. `compile-names` / `decompile-names` / `validate-names` for text-first `.names` file workflow.
- **`ddrw view/edit/import`**: Dungeon drawing data (1792 bytes) with structured perspective vector and tile record parsing.
- **`disk info/list/extract/audit`**: ProDOS disk image operations — show volume info, list files, extract all files, audit disk space (free blocks, alignment waste, capacity estimates). Requires external `diskiigs` tool.
- **`TILE_CHARS_REVERSE` / `DUNGEON_TILE_CHARS_REVERSE`**: Reverse lookups in `constants.py` for char→tile-byte conversion (used by import commands). **`TILE_NAMES_REVERSE` / `DUNGEON_TILE_NAMES_REVERSE`**: Full name→tile-byte reverse lookups for JSON round-trip (e.g., "Grass"→0x04).
- **CON file layout** (fully resolved via engine code tracing): 0x79-0x7F = unused padding, 0x90-0x9F = runtime monster arrays (saved-tile + status, overwritten at init), 0xA8-0xAF = runtime PC arrays (saved-tile + appearance, overwritten at init), 0xB0-0xBF = unused tail padding. Preserved for round-trip fidelity.
- **PRTY file layout** (verified against zero-page $E0-$EF): $E0=transport, $E1=party_size, $E2=location_type, $E3=saved_x, $E4=saved_y, $E5=sentinel, $E6-$E9=slot_ids. Constants in `PRTY_OFF_*`.
- **Special location trailing bytes**: BRND/SHRN/FNTN/TIME files' last 7 bytes are unused disk residue (text fragments), not game data. Preserved for round-trip fidelity.

## Total conversion support

Setters follow a **named-first, raw-fallback** pattern for total conversion scenarios:
- Named lookups first (e.g., `status='G'`, `transport='horse'`) — friendly for standard play
- Raw int/hex fallback (e.g., `status=0x47`, `transport=10`) — flexible for mods with custom values
- Equipment setters accept full byte range (0-255), not just vanilla game indices
- Validation is advisory (warnings via `--validate`) not enforced (no setter errors on valid bytes)

### Total conversion pipeline (`conversions/`)

Reusable framework for building full game replacements:

- **`conversions/TEMPLATE/`**: Starter templates — `CHECKLIST.md` (every replaceable asset with u3edit command), `STORY_TEMPLATE.md` (narrative structure), `apply_template.sh` (11-phase skeleton script)
- **`conversions/tools/tile_compiler.py`**: Standalone tile compiler (also available as `u3edit shapes compile/decompile`).
- **`conversions/tools/map_compiler.py`**: Standalone map compiler (also available as `u3edit map compile/decompile`).
- **`conversions/tools/name_compiler.py`**: Standalone name table compiler (also available as `u3edit patch compile-names/decompile-names/validate-names`).
- **`conversions/tools/gen_maps.py`**: Programmatic map generator for guaranteed-dimension surface (64×64) and dungeon (8×16×16) maps.
- **`conversions/tools/shop_apply.py`**: Text-matching shop overlay string replacer. Discovers inline strings via `extract_overlay_strings()` at runtime, matches by vanilla text, replaces with new text. No hardcoded offsets needed.
- **`conversions/tools/verify.py`**: Post-conversion verification — checks file presence, sizes, and optionally compares hashes against vanilla to confirm all assets were replaced.
- **`conversions/tools/MUSIC_FORMAT.md`**: MBS (AY-3-8910) byte format reference for sound editing.
- **`conversions/voidborn/`**: Complete reference total conversion ("Voidborn") with full narrative (`VOIDBORN.md`), `apply.sh` (full pipeline), and text-first source files in `sources/`: 13 bestiary JSON, 9 combat JSON, 4 special JSON, 19 dialog TXT, 20 map text-art (13 surface + 7 dungeon), 256-tile pixel art, name table `.names`, title text JSON, shop overlay strings JSON, 3 sound JSONs (SOSA/SOSM/MBS), DDRW JSON.

## Engine SDK (`engine/`)

Buildable engine source tree using the Rosetta toolchain (asmiigs/deasmiigs). All three engine binaries reassemble byte-identical from CIDAR disassembly:

- **`engine/subs/subs.s`**: SUBS shared library (3,584 bytes at $4100) — string printer, math, display
- **`engine/ult3/ult3.s`**: Main engine (17,408 bytes at $5000) — game logic, combat, file I/O
- **`engine/exod/exod.s`**: Boot loader (26,208 bytes at $2000) — world map, location entrances
- **`engine/originals/`**: Original binaries for byte-identical verification
- **`engine/build.sh`**: Build script — assembles all 3 binaries, verifies byte-identical output
- **`engine/verify.py`**: Python verification script for CI/programmatic use

Build pipeline: `asmiigs --cpu 6502 source.s -o output.omf` → OMF has 60-byte header + code + 1-byte trailer. Code at offset 60 matches original binary exactly.

### Inline string tools (`engine/tools/`)

- **`string_catalog.py`**: Extracts all JSR $46BA inline strings from engine binaries. Auto-detects origin address from filename. Outputs text or JSON catalog with categories.
- **`ult3_strings.json`**: Pre-built catalog of 245 inline strings in ULT3 (3,714 bytes total). Categories: quest-item, combat, movement, magic, equipment, location, trap, fountain, shop, status, story, ui-prompt, death, other.
- **`string_patcher.py`**: Binary-level in-place string patcher. Matches by index, vanilla text, or address. Constraint: replacement must fit in original byte allocation.
- **`source_patcher.py`**: Source-level ASC directive patcher. Modifies `.s` assembly files — **no length constraints**. Requires asmiigs reassembly after patching.

### Scenario build pipeline (`engine/scenario_build.sh`)

Two-tier build system for scenario/conversion authors:
1. **Source-level** (preferred): `source_patcher.py` modifies `.s` files → `asmiigs` reassembles → no string length limits
2. **Binary-level** (fallback): `string_patcher.py` patches binary in-place → no assembler needed, but strings must fit original space

Scenario patch files:
- `engine_strings_full.json`: Source-level patches (used when asmiigs is available)
- `engine_strings.json`: Binary-level patches (fallback, length-constrained)

## Data integrity rules

- Setter properties validate and clamp to valid ranges (e.g., coordinates 0–63, BCD max 99/9999)
- Map JSON round-trip uses `TILE_NAMES_REVERSE` / `DUNGEON_TILE_NAMES_REVERSE` for full name→tile_id resolution
- TLK records use `is_text_record()` to filter binary data from dialog
- `DiskContext` preserves ProDOS file type/aux info through read-modify-write cycles
