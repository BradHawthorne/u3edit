"""TUI dialog editor for TLK files (multi-record string list editing)."""

from ..tlk import load_tlk_records, encode_record, decode_record, is_text_record
from ..constants import TLK_RECORD_END


class DialogEditor:
    """String list editor for TLK dialog files.

    Similar to TextEditor but handles multi-line records with 0xFF line breaks.
    """

    def __init__(self, file_path, data, save_callback=None):
        self.file_path = file_path
        self.original_data = bytes(data)
        self.save_callback = save_callback
        self.dirty = False

        # Parse records from raw data, preserving binary parts
        self._raw_parts = data.split(bytes([TLK_RECORD_END]))
        self._text_part_indices = []  # maps text record index → raw part index
        self._modified_records = set()  # track which text records were edited
        self.records = []  # list of list[str] (lines per record)
        for i, part in enumerate(self._raw_parts):
            if not part:
                continue
            if not is_text_record(part):
                continue
            self._text_part_indices.append(i)
            self.records.append(decode_record(part + bytes([TLK_RECORD_END])))

        self.selected_index = 0

    @property
    def is_dirty(self):
        return self.dirty

    def save(self):
        self._save()

    def _save(self):
        # Only re-encode records the user actually modified; preserve others as-is
        parts = list(self._raw_parts)
        for text_idx in self._modified_records:
            raw_idx = self._text_part_indices[text_idx]
            encoded = encode_record(self.records[text_idx])
            parts[raw_idx] = encoded[:-1]  # strip trailing TLK_RECORD_END
        data = bytes([TLK_RECORD_END]).join(parts)
        if self.save_callback:
            self.save_callback(data)
        else:
            with open(self.file_path, 'wb') as f:
                f.write(data)
        self.dirty = False

    def build_ui(self):
        from prompt_toolkit.layout import HSplit, Window, FormattedTextControl
        from prompt_toolkit.layout.controls import UIControl, UIContent
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.shortcuts import input_dialog

        editor = self

        class RecordListControl(UIControl):
            def create_content(self, width, height):
                lines = []
                for i, rec in enumerate(editor.records):
                    text = ' / '.join(rec)
                    if len(text) > width - 10:
                        text = text[:width - 13] + '...'
                    if i == editor.selected_index:
                        style = 'class:palette-selected'
                        marker = ' <'
                    else:
                        style = 'class:palette-normal'
                        marker = ''
                    lines.append([(style,
                                   f' [{i:2d}] {text}{marker}'.ljust(width))])
                if not lines:
                    lines.append([('', ' (no dialog records)')])
                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        def get_status():
            dirty = ' [MODIFIED]' if editor.dirty else ''
            if editor.records:
                rec = editor.records[editor.selected_index]
                line_count = len(rec)
                return [
                    ('class:status', f' Dialog Editor: {editor.file_path}'),
                    ('class:status-dirty' if editor.dirty else 'class:status', dirty),
                    ('class:status', f' | Record {editor.selected_index} ({line_count} lines)'),
                ]
            return [('class:status', f' Dialog Editor: {editor.file_path} | (empty)')]

        def get_help():
            return [
                ('class:help-key', ' Up/Down'), ('class:help-text', '=navigate '),
                ('class:help-key', 'Enter'), ('class:help-text', '=edit '),
                ('class:help-key', 'Escape'), ('class:help-text', '=back '),
            ]

        root = HSplit([
            Window(content=RecordListControl(), wrap_lines=False),
            Window(content=FormattedTextControl(get_status), height=1),
            Window(content=FormattedTextControl(get_help), height=1),
        ])

        kb = KeyBindings()

        @kb.add('up')
        def _up(event):
            if editor.records:
                editor.selected_index = max(0, editor.selected_index - 1)

        @kb.add('down')
        def _down(event):
            if editor.records:
                editor.selected_index = min(len(editor.records) - 1,
                                            editor.selected_index + 1)

        @kb.add('enter')
        def _edit(event):
            if not editor.records:
                return
            rec = editor.records[editor.selected_index]
            current = '\\n'.join(rec)
            result = input_dialog(
                title=f'Edit Record {editor.selected_index}',
                text='Use \\n for line breaks:',
                default=current,
            ).run()
            if result is not None and result != current:
                editor.records[editor.selected_index] = result.split('\\n')
                editor._modified_records.add(editor.selected_index)
                editor.dirty = True

        return root, kb
