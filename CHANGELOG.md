# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [1.20.0] - 2026-02-24

### Added
- 609 new tests (1903 → 2512) achieving 100% code coverage across all 40 source files
- `# pragma: no cover` markers for untestable prompt_toolkit UI methods (~600 lines)
- `tests/test_tui_pure_logic.py`: 67+ tests for TUI pure logic (editor state, save callbacks, render cells, factory methods)
- `tests/test_exod_coverage.py`: 80+ tests for EXOD PNG filters, HGR encoding, CLI commands, crawl/glyph subcommands
- `tests/test_final_coverage.py`: 41 targeted tests closing the last coverage gaps across 12 modules

### Changed
- Coverage threshold enforced at 100% in CI (was 75%)
- Version bump to 1.20.0

## [1.19.0] - 2026-02-23

### Added
- CHANGELOG.md with full release history from v1.0.0 to v1.19.0
- CONTRIBUTING.md with development setup, testing, and module conventions
- GitHub issue templates (bug report and feature request) and PR template
- Coverage threshold enforcement at 75% via pytest-cov in CI

## [1.18.0] - 2026-02-23

### Added
- TUI editor tests for theme, bestiary, roster, party, and dialog editors
- CLI command tests for roster create, bestiary dump, TLK extract/build, disk build

### Changed
- README updated with bestiary dump and TLK extract/build examples

## [1.17.0] - 2026-02-23

### Changed
- Complete test reorganization: 216 test classes moved from monolithic file to per-module test files
- conftest.py organized with section comments grouping fixtures by data type
- Removed unused sample_map_file fixture

## [1.16.0] - 2026-02-23

### Added
- CI workflows: ruff linting, multi-version Python test matrix, PyPI publish, engine verify
- EXOD TUI tab in unified editor
- Glyph import for EXOD title screen editor
- Native Python ProDOS disk image builder (replaces diskiigs dependency)

## [1.15.0] - 2026-02-22

### Changed
- Package renamed from `u3edit` to `ult3edit` across entire codebase
- CLI command changed from `u3edit` to `ult3edit`, console scripts from `u3-*` to `ult3-*`

## [1.14.0] - 2026-02-23

### Added
- EXOD text crawl editor and glyph table viewer (`exod crawl`/`exod glyph`)
- EXOD title screen editor with HGR graphics conversion (`exod title`)
- Crawl compose tool with 5x7 bitmap font for text-to-crawl generation
- Glyph import, disk build improvements, and EXOD TUI tab

### Changed
- Repository cleanup: removed stale files, updated .gitignore

## [1.13.0] - 2026-02-23

### Added
- EXOD crawl and glyph subcommands documented and wired into CLI
- Voidborn text crawl source integrated into apply.sh pipeline

## [1.12.0] - 2026-02-22

### Added
- Full engine code archaeology: academic-level annotation of all three engine source files (SUBS, ULT3, EXOD)
- Complete engine symbolication: 864 labels renamed to semantic names across all binaries
- Native Python ProDOS disk image builder, replacing external diskiigs dependency

### Changed
- Package renamed from `u3edit` to `ult3edit` (CLI command: `ult3edit`, console scripts: `ult3-*`)

### Fixed
- EXOD phantom coordinate tables corrected (were actually animation frame data)
- ProDOS disk image boot: correct block layout, directory headers, and root entry order
- Windows compatibility fixes in apply.sh

## [1.11.0] - 2026-02-21

### Added
- Progress checker, roster/patch/tlk/diff/text coverage tests reaching 1175+ tests
- Exhaustive error path and edge case test coverage across all modules

### Fixed
- diff_combat tile comparison bug
- 22 quality items fixed across all modules, tools, scripts, and docs

## [1.10.0] - 2026-02-21

### Added
- Expanded CLI test coverage: dispatch integration, filter flags, edge cases

### Fixed
- Text import phantom records, TLK case sensitivity bug, find/replace error handling
- Map compile unknown tile default changed to grass (0x04) for overworld
- Import TypeError bug, special truncated file crash, DiskContext resource leak

