"""Ultima III: Exodus - Combat Battlefield Viewer.

CON files: 192 bytes (0xC0), loaded at $9900. Layout verified via engine
code tracing (ULT3.s lookup_add at $7E18, spawn loop, PC init loop):
  0x00-0x78: 11x11 battlefield tiles (121 bytes)
  0x79-0x7F: Unused padding (7 bytes, never read by engine)
  0x80-0x87: Monster start X positions [0-7]
  0x88-0x8F: Monster start Y positions [0-7]
  0x90-0x97: Runtime: saved tile under monster (overwritten at combat init)
  0x98-0x9F: Runtime: monster type/status (overwritten at combat init)
  0xA0-0xA3: PC start X positions [0-3]
  0xA4-0xA7: PC start Y positions [0-3]
  0xA8-0xAB: Runtime: saved tile under PC (overwritten at init)
  0xAC-0xAF: Runtime: PC appearance tile (overwritten by JSR $7F5D)
  0xB0-0xBF: Unused tail padding (16 bytes, never read by engine)
"""

import argparse
import json
import os
import sys

from .constants import (
    CON_NAMES, CON_LETTERS, CON_FILE_SIZE,
    CON_MAP_WIDTH, CON_MAP_HEIGHT, CON_MAP_TILES,
    CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET, CON_MONSTER_COUNT,
    CON_PC_X_OFFSET, CON_PC_Y_OFFSET, CON_PC_COUNT,
    CON_PADDING1_OFFSET, CON_PADDING1_SIZE,
    CON_RUNTIME_MONSAVE_OFFSET, CON_RUNTIME_MONSTATUS_OFFSET,
    CON_RUNTIME_PCSAVE_OFFSET, CON_RUNTIME_PCTILE_OFFSET,
    CON_PADDING2_OFFSET, CON_PADDING2_SIZE,
    tile_char, TILE_CHARS_REVERSE,
)
from .fileutil import resolve_game_file, backup_file, hex_int
from .json_export import export_json


