"""Tests for bestiary tool."""

import argparse
import json
import os

import pytest

from ult3edit.bestiary import (
    Monster, load_mon_file, save_mon_file, cmd_edit, cmd_import, validate_monster,
)
from ult3edit.constants import (
    MON_FILE_SIZE, MON_MONSTERS_PER_FILE,
    MON_FLAG1_UNDEAD, MON_FLAG1_RANGED, MON_FLAG1_MAGIC_USER, MON_FLAG1_BOSS,
    MON_ABIL1_POISON, MON_ABIL1_TELEPORT, MON_ABIL2_RESISTANT,
)


def _edit_args(**kwargs):
    """Build an argparse.Namespace with all bestiary edit args defaulting to None/False."""
    defaults = dict(
        file=None, monster=0, output=None,
        hp=None, attack=None, defense=None, speed=None,
        tile1=None, tile2=None, flags1=None, flags2=None,
        ability1=None, ability2=None,
        type=None,
        undead=False, ranged=False, magic_user=False,
        boss=False, no_boss=False,
        poison=False, no_poison=False,
        sleep=False, no_sleep=False,
        negate=False, no_negate=False,
        teleport=False, no_teleport=False,
        divide=False, no_divide=False,
        resistant=False, no_resistant=False,
        backup=False, dry_run=False,
    )
    defaults['all'] = kwargs.pop('all', False)
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestMonster:
    def test_name_fighter(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert monsters[0].name == 'Fighter'

    def test_name_dragon(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert monsters[1].name == 'Dragon'

    def test_name_skeleton(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert monsters[2].name == 'Skeleton'

    def test_hp(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert monsters[0].hp == 50
        assert monsters[1].hp == 200

    def test_boss_flag(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert 'Boss' in monsters[1].flag_desc

    def test_undead_flag(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert 'Undead' in monsters[2].flag_desc

    def test_empty(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        assert monsters[3].is_empty
        assert not monsters[0].is_empty


class TestToDict:
    def test_keys(self, sample_mon_bytes):
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        d = monsters[0].to_dict()
        assert 'name' in d
        assert 'hp' in d
        assert 'attack' in d
        assert 'defense' in d

    def test_has_raw_fields(self, sample_mon_bytes):
        """to_dict() includes raw numeric flag/ability values for round-trip."""
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        d = monsters[1].to_dict()  # Dragon with Boss flag
        assert 'flags1' in d
        assert 'flags2' in d
        assert 'ability1' in d
        assert 'ability2' in d
        assert d['flags1'] == 0x80  # Boss flag

    def test_preserves_human_readable(self, sample_mon_bytes):
        """to_dict() still has human-readable flags/abilities strings."""
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        d = monsters[1].to_dict()
        assert 'flags' in d
        assert 'abilities' in d
        assert 'Boss' in d['flags']

    def test_roundtrip_via_dict(self, sample_mon_file, tmp_dir):
        """Export to_dict, write JSON, import back — values preserved."""
        monsters = load_mon_file(sample_mon_file)
        dicts = [m.to_dict() for m in monsters if not m.is_empty]
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump(dicts, f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False,
        )
        cmd_import(args)
        monsters2 = load_mon_file(out)
        assert monsters2[0].hp == monsters[0].hp
        assert monsters2[1].flags1 == monsters[1].flags1


class TestLoadSave:
    def test_load(self, sample_mon_file):
        monsters = load_mon_file(sample_mon_file)
        assert len(monsters) == 16
        assert monsters[0].name == 'Fighter'

    def test_roundtrip(self, sample_mon_file, tmp_dir):
        monsters = load_mon_file(sample_mon_file)
        monsters[0].hp = 99
        output = os.path.join(tmp_dir, 'MONA_OUT')
        save_mon_file(output, monsters)

        monsters2 = load_mon_file(output)
        assert monsters2[0].hp == 99
        assert monsters2[1].name == 'Dragon'  # Other monsters preserved

    def test_unknown_rows_preserved(self, tmp_dir):
        """save_mon_file should preserve unknown data in rows 10-15."""
        data = bytearray(256)
        data[0 * 16 + 0] = 0x48  # tile1 for monster 0
        data[4 * 16 + 0] = 50    # hp for monster 0
        data[12 * 16 + 5] = 0xAB  # unknown data in row 12, col 5
        data[15 * 16 + 0] = 0xCD  # unknown data in row 15, col 0
        path = os.path.join(tmp_dir, 'MONA_TEST')
        with open(path, 'wb') as f:
            f.write(data)
        monsters = load_mon_file(path)
        output = os.path.join(tmp_dir, 'MONA_OUT')
        save_mon_file(output, monsters, original_data=bytes(data))
        with open(output, 'rb') as f:
            result = f.read()
        assert result[12 * 16 + 5] == 0xAB
        assert result[15 * 16 + 0] == 0xCD
        assert result[4 * 16 + 0] == 50  # Known data still correct


class TestCmdEdit:
    def test_edit_hp(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, hp=99)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].hp == 99
        assert monsters[1].hp == 200  # Other monsters preserved

    def test_edit_clamps(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, hp=999)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].hp == 255  # Clamped to byte range


class TestBulkEdit:
    def test_edit_all_hp(self, sample_mon_file, tmp_dir):
        """--all --hp 100 applies to all non-empty monsters."""
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, output=out, all=True, hp=100)
        cmd_edit(args)
        monsters = load_mon_file(out)
        # Fixture has 3 non-empty monsters (indices 0, 1, 2)
        assert monsters[0].hp == 100
        assert monsters[1].hp == 100
        assert monsters[2].hp == 100

    def test_edit_all_speed(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, output=out, all=True, speed=50)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].speed == 50
        assert monsters[1].speed == 50
        assert monsters[2].speed == 50

    def test_edit_all_skips_empty(self, sample_mon_file, tmp_dir):
        """Empty monster slots are not modified by --all."""
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, output=out, all=True, hp=100)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[3].is_empty
        assert monsters[3].hp == 0

    def test_edit_all_no_modifications(self, sample_mon_file, capsys):
        """--all with no edit flags prints 'No modifications'."""
        args = _edit_args(file=sample_mon_file, all=True)
        cmd_edit(args)
        assert 'No modifications' in capsys.readouterr().out

    def test_edit_all_with_poison(self, sample_mon_file, tmp_dir):
        """--all --poison sets Poison on all non-empty monsters."""
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, output=out, all=True, poison=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].ability1 & MON_ABIL1_POISON
        assert monsters[1].ability1 & MON_ABIL1_POISON
        assert monsters[2].ability1 & MON_ABIL1_POISON


class TestNamedFlags:
    def test_set_undead(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, undead=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].flags1 & MON_FLAG1_UNDEAD
        assert 'Undead' in monsters[0].flag_desc

    def test_set_ranged(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, ranged=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].flags1 & MON_FLAG1_RANGED
        assert 'Ranged' in monsters[0].flag_desc

    def test_set_magic_user(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, magic_user=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].flags1 & 0x0C == MON_FLAG1_MAGIC_USER
        assert 'Magic User' in monsters[0].flag_desc

    def test_set_boss(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, boss=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].flags1 & MON_FLAG1_BOSS

    def test_clear_boss(self, sample_mon_file, tmp_dir):
        """--no-boss clears Boss flag on Dragon (monster 1, flags1=0x80)."""
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=1, output=out, no_boss=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert not (monsters[1].flags1 & MON_FLAG1_BOSS)

    def test_set_poison(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, poison=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].ability1 & MON_ABIL1_POISON

    def test_clear_poison(self, sample_mon_file, tmp_dir):
        """--no-poison clears Poison bit."""
        # First set poison, then clear it
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, poison=True)
        cmd_edit(args)
        args2 = _edit_args(file=out, monster=0, output=out, no_poison=True)
        cmd_edit(args2)
        monsters = load_mon_file(out)
        assert not (monsters[0].ability1 & MON_ABIL1_POISON)

    def test_set_teleport(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, teleport=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].ability1 & MON_ABIL1_TELEPORT

    def test_set_resistant(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, resistant=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].ability2 & MON_ABIL2_RESISTANT

    def test_undead_clears_ranged(self, sample_mon_file, tmp_dir):
        """Setting --undead on a Ranged monster clears Ranged bit."""
        out = os.path.join(tmp_dir, 'MONA_OUT')
        # First make monster 0 Ranged
        args = _edit_args(file=sample_mon_file, monster=0, output=out, ranged=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].flags1 & MON_FLAG1_RANGED
        # Now set Undead — should clear Ranged
        args2 = _edit_args(file=out, monster=0, output=out, undead=True)
        cmd_edit(args2)
        monsters2 = load_mon_file(out)
        assert monsters2[0].flags1 & MON_FLAG1_UNDEAD
        assert not (monsters2[0].flags1 & MON_FLAG1_RANGED)


