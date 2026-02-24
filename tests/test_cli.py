"""Tests for unified CLI dispatcher."""

import argparse
import json
import os
import subprocess
import sys


def _help_output(module: str, subcmd: str) -> str:
    """Get --help output from a standalone module entry point."""
    result = subprocess.run(
        [sys.executable, '-m', f'ult3edit.{module}', subcmd, '--help'],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout + result.stderr


class TestCLI:
    def test_help(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', '--help'],
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
            [sys.executable, '-m', 'ult3edit', '--version'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'ult3edit' in result.stdout

    def test_no_args_shows_help(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'usage' in result.stdout.lower() or 'positional' in result.stdout.lower()

    def test_spell_view(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', 'spell', 'view'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'Wizard Spells' in result.stdout
        assert 'Cleric Spells' in result.stdout

    def test_equip_view(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', 'equip', 'view'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert 'Weapons' in result.stdout
        assert 'Armor' in result.stdout

    def test_spell_json(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', 'spell', 'view', '--json'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert 'wizard' in data
        assert len(data['wizard']) == 16

    def test_equip_json(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', 'equip', 'view', '--json'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert 'weapons' in data
        assert 'armors' in data

    def test_all_subcommands_in_help(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', '--help'],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        for cmd in ['roster', 'bestiary', 'map', 'tlk', 'combat',
                     'save', 'special', 'text', 'spell', 'equip', 'disk',
                     'shapes', 'sound', 'patch', 'ddrw', 'diff', 'edit']:
            assert cmd in result.stdout, f"Missing subcommand '{cmd}' in help"

    def test_edit_missing_image(self):
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', 'edit', '/nonexistent/fake.po'],
            capture_output=True, text=True
        )
        assert result.returncode != 0
        assert 'not found' in result.stderr.lower() or 'error' in result.stderr.lower()


# ── Migrated from test_new_features.py ──

class TestCliParity:
    """Verify standalone main() parsers have full arg parity with register_parser()."""

    def test_roster_main_create_help(self):
        out = _help_output('roster', 'create')
        assert '--name' in out
        assert '--race' in out
        assert '--force' in out
        assert 'Overwrite existing' in out

    def test_bestiary_main_validate(self):
        out = _help_output('bestiary', 'view')
        assert '--validate' in out

    def test_map_main_set_exists(self):
        out = _help_output('map', 'set')
        assert '--tile' in out
        assert '--x' in out
        assert '--y' in out

    def test_map_main_import_exists(self):
        out = _help_output('map', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_map_main_fill_exists(self):
        out = _help_output('map', 'fill')
        assert '--x1' in out
        assert '--tile' in out

    def test_map_main_replace_exists(self):
        out = _help_output('map', 'replace')
        assert '--from' in out
        assert '--to' in out

    def test_map_main_find_exists(self):
        out = _help_output('map', 'find')
        assert '--tile' in out
        assert '--json' in out

    def test_combat_main_edit_exists(self):
        out = _help_output('combat', 'edit')
        assert '--tile' in out
        assert '--monster-pos' in out
        assert '--pc-pos' in out

    def test_combat_main_import_exists(self):
        out = _help_output('combat', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_combat_main_validate(self):
        out = _help_output('combat', 'view')
        assert '--validate' in out

    def test_special_main_edit_exists(self):
        out = _help_output('special', 'edit')
        assert '--tile' in out
        assert '--backup' in out

    def test_special_main_import_exists(self):
        out = _help_output('special', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_save_main_validate(self):
        out = _help_output('save', 'view')
        assert '--validate' in out

    def test_save_main_import_dryrun(self):
        out = _help_output('save', 'import')
        assert '--dry-run' in out
        assert '--backup' in out

    def test_text_main_import_exists(self):
        out = _help_output('text', 'import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_tlk_main_edit_help(self):
        out = _help_output('tlk', 'edit')
        assert '--find' in out
        assert '--replace' in out
        assert '--ignore-case' in out

    def test_spell_main_help(self):
        out = _help_output('spell', 'view')
        assert '--wizard-only' in out
        assert '--cleric-only' in out

    def test_equip_main_help(self):
        out = _help_output('equip', 'view')
        assert '--json' in out

    def test_shapes_main_export_help(self):
        out = _help_output('shapes', 'export')
        assert '--scale' in out
        assert '--sheet' in out
        assert 'Scale factor' in out

    def test_sound_main_import_dryrun(self):
        out = _help_output('sound', 'import')
        assert '--dry-run' in out
        assert '--backup' in out

    def test_patch_main_dump_help(self):
        out = _help_output('patch', 'dump')
        assert '--offset' in out
        assert '--length' in out
        assert 'Start offset' in out

    def test_ddrw_main_import_dryrun(self):
        out = _help_output('ddrw', 'import')
        assert '--dry-run' in out
        assert '--backup' in out

    def test_disk_main_info_help(self):
        out = _help_output('disk', 'info')
        assert '--json' in out
        assert 'image' in out.lower()

    def test_disk_main_list_help(self):
        out = _help_output('disk', 'list')
        assert '--json' in out
        assert '--path' in out

    def test_disk_main_extract_help(self):
        out = _help_output('disk', 'extract')
        assert 'image' in out.lower()

    def test_disk_main_audit_help(self):
        out = _help_output('disk', 'audit')
        assert '--json' in out
        assert '--detail' in out

    def test_diff_main_help(self):
        """diff module standalone main() has correct args."""
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit.diff', '--help'],
            capture_output=True, text=True, timeout=10)
        out = result.stdout + result.stderr
        assert 'path1' in out
        assert 'path2' in out
        assert '--json' in out
        assert '--summary' in out

    def test_map_main_compile_help(self):
        out = _help_output('map', 'compile')
        assert '--dungeon' in out
        assert 'source' in out

    def test_map_main_decompile_help(self):
        out = _help_output('map', 'decompile')
        assert '--output' in out

    def test_shapes_main_compile_help(self):
        out = _help_output('shapes', 'compile')
        assert '--format' in out
        assert 'source' in out

    def test_shapes_main_decompile_help(self):
        out = _help_output('shapes', 'decompile')
        assert '--output' in out

    def test_patch_main_compile_names_help(self):
        out = _help_output('patch', 'compile-names')
        assert 'source' in out
        assert '--output' in out

    def test_patch_main_decompile_names_help(self):
        out = _help_output('patch', 'decompile-names')
        assert '--output' in out

    def test_patch_main_validate_names_help(self):
        out = _help_output('patch', 'validate-names')
        assert 'source' in out

    def test_patch_main_strings_edit_help(self):
        out = _help_output('patch', 'strings-edit')
        assert '--text' in out
        assert '--index' in out
        assert '--vanilla' in out
        assert '--address' in out

    def test_patch_main_strings_import_help(self):
        out = _help_output('patch', 'strings-import')
        assert '--backup' in out
        assert '--dry-run' in out

    def test_exod_main_view_help(self):
        out = _help_output('exod', 'view')
        assert '--json' in out

    def test_exod_main_export_help(self):
        out = _help_output('exod', 'export')
        assert '--frame' in out
        assert '--scale' in out

    def test_exod_main_import_help(self):
        out = _help_output('exod', 'import')
        assert '--frame' in out
        assert '--backup' in out
        assert '--dry-run' in out

    def test_exod_main_glyph_help(self):
        out = _help_output('exod', 'glyph')
        assert 'view' in out
        assert 'export' in out
        assert 'import' in out

    def test_exod_main_crawl_help(self):
        out = _help_output('exod', 'crawl')
        assert 'view' in out
        assert 'compose' in out

    def test_disk_main_build_help(self):
        out = _help_output('disk', 'build')
        assert '--vol-name' in out
        assert '--boot-from' in out


class TestCliDispatch:
    """Test CLI dispatcher edge cases."""

    def test_unknown_subcommand(self, capsys):
        """CLI with no subcommand prints help or exits."""
        from ult3edit.cli import main
        sys_argv_backup = sys.argv
        sys.argv = ['ult3edit']
        try:
            main()
        except SystemExit:
            pass  # Expected
        finally:
            sys.argv = sys_argv_backup


# =============================================================================
# Batch 7: Final gaps — combat edit, dispatch fallbacks, directory errors
# =============================================================================


class TestDispatchFallbacks:
    """Test dispatch() fallback for unrecognized subcommands."""

    def test_combat_dispatch_unknown(self, capsys):
        """Combat dispatch with unknown command prints usage."""
        from ult3edit.combat import dispatch
        args = argparse.Namespace(combat_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_bestiary_dispatch_unknown(self, capsys):
        """Bestiary dispatch with unknown command prints usage."""
        from ult3edit.bestiary import dispatch
        args = argparse.Namespace(bestiary_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_map_dispatch_unknown(self, capsys):
        """Map dispatch with unknown command prints usage."""
        from ult3edit.map import dispatch
        args = argparse.Namespace(map_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_tlk_dispatch_unknown(self, capsys):
        """TLK dispatch with unknown command prints usage."""
        from ult3edit.tlk import dispatch
        args = argparse.Namespace(tlk_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_save_dispatch_unknown(self, capsys):
        """Save dispatch with unknown command prints usage."""
        from ult3edit.save import dispatch
        args = argparse.Namespace(save_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_special_dispatch_unknown(self, capsys):
        """Special dispatch with unknown command prints usage."""
        from ult3edit.special import dispatch
        args = argparse.Namespace(special_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_text_dispatch_unknown(self, capsys):
        """Text dispatch with unknown command prints usage."""
        from ult3edit.text import dispatch
        args = argparse.Namespace(text_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_ddrw_dispatch_unknown(self, capsys):
        """DDRW dispatch with unknown command prints usage."""
        from ult3edit.ddrw import dispatch
        args = argparse.Namespace(ddrw_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_patch_dispatch_unknown(self, capsys):
        """Patch dispatch with unknown command prints usage."""
        from ult3edit.patch import dispatch
        args = argparse.Namespace(patch_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_roster_dispatch_unknown(self, capsys):
        """Roster dispatch with unknown command prints usage."""
        from ult3edit.roster import dispatch
        args = argparse.Namespace(roster_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_sound_dispatch_unknown(self, capsys):
        """Sound dispatch with unknown command prints usage."""
        from ult3edit.sound import dispatch
        args = argparse.Namespace(sound_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_shapes_dispatch_unknown(self, capsys):
        """Shapes dispatch with unknown command prints usage."""
        from ult3edit.shapes import dispatch
        args = argparse.Namespace(shapes_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_equip_dispatch_unknown(self, capsys):
        """Equip dispatch with unknown command prints usage."""
        from ult3edit.equip import dispatch
        args = argparse.Namespace(equip_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()

    def test_spell_dispatch_unknown(self, capsys):
        """Spell dispatch with unknown command prints usage."""
        from ult3edit.spell import dispatch
        args = argparse.Namespace(spell_command='bogus')
        dispatch(args)
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or 'usage' in captured.err.lower()


import pytest


class TestConsoleScriptEntryPoints:
    """Verify all ult3-* console scripts respond to --help."""

    ALL_MODULES = [
        "roster", "bestiary", "map", "tlk", "combat", "save",
        "special", "text", "spell", "equip", "disk", "shapes",
        "sound", "patch", "ddrw", "diff", "exod",
    ]

    @pytest.mark.parametrize("module", ALL_MODULES)
    def test_module_help(self, module):
        result = subprocess.run(
            [sys.executable, '-m', f'ult3edit.{module}', '--help'],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert len(result.stdout) > 20  # Non-trivial help text


# ── Migrated from test_new_features.py ──

class TestValidateOnEditArgs:
    """Verify --validate is accepted by bestiary and combat edit subparsers."""

    def test_bestiary_edit_accepts_validate(self):
        """bestiary edit --validate should be a valid CLI arg."""
        import argparse
        from ult3edit.bestiary import register_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='module')
        register_parser(sub)
        args = parser.parse_args(['bestiary', 'edit', 'test.mon', '--monster', '0',
                                  '--hp', '50', '--validate'])
        assert args.validate is True

    def test_combat_edit_accepts_validate(self):
        """combat edit --validate should be a valid CLI arg."""
        import argparse
        from ult3edit.combat import register_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='module')
        register_parser(sub)
        args = parser.parse_args(['combat', 'edit', 'test.con',
                                  '--tile', '0', '0', '32', '--validate'])
        assert args.validate is True

    def test_bestiary_edit_validate_runs(self, tmp_dir, sample_mon_bytes):
        """bestiary edit with --validate should show warnings."""
        from ult3edit.bestiary import cmd_edit
        mon_file = os.path.join(tmp_dir, 'MONA#069900')
        with open(mon_file, 'wb') as f:
            f.write(sample_mon_bytes)
        args = type('Args', (), {
            'file': mon_file, 'monster': 0, 'all': False,
            'output': None, 'backup': False, 'dry_run': True,
            'validate': True,
            'name': None, 'tile1': None, 'tile2': None,
            'hp': 50, 'attack': None, 'defense': None, 'speed': None,
            'flags1': None, 'flags2': None, 'ability1': None, 'ability2': None,
            'type': None,
            'boss': None, 'no_boss': None, 'undead': None, 'ranged': None,
            'magic_user': None, 'poison': None, 'no_poison': None,
            'sleep': None, 'no_sleep': None, 'negate': None, 'no_negate': None,
            'teleport': None, 'no_teleport': None,
            'divide': None, 'no_divide': None,
            'resistant': None, 'no_resistant': None,
        })()
        # Should not raise
        cmd_edit(args)

    def test_combat_edit_validate_runs(self, tmp_dir, sample_con_bytes):
        """combat edit with --validate should show warnings."""
        from ult3edit.combat import cmd_edit
        con_file = os.path.join(tmp_dir, 'CONA#069900')
        with open(con_file, 'wb') as f:
            f.write(sample_con_bytes)
        args = type('Args', (), {
            'file': con_file,
            'output': None, 'backup': False, 'dry_run': True,
            'validate': True,
            'tile': [5, 5, 0x20],
            'monster_pos': None, 'pc_pos': None,
        })()
        # Should not raise
        cmd_edit(args)


class TestHexIntArgParsing:
    """Verify that CLI args for tiles, offsets, and flags accept hex (0x) prefix."""

    def test_hex_int_helper(self):
        from ult3edit.fileutil import hex_int
        assert hex_int('10') == 10
        assert hex_int('0x0A') == 10
        assert hex_int('0xFF') == 255
        assert hex_int('0') == 0

    def test_hex_int_rejects_garbage(self):
        from ult3edit.fileutil import hex_int
        with pytest.raises(ValueError):
            hex_int('xyz')

    def test_map_tile_accepts_hex(self, tmp_dir):
        """map set --tile 0x01 should parse without error."""
        import argparse
        from ult3edit.map import cmd_set
        from ult3edit.constants import MAP_OVERWORLD_SIZE
        path = os.path.join(tmp_dir, 'MAP')
        data = bytes(MAP_OVERWORLD_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, x=0, y=0, tile=0x01,
            output=None, backup=False, dry_run=True)
        cmd_set(args)  # Should not raise

    def test_combat_tile_accepts_hex(self, tmp_dir):
        """combat edit --tile 0x08 should parse without error."""
        from ult3edit.combat import cmd_edit as combat_cmd_edit
        from ult3edit.constants import CON_FILE_SIZE
        path = os.path.join(tmp_dir, 'CON')
        data = bytearray(CON_FILE_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = type('Args', (), {
            'file': path, 'tile': [0, 0, 0x08],
            'monster_pos': None, 'pc_pos': None,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        combat_cmd_edit(args)  # Should not raise

    def test_bestiary_flags_accept_hex(self, tmp_dir):
        """bestiary edit --flags1 0x80 should parse without error."""
        from ult3edit.bestiary import cmd_edit as bestiary_cmd_edit
        from ult3edit.constants import MON_FILE_SIZE
        path = os.path.join(tmp_dir, 'MON')
        data = bytearray(MON_FILE_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = type('Args', (), {
            'file': path, 'monster': 0,
            'tile1': None, 'tile2': None,
            'flags1': 0x80, 'flags2': None,
            'hp': None, 'attack': None, 'defense': None, 'speed': None,
            'ability1': None, 'ability2': None,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        bestiary_cmd_edit(args)  # Should not raise

    def test_special_tile_accepts_hex(self, tmp_dir):
        """special edit --tile 0x00 0x00 0x08 should parse without error."""
        from ult3edit.special import cmd_edit as special_cmd_edit
        from ult3edit.constants import SPECIAL_FILE_SIZE
        path = os.path.join(tmp_dir, 'BRND')
        data = bytearray(SPECIAL_FILE_SIZE)
        with open(path, 'wb') as f:
            f.write(data)
        args = type('Args', (), {
            'file': path, 'tile': [0, 0, 0x08],
            'output': None, 'backup': False, 'dry_run': True,
        })()
        special_cmd_edit(args)  # Should not raise

    def test_argparser_accepts_hex_string(self):
        """Verify argparse actually parses '0x0A' string to 10 via hex_int type."""
        import argparse
        from ult3edit.fileutil import hex_int
        parser = argparse.ArgumentParser()
        parser.add_argument('--tile', type=hex_int)
        args = parser.parse_args(['--tile', '0x0A'])
        assert args.tile == 10

    def test_argparser_accepts_decimal_string(self):
        """hex_int still works with plain decimal strings."""
        import argparse
        from ult3edit.fileutil import hex_int
        parser = argparse.ArgumentParser()
        parser.add_argument('--offset', type=hex_int)
        args = parser.parse_args(['--offset', '240'])
        assert args.offset == 240


class TestDictKeyValidation:
    """Verify non-numeric dict keys are handled gracefully."""

    def test_bestiary_import_skips_bad_keys(self, tmp_path):
        """Bestiary import skips non-numeric keys without crashing."""
        from ult3edit.bestiary import cmd_import, load_mon_file
        mon_data = bytearray(256)
        mon_path = str(tmp_path / 'MONA')
        with open(mon_path, 'wb') as f:
            f.write(mon_data)

        jdata = {
            "monsters": {
                "0": {"hp": 100},
                "abc": {"hp": 200},  # non-numeric key
                "1": {"hp": 150}
            }
        }
        json_path = str(tmp_path / 'bestiary.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': mon_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        cmd_import(args)  # Should not crash

        monsters = load_mon_file(mon_path)
        assert monsters[0].hp == 100
        assert monsters[1].hp == 150

    def test_combat_import_skips_bad_keys(self, tmp_path):
        """Combat import skips non-numeric monster keys without crashing."""
        from ult3edit.combat import cmd_import as combat_import
        from ult3edit.constants import CON_FILE_SIZE
        con_data = bytearray(CON_FILE_SIZE)
        con_path = str(tmp_path / 'CONA')
        with open(con_path, 'wb') as f:
            f.write(con_data)

        jdata = {
            "tiles": [['.' for _ in range(11)] for _ in range(11)],
            "monsters": {
                "0": {"x": 3, "y": 4},
                "bad": {"x": 5, "y": 6}  # non-numeric key
            }
        }
        json_path = str(tmp_path / 'combat.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': con_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        combat_import(args)  # Should not crash


# =============================================================================
# Coverage: cli.py lines 48-51 (_cmd_unified_edit error path),
# 108-136 (dispatch routing dict, handler call)
# =============================================================================


class TestCliUnifiedEditError:
    """Cover lines 48-51: _cmd_unified_edit when file not found."""

    def test_edit_nonexistent_image(self):
        from ult3edit.cli import _cmd_unified_edit
        args = argparse.Namespace(image='/nonexistent/fake.po')
        with pytest.raises(SystemExit):
            _cmd_unified_edit(args)


class TestCliMainDispatchRouting:
    """Cover lines 108-136: main() dispatcher routing table."""

    def test_main_version(self, capsys):
        from ult3edit.cli import main
        old_argv = sys.argv
        sys.argv = ['ult3edit', '--version']
        try:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        finally:
            sys.argv = old_argv

    def test_main_dispatch_spell(self, capsys):
        """main() dispatches 'spell view' through the routing dict."""
        from ult3edit.cli import main
        old_argv = sys.argv
        sys.argv = ['ult3edit', 'spell', 'view']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Wizard Spells' in out

    def test_main_dispatch_equip(self, capsys):
        """main() dispatches 'equip view' through the routing dict."""
        from ult3edit.cli import main
        old_argv = sys.argv
        sys.argv = ['ult3edit', 'equip', 'view']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Weapons' in out

    def test_main_no_tool_shows_help(self, capsys):
        """main() with no tool shows help and exits 0."""
        from ult3edit.cli import main
        old_argv = sys.argv
        sys.argv = ['ult3edit']
        try:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        finally:
            sys.argv = old_argv


# =============================================================================
# Coverage: __main__.py (2 uncovered lines) — import and call main
# =============================================================================


class TestDunderMain:
    """Cover __main__.py lines 2-4: the module imports cli.main and calls it."""

    def test_dunder_main_import_and_call(self):
        """Importing __main__ calls main(), which uses sys.argv.
        We mock sys.argv to '--help' so it exits cleanly."""
        old_argv = sys.argv
        sys.argv = ['ult3edit', '--help']
        try:
            with pytest.raises(SystemExit) as exc_info:
                import importlib
                # Force re-import since it may be cached
                import ult3edit.__main__ as m
                importlib.reload(m)
            assert exc_info.value.code == 0
        finally:
            sys.argv = old_argv

    def test_python_m_ult3edit_help(self):
        """Run python -m ult3edit --help to cover __main__.py execution."""
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'ult3edit', '--help'],
            capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert 'ult3edit' in result.stdout

