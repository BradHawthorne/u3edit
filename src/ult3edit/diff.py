"""Ultima III: Exodus - Game Data Diff Tool.

Compare two game files or directories and report differences.
Supports all data types: roster, bestiary, combat maps, save state,
overworld/dungeon maps, special locations, TLK dialog, sound (SOSA/SOSM/MBS),
shapes (SHPS), dungeon drawing (DDRW), and text (TEXT).

Usage:
    ult3edit diff file1 file2              # Compare two files of the same type
    ult3edit diff dir1 dir2                # Compare all game files in two directories
    ult3edit diff dir1 dir2 --summary      # Show change counts only
    ult3edit diff dir1 dir2 --json         # Output as JSON
"""

import argparse
import os
import sys
from typing import Any

from .constants import (
    ROSTER_FILE_SIZE, CHAR_RECORD_SIZE,
    MON_FILE_SIZE, MON_LETTERS, CON_FILE_SIZE, CON_NAMES, CON_LETTERS,
    SPECIAL_NAMES,
    PRTY_FILE_SIZE, PLRS_FILE_SIZE,
    SOSA_FILE_SIZE, SOSM_FILE_SIZE, MBS_FILE_SIZE,
    TEXT_FILE_SIZE, DDRW_FILE_SIZE, SHPS_FILE_SIZE,
    MAP_DUNGEON_SIZE, MAP_LETTERS,
    TLK_LETTERS,
)
from .fileutil import resolve_game_file, resolve_single_file
from .json_export import export_json
from .roster import Character, load_roster
from .bestiary import load_mon_file
from .combat import CombatMap
from .save import PartyState
from .tlk import load_tlk_records


# =============================================================================
# Data structures
# =============================================================================

class FieldDiff:
    """A single field difference between two values."""

    def __init__(self, path: str, old: Any, new: Any):
        self.path = path
        self.old = old
        self.new = new


class EntityDiff:
    """Differences for a single entity (character, monster, etc.)."""

    def __init__(self, entity_type: str, label: str):
        self.entity_type = entity_type
        self.label = label
        self.fields: list[FieldDiff] = []

    @property
    def changed(self) -> bool:
        return len(self.fields) > 0


class FileDiff:
    """Differences for a single file type."""

    def __init__(self, file_type: str, file_name: str):
        self.file_type = file_type
        self.file_name = file_name
        self.entities: list[EntityDiff] = []
        self.added_entities: list[str] = []
        self.removed_entities: list[str] = []
        self.tile_changes: int = 0
        self.tile_positions: list[tuple[int, int]] = []
        self.dungeon_width: int = 0  # Set to 16 for dungeon maps

    @property
    def changed(self) -> bool:
        return (any(e.changed for e in self.entities)
                or bool(self.added_entities) or bool(self.removed_entities)
                or self.tile_changes > 0)

    @property
    def change_count(self) -> int:
        return sum(1 for e in self.entities if e.changed)


class GameDiff:
    """Top-level container for all file diffs."""

    def __init__(self):
        self.files: list[FileDiff] = []

    @property
    def changed(self) -> bool:
        return any(f.changed for f in self.files)


# =============================================================================
# Core diff algorithm
# =============================================================================

def diff_dicts(old: dict, new: dict, prefix: str = '') -> list[FieldDiff]:
    """Recursively compare two dicts and return field-level differences."""
    diffs = []
    all_keys = sorted(set(list(old.keys()) + list(new.keys())))
    for key in all_keys:
        path = f"{prefix}.{key}" if prefix else str(key)
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val == new_val:
            continue
        if isinstance(old_val, dict) and isinstance(new_val, dict):
            diffs.extend(diff_dicts(old_val, new_val, path))
        elif isinstance(old_val, list) and isinstance(new_val, list):
            diffs.extend(_diff_lists(old_val, new_val, path))
        else:
            diffs.append(FieldDiff(path, old_val, new_val))
    return diffs