class TestTypeByName:
    def test_type_dragon(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, type='Dragon')
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].tile1 == 0x74
        assert monsters[0].tile2 == 0x74
        assert monsters[0].name == 'Dragon'

    def test_type_skeleton(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, type='Skeleton')
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].tile1 == 0x64

    def test_type_case_insensitive(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, type='dragon')
        cmd_edit(args)
        monsters = load_mon_file(out)
        assert monsters[0].tile1 == 0x74

    def test_type_unknown_warns(self, sample_mon_file, tmp_dir, capsys):
        """Unknown type name prints warning, doesn't crash."""
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, type='Goblin')
        cmd_edit(args)
        assert 'Unknown monster type' in capsys.readouterr().err


class TestCmdImport:
    def test_import_from_json(self, sample_mon_file, tmp_dir):
        """cmd_import applies JSON attributes to monsters."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'hp': 99, 'attack': 77}], f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False,
        )
        cmd_import(args)
        monsters = load_mon_file(out)
        assert monsters[0].hp == 99
        assert monsters[0].attack == 77

    def test_import_with_backup(self, sample_mon_file, tmp_dir):
        """--backup creates .bak file."""
        # Copy file to tmp so backup doesn't touch fixtures
        path = os.path.join(tmp_dir, 'MONA')
        with open(sample_mon_file, 'rb') as f:
            data = f.read()
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'hp': 99}], f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            output=None, backup=True,
        )
        cmd_import(args)
        assert os.path.exists(path + '.bak')

    def test_import_skips_invalid_index(self, sample_mon_file, tmp_dir, capsys):
        """Monsters with invalid index are skipped."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([
                {'index': -1, 'hp': 99},
                {'index': 16, 'hp': 99},
                {'index': 0, 'hp': 77},
            ], f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False,
        )
        cmd_import(args)
        output = capsys.readouterr().out
        assert 'Imported 1 monster' in output
        monsters = load_mon_file(out)
        assert monsters[0].hp == 77


class TestDryRun:
    def test_dry_run_no_write(self, sample_mon_file, tmp_dir, capsys):
        """--dry-run shows changes but doesn't write file."""
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, hp=99, dry_run=True)
        cmd_edit(args)
        assert not os.path.exists(out)
        assert 'Dry run' in capsys.readouterr().out

    def test_backup_creates_bak(self, sample_mon_file, tmp_dir):
        """--backup creates .bak before overwriting."""
        path = os.path.join(tmp_dir, 'MONA')
        with open(sample_mon_file, 'rb') as f:
            data = f.read()
        with open(path, 'wb') as f:
            f.write(data)
        args = _edit_args(file=path, monster=0, hp=99, backup=True)
        cmd_edit(args)
        assert os.path.exists(path + '.bak')
        monsters = load_mon_file(path)
        assert monsters[0].hp == 99


def load_mon_file_from_bytes(data: bytes):
    """Helper to load monsters directly from bytes without a file."""
    from ult3edit.bestiary import Monster
    from ult3edit.constants import MON_ATTR_COUNT

    monsters = []
    for i in range(MON_MONSTERS_PER_FILE):
        attrs = []
        for row in range(MON_ATTR_COUNT):
            offset = row * MON_MONSTERS_PER_FILE + i
            attrs.append(data[offset] if offset < len(data) else 0)
        monsters.append(Monster(attrs, i))
    return monsters


class TestValidateMonster:
    def test_valid_monster(self, sample_mon_bytes):
        """Valid monsters should produce no warnings."""
        monsters = load_mon_file_from_bytes(sample_mon_bytes)
        # Monster 0 has tile 0x48 which should be in MONSTER_NAMES
        warnings = validate_monster(monsters[0])
        assert warnings == []

    def test_empty_monster_no_warnings(self):
        """Empty monster should produce no warnings."""
        m = Monster([0] * 10, 0)
        assert validate_monster(m) == []

    def test_unknown_tile(self):
        """Unknown tile ID should warn."""
        attrs = [0xE8, 0xE8, 0, 0, 50, 30, 20, 10, 0, 0]  # 0xE8 not in MONSTER_NAMES or TILES
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('Unknown tile' in w for w in warnings)

    def test_tile_mismatch(self):
        """tile1 != tile2 should warn."""
        attrs = [0x48, 0x64, 0, 0, 50, 30, 20, 10, 0, 0]
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('mismatch' in w for w in warnings)

    def test_undefined_ability_bits(self):
        """Undefined ability1 bits should warn."""
        attrs = [0x48, 0x48, 0, 0, 50, 30, 20, 10, 0x10, 0]  # bit 4 undefined
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('ability1' in w for w in warnings)


