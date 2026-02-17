"""Tests for equipment reference tool."""

from u3edit.constants import (
    WEAPONS, ARMORS, WEAPON_DAMAGE, WEAPON_PRICE, ARMOR_EVASION,
    CLASS_MAX_WEAPON, CLASS_MAX_ARMOR, CLASSES,
)


class TestWeaponStats:
    def test_damage_count_matches(self):
        assert len(WEAPON_DAMAGE) == len(WEAPONS)

    def test_price_count_matches(self):
        assert len(WEAPON_PRICE) == len(WEAPONS)

    def test_hands_free(self):
        assert WEAPON_DAMAGE[0] == 0
        assert WEAPON_PRICE[0] == 0

    def test_exotic_best(self):
        assert WEAPON_DAMAGE[-1] == max(WEAPON_DAMAGE)


class TestArmorStats:
    def test_evasion_count_matches(self):
        assert len(ARMOR_EVASION) == len(ARMORS)

    def test_evasion_range(self):
        for ev in ARMOR_EVASION:
            assert 0 < ev <= 100

    def test_exotic_best(self):
        assert ARMOR_EVASION[-1] == max(ARMOR_EVASION)


class TestClassRestrictions:
    def test_all_classes_covered(self):
        for cls in CLASSES.values():
            assert cls in CLASS_MAX_WEAPON
            assert cls in CLASS_MAX_ARMOR

    def test_indices_valid(self):
        for cls, idx in CLASS_MAX_WEAPON.items():
            assert 0 <= idx < len(WEAPONS)
        for cls, idx in CLASS_MAX_ARMOR.items():
            assert 0 <= idx < len(ARMORS)

    def test_wizard_limited(self):
        assert CLASS_MAX_WEAPON['Wizard'] <= 2  # Dagger or less
        assert CLASS_MAX_ARMOR['Wizard'] <= 2  # Cloth or less
