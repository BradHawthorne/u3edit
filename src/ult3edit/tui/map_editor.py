"""TUI editor for MAP files (overworld 64x64, town, dungeon 16x16 x 8 levels)."""

from .base import EditorState, BaseTileEditor


class MapEditor(BaseTileEditor):
    """Map tile editor with scrolling viewport and dungeon level switching.

    Overworld/town: single grid, scrolling viewport.
    Dungeon: 8 levels of 16x16, keys 1-8 switch levels.
    """

    def __init__(self, file_path: str, data: bytes, is_dungeon: bool = False,
                 save_callback=None):
        self.full_data = bytearray(data)
        self.is_dungeon = is_dungeon
        self.current_level = 0
        self.num_levels = len(data) // 256 if is_dungeon else 1

        if is_dungeon:
            # Pad to at least one full level if file is short
            if len(self.full_data) < 256:
                self.full_data.extend(bytes(256 - len(self.full_data)))
            level_data = bytearray(self.full_data[:256])
            state = EditorState(
                data=level_data, width=16, height=16, is_dungeon=True,
            )
        else:
            width = 64
            height = len(data) // width
            state = EditorState(
                data=bytearray(data), width=width, height=height,
            )

        super().__init__(state, file_path, title='Map Editor',
                         save_callback=save_callback)

    def switch_level(self, level: int) -> None:
        """Switch dungeon level (0-based). Saves current level to full_data first."""
        if not self.is_dungeon or level < 0 or level >= self.num_levels:
            return
        # Save current level back
        offset = self.current_level * 256
        self.full_data[offset:offset + 256] = self.state.data
        # Load new level
        self.current_level = level
        offset = level * 256
        self.state.data = bytearray(self.full_data[offset:offset + 256])
        self.state.cursor_x = min(self.state.cursor_x, 15)
        self.state.cursor_y = min(self.state.cursor_y, 15)

    def _extra_status(self) -> str:
        if self.is_dungeon:
            return f'| Level {self.current_level + 1}/{self.num_levels}'
        return f'| {self.state.width}x{self.state.height}'

    def _extra_keybindings(self, kb) -> None:
        editor = self

        # Dungeon level switching (1-8)
        for n in range(1, 9):
            @kb.add(str(n))
            def _switch(event, level=n - 1):
                editor.switch_level(level)

    def _save(self) -> None:
        if self.is_dungeon:
            offset = self.current_level * 256
            self.full_data[offset:offset + 256] = self.state.data
            out = bytes(self.full_data)
        else:
            out = bytes(self.state.data)
        if self.save_callback:
            self.save_callback(out)
        else:
            with open(self.file_path, 'wb') as f:
                f.write(out)
        self.state.dirty = False
