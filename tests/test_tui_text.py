"""Tests for TextEditor record parsing and rebuilding (no terminal needed)."""

from ult3edit.tui.text_editor import parse_text_records, rebuild_text_data


class TestParseRecords:
    def test_parse_sample(self, sample_text_bytes):
        records = parse_text_records(sample_text_bytes)
        assert len(records) == 3
        assert records[0].text == 'ULTIMA III'
        assert records[1].text == 'EXODUS'
        assert records[2].text == 'PRESS ANY KEY'

    def test_offsets(self, sample_text_bytes):
        records = parse_text_records(sample_text_bytes)
        assert records[0].offset == 0
        # 'ULTIMA III' = 10 chars + 1 null = offset 11
        assert records[1].offset == 11
        # 'EXODUS' = 6 chars + 1 null = offset 18
        assert records[2].offset == 18

    def test_max_len(self, sample_text_bytes):
        records = parse_text_records(sample_text_bytes)
        assert records[0].max_len == 10  # 'ULTIMA III'
        assert records[1].max_len == 6   # 'EXODUS'
        assert records[2].max_len == 13  # 'PRESS ANY KEY'

    def test_empty_data(self):
        records = parse_text_records(bytes(1024))
        assert records == []


class TestRebuild:
    def test_roundtrip(self, sample_text_bytes):
        records = parse_text_records(sample_text_bytes)
        rebuilt = rebuild_text_data(records, len(sample_text_bytes))
        # The text portions should match
        for rec in records:
            orig_slice = sample_text_bytes[rec.offset:rec.offset + rec.max_len]
            rebuilt_slice = rebuilt[rec.offset:rec.offset + rec.max_len]
            # Compare decoded text (encoding uppercases)
            from ult3edit.fileutil import decode_high_ascii
            assert decode_high_ascii(rebuilt_slice) == decode_high_ascii(bytes(orig_slice))

    def test_edit_preserves_offsets(self, sample_text_bytes):
        records = parse_text_records(sample_text_bytes)
        records[1].text = 'HELLO'  # Change 'EXODUS' to 'HELLO'
        rebuilt = rebuild_text_data(records, len(sample_text_bytes))
        # Re-parse and check
        new_records = parse_text_records(rebuilt)
        # The original 3 records should still be at same offsets
        assert new_records[0].text == 'ULTIMA III'
        assert new_records[1].text == 'HELLO'
        assert new_records[2].text == 'PRESS ANY KEY'


class TestSaveState:
    def test_party_size_setter(self, sample_prty_bytes):
        from ult3edit.save import PartyState
        party = PartyState(sample_prty_bytes)
        party.party_size = 3
        assert party.party_size == 3

    def test_party_size_clamps(self, sample_prty_bytes):
        from ult3edit.save import PartyState
        party = PartyState(sample_prty_bytes)
        party.party_size = 10
        assert party.party_size == 4
        party.party_size = -1
        assert party.party_size == 0

    def test_slot_ids_setter(self, sample_prty_bytes):
        from ult3edit.save import PartyState
        party = PartyState(sample_prty_bytes)
        party.slot_ids = [5, 6, 7, 8]
        assert party.slot_ids == [5, 6, 7, 8]

    def test_slot_ids_clamps(self, sample_prty_bytes):
        from ult3edit.save import PartyState
        party = PartyState(sample_prty_bytes)
        party.slot_ids = [0, 19, 25, -1]
        assert party.slot_ids == [0, 19, 19, 0]
