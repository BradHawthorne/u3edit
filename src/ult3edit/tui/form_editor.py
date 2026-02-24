"""Form-based editor for record data (roster, bestiary, party).

FormField: a single editable field with label, getter, setter.
FormEditorTab: scrollable list of records with field-level editing.
"""


class FormField:
    """A single editable field in a form."""

    def __init__(self, label, getter, setter, fmt='str'):
        self.label = label
        self.getter = getter   # callable() -> display value
        self.setter = setter   # callable(new_value_str) -> None
        self.fmt = fmt         # 'str', 'int'


class FormEditorTab:
    """Scrollable record list with field editing via input_dialog.

    Layout:
    +--------------------------------------+
    | Title                                |
    +--------------------------------------+
    |  [record list or field list]         |
    +--------------------------------------+
    | Status bar                           |
    | Help bar                             |
    +--------------------------------------+

    Two modes:
      - Record list: shows all records, Enter opens field list
      - Field list: shows fields for selected record, Enter edits field
    """

    def __init__(self, tab_name, records, record_label_fn, field_factory,
                 save_callback, get_save_data):
        """
        Args:
            tab_name: Display name for the tab.
            records: List of data objects.
            record_label_fn: (record, index) -> display string for the record list.
            field_factory: (record) -> list[FormField] for field editing.
            save_callback: callable(bytes) to save data.
            get_save_data: callable() -> bytes to get serialized data.
        """
        self.tab_name = tab_name
        self.records = records
        self.record_label_fn = record_label_fn
        self.field_factory = field_factory
        self.save_callback = save_callback
        self.get_save_data = get_save_data
        self.selected_record = 0
        self.selected_field = 0
        self.editing_fields = False  # False = record list, True = field list
        self.dirty = False
        self._current_fields = []

    @property
    def name(self):
        return self.tab_name

    @property
    def is_dirty(self):
        return self.dirty

    def save(self):
        if self.save_callback and self.get_save_data:
            self.save_callback(self.get_save_data())
            self.dirty = False

    def build_ui(self):  # pragma: no cover
        from prompt_toolkit.layout import HSplit, Window, FormattedTextControl
        from prompt_toolkit.layout.controls import UIControl, UIContent
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.shortcuts import input_dialog

        tab = self

        class ListControl(UIControl):
            def create_content(self, width, height):
                lines = []
                if not tab.editing_fields:
                    # Record list mode
                    for i, rec in enumerate(tab.records):
                        label = tab.record_label_fn(rec, i)
                        if i == tab.selected_record:
                            style = 'class:palette-selected'
                            marker = ' <'
                        else:
                            style = 'class:palette-normal'
                            marker = ''
                        lines.append([(style,
                                       f' {label}{marker}'.ljust(width))])
                else:
                    # Field list mode
                    lines.append([('class:palette-header',
                                   f' Editing record {tab.selected_record} '.ljust(width))])
                    lines.append([('class:palette-header',
                                   ' ' + '─' * (width - 2) + ' ')])
                    for i, field in enumerate(tab._current_fields):
                        val = field.getter()
                        label = f' {field.label:<16s}: {val}'
                        if i == tab.selected_field:
                            style = 'class:palette-selected'
                            marker = ' <'
                        else:
                            style = 'class:palette-normal'
                            marker = ''
                        lines.append([(style,
                                       f'{label}{marker}'.ljust(width))])

                if not lines:
                    lines.append([('', ' (no records)')])
                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        def get_status():
            dirty = ' [MODIFIED]' if tab.dirty else ''
            if tab.editing_fields and tab._current_fields:
                field = tab._current_fields[tab.selected_field]
                return [
                    ('class:status', f' {tab.tab_name}'),
                    ('class:status-dirty' if tab.dirty else 'class:status', dirty),
                    ('class:status', f' | Record {tab.selected_record} | {field.label}'),
                ]
            return [
                ('class:status', f' {tab.tab_name}'),
                ('class:status-dirty' if tab.dirty else 'class:status', dirty),
                ('class:status', f' | {len(tab.records)} records'),
            ]

        def get_help():
            if tab.editing_fields:
                return [
                    ('class:help-key', ' Up/Down'), ('class:help-text', '=navigate '),
                    ('class:help-key', 'Enter'), ('class:help-text', '=edit field '),
                    ('class:help-key', 'Escape'), ('class:help-text', '=back '),
                ]
            return [
                ('class:help-key', ' Up/Down'), ('class:help-text', '=navigate '),
                ('class:help-key', 'Enter'), ('class:help-text', '=edit '),
            ]

        root = HSplit([
            Window(content=ListControl(), wrap_lines=False),
            Window(content=FormattedTextControl(get_status), height=1),
            Window(content=FormattedTextControl(get_help), height=1),
        ])

        kb = KeyBindings()

        @kb.add('up')
        def _up(event):
            if tab.editing_fields:
                if tab._current_fields:
                    tab.selected_field = max(0, tab.selected_field - 1)
            else:
                if tab.records:
                    tab.selected_record = max(0, tab.selected_record - 1)

        @kb.add('down')
        def _down(event):
            if tab.editing_fields:
                if tab._current_fields:
                    tab.selected_field = min(len(tab._current_fields) - 1,
                                             tab.selected_field + 1)
            else:
                if tab.records:
                    tab.selected_record = min(len(tab.records) - 1,
                                              tab.selected_record + 1)

        @kb.add('enter')
        def _enter(event):
            if not tab.records:
                return
            if not tab.editing_fields:
                # Enter field editing mode
                rec = tab.records[tab.selected_record]
                tab._current_fields = tab.field_factory(rec)
                if not tab._current_fields:
                    return
                tab.selected_field = 0
                tab.editing_fields = True
            else:
                # Edit the selected field
                if not tab._current_fields:
                    return
                field = tab._current_fields[tab.selected_field]
                current_val = str(field.getter())
                result = input_dialog(
                    title=f'Edit {field.label}',
                    text=f'Current: {current_val}',
                    default=current_val,
                ).run()
                if result is not None and result != current_val:
                    try:
                        field.setter(result)
                        tab.dirty = True
                    except (ValueError, TypeError):
                        pass  # Invalid input, ignore

        @kb.add('escape')
        def _back(event):
            if tab.editing_fields:
                tab.editing_fields = False
                tab._current_fields = []

        return root, kb
