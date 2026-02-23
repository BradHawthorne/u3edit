"""TUI editors for EXOD title screen data.

Provides three sub-editors for use within a DrillDownTab:
- ExodCrawlEditor: editable coordinate list for text crawl
- ExodGlyphViewer: read-only glyph pointer table display
- ExodFrameViewer: read-only HGR frame region summary
"""

from ..exod import (
    EXOD_SIZE,
    FRAMES,
    GLYPH_COLS,
    GLYPH_COUNT,
    GLYPH_DATA_SIZE,
    GLYPH_ROWS,
    GLYPH_TABLE_OFFSET,
    GLYPH_VARIANTS,
    HGR_PIXELS_PER_BYTE,
    TEXT_CRAWL_OFFSET,
    build_text_crawl,
    extract_glyph_pointers,
    extract_glyph_subpointers,
    extract_text_crawl,
    glyph_ptr_to_file_offset,
    patch_text_crawl,
)


class ExodCrawlEditor:
    """Editable coordinate list for EXOD text crawl data.

    Displays (X, Y) coordinate pairs with cursor navigation.
    Enter edits the selected coordinate, 'a' adds a new point,
    'd' deletes the selected point.
    """

    def __init__(self, exod_data, save_callback=None):
        self._data = bytearray(exod_data)
        self.coords = extract_text_crawl(self._data)
        self.selected_index = 0
        self.dirty = False
        self.save_callback = save_callback

    @property
    def name(self):
        return 'Crawl'

    @property
    def is_dirty(self):
        return self.dirty

    def build_ui(self):
        from prompt_toolkit.layout import HSplit, Window, FormattedTextControl
        from prompt_toolkit.layout.controls import UIControl, UIContent
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.shortcuts import input_dialog

        editor = self

        class CoordListControl(UIControl):
            def create_content(self, width, height):
                lines = []
                lines.append([('class:palette-header',
                               f' Text Crawl — {len(editor.coords)} points '.ljust(width))])
                lines.append([('class:palette-header',
                               ' ' + '─' * (width - 2) + ' ')])
                for i, (x, y) in enumerate(editor.coords):
                    label = f' [{i:3d}]  X={x:3d}  Y={y:3d}'
                    if i == editor.selected_index:
                        style = 'class:palette-selected'
                        marker = ' <'
                    else:
                        style = 'class:palette-normal'
                        marker = ''
                    lines.append([(style, f'{label}{marker}'.ljust(width))])
                if not editor.coords:
                    lines.append([('', ' (no coordinate points)')])
                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        def get_status():
            dirty = ' [MODIFIED]' if editor.dirty else ''
            if editor.coords:
                x, y = editor.coords[editor.selected_index]
                return [
                    ('class:status', f' Crawl Editor'),
                    ('class:status-dirty' if editor.dirty else 'class:status', dirty),
                    ('class:status', f' | Point {editor.selected_index}/{len(editor.coords)} '
                                     f'  X={x} Y={y}'),
                ]
            return [('class:status', f' Crawl Editor | (empty){dirty}')]

        def get_help():
            return [
                ('class:help-key', ' Up/Down'), ('class:help-text', '=navigate '),
                ('class:help-key', 'Enter'), ('class:help-text', '=edit '),
                ('class:help-key', 'a'), ('class:help-text', '=add '),
                ('class:help-key', 'd'), ('class:help-text', '=delete '),
            ]

        coord_list = Window(content=CoordListControl(), wrap_lines=False)
        status_bar = Window(content=FormattedTextControl(get_status), height=1)
        help_bar = Window(content=FormattedTextControl(get_help), height=1)
        root = HSplit([coord_list, status_bar, help_bar])

        kb = KeyBindings()

        @kb.add('up')
        def _up(event):
            if editor.coords:
                editor.selected_index = max(0, editor.selected_index - 1)

        @kb.add('down')
        def _down(event):
            if editor.coords:
                editor.selected_index = min(len(editor.coords) - 1,
                                            editor.selected_index + 1)

        @kb.add('enter')
        def _edit(event):
            if not editor.coords:
                return
            x, y = editor.coords[editor.selected_index]
            result = input_dialog(
                title=f'Edit Point {editor.selected_index}',
                text='Enter X,Y (e.g. 140,132):',
                default=f'{x},{y}',
            ).run()
            if result is not None:
                try:
                    parts = result.split(',')
                    nx, ny = int(parts[0].strip()), int(parts[1].strip())
                    nx = max(1, min(255, nx))
                    ny = max(0, min(191, ny))
                    if (nx, ny) != (x, y):
                        editor.coords[editor.selected_index] = (nx, ny)
                        editor.dirty = True
                except (ValueError, IndexError):
                    pass

        @kb.add('a')
        def _add(event):
            # Insert after current position with default coords
            idx = editor.selected_index + 1 if editor.coords else 0
            editor.coords.insert(idx, (140, 132))
            editor.selected_index = idx
            editor.dirty = True

        @kb.add('d')
        def _delete(event):
            if editor.coords:
                del editor.coords[editor.selected_index]
                if editor.selected_index >= len(editor.coords) and editor.coords:
                    editor.selected_index = len(editor.coords) - 1
                editor.dirty = True

        return root, kb

    def save(self):
        crawl_bytes = build_text_crawl(self.coords)
        data = bytearray(self._data)
        patch_text_crawl(data, crawl_bytes)
        self._data = bytes(data)
        if self.save_callback:
            self.save_callback(self._data)
        self.dirty = False