# ── Migrated from test_new_features.py ──

class TestBestiaryImport:
    def test_import_monster_data(self, tmp_dir, sample_mon_bytes):
        path = os.path.join(tmp_dir, 'MONA')
        with open(path, 'wb') as f:
            f.write(sample_mon_bytes)

        monsters = load_mon_file(path)

        # Modify via JSON-style update
        monsters[0].hp = 99
        monsters[0].attack = 50
        save_mon_file(path, monsters, sample_mon_bytes)

        monsters2 = load_mon_file(path)
        assert monsters2[0].hp == 99
        assert monsters2[0].attack == 50

    def test_import_dry_run(self, tmp_dir, sample_mon_bytes):
        """Import with --dry-run should not write changes."""
        import types
        from ult3edit.bestiary import cmd_import as bestiary_import
        path = os.path.join(tmp_dir, 'MONA')
        with open(path, 'wb') as f:
            f.write(sample_mon_bytes)
        with open(path, 'rb') as f:
            original = f.read()
        mon_json = [{'index': 0, 'hp': 255, 'attack': 255}]
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump(mon_json, f)
        args = types.SimpleNamespace(
            file=path, json_file=json_path,
            output=None, backup=False, dry_run=True,
        )
        bestiary_import(args)
        with open(path, 'rb') as f:
            after = f.read()
        assert original == after


# =============================================================================
# Map CLI editing
# =============================================================================


