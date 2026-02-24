"""Tests for EditorTab, DrillDownTab state management."""


from ult3edit.tui.editor_tab import TileEditorTab, DrillDownTab
from ult3edit.tui.base import EditorState, BaseTileEditor


class TestTileEditorTab:
    def test_name(self):
        state = EditorState(data=bytearray(256), width=16, height=16)
        editor = BaseTileEditor(state, '/tmp/test', title='Test Editor')
        tab = TileEditorTab(editor)
        assert tab.name == 'Test Editor'

    def test_dirty_tracking(self):
        state = EditorState(data=bytearray(256), width=16, height=16)
        editor = BaseTileEditor(state, '/tmp/test')
        tab = TileEditorTab(editor)
        assert not tab.is_dirty
        state.dirty = True
        assert tab.is_dirty

    def test_save_clears_dirty(self):
        state = EditorState(data=bytearray(256), width=16, height=16)
        saved = []
        editor = BaseTileEditor(state, '/tmp/test',
                                save_callback=lambda d: saved.append(d))
        tab = TileEditorTab(editor)
        state.dirty = True
        tab.save()
        assert not tab.is_dirty
        assert len(saved) == 1


class MockEditor:
    """Mock editor for DrillDownTab tests."""

    def __init__(self):
        self._dirty = False
        self._saved = False

    @property
    def is_dirty(self):
        return self._dirty

    def build_ui(self):
        from prompt_toolkit.layout import Window
        from prompt_toolkit.key_binding import KeyBindings
        return Window(), KeyBindings()

    def save(self):
        self._saved = True
        self._dirty = False


class TestDrillDownTab:
    def _make_tab(self, file_list=None):
        if file_list is None:
            file_list = [('MAPA', 'Sosaria'), ('MAPB', 'LB Castle')]

        class MockSession:
            def read(self, name):
                return bytes(256)

            def make_save_callback(self, name):
                def cb(data):
                    pass
                return cb

        def factory(fname, data, save_cb):
            return MockEditor()

        return DrillDownTab('Maps', file_list, factory, MockSession())

    def test_initial_state(self):
        tab = self._make_tab()
        assert tab.name == 'Maps'
        assert tab.active_editor is None
        assert tab.selected_index == 0
        assert not tab.is_dirty

    def test_selector_navigation(self):
        tab = self._make_tab()
        tab.selected_index = 0
        tab.selected_index = min(len(tab.file_list) - 1, tab.selected_index + 1)
        assert tab.selected_index == 1

    def test_open_editor(self):
        tab = self._make_tab()
        tab._open_editor()
        assert tab.active_editor is not None

    def test_close_editor(self):
        tab = self._make_tab()
        tab._open_editor()
        assert tab.active_editor is not None
        tab.active_editor = None
        tab._editor_container = None
        assert tab.active_editor is None

    def test_dirty_from_editor(self):
        tab = self._make_tab()
        tab._open_editor()
        assert not tab.is_dirty
        tab.active_editor._dirty = True
        assert tab.is_dirty

    def test_empty_file_list(self):
        tab = self._make_tab(file_list=[])
        assert not tab.is_dirty
        tab._open_editor()  # Should be a no-op
        assert tab.active_editor is None

    def test_save_propagates_to_editor(self):
        tab = self._make_tab()
        tab._open_editor()
        tab.active_editor._dirty = True
        tab.save()
        assert tab.active_editor._saved
        assert not tab.active_editor._dirty

    def test_save_noop_without_editor(self):
        tab = self._make_tab()
        tab.save()  # Should not crash

    def test_is_dirty_false_in_selector(self):
        """is_dirty should be False when no editor is open."""
        tab = self._make_tab()
        assert not tab.is_dirty