class CombatMap:
    """A single combat battlefield."""

    def __init__(self, data: bytes):
        self.tiles = data[:CON_MAP_TILES]
        self.monster_x = [data[CON_MONSTER_X_OFFSET + i] if CON_MONSTER_X_OFFSET + i < len(data) else 0
                          for i in range(CON_MONSTER_COUNT)]
        self.monster_y = [data[CON_MONSTER_Y_OFFSET + i] if CON_MONSTER_Y_OFFSET + i < len(data) else 0
                          for i in range(CON_MONSTER_COUNT)]
        self.pc_x = [data[CON_PC_X_OFFSET + i] if CON_PC_X_OFFSET + i < len(data) else 0
                     for i in range(CON_PC_COUNT)]
        self.pc_y = [data[CON_PC_Y_OFFSET + i] if CON_PC_Y_OFFSET + i < len(data) else 0
                     for i in range(CON_PC_COUNT)]
        # Padding and runtime arrays — preserved for round-trip fidelity
        # padding1: 7 bytes between tile grid and monster positions (unused)
        self.padding1 = list(data[CON_PADDING1_OFFSET:CON_PADDING1_OFFSET + CON_PADDING1_SIZE]) \
            if len(data) > CON_PADDING1_OFFSET else [0] * CON_PADDING1_SIZE
        # runtime_data: 16 bytes of runtime arrays (saved-tile + status, overwritten at init)
        self.runtime_monster = list(data[CON_RUNTIME_MONSAVE_OFFSET:CON_RUNTIME_MONSTATUS_OFFSET + 8]) \
            if len(data) > CON_RUNTIME_MONSAVE_OFFSET else [0] * 16
        # runtime_pc: 8 bytes of runtime arrays (saved-tile + appearance, overwritten at init)
        self.runtime_pc = list(data[CON_RUNTIME_PCSAVE_OFFSET:CON_RUNTIME_PCTILE_OFFSET + 4]) \
            if len(data) > CON_RUNTIME_PCSAVE_OFFSET else [0] * 8
        # padding2: 16 bytes of unused tail padding
        self.padding2 = list(data[CON_PADDING2_OFFSET:CON_PADDING2_OFFSET + CON_PADDING2_SIZE]) \
            if len(data) > CON_PADDING2_OFFSET else [0] * CON_PADDING2_SIZE

    def render(self) -> str:
        """Render 11x11 battlefield with position overlays."""
        # Build base grid
        grid = []
        for y in range(CON_MAP_HEIGHT):
            row = []
            for x in range(CON_MAP_WIDTH):
                offset = y * CON_MAP_WIDTH + x
                if offset < len(self.tiles):
                    row.append(tile_char(self.tiles[offset]))
                else:
                    row.append(' ')
            grid.append(row)

        # Overlay monster positions
        for i in range(CON_MONSTER_COUNT):
            mx, my = self.monster_x[i], self.monster_y[i]
            if 0 <= mx < CON_MAP_WIDTH and 0 <= my < CON_MAP_HEIGHT:
                grid[my][mx] = 'm'

        # Overlay PC positions
        for i in range(CON_PC_COUNT):
            px, py = self.pc_x[i], self.pc_y[i]
            if 0 <= px < CON_MAP_WIDTH and 0 <= py < CON_MAP_HEIGHT:
                grid[py][px] = '@'

        lines = ['     ' + ''.join(f'{x % 10}' for x in range(CON_MAP_WIDTH))]
        for y, row in enumerate(grid):
            lines.append(f'  {y:2d}  {"".join(row)}')

        # Show padding/runtime data if non-zero (for debugging/analysis)
        has_extra = any(self.padding1) or any(self.runtime_monster) or any(self.padding2)
        if has_extra:
            lines.append('')
            if any(self.padding1):
                lines.append(f'  Padding (0x79): {" ".join(f"{b:02X}" for b in self.padding1)}')
            if any(self.runtime_monster):
                lines.append(f'  Runtime monster (0x90): {" ".join(f"{b:02X}" for b in self.runtime_monster)}')
            if any(self.padding2):
                lines.append(f'  Padding (0xB0): {" ".join(f"{b:02X}" for b in self.padding2)}')

        return '\n'.join(lines)

    def to_dict(self) -> dict:
        result = {
            'tiles': [[tile_char(self.tiles[y * CON_MAP_WIDTH + x])
                        for x in range(CON_MAP_WIDTH)
                        if y * CON_MAP_WIDTH + x < len(self.tiles)]
                       for y in range(CON_MAP_HEIGHT)
                       if y * CON_MAP_WIDTH < len(self.tiles)],
            'monsters': [{'x': self.monster_x[i], 'y': self.monster_y[i]}
                         for i in range(CON_MONSTER_COUNT)],
            'pcs': [{'x': self.pc_x[i], 'y': self.pc_y[i]}
                    for i in range(CON_PC_COUNT)],
            'padding': {
                'pre_monster': self.padding1,
                'tail': self.padding2,
            },
            'runtime': {
                'monster_save_and_status': self.runtime_monster,
                'pc_save_and_tile': self.runtime_pc,
            },
        }
        return result


def validate_combat_map(cm: CombatMap) -> list[str]:
    """Check a combat map for data integrity issues.

    Returns a list of warning strings (empty if valid).
    """
    warnings = []

    # Check tile alignment (should be multiples of 4 for animation masking)
    misaligned = 0
    for i, t in enumerate(cm.tiles):
        if t != 0 and (t & 0x03) != 0:
            misaligned += 1
    if misaligned:
        warnings.append(f"{misaligned} tile(s) not aligned to 4-byte boundary (animation frame masking)")

    # Monster positions should be within grid bounds
    for i in range(CON_MONSTER_COUNT):
        mx, my = cm.monster_x[i], cm.monster_y[i]
        if (mx or my) and (mx >= CON_MAP_WIDTH or my >= CON_MAP_HEIGHT):
            warnings.append(f"Monster {i} position ({mx}, {my}) out of bounds")

    # PC positions should be within grid bounds
    for i in range(CON_PC_COUNT):
        px, py = cm.pc_x[i], cm.pc_y[i]
        if px >= CON_MAP_WIDTH or py >= CON_MAP_HEIGHT:
            warnings.append(f"PC {i} position ({px}, {py}) out of bounds")

    # Check for overlapping start positions (only count non-zero positions)
    positions = {}
    for i in range(CON_MONSTER_COUNT):
        mx, my = cm.monster_x[i], cm.monster_y[i]
        if mx or my:
            key = (mx, my)
            if key in positions:
                warnings.append(f"Monster {i} overlaps with {positions[key]} at ({mx}, {my})")
            positions[key] = f"monster {i}"
    for i in range(CON_PC_COUNT):
        px, py = cm.pc_x[i], cm.pc_y[i]
        if px or py:
            key = (px, py)
            if key in positions:
                warnings.append(f"PC {i} overlaps with {positions[key]} at ({px}, {py})")
            positions[key] = f"PC {i}"

    return warnings