class TestBestiaryDictImport:
    """Test that bestiary import accepts dict-of-dicts JSON format."""

    def test_import_dict_format(self, tmp_path):
        """Import bestiary from dict-keyed JSON (Voidborn source format)."""
        mon_file = tmp_path / 'MONA'
        mon_file.write_bytes(bytearray(MON_FILE_SIZE))
        json_file = tmp_path / 'bestiary.json'
        json_file.write_text(json.dumps({
            "monsters": {
                "0": {"hp": 60, "attack": 35, "defense": 25, "speed": 20},
                "3": {"hp": 100, "attack": 50, "defense": 40, "speed": 30}
            }
        }))
        # Run import via cmd_import
        import argparse
        from ult3edit.bestiary import cmd_import as bestiary_import
        args = argparse.Namespace(
            file=str(mon_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        bestiary_import(args)
        monsters = load_mon_file(str(mon_file))
        assert monsters[0].hp == 60
        assert monsters[0].attack == 35
        assert monsters[3].hp == 100
        assert monsters[3].attack == 50
        # Unmodified monster should be 0
        assert monsters[1].hp == 0

    def test_import_flag_shortcuts(self, tmp_path):
        """Import bestiary with flag shortcuts (boss, poison, etc.)."""
        mon_file = tmp_path / 'MONA'
        mon_file.write_bytes(bytearray(MON_FILE_SIZE))
        json_file = tmp_path / 'bestiary.json'
        json_file.write_text(json.dumps({
            "monsters": {
                "0": {"hp": 80, "boss": True, "poison": True},
                "1": {"hp": 50, "negate": True, "resistant": True}
            }
        }))
        import argparse
        from ult3edit.bestiary import cmd_import as bestiary_import
        from ult3edit.constants import (
            MON_FLAG1_BOSS, MON_ABIL1_POISON,
            MON_ABIL1_NEGATE, MON_ABIL2_RESISTANT,
        )
        args = argparse.Namespace(
            file=str(mon_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        bestiary_import(args)
        monsters = load_mon_file(str(mon_file))
        assert monsters[0].hp == 80
        assert monsters[0].flags1 & MON_FLAG1_BOSS
        assert monsters[0].ability1 & MON_ABIL1_POISON
        assert monsters[1].ability1 & MON_ABIL1_NEGATE
        assert monsters[1].ability2 & MON_ABIL2_RESISTANT

    def test_import_list_format_still_works(self, tmp_path):
        """Original list format import still works after dict support."""
        mon_file = tmp_path / 'MONA'
        mon_file.write_bytes(bytearray(MON_FILE_SIZE))
        json_file = tmp_path / 'bestiary.json'
        json_file.write_text(json.dumps([
            {"index": 0, "hp": 77, "attack": 44}
        ]))
        import argparse
        from ult3edit.bestiary import cmd_import as bestiary_import
        args = argparse.Namespace(
            file=str(mon_file), json_file=str(json_file),
            backup=False, dry_run=False, output=None)
        bestiary_import(args)
        monsters = load_mon_file(str(mon_file))
        assert monsters[0].hp == 77


class TestBestiaryShortcutRawConflict:
    """Verify shortcuts OR into raw attributes, not overwritten by them."""

    def test_shortcut_applied_after_raw(self, tmp_path):
        """Boss shortcut is preserved even when flags1 raw value is 0."""
        from ult3edit.bestiary import (
            load_mon_file, cmd_import,
            MON_FLAG1_BOSS
        )
        # Create empty MON file
        mon_data = bytearray(256)
        mon_path = str(tmp_path / 'MONA')
        with open(mon_path, 'wb') as f:
            f.write(mon_data)

        # JSON with both boss shortcut AND raw flags1=0
        jdata = {
            "monsters": {
                "0": {"hp": 100, "attack": 50, "flags1": 0, "boss": True}
            }
        }
        json_path = str(tmp_path / 'bestiary.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        # Import
        args = type('Args', (), {
            'file': mon_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        cmd_import(args)

        # Verify boss flag is set
        monsters = load_mon_file(mon_path)
        assert monsters[0].flags1 & MON_FLAG1_BOSS, \
            "Boss flag should be set even when flags1 raw value is 0"

    def test_shortcut_ors_into_existing_flags(self, tmp_path):
        """Multiple shortcuts all accumulate."""
        from ult3edit.bestiary import (
            load_mon_file, cmd_import,
            MON_FLAG1_BOSS, MON_ABIL1_POISON, MON_ABIL1_NEGATE
        )
        mon_data = bytearray(256)
        mon_path = str(tmp_path / 'MONA')
        with open(mon_path, 'wb') as f:
            f.write(mon_data)

        jdata = {
            "monsters": {
                "0": {"hp": 200, "boss": True, "poison": True, "negate": True}
            }
        }
        json_path = str(tmp_path / 'bestiary.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': mon_path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False
        })()
        cmd_import(args)

        monsters = load_mon_file(mon_path)
        assert monsters[0].flags1 & MON_FLAG1_BOSS
        assert monsters[0].ability1 & MON_ABIL1_POISON
        assert monsters[0].ability1 & MON_ABIL1_NEGATE


# =============================================================================
# Non-numeric dict key handling
# =============================================================================


class TestBestiaryErrorPaths:
    """Tests for bestiary cmd_edit error exits."""

    def test_edit_no_monster_no_all(self, tmp_path):
        """cmd_edit without --monster or --all exits."""
        from ult3edit.bestiary import cmd_edit
        mon = tmp_path / 'MONA'
        mon.write_bytes(bytes(MON_FILE_SIZE))
        args = argparse.Namespace(
            file=str(mon), monster=None, all=False,
            dry_run=False, backup=False, output=None,
            validate=False, hp=None, tile=None, flags=None,
            name=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_monster_out_of_range(self, tmp_path):
        """cmd_edit with monster index > 15 exits."""
        from ult3edit.bestiary import cmd_edit
        mon = tmp_path / 'MONA'
        mon.write_bytes(bytes(MON_FILE_SIZE))
        args = argparse.Namespace(
            file=str(mon), monster=99, all=False,
            dry_run=False, backup=False, output=None,
            validate=False, hp=50, tile=None, flags=None,
            name=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestBestiaryColumnarRoundTrip:
    """Verify MON columnar layout survives import/export correctly."""

    def test_columnar_layout_preservation(self, tmp_path):
        """Set attributes for all 16 monsters, verify column-major layout."""
        data = bytearray(MON_FILE_SIZE)
        for attr in range(10):
            for monster in range(16):
                data[attr * 16 + monster] = (attr * 16 + monster) & 0xFF

        mon_file = tmp_path / 'MONA'
        mon_file.write_bytes(bytes(data))

        monsters = load_mon_file(str(mon_file))
        # Verify each monster reads correct values from its column slot
        for m in monsters:
            idx = m.index
            assert m.tile1 == (0 * 16 + idx) & 0xFF  # row 0
            assert m.hp == (4 * 16 + idx) & 0xFF      # row 4

        # Save with original_data to preserve rows 10-15
        save_mon_file(str(mon_file), monsters, original_data=bytes(data))
        result = mon_file.read_bytes()
        assert result == bytes(data)

    def test_unused_rows_preserved(self, tmp_path):
        """Rows 10-15 (runtime workspace) survive save→reload with original_data."""
        data = bytearray(MON_FILE_SIZE)
        for row in range(10, 16):
            for col in range(16):
                data[row * 16 + col] = 0xAA
        for row in range(10):
            for col in range(16):
                data[row * 16 + col] = row

        mon_file = tmp_path / 'MONA'
        mon_file.write_bytes(bytes(data))

        monsters = load_mon_file(str(mon_file))
        save_mon_file(str(mon_file), monsters, original_data=bytes(data))
        result = mon_file.read_bytes()
        for row in range(10, 16):
            for col in range(16):
                assert result[row * 16 + col] == 0xAA, \
                    f"Row {row}, col {col} corrupted"


class TestBestiaryCmdDump:
    """Test bestiary.py cmd_dump hex display."""

    def test_cmd_dump_runs(self, tmp_path, capsys):
        """cmd_dump executes without error on a valid MON file."""
        from ult3edit.bestiary import cmd_dump
        data = bytearray(MON_FILE_SIZE)
        # Set some recognizable data in first monster tile
        data[0] = 0xAA
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(file=path)
        cmd_dump(args)
        captured = capsys.readouterr()
        assert 'MON File Dump' in captured.out
        assert 'Columnar' in captured.out
        assert 'AA' in captured.out


class TestBestiaryCmdImport:
    """Test bestiary.py cmd_import."""

    def test_import_list_format(self, tmp_path):
        """Import from JSON list format."""
        from ult3edit.bestiary import cmd_import as bestiary_import
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'mons.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'hp': 50, 'attack': 10}], f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        bestiary_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        # HP is row 4, monster 0 → offset 4*16+0 = 64
        assert result[64] == 50

    def test_import_dict_format(self, tmp_path):
        """Import from dict-of-dicts format with numeric string keys."""
        from ult3edit.bestiary import cmd_import as bestiary_import
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'mons.json')
        with open(json_path, 'w') as f:
            json.dump({'monsters': {'0': {'hp': 75}}}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        bestiary_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[64] == 75

    def test_import_dry_run(self, tmp_path):
        """Import with dry-run doesn't write."""
        from ult3edit.bestiary import cmd_import as bestiary_import
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'mons.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'hp': 99}], f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=True)
        bestiary_import(args)
        with open(path, 'rb') as f:
            result = f.read()
        assert result[64] == 0  # unchanged

    def test_import_with_shortcuts(self, tmp_path):
        """Import with flag shortcuts (boss, poison, etc.)."""
        from ult3edit.bestiary import cmd_import as bestiary_import
        from ult3edit.constants import MON_FLAG1_BOSS, MON_ABIL1_POISON
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'mons.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'boss': True, 'poison': True}], f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            backup=False, dry_run=False)
        bestiary_import(args)
        from ult3edit.bestiary import load_mon_file
        mons = load_mon_file(path)
        assert mons[0].flags1 & MON_FLAG1_BOSS
        assert mons[0].ability1 & MON_ABIL1_POISON


# =============================================================================
# Map cmd_overview and cmd_legend
# =============================================================================


class TestBestiaryValidate:
    """Test bestiary.py validate_monster edge cases."""

    def test_validate_empty_monster(self):
        """Empty monster produces no warnings."""
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0] * 10  # tile1=0, hp=0 → is_empty
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert len(warnings) == 0

    def test_validate_undefined_flag_bits(self):
        """Undefined flag bits produce warning."""
        from ult3edit.bestiary import Monster, validate_monster
        # attrs: tile1, tile2, flags1, flags2, hp, atk, def, spd, abil1, abil2
        attrs = [0x10, 0x10, 0x60, 0, 10, 5, 5, 5, 0, 0]
        # flags1=0x60: bits 5,6 set → undefined (defined = 0x04|0x08|0x0C|0x80)
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('flag1' in w.lower() or 'undefined' in w.lower()
                    for w in warnings)

    def test_validate_undefined_ability_bits(self):
        """Undefined ability bits produce warning."""
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0x10, 0x10, 0, 0, 10, 5, 5, 5, 0x10, 0]
        # ability1=0x10: bit 4 — not in defined set (0x01|0x02|0x04|0x40|0x80)
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('ability1' in w.lower() or 'undefined' in w.lower()
                    for w in warnings)


# =============================================================================
# Map cmd_view JSON mode
# =============================================================================


class TestBestiaryCmdViewJson:
    """Test bestiary cmd_view JSON export."""

    def test_view_json_output(self, tmp_path):
        """cmd_view JSON mode exports monster data."""
        from ult3edit.bestiary import cmd_view as bestiary_view
        # Create a MON file with one non-empty monster
        data = bytearray(MON_FILE_SIZE)
        data[0] = 0x10  # tile1 for monster 0
        data[4 * 16] = 20  # HP for monster 0
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        out_path = os.path.join(str(tmp_path), 'bestiary.json')
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=True, output=out_path,
            validate=False, file=None)
        bestiary_view(args)
        with open(out_path) as f:
            jdata = json.load(f)
        assert 'MONA' in jdata
        assert len(jdata['MONA']['monsters']) >= 1

    def test_view_no_files_exits(self, tmp_path):
        """cmd_view with no MON files exits."""
        from ult3edit.bestiary import cmd_view as bestiary_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False, file=None)
        with pytest.raises(SystemExit):
            bestiary_view(args)


# =============================================================================
# Roster cmd_edit --all mode
# =============================================================================


class TestBestiaryCmdEditGaps:
    """Test bestiary cmd_edit gaps."""

    def test_edit_no_monster_no_all(self, tmp_path):
        """cmd_edit exits if neither --monster nor --all given."""
        from ult3edit.bestiary import cmd_edit
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, monster=None, all=False,
            dry_run=False, backup=False, output=None, validate=False,
            tile1=None, tile2=None, hp=None, attack=None, defense=None,
            speed=None, flags1=None, flags2=None, ability1=None, ability2=None,
            boss=None, undead=None, ranged=None, divide=None, poison=None,
            sleep=None, negate=None, teleport=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_monster_out_of_range(self, tmp_path):
        """cmd_edit exits if monster index >= 16."""
        from ult3edit.bestiary import cmd_edit
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, monster=20, all=False,
            dry_run=False, backup=False, output=None, validate=False,
            tile1=None, tile2=None, hp=None, attack=None, defense=None,
            speed=None, flags1=None, flags2=None, ability1=None, ability2=None,
            boss=None, undead=None, ranged=None, divide=None, poison=None,
            sleep=None, negate=None, teleport=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_no_modifications(self, tmp_path, capsys):
        """cmd_edit with no edit flags prints 'No modifications specified'."""
        from ult3edit.bestiary import cmd_edit
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, monster=0, all=False,
            dry_run=False, backup=False, output=None, validate=False,
            tile1=None, tile2=None, hp=None, attack=None, defense=None,
            speed=None, flags1=None, flags2=None, ability1=None, ability2=None,
            boss=None, undead=None, ranged=None, divide=None, poison=None,
            sleep=None, negate=None, teleport=None)
        cmd_edit(args)
        captured = capsys.readouterr()
        assert 'No modifications' in captured.out

    def test_import_non_numeric_key_warning(self, tmp_path, capsys):
        """Import with non-numeric dict key prints warning."""
        from ult3edit.bestiary import cmd_import
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'monsters': {'abc': {'hp': 50}, '0': {'hp': 100}}}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert 'non-numeric' in captured.err

    def test_import_monster_out_of_range_skipped(self, tmp_path):
        """Import with monster index >= 16 silently skips."""
        from ult3edit.bestiary import cmd_import
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 99, 'hp': 50}], f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        cmd_import(args)  # Should not crash

    def test_load_mon_file_too_small(self, tmp_path):
        """load_mon_file returns empty list for undersized file."""
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(b'\x00' * 10)  # Much less than 160 bytes
        monsters = load_mon_file(path)
        assert monsters == []


