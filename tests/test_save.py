"""Tests for save state tool."""

import argparse
import os

from ult3edit.save import PartyState, cmd_edit, validate_party_state
from ult3edit.constants import (
    PRTY_FILE_SIZE, PRTY_OFF_TRANSPORT, PRTY_OFF_PARTY_SIZE,
    PRTY_OFF_LOCATION, PRTY_OFF_SENTINEL,
    PRTY_OFF_SLOT_IDS,
)


class TestPartyState:
    def test_transport(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.transport == 'On Foot'

    def test_location(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.location_type == 'Sosaria'

    def test_coordinates(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.x == 32
        assert party.y == 32

    def test_party_size(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.party_size == 4

    def test_slot_ids(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.slot_ids == [0, 1, 2, 3]


class TestSetters:
    def test_set_transport(self, sample_prty_bytes):
        party = PartyState(bytearray(sample_prty_bytes))
        party.transport = 'horse'
        assert party.transport == 'Horse'

    def test_set_coordinates(self, sample_prty_bytes):
        party = PartyState(bytearray(sample_prty_bytes))
        party.x = 10
        party.y = 20
        assert party.x == 10
        assert party.y == 20

    def test_clamp_coordinates(self, sample_prty_bytes):
        party = PartyState(bytearray(sample_prty_bytes))
        party.x = 100
        assert party.x == 63


class TestToDict:
    def test_keys(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        d = party.to_dict()
        assert 'transport' in d
        assert 'x' in d
        assert 'y' in d
        assert 'party_size' in d
        assert 'slot_ids' in d


def _save_args(**kwargs):
    defaults = dict(game_dir=None, transport=None, x=None, y=None,
                    party_size=None, slot_ids=None, output=None)
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestCmdEdit:
    def _write_prty(self, tmp_dir, data):
        prty_path = os.path.join(tmp_dir, 'PRTY#060000')
        with open(prty_path, 'wb') as f:
            f.write(data)

    def test_edit_transport(self, tmp_dir, sample_prty_bytes):
        self._write_prty(tmp_dir, sample_prty_bytes)
        out = os.path.join(tmp_dir, 'PRTY_OUT')
        cmd_edit(_save_args(game_dir=tmp_dir, transport='horse', output=out))
        with open(out, 'rb') as f:
            result = f.read()
        assert PartyState(result).transport == 'Horse'

    def test_edit_coordinates(self, tmp_dir, sample_prty_bytes):
        self._write_prty(tmp_dir, sample_prty_bytes)
        out = os.path.join(tmp_dir, 'PRTY_OUT')
        cmd_edit(_save_args(game_dir=tmp_dir, x=10, y=20, output=out))
        with open(out, 'rb') as f:
            result = f.read()
        party = PartyState(result)
        assert party.x == 10
        assert party.y == 20

    def test_edit_party_size(self, tmp_dir, sample_prty_bytes):
        self._write_prty(tmp_dir, sample_prty_bytes)
        out = os.path.join(tmp_dir, 'PRTY_OUT')
        cmd_edit(_save_args(game_dir=tmp_dir, party_size=2, output=out))
        with open(out, 'rb') as f:
            result = f.read()
        assert PartyState(result).party_size == 2

    def test_transport_foot_alias(self, tmp_dir, sample_prty_bytes):
        """'foot' should work as an alias for 'on foot'."""
        self._write_prty(tmp_dir, sample_prty_bytes)
        out = os.path.join(tmp_dir, 'PRTY_OUT')
        cmd_edit(_save_args(game_dir=tmp_dir, transport='foot', output=out))
        with open(out, 'rb') as f:
            result = f.read()
        assert PartyState(result).transport == 'On Foot'


class TestValidatePartyState:
    def test_valid_party(self, sample_prty_bytes):
        """Valid party should produce no warnings."""
        party = PartyState(sample_prty_bytes)
        assert validate_party_state(party) == []

    def test_unknown_transport(self):
        """Unknown transport code should warn."""
        data = bytearray(PRTY_FILE_SIZE)
        data[PRTY_OFF_TRANSPORT] = 0x42  # Unknown
        data[PRTY_OFF_SENTINEL] = 0xFF
        party = PartyState(bytes(data))
        warnings = validate_party_state(party)
        assert any('transport' in w.lower() for w in warnings)

    def test_party_size_exceeds_max(self):
        """Party size > 4 should warn."""
        data = bytearray(PRTY_FILE_SIZE)
        data[PRTY_OFF_PARTY_SIZE] = 5
        data[PRTY_OFF_TRANSPORT] = 0x01
        data[PRTY_OFF_SENTINEL] = 0xFF
        party = PartyState(bytes(data))
        warnings = validate_party_state(party)
        assert any('Party size' in w for w in warnings)

    def test_unknown_location_type(self):
        """Unknown location type should warn."""
        data = bytearray(PRTY_FILE_SIZE)
        data[PRTY_OFF_TRANSPORT] = 0x01
        data[PRTY_OFF_LOCATION] = 0x42  # Unknown
        data[PRTY_OFF_SENTINEL] = 0xFF
        party = PartyState(bytes(data))
        warnings = validate_party_state(party)
        assert any('location' in w.lower() for w in warnings)

    def test_invalid_slot_ids(self):
        """Slot IDs > 19 should warn."""
        data = bytearray(PRTY_FILE_SIZE)
        data[PRTY_OFF_TRANSPORT] = 0x01
        data[PRTY_OFF_PARTY_SIZE] = 1
        data[PRTY_OFF_SENTINEL] = 0xFF
        data[PRTY_OFF_SLOT_IDS] = 25  # > 19
        party = PartyState(bytes(data))
        warnings = validate_party_state(party)
        assert any('roster index' in w for w in warnings)

    def test_unexpected_sentinel(self):
        """Non-$FF/$00 sentinel should warn."""
        data = bytearray(PRTY_FILE_SIZE)
        data[PRTY_OFF_TRANSPORT] = 0x01
        data[PRTY_OFF_SENTINEL] = 0x42  # Unexpected
        party = PartyState(bytes(data))
        warnings = validate_party_state(party)
        assert any('sentinel' in w.lower() for w in warnings)


class TestPlrsImport:
    """Tests for PLRS character import via save cmd_import."""

    def _setup_game_dir(self, tmp_dir, sample_prty_bytes, sample_character_bytes):
        """Write PRTY and PLRS files to tmp_dir."""
        from ult3edit.constants import CHAR_RECORD_SIZE, PLRS_FILE_SIZE
        prty_path = os.path.join(tmp_dir, 'PRTY#060000')
        with open(prty_path, 'wb') as f:
            f.write(sample_prty_bytes)
        plrs_data = bytearray(PLRS_FILE_SIZE)
        for i in range(4):
            plrs_data[i * CHAR_RECORD_SIZE:(i + 1) * CHAR_RECORD_SIZE] = sample_character_bytes
        plrs_path = os.path.join(tmp_dir, 'PLRS#060000')
        with open(plrs_path, 'wb') as f:
            f.write(plrs_data)
        return plrs_path

    def test_import_plrs_name(self, tmp_dir, sample_prty_bytes, sample_character_bytes):
        """Import should update character name in PLRS."""
        import json
        import types
        from ult3edit.save import cmd_import as save_import
        from ult3edit.roster import Character
        from ult3edit.constants import CHAR_RECORD_SIZE
        plrs_path = self._setup_game_dir(tmp_dir, sample_prty_bytes, sample_character_bytes)
        jdata = {'active_characters': [{'name': 'WIZARD'}]}
        json_path = os.path.join(tmp_dir, 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = types.SimpleNamespace(
            game_dir=tmp_dir, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        save_import(args)
        with open(plrs_path, 'rb') as f:
            result = f.read()
        char = Character(result[0:CHAR_RECORD_SIZE])
        assert char.name == 'WIZARD'

    def test_import_plrs_stats(self, tmp_dir, sample_prty_bytes, sample_character_bytes):
        """Import should update character stats in PLRS."""
        import json
        import types
        from ult3edit.save import cmd_import as save_import
        from ult3edit.roster import Character
        from ult3edit.constants import CHAR_RECORD_SIZE
        plrs_path = self._setup_game_dir(tmp_dir, sample_prty_bytes, sample_character_bytes)
        jdata = {'active_characters': [{'stats': {'str': 99, 'dex': 75}, 'gold': 5000}]}
        json_path = os.path.join(tmp_dir, 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = types.SimpleNamespace(
            game_dir=tmp_dir, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        save_import(args)
        with open(plrs_path, 'rb') as f:
            result = f.read()
        char = Character(result[0:CHAR_RECORD_SIZE])
        assert char.strength == 99
        assert char.dexterity == 75
        assert char.gold == 5000

    def test_import_plrs_dry_run(self, tmp_dir, sample_prty_bytes, sample_character_bytes):
        """Dry run should not write PLRS changes."""
        import json
        import types
        from ult3edit.save import cmd_import as save_import
        plrs_path = self._setup_game_dir(tmp_dir, sample_prty_bytes, sample_character_bytes)
        with open(plrs_path, 'rb') as f:
            original = f.read()
        jdata = {'active_characters': [{'name': 'CHANGED', 'gold': 9999}]}
        json_path = os.path.join(tmp_dir, 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = types.SimpleNamespace(
            game_dir=tmp_dir, json_file=json_path,
            output=None, backup=False, dry_run=True,
        )
        save_import(args)
        with open(plrs_path, 'rb') as f:
            after = f.read()
        assert original == after

    def test_import_plrs_missing_file(self, tmp_dir, sample_prty_bytes):
        """Missing PLRS file should skip gracefully."""
        import json
        import types
        from ult3edit.save import cmd_import as save_import
        # Only write PRTY, no PLRS
        prty_path = os.path.join(tmp_dir, 'PRTY#060000')
        with open(prty_path, 'wb') as f:
            f.write(sample_prty_bytes)
        jdata = {'active_characters': [{'name': 'WIZARD'}]}
        json_path = os.path.join(tmp_dir, 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = types.SimpleNamespace(
            game_dir=tmp_dir, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        # Should not raise, just warn
        save_import(args)

    def test_import_plrs_multiple_slots(self, tmp_dir, sample_prty_bytes, sample_character_bytes):
        """Import should update multiple PLRS slots."""
        import json
        import types
        from ult3edit.save import cmd_import as save_import
        from ult3edit.roster import Character
        from ult3edit.constants import CHAR_RECORD_SIZE
        plrs_path = self._setup_game_dir(tmp_dir, sample_prty_bytes, sample_character_bytes)
        jdata = {'active_characters': [
            {'name': 'ALPHA', 'hp': 100},
            {'name': 'BETA', 'hp': 200},
        ]}
        json_path = os.path.join(tmp_dir, 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = types.SimpleNamespace(
            game_dir=tmp_dir, json_file=json_path,
            output=None, backup=False, dry_run=False,
        )
        save_import(args)
        with open(plrs_path, 'rb') as f:
            result = f.read()
        char0 = Character(result[0:CHAR_RECORD_SIZE])
        char1 = Character(result[CHAR_RECORD_SIZE:CHAR_RECORD_SIZE * 2])
        assert char0.name == 'ALPHA'
        assert char0.hp == 100
        assert char1.name == 'BETA'
        assert char1.hp == 200
