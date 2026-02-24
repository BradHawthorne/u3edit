"""Tests for TUI pure logic methods (no prompt_toolkit required)."""


from ult3edit.constants import (
    CON_FILE_SIZE, CON_MONSTER_X_OFFSET, CON_MONSTER_Y_OFFSET, CON_PC_X_OFFSET, CON_PC_Y_OFFSET, CHAR_RECORD_SIZE, CHAR_MAX_SLOTS, TLK_RECORD_END,
)
from ult3edit.tui.base import EditorState, BaseTileEditor
from ult3edit.tui.combat_editor import CombatEditor
from ult3edit.tui.map_editor import MapEditor
from ult3edit.tui.special_editor import SpecialEditor
from ult3edit.tui.dialog_editor import DialogEditor
from ult3edit.tui.text_editor import TextEditor, parse_text_records, rebuild_text_data
from ult3edit.tui.exod_editor import (
    ExodCrawlEditor, ExodGlyphViewer, ExodFrameViewer,
    make_exod_crawl_editor, make_exod_glyph_viewer, make_exod_frame_viewer,
)
from ult3edit.tui.form_editor import FormEditorTab
from ult3edit.tui.roster_editor import _character_label
from ult3edit.tui.bestiary_editor import _monster_label, _byte_clamp
from ult3edit.tui.editor_tab import TileEditorTab, TextEditorTab, DialogEditorTab, DrillDownTab


# ---- BaseTileEditor pure logic ----

class TestBaseTileEditorPureLogic:
    """Test BaseTileEditor methods that don't require prompt_toolkit."""

    def test_save_with_callback(self):
        data = bytearray(64)
        data[0] = 0x04
        state = EditorState(data=data, width=8, height=8)
        state.dirty = True
        saved = []
        editor = BaseTileEditor(state, 'test.map', save_callback=lambda d: saved.append(d))
        editor._save()
        assert len(saved) == 1
        assert saved[0][0] == 0x04
        assert not state.dirty

    def test_save_to_file(self, tmp_path):
        data = bytearray(64)
        data[5] = 0x10
        state = EditorState(data=data, width=8, height=8)
        state.dirty = True
        fpath = str(tmp_path / 'test.map')
        editor = BaseTileEditor(state, fpath)
        editor._save()
        assert not state.dirty
        assert (tmp_path / 'test.map').read_bytes()[5] == 0x10

    def test_extra_status_returns_empty(self):
        state = EditorState(data=bytearray(64), width=8, height=8)
        editor = BaseTileEditor(state, 'test')
        assert editor._extra_status() == ''

    def test_render_cell(self):
        state = EditorState(data=bytearray(64), width=8, height=8)
        editor = BaseTileEditor(state, 'test')
        style, ch = editor._render_cell(0, 0, 0x04)
        assert isinstance(style, str)
        assert isinstance(ch, str)

    def test_extra_keybindings_noop(self):
        state = EditorState(data=bytearray(64), width=8, height=8)
        editor = BaseTileEditor(state, 'test')
        editor._extra_keybindings(None)  # Should not raise


# ---- CombatEditor pure logic ----

