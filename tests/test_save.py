"""Tests for save state tool."""

import pytest

from u3edit.save import PartyState
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
