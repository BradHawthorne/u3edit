"""Tests for spell reference tool."""

from u3edit.constants import WIZARD_SPELLS, CLERIC_SPELLS


class TestSpellLists:
    def test_wizard_count(self):
        assert len(WIZARD_SPELLS) == 16

    def test_cleric_count(self):
        assert len(CLERIC_SPELLS) == 16

    def test_all_have_names(self):
        for name, cost in WIZARD_SPELLS + CLERIC_SPELLS:
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(cost, int) and cost >= 0

    def test_mp_costs_reasonable(self):
        for name, cost in WIZARD_SPELLS + CLERIC_SPELLS:
            assert 0 <= cost <= 100
