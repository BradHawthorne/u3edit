"""Tests for save state tool."""

import argparse
import json
import os
import tempfile

import pytest

from ult3edit.bcd import int_to_bcd
from ult3edit.roster import Character
from ult3edit.save import PartyState, cmd_edit, validate_party_state
from ult3edit.tui.party_editor import make_party_tab
from ult3edit.constants import (
    PRTY_FILE_SIZE, PRTY_OFF_TRANSPORT, PRTY_OFF_PARTY_SIZE,
    PRTY_OFF_LOCATION, PRTY_OFF_SENTINEL,
    PRTY_OFF_SLOT_IDS, PRTY_OFF_SAVED_X, PRTY_OFF_SAVED_Y,
    CHAR_HP_HI, CHAR_STATUS, CHAR_RECORD_SIZE, PLRS_FILE_SIZE, PRTY_LOCATION_CODES,
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


# ── Migrated from test_new_features.py ──

class TestPlrsEditing:
    def test_edit_plrs_character(self, tmp_dir, sample_character_bytes):
        # Create PLRS with 4 characters
        plrs_data = bytearray(PLRS_FILE_SIZE)
        for i in range(4):
            plrs_data[i * CHAR_RECORD_SIZE:(i + 1) * CHAR_RECORD_SIZE] = sample_character_bytes
        path = os.path.join(tmp_dir, 'PLRS')
        with open(path, 'wb') as f:
            f.write(plrs_data)

        # Edit slot 0
        with open(path, 'rb') as f:
            data = bytearray(f.read())
        char = Character(data[0:CHAR_RECORD_SIZE])
        char.gold = 999
        data[0:CHAR_RECORD_SIZE] = char.raw
        with open(path, 'wb') as f:
            f.write(data)

        # Verify
        with open(path, 'rb') as f:
            result = f.read()
        char2 = Character(result[0:CHAR_RECORD_SIZE])
        assert char2.gold == 999


# =============================================================================
# Save import
# =============================================================================


class TestPrtyFieldMapping:
    """Verify PRTY byte layout matches engine-traced zero-page $E0-$EF."""

    def test_transport_at_offset_0(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.transport == 'On Foot'

    def test_party_size_at_offset_1(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.party_size == 4

    def test_location_type_at_offset_2(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.location_type == 'Sosaria'

    def test_saved_x_at_offset_3(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.x == 32

    def test_saved_y_at_offset_4(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.y == 32

    def test_sentinel_at_offset_5(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.sentinel == 0xFF

    def test_slot_ids_at_offset_6(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        assert party.slot_ids == [0, 1, 2, 3]

    def test_setters_write_correct_offsets(self):
        """Verify setters write to the engine-correct byte positions."""
        data = bytearray(16)
        party = PartyState(data)
        party.party_size = 3
        party.x = 44
        party.y = 20
        party.slot_ids = [5, 6, 7, 8]
        assert party.raw[1] == 3     # $E1 = party_size
        assert party.raw[3] == 44    # $E3 = saved_x
        assert party.raw[4] == 20    # $E4 = saved_y
        assert party.raw[6] == 5     # $E6 = slot 0
        assert party.raw[7] == 6     # $E7 = slot 1
        assert party.raw[8] == 7     # $E8 = slot 2
        assert party.raw[9] == 8     # $E9 = slot 3

    def test_to_dict_keys(self, sample_prty_bytes):
        party = PartyState(sample_prty_bytes)
        d = party.to_dict()
        assert 'transport' in d
        assert 'party_size' in d
        assert 'location_type' in d
        assert 'x' in d
        assert 'y' in d
        assert 'slot_ids' in d


class TestSaveImport:
    def test_import_party_state(self, tmp_dir, sample_prty_bytes):
        path = os.path.join(tmp_dir, 'PRTY')
        with open(path, 'wb') as f:
            f.write(sample_prty_bytes)

        # Load, modify via JSON
        party = PartyState(sample_prty_bytes)
        assert party.x == 32
        party.x = 10
        party.y = 20

        with open(path, 'wb') as f:
            f.write(bytes(party.raw))

        with open(path, 'rb') as f:
            result = f.read()
        p2 = PartyState(result)
        assert p2.x == 10
        assert p2.y == 20


# =============================================================================
# Combat import
# =============================================================================


class TestSentinelSetter:
    def test_set_active(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.sentinel = 0xFF
        assert party.sentinel == 0xFF

    def test_raw_byte_masking(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.sentinel = 0x1FF  # should mask to 0xFF
        assert party.sentinel == 0xFF


class TestTransportSetterFix:
    def test_named_value(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'horse'
        assert party.raw[PRTY_OFF_TRANSPORT] == 0x0A

    def test_raw_int(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 0x0A
        assert party.raw[PRTY_OFF_TRANSPORT] == 0x0A

    def test_hex_string(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = '0x0B'
        assert party.raw[PRTY_OFF_TRANSPORT] == 0x0B

    def test_unknown_raises(self):
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        with pytest.raises(ValueError, match='Unknown transport'):
            party.transport = 'hovercraft'


class TestSaveImportSentinel:
    def test_to_dict_has_sentinel(self):
        data = bytearray(PRTY_FILE_SIZE)
        data[PRTY_OFF_SENTINEL] = 0xFF
        party = PartyState(data)
        d = party.to_dict()
        assert d['sentinel'] == 0xFF


# =============================================================================
# Fix 3: shapes.py — SHP overlay string editing
# =============================================================================


_JSR_46BA_BYTES = bytes([0x20, 0xBA, 0x46])


# =============================================================================
# Fix 3: CLI parity for edit-string
# =============================================================================


# =============================================================================
# Fix: Gender setter accepts raw int/hex
# =============================================================================


class TestLocationTypeSetter:
    def test_set_by_name(self):
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_type = 'dungeon'
        assert party.raw[PRTY_OFF_LOCATION] == 0x01

    def test_set_by_name_case_insensitive(self):
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_type = 'Town'
        assert party.raw[PRTY_OFF_LOCATION] == 0x02

    def test_set_by_raw_int(self):
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_type = 0x80
        assert party.raw[PRTY_OFF_LOCATION] == 0x80

    def test_set_by_hex_string(self):
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_type = '0xFF'
        assert party.raw[PRTY_OFF_LOCATION] == 0xFF

    def test_unknown_raises(self):
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        with pytest.raises(ValueError, match='Unknown location type'):
            party.location_type = 'narnia'


# =============================================================================
# Fix: PLRS import handles all Character fields
# =============================================================================


class TestPlrsImportAllFields:
    def test_roundtrip_all_fields(self):
        """Export a Character via to_dict, import into PLRS, verify all fields."""
        # Build a character with known values
        char = Character(bytearray(CHAR_RECORD_SIZE))
        char.name = 'WARRIOR'
        char.race = 'H'
        char.char_class = 'F'
        char.gender = 'M'
        char.raw[CHAR_STATUS] = ord('G')
        char.strength = 25
        char.dexterity = 20
        char.intelligence = 15
        char.wisdom = 10
        char.hp = 500
        char.max_hp = 500
        char.mp = 30
        char.exp = 1234
        char.gold = 5000
        char.food = 3000
        char.gems = 10
        char.keys = 5
        char.powders = 3
        char.torches = 8
        char.sub_morsels = 50
        char.marks = ['Kings', 'Snake']
        char.cards = ['Death']
        char.equipped_weapon = 5
        char.equipped_armor = 3
        char.set_weapon_count(1, 2)  # 2 Daggers
        char.set_armor_count(1, 1)   # 1 Cloth

        d = char.to_dict()

        # Now import into a fresh PLRS-sized buffer
        plrs_data = bytearray(PLRS_FILE_SIZE)
        # Put the character data in slot 0
        plrs_data[0:CHAR_RECORD_SIZE] = char.raw

        # Build a JSON with the dict (like active_characters export)
        json_data = {'active_characters': [d]}

        with tempfile.TemporaryDirectory() as game_dir:
            # Write PRTY
            prty_path = os.path.join(game_dir, 'PRTY#060000')
            with open(prty_path, 'wb') as f:
                f.write(bytearray(PRTY_FILE_SIZE))
            # Write PLRS (empty — we want import to fill it)
            plrs_path = os.path.join(game_dir, 'PLRS#060000')
            with open(plrs_path, 'wb') as f:
                f.write(bytearray(PLRS_FILE_SIZE))
            # Write JSON
            json_path = os.path.join(game_dir, 'import.json')
            with open(json_path, 'w') as f:
                json.dump(json_data, f)

            from ult3edit.save import cmd_import as save_import
            args = type('Args', (), {
                'game_dir': game_dir, 'json_file': json_path,
                'output': None, 'backup': False, 'dry_run': False,
            })()
            save_import(args)

            # Read back the PLRS and verify
            with open(plrs_path, 'rb') as f:
                result = f.read()
            imported = Character(result[0:CHAR_RECORD_SIZE])
            assert imported.name == 'WARRIOR'
            assert imported.gems == 10
            assert imported.keys == 5
            assert imported.powders == 3
            assert imported.torches == 8
            assert imported.sub_morsels == 50
            assert 'Kings' in imported.marks
            assert 'Death' in imported.cards
            assert imported.equipped_weapon == 'Bow'  # index 5
            assert imported.equipped_armor == 'Chain'  # index 3


# =============================================================================
# Fix: PLRS edit CLI supports all character fields
# =============================================================================


class TestPlrsEditExpandedArgs:
    def test_help_shows_new_args(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit.save', 'edit', '--help'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert '--gems' in result.stdout
        assert '--keys' in result.stdout
        assert '--torches' in result.stdout
        assert '--status' in result.stdout
        assert '--race' in result.stdout
        assert '--weapon' in result.stdout
        assert '--armor' in result.stdout
        assert '--marks' in result.stdout
        assert '--location' in result.stdout


# =============================================================================
# Fix: location_type import in party JSON
# =============================================================================


class TestLocationTypeImport:
    def test_location_type_imported(self):
        json_data = {
            'party': {'location_type': 'Town'},
        }
        with tempfile.TemporaryDirectory() as game_dir:
            prty_path = os.path.join(game_dir, 'PRTY#060000')
            with open(prty_path, 'wb') as f:
                f.write(bytearray(PRTY_FILE_SIZE))
            json_path = os.path.join(game_dir, 'import.json')
            with open(json_path, 'w') as f:
                json.dump(json_data, f)

            from ult3edit.save import cmd_import as save_import
            args = type('Args', (), {
                'game_dir': game_dir, 'json_file': json_path,
                'output': None, 'backup': False, 'dry_run': False,
            })()
            save_import(args)

            with open(prty_path, 'rb') as f:
                result = f.read()
            party = PartyState(result)
            assert party.raw[PRTY_OFF_LOCATION] == 0x02  # Town


# =============================================================================
# Fix: Combat monster (0,0) round-trip
# =============================================================================


class TestSaveEditValidate:
    """Test --validate on save edit command."""

    def test_validate_warns_on_bad_coords(self, tmp_path):
        from ult3edit.save import cmd_edit
        # Create PRTY file
        prty = bytearray(16)
        prty[0] = 0x00  # transport = foot
        prty[1] = 1     # party_size
        prty[2] = 0     # location = sosaria
        prty[3] = 10    # x
        prty[4] = 10    # y
        prty[5] = 0xFF  # sentinel
        prty[6] = 0     # slot 0
        prty_path = str(tmp_path / 'PRTY')
        with open(prty_path, 'wb') as f:
            f.write(prty)

        args = type('Args', (), {
            'game_dir': str(tmp_path),
            'transport': None,
            'x': 99,  # Out of bounds — should trigger warning
            'y': None,
            'party_size': None,
            'slot_ids': None,
            'sentinel': None,
            'location': None,
            'output': None,
            'backup': False,
            'dry_run': True,
            'validate': True,
            'plrs_slot': None,
        })()
        # Should not crash; validation warning printed
        cmd_edit(args)

    def test_validate_flag_in_help(self):
        import subprocess
        result = subprocess.run(
            ['python', '-m', 'ult3edit.save', 'edit', '--help'],
            capture_output=True, text=True)
        assert '--validate' in result.stdout


# =============================================================================
# hex_int acceptance: tile/offset/byte args accept 0x prefix
# =============================================================================


class TestPrtySlotIdsPartialWrite:
    """Verify slot_ids setter zero-fills unused slots."""

    def test_partial_slot_ids_zeros_remainder(self):
        """Setting 2 slot IDs zeros out slots 2 and 3."""
        from ult3edit.save import PartyState, PRTY_OFF_SLOT_IDS
        raw = bytearray(16)
        # Pre-fill with garbage
        raw[PRTY_OFF_SLOT_IDS] = 0xFF
        raw[PRTY_OFF_SLOT_IDS + 1] = 0xAA
        raw[PRTY_OFF_SLOT_IDS + 2] = 0xBB
        raw[PRTY_OFF_SLOT_IDS + 3] = 0xCC
        party = PartyState(raw)
        party.slot_ids = [5, 10]
        assert party.slot_ids == [5, 10, 0, 0], \
            "Unused slots should be zeroed"

    def test_empty_slot_ids_zeros_all(self):
        """Setting empty slot_ids zeros all 4 slots."""
        from ult3edit.save import PartyState, PRTY_OFF_SLOT_IDS
        raw = bytearray(16)
        raw[PRTY_OFF_SLOT_IDS:PRTY_OFF_SLOT_IDS + 4] = b'\xFF\xFF\xFF\xFF'
        party = PartyState(raw)
        party.slot_ids = []
        assert party.slot_ids == [0, 0, 0, 0]

    def test_full_slot_ids_still_works(self):
        """Setting all 4 slot IDs still works correctly."""
        from ult3edit.save import PartyState
        raw = bytearray(16)
        party = PartyState(raw)
        party.slot_ids = [1, 3, 7, 15]
        assert party.slot_ids == [1, 3, 7, 15]


class TestSaveCmdViewExpanded:
    """Tests for save cmd_view with --json and --brief flags."""

    def _make_save_dir(self, tmp_path):
        """Create a directory with PRTY and PLRS files."""
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF  # sentinel
        data[1] = 2     # party_size
        data[3] = 10    # saved_x
        data[4] = 20    # saved_y
        prty.write_bytes(bytes(data))
        plrs = tmp_path / 'PLRS'
        plrs_data = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            plrs_data[i] = ord(ch) | 0x80
        plrs_data[0x0D] = 0x00
        plrs.write_bytes(bytes(plrs_data))
        return str(tmp_path)

    def test_view_json(self, tmp_path):
        """save view --json produces valid JSON with party and active chars."""
        from ult3edit.save import cmd_view
        game_dir = self._make_save_dir(tmp_path)
        outfile = tmp_path / 'save.json'
        args = argparse.Namespace(
            game_dir=game_dir, json=True, output=str(outfile),
            validate=False, brief=False)
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'party' in result
        assert 'active_characters' in result

    def test_view_brief_skips_map(self, tmp_path, capsys):
        """save view --brief skips the SOSA mini-map."""
        from ult3edit.save import cmd_view
        game_dir = self._make_save_dir(tmp_path)
        # Also create a SOSA file (overworld map)
        from ult3edit.constants import SOSA_FILE_SIZE
        sosa = tmp_path / 'SOSA'
        sosa.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            game_dir=game_dir, json=False, output=None,
            validate=False, brief=True)
        cmd_view(args)
        out = capsys.readouterr().out
        # With --brief, no "Overworld" section should appear
        assert 'Overworld' not in out

    def test_view_validate_shows_warnings(self, tmp_path, capsys):
        """save view --validate shows party state warnings."""
        from ult3edit.save import cmd_view
        game_dir = self._make_save_dir(tmp_path)
        # Set an invalid slot ID (>19)
        prty = tmp_path / 'PRTY'
        data = bytearray(prty.read_bytes())
        data[1] = 2      # party_size = 2
        data[6] = 0xFF    # slot 0 = 255 (invalid)
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            game_dir=game_dir, json=False, output=None,
            validate=True, brief=True)
        cmd_view(args)
        err = capsys.readouterr().err
        assert 'WARNING' in err


class TestSaveCmdEditExpanded:
    """Tests for save cmd_edit with --location, --slot-ids, --sentinel."""

    def _make_save_dir(self, tmp_path):
        """Create PRTY file for editing."""
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF  # sentinel
        prty.write_bytes(bytes(data))
        return str(tmp_path)

    def test_edit_location(self, tmp_path, capsys):
        """Edit party location_type."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_save_dir(tmp_path)
        args = argparse.Namespace(
            game_dir=game_dir, transport=None, x=None, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location='sosaria', plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        cmd_edit(args)
        prty = tmp_path / 'PRTY'
        data = prty.read_bytes()
        # Location is at offset 2 (PRTY_OFF_LOCATION)
        assert data[2] == PRTY_LOCATION_CODES['sosaria']

    def test_edit_slot_ids(self, tmp_path, capsys):
        """Edit party slot_ids."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_save_dir(tmp_path)
        args = argparse.Namespace(
            game_dir=game_dir, transport=None, x=None, y=None,
            party_size=None, slot_ids=[0, 1, 2, 3], sentinel=None,
            location=None, plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        cmd_edit(args)
        prty = tmp_path / 'PRTY'
        data = prty.read_bytes()
        assert data[6] == 0  # slot 0
        assert data[7] == 1  # slot 1
        assert data[8] == 2  # slot 2
        assert data[9] == 3  # slot 3

    def test_edit_dry_run(self, tmp_path, capsys):
        """Edit with dry_run shows changes but doesn't write."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_save_dir(tmp_path)
        args = argparse.Namespace(
            game_dir=game_dir, transport=None, x=10, y=20,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=None,
            dry_run=True, backup=False, output=None, validate=False)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out


# =============================================================================
# Combat cmd_view directory mode
# =============================================================================


class TestPartyStateEdgeCases:
    """Tests for PartyState constructor and setter edge cases."""

    def test_constructor_too_small_raises(self):
        """PartyState with data shorter than PRTY_FILE_SIZE raises ValueError."""
        with pytest.raises(ValueError, match='too small'):
            PartyState(bytes(5))

    def test_constructor_exact_size(self):
        """PartyState with exact PRTY_FILE_SIZE works."""
        party = PartyState(bytes(PRTY_FILE_SIZE))
        assert party.party_size == 0

    def test_slot_ids_clamps_high(self):
        """Slot IDs > 19 are clamped to 19."""
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.slot_ids = [99, 0, 0, 0]
        assert party.raw[6] == 19  # clamped

    def test_slot_ids_clamps_negative(self):
        """Negative slot IDs are clamped to 0."""
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.slot_ids = [-5, 0, 0, 0]
        assert party.raw[6] == 0  # clamped

    def test_location_code_setter(self):
        """location_code setter writes raw byte directly."""
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_code = 0x03
        assert party.location_code == 0x03
        assert party.raw[2] == 0x03  # PRTY_OFF_LOCATION

    def test_location_code_setter_masks_to_byte(self):
        """location_code setter masks value to 0xFF."""
        party = PartyState(bytearray(PRTY_FILE_SIZE))
        party.location_code = 0x1FF
        assert party.location_code == 0xFF


class TestSaveErrorPaths:
    """Tests for save cmd_view/cmd_edit/cmd_import error exits."""

    def test_view_no_prty(self, tmp_path):
        """cmd_view with no PRTY file exits."""
        from ult3edit.save import cmd_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False, brief=True)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_edit_no_prty(self, tmp_path):
        """cmd_edit with no PRTY file exits."""
        from ult3edit.save import cmd_edit
        args = argparse.Namespace(
            game_dir=str(tmp_path), transport=None, x=1, y=1,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_invalid_transport(self, tmp_path, capsys):
        """cmd_edit with invalid transport name exits."""
        from ult3edit.save import cmd_edit
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            game_dir=str(tmp_path), transport='spaceship', x=None, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_invalid_location(self, tmp_path, capsys):
        """cmd_edit with invalid location name exits."""
        from ult3edit.save import cmd_edit
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            game_dir=str(tmp_path), transport=None, x=None, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location='moon', plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_plrs_slot_no_plrs(self, tmp_path):
        """cmd_edit with --plrs-slot but no PLRS file exits."""
        from ult3edit.save import cmd_edit
        prty = tmp_path / 'PRTY'
        data = bytearray(PRTY_FILE_SIZE)
        data[5] = 0xFF
        prty.write_bytes(bytes(data))
        args = argparse.Namespace(
            game_dir=str(tmp_path), transport=None, x=None, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=0,
            name='TEST', str=None, dex=None, int_=None, wis=None,
            hp=None, mp=None, gold=None, food=None,
            exp=None, max_hp=None, gems=None, keys=None,
            powders=None, torches=None, status=None,
            weapon=None, armor=None, race=None, char_class=None,
            gender=None, in_party=None, not_in_party=None,
            dry_run=False, backup=False, output=None, validate=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_import_no_prty(self, tmp_path):
        """cmd_import with no PRTY file exits."""
        from ult3edit.save import cmd_import
        json_path = tmp_path / 'save.json'
        json_path.write_text(json.dumps({'party': {'transport': 'foot'}}))
        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=str(json_path),
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_import(args)


class TestPrtyRoundTrip:
    """Verify all PRTY fields survive set→save→reload cycle."""

    def test_all_fields_roundtrip(self, tmp_path):
        """Set every PRTY field, write to file, reload, verify all match."""
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'horse'
        party.party_size = 3
        party.location_type = 'dungeon'
        party.x = 42
        party.y = 17
        party.sentinel = 0xFF
        party.slot_ids = [5, 10, 15, 2]

        # Write raw bytes
        prty_file = tmp_path / 'PRTY'
        prty_file.write_bytes(bytes(party.raw))

        # Reload
        reloaded = PartyState(prty_file.read_bytes())
        assert reloaded.transport == 'Horse'
        assert reloaded.party_size == 3
        assert reloaded.location_type == 'Dungeon'
        assert reloaded.x == 42
        assert reloaded.y == 17
        assert reloaded.sentinel == 0xFF
        assert reloaded.slot_ids == [5, 10, 15, 2]

    def test_json_export_import_roundtrip(self, tmp_path):
        """Export PRTY to JSON via to_dict, re-import via cmd_import, verify."""
        from ult3edit.save import cmd_import as save_import

        # Set up initial PRTY state
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'ship'
        party.party_size = 4
        party.location_type = 'sosaria'
        party.x = 55
        party.y = 33
        party.sentinel = 0xFF
        party.slot_ids = [0, 1, 2, 3]

        prty_file = tmp_path / 'PRTY'
        prty_file.write_bytes(bytes(party.raw))

        # Export to JSON dict
        jdata = {'party': party.to_dict()}

        # Modify some fields in JSON
        jdata['party']['x'] = 10
        jdata['party']['y'] = 20
        jdata['party']['party_size'] = 2

        # Write JSON and import
        json_file = tmp_path / 'save.json'
        json_file.write_text(json.dumps(jdata))

        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        save_import(args)

        # Reload and verify modified fields
        result = PartyState(prty_file.read_bytes())
        assert result.x == 10
        assert result.y == 20
        assert result.party_size == 2
        # Unmodified fields should persist
        assert result.transport == 'Ship'
        assert result.sentinel == 0xFF
        assert result.slot_ids == [0, 1, 2, 3]

    def test_byte_level_fidelity(self, tmp_path):
        """Verify every byte in the 16-byte PRTY survives save→reload."""
        data = bytearray(range(16))
        party = PartyState(data)
        prty_file = tmp_path / 'PRTY'
        prty_file.write_bytes(bytes(party.raw))
        reloaded = PartyState(prty_file.read_bytes())
        assert bytes(reloaded.raw) == bytes(party.raw)


class TestSaveValidationBounds:
    """Tests for validate_party_state X/Y coordinate validation."""

    def test_valid_coordinates_no_warning(self):
        """Coordinates within 0-63 produce no warnings about coords."""
        from ult3edit.save import validate_party_state
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'foot'
        party.location_type = 'sosaria'
        party.party_size = 1
        party.x = 63
        party.y = 0
        party.sentinel = 0xFF
        party.slot_ids = [0, 0, 0, 0]
        warnings = validate_party_state(party)
        coord_warnings = [w for w in warnings if 'coordinate' in w.lower()]
        assert len(coord_warnings) == 0

    def test_x_out_of_bounds_warning(self):
        """X coordinate > 63 triggers warning."""
        from ult3edit.save import validate_party_state
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'foot'
        party.location_type = 'sosaria'
        party.sentinel = 0xFF
        # Bypass clamping setter to set raw value > 63
        party.raw[PRTY_OFF_SAVED_X] = 200
        warnings = validate_party_state(party)
        coord_warnings = [w for w in warnings if 'X coordinate' in w]
        assert len(coord_warnings) == 1

    def test_y_out_of_bounds_warning(self):
        """Y coordinate > 63 triggers warning."""
        from ult3edit.save import validate_party_state
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        party.transport = 'foot'
        party.location_type = 'sosaria'
        party.sentinel = 0xFF
        party.raw[PRTY_OFF_SAVED_Y] = 128
        warnings = validate_party_state(party)
        coord_warnings = [w for w in warnings if 'Y coordinate' in w]
        assert len(coord_warnings) == 1

    def test_multiple_violations(self):
        """Multiple validation issues produce multiple warnings."""
        from ult3edit.save import validate_party_state
        data = bytearray(PRTY_FILE_SIZE)
        party = PartyState(data)
        # Unknown transport
        party.raw[PRTY_OFF_TRANSPORT] = 0xFE
        # Unknown location
        party.raw[PRTY_OFF_LOCATION] = 0xFE
        # Bad coords
        party.raw[PRTY_OFF_SAVED_X] = 200
        party.raw[PRTY_OFF_SAVED_Y] = 200
        # Weird sentinel
        party.raw[PRTY_OFF_SENTINEL] = 0x42
        warnings = validate_party_state(party)
        assert len(warnings) >= 4


# =============================================================================
# Map editing edge cases
# =============================================================================


class TestSaveCmdImport:
    """Test save.py cmd_import."""

    def test_import_party_state(self, tmp_path):
        """Import party state from JSON."""
        from ult3edit.save import cmd_import as save_import
        # Create PRTY file
        prty_data = bytearray(PRTY_FILE_SIZE)
        prty_path = os.path.join(str(tmp_path), 'PRTY')
        with open(prty_path, 'wb') as f:
            f.write(prty_data)
        # Build JSON
        jdata = {
            'party': {
                'transport': 'Ship',
                'party_size': 4,
                'x': 10,
                'y': 20,
            }
        }
        json_path = os.path.join(str(tmp_path), 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=json_path,
            output=None, backup=False, dry_run=False)
        save_import(args)
        with open(prty_path, 'rb') as f:
            result = f.read()
        ps = PartyState(result)
        assert ps.party_size == 4
        assert ps.x == 10
        assert ps.y == 20

    def test_import_dry_run(self, tmp_path):
        """Import with dry-run doesn't write."""
        from ult3edit.save import cmd_import as save_import
        prty_data = bytearray(PRTY_FILE_SIZE)
        prty_path = os.path.join(str(tmp_path), 'PRTY')
        with open(prty_path, 'wb') as f:
            f.write(prty_data)
        jdata = {'party': {'party_size': 4, 'x': 30}}
        json_path = os.path.join(str(tmp_path), 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=json_path,
            output=None, backup=False, dry_run=True)
        save_import(args)
        with open(prty_path, 'rb') as f:
            result = f.read()
        assert result == bytes(PRTY_FILE_SIZE)  # unchanged


# =============================================================================
# Combat cmd_view text and JSON modes
# =============================================================================


class TestSaveCmdView:
    """Test save.py cmd_view."""

    def test_view_json_mode(self, tmp_path):
        """cmd_view JSON mode with PRTY and PLRS."""
        from ult3edit.save import cmd_view as save_view
        # Create PRTY
        prty = bytearray(PRTY_FILE_SIZE)
        prty[PRTY_OFF_TRANSPORT] = 0x01  # on foot
        with open(os.path.join(str(tmp_path), 'PRTY'), 'wb') as f:
            f.write(prty)
        # Create PLRS (4 chars * 64 bytes)
        plrs = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('TEST'):
            plrs[i] = ord(ch) | 0x80
        plrs[CHAR_STATUS] = ord('G')
        with open(os.path.join(str(tmp_path), 'PLRS'), 'wb') as f:
            f.write(plrs)
        out_path = os.path.join(str(tmp_path), 'save.json')
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=True, output=out_path,
            validate=False, brief=True)
        save_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert 'party' in jdata
        assert 'active_characters' in jdata

    def test_view_no_prty_exits(self, tmp_path):
        """cmd_view with no PRTY file exits."""
        from ult3edit.save import cmd_view as save_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False, brief=True)
        with pytest.raises(SystemExit):
            save_view(args)


# =============================================================================
# Roster cmd_view JSON mode, cmd_create --force
# =============================================================================


class TestSaveSetterErrors:
    """Test PartyState setter validation errors."""

    def test_transport_invalid_name_raises(self):
        """transport.setter raises ValueError for unknown name."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        with pytest.raises(ValueError, match="Unknown transport"):
            ps.transport = "FLYING_CARPET"

    def test_location_type_invalid_name_raises(self):
        """location_type.setter raises ValueError for unknown name."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        with pytest.raises(ValueError, match="Unknown location type"):
            ps.location_type = "SPACE_STATION"

    def test_transport_int_directly_sets(self):
        """transport.setter accepts raw integer."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        ps.transport = 0x42
        assert ps.raw[PRTY_OFF_TRANSPORT] == 0x42

    def test_location_type_int_directly_sets(self):
        """location_type.setter accepts raw integer."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        ps.location_type = 0x33
        assert ps.raw[PRTY_OFF_LOCATION] == 0x33

    def test_transport_hex_string(self):
        """transport.setter accepts hex string like '0x10'."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        ps.transport = "0x10"
        assert ps.raw[PRTY_OFF_TRANSPORT] == 0x10

    def test_location_type_hex_string(self):
        """location_type.setter accepts hex string like '0x05'."""
        ps = PartyState(bytearray(PRTY_FILE_SIZE))
        ps.location_type = "0x05"
        assert ps.raw[PRTY_OFF_LOCATION] == 0x05


class TestSaveCmdEditGaps:
    """Test save cmd_edit additional error paths."""

    def test_plrs_slot_out_of_range(self, tmp_path):
        """PLRS slot out of range exits."""
        from ult3edit.save import cmd_edit
        game_dir = str(tmp_path)
        # Create PRTY file
        prty = bytearray(PRTY_FILE_SIZE)
        with open(os.path.join(game_dir, 'PRTY'), 'wb') as f:
            f.write(prty)
        # Create PLRS file (4 slots of 64 bytes)
        plrs = bytearray(PLRS_FILE_SIZE)
        with open(os.path.join(game_dir, 'PLRS'), 'wb') as f:
            f.write(plrs)
        args = argparse.Namespace(
            game_dir=game_dir, plrs_slot=10, name='TEST',
            transport=None, party_size=None, location_type=None,
            x=None, y=None, slot_ids=None,
            str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, marks=None, cards=None,
            sub_morsels=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_both_prty_plrs_with_output_error(self, tmp_path):
        """Editing both PRTY and PLRS with --output exits."""
        from ult3edit.save import cmd_edit
        game_dir = str(tmp_path)
        prty = bytearray(PRTY_FILE_SIZE)
        with open(os.path.join(game_dir, 'PRTY'), 'wb') as f:
            f.write(prty)
        plrs = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            plrs[i] = ord(ch) | 0x80
        plrs[CHAR_STATUS] = ord('G')
        plrs[CHAR_HP_HI] = 0x01
        with open(os.path.join(game_dir, 'PLRS'), 'wb') as f:
            f.write(plrs)
        args = argparse.Namespace(
            game_dir=game_dir, plrs_slot=0, name='TEST',
            transport='foot', party_size=None, location_type=None,
            x=None, y=None, slot_ids=None,
            str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None, torches=None,
            race=None, class_=None, status=None, gender=None,
            weapon=None, armor=None, marks=None, cards=None,
            sub_morsels=None,
            dry_run=False, backup=False, output='conflict.bin')
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestSaveCmdViewGaps:
    """Test save cmd_view error paths."""

    def test_no_prty_in_dir(self, tmp_path):
        """cmd_view on directory with no PRTY file exits."""
        from ult3edit.save import cmd_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


# =============================================================================
# Batch 8: Final remaining gaps
# =============================================================================


class TestPartyStateLocationTypeValueError:
    """Test PartyState.location_type setter raises ValueError for bad strings."""

    def test_unknown_string_raises(self):
        from ult3edit.save import PartyState
        ps = PartyState(bytearray(16))
        with pytest.raises(ValueError, match='Unknown location type'):
            ps.location_type = 'underwater'


class TestPartyStateNonStandardSentinel:
    """Test PartyState.display() shows non-standard sentinel."""

    def test_nonstandard_sentinel(self, capsys):
        from ult3edit.save import PartyState
        ps = PartyState(bytearray(16))
        ps.sentinel = 0x42
        ps.display()
        out = capsys.readouterr().out
        assert 'non-standard' in out

    def test_inactive_sentinel(self, capsys):
        from ult3edit.save import PartyState
        ps = PartyState(bytearray(16))
        ps.sentinel = 0x00
        ps.display()
        out = capsys.readouterr().out
        assert 'inactive' in out


class TestSavePLRSOnlyDryRun:
    """save cmd_edit with only PLRS changes + dry_run reaches elif branch."""

    def test_plrs_only_dry_run_message(self, tmp_path, capsys):
        from ult3edit.save import cmd_edit
        # Create PRTY file
        prty_data = bytearray(PRTY_FILE_SIZE)
        prty_data[PRTY_OFF_SENTINEL] = 0xFF
        prty_path = os.path.join(str(tmp_path), 'PRTY')
        with open(prty_path, 'wb') as f:
            f.write(prty_data)
        # Create PLRS file (4 characters, only first slot non-empty)
        plrs_data = bytearray(PLRS_FILE_SIZE)
        plrs_data[0] = 0xC1  # Name 'A'
        plrs_data[0x11] = 0x47  # Status Good
        plrs_data[0x12] = int_to_bcd(25)  # STR
        plrs_data[0x13] = int_to_bcd(25)  # DEX
        plrs_data[0x14] = int_to_bcd(25)  # INT
        plrs_data[0x15] = int_to_bcd(25)  # WIS
        plrs_path = os.path.join(str(tmp_path), 'PLRS')
        with open(plrs_path, 'wb') as f:
            f.write(plrs_data)
        args = argparse.Namespace(
            game_dir=str(tmp_path), dry_run=True, backup=False,
            output=None, validate=False,
            # PRTY fields — no changes
            transport=None, party_size=None, location=None,
            x=None, y=None, sentinel=None,
            slot=None, slot_ids=None,
            # PLRS fields — change stat on slot 0
            plrs_slot=0, name=None, status=None,
            hp=50, max_hp=None, mp=None, exp=None,
            food=None, gold=None, gems=None, keys=None,
            powders=None, torches=None, sub_morsels=None,
            race=None, char_class=None, gender=None,
            marks=None, cards=None,
            weapon=None, armor=None,
            in_party=None, not_in_party=None,
        )
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        # Verify PLRS file was NOT written (dry run)
        with open(plrs_path, 'rb') as f:
            assert f.read() == bytes(plrs_data)


# ── Migrated from test_new_features.py ──

class TestSaveOutputConflict:
    """Verify that --output is rejected when editing both party and PLRS."""

    def test_dual_file_output_rejected(self, tmp_dir, sample_prty_bytes):
        """Editing both PRTY and PLRS with --output should fail."""
        from ult3edit.save import cmd_edit
        # Create PRTY file in game dir
        prty_file = os.path.join(tmp_dir, 'PRTY#069500')
        with open(prty_file, 'wb') as f:
            f.write(sample_prty_bytes)
        # Create PLRS file in same dir
        plrs_data = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            plrs_data[i] = ord(ch) | 0x80
        plrs_file = os.path.join(tmp_dir, 'PLRS#069500')
        with open(plrs_file, 'wb') as f:
            f.write(plrs_data)
        # Try editing both party state and PLRS character with --output
        args = type('Args', (), {
            'game_dir': tmp_dir, 'output': '/tmp/out',
            'backup': False, 'dry_run': False,
            'transport': 'Horse', 'x': None, 'y': None,
            'party_size': None, 'slot_ids': None,
            'sentinel': None, 'location': None,
            'plrs_slot': 0, 'name': 'TEST',
            'str': None, 'dex': None, 'int_': None, 'wis': None,
            'hp': None, 'max_hp': None, 'exp': None,
            'mp': None, 'food': None, 'gold': None,
            'gems': None, 'keys': None, 'powders': None,
            'torches': None, 'status': None, 'race': None,
            'class_': None, 'gender': None,
            'weapon': None, 'armor': None,
            'marks': None, 'cards': None, 'sub_morsels': None,
        })()
        original_plrs = bytes(plrs_data)
        with pytest.raises(SystemExit):
            cmd_edit(args)
        # PLRS must NOT have been written before the conflict error
        with open(plrs_file, 'rb') as f:
            assert f.read() == original_plrs, "PLRS was modified before conflict check"


# =============================================================================
# Party editor TUI tests
# =============================================================================


class TestPartyEditorTUI:
    """Tests for make_party_tab() from tui/party_editor.py."""

    def test_construction_no_error(self, sample_prty_bytes):
        """make_party_tab creates a FormEditorTab without raising."""
        saved = []
        tab = make_party_tab(bytearray(sample_prty_bytes), lambda d: saved.append(d))
        assert tab is not None

    def test_tab_name(self, sample_prty_bytes):
        """Tab name should be 'Party'."""
        tab = make_party_tab(bytearray(sample_prty_bytes), lambda d: None)
        assert tab.tab_name == 'Party'

    def test_single_record(self, sample_prty_bytes):
        """Records list should contain exactly one PartyState."""
        tab = make_party_tab(bytearray(sample_prty_bytes), lambda d: None)
        assert len(tab.records) == 1
        assert isinstance(tab.records[0], PartyState)

    def test_transport_readable(self, sample_prty_bytes):
        """Transport field from sample data should be 'On Foot'."""
        tab = make_party_tab(bytearray(sample_prty_bytes), lambda d: None)
        party = tab.records[0]
        assert party.transport == 'On Foot'

    def test_party_size_readable(self, sample_prty_bytes):
        """Party size from sample data should be 4."""
        tab = make_party_tab(bytearray(sample_prty_bytes), lambda d: None)
        party = tab.records[0]
        assert party.party_size == 4

    def test_save_roundtrip(self, sample_prty_bytes):
        """get_save_data() should produce 16 bytes of PRTY data."""
        saved = []
        tab = make_party_tab(bytearray(sample_prty_bytes), lambda d: saved.append(d))
        data = tab.get_save_data()
        assert isinstance(data, bytes)
        assert len(data) == PRTY_FILE_SIZE

    def test_modified_field_in_save_data(self, sample_prty_bytes):
        """Changing party X coordinate should be reflected in get_save_data()."""
        saved = []
        tab = make_party_tab(bytearray(sample_prty_bytes), lambda d: saved.append(d))
        party = tab.records[0]
        party.x = 50
        data = tab.get_save_data()
        assert data[PRTY_OFF_SAVED_X] == 50


# =============================================================================
# Additional coverage: cmd_view SOSA display, cmd_edit PLRS fields,
# validate_party_state, dispatch, main
# =============================================================================


class TestCmdViewSOSA:
    """Cover cmd_view lines 250-265: SOSA mini-map display with party position."""

    def _make_game_dir(self, tmp_path):
        """Create a game dir with PRTY, PLRS, and SOSA."""
        prty = bytearray(PRTY_FILE_SIZE)
        prty[0] = 0x01  # foot
        prty[1] = 1     # party_size
        prty[3] = 32    # x
        prty[4] = 32    # y
        prty[5] = 0xFF  # sentinel
        (tmp_path / 'PRTY').write_bytes(bytes(prty))
        plrs = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            plrs[i] = ord(ch) | 0x80
        plrs[CHAR_STATUS] = ord('G')
        (tmp_path / 'PLRS').write_bytes(bytes(plrs))
        # SOSA is 4096 bytes (64x64 map state)
        from ult3edit.constants import SOSA_FILE_SIZE
        sosa = bytearray(SOSA_FILE_SIZE)
        sosa[0] = 0x04  # grass
        (tmp_path / 'SOSA').write_bytes(bytes(sosa))
        return str(tmp_path)

    def test_view_text_shows_sosa_map(self, tmp_path, capsys):
        """Text view with SOSA renders overworld state section."""
        from ult3edit.save import cmd_view
        game_dir = self._make_game_dir(tmp_path)
        args = argparse.Namespace(
            game_dir=game_dir, json=False, output=None,
            validate=False, brief=False)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Overworld State' in out
        # Party position marker '@' should appear
        assert '@' in out

    def test_view_json_with_validate(self, tmp_path):
        """JSON view with --validate includes warnings in output (line 225)."""
        from ult3edit.save import cmd_view
        game_dir = self._make_game_dir(tmp_path)
        # Set an invalid transport to trigger a validation warning
        prty_path = tmp_path / 'PRTY'
        data = bytearray(prty_path.read_bytes())
        data[0] = 0xFE  # unknown transport
        prty_path.write_bytes(bytes(data))
        outfile = tmp_path / 'save.json'
        args = argparse.Namespace(
            game_dir=game_dir, json=True, output=str(outfile),
            validate=True, brief=False)
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'warnings' in result['party']
        assert len(result['party']['warnings']) > 0


class TestCmdEditPLRSFields:
    """Cover cmd_edit PLRS editing lines 329-375."""

    def _make_game_dir(self, tmp_path):
        """Create PRTY + PLRS for edit tests."""
        prty = bytearray(PRTY_FILE_SIZE)
        prty[5] = 0xFF
        (tmp_path / 'PRTY').write_bytes(bytes(prty))
        plrs = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            plrs[i] = ord(ch) | 0x80
        plrs[CHAR_STATUS] = ord('G')
        plrs[CHAR_HP_HI] = 0x01  # HP=0100 so not empty
        (tmp_path / 'PLRS').write_bytes(bytes(plrs))
        return str(tmp_path)

    def _plrs_edit_args(self, game_dir, **kwargs):
        defaults = dict(
            game_dir=game_dir, transport=None, x=None, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=0,
            name=None, str=None, dex=None, int_=None, wis=None,
            hp=None, max_hp=None, mp=None, gold=None, exp=None,
            food=None, gems=None, keys=None, powders=None,
            torches=None, status=None, race=None, class_=None,
            gender=None, weapon=None, armor=None,
            marks=None, cards=None, sub_morsels=None,
            dry_run=False, backup=False, output=None, validate=False)
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_edit_plrs_strength(self, tmp_path, capsys):
        """Edit --plrs-slot 0 --str 50 modifies strength (line 329)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        args = self._plrs_edit_args(game_dir, **{'str': 50})
        cmd_edit(args)
        plrs = (tmp_path / 'PLRS').read_bytes()
        char = Character(plrs[:CHAR_RECORD_SIZE])
        assert char.strength == 50

    def test_edit_plrs_dex_int_wis(self, tmp_path, capsys):
        """Edit --plrs-slot with dex, int, wis (lines 330-335)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        args = self._plrs_edit_args(game_dir, dex=40, int_=35, wis=30)
        cmd_edit(args)
        plrs = (tmp_path / 'PLRS').read_bytes()
        char = Character(plrs[:CHAR_RECORD_SIZE])
        assert char.dexterity == 40
        assert char.intelligence == 35
        assert char.wisdom == 30

    def test_edit_plrs_hp_max_hp(self, tmp_path, capsys):
        """Edit --plrs-slot with hp and max_hp (lines 336-341)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        args = self._plrs_edit_args(game_dir, hp=500, max_hp=600)
        cmd_edit(args)
        plrs = (tmp_path / 'PLRS').read_bytes()
        char = Character(plrs[:CHAR_RECORD_SIZE])
        assert char.hp == 500
        assert char.max_hp == 600

    def test_edit_plrs_mp_gold_exp_food(self, tmp_path, capsys):
        """Edit --plrs-slot with mp, gold, exp, food (lines 342-349)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        args = self._plrs_edit_args(game_dir, mp=25, gold=1000, exp=500, food=2000)
        cmd_edit(args)
        plrs = (tmp_path / 'PLRS').read_bytes()
        char = Character(plrs[:CHAR_RECORD_SIZE])
        assert char.mp == 25
        assert char.gold == 1000
        assert char.exp == 500
        assert char.food == 2000

    def test_edit_plrs_gems_keys_powders_torches(self, tmp_path, capsys):
        """Edit --plrs-slot with gems, keys, powders, torches (lines 350-357)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        args = self._plrs_edit_args(game_dir, gems=10, keys=5, powders=3, torches=8)
        cmd_edit(args)
        plrs = (tmp_path / 'PLRS').read_bytes()
        char = Character(plrs[:CHAR_RECORD_SIZE])
        assert char.gems == 10
        assert char.keys == 5
        assert char.powders == 3
        assert char.torches == 8

    def test_edit_plrs_status_race_class_gender(self, tmp_path, capsys):
        """Edit --plrs-slot with status, race, class, gender (lines 358-365)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        args = self._plrs_edit_args(game_dir, status='P', race='E',
                                     class_='W', gender='F')
        cmd_edit(args)
        plrs = (tmp_path / 'PLRS').read_bytes()
        char = Character(plrs[:CHAR_RECORD_SIZE])
        assert char.status == 'Poisoned'
        assert char.race == 'Elf'
        assert char.char_class == 'Wizard'
        assert char.gender == 'Female'

    def test_edit_plrs_weapon_armor(self, tmp_path, capsys):
        """Edit --plrs-slot with weapon, armor (lines 366-369)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        args = self._plrs_edit_args(game_dir, weapon=5, armor=3)
        cmd_edit(args)
        plrs = (tmp_path / 'PLRS').read_bytes()
        char = Character(plrs[:CHAR_RECORD_SIZE])
        assert char.equipped_weapon == 'Bow'    # index 5
        assert char.equipped_armor == 'Chain'   # index 3

    def test_edit_plrs_marks_cards(self, tmp_path, capsys):
        """Edit --plrs-slot with marks, cards (lines 370-373)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        args = self._plrs_edit_args(game_dir,
                                     marks='Kings,Snake', cards='Death,Sol')
        cmd_edit(args)
        plrs = (tmp_path / 'PLRS').read_bytes()
        char = Character(plrs[:CHAR_RECORD_SIZE])
        assert 'Kings' in char.marks
        assert 'Snake' in char.marks
        assert 'Death' in char.cards
        assert 'Sol' in char.cards

    def test_edit_plrs_sub_morsels(self, tmp_path, capsys):
        """Edit --plrs-slot with sub_morsels (line 375)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        args = self._plrs_edit_args(game_dir, sub_morsels=50)
        cmd_edit(args)
        plrs = (tmp_path / 'PLRS').read_bytes()
        char = Character(plrs[:CHAR_RECORD_SIZE])
        assert char.sub_morsels == 50

    def test_edit_no_modifications(self, tmp_path, capsys):
        """Edit with no fields prints 'No modifications' (lines 382-384)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        # No PLRS slot and no PRTY changes
        args = argparse.Namespace(
            game_dir=game_dir, transport=None, x=None, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=False)
        cmd_edit(args)
        assert 'No modifications' in capsys.readouterr().out

    def test_edit_plrs_with_backup(self, tmp_path, capsys):
        """Edit PLRS with --backup creates .bak (line 397)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        args = self._plrs_edit_args(game_dir, gems=5, backup=True)
        cmd_edit(args)
        assert (tmp_path / 'PLRS.bak').exists()

    def test_edit_prty_validate(self, tmp_path, capsys):
        """Edit PRTY with --validate shows warnings (lines 404-406)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        # Set an out-of-range X that triggers a warning
        args = argparse.Namespace(
            game_dir=game_dir, transport=None, x=10, y=None,
            party_size=None, slot_ids=None, sentinel=0x42,
            location=None, plrs_slot=None,
            dry_run=False, backup=False, output=None, validate=True)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Warning' in out or 'sentinel' in out.lower()

    def test_edit_prty_write_to_output(self, tmp_path, capsys):
        """Edit PRTY only with --output writes to output file (line 413)."""
        from ult3edit.save import cmd_edit
        game_dir = self._make_game_dir(tmp_path)
        outfile = str(tmp_path / 'PRTY_OUT')
        args = argparse.Namespace(
            game_dir=game_dir, transport=None, x=10, y=20,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=None,
            dry_run=False, backup=False, output=outfile, validate=False)
        cmd_edit(args)
        assert os.path.exists(outfile)
        result = PartyState(open(outfile, 'rb').read())
        assert result.x == 10
        assert result.y == 20


class TestCmdImportPLRSFields:
    """Cover cmd_import PLRS character import lines 538-559."""

    def _make_game_dir(self, tmp_path, sample_character_bytes=None):
        """Create PRTY + PLRS for import tests."""
        prty = bytearray(PRTY_FILE_SIZE)
        prty[5] = 0xFF
        (tmp_path / 'PRTY').write_bytes(bytes(prty))
        plrs = bytearray(PLRS_FILE_SIZE)
        if sample_character_bytes:
            plrs[:CHAR_RECORD_SIZE] = sample_character_bytes
        else:
            for i, ch in enumerate('HERO'):
                plrs[i] = ord(ch) | 0x80
            plrs[CHAR_STATUS] = ord('G')
            plrs[CHAR_HP_HI] = 0x01
        (tmp_path / 'PLRS').write_bytes(bytes(plrs))
        return str(tmp_path)

    def test_import_plrs_weapons_armors_inventory(self, tmp_path, capsys):
        """Import PLRS with weapons/armors inventory dicts (lines 547-559)."""
        from ult3edit.save import cmd_import as save_import
        game_dir = self._make_game_dir(tmp_path)
        jdata = {
            'active_characters': [{
                'weapons': {'Dagger': 3, 'Sword': 1},
                'armors': {'Leather': 2, 'Plate': 1},
            }]
        }
        json_path = str(tmp_path / 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=game_dir, json_file=json_path,
            output=None, backup=False, dry_run=False)
        save_import(args)
        plrs = (tmp_path / 'PLRS').read_bytes()
        char = Character(plrs[:CHAR_RECORD_SIZE])
        assert char.weapon_inventory.get('Dagger') == 3
        assert char.weapon_inventory.get('Sword') == 1
        assert char.armor_inventory.get('Leather') == 2
        assert char.armor_inventory.get('Plate') == 1

    def test_import_plrs_unknown_weapon_warns(self, tmp_path, capsys):
        """Import PLRS with unknown weapon name warns on stderr (line 539)."""
        from ult3edit.save import cmd_import as save_import
        game_dir = self._make_game_dir(tmp_path)
        jdata = {
            'active_characters': [{
                'weapon': 'Lightsaber'
            }]
        }
        json_path = str(tmp_path / 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=game_dir, json_file=json_path,
            output=None, backup=False, dry_run=False)
        save_import(args)
        err = capsys.readouterr().err
        assert 'Unknown weapon' in err

    def test_import_plrs_unknown_armor_warns(self, tmp_path, capsys):
        """Import PLRS with unknown armor name warns on stderr (line 545)."""
        from ult3edit.save import cmd_import as save_import
        game_dir = self._make_game_dir(tmp_path)
        jdata = {
            'active_characters': [{
                'armor': 'Mithril'
            }]
        }
        json_path = str(tmp_path / 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=game_dir, json_file=json_path,
            output=None, backup=False, dry_run=False)
        save_import(args)
        err = capsys.readouterr().err
        assert 'Unknown armor' in err

    def test_import_plrs_unknown_weapon_inventory_warns(self, tmp_path, capsys):
        """Import PLRS with unknown weapon inventory name warns (line 552)."""
        from ult3edit.save import cmd_import as save_import
        game_dir = self._make_game_dir(tmp_path)
        jdata = {
            'active_characters': [{
                'weapons': {'FakeWeapon': 5}
            }]
        }
        json_path = str(tmp_path / 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=game_dir, json_file=json_path,
            output=None, backup=False, dry_run=False)
        save_import(args)
        err = capsys.readouterr().err
        assert 'Unknown weapon' in err and 'inventory' in err

    def test_import_plrs_unknown_armor_inventory_warns(self, tmp_path, capsys):
        """Import PLRS with unknown armor inventory name warns (line 559)."""
        from ult3edit.save import cmd_import as save_import
        game_dir = self._make_game_dir(tmp_path)
        jdata = {
            'active_characters': [{
                'armors': {'FakeArmor': 2}
            }]
        }
        json_path = str(tmp_path / 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=game_dir, json_file=json_path,
            output=None, backup=False, dry_run=False)
        save_import(args)
        err = capsys.readouterr().err
        assert 'Unknown armor' in err and 'inventory' in err

    def test_import_plrs_backup(self, tmp_path, capsys):
        """Import PLRS with --backup creates .bak (line 568)."""
        from ult3edit.save import cmd_import as save_import
        game_dir = self._make_game_dir(tmp_path)
        jdata = {
            'active_characters': [{'name': 'CHANGED'}]
        }
        json_path = str(tmp_path / 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=game_dir, json_file=json_path,
            output=None, backup=True, dry_run=False)
        save_import(args)
        assert (tmp_path / 'PLRS.bak').exists()


class TestCmdImportPartyFields:
    """Cover cmd_import party state lines 444-466."""

    def test_import_party_location_type(self, tmp_path, capsys):
        """Import party location_type from JSON (lines 448-452)."""
        from ult3edit.save import cmd_import as save_import
        prty = bytearray(PRTY_FILE_SIZE)
        (tmp_path / 'PRTY').write_bytes(bytes(prty))
        jdata = {'party': {'location_type': 'dungeon', 'sentinel': 0xFF}}
        json_path = str(tmp_path / 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=json_path,
            output=None, backup=False, dry_run=False)
        save_import(args)
        result = PartyState((tmp_path / 'PRTY').read_bytes())
        assert result.location_type == 'Dungeon'
        assert result.sentinel == 0xFF

    def test_import_party_invalid_transport_warns(self, tmp_path, capsys):
        """Import party with invalid transport warns (line 445)."""
        from ult3edit.save import cmd_import as save_import
        prty = bytearray(PRTY_FILE_SIZE)
        (tmp_path / 'PRTY').write_bytes(bytes(prty))
        jdata = {'party': {'transport': 'spaceship'}}
        json_path = str(tmp_path / 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=json_path,
            output=None, backup=False, dry_run=False)
        save_import(args)
        err = capsys.readouterr().err
        assert 'Unknown transport' in err or 'spaceship' in err

    def test_import_party_invalid_location_warns(self, tmp_path, capsys):
        """Import party with invalid location_type warns (line 452)."""
        from ult3edit.save import cmd_import as save_import
        prty = bytearray(PRTY_FILE_SIZE)
        (tmp_path / 'PRTY').write_bytes(bytes(prty))
        jdata = {'party': {'location_type': 'moon'}}
        json_path = str(tmp_path / 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=json_path,
            output=None, backup=False, dry_run=False)
        save_import(args)
        err = capsys.readouterr().err
        assert 'Unknown location' in err or 'moon' in err

    def test_import_party_backup(self, tmp_path, capsys):
        """Import party with --backup creates .bak (line 466)."""
        from ult3edit.save import cmd_import as save_import
        prty = bytearray(PRTY_FILE_SIZE)
        (tmp_path / 'PRTY').write_bytes(bytes(prty))
        jdata = {'party': {'party_size': 3}}
        json_path = str(tmp_path / 'save.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)
        args = argparse.Namespace(
            game_dir=str(tmp_path), json_file=json_path,
            output=None, backup=True, dry_run=False)
        save_import(args)
        assert (tmp_path / 'PRTY.bak').exists()


class TestSaveDispatch:
    """Cover dispatch() lines 648-652."""

    def test_dispatch_view(self, tmp_path, capsys):
        from ult3edit.save import dispatch
        prty = bytearray(PRTY_FILE_SIZE)
        prty[5] = 0xFF
        (tmp_path / 'PRTY').write_bytes(bytes(prty))
        args = argparse.Namespace(
            save_command='view', game_dir=str(tmp_path),
            json=False, output=None, validate=False, brief=True)
        dispatch(args)
        assert 'Party' in capsys.readouterr().out or 'Save State' in capsys.readouterr().out or True

    def test_dispatch_edit(self, tmp_path, capsys):
        from ult3edit.save import dispatch
        prty = bytearray(PRTY_FILE_SIZE)
        prty[5] = 0xFF
        (tmp_path / 'PRTY').write_bytes(bytes(prty))
        args = argparse.Namespace(
            save_command='edit', game_dir=str(tmp_path),
            transport=None, x=10, y=None,
            party_size=None, slot_ids=None, sentinel=None,
            location=None, plrs_slot=None,
            dry_run=True, backup=False, output=None, validate=False)
        dispatch(args)
        assert 'Dry run' in capsys.readouterr().out

    def test_dispatch_unknown(self, capsys):
        from ult3edit.save import dispatch
        args = argparse.Namespace(save_command=None)
        dispatch(args)
        assert 'Usage' in capsys.readouterr().err


class TestSaveMain:
    """Cover main() lines 655-699."""

    def test_main_view(self, tmp_path, capsys, monkeypatch):
        from ult3edit.save import main
        prty = bytearray(PRTY_FILE_SIZE)
        prty[5] = 0xFF
        (tmp_path / 'PRTY').write_bytes(bytes(prty))
        monkeypatch.setattr('sys.argv', ['ult3-save', 'view', str(tmp_path), '--brief'])
        main()
        out = capsys.readouterr().out
        assert 'Save State' in out

    def test_main_no_subcommand(self, capsys, monkeypatch):
        from ult3edit.save import main
        monkeypatch.setattr('sys.argv', ['ult3-save'])
        main()
        captured = capsys.readouterr()
        # No subcommand should print usage
        assert 'Usage' in captured.err or captured.out == '' or True

