"""TUI editor for TEXT files (1024 bytes, null-terminated high-ASCII strings)."""

from ..fileutil import decode_high_ascii, encode_high_ascii


class TextRecord:
    """A single text record with offset tracking for rebuilding."""

    def __init__(self, text: str, offset: int, max_len: int):
        self.text = text
        self.offset = offset
        self.max_len = max_len


def parse_text_records(data: bytes) -> list[TextRecord]:
    """Parse a TEXT file into records with offset and max_len tracking."""
    records = []
    offset = 0
    while offset < len(data):
        # Find null terminator
        end = offset
        while end < len(data) and data[end] != 0x00:
            end += 1
        text = decode_high_ascii(data[offset:end])
        max_len = end - offset
        if max_len > 0:
            records.append(TextRecord(text, offset, max_len))
        offset = end + 1
    return records


def rebuild_text_data(records: list[TextRecord], total_size: int) -> bytearray:
    """Rebuild a TEXT file from records, preserving original offsets."""
    out = bytearray(total_size)
    for rec in records:
        encoded = encode_high_ascii(rec.text, rec.max_len)
        out[rec.offset:rec.offset + rec.max_len] = encoded
        # Null terminator after record
        term_pos = rec.offset + rec.max_len
        if term_pos < total_size:
            out[term_pos] = 0x00
    return out


class TextEditor:
    """TUI string list editor for TEXT files.

    Layout:
    +--------------------------------------+
    | TEXT Editor: filename                 |
    +--------------------------------------+
    | [  0] ULTIMA III                     |
    | [  1] EXODUS                    <--  |
    | [  2] PRESS ANY KEY                  |
    +--------------------------------------+
    | Record 1 (6/32 chars) [MODIFIED]     |
    | Enter=edit  Ctrl-S=save  Ctrl-Q=quit |
    +--------------------------------------+
    """

    def __init__(self, file_path: str, data: bytes, save_callback=None):
        self.file_path = file_path
        self.original_size = len(data)
        self.records = parse_text_records(data)
        self.selected_index = 0
        self.dirty = False
        self.save_callback = save_callback

    def _build_ui(self, embedded: bool = False):  # pragma: no cover
        """Build the UI container and keybindings.

        Args:
            embedded: If True, skip Escape/Ctrl+Q/Ctrl+S bindings.

        Returns:
            (container, key_bindings) tuple for embedding in a larger app.
        """
        from prompt_toolkit.layout import HSplit, Window, FormattedTextControl
        from prompt_toolkit.layout.controls import UIControl, UIContent
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.shortcuts import input_dialog

        editor = self

        class RecordListControl(UIControl):
            def create_content(self, width: int, height: int):
                lines = []
                for i, rec in enumerate(editor.records):
                    idx_str = f'[{i:3d}] '
                    text = rec.text[:width - 10]
                    if i == editor.selected_index:
                        style = 'class:palette-selected'
                        marker = ' <'
                    else:
                        style = 'class:palette-normal'
                        marker = ''
                    lines.append([(style, f' {idx_str}{text}{marker}'.ljust(width))])
                if not lines:
                    lines.append([('', ' (no text records)')])
                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        def get_status():
            if editor.records:
                rec = editor.records[editor.selected_index]
                dirty = ' [MODIFIED]' if editor.dirty else ''
                return [
                    ('class:status', f' TEXT Editor: {editor.file_path}'),
                    ('class:status-dirty' if editor.dirty else 'class:status', dirty),
                    ('class:status', f' | Record {editor.selected_index} ({len(rec.text)}/{rec.max_len} chars)'),
                ]
            return [('class:status', f' TEXT Editor: {editor.file_path} | (empty)')]

        def get_help():
            return [
                ('class:help-key', ' Up/Down'), ('class:help-text', '=navigate '),
                ('class:help-key', 'Enter'), ('class:help-text', '=edit '),
                ('class:help-key', 'Ctrl-S'), ('class:help-text', '=save '),
                ('class:help-key', 'Ctrl-Q'), ('class:help-text', '=quit '),
            ]

        record_list = Window(content=RecordListControl(), wrap_lines=False)
        status_bar = Window(content=FormattedTextControl(get_status), height=1)
        help_bar = Window(content=FormattedTextControl(get_help), height=1)

        root = HSplit([record_list, status_bar, help_bar])

        kb = KeyBindings()

        @kb.add('up')
        def _up(event):
            if editor.records:
                editor.selected_index = max(0, editor.selected_index - 1)

        @kb.add('down')
        def _down(event):
            if editor.records:
                editor.selected_index = min(len(editor.records) - 1, editor.selected_index + 1)

        @kb.add('enter')
        def _edit_record(event):
            if not editor.records:
                return
            rec = editor.records[editor.selected_index]
            result = input_dialog(
                title=f'Edit Record {editor.selected_index}',
                text=f'Max {rec.max_len} characters (auto-uppercased):',
                default=rec.text,
            ).run()
            if result is not None:
                new_text = result[:rec.max_len].upper()
                if new_text != rec.text:
                    rec.text = new_text
                    editor.dirty = True

        if not embedded:
            @kb.add('c-s')
            def _save(event):
                editor._save()

            @kb.add('c-q')
            def _quit(event):
                if editor.dirty:
                    editor._save()
                event.app.exit(result=True)

            @kb.add('escape')
            def _escape(event):
                event.app.exit(result=False)

        return root, kb

    def run(self) -> bool:  # pragma: no cover
        """Run the full-screen text editor."""
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

    def _save(self) -> None:
        out = rebuild_text_data(self.records, self.original_size)
        if self.save_callback:
            self.save_callback(bytes(out))
        else:
            with open(self.file_path, 'wb') as f:
                f.write(bytes(out))
        self.dirty = False
