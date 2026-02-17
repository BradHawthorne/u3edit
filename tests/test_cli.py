"""Tests for unified CLI dispatcher."""

import json
import subprocess
import sys


class TestCLI:
    def test_help(self):
        result = subprocess.run(
            [sys.executable, '-m', 'u3edit', '--help'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'roster' in result.stdout
        assert 'bestiary' in result.stdout
        assert 'spell' in result.stdout
        assert 'equip' in result.stdout
        assert 'disk' in result.stdout

    def test_version(self):
        result = subprocess.run(
            [sys.executable, '-m', 'u3edit', '--version'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'u3edit' in result.stdout

    def test_no_args_shows_help(self):
        result = subprocess.run(
            [sys.executable, '-m', 'u3edit'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'usage' in result.stdout.lower() or 'positional' in result.stdout.lower()

    def test_spell_view(self):
        result = subprocess.run(
            [sys.executable, '-m', 'u3edit', 'spell', 'view'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'Wizard Spells' in result.stdout
        assert 'Cleric Spells' in result.stdout

    def test_equip_view(self):
        result = subprocess.run(
            [sys.executable, '-m', 'u3edit', 'equip', 'view'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'Weapons' in result.stdout
        assert 'Armor' in result.stdout

    def test_spell_json(self):
        result = subprocess.run(
            [sys.executable, '-m', 'u3edit', 'spell', 'view', '--json'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert 'wizard' in data
        assert len(data['wizard']) == 16

    def test_equip_json(self):
        result = subprocess.run(
            [sys.executable, '-m', 'u3edit', 'equip', 'view', '--json'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert 'weapons' in data
        assert 'armors' in data

    def test_all_subcommands_in_help(self):
        result = subprocess.run(
            [sys.executable, '-m', 'u3edit', '--help'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        for cmd in ['roster', 'bestiary', 'map', 'tlk', 'combat',
                     'save', 'special', 'text', 'spell', 'equip', 'disk']:
            assert cmd in result.stdout, f"Missing subcommand '{cmd}' in help"
