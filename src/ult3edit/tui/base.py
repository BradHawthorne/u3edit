"""Base tile editor: EditorState (pure data) + BaseTileEditor (prompt_toolkit UI)."""

from dataclasses import dataclass, field

from ..constants import tile_char, tile_name, TILES, DUNGEON_TILES


# =============================================================================
# EditorState: pure data model, testable without prompt_toolkit
# =============================================================================

@dataclass
class EditorState:
    """Mutable state for a tile grid editor. No I/O or rendering."""

    data: bytearray
    width: int
    height: int
    cursor_x: int = 0
    cursor_y: int = 0
    viewport_x: int = 0
    viewport_y: int = 0
    viewport_w: int = 40
    viewport_h: int = 20
    selected_tile: int = 0x04
    is_dungeon: bool = False
    dirty: bool = False
    mode: str = 'paint'
    palette: list = field(default_factory=list)
    palette_index: int = 0

    def __post_init__(self):
        if not self.palette:
            source = DUNGEON_TILES if self.is_dungeon else TILES
            self.palette = sorted(source.keys())
            if self.palette:
                self.selected_tile = self.palette[0]

    def tile_at(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.data[y * self.width + x]
        return 0

    def set_tile(self, x: int, y: int, value: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.data[y * self.width + x] = value
            self.dirty = True

    def move_cursor(self, dx: int, dy: int) -> None:
        self.cursor_x = max(0, min(self.width - 1, self.cursor_x + dx))
        self.cursor_y = max(0, min(self.height - 1, self.cursor_y + dy))
        self._scroll_viewport()

    def _scroll_viewport(self) -> None:
        margin = 2
        # Horizontal
        if self.cursor_x < self.viewport_x + margin:
            self.viewport_x = max(0, self.cursor_x - margin)
        if self.cursor_x >= self.viewport_x + self.viewport_w - margin:
            self.viewport_x = self.cursor_x - self.viewport_w + margin + 1
        # Vertical
        if self.cursor_y < self.viewport_y + margin:
            self.viewport_y = max(0, self.cursor_y - margin)
        if self.cursor_y >= self.viewport_y + self.viewport_h - margin:
            self.viewport_y = self.cursor_y - self.viewport_h + margin + 1
        # Clamp
        max_vx = max(0, self.width - self.viewport_w)
        max_vy = max(0, self.height - self.viewport_h)
        self.viewport_x = max(0, min(self.viewport_x, max_vx))
        self.viewport_y = max(0, min(self.viewport_y, max_vy))

    def paint(self) -> None:
        self.set_tile(self.cursor_x, self.cursor_y, self.selected_tile)

    def select_next_tile(self) -> None:
        if self.palette:
            self.palette_index = (self.palette_index + 1) % len(self.palette)
            self.selected_tile = self.palette[self.palette_index]

    def select_prev_tile(self) -> None:
        if self.palette:
            self.palette_index = (self.palette_index - 1) % len(self.palette)
            self.selected_tile = self.palette[self.palette_index]



# =============================================================================
# BaseTileEditor: prompt_toolkit UI layer
# =============================================================================

class BaseTileEditor:
    """Base class for TUI tile editors using prompt_toolkit.

    Layout:
    +---------------------------+----------+
    |   Grid Viewport           | Palette  |
    |   (with cursor highlight) | Sidebar  |
    +---------------------------+----------+
    | Status: pos, tile, mode, dirty       |
    | Keys: arrows/space/[]/Ctrl-S/Ctrl-Q  |
    +--------------------------------------+

    In embedded mode (within UnifiedApp), Ctrl-S/Ctrl-Q/Escape are handled
    by the parent app, not this widget.

    Subclasses override: _save(), _extra_status(), _extra_keybindings(),
    _render_cell() for custom overlays.
    """

    def __init__(self, state: EditorState, file_path: str, title: str = 'Tile Editor',
                 save_callback=None):
        self.state = state
        self.file_path = file_path
        self.title = title
        self.show_help = False
        self.save_callback = save_callback

    def _save(self) -> None:
        """Write data to file. Override in subclasses."""
        if self.save_callback:
            self.save_callback(bytes(self.state.data))
        else:
            with open(self.file_path, 'wb') as f:
                f.write(bytes(self.state.data))
        self.state.dirty = False

    def _extra_status(self) -> str:
        """Extra status text for subclass-specific info. Override as needed."""
        return ''

    def _render_cell(self, x: int, y: int, tile_byte: int) -> tuple[str, str]:
        """Return (style, char) for a cell. Override for custom overlays."""
        ch = tile_char(tile_byte, self.state.is_dungeon)
        from .theme import tile_style
        style = tile_style(tile_byte, self.state.is_dungeon)
        return style, ch

    def _extra_keybindings(self, kb) -> None:
        """Add subclass-specific keybindings. Override as needed."""
        pass

    def _build_ui(self, embedded: bool = False):  # pragma: no cover
        """Build the UI container and keybindings.

        Args:
            embedded: If True, skip Escape/Ctrl+Q/Ctrl+S bindings (handled by host app).

        Returns:
            (container, key_bindings) tuple for embedding in a larger app.
        """
        from prompt_toolkit.layout import HSplit, VSplit, Window, FormattedTextControl
        from prompt_toolkit.layout.controls import UIControl, UIContent
        from prompt_toolkit.key_binding import KeyBindings

        editor = self
        state = self.state

        # --- Grid Control ---
        class GridControl(UIControl):
            def create_content(self, width: int, height: int):
                usable_w = max(1, width - 5)
                usable_h = max(1, height)
                state.viewport_w = min(usable_w, state.width)
                state.viewport_h = min(usable_h, state.height)
                state._scroll_viewport()

                lines = []
                for vy in range(state.viewport_h):
                    gy = state.viewport_y + vy
                    fragments = []
                    fragments.append(('class:row-label', f'{gy:3d} '))
                    for vx in range(state.viewport_w):
                        gx = state.viewport_x + vx
                        tile_byte = state.tile_at(gx, gy)
                        style, ch = editor._render_cell(gx, gy, tile_byte)
                        if gx == state.cursor_x and gy == state.cursor_y:
                            style = 'class:cursor'
                        fragments.append((style, ch))
                    lines.append(fragments)
                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        # --- Palette Control ---
        class PalControl(UIControl):
            def create_content(self, width: int, height: int):
                source = DUNGEON_TILES if state.is_dungeon else TILES
                lines = []
                lines.append([('class:palette-header', ' Tiles ')])
                lines.append([('class:palette-header', ' ───── ')])
                for i, tile_id in enumerate(state.palette):
                    ch, name = source.get(tile_id, ('?', f'${tile_id:02X}'))
                    label = f' {ch} {name[:width-4]}'
                    if i == state.palette_index:
                        style = 'class:palette-selected'
                    else:
                        style = 'class:palette-normal'
                    lines.append([(style, label.ljust(width))])
                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        # --- Status bar ---
        def get_status():
            t = state.tile_at(state.cursor_x, state.cursor_y)
            tname = tile_name(t, state.is_dungeon)
            dirty = ' [MODIFIED]' if state.dirty else ''
            extra = editor._extra_status()
            sel_name = tile_name(state.selected_tile, state.is_dungeon)
            return [
                ('class:status', f' {editor.title}: {editor.file_path} '),
                ('class:status-dirty' if state.dirty else 'class:status', dirty),
                ('class:status', f' | ({state.cursor_x},{state.cursor_y}) {tname}'),
                ('class:status', f' | Brush: {tile_char(state.selected_tile, state.is_dungeon)} {sel_name}'),
                ('class:status', f' {extra}'),
            ]

        def get_help():
            if editor.show_help:
                return [
                    ('class:help-key', ' Arrows'), ('class:help-text', '=move '),
                    ('class:help-key', 'Space'), ('class:help-text', '=paint '),
                    ('class:help-key', '[ ]'), ('class:help-text', '=tile '),
                    ('class:help-key', 'Ctrl-S'), ('class:help-text', '=save '),
                    ('class:help-key', 'Ctrl-Q'), ('class:help-text', '=quit '),
                    ('class:help-key', '?'), ('class:help-text', '=help'),
                ]
            return [
                ('class:status-text', ' Press '),
                ('class:help-key', '?'),
                ('class:status-text', ' for help'),
            ]

        # --- Layout ---
        grid_window = Window(content=GridControl(), wrap_lines=False)
        palette_window = Window(content=PalControl(), width=18, wrap_lines=False)
        status_bar = Window(content=FormattedTextControl(get_status), height=1)
        help_bar = Window(content=FormattedTextControl(get_help), height=1)

        root = HSplit([
            VSplit([grid_window, palette_window]),
            status_bar,
            help_bar,
        ])

        # --- Keybindings ---
        kb = KeyBindings()

        @kb.add('up')
        def _up(event):
            state.move_cursor(0, -1)

        @kb.add('down')
        def _down(event):
            state.move_cursor(0, 1)

        @kb.add('left')
        def _left(event):
            state.move_cursor(-1, 0)

        @kb.add('right')
        def _right(event):
            state.move_cursor(1, 0)

        @kb.add(' ')
        def _paint_space(event):
            state.paint()

        @kb.add('enter')
        def _paint_enter(event):
            state.paint()

        @kb.add(']')
        def _next_tile(event):
            state.select_next_tile()

        @kb.add('[')
        def _prev_tile(event):
            state.select_prev_tile()

        @kb.add('?')
        def _toggle_help(event):
            editor.show_help = not editor.show_help

        if not embedded:
            @kb.add('c-s')
            def _save_cmd(event):
                editor._save()

            @kb.add('c-q')
            def _quit(event):
                if state.dirty:
                    editor._save()
                event.app.exit(result=True)

            @kb.add('escape')
            def _escape(event):
                event.app.exit(result=False)

        self._extra_keybindings(kb)

        return root, kb

    def run(self) -> bool:  # pragma: no cover
        """Run the full-screen editor. Returns True if saved."""
        from prompt_toolkit import Application
        from prompt_toolkit.layout import Layout
        from .theme import U3_STYLE

        root, kb = self._build_ui(embedded=False)
        app = Application(
            layout=Layout(root),
            key_bindings=kb,
            style=U3_STYLE,
            full_screen=True,
            mouse_support=False,
        )
        return app.run()