def _diff_lists(old: list, new: list, prefix: str) -> list[FieldDiff]:
    """Compare two lists element-by-element."""
    diffs = []
    max_len = max(len(old), len(new))
    for i in range(max_len):
        path = f"{prefix}[{i}]"
        old_val = old[i] if i < len(old) else None
        new_val = new[i] if i < len(new) else None
        if old_val == new_val:
            continue
        if isinstance(old_val, dict) and isinstance(new_val, dict):
            diffs.extend(diff_dicts(old_val, new_val, path))
        else:
            diffs.append(FieldDiff(path, old_val, new_val))
    return diffs


def _diff_tile_grid(fd: FileDiff, data1: bytes, data2: bytes,
                    width: int, height: int) -> None:
    """Compare two tile grids, populate tile_changes and tile_positions."""
    for y in range(height):
        for x in range(width):
            offset = y * width + x
            if offset < len(data1) and offset < len(data2):
                if data1[offset] != data2[offset]:
                    fd.tile_changes += 1
                    fd.tile_positions.append((x, y))


# =============================================================================
# Per-type diff functions
# =============================================================================

def diff_roster(path1: str, path2: str) -> FileDiff:
    """Compare two ROST files."""
    chars1, _ = load_roster(path1)
    chars2, _ = load_roster(path2)
    fd = FileDiff('ROST', 'ROST')
    for i in range(min(len(chars1), len(chars2))):
        c1, c2 = chars1[i], chars2[i]
        if c1.is_empty and c2.is_empty:
            continue
        label = f"Slot {i}"
        if not c1.is_empty:
            label += f": {c1.name}"
        elif not c2.is_empty:
            label += f": {c2.name}"
        if c1.is_empty and not c2.is_empty:
            fd.added_entities.append(label)
            continue
        if not c1.is_empty and c2.is_empty:
            fd.removed_entities.append(label)
            continue
        ed = EntityDiff('character', label)
        ed.fields = diff_dicts(c1.to_dict(), c2.to_dict())
        fd.entities.append(ed)
    return fd


def diff_bestiary(path1: str, path2: str, letter: str) -> FileDiff:
    """Compare two MON files."""
    mons1 = load_mon_file(path1, letter)
    mons2 = load_mon_file(path2, letter)
    fd = FileDiff(f'MON{letter}', f'MON{letter}')
    for i in range(min(len(mons1), len(mons2))):
        m1, m2 = mons1[i], mons2[i]
        if m1.is_empty and m2.is_empty:
            continue
        label = f"Monster #{i}"
        if not m1.is_empty:
            label += f": {m1.name}"
        elif not m2.is_empty:
            label += f": {m2.name}"
        if m1.is_empty and not m2.is_empty:
            fd.added_entities.append(label)
            continue
        if not m1.is_empty and m2.is_empty:
            fd.removed_entities.append(label)
            continue
        ed = EntityDiff('monster', label)
        ed.fields = diff_dicts(m1.to_dict(), m2.to_dict())
        fd.entities.append(ed)
    return fd


def diff_combat(path1: str, path2: str, letter: str) -> FileDiff:
    """Compare two CON files."""
    with open(path1, 'rb') as f:
        data1 = f.read()
    with open(path2, 'rb') as f:
        data2 = f.read()
    cm1, cm2 = CombatMap(data1), CombatMap(data2)
    fd = FileDiff(f'CON{letter}', f'CON{letter}')
    # Compare structured data (positions, runtime) via to_dict
    d1, d2 = cm1.to_dict(), cm2.to_dict()
    pos_d1 = {k: v for k, v in d1.items() if k != 'tiles'}
    pos_d2 = {k: v for k, v in d2.items() if k != 'tiles'}
    ed = EntityDiff('combat_map', CON_NAMES.get(letter, f'CON{letter}'))
    ed.fields = diff_dicts(pos_d1, pos_d2)
    fd.entities.append(ed)
    # Tile grid comparison — use raw bytes, not string chars from to_dict
    _diff_tile_grid(fd, bytes(cm1.tiles), bytes(cm2.tiles), 11, 11)
    return fd


