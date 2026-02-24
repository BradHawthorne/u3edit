"""Unified tabbed TUI editor for Ultima III game data.

Opens a disk image and provides tabbed access to all game data editors:
Maps, Combat, Special, Dialog, Text, Roster, Bestiary, Party.
"""

import os

from ..constants import MAP_DUNGEON_SIZE
from .game_session import GameSession
from .editor_tab import TileEditorTab, TextEditorTab, DialogEditorTab, DrillDownTab
from .theme import U3_STYLE


class UnifiedApp:
    """Single prompt_toolkit Application hosting all editor tabs."""

    def __init__(self, session: GameSession):
        self.session = session
        self.tabs = []
        self.active_tab_index = 0

    def _build_tabs(self):
        """Create all tabs from the game session catalog."""
        session = self.session

        # Maps tab (DrillDownTab)
        if session.has_category('maps'):
            self.tabs.append(DrillDownTab(
                'Maps', session.files_in('maps'),
                self._make_map_editor, session,
            ))

        # Combat tab (DrillDownTab)
        if session.has_category('combat'):
            self.tabs.append(DrillDownTab(
                'Combat', session.files_in('combat'),
                self._make_combat_editor, session,
            ))

        # Special tab (DrillDownTab)
        if session.has_category('special'):
            self.tabs.append(DrillDownTab(
                'Special', session.files_in('special'),
                self._make_special_editor, session,
            ))

        # Dialog tab (DrillDownTab)
        if session.has_category('dialog'):
            self.tabs.append(DrillDownTab(
                'Dialog', session.files_in('dialog'),
                self._make_dialog_editor, session,
            ))

        # Text tab (single file)
        if session.has_category('text'):
            data = session.read('TEXT')
            if data:
                from .text_editor import TextEditor
                editor = TextEditor('TEXT', data,
                                    save_callback=session.make_save_callback('TEXT'))
                self.tabs.append(TextEditorTab(editor))

        # Roster tab (single file)
        if session.has_category('roster'):
            data = session.read('ROST')
            if data:
                from .roster_editor import make_roster_tab
                tab = make_roster_tab(data, session.make_save_callback('ROST'))
                self.tabs.append(tab)

        # Bestiary tab (DrillDownTab)
        if session.has_category('bestiary'):
            self.tabs.append(DrillDownTab(
                'Bestiary', session.files_in('bestiary'),
                self._make_bestiary_editor, session,
            ))

        # Party tab (single file)
        if session.has_category('party'):
            data = session.read('PRTY')
            if data:
                from .party_editor import make_party_tab
                tab = make_party_tab(data, session.make_save_callback('PRTY'))
                self.tabs.append(tab)

        # EXOD tab (title screen sub-editors)
        if session.has_category('exod'):
            self.tabs.append(DrillDownTab(
                'EXOD', session.files_in('exod'),
                self._make_exod_editor, session,
            ))

    def _make_map_editor(self, fname, data, save_cb):
        """Factory for MapEditor wrapped as a tab."""
        from .map_editor import MapEditor
        is_dungeon = len(data) <= MAP_DUNGEON_SIZE
        editor = MapEditor(fname, data, is_dungeon, save_callback=save_cb)
        return TileEditorTab(editor)

    def _make_combat_editor(self, fname, data, save_cb):
        """Factory for CombatEditor wrapped as a tab."""
        from .combat_editor import CombatEditor
        editor = CombatEditor(fname, data, save_callback=save_cb)
        return TileEditorTab(editor)

    def _make_special_editor(self, fname, data, save_cb):
        """Factory for SpecialEditor wrapped as a tab."""
        from .special_editor import SpecialEditor
        editor = SpecialEditor(fname, data, save_callback=save_cb)
        return TileEditorTab(editor)

    def _make_dialog_editor(self, fname, data, save_cb):
        """Factory for DialogEditor wrapped as a tab."""
        from .dialog_editor import DialogEditor
        editor = DialogEditor(fname, data, save_callback=save_cb)
        return DialogEditorTab(editor)

    def _make_bestiary_editor(self, fname, data, save_cb):
        """Factory for BestiaryEditor wrapped as a tab."""
        letter = fname[-1] if fname.startswith('MON') else '?'
        from .bestiary_editor import make_bestiary_tab
        return make_bestiary_tab(data, letter, save_cb)

    def _make_exod_editor(self, fname, data, save_cb):
        """Factory for EXOD sub-editors (crawl, glyphs, frames).

        fname is 'EXOD:crawl', 'EXOD:glyphs', or 'EXOD:frames'.
        All read from the same EXOD binary via session.
        """
        exod_data = self.session.read('EXOD')
        if exod_data is None:
            return None
        sub = fname.split(':')[1] if ':' in fname else fname
        if sub == 'crawl':
            from .exod_editor import ExodCrawlEditor
            return ExodCrawlEditor(exod_data,
                                   save_callback=self.session.make_save_callback('EXOD'))
        elif sub == 'glyphs':
            from .exod_editor import ExodGlyphViewer
            return ExodGlyphViewer(exod_data)
        elif sub == 'frames':
            from .exod_editor import ExodFrameViewer
            return ExodFrameViewer(exod_data)
        return None

    def run(self):  # pragma: no cover
        """Run the unified tabbed editor."""
        from prompt_toolkit import Application
        from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
        from prompt_toolkit.layout.containers import DynamicContainer
        from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings, \
            ConditionalKeyBindings
        from prompt_toolkit.filters import Condition

        self._build_tabs()
        if not self.tabs:
            print("No game data files found on disk image.")
            return False

        # Build UI for each tab (skip tabs that fail to build)
        tab_containers = []
        tab_keybindings = []
        valid_tabs = []
        for tab in self.tabs:
            try:
                container, kb = tab.build_ui()
                tab_containers.append(container)
                tab_keybindings.append(kb)
                valid_tabs.append(tab)
            except Exception as e:
                import sys
                print(f"Warning: tab '{tab.name}' failed to build: {e}",
                      file=sys.stderr)
        self.tabs = valid_tabs
        if not self.tabs:
            print("No game data files found on disk image.")
            return False

        app_ref = self

        # Tab bar
        def get_tab_bar():
            fragments = [('class:tab-bar', ' ')]
            for i, tab in enumerate(app_ref.tabs):
                dirty = '*' if tab.is_dirty else ''
                if i == app_ref.active_tab_index:
                    style = 'class:tab-active'
                else:
                    style = 'class:tab-inactive'
                fragments.append((style, f' {i + 1}:{tab.name}{dirty} '))
                fragments.append(('class:tab-bar', ' '))
            return fragments

        tab_bar = Window(content=FormattedTextControl(get_tab_bar), height=1)

        # Dynamic content
        def get_content():
            return tab_containers[app_ref.active_tab_index]
        content = DynamicContainer(get_content)

        # Global status
        def get_global_status():
            img = os.path.basename(app_ref.session.image_path)
            dirty_count = sum(1 for t in app_ref.tabs if t.is_dirty)
            dirty_text = f' ({dirty_count} modified)' if dirty_count else ''
            return [
                ('class:status', f' ult3edit: {img}'),
                ('class:status-dirty' if dirty_count else 'class:status', dirty_text),
                ('class:status', f' | Tab {app_ref.active_tab_index + 1}/{len(app_ref.tabs)}'),
            ]

        # Global help
        def get_global_help():
            return [
                ('class:help-key', ' F5/F6 '), ('class:help-text', '=prev/next tab '),
                ('class:help-key', 'Ctrl+S'), ('class:help-text', '=save '),
                ('class:help-key', 'Ctrl+Q'), ('class:help-text', '=quit '),
            ]

        status_bar = Window(content=FormattedTextControl(get_global_status),
                            height=1)
        help_bar = Window(content=FormattedTextControl(get_global_help), height=1)

        root = HSplit([tab_bar, content, status_bar, help_bar])

        # Global keybindings
        global_kb = KeyBindings()

        @global_kb.add('c-right')
        @global_kb.add('s-tab', eager=True)
        @global_kb.add('f6')
        def _next_tab(event):
            app_ref.active_tab_index = (
                (app_ref.active_tab_index + 1) % len(app_ref.tabs))

        @global_kb.add('c-left')
        @global_kb.add('f5')
        def _prev_tab(event):
            app_ref.active_tab_index = (
                (app_ref.active_tab_index - 1) % len(app_ref.tabs))

        @global_kb.add('c-s')
        def _save_current(event):
            app_ref.tabs[app_ref.active_tab_index].save()

        @global_kb.add('c-q')
        def _quit(event):
            import sys
            for tab in app_ref.tabs:
                if tab.is_dirty:
                    try:
                        tab.save()
                    except Exception as e:
                        print(f'Warning: failed to save {tab.name}: {e}',
                              file=sys.stderr)
            event.app.exit(result=True)

        # Per-tab keybindings (conditional)
        conditional_kbs = []
        for i, kb in enumerate(tab_keybindings):
            if kb:
                cond = Condition(lambda idx=i: app_ref.active_tab_index == idx)
                conditional_kbs.append(ConditionalKeyBindings(kb, cond))

        all_kb = merge_key_bindings([global_kb] + conditional_kbs)

        app = Application(
            layout=Layout(root),
            key_bindings=all_kb,
            style=U3_STYLE,
            full_screen=True,
            mouse_support=False,
        )
        return app.run()
