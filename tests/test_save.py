"""Tests for save state tool."""

import argparse
import os
import pytest

from u3edit.save import PartyState, cmd_edit
from u3edit.constants import PRTY_FILE_SIZE


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