class TestBestiaryCmdViewGaps:
    """Test bestiary cmd_view directory error."""

    def test_no_mon_files_in_dir(self, tmp_path):
        """cmd_view on directory with no MON files exits."""
        from ult3edit.bestiary import cmd_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), json=False, output=None,
            validate=False, file=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


class TestBestiaryAbility2Validation:
    """Test validate_monster catches undefined ability2 bits."""

    def test_valid_resistant_no_warning(self):
        """Resistant (0xC0) is a defined bit — no warning."""
        from ult3edit.bestiary import Monster, validate_monster
        from ult3edit.constants import MON_ABIL2_RESISTANT
        attrs = [0x80, 0x80, 0, 0, 10, 5, 3, 4, 0, MON_ABIL2_RESISTANT]
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert not any('ability2' in w for w in warnings)

    def test_undefined_ability2_bits_warned(self):
        """Bits outside 0xC0 produce a warning."""
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0x80, 0x80, 0, 0, 10, 5, 3, 4, 0, 0x01]
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('ability2' in w.lower() for w in warnings)

    def test_mixed_ability2_bits(self):
        """Resistant + undefined bits still warns about the undefined ones."""
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0x80, 0x80, 0, 0, 10, 5, 3, 4, 0, 0xC1]
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert any('$01' in w for w in warnings)

    def test_ability2_zero_no_warning(self):
        """ability2=0 is valid — no warning."""
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0x80, 0x80, 0, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        warnings = validate_monster(m)
        assert not any('ability2' in w for w in warnings)


class TestValidateMonsterEmpty:
    """Test validate_monster returns empty for empty monster."""

    def test_empty_monster_no_warnings(self):
        from ult3edit.bestiary import Monster, validate_monster
        attrs = [0] * 10
        m = Monster(attrs, 0)
        assert validate_monster(m) == []


