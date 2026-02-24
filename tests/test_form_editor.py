"""Tests for FormEditorTab, RosterEditor, BestiaryEditor, PartyEditor, DialogEditor."""


from ult3edit.tui.form_editor import FormField, FormEditorTab


class TestFormField:
    def test_getter_setter(self):
        val = [42]
        field = FormField('Test', lambda: val[0], lambda v: val.__setitem__(0, int(v)))
        assert field.getter() == 42
        field.setter('99')
        assert val[0] == 99

    def test_label(self):
        field = FormField('My Field', lambda: 'x', lambda v: None)
        assert field.label == 'My Field'

    def test_fmt_default(self):
        field = FormField('F', lambda: 0, lambda v: None)
        assert field.fmt == 'str'

    def test_fmt_int(self):
        field = FormField('F', lambda: 0, lambda v: None, fmt='int')
        assert field.fmt == 'int'


class TestFormEditorTab:
    def _make_tab(self, records=None):
        if records is None:
            records = [{'name': 'Alice', 'hp': 100}, {'name': 'Bob', 'hp': 50}]

        def label_fn(rec, i):
            return f'[{i}] {rec["name"]} HP:{rec["hp"]}'

        def field_factory(rec):
            return [
                FormField('Name', lambda: rec['name'],
                          lambda v: rec.__setitem__('name', v)),
                FormField('HP', lambda: rec['hp'],
                          lambda v: rec.__setitem__('hp', int(v)), fmt='int'),
            ]

        saved = []
        return FormEditorTab(
            tab_name='Test',
            records=records,
            record_label_fn=label_fn,
            field_factory=field_factory,
            save_callback=lambda d: saved.append(d),
            get_save_data=lambda: b'saved',
        ), saved

    def test_initial_state(self):
        tab, _ = self._make_tab()
        assert tab.name == 'Test'
        assert not tab.is_dirty
        assert tab.selected_record == 0
        assert not tab.editing_fields

    def test_navigation(self):
        tab, _ = self._make_tab()
        tab.selected_record = 1
        assert tab.selected_record == 1

    def test_enter_field_mode(self):
        tab, _ = self._make_tab()
        rec = tab.records[0]
        tab._current_fields = tab.field_factory(rec)
        tab.editing_fields = True
        tab.selected_field = 0
        assert tab.editing_fields
        assert len(tab._current_fields) == 2

    def test_save(self):
        tab, saved = self._make_tab()
        tab.dirty = True
        tab.save()
        assert not tab.is_dirty
        assert saved == [b'saved']

    def test_empty_records(self):
        tab, _ = self._make_tab(records=[])
        assert tab.name == 'Test'
        assert len(tab.records) == 0
        assert tab.selected_record == 0
        assert not tab.is_dirty

    def test_empty_records_navigation_safe(self):
        """Arrow keys on empty records should not crash."""
        tab, _ = self._make_tab(records=[])
        # Simulating what the keybinding handler does
        if tab.records:
            tab.selected_record = max(0, tab.selected_record - 1)
        # Should still be 0 (no crash)
        assert tab.selected_record == 0


class TestRosterEditor:
    def test_make_roster_tab(self, sample_roster_bytes):
        from ult3edit.tui.roster_editor import make_roster_tab
        saved = []
        tab = make_roster_tab(sample_roster_bytes, lambda d: saved.append(d))
        assert tab.name == 'Roster'
        assert len(tab.records) == 20

    def test_roster_field_editing(self, sample_roster_bytes):
        from ult3edit.tui.roster_editor import make_roster_tab, _character_fields
        tab = make_roster_tab(sample_roster_bytes, lambda d: None)
        # First character should be non-empty
        char = tab.records[0]
        fields = _character_fields(char)
        # Should have many fields
        assert len(fields) > 10
        # Name field getter should work
        name_field = fields[0]
        assert name_field.label == 'Name'
        name_val = name_field.getter()
        assert isinstance(name_val, str)

    def test_roster_field_getters_no_crash(self, sample_roster_bytes):
        """All field getters should work without AttributeError."""
        from ult3edit.tui.roster_editor import _character_fields
        from ult3edit.roster import Character
        char = Character(sample_roster_bytes[:64])
        fields = _character_fields(char)
        for field in fields:
            val = field.getter()
            assert val is not None

    def test_roster_save_roundtrip(self, sample_roster_bytes):
        from ult3edit.tui.roster_editor import make_roster_tab
        saved = []
        tab = make_roster_tab(sample_roster_bytes, lambda d: saved.append(d))
        tab.dirty = True
        tab.save()
        assert len(saved) == 1
        assert len(saved[0]) == 1280


