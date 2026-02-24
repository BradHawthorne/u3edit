"""Tests for bestiary tool."""

import argparse
import json
import os

from ult3edit.bestiary import (
    Monster, load_mon_file, save_mon_file, cmd_edit, cmd_import, validate_monster,
)
from ult3edit.constants import (
    MON_MONSTERS_PER_FILE,
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
