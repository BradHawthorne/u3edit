"""Editor tab abstractions for the unified tabbed editor.

EditorTab: protocol interface for all tabs.
TileEditorTab: wraps a BaseTileEditor subclass.
TextEditorTab: wraps a TextEditor.
DrillDownTab: file selector → embedded editor → back.
"""

from prompt_toolkit.layout import HSplit, Window, FormattedTextControl
from prompt_toolkit.layout.containers import DynamicContainer
from prompt_toolkit.layout.controls import UIControl, UIContent
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings, \
    ConditionalKeyBindings
from prompt_toolkit.filters import Condition


class TileEditorTab:
    """Wraps a BaseTileEditor subclass as a tab."""

    def __init__(self, editor):
        self._editor = editor

    @property
    def name(self):
        return self._editor.title

    @property
    def is_dirty(self):
        return self._editor.state.dirty

    def build_ui(self):
        return self._editor._build_ui(embedded=True)

    def save(self):
        self._editor._save()


class TextEditorTab:
    """Wraps a TextEditor as a tab."""

    def __init__(self, editor):
        self._editor = editor

    @property
    def name(self):
        return 'Text'

    @property
    def is_dirty(self):
        return self._editor.dirty

    def build_ui(self):
        return self._editor._build_ui(embedded=True)

    def save(self):
        self._editor._save()


class DialogEditorTab:
    """Wraps a DialogEditor as a tab."""

    def __init__(self, editor):
        self._editor = editor

    @property
    def name(self):
        return 'Dialog'

    @property
    def is_dirty(self):
        return self._editor.is_dirty

    def build_ui(self):
        return self._editor.build_ui()

    def save(self):
        self._editor.save()


class DrillDownTab:
    """Multi-file tab: file selector list → editor → back with Escape.

    file_list: [(file_name, display_name), ...]
    editor_factory: (file_name, data, save_callback) -> tab-like object with
                    build_ui()/save()/is_dirty
    """

    def __init__(self, tab_name, file_list, editor_factory, session):
        self.tab_name = tab_name
        self.file_list = file_list
        self.editor_factory = editor_factory
        self.session = session
        self.selected_index = 0
        self.active_editor = None  # None = selector mode

    @property
    def name(self):
        return self.tab_name

    @property
    def is_dirty(self):
        if self.active_editor:
            return self.active_editor.is_dirty
        return False

    def save(self):
        if self.active_editor:
            self.active_editor.save()

    def build_ui(self):
        """Build a dynamic container that switches between selector and editor."""
        tab = self

        # --- Selector UI ---
        class SelectorControl(UIControl):
            def create_content(self, width, height):
                lines = []
                lines.append([('class:palette-header',
                               f' {tab.tab_name} — Select a file '.ljust(width))])
                lines.append([('class:palette-header', ' ' + '─' * (width - 2) + ' ')])
                for i, (fname, display) in enumerate(tab.file_list):
                    label = f' {fname:<8s} {display}'
                    if i == tab.selected_index:
                        style = 'class:palette-selected'
                        marker = ' <'
                    else:
                        style = 'class:palette-normal'
                        marker = ''
                    lines.append([(style, f'{label}{marker}'.ljust(width))])
                if not tab.file_list:
                    lines.append([('', ' (no files found)')])
                return UIContent(
                    get_line=lambda i: lines[i] if i < len(lines) else [],
                    line_count=len(lines),
                )

        def get_selector_status():
            if tab.file_list:
                fname, display = tab.file_list[tab.selected_index]
                return [('class:status', f' {tab.tab_name}: {fname} — {display}')]
            return [('class:status', f' {tab.tab_name}: (empty)')]

        def get_selector_help():
            return [
                ('class:help-key', ' Up/Down'), ('class:help-text', '=navigate '),
                ('class:help-key', 'Enter'), ('class:help-text', '=open '),
            ]

        selector_layout = HSplit([
            Window(content=SelectorControl(), wrap_lines=False),
            Window(content=FormattedTextControl(get_selector_status), height=1),
            Window(content=FormattedTextControl(get_selector_help), height=1),
        ])

        # --- Dynamic content ---
        self._selector_layout = selector_layout
        self._editor_container = None
        self._editor_kb = None

        def get_container():
            if tab.active_editor and tab._editor_container:
                return tab._editor_container
            return tab._selector_layout

        dynamic = DynamicContainer(get_container)

        # --- Keybindings ---
        # Selector keybindings (only active when no sub-editor is open)
        selector_kb = KeyBindings()
        in_selector = Condition(lambda: tab.active_editor is None)

        @selector_kb.add('up')
        def _up(event):
            if tab.file_list:
                tab.selected_index = max(0, tab.selected_index - 1)

        @selector_kb.add('down')
        def _down(event):
            if tab.file_list:
                tab.selected_index = min(len(tab.file_list) - 1,
                                         tab.selected_index + 1)

        @selector_kb.add('enter')
        def _open(event):
            if tab.file_list:
                tab._open_editor()

        # Escape: return to selector (always active, saves dirty sub-editor)
        nav_kb = KeyBindings()

        @nav_kb.add('escape')
        def _back(event):
            if tab.active_editor:
                # If sub-editor has field-editing mode, exit that first
                if (hasattr(tab.active_editor, 'editing_fields')
                        and tab.active_editor.editing_fields):
                    tab.active_editor.editing_fields = False
                    tab.active_editor._current_fields = []
                    return
                if tab.active_editor.is_dirty:
                    tab.active_editor.save()
                tab.active_editor = None
                tab._editor_container = None
                tab._editor_kb = None

        # Sub-editor keybindings: dynamically forwarded via _DynamicEditorBindings
        class _DynamicEditorBindings:
            """Proxy that delegates to the current sub-editor's keybindings."""
            def _update_cache(self):
                pass

            @property
            def _version(self):
                kb = tab._editor_kb
                return id(kb) if kb else 0

            @property
            def bindings(self):
                kb = tab._editor_kb
                return kb.bindings if kb else []

        in_editor = Condition(lambda: tab.active_editor is not None)
        editor_proxy = _DynamicEditorBindings()
        editor_cond = ConditionalKeyBindings(editor_proxy, in_editor)

        merged = merge_key_bindings([
            nav_kb,
            ConditionalKeyBindings(selector_kb, in_selector),
            editor_cond,
        ])
        return dynamic, merged

    def _open_editor(self):
        """Open the editor for the currently selected file."""
        if not self.file_list:
            return
        fname, display = self.file_list[self.selected_index]
        data = self.session.read(fname)
        if data is None:
            return
        save_cb = self.session.make_save_callback(fname)
        self.active_editor = self.editor_factory(fname, data, save_cb)
        # Build the editor's UI
        container, kb = self.active_editor.build_ui()
        self._editor_container = container
        self._editor_kb = kb
