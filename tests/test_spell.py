"""Tests for spell reference tool."""

import argparse
import json
import os

from ult3edit.constants import WIZARD_SPELLS, CLERIC_SPELLS


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


# ── Migrated from test_new_features.py ──

class TestSpellView:
    """Test spell.py cmd_view."""

    def test_view_all_spells(self, capsys):
        """cmd_view shows both wizard and cleric spells."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            wizard_only=False, cleric_only=False)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Wizard Spells' in captured.out
        assert 'Cleric Spells' in captured.out

    def test_view_wizard_only(self, capsys):
        """cmd_view with --wizard-only hides cleric spells."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            wizard_only=True, cleric_only=False)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Wizard Spells' in captured.out
        assert 'Cleric Spells' not in captured.out

    def test_view_cleric_only(self, capsys):
        """cmd_view with --cleric-only hides wizard spells."""
        from ult3edit.spell import cmd_view
        args = argparse.Namespace(
            json=False, output=None,
            wizard_only=False, cleric_only=True)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'Wizard Spells' not in captured.out
        assert 'Cleric Spells' in captured.out

    def test_view_json_output(self, tmp_path):
        """cmd_view JSON mode produces structured spell data."""
        from ult3edit.spell import cmd_view
        out_path = os.path.join(str(tmp_path), 'spells.json')
        args = argparse.Namespace(
            json=True, output=out_path,
            wizard_only=False, cleric_only=False)
        cmd_view(args)
        with open(out_path) as f:
            data = json.load(f)
        assert 'wizard' in data
        assert 'cleric' in data
        assert len(data['wizard']) > 0
        assert 'mp' in data['wizard'][0]

    def test_dispatch_no_command(self, capsys):
        """dispatch with no subcommand prints usage."""
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command=None)
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err


# =============================================================================
# Diff module: core algorithm and per-type diff functions
# =============================================================================


class TestSpellDispatchFallback:
    """spell dispatch with unknown command prints usage."""

    def test_dispatch_unknown_command(self, capsys):
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command='unknown')
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err

    def test_dispatch_none_command(self, capsys):
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err


# =============================================================================
# Coverage: spell.py lines 59, 65-76 — dispatch view route and main()
# =============================================================================


class TestSpellDispatchView:
    """Cover line 59: dispatch routes spell_command='view' to cmd_view."""

    def test_dispatch_view_runs(self, capsys):
        from ult3edit.spell import dispatch
        args = argparse.Namespace(
            spell_command='view',
            json=False, output=None,
            wizard_only=False, cleric_only=False)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Wizard Spells' in out


class TestSpellMain:
    """Cover lines 65-76: main() standalone entry point."""

    def test_main_view(self, capsys):
        from ult3edit.spell import main
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-spell', 'view']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Wizard Spells' in out
        assert 'Cleric Spells' in out

    def test_main_view_wizard_only(self, capsys):
        from ult3edit.spell import main
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-spell', 'view', '--wizard-only']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Wizard Spells' in out
        assert 'Cleric Spells' not in out

    def test_main_view_json(self, tmp_path, capsys):
        from ult3edit.spell import main
        outfile = tmp_path / 'spells.json'
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-spell', 'view', '--json', '--output', str(outfile)]
        try:
            main()
        finally:
            sys.argv = old_argv
        result = json.loads(outfile.read_text())
        assert 'wizard' in result

    def test_main_no_subcommand(self, capsys):
        from ult3edit.spell import main
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-spell']
        try:
            main()
        finally:
            sys.argv = old_argv
        err = capsys.readouterr().err
        assert 'Usage' in err or 'usage' in err.lower() or 'spell' in err.lower()