class ExodGlyphViewer:
    """Read-only display of glyph pointer table structure."""

    def __init__(self, exod_data):
        self._data = bytes(exod_data)

    @property
    def name(self):
        return 'Glyphs'

    @property
    def is_dirty(self):
        return False

    def build_ui(self):
        from prompt_toolkit.layout import HSplit, Window, FormattedTextControl
        from prompt_toolkit.layout.controls import UIControl, UIContent
        from prompt_toolkit.key_binding import KeyBindings

        viewer = self
        pointers = extract_glyph_pointers(viewer._data)

        class GlyphTableControl(UIControl):
            def create_content(self, width, height):
                lines = []
                lines.append([('class:palette-header',
                               f' Glyph Table — {GLYPH_COUNT} entries '.ljust(width))])
                lines.append([('class:palette-header',
                               ' ' + '─' * (width - 2) + ' ')])
                for i, ptr in enumerate(pointers):
                    off = glyph_ptr_to_file_offset(ptr)
                    status = 'OK' if off >= 0 else 'OUT OF RANGE'
                    lines.append([('class:palette-normal',
                                   f'  Glyph {i}: ${ptr:04X} (offset ${off:04X}) [{status}]'.ljust(width))])
                    if off >= 0:
                        subptrs = extract_glyph_subpointers(viewer._data, ptr)
                        for j, sp in enumerate(subptrs):
                            sp_off = glyph_ptr_to_file_offset(sp)
                            sp_status = 'OK' if sp_off >= 0 else 'N/A'
                            dim = f'{GLYPH_COLS * HGR_PIXELS_PER_BYTE}x{GLYPH_ROWS}'
                            lines.append([('class:palette-normal',
                                           f'    v{j}: ${sp:04X} -> ${sp_off:04X} '
                                           f'{dim} [{sp_status}]'.ljust(width))])
                lines.append([('', '')])
                lines.append([('class:palette-normal',
                               f'  Total data: {GLYPH_COUNT} glyphs x '
                               f'{GLYPH_VARIANTS} variants x '
                               f'{GLYPH_DATA_SIZE} bytes = '
                               f'{GLYPH_COUNT * GLYPH_VARIANTS * GLYPH_DATA_SIZE} bytes'.ljust(width))])
                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        def get_status():
            return [('class:status', ' Glyph Table (read-only)')]

        def get_help():
            return [('class:help-key', ' Escape'), ('class:help-text', '=back ')]

        root = HSplit([
            Window(content=GlyphTableControl(), wrap_lines=False),
            Window(content=FormattedTextControl(get_status), height=1),
            Window(content=FormattedTextControl(get_help), height=1),
        ])
        return root, KeyBindings()

    def save(self):
        pass


class ExodFrameViewer:
    """Read-only summary of HGR frame regions."""

    def __init__(self, exod_data):
        self._data = bytes(exod_data)

    @property
    def name(self):
        return 'Frames'

    @property
    def is_dirty(self):
        return False

    def build_ui(self):
        from prompt_toolkit.layout import HSplit, Window, FormattedTextControl
        from prompt_toolkit.layout.controls import UIControl, UIContent
        from prompt_toolkit.key_binding import KeyBindings

        viewer = self

        class FrameTableControl(UIControl):
            def create_content(self, width, height):
                lines = []
                lines.append([('class:palette-header',
                               f' HGR Frames — {len(FRAMES)} defined '.ljust(width))])
                lines.append([('class:palette-header',
                               ' ' + '─' * (width - 2) + ' ')])
                lines.append([('class:palette-normal',
                               f'  {"Name":<12s} {"Rows":>5s} {"Cols":>5s} '
                               f'{"Width":>6s} {"Offset":>8s} {"Desc"}'.ljust(width))])
                lines.append([('class:palette-normal',
                               f'  {"─" * 10:<12s} {"─" * 4:>5s} {"─" * 4:>5s} '
                               f'{"─" * 5:>6s} {"─" * 6:>8s} {"─" * 20}'.ljust(width))])
                for name, (start_row, num_rows, col_bytes, col_offset, desc) in FRAMES.items():
                    px_width = col_bytes * HGR_PIXELS_PER_BYTE
                    data_size = num_rows * col_bytes
                    lines.append([('class:palette-normal',
                                   f'  {name:<12s} {num_rows:>5d} {col_bytes:>5d} '
                                   f'{px_width:>5d}px '
                                   f'{data_size:>6d}B  {desc}'.ljust(width))])
                lines.append([('', '')])
                lines.append([('class:palette-normal',
                               f'  HGR page: $2000-$3FFF (8,192 bytes)'.ljust(width))])
                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        def get_status():
            return [('class:status', ' Frame Summary (read-only)')]

        def get_help():
            return [('class:help-key', ' Escape'), ('class:help-text', '=back ')]

        root = HSplit([
            Window(content=FrameTableControl(), wrap_lines=False),
            Window(content=FormattedTextControl(get_status), height=1),
            Window(content=FormattedTextControl(get_help), height=1),
        ])
        return root, KeyBindings()

    def save(self):
        pass


def make_exod_crawl_editor(exod_data, save_callback):
    """Factory: create ExodCrawlEditor tab."""
    return ExodCrawlEditor(exod_data, save_callback=save_callback)


def make_exod_glyph_viewer(exod_data):
    """Factory: create ExodGlyphViewer tab."""
    return ExodGlyphViewer(exod_data)


def make_exod_frame_viewer(exod_data):
    """Factory: create ExodFrameViewer tab."""
    return ExodFrameViewer(exod_data)
