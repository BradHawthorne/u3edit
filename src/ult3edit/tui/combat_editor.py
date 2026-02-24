"""TUI editor for combat maps (CON files, 192 bytes, 11x11 tiles + positions)."""

from ..constants import (
    CON_FILE_SIZE, CON_MAP_WIDTH, CON_MAP_HEIGHT, CON_MAP_TILES,
    CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET, CON_MONSTER_COUNT,
    CON_PC_X_OFFSET, CON_PC_Y_OFFSET, CON_PC_COUNT,
    tile_char,
)
from .base import EditorState, BaseTileEditor


class CombatEditor(BaseTileEditor):
    """11x11 combat battlefield editor with monster/PC placement modes.

    Modes:
      'paint'   - place tiles (default)
      'monster' - place monster start positions (8 slots)
      'pc'      - place PC start positions (4 slots)
    """

    def __init__(self, file_path: str, data: bytes, save_callback=None):
        self.full_data = bytearray(data) if len(data) >= CON_FILE_SIZE else bytearray(CON_FILE_SIZE)
        if len(data) < CON_FILE_SIZE:
            self.full_data[:len(data)] = data

        tile_data = bytearray(self.full_data[:CON_MAP_TILES])
        state = EditorState(
            data=tile_data,
            width=CON_MAP_WIDTH,
            height=CON_MAP_HEIGHT,
        )

        # Extract positions
        self.monster_x = [self.full_data[CON_MONSTER_X_OFFSET + i]
                          for i in range(CON_MONSTER_COUNT)]
        self.monster_y = [self.full_data[CON_MONSTER_Y_OFFSET + i]
                          for i in range(CON_MONSTER_COUNT)]
        self.pc_x = [self.full_data[CON_PC_X_OFFSET + i]
                     for i in range(CON_PC_COUNT)]
        self.pc_y = [self.full_data[CON_PC_Y_OFFSET + i]
                     for i in range(CON_PC_COUNT)]
        self.placement_slot = 0

        super().__init__(state, file_path, title='Combat Map Editor',
                         save_callback=save_callback)

    def _render_cell(self, x: int, y: int, tile_byte: int) -> tuple[str, str]:
        """Overlay monster/PC markers on top of tiles."""
        # Check for monster positions
        for i in range(CON_MONSTER_COUNT):
            if self.monster_x[i] == x and self.monster_y[i] == y:
                if self.monster_x[i] or self.monster_y[i]:  # skip if both 0 (no monster)
                    return 'class:overlay-monster', str(i)

        # Check for PC positions
        for i in range(CON_PC_COUNT):
            if self.pc_x[i] == x and self.pc_y[i] == y:
                return 'class:overlay-pc', str(i + 1)

        # Default tile rendering
        ch = tile_char(tile_byte, False)
        from .theme import tile_style
        style = tile_style(tile_byte, False)
        return style, ch

    def _extra_status(self) -> str:
        mode = self.state.mode
        if mode == 'monster':
            return f'| Mode: MONSTER [slot {self.placement_slot}]'
        elif mode == 'pc':
            return f'| Mode: PC [slot {self.placement_slot + 1}]'
        return '| Mode: PAINT'

    def _place_at_cursor(self) -> None:
        """Place monster or PC at current cursor position based on mode."""
        x, y = self.state.cursor_x, self.state.cursor_y
        if self.state.mode == 'monster':
            self.monster_x[self.placement_slot] = x
            self.monster_y[self.placement_slot] = y
            self.state.dirty = True
            # Auto-advance to next slot
            self.placement_slot = (self.placement_slot + 1) % CON_MONSTER_COUNT
        elif self.state.mode == 'pc':
            self.pc_x[self.placement_slot] = x
            self.pc_y[self.placement_slot] = y
            self.state.dirty = True
            self.placement_slot = (self.placement_slot + 1) % CON_PC_COUNT
        else:
            self.state.paint()

    def _extra_keybindings(self, kb) -> None:  # pragma: no cover
        editor = self

        @kb.add('p')
        def _paint_mode(event):
            editor.state.mode = 'paint'
            editor.placement_slot = 0

        @kb.add('m')
        def _monster_mode(event):
            editor.state.mode = 'monster'
            editor.placement_slot = 0

        @kb.add('@')
        def _pc_mode(event):
            editor.state.mode = 'pc'
            editor.placement_slot = 0

        # Override paint to handle placement modes
        # The base 'space' and 'enter' bindings call state.paint().
        # We need to intercept placement. Rebind space/enter here.
        @kb.add(' ', eager=True)
        def _place_space(event):
            editor._place_at_cursor()

        @kb.add('enter', eager=True)
        def _place_enter(event):
            editor._place_at_cursor()

        # Number keys for slot selection
        for n in range(8):
            @kb.add(str(n))
            def _select_slot(event, slot=n):
                if editor.state.mode == 'monster' and slot < CON_MONSTER_COUNT:
                    editor.placement_slot = slot
                elif editor.state.mode == 'pc' and 1 <= slot <= CON_PC_COUNT:
                    editor.placement_slot = slot - 1

    def _save(self) -> None:
        out = bytearray(CON_FILE_SIZE)
        # Preserve any padding/unknown bytes from original
        out[:] = self.full_data[:CON_FILE_SIZE]
        # Write tiles
        out[:CON_MAP_TILES] = self.state.data
        # Write positions
        for i in range(CON_MONSTER_COUNT):
            out[CON_MONSTER_X_OFFSET + i] = self.monster_x[i]
            out[CON_MONSTER_Y_OFFSET + i] = self.monster_y[i]
        for i in range(CON_PC_COUNT):
            out[CON_PC_X_OFFSET + i] = self.pc_x[i]
            out[CON_PC_Y_OFFSET + i] = self.pc_y[i]
        if self.save_callback:
            self.save_callback(bytes(out))
        else:
            with open(self.file_path, 'wb') as f:
                f.write(bytes(out))
        self.state.dirty = False