def cmd_view(args) -> None:
    path_or_dir = args.path
    do_validate = getattr(args, 'validate', False)

    if os.path.isdir(path_or_dir):
        con_files = []
        for letter in CON_LETTERS:
            path = resolve_game_file(path_or_dir, 'CON', letter)
            if path:
                con_files.append((letter, path))

        if not con_files:
            print(f"Error: No CON files found in {path_or_dir}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            result = {}
            for letter, path in con_files:
                with open(path, 'rb') as f:
                    data = f.read()
                cm = CombatMap(data)
                d = {
                    'name': CON_NAMES.get(letter, 'Unknown'),
                    **cm.to_dict(),
                }
                if do_validate:
                    d['warnings'] = validate_combat_map(cm)
                result[f'CON{letter}'] = d
            export_json(result, args.output)
            return

        print(f"\n=== Ultima III Combat Maps ({len(con_files)} arenas) ===\n")
        for letter, path in con_files:
            name = CON_NAMES.get(letter, 'Unknown')
            with open(path, 'rb') as f:
                data = f.read()
            cm = CombatMap(data)
            print(f"  CON{letter} - {name}")
            print(cm.render())
            print(f"  Legend: @ = PC start, m = monster start")
            if do_validate:
                for w in validate_combat_map(cm):
                    print(f"  WARNING: {w}", file=sys.stderr)
            print()
    else:
        with open(path_or_dir, 'rb') as f:
            data = f.read()

        filename = os.path.basename(path_or_dir)

        if args.json:
            cm = CombatMap(data)
            d = {'file': filename, **cm.to_dict()}
            if do_validate:
                d['warnings'] = validate_combat_map(cm)
            export_json(d, args.output)
            return

        cm = CombatMap(data)
        print(f"\n=== Combat Map: {filename} ({len(data)} bytes) ===\n")
        print(cm.render())
        print(f"\n  Legend: @ = PC start, m = monster start")
        if do_validate:
            for w in validate_combat_map(cm):
                print(f"  WARNING: {w}", file=sys.stderr)
        print()


def _has_cli_edit_args(args) -> bool:
    """Check if any CLI editing flags were provided."""
    return (getattr(args, 'tile', None) is not None
            or getattr(args, 'monster_pos', None) is not None
            or getattr(args, 'pc_pos', None) is not None)


def cmd_edit(args) -> None:
    """Edit a combat map via CLI args or TUI fallback."""
    if not _has_cli_edit_args(args):
        # No CLI args — launch TUI editor
        from .tui import require_prompt_toolkit
        require_prompt_toolkit()
        from .tui.combat_editor import CombatEditor

        with open(args.file, 'rb') as f:
            data = f.read()

        editor = CombatEditor(args.file, data)
        editor.run()
        return

    # CLI editing mode
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())
    dry_run = getattr(args, 'dry_run', False)
    do_backup = getattr(args, 'backup', False)
    changes = 0

    # --tile X Y VALUE
    if getattr(args, 'tile', None) is not None:
        tx, ty, tval = args.tile
        if not (0 <= tx < CON_MAP_WIDTH and 0 <= ty < CON_MAP_HEIGHT):
            print(f"Error: tile ({tx}, {ty}) out of bounds (0-{CON_MAP_WIDTH - 1})",
                  file=sys.stderr)
            sys.exit(1)
        if not (0 <= tval <= 255):
            print(f"Error: tile value {tval} out of range (0-255)", file=sys.stderr)
            sys.exit(1)
        offset = ty * CON_MAP_WIDTH + tx
        old_val = data[offset]
        data[offset] = tval
        print(f"Tile ({tx}, {ty}): ${old_val:02X} -> ${tval:02X}")
        changes += 1

    # --monster-pos INDEX X Y
    if getattr(args, 'monster_pos', None) is not None:
        idx, mx, my = args.monster_pos
        if not (0 <= idx < CON_MONSTER_COUNT):
            print(f"Error: monster index {idx} out of range (0-{CON_MONSTER_COUNT - 1})",
                  file=sys.stderr)
            sys.exit(1)
        if not (0 <= mx < CON_MAP_WIDTH and 0 <= my < CON_MAP_HEIGHT):
            print(f"Error: position ({mx}, {my}) out of bounds (0-{CON_MAP_WIDTH - 1})",
                  file=sys.stderr)
            sys.exit(1)
        old_x = data[CON_MONSTER_X_OFFSET + idx]
        old_y = data[CON_MONSTER_Y_OFFSET + idx]
        data[CON_MONSTER_X_OFFSET + idx] = mx
        data[CON_MONSTER_Y_OFFSET + idx] = my
        print(f"Monster {idx}: ({old_x}, {old_y}) -> ({mx}, {my})")
        changes += 1

    # --pc-pos INDEX X Y
    if getattr(args, 'pc_pos', None) is not None:
        idx, px, py = args.pc_pos
        if not (0 <= idx < CON_PC_COUNT):
            print(f"Error: PC index {idx} out of range (0-{CON_PC_COUNT - 1})",
                  file=sys.stderr)
            sys.exit(1)
        if not (0 <= px < CON_MAP_WIDTH and 0 <= py < CON_MAP_HEIGHT):
            print(f"Error: position ({px}, {py}) out of bounds (0-{CON_MAP_WIDTH - 1})",
                  file=sys.stderr)
            sys.exit(1)
        old_x = data[CON_PC_X_OFFSET + idx]
        old_y = data[CON_PC_Y_OFFSET + idx]
        data[CON_PC_X_OFFSET + idx] = px
        data[CON_PC_Y_OFFSET + idx] = py
        print(f"PC {idx}: ({old_x}, {old_y}) -> ({px}, {py})")
        changes += 1

    if changes == 0:
        print("No changes specified.")
        return

    if getattr(args, 'validate', False):
        cm = CombatMap(data)
        for w in validate_combat_map(cm):
            print(f"  WARNING: {w}", file=sys.stderr)

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = getattr(args, 'output', None) or args.file
    if do_backup and (not getattr(args, 'output', None) or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Saved to {output}")


def cmd_import(args) -> None:
    """Import a combat map from JSON."""
    with open(args.file, 'rb') as f:
        data = bytearray(f.read())
    do_backup = getattr(args, 'backup', False)
    dry_run = getattr(args, 'dry_run', False)

    with open(args.json_file, 'r', encoding='utf-8') as f:
        jdata = json.load(f)

    # Import tiles
    tile_changes = 0
    tiles = jdata.get('tiles', [])
    for y, row in enumerate(tiles[:CON_MAP_HEIGHT]):
        for x, ch in enumerate(row[:CON_MAP_WIDTH]):
            offset = y * CON_MAP_WIDTH + x
            new_val = TILE_CHARS_REVERSE.get(ch, 0x20)
            if data[offset] != new_val:
                tile_changes += 1
            data[offset] = new_val

    # Import monster positions (accept list or dict-of-dicts format)
    pos_changes = 0
    raw_mons = jdata.get('monsters', [])
    if isinstance(raw_mons, dict):
        raw_mons = [raw_mons[str(i)] for i in sorted(int(k) for k in raw_mons)]
    for i, m in enumerate(raw_mons[:CON_MONSTER_COUNT]):
        nx, ny = m.get('x', 0), m.get('y', 0)
        if data[CON_MONSTER_X_OFFSET + i] != nx or data[CON_MONSTER_Y_OFFSET + i] != ny:
            pos_changes += 1
        data[CON_MONSTER_X_OFFSET + i] = nx
        data[CON_MONSTER_Y_OFFSET + i] = ny

    # Import PC positions (accept list or dict-of-dicts format)
    raw_pcs = jdata.get('pcs', [])
    if isinstance(raw_pcs, dict):
        raw_pcs = [raw_pcs[str(i)] for i in sorted(int(k) for k in raw_pcs)]
    for i, p in enumerate(raw_pcs[:CON_PC_COUNT]):
        nx, ny = p.get('x', 0), p.get('y', 0)
        if data[CON_PC_X_OFFSET + i] != nx or data[CON_PC_Y_OFFSET + i] != ny:
            pos_changes += 1
        data[CON_PC_X_OFFSET + i] = nx
        data[CON_PC_Y_OFFSET + i] = ny

    # Import padding/runtime data for round-trip fidelity
    padding = jdata.get('padding', {})
    for i, b in enumerate(padding.get('pre_monster', [])[:CON_PADDING1_SIZE]):
        if CON_PADDING1_OFFSET + i < len(data):
            data[CON_PADDING1_OFFSET + i] = b
    for i, b in enumerate(padding.get('tail', [])[:CON_PADDING2_SIZE]):
        if CON_PADDING2_OFFSET + i < len(data):
            data[CON_PADDING2_OFFSET + i] = b
    runtime = jdata.get('runtime', {})
    for i, b in enumerate(runtime.get('monster_save_and_status', [])[:16]):
        if CON_RUNTIME_MONSAVE_OFFSET + i < len(data):
            data[CON_RUNTIME_MONSAVE_OFFSET + i] = b
    for i, b in enumerate(runtime.get('pc_save_and_tile', [])[:8]):
        if CON_RUNTIME_PCSAVE_OFFSET + i < len(data):
            data[CON_RUNTIME_PCSAVE_OFFSET + i] = b
    # Backward compat: accept old 'descriptor' key
    desc = jdata.get('descriptor', {})
    if desc:
        for i, b in enumerate(desc.get('block1', [])[:CON_PADDING1_SIZE]):
            if CON_PADDING1_OFFSET + i < len(data):
                data[CON_PADDING1_OFFSET + i] = b

    print(f"Import: {tile_changes} tile(s) changed, {pos_changes} position(s) changed")

    if dry_run:
        print("Dry run - no changes written.")
        return

    output = args.output if args.output else args.file
    if do_backup and (not args.output or args.output == args.file):
        backup_file(args.file)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Imported combat map to {output}")


def _add_combat_write_args(p) -> None:
    """Add common write arguments for combat edit commands."""
    p.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p.add_argument('--dry-run', action='store_true', help='Show changes without writing')


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('combat', help='Combat battlefield viewer/editor')
    sub = p.add_subparsers(dest='combat_command')

    p_view = sub.add_parser('view', help='View combat maps')
    p_view.add_argument('path', help='CON file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')
    p_view.add_argument('--validate', action='store_true', help='Check data integrity')

    p_edit = sub.add_parser('edit', help='Edit a combat map (CLI or TUI)')
    p_edit.add_argument('file', help='CON file path')
    p_edit.add_argument('--tile', type=hex_int, nargs=3, metavar=('X', 'Y', 'VALUE'),
                        help='Set tile at (X, Y) to VALUE')
    p_edit.add_argument('--monster-pos', type=int, nargs=3, metavar=('INDEX', 'X', 'Y'),
                        help='Set monster INDEX start position to (X, Y)')
    p_edit.add_argument('--pc-pos', type=int, nargs=3, metavar=('INDEX', 'X', 'Y'),
                        help='Set PC INDEX start position to (X, Y)')
    _add_combat_write_args(p_edit)
    p_edit.add_argument('--validate', action='store_true', help='Check data integrity after edit')

    p_import = sub.add_parser('import', help='Import combat map from JSON')
    p_import.add_argument('file', help='CON file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true', help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true', help='Show changes without writing')


def dispatch(args) -> None:
    cmd = args.combat_command
    if cmd == 'view':
        cmd_view(args)
    elif cmd == 'edit':
        cmd_edit(args)
    elif cmd == 'import':
        cmd_import(args)
    else:
        print("Usage: u3edit combat {view|edit|import} ...", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Combat Battlefield Viewer')
    sub = parser.add_subparsers(dest='combat_command')

    p_view = sub.add_parser('view', help='View combat maps')
    p_view.add_argument('path', help='CON file or GAME directory')
    p_view.add_argument('--json', action='store_true', help='Output as JSON')
    p_view.add_argument('--output', '-o', help='Output file (for --json)')
    p_view.add_argument('--validate', action='store_true', help='Check data integrity')

    p_edit = sub.add_parser('edit', help='Edit a combat map (CLI or TUI)')
    p_edit.add_argument('file', help='CON file path')
    p_edit.add_argument('--tile', type=hex_int, nargs=3, metavar=('X', 'Y', 'VALUE'),
                        help='Set tile at (X, Y) to VALUE')
    p_edit.add_argument('--monster-pos', type=int, nargs=3,
                        metavar=('INDEX', 'X', 'Y'),
                        help='Set monster INDEX start position to (X, Y)')
    p_edit.add_argument('--pc-pos', type=int, nargs=3,
                        metavar=('INDEX', 'X', 'Y'),
                        help='Set PC INDEX start position to (X, Y)')
    _add_combat_write_args(p_edit)
    p_edit.add_argument('--validate', action='store_true', help='Check data integrity after edit')

    p_import = sub.add_parser('import', help='Import combat map from JSON')
    p_import.add_argument('file', help='CON file path')
    p_import.add_argument('json_file', help='JSON file to import')
    p_import.add_argument('--output', '-o', help='Output file (default: overwrite)')
    p_import.add_argument('--backup', action='store_true',
                          help='Create .bak backup before overwrite')
    p_import.add_argument('--dry-run', action='store_true',
                          help='Show changes without writing')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