## [1.9.0] - 2026-02-21

### Added
- Diff support for MBS, DDRW, SHPS, and TEXT file types
- Compile/decompile warnings and combat import bounds validation
- View command tests for all modules, reaching 1002 tests

### Fixed
- CombatMap boundary checks for truncated CON files
- pyproject.toml version mismatch corrected

## [1.8.0] - 2026-02-21

### Added
- Compile/decompile subcommands for map, shapes, and patch CLI modules
- Refactored Voidborn apply.sh to use ult3edit CLI instead of external scripts

## [1.7.0] - 2026-02-21

### Added
- Engine SDK with byte-identical round-trip assembly for all three engine binaries
- Inline string catalog tool identifying 245 JSR $46BA strings in ULT3
- Inline string patcher (binary-level) and source-level string patcher
- Scenario build pipeline with two-tier patching (source-level preferred, binary fallback)
- `patch strings`, `patch strings-edit`, and `patch strings-import` CLI commands
- Scenario template for total conversion authors

## [1.6.0] - 2026-02-20

### Added
- Total conversion support: raw int/hex fallback for all setters, full byte range equipment
- SHP overlay inline string extraction and replacement (`shapes edit-string`)

### Fixed
- Gender setter crash, PLRS import data loss, combat round-trip bug
- Equipment name setters, special JSON key handling, help text parity
- Map round-trip fidelity, save conflict guard, marks/cards case sensitivity
- HP > MaxHP race condition, shapes import KeyError, hex int parsing across all modules

## [1.5.0] - 2026-02-20

### Added
- CLI parity: standalone `main()` synced with `register_parser()` across all 14 modules
- Full module coverage documentation

## [1.4.0] - 2026-02-20

### Added
- CLI editing for combat (`--tile`, `--monster-pos`, `--pc-pos`) and special (`--tile`) maps
- `--dry-run` support on all import commands across every module
- TLK find-and-replace (`tlk edit --find/--replace`) with `--ignore-case`
- Bestiary bulk editing (`--all`), named flag toggles (`--undead`, `--boss`, etc.), `--type` by name
- Diff tool for comparing game data files and directories

### Fixed
- PRTY field mapping corrected via engine code tracing
- CON and special location layouts verified against engine source

## [1.3.0] - 2026-02-18

### Added
- CIDAR-verified patch regions with structured parsing for engine binary
- Shapes, sound, patch, and DDRW modules for total conversion asset support
- Disk audit command for ProDOS disk space analysis

## [1.2.0] - 2026-02-18

### Added
- `--backup` and `--dry-run` flags on all edit and import commands
- `--validate` data validation for roster, bestiary, save, and combat
- JSON import support for roster, bestiary, save, combat, map, and special
- Map CLI editing (`map set/fill/replace/find`)
- Progression checker (`roster check-progress`) for endgame readiness
- TLK regex search (`tlk search --regex`)
- Test suite expanded to 335 tests

## [1.1.0] - 2026-02-17

### Added
- Real data validation across all modules
- Spell and equipment reference viewers (view-only modules)
- Expanded tile table with full Ultima III tile set
- Unified tabbed TUI editor (`u3edit edit game.po`) with prompt_toolkit
- TUI editors for map, combat, special, text, roster, bestiary, and save
- Race, class, weapon/armor inventory editing in roster CLI

### Fixed
- ProDOS type preservation in disk context read-modify-write cycles
- TLK re-encoding corruption, bestiary data loss on save
- Multiple data integrity bugs in roster setters and combat parsing

## [1.0.0] - 2026-02-17

### Added
- Initial release: complete Ultima III data toolkit
- CLI viewers and editors for roster, bestiary, map, TLK dialog, combat, save, special, and text
- Binary encoding support: BCD, high-bit ASCII, columnar layout, bitmask fields
- ProDOS disk image integration via DiskContext
- JSON output for all view commands
- Test suite with synthesized binary data (no game files needed)