def _diff_prty(path1: str, path2: str) -> FileDiff:
    """Compare two PRTY files."""
    with open(path1, 'rb') as f:
        party1 = PartyState(f.read())
    with open(path2, 'rb') as f:
        party2 = PartyState(f.read())
    fd = FileDiff('PRTY', 'PRTY')
    ed = EntityDiff('party', 'Party State')
    ed.fields = diff_dicts(party1.to_dict(), party2.to_dict())
    fd.entities.append(ed)
    return fd


def _diff_plrs(path1: str, path2: str) -> FileDiff:
    """Compare two PLRS files (4 active characters)."""
    with open(path1, 'rb') as f:
        d1 = f.read()
    with open(path2, 'rb') as f:
        d2 = f.read()
    fd = FileDiff('PLRS', 'PLRS')
    for i in range(min(4, len(d1) // CHAR_RECORD_SIZE, len(d2) // CHAR_RECORD_SIZE)):
        off = i * CHAR_RECORD_SIZE
        c1 = Character(d1[off:off + CHAR_RECORD_SIZE])
        c2 = Character(d2[off:off + CHAR_RECORD_SIZE])
        if c1.is_empty and c2.is_empty:
            continue
        name = c1.name if not c1.is_empty else c2.name
        label = f"Active slot {i}: {name}"
        if c1.is_empty and not c2.is_empty:
            fd.added_entities.append(label)
            continue
        if not c1.is_empty and c2.is_empty:
            fd.removed_entities.append(label)
            continue
        ed = EntityDiff('character', label)
        ed.fields = diff_dicts(c1.to_dict(), c2.to_dict())
        fd.entities.append(ed)
    return fd


def diff_map(path1: str, path2: str, name: str) -> FileDiff:
    """Compare two MAP files (tile grid only)."""
    with open(path1, 'rb') as f:
        data1 = f.read()
    with open(path2, 'rb') as f:
        data2 = f.read()
    fd = FileDiff(name, name)
    # Dungeon MAPs are 2048 bytes (8 levels × 16×16), overworld are 4096 (64×64)
    if len(data1) == MAP_DUNGEON_SIZE:
        width = 16
        fd.dungeon_width = 16
    else:
        width = 64
    height = len(data1) // width if len(data1) >= width else 1
    _diff_tile_grid(fd, data1, data2, width, height)
    return fd


def diff_special(path1: str, path2: str, name: str) -> FileDiff:
    """Compare two special location files (BRND/SHRN/FNTN/TIME)."""
    with open(path1, 'rb') as f:
        data1 = f.read()
    with open(path2, 'rb') as f:
        data2 = f.read()
    fd = FileDiff(name, name)
    _diff_tile_grid(fd, data1[:121], data2[:121], 11, 11)
    return fd


def diff_tlk(path1: str, path2: str, letter: str) -> FileDiff:
    """Compare two TLK dialog files."""
    recs1 = load_tlk_records(path1)
    recs2 = load_tlk_records(path2)
    fd = FileDiff(f'TLK{letter}', f'TLK{letter}')
    max_recs = max(len(recs1), len(recs2))
    for i in range(max_recs):
        r1 = recs1[i] if i < len(recs1) else None
        r2 = recs2[i] if i < len(recs2) else None
        if r1 == r2:
            continue
        label = f"Record {i}"
        if r1 is None:
            fd.added_entities.append(label)
        elif r2 is None:
            fd.removed_entities.append(label)
        else:
            ed = EntityDiff('dialog', label)
            ed.fields = diff_dicts({'lines': r1}, {'lines': r2})
            fd.entities.append(ed)
    return fd


def diff_binary(path1: str, path2: str, name: str) -> FileDiff:
    """Compare two binary files byte-by-byte."""
    with open(path1, 'rb') as f:
        data1 = f.read()
    with open(path2, 'rb') as f:
        data2 = f.read()
    fd = FileDiff(name, name)
    ed = EntityDiff('binary', name)
    if len(data1) != len(data2):
        ed.fields.append(FieldDiff('size', len(data1), len(data2)))
    min_len = min(len(data1), len(data2))
    changed_bytes = sum(1 for i in range(min_len) if data1[i] != data2[i])
    changed_bytes += abs(len(data1) - len(data2))
    if changed_bytes:
        ed.fields.append(FieldDiff('changed_bytes', 0, changed_bytes))
    fd.entities.append(ed)
    return fd


def diff_save(dir1: str, dir2: str) -> list[FileDiff]:
    """Compare save state files (PRTY, PLRS) between two directories."""
    results = []
    p1 = resolve_single_file(dir1, 'PRTY')
    p2 = resolve_single_file(dir2, 'PRTY')
    if p1 and p2:
        results.append(_diff_prty(p1, p2))
    pl1 = resolve_single_file(dir1, 'PLRS')
    pl2 = resolve_single_file(dir2, 'PLRS')
    if pl1 and pl2:
        results.append(_diff_plrs(pl1, pl2))
    return results


# =============================================================================
# File type detection
# =============================================================================

def detect_file_type(path: str) -> str | None:
    """Detect game file type from filename pattern and size."""
    basename = os.path.basename(path).split('#')[0].upper()
    try:
        size = os.path.getsize(path)
    except OSError:
        return None

    if basename == 'ROST' and size == ROSTER_FILE_SIZE:
        return 'ROST'
    if basename == 'PRTY' and size == PRTY_FILE_SIZE:
        return 'PRTY'
    if basename == 'PLRS' and size == PLRS_FILE_SIZE:
        return 'PLRS'
    if basename == 'SOSA' and size == SOSA_FILE_SIZE:
        return 'SOSA'
    if basename == 'SOSM' and size == SOSM_FILE_SIZE:
        return 'SOSM'
    if basename == 'MBS' and size == MBS_FILE_SIZE:
        return 'MBS'
    if basename == 'TEXT' and size == TEXT_FILE_SIZE:
        return 'TEXT'
    if basename == 'DDRW' and size == DDRW_FILE_SIZE:
        return 'DDRW'
    if basename == 'SHPS' and size == SHPS_FILE_SIZE:
        return 'SHPS'
    if basename.startswith('MON') and len(basename) == 4 and size == MON_FILE_SIZE:
        return basename
    if basename.startswith('CON') and len(basename) == 4 and size == CON_FILE_SIZE:
        return basename
    if basename.startswith('MAP') and len(basename) == 4:
        return basename
    if basename.startswith('TLK') and len(basename) == 4:
        return basename
    if basename in SPECIAL_NAMES:
        return basename
    return None


# =============================================================================
# Dispatchers
# =============================================================================

def diff_file(path1: str, path2: str) -> FileDiff | None:
    """Compare two files of the same type. Auto-detects type."""
    ftype = detect_file_type(path1)
    if ftype is None:
        ftype = detect_file_type(path2)
    if ftype is None:
        print(f"Error: Cannot detect file type for {path1}", file=sys.stderr)
        return None

    if ftype == 'ROST':
        return diff_roster(path1, path2)
    if ftype.startswith('MON'):
        return diff_bestiary(path1, path2, ftype[3])
    if ftype.startswith('CON'):
        return diff_combat(path1, path2, ftype[3])
    if ftype.startswith('MAP'):
        return diff_map(path1, path2, ftype)
    if ftype.startswith('TLK'):
        return diff_tlk(path1, path2, ftype[3])
    if ftype in SPECIAL_NAMES:
        return diff_special(path1, path2, ftype)
    if ftype == 'PRTY':
        return _diff_prty(path1, path2)
    if ftype == 'PLRS':
        return _diff_plrs(path1, path2)
    if ftype in ('SOSA', 'SOSM', 'MBS', 'TEXT', 'DDRW', 'SHPS'):
        return diff_binary(path1, path2, ftype)
    return None  # pragma: no cover — all detect_file_type results handled above


def diff_directories(dir1: str, dir2: str) -> GameDiff:
    """Compare all known game files between two directories."""
    gd = GameDiff()

    # Roster
    r1 = resolve_single_file(dir1, 'ROST')
    r2 = resolve_single_file(dir2, 'ROST')
    if r1 and r2:
        gd.files.append(diff_roster(r1, r2))

    # Bestiary (MON A-L, Z)
    for letter in MON_LETTERS:
        p1 = resolve_game_file(dir1, 'MON', letter)
        p2 = resolve_game_file(dir2, 'MON', letter)
        if p1 and p2:
            gd.files.append(diff_bestiary(p1, p2, letter))

    # Combat (CON files)
    for letter in CON_LETTERS:
        p1 = resolve_game_file(dir1, 'CON', letter)
        p2 = resolve_game_file(dir2, 'CON', letter)
        if p1 and p2:
            gd.files.append(diff_combat(p1, p2, letter))

    # Maps
    for letter in MAP_LETTERS:
        p1 = resolve_game_file(dir1, 'MAP', letter)
        p2 = resolve_game_file(dir2, 'MAP', letter)
        if p1 and p2:
            name = f'MAP{letter}'
            gd.files.append(diff_map(p1, p2, name))

    # Save state (PRTY, PLRS)
    for fd in diff_save(dir1, dir2):
        gd.files.append(fd)

    # Sound files (SOSA, SOSM, MBS)
    for snd in ('SOSA', 'SOSM', 'MBS'):
        s1 = resolve_single_file(dir1, snd)
        s2 = resolve_single_file(dir2, snd)
        if s1 and s2:
            gd.files.append(diff_binary(s1, s2, snd))

    # Binary data files (TEXT, DDRW, SHPS)
    for binfile in ('TEXT', 'DDRW', 'SHPS'):
        b1 = resolve_single_file(dir1, binfile)
        b2 = resolve_single_file(dir2, binfile)
        if b1 and b2:
            gd.files.append(diff_binary(b1, b2, binfile))

    # Special locations
    for prefix in SPECIAL_NAMES:
        p1 = resolve_single_file(dir1, prefix)
        p2 = resolve_single_file(dir2, prefix)
        if p1 and p2:
            gd.files.append(diff_special(p1, p2, prefix))

    # TLK files
    for letter in TLK_LETTERS:
        p1 = resolve_game_file(dir1, 'TLK', letter)
        p2 = resolve_game_file(dir2, 'TLK', letter)
        if p1 and p2:
            gd.files.append(diff_tlk(p1, p2, letter))

    return gd


# =============================================================================
# Output formatters
# =============================================================================

def format_text(gd: GameDiff) -> str:
    """Format a GameDiff as human-readable text."""
    lines = []
    changed_files = [f for f in gd.files if f.changed]
    if not changed_files:
        lines.append("No differences found.")
        return '\n'.join(lines)

    for fd in changed_files:
        lines.append(f"--- {fd.file_name}")
        lines.append(f"+++ {fd.file_name}")

        for label in fd.removed_entities:
            lines.append(f"  - Removed: {label}")
        for label in fd.added_entities:
            lines.append(f"  + Added: {label}")

        for ed in fd.entities:
            if not ed.changed:
                continue
            lines.append(f"  {ed.label}:")
            for f in ed.fields:
                lines.append(f"    {f.path}: {f.old} -> {f.new}")

        if fd.tile_changes > 0:
            lines.append(f"  Tiles changed: {fd.tile_changes}")
            show = fd.tile_positions if fd.tile_changes <= 20 else fd.tile_positions[:10]
            for x, y in show:
                if fd.dungeon_width:
                    lvl, row = divmod(y, fd.dungeon_width)
                    lines.append(f"    Level {lvl} ({x}, {row})")
                else:
                    lines.append(f"    ({x}, {y})")
            if fd.tile_changes > 20:
                lines.append(f"    ... and {fd.tile_changes - 10} more")
        lines.append('')

    return '\n'.join(lines)


def format_summary(gd: GameDiff) -> str:
    """Format a GameDiff as a summary (counts only)."""
    lines = []
    changed_files = [f for f in gd.files if f.changed]
    if not changed_files:
        lines.append("No differences found.")
        return '\n'.join(lines)

    for fd in changed_files:
        counts = []
        entity_changes = fd.change_count
        if entity_changes:
            counts.append(f"{entity_changes} changed")
        if fd.added_entities:
            counts.append(f"{len(fd.added_entities)} added")
        if fd.removed_entities:
            counts.append(f"{len(fd.removed_entities)} removed")
        if fd.tile_changes:
            counts.append(f"{fd.tile_changes} tiles changed")
        summary = ', '.join(counts)
        lines.append(f"  {fd.file_name}: {summary}")

    lines.append(f"\nTotal: {len(changed_files)} file(s) with differences")
    return '\n'.join(lines)


def to_json(gd: GameDiff) -> dict:
    """Convert a GameDiff to a JSON-serializable dict."""
    result: dict[str, Any] = {'files': []}
    for fd in gd.files:
        if not fd.changed:
            continue
        fobj: dict[str, Any] = {
            'file': fd.file_name,
            'type': fd.file_type,
            'entities': [],
        }
        if fd.added_entities:
            fobj['added'] = fd.added_entities
        if fd.removed_entities:
            fobj['removed'] = fd.removed_entities
        for ed in fd.entities:
            if not ed.changed:
                continue
            eobj = {
                'label': ed.label,
                'type': ed.entity_type,
                'changes': [
                    {'field': f.path, 'old': f.old, 'new': f.new}
                    for f in ed.fields
                ],
            }
            fobj['entities'].append(eobj)
        if fd.tile_changes:
            fobj['tile_changes'] = fd.tile_changes
            fobj['tile_positions'] = [{'x': x, 'y': y} for x, y in fd.tile_positions]
        result['files'].append(fobj)
    return result


# =============================================================================
# CLI
# =============================================================================

def cmd_diff(args) -> None:
    """Main diff command handler."""
    path1, path2 = args.path1, args.path2
    is_dir1 = os.path.isdir(path1)
    is_dir2 = os.path.isdir(path2)

    if is_dir1 != is_dir2:
        print("Error: Both arguments must be files or both must be directories",
              file=sys.stderr)
        sys.exit(1)

    if is_dir1:
        gd = diff_directories(path1, path2)
    else:
        fd = diff_file(path1, path2)
        if fd is None:
            sys.exit(1)
        gd = GameDiff()
        gd.files.append(fd)

    if args.json:
        export_json(to_json(gd), getattr(args, 'output', None))
    elif args.summary:
        print(format_summary(gd))
    else:
        print(format_text(gd))


def register_parser(subparsers) -> None:
    """Register diff subcommand on a CLI subparser group."""
    p = subparsers.add_parser('diff', help='Compare game data files or directories')
    p.add_argument('path1', help='First file or directory')
    p.add_argument('path2', help='Second file or directory')
    p.add_argument('--json', action='store_true', help='Output as JSON')
    p.add_argument('--summary', action='store_true', help='Show summary counts only')
    p.add_argument('--output', '-o', help='Output file (for --json)')


def dispatch(args) -> None:
    """Dispatch diff command."""
    cmd_diff(args)


def main() -> None:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Game Data Diff Tool')
    parser.add_argument('path1', help='First file or directory')
    parser.add_argument('path2', help='Second file or directory')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--summary', action='store_true', help='Show summary counts only')
    parser.add_argument('--output', '-o', help='Output file')
    args = parser.parse_args()
    cmd_diff(args)


if __name__ == '__main__':
    main()