class TestCombatEditorPureLogic:
    """Test CombatEditor methods that don't require prompt_toolkit."""

    def _make_editor(self):
        data = bytearray(CON_FILE_SIZE)
        # Set monster 0 at (3, 4)
        data[CON_MONSTER_X_OFFSET] = 3
        data[CON_MONSTER_Y_OFFSET] = 4
        # Set PC 0 at (5, 6)
        data[CON_PC_X_OFFSET] = 5
        data[CON_PC_Y_OFFSET] = 6
        saved = []
        editor = CombatEditor('test.con', bytes(data), save_callback=lambda d: saved.append(d))
        return editor, saved

    def test_render_cell_monster_overlay(self):
        editor, _ = self._make_editor()
        style, ch = editor._render_cell(3, 4, 0x00)
        assert style == 'class:overlay-monster'
        assert ch == '0'

    def test_render_cell_pc_overlay(self):
        editor, _ = self._make_editor()
        style, ch = editor._render_cell(5, 6, 0x00)
        assert style == 'class:overlay-pc'
        assert ch == '1'

    def test_render_cell_tile(self):
        editor, _ = self._make_editor()
        style, ch = editor._render_cell(1, 1, 0x04)
        assert 'class:' in style
        assert ch  # non-empty char

    def test_extra_status_paint_mode(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'paint'
        assert 'PAINT' in editor._extra_status()

    def test_extra_status_monster_mode(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'monster'
        status = editor._extra_status()
        assert 'MONSTER' in status
        assert 'slot' in status

    def test_extra_status_pc_mode(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'pc'
        assert 'PC' in editor._extra_status()

    def test_place_at_cursor_monster(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'monster'
        editor.placement_slot = 2
        editor.state.cursor_x = 7
        editor.state.cursor_y = 8
        editor._place_at_cursor()
        assert editor.monster_x[2] == 7
        assert editor.monster_y[2] == 8
        assert editor.state.dirty
        assert editor.placement_slot == 3  # auto-advance

    def test_place_at_cursor_pc(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'pc'
        editor.placement_slot = 1
        editor.state.cursor_x = 9
        editor.state.cursor_y = 10
        editor._place_at_cursor()
        assert editor.pc_x[1] == 9
        assert editor.pc_y[1] == 10
        assert editor.state.dirty

    def test_place_at_cursor_paint(self):
        editor, _ = self._make_editor()
        editor.state.mode = 'paint'
        editor.state.selected_tile = 0x20
        editor.state.cursor_x = 0
        editor.state.cursor_y = 0
        editor._place_at_cursor()
        assert editor.state.tile_at(0, 0) == 0x20

    def test_save_callback(self):
        editor, saved = self._make_editor()
        editor.state.set_tile(0, 0, 0x20)
        editor._save()
        assert len(saved) == 1
        assert len(saved[0]) == CON_FILE_SIZE
        assert saved[0][0] == 0x20
        assert not editor.state.dirty

    def test_short_data_pads(self):
        """CombatEditor pads short data to CON_FILE_SIZE."""
        editor = CombatEditor('test.con', bytes(10))
        assert len(editor.full_data) == CON_FILE_SIZE


# ---- MapEditor pure logic ----

class TestMapEditorPureLogic:
    """Test MapEditor methods that don't require prompt_toolkit."""

    def test_overworld_extra_status(self):
        data = bytearray(4096)  # 64x64
        editor = MapEditor('test.map', bytes(data))
        status = editor._extra_status()
        assert '64x64' in status

    def test_dungeon_extra_status(self):
        data = bytearray(2048)  # 8 levels of 16x16
        editor = MapEditor('test.map', bytes(data), is_dungeon=True)
        status = editor._extra_status()
        assert 'Level 1/8' in status

    def test_switch_level(self):
        data = bytearray(2048)
        data[0] = 0xAA  # Level 0, first tile
        data[256] = 0xBB  # Level 1, first tile
        editor = MapEditor('test.map', bytes(data), is_dungeon=True)
        assert editor.state.data[0] == 0xAA
        editor.switch_level(1)
        assert editor.current_level == 1
        assert editor.state.data[0] == 0xBB

    def test_switch_level_out_of_range(self):
        data = bytearray(2048)
        editor = MapEditor('test.map', bytes(data), is_dungeon=True)
        editor.switch_level(99)  # Should be ignored
        assert editor.current_level == 0

    def test_save_overworld_callback(self):
        data = bytearray(4096)
        saved = []
        editor = MapEditor('test.map', bytes(data), save_callback=lambda d: saved.append(d))
        editor.state.set_tile(0, 0, 0x04)
        editor._save()
        assert len(saved) == 1
        assert saved[0][0] == 0x04

    def test_save_dungeon_merges_level(self):
        data = bytearray(2048)
        saved = []
        editor = MapEditor('test.map', bytes(data), is_dungeon=True,
                           save_callback=lambda d: saved.append(d))
        editor.state.set_tile(0, 0, 0x01)
        editor._save()
        assert len(saved) == 1
        assert saved[0][0] == 0x01
        assert len(saved[0]) == 2048

    def test_save_to_file(self, tmp_path):
        fpath = str(tmp_path / 'test.map')
        data = bytearray(4096)
        editor = MapEditor(fpath, bytes(data))
        editor.state.set_tile(0, 0, 0x10)
        editor._save()
        assert (tmp_path / 'test.map').read_bytes()[0] == 0x10


# ---- SpecialEditor pure logic ----

class TestSpecialEditorPureLogic:

    def test_save_to_file(self, tmp_path):
        fpath = str(tmp_path / 'BRND')
        data = bytearray(128)
        editor = SpecialEditor(fpath, bytes(data))
        editor.state.set_tile(0, 0, 0x20)
        editor._save()
        result = (tmp_path / 'BRND').read_bytes()
        assert result[0] == 0x20


# ---- DialogEditor pure logic ----

class TestDialogEditorPureLogic:

    def _make_tlk_data(self):
        """Build minimal TLK data with 2 text records."""
        from ult3edit.fileutil import encode_high_ascii
        rec1 = encode_high_ascii('HELLO', 5) + bytes([0xFF]) + encode_high_ascii('WORLD', 5)
        rec2 = encode_high_ascii('TEST', 4)
        return rec1 + bytes([TLK_RECORD_END]) + rec2 + bytes([TLK_RECORD_END])

    def test_init_parses_records(self):
        data = self._make_tlk_data()
        editor = DialogEditor('test.tlk', data)
        assert len(editor.records) >= 1

    def test_save_with_callback(self):
        data = self._make_tlk_data()
        saved = []
        editor = DialogEditor('test.tlk', data, save_callback=lambda d: saved.append(d))
        editor._modified_records.add(0)
        editor.dirty = True
        editor._save()
        assert len(saved) == 1
        assert not editor.dirty

    def test_save_to_file(self, tmp_path):
        data = self._make_tlk_data()
        fpath = str(tmp_path / 'TLKA')
        editor = DialogEditor(fpath, data)
        editor._save()
        assert (tmp_path / 'TLKA').exists()


# ---- TextEditor pure logic ----

class TestTextEditorPureLogic:

    def _make_text_data(self):
        """Build minimal TEXT data with high-ASCII strings."""
        from ult3edit.fileutil import encode_high_ascii
        s1 = encode_high_ascii('HELLO', 5) + b'\x00'
        s2 = encode_high_ascii('WORLD', 5) + b'\x00'
        return s1 + s2

    def test_parse_text_records(self):
        data = self._make_text_data()
        records = parse_text_records(data)
        assert len(records) == 2
        assert records[0].text == 'HELLO'
        assert records[1].text == 'WORLD'

    def test_rebuild_text_data(self):
        data = self._make_text_data()
        records = parse_text_records(data)
        rebuilt = rebuild_text_data(records, len(data))
        assert len(rebuilt) == len(data)
        # Re-parse should get same records
        re_parsed = parse_text_records(bytes(rebuilt))
        assert len(re_parsed) == 2

    def test_text_editor_init(self):
        data = self._make_text_data()
        editor = TextEditor('test.txt', data)
        assert len(editor.records) == 2
        assert not editor.dirty

    def test_text_editor_save_callback(self):
        data = self._make_text_data()
        saved = []
        editor = TextEditor('test.txt', data, save_callback=lambda d: saved.append(d))
        editor.records[0].text = 'THERE'
        editor.dirty = True
        editor._save()
        assert len(saved) == 1
        assert not editor.dirty

    def test_text_editor_save_to_file(self, tmp_path):
        data = self._make_text_data()
        fpath = str(tmp_path / 'TEXT')
        editor = TextEditor(fpath, data)
        editor._save()
        assert (tmp_path / 'TEXT').exists()


# ---- ExodEditor pure logic ----

class TestExodEditorPureLogic:

    def _make_exod_data(self):
        """Build minimal EXOD data (26208 bytes)."""
        return bytearray(26208)

    def test_crawl_editor_init(self):
        data = self._make_exod_data()
        editor = ExodCrawlEditor(data)
        assert editor.name == 'Crawl'
        assert not editor.is_dirty

    def test_crawl_editor_save(self):
        data = self._make_exod_data()
        saved = []
        editor = ExodCrawlEditor(data, save_callback=lambda d: saved.append(d))
        editor.coords = [(140, 132), (100, 100)]
        editor.dirty = True
        editor.save()
        assert len(saved) == 1
        assert not editor.dirty

    def test_glyph_viewer_properties(self):
        data = self._make_exod_data()
        viewer = ExodGlyphViewer(data)
        assert viewer.name == 'Glyphs'
        assert not viewer.is_dirty
        viewer.save()  # no-op

    def test_frame_viewer_properties(self):
        data = self._make_exod_data()
        viewer = ExodFrameViewer(data)
        assert viewer.name == 'Frames'
        assert not viewer.is_dirty
        viewer.save()  # no-op

    def test_factory_crawl_editor(self):
        data = self._make_exod_data()
        editor = make_exod_crawl_editor(data, save_callback=lambda d: None)
        assert isinstance(editor, ExodCrawlEditor)

    def test_factory_glyph_viewer(self):
        data = self._make_exod_data()
        viewer = make_exod_glyph_viewer(data)
        assert isinstance(viewer, ExodGlyphViewer)

    def test_factory_frame_viewer(self):
        data = self._make_exod_data()
        viewer = make_exod_frame_viewer(data)
        assert isinstance(viewer, ExodFrameViewer)


# ---- FormEditorTab pure logic ----

class TestFormEditorTabPureLogic:

    def test_properties(self):
        tab = FormEditorTab(
            tab_name='Test',
            records=['a', 'b'],
            record_label_fn=lambda r, i: f'{i}: {r}',
            field_factory=lambda r: [],
            save_callback=lambda d: None,
            get_save_data=lambda: b'data',
        )
        assert tab.name == 'Test'
        assert not tab.is_dirty
        tab.dirty = True
        assert tab.is_dirty

    def test_save(self):
        saved = []
        tab = FormEditorTab(
            tab_name='Test',
            records=[],
            record_label_fn=lambda r, i: '',
            field_factory=lambda r: [],
            save_callback=lambda d: saved.append(d),
            get_save_data=lambda: b'testdata',
        )
        tab.dirty = True
        tab.save()
        assert saved == [b'testdata']
        assert not tab.dirty


# ---- Editor tab wrappers ----

class TestEditorTabWrappers:

    def test_tile_editor_tab(self):
        data = bytearray(64)
        state = EditorState(data=data, width=8, height=8)
        editor = BaseTileEditor(state, 'test')
        tab = TileEditorTab(editor)
        assert tab.name == 'Tile Editor'
        assert not tab.is_dirty
        state.dirty = True
        assert tab.is_dirty

    def test_tile_editor_tab_save(self):
        data = bytearray(64)
        state = EditorState(data=data, width=8, height=8)
        saved = []
        editor = BaseTileEditor(state, 'test', save_callback=lambda d: saved.append(d))
        tab = TileEditorTab(editor)
        state.dirty = True
        tab.save()
        assert len(saved) == 1

    def test_text_editor_tab(self):
        from ult3edit.fileutil import encode_high_ascii
        data = encode_high_ascii('TEST', 4) + b'\x00'
        text_editor = TextEditor('test', data)
        tab = TextEditorTab(text_editor)
        assert tab.name == 'Text'
        assert not tab.is_dirty

    def test_text_editor_tab_save(self):
        from ult3edit.fileutil import encode_high_ascii
        data = encode_high_ascii('TEST', 4) + b'\x00'
        saved = []
        text_editor = TextEditor('test', data, save_callback=lambda d: saved.append(d))
        tab = TextEditorTab(text_editor)
        text_editor.dirty = True
        tab.save()
        assert len(saved) == 1

    def test_dialog_editor_tab(self):
        from ult3edit.fileutil import encode_high_ascii
        data = encode_high_ascii('HI', 2) + bytes([TLK_RECORD_END])
        dialog_editor = DialogEditor('test', data)
        tab = DialogEditorTab(dialog_editor)
        assert tab.name == 'Dialog'
        assert not tab.is_dirty

    def test_dialog_editor_tab_save(self):
        from ult3edit.fileutil import encode_high_ascii
        data = encode_high_ascii('HI', 2) + bytes([TLK_RECORD_END])
        saved = []
        dialog_editor = DialogEditor('test', data, save_callback=lambda d: saved.append(d))
        tab = DialogEditorTab(dialog_editor)
        dialog_editor.dirty = True
        tab.save()
        assert len(saved) == 1


# ---- DrillDownTab pure logic ----

class TestDrillDownTabPureLogic:

    def test_properties_no_editor(self):
        tab = DrillDownTab('Test', [('FILE', 'Display')], lambda f, d, s: None, None)
        assert tab.name == 'Test'
        assert not tab.is_dirty

    def test_save_no_editor(self):
        tab = DrillDownTab('Test', [], lambda f, d, s: None, None)
        tab.save()  # no-op, no active editor

    def test_open_editor_empty_list(self):
        tab = DrillDownTab('Test', [], lambda f, d, s: None, None)
        tab._open_editor()
        assert tab.active_editor is None


# ---- Roster editor label ----

class TestRosterEditorLabel:

    def test_character_label_non_empty(self):
        from ult3edit.roster import Character
        raw = bytearray(CHAR_RECORD_SIZE)
        # Write a name in high-ASCII
        from ult3edit.fileutil import encode_high_ascii
        name_bytes = encode_high_ascii('HERO', 10)
        raw[0:10] = name_bytes
        raw[0x16] = 0  # Human
        raw[0x17] = 0  # Fighter
        char = Character(raw)
        label = _character_label(char, 0)
        assert 'HERO' in label
        assert '[' in label

    def test_character_label_empty(self):
        from ult3edit.roster import Character
        raw = bytearray(CHAR_RECORD_SIZE)
        char = Character(raw)
        label = _character_label(char, 5)
        assert 'empty' in label


# ---- Bestiary editor label ----

class TestBestiaryEditorLabel:

    def test_monster_label_non_empty(self):
        from ult3edit.bestiary import Monster
        attrs = [0x60, 0x64, 0x00, 0x00, 10, 5, 3, 2, 0, 0]
        mon = Monster(attrs, 0, 'A')
        label = _monster_label(mon, 0)
        assert 'HP:' in label

    def test_monster_label_empty(self):
        from ult3edit.bestiary import Monster
        attrs = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        mon = Monster(attrs, 0, 'A')
        label = _monster_label(mon, 3)
        assert 'empty' in label

    def test_byte_clamp_hex(self):
        assert _byte_clamp('0xFF') == 255
        assert _byte_clamp('$FF') == 255
        assert _byte_clamp('256') == 255
        assert _byte_clamp('-1') == 0
        assert _byte_clamp('100') == 100


# ---- UnifiedApp factory methods ----

class TestUnifiedAppFactories:

    def test_make_map_editor_overworld(self):
        from ult3edit.tui.app import UnifiedApp
        app = UnifiedApp.__new__(UnifiedApp)
        data = bytearray(4096)
        saved = []
        tab = app._make_map_editor('MAPA', bytes(data), lambda d: saved.append(d))
        assert isinstance(tab, TileEditorTab)
        assert tab.name == 'Map Editor'

    def test_make_map_editor_dungeon(self):
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.constants import MAP_DUNGEON_SIZE
        app = UnifiedApp.__new__(UnifiedApp)
        data = bytearray(MAP_DUNGEON_SIZE)
        tab = app._make_map_editor('MAPD', bytes(data), lambda d: None)
        assert isinstance(tab, TileEditorTab)

    def test_make_combat_editor(self):
        from ult3edit.tui.app import UnifiedApp
        app = UnifiedApp.__new__(UnifiedApp)
        data = bytearray(CON_FILE_SIZE)
        tab = app._make_combat_editor('CONA', bytes(data), lambda d: None)
        assert isinstance(tab, TileEditorTab)

    def test_make_special_editor(self):
        from ult3edit.tui.app import UnifiedApp
        app = UnifiedApp.__new__(UnifiedApp)
        data = bytearray(128)
        tab = app._make_special_editor('BRND', bytes(data), lambda d: None)
        assert isinstance(tab, TileEditorTab)

    def test_make_dialog_editor(self):
        from ult3edit.tui.app import UnifiedApp
        from ult3edit.fileutil import encode_high_ascii
        app = UnifiedApp.__new__(UnifiedApp)
        data = encode_high_ascii('HI', 2) + bytes([TLK_RECORD_END])
        tab = app._make_dialog_editor('TLKA', data, lambda d: None)
        assert isinstance(tab, DialogEditorTab)

    def test_make_bestiary_editor(self):
        from ult3edit.tui.app import UnifiedApp
        app = UnifiedApp.__new__(UnifiedApp)
        data = bytearray(256)
        tab = app._make_bestiary_editor('MONA', bytes(data), lambda d: None)
        assert tab is not None
        assert isinstance(tab, FormEditorTab)

    def test_make_exod_editor_crawl(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return bytearray(26208)
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('EXOD:crawl', bytearray(26208), lambda d: None)
        assert isinstance(tab, ExodCrawlEditor)

    def test_make_exod_editor_glyphs(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return bytearray(26208)
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('EXOD:glyphs', bytearray(26208), lambda d: None)
        assert isinstance(tab, ExodGlyphViewer)

    def test_make_exod_editor_frames(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return bytearray(26208)
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('EXOD:frames', bytearray(26208), lambda d: None)
        assert isinstance(tab, ExodFrameViewer)

    def test_make_exod_editor_none_data(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return None
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('EXOD:crawl', bytearray(26208), lambda d: None)
        assert tab is None

    def test_make_exod_editor_unknown_sub(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def read(self, name):
                return bytearray(26208)
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp.__new__(UnifiedApp)
        app.session = MockSession()
        tab = app._make_exod_editor('EXOD:unknown', bytearray(26208), lambda d: None)
        assert tab is None

    def test_build_tabs(self):
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            def has_category(self, cat):
                return cat == 'party'
            def files_in(self, cat):
                return []
            def read(self, name):
                return bytearray(16)  # PRTY size
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp(MockSession())
        app._build_tabs()
        assert len(app.tabs) >= 1  # At least the Party tab


# =============================================================================
# Coverage: app.py _build_tabs with multiple categories (lines 29, 36, 43,
# 50, 57-62, 66-70, 74, 89), editor_tab.py _open_editor None data (line 241)
# =============================================================================


class TestUnifiedAppBuildTabsMulti:
    """Cover app.py _build_tabs with maps, combat, special, dialog, text,
    roster, bestiary, exod categories."""

    def _make_mock_session(self, categories):
        """Create a mock session with specified categories."""
        from ult3edit.fileutil import encode_high_ascii
        from ult3edit.constants import CON_FILE_SIZE, CHAR_RECORD_SIZE

        file_data = {}
        catalog = {}

        if 'maps' in categories:
            catalog['maps'] = [('MAPA', 'Sosaria')]
            file_data['MAPA'] = bytearray(4096)

        if 'combat' in categories:
            catalog['combat'] = [('CONA', 'Combat A')]
            file_data['CONA'] = bytearray(CON_FILE_SIZE)

        if 'special' in categories:
            catalog['special'] = [('BRND', 'Brand')]
            file_data['BRND'] = bytearray(128)

        if 'dialog' in categories:
            catalog['dialog'] = [('TLKA', 'Dialog A')]
            file_data['TLKA'] = encode_high_ascii('HI', 2) + bytes([TLK_RECORD_END])

        if 'text' in categories:
            catalog['text'] = [('TEXT', 'Game Text')]
            file_data['TEXT'] = encode_high_ascii('TEST', 4) + b'\x00'

        if 'roster' in categories:
            catalog['roster'] = [('ROST', 'Roster')]
            file_data['ROST'] = bytearray(CHAR_RECORD_SIZE * CHAR_MAX_SLOTS)

        if 'bestiary' in categories:
            catalog['bestiary'] = [('MONA', 'Monsters A')]
            file_data['MONA'] = bytearray(256)

        if 'exod' in categories:
            catalog['exod'] = [
                ('EXOD:crawl', 'Text Crawl'),
                ('EXOD:glyphs', 'Glyph Table'),
                ('EXOD:frames', 'HGR Frames'),
            ]
            file_data['EXOD'] = bytearray(26208)

        class MockSession:
            image_path = 'test.po'
            def has_category(self, cat):
                return cat in catalog
            def files_in(self, cat):
                return catalog.get(cat, [])
            def read(self, name):
                base = name.split(':')[0] if ':' in name else name
                return file_data.get(base)
            def make_save_callback(self, name):
                return lambda d: None

        return MockSession()

    def test_build_tabs_maps(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['maps'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Maps' for t in app.tabs)

    def test_build_tabs_combat(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['combat'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Combat' for t in app.tabs)

    def test_build_tabs_special(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['special'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Special' for t in app.tabs)

    def test_build_tabs_dialog(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['dialog'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Dialog' for t in app.tabs)

    def test_build_tabs_text(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['text'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Text' for t in app.tabs)

    def test_build_tabs_roster(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['roster'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert len(app.tabs) >= 1

    def test_build_tabs_bestiary(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['bestiary'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'Bestiary' for t in app.tabs)

    def test_build_tabs_exod(self):
        from ult3edit.tui.app import UnifiedApp
        session = self._make_mock_session(['exod'])
        app = UnifiedApp(session)
        app._build_tabs()
        assert any(t.name == 'EXOD' for t in app.tabs)

    def test_build_tabs_text_none_data(self):
        """Text category where read returns None should not add tab."""
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            image_path = 'test.po'
            def has_category(self, cat):
                return cat == 'text'
            def files_in(self, cat):
                return [('TEXT', 'Game Text')] if cat == 'text' else []
            def read(self, name):
                return None
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp(MockSession())
        app._build_tabs()
        assert not any(t.name == 'Text' for t in app.tabs)

    def test_build_tabs_roster_none_data(self):
        """Roster category where read returns None should not add tab."""
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            image_path = 'test.po'
            def has_category(self, cat):
                return cat == 'roster'
            def files_in(self, cat):
                return [('ROST', 'Roster')] if cat == 'roster' else []
            def read(self, name):
                return None
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp(MockSession())
        app._build_tabs()
        assert len(app.tabs) == 0

    def test_build_tabs_party_none_data(self):
        """Party category where read returns None should not add tab."""
        from ult3edit.tui.app import UnifiedApp

        class MockSession:
            image_path = 'test.po'
            def has_category(self, cat):
                return cat == 'party'
            def files_in(self, cat):
                return [('PRTY', 'Party State')] if cat == 'party' else []
            def read(self, name):
                return None
            def make_save_callback(self, name):
                return lambda d: None

        app = UnifiedApp(MockSession())
        app._build_tabs()
        assert len(app.tabs) == 0


class TestDrillDownTabOpenEditorNoneData:
    """Cover editor_tab.py line 241: _open_editor returns early when
    session.read returns None."""

    def test_open_editor_none_data(self):
        class MockSession:
            def read(self, name):
                return None
            def make_save_callback(self, name):
                return lambda d: None

        tab = DrillDownTab('Test', [('MISSING', 'Missing File')],
                           lambda f, d, s: None, MockSession())
        tab._open_editor()
        assert tab.active_editor is None
