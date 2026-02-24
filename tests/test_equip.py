"""Tests for equipment reference tool."""

import argparse
import json
import os

from ult3edit.constants import (
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


# ── Migrated from test_new_features.py ──

class TestEquipView:
    """Test equip.py cmd_view."""

    def test_view_text_output(self, capsys):
        """cmd_view in text mode outputs weapon and armor tables."""
        from ult3edit.equip import cmd_view
        args = argparse.Namespace(json=False, output=None)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Weapons' in captured.out
        assert 'Armor' in captured.out
        assert 'Class Equipment Restrictions' in captured.out

    def test_view_json_output(self, tmp_path):
        """cmd_view in JSON mode produces valid structured data."""
        from ult3edit.equip import cmd_view
        out_path = os.path.join(str(tmp_path), 'equip.json')
        args = argparse.Namespace(json=True, output=out_path)
        cmd_view(args)
        with open(out_path) as f:
            data = json.load(f)
        assert 'weapons' in data
        assert 'armors' in data
        assert 'class_restrictions' in data
        assert len(data['weapons']) > 0
        assert 'damage' in data['weapons'][0]

    def test_dispatch_no_command(self, capsys):
        """dispatch with no subcommand prints usage."""
        from ult3edit.equip import dispatch
        args = argparse.Namespace(equip_command=None)
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err


# =============================================================================
# Coverage: equip.py lines 78-87 — main() standalone entry point
# =============================================================================


class TestEquipMain:
    """Cover lines 78-87: main() standalone entry point."""

    def test_main_view(self, capsys):
        from ult3edit.equip import main
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-equip', 'view']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Weapons' in out
        assert 'Armor' in out

    def test_main_view_json(self, tmp_path, capsys):
        from ult3edit.equip import main
        outfile = tmp_path / 'equip.json'
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-equip', 'view', '--json', '--output', str(outfile)]
        try:
            main()
        finally:
            sys.argv = old_argv
        result = json.loads(outfile.read_text())
        assert 'weapons' in result
        assert 'armors' in result

    def test_main_no_subcommand(self, capsys):
        from ult3edit.equip import main
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-equip']
        try:
            main()
        finally:
            sys.argv = old_argv
        err = capsys.readouterr().err
        assert 'Usage' in err or 'usage' in err.lower() or 'equip' in err.lower()


# =============================================================================
# Spell reference (spell.py)
# =============================================================================