class TestBestiaryEditor:
    def test_make_bestiary_tab(self, sample_mon_bytes):
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        saved = []
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: saved.append(d))
        assert tab.name == 'MONA'
        assert len(tab.records) == 16

    def test_bestiary_roundtrip(self, sample_mon_bytes):
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: None)
        data = tab.get_save_data()
        assert len(data) == 256

    def test_bestiary_roundtrip_preserves_data(self, sample_mon_bytes):
        """Round-trip should preserve monster attributes."""
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: None)
        data = tab.get_save_data()
        assert data == sample_mon_bytes

    def test_byte_clamp(self):
        from ult3edit.tui.bestiary_editor import _byte_clamp
        assert _byte_clamp('42') == 42
        assert _byte_clamp('0x48') == 0x48
        assert _byte_clamp('$48') == 0x48
        assert _byte_clamp('300') == 255
        assert _byte_clamp('-1') == 0
        assert _byte_clamp('0') == 0

    def test_bestiary_field_getters(self, sample_mon_bytes):
        """All field getters should work without crash."""
        from ult3edit.tui.bestiary_editor import make_bestiary_tab, _monster_fields
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: None)
        monster = tab.records[0]
        fields = _monster_fields(monster)
        for field in fields:
            val = field.getter()
            assert val is not None


class TestPartyEditor:
    def test_make_party_tab(self, sample_prty_bytes):
        from ult3edit.tui.party_editor import make_party_tab
        saved = []
        tab = make_party_tab(sample_prty_bytes, lambda d: saved.append(d))
        assert tab.name == 'Party'
        assert len(tab.records) == 1

    def test_party_fields(self, sample_prty_bytes):
        from ult3edit.tui.party_editor import make_party_tab, _party_fields
        tab = make_party_tab(sample_prty_bytes, lambda d: None)
        party = tab.records[0]
        fields = _party_fields(party)
        assert len(fields) == 7
        labels = [f.label for f in fields]
        assert 'Transport' in labels
        assert 'Party Size' in labels
        assert 'Location' in labels
        assert 'Sentinel' in labels

    def test_party_save_roundtrip(self, sample_prty_bytes):
        from ult3edit.tui.party_editor import make_party_tab
        saved = []
        tab = make_party_tab(sample_prty_bytes, lambda d: saved.append(d))
        tab.dirty = True
        tab.save()
        assert len(saved) == 1
        assert len(saved[0]) == 16
        assert saved[0] == sample_prty_bytes


class TestDialogEditor:
    def test_parse_records(self):
        from ult3edit.tui.dialog_editor import DialogEditor
        # Build a simple TLK-style binary: two records
        rec1 = bytes([0xC8, 0xC5, 0xCC, 0xCC, 0xCF, 0x00])  # "HELLO\0"
        rec2 = bytes([0xD7, 0xCF, 0xD2, 0xCC, 0xC4, 0x00])  # "WORLD\0"
        data = rec1 + rec2
        editor = DialogEditor('/tmp/test', data)
        assert len(editor.records) == 2
        assert editor.records[0] == ['HELLO']
        assert editor.records[1] == ['WORLD']

    def test_dirty_tracking(self):
        from ult3edit.tui.dialog_editor import DialogEditor
        data = bytes([0xC8, 0xC9, 0x00])  # "HI\0"
        editor = DialogEditor('/tmp/test', data)
        assert not editor.is_dirty
        editor.dirty = True
        assert editor.is_dirty

    def test_save_encodes_and_calls_callback(self):
        from ult3edit.tui.dialog_editor import DialogEditor
        rec1 = bytes([0xC8, 0xC9, 0x00])  # "HI\0"
        saved = []
        editor = DialogEditor('/tmp/test', rec1, save_callback=lambda d: saved.append(d))
        editor.dirty = True
        editor.save()
        assert not editor.is_dirty
        assert len(saved) == 1
        assert isinstance(saved[0], bytes)

    def test_multiline_record(self):
        from ult3edit.tui.dialog_editor import DialogEditor
        # "LINE1\xFFLINE2\x00" — multi-line record
        data = bytes([0xCC, 0xC9, 0xCE, 0xC5, 0xB1, 0xFF,
                      0xCC, 0xC9, 0xCE, 0xC5, 0xB2, 0x00])
        editor = DialogEditor('/tmp/test', data)
        assert len(editor.records) == 1
        assert len(editor.records[0]) == 2
        assert editor.records[0][0] == 'LINE1'
        assert editor.records[0][1] == 'LINE2'