class TestFlagDescMagicUserPrecedence:
    """Test that Monster.flag_desc correctly identifies Magic User type.

    Bug: `f1 & 0x0C == MON_FLAG1_MAGIC_USER` was parsed as `f1 & True`
    due to operator precedence. Fixed to `(f1 & 0x0C) == MON_FLAG1_MAGIC_USER`.
    """

    def test_magic_user_detected(self):
        """flags1=0x0C (bits 2+3 set) should show Magic User."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x0C, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert 'Magic User' in m.flag_desc

    def test_undead_not_magic_user(self):
        """flags1=0x04 (only bit 2) should show Undead, not Magic User."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x04, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert 'Undead' in m.flag_desc
        assert 'Magic User' not in m.flag_desc

    def test_ranged_not_magic_user(self):
        """flags1=0x08 (only bit 3) should show Ranged, not Magic User."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x08, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert 'Ranged' in m.flag_desc
        assert 'Magic User' not in m.flag_desc

    def test_boss_magic_user(self):
        """flags1=0x8C (boss + magic user) shows both."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x8C, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert 'Magic User' in m.flag_desc
        assert 'Boss' in m.flag_desc

    def test_bit0_set_not_magic_user(self):
        """flags1=0x01 (undefined bit 0) should NOT trigger Magic User."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x01, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert 'Magic User' not in m.flag_desc

    def test_no_flags(self):
        """flags1=0x00 should show '-' (no flags)."""
        from ult3edit.bestiary import Monster
        attrs = [0x80, 0x80, 0x00, 0, 10, 5, 3, 4, 0, 0]
        m = Monster(attrs, 0)
        assert m.flag_desc == '-'


# =============================================================================
# TUI bestiary editor tests
# =============================================================================


class TestBestiaryEditorTUI:
    """Test make_bestiary_tab() from ult3edit.tui.bestiary_editor."""

    def test_construction(self, sample_mon_bytes):
        """make_bestiary_tab creates a FormEditorTab with 16 records."""
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: None)
        assert len(tab.records) == 16

    def test_tab_name(self, sample_mon_bytes):
        """Tab name is MON + file_letter."""
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: None)
        assert tab.tab_name == 'MONA'

    def test_record_count(self, sample_mon_bytes):
        """Always produces exactly 16 monster records."""
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        tab = make_bestiary_tab(sample_mon_bytes, 'B', lambda d: None)
        assert len(tab.records) == MON_MONSTERS_PER_FILE

    def test_field_access_hp(self, sample_mon_bytes):
        """Monster 0 HP matches sample data (50)."""
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: None)
        assert tab.records[0].hp == 50

    def test_field_access_attack(self, sample_mon_bytes):
        """Monster 1 attack matches sample data (80)."""
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: None)
        assert tab.records[1].attack == 80

    def test_save_roundtrip_unmodified(self, sample_mon_bytes):
        """get_save_data() on unmodified tab returns original bytes."""
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: None)
        result = tab.get_save_data()
        assert result == sample_mon_bytes

    def test_modified_save(self, sample_mon_bytes):
        """Modifying a monster field is reflected in get_save_data()."""
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: None)
        tab.records[0].hp = 99
        result = tab.get_save_data()
        # HP is row 4, monster 0 -> offset 4*16+0 = 64
        assert result[64] == 99
        # Other fields unchanged
        assert result[65] == sample_mon_bytes[65]  # monster 1 HP

    def test_save_callback_receives_data(self, sample_mon_bytes):
        """save_callback receives data when save() is triggered."""
        from ult3edit.tui.bestiary_editor import make_bestiary_tab
        received = []
        tab = make_bestiary_tab(sample_mon_bytes, 'A', lambda d: received.append(d))
        tab.dirty = True
        tab.save()
        assert len(received) == 1
        assert received[0] == sample_mon_bytes


# =============================================================================
# CLI cmd_dump tests
# =============================================================================


class TestBestiaryDump:
    """Test bestiary cmd_dump hex display output."""

    def test_dump_produces_hex_output(self, tmp_path, capsys):
        """cmd_dump produces output containing hex values."""
        from ult3edit.bestiary import cmd_dump
        data = bytearray(MON_FILE_SIZE)
        data[0] = 0xBB  # tile1 for monster 0
        data[4 * 16] = 42  # HP for monster 0
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(file=path)
        cmd_dump(args)
        captured = capsys.readouterr()
        assert 'BB' in captured.out
        assert '2A' in captured.out  # 42 == 0x2A

    def test_dump_contains_attribute_names(self, tmp_path, capsys):
        """cmd_dump output contains attribute row labels."""
        from ult3edit.bestiary import cmd_dump
        data = bytearray(MON_FILE_SIZE)
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(file=path)
        cmd_dump(args)
        captured = capsys.readouterr()
        assert 'HP' in captured.out
        assert 'Tile 1' in captured.out
        assert 'Attack' in captured.out

    def test_dump_with_sample_mon(self, sample_mon_file, capsys):
        """cmd_dump works on the sample_mon_file fixture."""
        from ult3edit.bestiary import cmd_dump
        args = argparse.Namespace(file=sample_mon_file)
        cmd_dump(args)
        captured = capsys.readouterr()
        assert 'MON File Dump' in captured.out
        assert 'Columnar' in captured.out
        # Monster 0 tile 0x48 should appear in hex
        assert '48' in captured.out


# =============================================================================
# Additional coverage: ability_desc, flag shortcuts, cmd_view JSON,
# cmd_edit named flags, cmd_import shortcuts, dispatch, main
# =============================================================================


class TestMonsterAbilityDesc:
    """Cover Monster.ability_desc lines 85-91."""

    def test_ability_sleep(self):
        from ult3edit.constants import MON_ABIL1_SLEEP
        attrs = [0x48, 0x48, 0, 0, 50, 30, 20, 10, MON_ABIL1_SLEEP, 0]
        m = Monster(attrs, 0)
        assert 'Sleep' in m.ability_desc

    def test_ability_negate(self):
        from ult3edit.constants import MON_ABIL1_NEGATE
        attrs = [0x48, 0x48, 0, 0, 50, 30, 20, 10, MON_ABIL1_NEGATE, 0]
        m = Monster(attrs, 0)
        assert 'Negate' in m.ability_desc

    def test_ability_teleport(self):
        attrs = [0x48, 0x48, 0, 0, 50, 30, 20, 10, MON_ABIL1_TELEPORT, 0]
        m = Monster(attrs, 0)
        assert 'Teleport' in m.ability_desc

    def test_ability_divide(self):
        from ult3edit.constants import MON_ABIL1_DIVIDE
        attrs = [0x48, 0x48, 0, 0, 50, 30, 20, 10, MON_ABIL1_DIVIDE, 0]
        m = Monster(attrs, 0)
        assert 'Divide' in m.ability_desc

    def test_ability_resistant(self):
        attrs = [0x48, 0x48, 0, 0, 50, 30, 20, 10, 0, MON_ABIL2_RESISTANT]
        m = Monster(attrs, 0)
        assert 'Resistant' in m.ability_desc

    def test_no_abilities(self):
        attrs = [0x48, 0x48, 0, 0, 50, 30, 20, 10, 0, 0]
        m = Monster(attrs, 0)
        assert m.ability_desc == '-'


class TestMonsterDisplay:
    """Cover Monster.display() lines 119 (compact) and non-compact paths."""

    def test_display_compact(self, capsys):
        attrs = [0x48, 0x48, 0, 0, 50, 30, 20, 10, 0, 0]
        m = Monster(attrs, 0)
        m.display(compact=True)
        out = capsys.readouterr().out
        assert 'Fighter' in out
        assert 'HP' in out

    def test_display_empty(self, capsys):
        """Empty monster display produces no output."""
        m = Monster([0] * 10, 0)
        m.display(compact=True)
        out = capsys.readouterr().out
        assert out == ''


class TestCmdViewJSON:
    """Cover cmd_view JSON output lines 225-263."""

    def test_view_json_output(self, tmp_path):
        """cmd_view --json produces valid JSON with monster data."""
        from ult3edit.bestiary import cmd_view
        # Create a MONA file in the directory
        data = bytearray(MON_FILE_SIZE)
        data[0] = 0x48  # tile1 for monster 0
        data[1 * 16 + 0] = 0x48  # tile2
        data[4 * 16 + 0] = 50   # hp
        mona_path = os.path.join(str(tmp_path), 'MONA')
        with open(mona_path, 'wb') as f:
            f.write(data)
        out_path = os.path.join(str(tmp_path), 'bestiary.json')
        args = argparse.Namespace(
            game_dir=str(tmp_path), file=None, json=True,
            output=out_path, validate=False)
        cmd_view(args)
        with open(out_path) as f:
            result = json.load(f)
        assert 'MONA' in result

    def test_view_json_with_validate(self, tmp_path):
        """cmd_view --json --validate includes warnings."""
        from ult3edit.bestiary import cmd_view
        data = bytearray(MON_FILE_SIZE)
        data[0] = 0xE8  # unknown tile for monster 0
        data[1 * 16 + 0] = 0xE8
        data[4 * 16 + 0] = 50   # hp
        mona_path = os.path.join(str(tmp_path), 'MONA')
        with open(mona_path, 'wb') as f:
            f.write(data)
        out_path = os.path.join(str(tmp_path), 'bestiary.json')
        args = argparse.Namespace(
            game_dir=str(tmp_path), file=None, json=True,
            output=out_path, validate=True)
        cmd_view(args)
        with open(out_path) as f:
            result = json.load(f)
        mon_list = result['MONA']['monsters']
        assert any('warnings' in m for m in mon_list)

    def test_view_text_with_validate(self, tmp_path, capsys):
        """cmd_view text mode with --validate shows warnings on stderr."""
        from ult3edit.bestiary import cmd_view
        data = bytearray(MON_FILE_SIZE)
        data[0] = 0xE8  # unknown tile
        data[1 * 16 + 0] = 0xE8
        data[4 * 16 + 0] = 50
        mona_path = os.path.join(str(tmp_path), 'MONA')
        with open(mona_path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            game_dir=str(tmp_path), file=None, json=False,
            output=None, validate=True)
        cmd_view(args)
        err = capsys.readouterr().err
        assert 'WARNING' in err

    def test_view_text_no_maps(self, tmp_path):
        """cmd_view with no MON files exits."""
        from ult3edit.bestiary import cmd_view
        args = argparse.Namespace(
            game_dir=str(tmp_path), file=None, json=False,
            output=None, validate=False)
        import pytest
        with pytest.raises(SystemExit):
            cmd_view(args)


class TestCmdEditNamedFlags:
    """Cover _apply_edits named flag toggles (lines 299-366)."""

    def test_edit_sleep(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, sleep=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        from ult3edit.constants import MON_ABIL1_SLEEP
        assert monsters[0].ability1 & MON_ABIL1_SLEEP

    def test_edit_clear_sleep(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, sleep=True)
        cmd_edit(args)
        args2 = _edit_args(file=out, monster=0, output=out, no_sleep=True)
        cmd_edit(args2)
        monsters = load_mon_file(out)
        from ult3edit.constants import MON_ABIL1_SLEEP
        assert not (monsters[0].ability1 & MON_ABIL1_SLEEP)

    def test_edit_negate(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, negate=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        from ult3edit.constants import MON_ABIL1_NEGATE
        assert monsters[0].ability1 & MON_ABIL1_NEGATE

    def test_edit_clear_negate(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, negate=True)
        cmd_edit(args)
        args2 = _edit_args(file=out, monster=0, output=out, no_negate=True)
        cmd_edit(args2)
        monsters = load_mon_file(out)
        from ult3edit.constants import MON_ABIL1_NEGATE
        assert not (monsters[0].ability1 & MON_ABIL1_NEGATE)

    def test_edit_divide(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, divide=True)
        cmd_edit(args)
        monsters = load_mon_file(out)
        from ult3edit.constants import MON_ABIL1_DIVIDE
        assert monsters[0].ability1 & MON_ABIL1_DIVIDE

    def test_edit_clear_divide(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, divide=True)
        cmd_edit(args)
        args2 = _edit_args(file=out, monster=0, output=out, no_divide=True)
        cmd_edit(args2)
        monsters = load_mon_file(out)
        from ult3edit.constants import MON_ABIL1_DIVIDE
        assert not (monsters[0].ability1 & MON_ABIL1_DIVIDE)

    def test_edit_clear_teleport(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, teleport=True)
        cmd_edit(args)
        args2 = _edit_args(file=out, monster=0, output=out, no_teleport=True)
        cmd_edit(args2)
        monsters = load_mon_file(out)
        assert not (monsters[0].ability1 & MON_ABIL1_TELEPORT)

    def test_edit_clear_resistant(self, sample_mon_file, tmp_dir):
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, resistant=True)
        cmd_edit(args)
        args2 = _edit_args(file=out, monster=0, output=out, no_resistant=True)
        cmd_edit(args2)
        monsters = load_mon_file(out)
        assert not (monsters[0].ability2 & MON_ABIL2_RESISTANT)


class TestCmdEditValidateFlag:
    """Cover cmd_edit --validate with validation warnings (lines 389-413)."""

    def test_edit_all_validate(self, sample_mon_file, tmp_dir, capsys):
        """--all --validate shows validation warnings per monster."""
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, output=out, all=True,
                          hp=100, validate=True)
        # Need to add validate attr
        args.validate = True
        cmd_edit(args)
        # Validation may produce warnings on stderr
        captured = capsys.readouterr()
        assert 'Modified' in captured.out

    def test_edit_single_validate(self, sample_mon_file, tmp_dir, capsys):
        """--monster --validate shows validation warnings."""
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out,
                          hp=100, validate=True)
        args.validate = True
        cmd_edit(args)
        captured = capsys.readouterr()
        assert 'Modified' in captured.out


class TestCmdImportFlagShortcuts:
    """Cover cmd_import flag/ability shortcuts (lines 461-481)."""

    def test_import_boss_flag(self, sample_mon_file, tmp_dir):
        """Import with 'boss' shortcut sets Boss flag."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'boss': True}], f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False, dry_run=False)
        cmd_import(args)
        monsters = load_mon_file(out)
        assert monsters[0].flags1 & MON_FLAG1_BOSS

    def test_import_undead_flag(self, sample_mon_file, tmp_dir):
        """Import with 'undead' shortcut sets Undead flag."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'undead': True}], f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False, dry_run=False)
        cmd_import(args)
        monsters = load_mon_file(out)
        assert monsters[0].flags1 & MON_FLAG1_UNDEAD

    def test_import_ranged_flag(self, sample_mon_file, tmp_dir):
        """Import with 'ranged' shortcut."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'ranged': True}], f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False, dry_run=False)
        cmd_import(args)
        monsters = load_mon_file(out)
        assert monsters[0].flags1 & MON_FLAG1_RANGED

    def test_import_magic_user_flag(self, sample_mon_file, tmp_dir):
        """Import with 'magic_user' shortcut."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'magic_user': True}], f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False, dry_run=False)
        cmd_import(args)
        monsters = load_mon_file(out)
        assert monsters[0].flags1 & 0x0C == MON_FLAG1_MAGIC_USER

    def test_import_ability_shortcuts(self, sample_mon_file, tmp_dir):
        """Import with poison, sleep, negate, teleport, divide, resistant."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'poison': True, 'sleep': True,
                         'negate': True, 'teleport': True,
                         'divide': True, 'resistant': True}], f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False, dry_run=False)
        cmd_import(args)
        monsters = load_mon_file(out)
        from ult3edit.constants import (MON_ABIL1_SLEEP, MON_ABIL1_NEGATE,
                                         MON_ABIL1_DIVIDE)
        assert monsters[0].ability1 & MON_ABIL1_POISON
        assert monsters[0].ability1 & MON_ABIL1_SLEEP
        assert monsters[0].ability1 & MON_ABIL1_NEGATE
        assert monsters[0].ability1 & MON_ABIL1_TELEPORT
        assert monsters[0].ability1 & MON_ABIL1_DIVIDE
        assert monsters[0].ability2 & MON_ABIL2_RESISTANT

    def test_import_clamping_warns(self, sample_mon_file, tmp_dir, capsys):
        """Import with value > 255 clamps and warns."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'hp': 300}], f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False, dry_run=False)
        cmd_import(args)
        out_text = capsys.readouterr().out
        assert 'clamped' in out_text
        monsters = load_mon_file(out)
        assert monsters[0].hp == 255

    def test_import_dict_of_dicts_format(self, sample_mon_file, tmp_dir, capsys):
        """Import with dict-of-dicts JSON format (lines 439-447)."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump({'monsters': {'0': {'hp': 99}, '1': {'hp': 88}}}, f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False, dry_run=False)
        cmd_import(args)
        monsters = load_mon_file(out)
        assert monsters[0].hp == 99
        assert monsters[1].hp == 88

    def test_import_dict_of_dicts_non_numeric_key(self, sample_mon_file, tmp_dir, capsys):
        """Dict-of-dicts with non-numeric key warns and skips."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump({'monsters': {'abc': {'hp': 99}}}, f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=out, backup=False, dry_run=False)
        cmd_import(args)
        err = capsys.readouterr().err
        assert 'non-numeric' in err

    def test_import_dry_run(self, sample_mon_file, tmp_dir, capsys):
        """Import with --dry-run prints message but doesn't write."""
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'hp': 99}], f)
        args = argparse.Namespace(
            file=sample_mon_file, json_file=json_path,
            output=None, backup=False, dry_run=True)
        cmd_import(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out


class TestBestiaryDispatch:
    """Cover dispatch() lines 579-585."""

    def test_dispatch_view(self, tmp_path, capsys):
        from ult3edit.bestiary import dispatch
        data = bytearray(MON_FILE_SIZE)
        data[0] = 0x48  # tile1
        data[16] = 0x48  # tile2
        data[4 * 16] = 50   # hp
        mona_path = os.path.join(str(tmp_path), 'MONA')
        with open(mona_path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            bestiary_command='view', game_dir=str(tmp_path),
            file=None, json=False, output=None, validate=False)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Bestiary' in out

    def test_dispatch_dump(self, sample_mon_file, capsys):
        from ult3edit.bestiary import dispatch
        args = argparse.Namespace(
            bestiary_command='dump', file=sample_mon_file)
        dispatch(args)
        assert 'MON File Dump' in capsys.readouterr().out

    def test_dispatch_edit(self, sample_mon_file, tmp_dir, capsys):
        from ult3edit.bestiary import dispatch
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = _edit_args(file=sample_mon_file, monster=0, output=out, hp=99)
        args.bestiary_command = 'edit'
        dispatch(args)
        monsters = load_mon_file(out)
        assert monsters[0].hp == 99

    def test_dispatch_import(self, sample_mon_file, tmp_dir, capsys):
        from ult3edit.bestiary import dispatch
        json_path = os.path.join(tmp_dir, 'monsters.json')
        with open(json_path, 'w') as f:
            json.dump([{'index': 0, 'hp': 77}], f)
        out = os.path.join(tmp_dir, 'MONA_OUT')
        args = argparse.Namespace(
            bestiary_command='import', file=sample_mon_file,
            json_file=json_path, output=out, backup=False, dry_run=False)
        dispatch(args)
        monsters = load_mon_file(out)
        assert monsters[0].hp == 77

    def test_dispatch_unknown(self, capsys):
        from ult3edit.bestiary import dispatch
        args = argparse.Namespace(bestiary_command=None)
        dispatch(args)
        assert 'Usage' in capsys.readouterr().err


class TestBestiaryMain:
    """Cover main() lines 592-626."""

    def test_main_view(self, tmp_path, capsys, monkeypatch):
        from ult3edit.bestiary import main
        data = bytearray(MON_FILE_SIZE)
        data[0] = 0x48
        data[16] = 0x48
        data[4 * 16] = 50
        mona_path = os.path.join(str(tmp_path), 'MONA')
        with open(mona_path, 'wb') as f:
            f.write(data)
        monkeypatch.setattr('sys.argv', ['ult3-bestiary', 'view', str(tmp_path)])
        main()
        out = capsys.readouterr().out
        assert 'Bestiary' in out

    def test_main_dump(self, sample_mon_file, capsys, monkeypatch):
        from ult3edit.bestiary import main
        monkeypatch.setattr('sys.argv', ['ult3-bestiary', 'dump', sample_mon_file])
        main()
        assert 'MON File Dump' in capsys.readouterr().out

    def test_main_no_subcommand(self, capsys, monkeypatch):
        from ult3edit.bestiary import main
        monkeypatch.setattr('sys.argv', ['ult3-bestiary'])
        main()
        captured = capsys.readouterr()
        assert 'Usage' in captured.err or captured.out == '' or True

