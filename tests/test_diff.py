"""Tests for diff tool."""

import argparse
import json
import os
import pytest

from ult3edit.diff import (
    FieldDiff, EntityDiff, FileDiff, GameDiff,
    diff_dicts, _diff_lists, diff_roster, diff_bestiary, diff_map, diff_special,
    _diff_prty, _diff_plrs, diff_tlk, detect_file_type, diff_file,
    diff_directories, diff_binary,
    format_text, format_summary, to_json, cmd_diff, dispatch,
)
from ult3edit.constants import (
    CHAR_RECORD_SIZE, CHAR_HP_HI, CHAR_STATUS, ROSTER_FILE_SIZE, CHAR_STR,
    MON_FILE_SIZE, PRTY_FILE_SIZE, PLRS_FILE_SIZE, SPECIAL_FILE_SIZE,
    CON_FILE_SIZE, MAP_OVERWORLD_SIZE, MAP_DUNGEON_SIZE, PRTY_OFF_TRANSPORT,
)
from ult3edit.bcd import int_to_bcd
from ult3edit.tlk import encode_record


# =============================================================================
# Core diff algorithm tests
# =============================================================================

class TestDiffDicts:
    def test_identical(self):
        d = {'hp': 100, 'name': 'HERO'}
        assert diff_dicts(d, d) == []

    def test_scalar_change(self):
        diffs = diff_dicts({'hp': 100}, {'hp': 200})
        assert len(diffs) == 1
        assert diffs[0].path == 'hp'
        assert diffs[0].old == 100
        assert diffs[0].new == 200

    def test_nested_dict(self):
        d1 = {'stats': {'str': 25, 'dex': 30}}
        d2 = {'stats': {'str': 50, 'dex': 30}}
        diffs = diff_dicts(d1, d2)
        assert len(diffs) == 1
        assert diffs[0].path == 'stats.str'

    def test_list_change(self):
        d1 = {'marks': ['Kings', 'Force']}
        d2 = {'marks': ['Kings', 'Snake']}
        diffs = diff_dicts(d1, d2)
        assert len(diffs) == 1
        assert diffs[0].path == 'marks[1]'

    def test_added_key(self):
        diffs = diff_dicts({}, {'hp': 100})
        assert len(diffs) == 1
        assert diffs[0].old is None
        assert diffs[0].new == 100

    def test_removed_key(self):
        diffs = diff_dicts({'hp': 100}, {})
        assert len(diffs) == 1
        assert diffs[0].old == 100
        assert diffs[0].new is None

    def test_empty_dicts(self):
        assert diff_dicts({}, {}) == []

    def test_list_length_mismatch(self):
        d1 = {'items': [1, 2]}
        d2 = {'items': [1, 2, 3]}
        diffs = diff_dicts(d1, d2)
        assert len(diffs) == 1
        assert diffs[0].path == 'items[2]'
        assert diffs[0].old is None
        assert diffs[0].new == 3


# =============================================================================
# Roster diff tests
# =============================================================================

class TestDiffRoster:
    def test_identical(self, tmp_dir, sample_roster_bytes):
        p1 = os.path.join(tmp_dir, 'ROST1')
        p2 = os.path.join(tmp_dir, 'ROST2')
        for p in (p1, p2):
            with open(p, 'wb') as f:
                f.write(sample_roster_bytes)
        fd = diff_roster(p1, p2)
        assert not fd.changed

    def test_stat_change(self, tmp_dir, sample_roster_bytes):
        data2 = bytearray(sample_roster_bytes)
        data2[CHAR_STR] = int_to_bcd(50)  # Change STR from 25 to 50
        p1 = os.path.join(tmp_dir, 'ROST1')
        p2 = os.path.join(tmp_dir, 'ROST2')
        with open(p1, 'wb') as f:
            f.write(sample_roster_bytes)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_roster(p1, p2)
        assert fd.changed
        assert any('str' in f.path for e in fd.entities for f in e.fields)

    def test_added_character(self, tmp_dir, sample_character_bytes):
        data1 = bytearray(ROSTER_FILE_SIZE)  # Empty roster
        data2 = bytearray(ROSTER_FILE_SIZE)
        data2[:CHAR_RECORD_SIZE] = sample_character_bytes  # Slot 0 populated
        p1 = os.path.join(tmp_dir, 'ROST1')
        p2 = os.path.join(tmp_dir, 'ROST2')
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_roster(p1, p2)
        assert fd.changed
        assert len(fd.added_entities) == 1
        assert 'Slot 0' in fd.added_entities[0]

    def test_removed_character(self, tmp_dir, sample_character_bytes):
        data1 = bytearray(ROSTER_FILE_SIZE)
        data1[:CHAR_RECORD_SIZE] = sample_character_bytes
        data2 = bytearray(ROSTER_FILE_SIZE)  # Empty roster
        p1 = os.path.join(tmp_dir, 'ROST1')
        p2 = os.path.join(tmp_dir, 'ROST2')
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_roster(p1, p2)
        assert fd.changed
        assert len(fd.removed_entities) == 1


# =============================================================================
# Bestiary diff tests
# =============================================================================

class TestDiffBestiary:
    def test_identical(self, tmp_dir, sample_mon_bytes):
        p1 = os.path.join(tmp_dir, 'MONA1')
        p2 = os.path.join(tmp_dir, 'MONA2')
        for p in (p1, p2):
            with open(p, 'wb') as f:
                f.write(sample_mon_bytes)
        fd = diff_bestiary(p1, p2, 'A')
        assert not fd.changed

    def test_hp_change(self, tmp_dir, sample_mon_bytes):
        data2 = bytearray(sample_mon_bytes)
        data2[4 * 16 + 0] = 99  # Monster 0 HP: 50 -> 99
        p1 = os.path.join(tmp_dir, 'MONA1')
        p2 = os.path.join(tmp_dir, 'MONA2')
        with open(p1, 'wb') as f:
            f.write(sample_mon_bytes)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_bestiary(p1, p2, 'A')
        assert fd.changed
        assert any('hp' in f.path for e in fd.entities for f in e.fields)

    def test_empty_ignored(self, tmp_dir):
        """Empty monster slots don't generate diffs."""
        data = bytearray(MON_FILE_SIZE)
        p1 = os.path.join(tmp_dir, 'MONA1')
        p2 = os.path.join(tmp_dir, 'MONA2')
        for p in (p1, p2):
            with open(p, 'wb') as f:
                f.write(data)
        fd = diff_bestiary(p1, p2, 'A')
        assert not fd.changed


# =============================================================================
# Map diff tests
# =============================================================================

class TestDiffMap:
    def test_identical(self, tmp_dir, sample_overworld_bytes):
        p1 = os.path.join(tmp_dir, 'MAPA1')
        p2 = os.path.join(tmp_dir, 'MAPA2')
        for p in (p1, p2):
            with open(p, 'wb') as f:
                f.write(sample_overworld_bytes)
        fd = diff_map(p1, p2, 'MAPA')
        assert not fd.changed

    def test_single_tile(self, tmp_dir, sample_overworld_bytes):
        data2 = bytearray(sample_overworld_bytes)
        data2[0] = 0xFF  # Change tile at (0,0)
        p1 = os.path.join(tmp_dir, 'MAPA1')
        p2 = os.path.join(tmp_dir, 'MAPA2')
        with open(p1, 'wb') as f:
            f.write(sample_overworld_bytes)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_map(p1, p2, 'MAPA')
        assert fd.tile_changes == 1
        assert fd.tile_positions == [(0, 0)]

    def test_many_tiles(self, tmp_dir):
        """More than 20 tile changes gets truncated in text output."""
        data1 = bytearray(4096)
        data2 = bytearray(4096)
        for i in range(50):
            data2[i] = 0xFF
        p1 = os.path.join(tmp_dir, 'MAPA1')
        p2 = os.path.join(tmp_dir, 'MAPA2')
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_map(p1, p2, 'MAPA')
        assert fd.tile_changes == 50


# =============================================================================
# Save diff tests
# =============================================================================

class TestDiffSave:
    def test_prty_change(self, tmp_dir, sample_prty_bytes):
        data2 = bytearray(sample_prty_bytes)
        data2[3] = 44  # Change saved X from 32 to 44
        p1 = os.path.join(tmp_dir, 'PRTY1')
        p2 = os.path.join(tmp_dir, 'PRTY2')
        with open(p1, 'wb') as f:
            f.write(sample_prty_bytes)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = _diff_prty(p1, p2)
        assert fd.changed
        assert any('x' in f.path for e in fd.entities for f in e.fields)

    def test_prty_identical(self, tmp_dir, sample_prty_bytes):
        p1 = os.path.join(tmp_dir, 'PRTY1')
        p2 = os.path.join(tmp_dir, 'PRTY2')
        for p in (p1, p2):
            with open(p, 'wb') as f:
                f.write(sample_prty_bytes)
        fd = _diff_prty(p1, p2)
        assert not fd.changed


# =============================================================================
# Special location diff tests
# =============================================================================

class TestDiffSpecial:
    def test_identical(self, tmp_dir, sample_special_bytes):
        p1 = os.path.join(tmp_dir, 'BRND1')
        p2 = os.path.join(tmp_dir, 'BRND2')
        for p in (p1, p2):
            with open(p, 'wb') as f:
                f.write(sample_special_bytes)
        fd = diff_special(p1, p2, 'BRND')
        assert not fd.changed

    def test_tile_change(self, tmp_dir, sample_special_bytes):
        data2 = bytearray(sample_special_bytes)
        data2[0] = 0xFF
        p1 = os.path.join(tmp_dir, 'BRND1')
        p2 = os.path.join(tmp_dir, 'BRND2')
        with open(p1, 'wb') as f:
            f.write(sample_special_bytes)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_special(p1, p2, 'BRND')
        assert fd.tile_changes == 1


# =============================================================================
# File type detection tests
# =============================================================================

class TestDetectFileType:
    def test_rost(self, tmp_dir):
        path = os.path.join(tmp_dir, 'ROST#069500')
        with open(path, 'wb') as f:
            f.write(bytearray(ROSTER_FILE_SIZE))
        assert detect_file_type(path) == 'ROST'

    def test_mon(self, tmp_dir):
        path = os.path.join(tmp_dir, 'MONA#069900')
        with open(path, 'wb') as f:
            f.write(bytearray(MON_FILE_SIZE))
        assert detect_file_type(path) == 'MONA'

    def test_prty(self, tmp_dir):
        path = os.path.join(tmp_dir, 'PRTY')
        with open(path, 'wb') as f:
            f.write(bytearray(PRTY_FILE_SIZE))
        assert detect_file_type(path) == 'PRTY'

    def test_special(self, tmp_dir):
        path = os.path.join(tmp_dir, 'BRND')
        with open(path, 'wb') as f:
            f.write(bytearray(SPECIAL_FILE_SIZE))
        assert detect_file_type(path) == 'BRND'

    def test_unknown(self, tmp_dir):
        path = os.path.join(tmp_dir, 'UNKNOWN')
        with open(path, 'wb') as f:
            f.write(bytearray(42))
        assert detect_file_type(path) is None


# =============================================================================
# Format output tests
# =============================================================================

class TestFormatText:
    def test_no_changes(self):
        gd = GameDiff()
        assert 'No differences' in format_text(gd)

    def test_field_changes(self):
        gd = GameDiff()
        fd = FileDiff('ROST', 'ROST')
        ed = EntityDiff('character', 'Slot 0: HERO')
        ed.fields.append(FieldDiff('hp', 100, 200))
        fd.entities.append(ed)
        gd.files.append(fd)
        text = format_text(gd)
        assert '--- ROST' in text
        assert 'Slot 0: HERO' in text
        assert '100 -> 200' in text

    def test_tile_changes_truncated(self):
        gd = GameDiff()
        fd = FileDiff('MAPA', 'MAPA')
        fd.tile_changes = 25
        fd.tile_positions = [(x, 0) for x in range(25)]
        gd.files.append(fd)
        text = format_text(gd)
        assert 'Tiles changed: 25' in text
        assert '... and 15 more' in text

    def test_added_removed(self):
        gd = GameDiff()
        fd = FileDiff('ROST', 'ROST')
        fd.added_entities.append('Slot 3: MAGE')
        fd.removed_entities.append('Slot 5: THIEF')
        gd.files.append(fd)
        text = format_text(gd)
        assert '+ Added: Slot 3: MAGE' in text
        assert '- Removed: Slot 5: THIEF' in text


class TestFormatSummary:
    def test_no_changes(self):
        gd = GameDiff()
        assert 'No differences' in format_summary(gd)

    def test_counts(self):
        gd = GameDiff()
        fd = FileDiff('ROST', 'ROST')
        ed = EntityDiff('character', 'Slot 0')
        ed.fields.append(FieldDiff('hp', 1, 2))
        fd.entities.append(ed)
        fd.added_entities.append('Slot 1')
        gd.files.append(fd)
        text = format_summary(gd)
        assert 'ROST: 1 changed, 1 added' in text
        assert 'Total: 1 file(s)' in text


class TestFormatJson:
    def test_structure(self):
        gd = GameDiff()
        fd = FileDiff('ROST', 'ROST')
        ed = EntityDiff('character', 'Slot 0')
        ed.fields.append(FieldDiff('hp', 100, 200))
        fd.entities.append(ed)
        gd.files.append(fd)
        result = to_json(gd)
        assert 'files' in result
        assert len(result['files']) == 1
        assert result['files'][0]['file'] == 'ROST'
        assert len(result['files'][0]['entities']) == 1
        changes = result['files'][0]['entities'][0]['changes']
        assert changes[0]['field'] == 'hp'
        assert changes[0]['old'] == 100
        assert changes[0]['new'] == 200

    def test_empty(self):
        gd = GameDiff()
        result = to_json(gd)
        assert result == {'files': []}


# =============================================================================
# CLI integration tests
# =============================================================================

class TestCmdDiff:
    def test_text_output(self, tmp_dir, sample_roster_bytes, capsys):
        data2 = bytearray(sample_roster_bytes)
        data2[CHAR_STR] = int_to_bcd(50)
        # Use subdirs so both files can be named ROST
        d1 = os.path.join(tmp_dir, 'a')
        d2 = os.path.join(tmp_dir, 'b')
        os.makedirs(d1)
        os.makedirs(d2)
        p1 = os.path.join(d1, 'ROST')
        p2 = os.path.join(d2, 'ROST')
        with open(p1, 'wb') as f:
            f.write(sample_roster_bytes)
        with open(p2, 'wb') as f:
            f.write(data2)
        args = argparse.Namespace(
            path1=p1, path2=p2, json=False, summary=False, output=None,
        )
        cmd_diff(args)
        output = capsys.readouterr().out
        assert 'ROST' in output

    def test_json_output(self, tmp_dir, sample_roster_bytes):
        d1 = os.path.join(tmp_dir, 'a')
        d2 = os.path.join(tmp_dir, 'b')
        os.makedirs(d1)
        os.makedirs(d2)
        p1 = os.path.join(d1, 'ROST')
        p2 = os.path.join(d2, 'ROST')
        for p in (p1, p2):
            with open(p, 'wb') as f:
                f.write(sample_roster_bytes)
        json_out = os.path.join(tmp_dir, 'diff.json')
        args = argparse.Namespace(
            path1=p1, path2=p2, json=True, summary=False, output=json_out,
        )
        cmd_diff(args)
        with open(json_out) as f:
            result = json.load(f)
        assert 'files' in result

    def test_summary_output(self, tmp_dir, sample_roster_bytes, capsys):
        data2 = bytearray(sample_roster_bytes)
        data2[CHAR_STR] = int_to_bcd(50)
        d1 = os.path.join(tmp_dir, 'a')
        d2 = os.path.join(tmp_dir, 'b')
        os.makedirs(d1)
        os.makedirs(d2)
        p1 = os.path.join(d1, 'ROST')
        p2 = os.path.join(d2, 'ROST')
        with open(p1, 'wb') as f:
            f.write(sample_roster_bytes)
        with open(p2, 'wb') as f:
            f.write(data2)
        args = argparse.Namespace(
            path1=p1, path2=p2, json=False, summary=True, output=None,
        )
        cmd_diff(args)
        output = capsys.readouterr().out
        assert 'changed' in output
        assert 'Total' in output

    def test_mixed_file_dir_error(self, tmp_dir, sample_roster_bytes):
        p1 = os.path.join(tmp_dir, 'ROST')
        with open(p1, 'wb') as f:
            f.write(sample_roster_bytes)
        args = argparse.Namespace(
            path1=p1, path2=tmp_dir, json=False, summary=False, output=None,
        )
        with pytest.raises(SystemExit):
            cmd_diff(args)


# =============================================================================
# Directory diff test
# =============================================================================

class TestDiffDirectories:
    def test_identical_dirs(self, tmp_dir, sample_roster_bytes, sample_mon_bytes):
        dir1 = os.path.join(tmp_dir, 'game1')
        dir2 = os.path.join(tmp_dir, 'game2')
        os.makedirs(dir1)
        os.makedirs(dir2)
        for d in (dir1, dir2):
            with open(os.path.join(d, 'ROST'), 'wb') as f:
                f.write(sample_roster_bytes)
            with open(os.path.join(d, 'MONA'), 'wb') as f:
                f.write(sample_mon_bytes)
        gd = diff_directories(dir1, dir2)
        assert not gd.changed

    def test_with_changes(self, tmp_dir, sample_roster_bytes, sample_mon_bytes):
        dir1 = os.path.join(tmp_dir, 'game1')
        dir2 = os.path.join(tmp_dir, 'game2')
        os.makedirs(dir1)
        os.makedirs(dir2)
        # Same roster in both
        for d in (dir1, dir2):
            with open(os.path.join(d, 'ROST'), 'wb') as f:
                f.write(sample_roster_bytes)
        # Modified bestiary in dir2
        with open(os.path.join(dir1, 'MONA'), 'wb') as f:
            f.write(sample_mon_bytes)
        data2 = bytearray(sample_mon_bytes)
        data2[4 * 16 + 0] = 99  # Monster 0 HP changed
        with open(os.path.join(dir2, 'MONA'), 'wb') as f:
            f.write(data2)
        gd = diff_directories(dir1, dir2)
        assert gd.changed
        changed = [f for f in gd.files if f.changed]
        assert len(changed) == 1
        assert changed[0].file_name == 'MONA'

    def test_missing_files_skipped(self, tmp_dir, sample_roster_bytes):
        dir1 = os.path.join(tmp_dir, 'game1')
        dir2 = os.path.join(tmp_dir, 'game2')
        os.makedirs(dir1)
        os.makedirs(dir2)
        # Only dir1 has ROST
        with open(os.path.join(dir1, 'ROST'), 'wb') as f:
            f.write(sample_roster_bytes)
        gd = diff_directories(dir1, dir2)
        # ROST should be skipped since it only exists in one dir
        assert not gd.changed


# ── Migrated from test_new_features.py ──

class TestDiffCommands:
    """Tests for diff cmd_diff."""

    def test_diff_identical_rosters(self, tmp_path, capsys):
        """Diffing identical roster files shows no changes."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import ROSTER_FILE_SIZE
        d1 = tmp_path / 'a'
        d2 = tmp_path / 'b'
        d1.mkdir()
        d2.mkdir()
        data = bytes(ROSTER_FILE_SIZE)
        (d1 / 'ROST').write_bytes(data)
        (d2 / 'ROST').write_bytes(data)
        args = argparse.Namespace(
            path1=str(d1 / 'ROST'), path2=str(d2 / 'ROST'),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'No differences' in out or 'identical' in out.lower() or out.strip() == ''

    def test_diff_modified_roster(self, tmp_path, capsys):
        """Diffing rosters with different names shows change."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import ROSTER_FILE_SIZE
        d1 = bytearray(ROSTER_FILE_SIZE)
        d2 = bytearray(ROSTER_FILE_SIZE)
        # Set a name in slot 0 of d2
        name = 'HERO'
        for i, ch in enumerate(name):
            d2[i] = ord(ch) | 0x80  # high-ASCII
        d2[0x0D] = 0x00  # null terminator
        d2[0x12] = 0x10  # STR=10 in BCD
        da = tmp_path / 'a'
        db = tmp_path / 'b'
        da.mkdir()
        db.mkdir()
        (da / 'ROST').write_bytes(bytes(d1))
        (db / 'ROST').write_bytes(bytes(d2))
        args = argparse.Namespace(
            path1=str(da / 'ROST'), path2=str(db / 'ROST'),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'HERO' in out or 'name' in out.lower()

    def test_diff_json_output(self, tmp_path):
        """Diff --json produces valid JSON."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import ROSTER_FILE_SIZE
        d1 = bytearray(ROSTER_FILE_SIZE)
        d2 = bytearray(ROSTER_FILE_SIZE)
        d2[0x12] = 0x50  # Change STR in slot 0
        da = tmp_path / 'a'
        db = tmp_path / 'b'
        da.mkdir()
        db.mkdir()
        (da / 'ROST').write_bytes(bytes(d1))
        (db / 'ROST').write_bytes(bytes(d2))
        outfile = tmp_path / 'diff.json'
        args = argparse.Namespace(
            path1=str(da / 'ROST'), path2=str(db / 'ROST'),
            json=True, summary=False, output=str(outfile))
        cmd_diff(args)
        result = json.loads(outfile.read_text())
        assert 'files' in result

    def test_diff_summary_mode(self, tmp_path, capsys):
        """Diff --summary shows counts."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import MAP_OVERWORLD_SIZE
        m1 = bytearray(MAP_OVERWORLD_SIZE)
        m2 = bytearray(MAP_OVERWORLD_SIZE)
        m2[0] = 0x01  # Change one tile
        f1 = tmp_path / 'MAPA'
        f2 = tmp_path / 'MAPA2'
        f1.write_bytes(bytes(m1))
        f2.write_bytes(bytes(m2))
        args = argparse.Namespace(
            path1=str(f1), path2=str(f2),
            json=False, summary=True, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        # Summary should mention changes
        assert '1' in out or 'change' in out.lower() or 'tile' in out.lower()

    def test_diff_mismatched_types_exits(self, tmp_path):
        """Diffing a file against a directory exits with error."""
        from ult3edit.diff import cmd_diff
        f1 = tmp_path / 'FILE'
        f1.write_bytes(b'\x00')
        d2 = tmp_path / 'DIR'
        d2.mkdir()
        args = argparse.Namespace(
            path1=str(f1), path2=str(d2),
            json=False, summary=False, output=None)
        with pytest.raises(SystemExit):
            cmd_diff(args)

    def test_diff_directories(self, tmp_path, capsys):
        """Diffing two directories compares matching files."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import ROSTER_FILE_SIZE
        d1 = tmp_path / 'game1'
        d2 = tmp_path / 'game2'
        d1.mkdir()
        d2.mkdir()
        data1 = bytearray(ROSTER_FILE_SIZE)
        data2 = bytearray(ROSTER_FILE_SIZE)
        data2[0x12] = 0x50  # Change STR
        (d1 / 'ROST').write_bytes(bytes(data1))
        (d2 / 'ROST').write_bytes(bytes(data2))
        args = argparse.Namespace(
            path1=str(d1), path2=str(d2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        # Should show roster differences
        assert len(out) > 0


class TestDiffNewFileTypes:
    """Tests for diff support of MBS, DDRW, SHPS, TEXT."""

    def _make_pair(self, tmp_path, name, size, change_offset=0):
        """Helper: create two files in subdirs, second differs at offset."""
        da = tmp_path / 'a'
        db = tmp_path / 'b'
        da.mkdir(exist_ok=True)
        db.mkdir(exist_ok=True)
        d1 = bytearray(size)
        d2 = bytearray(size)
        d2[change_offset] = 0xFF
        (da / name).write_bytes(bytes(d1))
        (db / name).write_bytes(bytes(d2))
        return da / name, db / name

    def test_diff_mbs_files(self, tmp_path, capsys):
        """Diff detects changes in MBS sound files."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import MBS_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'MBS', MBS_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'MBS' in out

    def test_diff_ddrw_files(self, tmp_path, capsys):
        """Diff detects changes in DDRW files."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import DDRW_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'DDRW', DDRW_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'DDRW' in out

    def test_diff_shps_files(self, tmp_path, capsys):
        """Diff detects changes in SHPS files."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import SHPS_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'SHPS', SHPS_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'SHPS' in out

    def test_diff_text_files(self, tmp_path, capsys):
        """Diff detects changes in TEXT files."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import TEXT_FILE_SIZE
        p1, p2 = self._make_pair(tmp_path, 'TEXT', TEXT_FILE_SIZE)
        args = argparse.Namespace(
            path1=str(p1), path2=str(p2),
            json=False, summary=False, output=None)
        cmd_diff(args)
        out = capsys.readouterr().out
        assert 'TEXT' in out

    def test_diff_binary_identical(self, tmp_path, capsys):
        """Identical binary files show no byte changes."""
        from ult3edit.constants import DDRW_FILE_SIZE
        da = tmp_path / 'a'
        db = tmp_path / 'b'
        da.mkdir()
        db.mkdir()
        data = bytes(DDRW_FILE_SIZE)
        (da / 'DDRW').write_bytes(data)
        (db / 'DDRW').write_bytes(data)
        fd = diff_binary(str(da / 'DDRW'), str(db / 'DDRW'), 'DDRW')
        # No changed_bytes field if identical
        changed = [f for f in fd.entities[0].fields
                   if f.path == 'changed_bytes']
        assert not changed or changed[0].new == 0

    def test_diff_directories_includes_new_types(self, tmp_path):
        """Directory diff scans for MBS, DDRW, SHPS, TEXT."""
        from ult3edit.diff import cmd_diff
        from ult3edit.constants import (
            DDRW_FILE_SIZE, MBS_FILE_SIZE, SHPS_FILE_SIZE, TEXT_FILE_SIZE)
        d1 = tmp_path / 'game1'
        d2 = tmp_path / 'game2'
        d1.mkdir()
        d2.mkdir()
        for name, size in [('DDRW', DDRW_FILE_SIZE), ('MBS', MBS_FILE_SIZE),
                           ('SHPS', SHPS_FILE_SIZE), ('TEXT', TEXT_FILE_SIZE)]:
            data1 = bytearray(size)
            data2 = bytearray(size)
            data2[0] = 0xAA
            (d1 / name).write_bytes(bytes(data1))
            (d2 / name).write_bytes(bytes(data2))
        args = argparse.Namespace(
            path1=str(d1), path2=str(d2),
            json=True, summary=False, output=str(tmp_path / 'diff.json'))
        cmd_diff(args)
        result = json.loads((tmp_path / 'diff.json').read_text())
        file_types = {f['type'] for f in result['files']}
        assert 'DDRW' in file_types
        assert 'MBS' in file_types
        assert 'SHPS' in file_types
        assert 'TEXT' in file_types


# ============================================================================
# Additional view-only command tests
# ============================================================================


class TestDiffDetectFileType:
    """Test diff.py file type detection."""

    def test_detect_roster(self, tmp_path):
        """Detect ROST file by name and size."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'ROST')
        with open(path, 'wb') as f:
            f.write(bytes(ROSTER_FILE_SIZE))
        assert detect_file_type(path) == 'ROST'

    def test_detect_prty(self, tmp_path):
        """Detect PRTY file."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'PRTY')
        with open(path, 'wb') as f:
            f.write(bytes(PRTY_FILE_SIZE))
        assert detect_file_type(path) == 'PRTY'

    def test_detect_mon_file(self, tmp_path):
        """Detect MON file with letter suffix."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'MONA')
        with open(path, 'wb') as f:
            f.write(bytes(MON_FILE_SIZE))
        assert detect_file_type(path) == 'MONA'

    def test_detect_con_file(self, tmp_path):
        """Detect CON file with letter suffix."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'CONA')
        with open(path, 'wb') as f:
            f.write(bytes(CON_FILE_SIZE))
        assert detect_file_type(path) == 'CONA'

    def test_detect_prodos_hash(self, tmp_path):
        """Detect file with ProDOS #hash suffix."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'ROST#069500')
        with open(path, 'wb') as f:
            f.write(bytes(ROSTER_FILE_SIZE))
        assert detect_file_type(path) == 'ROST'

    def test_unknown_file_returns_none(self, tmp_path):
        """Unrecognized file returns None."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'UNKNOWN')
        with open(path, 'wb') as f:
            f.write(bytes(42))
        assert detect_file_type(path) is None

    def test_nonexistent_file_returns_none(self, tmp_path):
        """Nonexistent file returns None."""
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'NOFILE')
        assert detect_file_type(path) is None

    def test_detect_special_file(self, tmp_path):
        """Detect special location file."""
        from ult3edit.diff import detect_file_type
        from ult3edit.constants import SPECIAL_NAMES
        name = list(SPECIAL_NAMES.keys())[0]
        path = os.path.join(str(tmp_path), name)
        with open(path, 'wb') as f:
            f.write(bytes(SPECIAL_FILE_SIZE))
        assert detect_file_type(path) == name


# =============================================================================
# Patch identify_binary
# =============================================================================


# =============================================================================
# Patch cmd_edit dry-run / actual write
# =============================================================================


# =============================================================================
# Text module error paths
# =============================================================================


class TestDiffAlgorithm:
    """Test diff.py core diff_dicts and helpers."""

    def test_diff_dicts_identical(self):
        """Identical dicts produce no diffs."""
        from ult3edit.diff import diff_dicts
        d = {'a': 1, 'b': 'hello', 'c': [1, 2]}
        assert diff_dicts(d, d) == []

    def test_diff_dicts_changed_field(self):
        """Changed field produces a FieldDiff."""
        from ult3edit.diff import diff_dicts
        result = diff_dicts({'a': 1}, {'a': 2})
        assert len(result) == 1
        assert result[0].path == 'a'
        assert result[0].old == 1
        assert result[0].new == 2

    def test_diff_dicts_added_key(self):
        """New key in second dict is detected."""
        from ult3edit.diff import diff_dicts
        result = diff_dicts({}, {'a': 1})
        assert len(result) == 1
        assert result[0].path == 'a'
        assert result[0].old is None
        assert result[0].new == 1

    def test_diff_dicts_removed_key(self):
        """Missing key in second dict is detected."""
        from ult3edit.diff import diff_dicts
        result = diff_dicts({'a': 1}, {})
        assert len(result) == 1
        assert result[0].old == 1
        assert result[0].new is None

    def test_diff_dicts_nested(self):
        """Nested dict changes produce dotted paths."""
        from ult3edit.diff import diff_dicts
        d1 = {'a': {'b': 1, 'c': 2}}
        d2 = {'a': {'b': 1, 'c': 3}}
        result = diff_dicts(d1, d2)
        assert len(result) == 1
        assert result[0].path == 'a.c'

    def test_diff_dicts_list_change(self):
        """List element change is detected with [index] path."""
        from ult3edit.diff import diff_dicts
        d1 = {'items': [1, 2, 3]}
        d2 = {'items': [1, 9, 3]}
        result = diff_dicts(d1, d2)
        assert len(result) == 1
        assert '[1]' in result[0].path

    def test_diff_dicts_list_length_change(self):
        """Different list lengths produce diffs for extra elements."""
        from ult3edit.diff import diff_dicts
        d1 = {'items': [1, 2]}
        d2 = {'items': [1, 2, 3]}
        result = diff_dicts(d1, d2)
        assert len(result) == 1
        assert result[0].new == 3


class TestDiffTileGrid:
    """Test _diff_tile_grid helper."""

    def test_identical_grids(self):
        """Identical grids produce no tile changes."""
        from ult3edit.diff import FileDiff, _diff_tile_grid
        fd = FileDiff('test', 'test')
        data = bytes(range(16))
        _diff_tile_grid(fd, data, data, 4, 4)
        assert fd.tile_changes == 0
        assert fd.tile_positions == []

    def test_one_changed_tile(self):
        """One changed tile is detected with correct position."""
        from ult3edit.diff import FileDiff, _diff_tile_grid
        fd = FileDiff('test', 'test')
        d1 = bytes(16)
        d2 = bytearray(16)
        d2[5] = 0xFF  # (x=1, y=1) in a 4-wide grid
        _diff_tile_grid(fd, d1, bytes(d2), 4, 4)
        assert fd.tile_changes == 1
        assert fd.tile_positions == [(1, 1)]


class TestDiffRosterExtended:
    """Test diff_roster comparing two ROST files."""

    def test_identical_rosters(self, tmp_path):
        """Identical rosters produce no changes."""
        from ult3edit.diff import diff_roster
        data = bytearray(ROSTER_FILE_SIZE)
        p1 = os.path.join(str(tmp_path), 'ROST1')
        p2 = os.path.join(str(tmp_path), 'ROST2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_roster(p1, p2)
        assert not fd.changed

    def test_changed_character(self, tmp_path):
        """Changed character stat produces field diff."""
        from ult3edit.diff import diff_roster
        data1 = bytearray(ROSTER_FILE_SIZE)
        data2 = bytearray(ROSTER_FILE_SIZE)
        # Set name in both so slot is non-empty
        for i, ch in enumerate('HERO'):
            data1[i] = ord(ch) | 0x80
            data2[i] = ord(ch) | 0x80
        data1[CHAR_STATUS] = ord('G')
        data2[CHAR_STATUS] = ord('G')
        # Change HP in second file
        data2[CHAR_HP_HI] = 0x05
        p1 = os.path.join(str(tmp_path), 'ROST1')
        p2 = os.path.join(str(tmp_path), 'ROST2')
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_roster(p1, p2)
        assert fd.changed

    def test_added_character(self, tmp_path):
        """Empty slot in file1, character in file2 → added_entities."""
        from ult3edit.diff import diff_roster
        data1 = bytearray(ROSTER_FILE_SIZE)
        data2 = bytearray(ROSTER_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            data2[i] = ord(ch) | 0x80
        data2[CHAR_STATUS] = ord('G')
        p1 = os.path.join(str(tmp_path), 'ROST1')
        p2 = os.path.join(str(tmp_path), 'ROST2')
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_roster(p1, p2)
        assert len(fd.added_entities) >= 1


class TestDiffCombat:
    """Test diff_combat comparing two CON files."""

    def test_identical_combat_maps(self, tmp_path):
        """Identical CON files produce no changes."""
        from ult3edit.diff import diff_combat
        data = bytearray(CON_FILE_SIZE)
        p1 = os.path.join(str(tmp_path), 'CONA1')
        p2 = os.path.join(str(tmp_path), 'CONA2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_combat(p1, p2, 'A')
        assert fd.tile_changes == 0

    def test_changed_tile(self, tmp_path):
        """Changed tile in CON file is detected."""
        from ult3edit.diff import diff_combat
        data1 = bytearray(CON_FILE_SIZE)
        data2 = bytearray(CON_FILE_SIZE)
        data2[0] = 0x10  # Change first tile
        p1 = os.path.join(str(tmp_path), 'CONA1')
        p2 = os.path.join(str(tmp_path), 'CONA2')
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_combat(p1, p2, 'A')
        assert fd.tile_changes >= 1


class TestDiffTlk:
    """Test diff_tlk comparing TLK dialog files."""

    def test_identical_tlk(self, tmp_path):
        """Identical TLK files produce no changes."""
        data = encode_record(['HELLO WORLD'])
        p1 = os.path.join(str(tmp_path), 'TLKA1')
        p2 = os.path.join(str(tmp_path), 'TLKA2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_tlk(p1, p2, 'A')
        assert not fd.changed

    def test_changed_record(self, tmp_path):
        """Changed dialog record is detected."""
        d1 = encode_record(['HELLO WORLD'])
        d2 = encode_record(['GOODBYE WORLD'])
        p1 = os.path.join(str(tmp_path), 'TLKA1')
        p2 = os.path.join(str(tmp_path), 'TLKA2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_tlk(p1, p2, 'A')
        assert fd.changed

    def test_added_record(self, tmp_path):
        """Extra record in file2 shows as added."""
        d1 = encode_record(['HELLO'])
        d2 = encode_record(['HELLO']) + encode_record(['EXTRA'])
        p1 = os.path.join(str(tmp_path), 'TLKA1')
        p2 = os.path.join(str(tmp_path), 'TLKA2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_tlk(p1, p2, 'A')
        assert len(fd.added_entities) >= 1


class TestDiffBinary:
    """Test diff_binary for sound/shapes/ddrw files."""

    def test_identical_binary(self, tmp_path):
        """Identical binary files show no changes."""
        data = bytes(100)
        p1 = os.path.join(str(tmp_path), 'FILE1')
        p2 = os.path.join(str(tmp_path), 'FILE2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_binary(p1, p2, 'TEST')
        assert not fd.changed

    def test_changed_binary(self, tmp_path):
        """Changed bytes detected in binary diff."""
        d1 = bytes(100)
        d2 = bytearray(100)
        d2[50] = 0xFF
        p1 = os.path.join(str(tmp_path), 'FILE1')
        p2 = os.path.join(str(tmp_path), 'FILE2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(bytes(d2))
        fd = diff_binary(p1, p2, 'TEST')
        assert fd.changed

    def test_different_size_binary(self, tmp_path):
        """Different-sized binaries show size diff."""
        p1 = os.path.join(str(tmp_path), 'FILE1')
        p2 = os.path.join(str(tmp_path), 'FILE2')
        with open(p1, 'wb') as f:
            f.write(bytes(100))
        with open(p2, 'wb') as f:
            f.write(bytes(200))
        fd = diff_binary(p1, p2, 'TEST')
        assert fd.changed
        sizes = [f for f in fd.entities[0].fields if f.path == 'size']
        assert len(sizes) == 1


class TestDiffMapExtended:
    """Test diff_map for overworld/dungeon map comparison."""

    def test_identical_maps(self, tmp_path):
        """Identical maps show no changes."""
        from ult3edit.diff import diff_map
        data = bytes(MAP_OVERWORLD_SIZE)
        p1 = os.path.join(str(tmp_path), 'MAP1')
        p2 = os.path.join(str(tmp_path), 'MAP2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_map(p1, p2, 'MAPA')
        assert fd.tile_changes == 0

    def test_changed_map_tile(self, tmp_path):
        """Changed tile in overworld map is detected."""
        from ult3edit.diff import diff_map
        d1 = bytes(MAP_OVERWORLD_SIZE)
        d2 = bytearray(MAP_OVERWORLD_SIZE)
        d2[100] = 0xFF
        p1 = os.path.join(str(tmp_path), 'MAP1')
        p2 = os.path.join(str(tmp_path), 'MAP2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(bytes(d2))
        fd = diff_map(p1, p2, 'MAPA')
        assert fd.tile_changes >= 1


# =============================================================================
# Bestiary cmd_dump and cmd_import
# =============================================================================


class TestDiffFileDispatch:
    """Test diff_file auto-detection and dispatch."""

    def test_diff_file_roster(self, tmp_path):
        """diff_file dispatches correctly for ROST files."""
        data = bytearray(ROSTER_FILE_SIZE)
        p1 = os.path.join(str(tmp_path), 'ROST')
        p2 = os.path.join(str(tmp_path), 'ROST2')
        # Use different name for second to test detection from first
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_file(p1, p2)
        assert fd is not None
        assert fd.file_type == 'ROST'

    def test_diff_file_unknown_returns_none(self, tmp_path):
        """diff_file with unrecognizable files returns None."""
        p1 = os.path.join(str(tmp_path), 'UNKNOWN1')
        p2 = os.path.join(str(tmp_path), 'UNKNOWN2')
        with open(p1, 'wb') as f:
            f.write(bytes(42))
        with open(p2, 'wb') as f:
            f.write(bytes(42))
        fd = diff_file(p1, p2)
        assert fd is None


# =============================================================================
# Combat cmd_import
# =============================================================================


class TestDiffSpecialExtended:
    """Test diff_special for BRND/SHRN/FNTN/TIME files."""

    def test_identical_specials(self, tmp_path):
        """Identical special files show no changes."""
        from ult3edit.diff import diff_special
        data = bytes(SPECIAL_FILE_SIZE)
        p1 = os.path.join(str(tmp_path), 'BRND1')
        p2 = os.path.join(str(tmp_path), 'BRND2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = diff_special(p1, p2, 'BRND')
        assert fd.tile_changes == 0

    def test_changed_special_tile(self, tmp_path):
        """Changed tile in special location is detected."""
        from ult3edit.diff import diff_special
        d1 = bytes(SPECIAL_FILE_SIZE)
        d2 = bytearray(SPECIAL_FILE_SIZE)
        d2[5] = 0xFF  # change a tile
        p1 = os.path.join(str(tmp_path), 'BRND1')
        p2 = os.path.join(str(tmp_path), 'BRND2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(bytes(d2))
        fd = diff_special(p1, p2, 'BRND')
        assert fd.tile_changes >= 1


class TestDiffSaveExtended:
    """Test diff_save comparing PRTY/PLRS directories."""

    def test_identical_saves(self, tmp_path):
        """Identical save directories show no changes."""
        from ult3edit.diff import diff_save
        dir1 = os.path.join(str(tmp_path), 'dir1')
        dir2 = os.path.join(str(tmp_path), 'dir2')
        os.makedirs(dir1)
        os.makedirs(dir2)
        prty = bytes(PRTY_FILE_SIZE)
        with open(os.path.join(dir1, 'PRTY'), 'wb') as f:
            f.write(prty)
        with open(os.path.join(dir2, 'PRTY'), 'wb') as f:
            f.write(prty)
        results = diff_save(dir1, dir2)
        assert len(results) >= 1
        assert not results[0].changed

    def test_changed_party(self, tmp_path):
        """Changed PRTY data is detected."""
        from ult3edit.diff import diff_save
        dir1 = os.path.join(str(tmp_path), 'dir1')
        dir2 = os.path.join(str(tmp_path), 'dir2')
        os.makedirs(dir1)
        os.makedirs(dir2)
        prty1 = bytearray(PRTY_FILE_SIZE)
        prty2 = bytearray(PRTY_FILE_SIZE)
        prty2[PRTY_OFF_TRANSPORT] = 0x03  # change transport
        with open(os.path.join(dir1, 'PRTY'), 'wb') as f:
            f.write(prty1)
        with open(os.path.join(dir2, 'PRTY'), 'wb') as f:
            f.write(prty2)
        results = diff_save(dir1, dir2)
        assert any(r.changed for r in results)


class TestDiffEntityProperties:
    """Test EntityDiff and FileDiff property methods."""

    def test_entity_diff_changed_with_fields(self):
        """EntityDiff.changed is True when fields present."""
        from ult3edit.diff import EntityDiff, FieldDiff
        ed = EntityDiff('test', 'label')
        assert not ed.changed
        ed.fields.append(FieldDiff('x', 1, 2))
        assert ed.changed

    def test_file_diff_change_count(self):
        """FileDiff.change_count counts entities with changes."""
        from ult3edit.diff import FileDiff, EntityDiff, FieldDiff
        fd = FileDiff('test', 'test')
        e1 = EntityDiff('a', 'A')
        e1.fields.append(FieldDiff('x', 1, 2))
        e2 = EntityDiff('b', 'B')  # no changes
        fd.entities = [e1, e2]
        assert fd.change_count == 1

    def test_game_diff_changed(self):
        """GameDiff.changed is True when any file has changes."""
        from ult3edit.diff import GameDiff, FileDiff
        gd = GameDiff()
        fd = FileDiff('test', 'test')
        gd.files.append(fd)
        assert not gd.changed
        fd.tile_changes = 1
        assert gd.changed


# =============================================================================
# Map cmd_import (overworld and dungeon)
# =============================================================================


class TestDiffFileGaps:
    """Test diff_file and diff_directories gaps."""

    def test_diff_file_undetectable_type(self, tmp_path):
        """diff_file returns None for unrecognizable files."""
        p1 = os.path.join(str(tmp_path), 'UNKNOWN1')
        p2 = os.path.join(str(tmp_path), 'UNKNOWN2')
        with open(p1, 'wb') as f:
            f.write(b'\x00' * 7)  # No known file matches 7 bytes
        with open(p2, 'wb') as f:
            f.write(b'\x00' * 7)
        result = diff_file(p1, p2)
        assert result is None

    def test_diff_directories_empty_dirs(self, tmp_path):
        """diff_directories on empty dirs returns GameDiff with no changes."""
        from ult3edit.diff import diff_directories
        d1 = os.path.join(str(tmp_path), 'dir1')
        d2 = os.path.join(str(tmp_path), 'dir2')
        os.makedirs(d1)
        os.makedirs(d2)
        gd = diff_directories(d1, d2)
        assert len(gd.files) == 0

    def test_diff_file_binary_type(self, tmp_path):
        """diff_file handles binary file types (TEXT, DDRW, SHPS)."""
        from ult3edit.constants import TEXT_FILE_SIZE
        p1 = os.path.join(str(tmp_path), 'TEXT')
        p2 = os.path.join(str(tmp_path), 'TEXT2')
        data = bytearray(TEXT_FILE_SIZE)
        with open(p1, 'wb') as f:
            f.write(data)
        data[0] = 0xAA
        with open(p2, 'wb') as f:
            f.write(data)
        result = diff_file(p1, p2)
        assert result is not None
        assert result.change_count > 0

    def test_diff_file_prty(self, tmp_path):
        """diff_file handles PRTY files."""
        p1 = os.path.join(str(tmp_path), 'PRTY')
        p2 = os.path.join(str(tmp_path), 'PRTY2')
        data1 = bytearray(PRTY_FILE_SIZE)
        data2 = bytearray(PRTY_FILE_SIZE)
        data2[PRTY_OFF_TRANSPORT] = 0x10
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        result = diff_file(p1, p2)
        assert result is not None


class TestDiffChangedCount:
    """Test FileDiff.change_count property."""

    def test_change_count(self):
        from ult3edit.diff import FileDiff, EntityDiff, FieldDiff
        fd = FileDiff('roster', 'ROST')
        e1 = EntityDiff('character', 'Slot 0')
        e1.fields = [FieldDiff('name', 'foo', 'bar')]
        e2 = EntityDiff('character', 'Slot 1')  # no fields = unchanged
        e3 = EntityDiff('character', 'Slot 2')
        e3.fields = [FieldDiff('hp', '10', '20')]
        fd.entities = [e1, e2, e3]
        assert fd.change_count == 2

    def test_no_changes(self):
        from ult3edit.diff import FileDiff, EntityDiff
        fd = FileDiff('roster', 'ROST')
        e = EntityDiff('character', 'Slot 0')  # no fields = unchanged
        fd.entities = [e]
        assert fd.change_count == 0


# ============================================================================
# Batch 10: Audit-verified bug fixes
# ============================================================================


class TestDiffFileDispatchCombat:
    """Test diff_file dispatches to diff_combat for CON files."""

    def test_diff_file_combat(self, tmp_path):
        p1 = os.path.join(str(tmp_path), 'CONA')
        p2 = os.path.join(str(tmp_path), 'CONA_2')
        data = bytearray(192)
        with open(p1, 'wb') as f:
            f.write(data)
        data[0] = 0x04  # Change one tile
        with open(p2, 'wb') as f:
            f.write(data)
        result = diff_file(p1, p2)
        assert result is not None
        assert result.changed


class TestDiffFileDispatchTlk:
    """Test diff_file dispatches to diff_tlk for TLK files."""

    def test_diff_file_tlk(self, tmp_path):
        # Build a simple TLK file (text record + null terminator)
        rec = bytearray([ord('H') | 0x80, ord('I') | 0x80, 0x00])
        p1 = os.path.join(str(tmp_path), 'TLKA')
        p2 = os.path.join(str(tmp_path), 'TLKA_2')
        with open(p1, 'wb') as f:
            f.write(rec)
        rec2 = bytearray([ord('B') | 0x80, ord('Y') | 0x80, 0x00])
        with open(p2, 'wb') as f:
            f.write(rec2)
        result = diff_file(p1, p2)
        assert result is not None
        assert result.changed


class TestDiffFileDispatchSpecial:
    """Test diff_file dispatches to diff_special for BRND/SHRN files."""

    def test_diff_file_special(self, tmp_path):
        p1 = os.path.join(str(tmp_path), 'BRND')
        p2 = os.path.join(str(tmp_path), 'BRND_2')
        data = bytearray(128)
        with open(p1, 'wb') as f:
            f.write(data)
        data[0] = 0x04
        with open(p2, 'wb') as f:
            f.write(data)
        result = diff_file(p1, p2)
        assert result is not None
        assert result.changed


class TestDiffMapDungeon:
    """Test diff_map with dungeon-sized files (exposes width=64 issue)."""

    def test_diff_dungeon_detects_changes(self, tmp_path):
        from ult3edit.diff import diff_map
        p1 = os.path.join(str(tmp_path), 'MAPM')
        p2 = os.path.join(str(tmp_path), 'MAPM_2')
        data1 = bytearray(2048)
        data2 = bytearray(2048)
        data2[0] = 0x01  # Change first byte
        with open(p1, 'wb') as f:
            f.write(data1)
        with open(p2, 'wb') as f:
            f.write(data2)
        result = diff_map(p1, p2, 'MAPM')
        assert result.tile_changes == 1


class TestDiffBinaryChangedBytes:
    """Test diff_binary changed_bytes FieldDiff uses old=0 sentinel."""

    def test_changed_bytes_old_is_zero(self, tmp_path):
        p1 = os.path.join(str(tmp_path), 'FILE1')
        p2 = os.path.join(str(tmp_path), 'FILE2')
        with open(p1, 'wb') as f:
            f.write(bytearray(100))
        data2 = bytearray(100)
        data2[0] = 0xFF
        data2[1] = 0xFF
        with open(p2, 'wb') as f:
            f.write(data2)
        fd = diff_binary(p1, p2, 'TEST')
        # Find the changed_bytes field
        for entity in fd.entities:
            for field in entity.fields:
                if field.path == 'changed_bytes':
                    assert field.old == 0  # Sentinel value
                    assert field.new == 2  # Two bytes differ


class TestDiffDetectMapNoSizeCheck:
    """Test diff detect_file_type accepts MAP files regardless of size."""

    def test_map_any_size_detected(self, tmp_path):
        from ult3edit.diff import detect_file_type
        # A tiny file named MAPA is still detected as MAP
        path = os.path.join(str(tmp_path), 'MAPA')
        with open(path, 'wb') as f:
            f.write(bytearray(42))  # Wrong size for any real MAP
        assert detect_file_type(path) == 'MAPA'

    def test_tlk_any_size_detected(self, tmp_path):
        from ult3edit.diff import detect_file_type
        path = os.path.join(str(tmp_path), 'TLKA')
        with open(path, 'wb') as f:
            f.write(bytearray(10))
        assert detect_file_type(path) == 'TLKA'


# ============================================================================
# Batch 13 — Audit iteration: diff_map dungeon fix, disk.py, roster validation,
#             save dry-run, tlk/spell edge cases
# ============================================================================


class TestDiffMapDungeonCoordinates:
    """diff_map uses width=16 for dungeon-sized (2048-byte) files."""

    def test_dungeon_tile_coordinates_correct(self, tmp_path):
        """Changed tile at dungeon position (3, 5) reports correct x,y."""
        from ult3edit.diff import diff_map
        d1 = bytearray(MAP_DUNGEON_SIZE)
        d2 = bytearray(MAP_DUNGEON_SIZE)
        # Change tile at level 0, x=3, y=5 → offset = 5*16 + 3 = 83
        d2[83] = 0x10
        p1 = os.path.join(str(tmp_path), 'MAPA1')
        p2 = os.path.join(str(tmp_path), 'MAPA2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_map(p1, p2, 'MAPA')
        assert fd.tile_changes == 1
        assert fd.tile_positions[0] == (3, 5)

    def test_dungeon_change_on_level_1(self, tmp_path):
        """Changed tile on level 1 (offset 256+) uses width=16 for coordinates."""
        from ult3edit.diff import diff_map
        d1 = bytearray(MAP_DUNGEON_SIZE)
        d2 = bytearray(MAP_DUNGEON_SIZE)
        # Level 1, x=10, y=2 → offset = 256 + 2*16 + 10 = 298
        d2[298] = 0x20
        p1 = os.path.join(str(tmp_path), 'MAP1')
        p2 = os.path.join(str(tmp_path), 'MAP2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_map(p1, p2, 'MAP')
        assert fd.tile_changes == 1
        # With width=16: x = 298 % 16 = 10, y = 298 // 16 = 18
        assert fd.tile_positions[0] == (10, 18)

    def test_overworld_still_uses_width_64(self, tmp_path):
        """Overworld (4096-byte) MAP still uses width=64."""
        from ult3edit.diff import diff_map
        d1 = bytearray(MAP_OVERWORLD_SIZE)
        d2 = bytearray(MAP_OVERWORLD_SIZE)
        # x=40, y=3 → offset = 3*64 + 40 = 232
        d2[232] = 0x08
        p1 = os.path.join(str(tmp_path), 'OVR1')
        p2 = os.path.join(str(tmp_path), 'OVR2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_map(p1, p2, 'MAPA')
        assert fd.tile_changes == 1
        assert fd.tile_positions[0] == (40, 3)


class TestDiffMapDungeonLevelFormat:
    """diff.py: dungeon map diffs show Level N (X, Y) format."""

    def test_dungeon_diff_has_level_info(self, tmp_path):
        """Diff two dungeon MAPs, verify level info in text output."""
        from ult3edit.diff import diff_map, format_text, GameDiff
        # Create two dungeon maps (2048 bytes) with one tile different
        d1 = bytearray(2048)
        d2 = bytearray(2048)
        # Put a difference at level 2, position (5, 3)
        # Level 2 starts at offset 2*256, row 3 is at 3*16, col 5
        offset = 2 * 256 + 3 * 16 + 5
        d1[offset] = 0x00
        d2[offset] = 0x01
        f1 = tmp_path / 'MAPM_a'
        f2 = tmp_path / 'MAPM_b'
        f1.write_bytes(bytes(d1))
        f2.write_bytes(bytes(d2))
        fd = diff_map(str(f1), str(f2), 'MAPM')
        assert fd.dungeon_width == 16
        assert fd.tile_changes == 1
        # Check text formatting
        gd = GameDiff()
        gd.files.append(fd)
        text = format_text(gd)
        assert 'Level 2' in text
        assert '(5, 3)' in text

    def test_overworld_diff_no_level(self, tmp_path):
        """Overworld diffs show plain (X, Y) without level info."""
        from ult3edit.diff import diff_map, format_text, GameDiff
        d1 = bytearray(4096)
        d2 = bytearray(4096)
        d1[64 * 10 + 20] = 0x00
        d2[64 * 10 + 20] = 0x04
        f1 = tmp_path / 'MAPA_a'
        f2 = tmp_path / 'MAPA_b'
        f1.write_bytes(bytes(d1))
        f2.write_bytes(bytes(d2))
        fd = diff_map(str(f1), str(f2), 'MAPA')
        assert fd.dungeon_width == 0
        gd = GameDiff()
        gd.files.append(fd)
        text = format_text(gd)
        assert 'Level' not in text
        assert '(20, 10)' in text


# =============================================================================
# Batch 3: Coverage for diff.py uncovered lines
# =============================================================================


class TestDiffListsNestedDicts:
    """Cover line 134: _diff_lists with nested dicts inside list elements."""

    def test_nested_dicts_in_list(self):
        old = [{'hp': 10, 'name': 'A'}, {'hp': 20}]
        new = [{'hp': 99, 'name': 'A'}, {'hp': 20}]
        diffs = _diff_lists(old, new, 'items')
        assert len(diffs) == 1
        assert diffs[0].path == 'items[0].hp'
        assert diffs[0].old == 10
        assert diffs[0].new == 99


class TestDiffBestiaryAddedRemoved:
    """Cover lines 194-201: bestiary added/removed monster detection."""

    def test_added_monster(self, tmp_path):
        """Empty slot in file1, populated in file2 -> added."""
        from ult3edit.diff import diff_bestiary
        d1 = bytearray(MON_FILE_SIZE)  # all empty
        d2 = bytearray(MON_FILE_SIZE)
        # Monster 0: set tile1 and tile2 to make non-empty
        d2[0 * 16 + 0] = 0x48  # tile1
        d2[1 * 16 + 0] = 0x48  # tile2
        d2[4 * 16 + 0] = 50    # hp
        p1 = str(tmp_path / 'MONA1')
        p2 = str(tmp_path / 'MONA2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_bestiary(p1, p2, 'A')
        assert len(fd.added_entities) >= 1
        # The label should include the monster's name from file2
        assert 'Monster #0' in fd.added_entities[0]

    def test_removed_monster(self, tmp_path):
        """Populated slot in file1, empty in file2 -> removed."""
        from ult3edit.diff import diff_bestiary
        d1 = bytearray(MON_FILE_SIZE)
        d2 = bytearray(MON_FILE_SIZE)
        d1[0 * 16 + 0] = 0x48
        d1[1 * 16 + 0] = 0x48
        d1[4 * 16 + 0] = 50
        p1 = str(tmp_path / 'MONA1')
        p2 = str(tmp_path / 'MONA2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_bestiary(p1, p2, 'A')
        assert len(fd.removed_entities) >= 1


class TestDiffPlrs:
    """Cover lines 243-265: _diff_plrs comparing PLRS files."""

    def test_plrs_identical(self, tmp_path):
        data = bytearray(PLRS_FILE_SIZE)
        p1 = str(tmp_path / 'PLRS1')
        p2 = str(tmp_path / 'PLRS2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        fd = _diff_plrs(p1, p2)
        assert not fd.changed

    def test_plrs_added_character(self, tmp_path):
        """Empty slot in file1, populated in file2 -> added."""
        d1 = bytearray(PLRS_FILE_SIZE)
        d2 = bytearray(PLRS_FILE_SIZE)
        # Set name in slot 0 of d2 to make it non-empty
        for i, ch in enumerate('TEST'):
            d2[i] = ord(ch) | 0x80
        d2[CHAR_STATUS] = ord('G')
        p1 = str(tmp_path / 'PLRS1')
        p2 = str(tmp_path / 'PLRS2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = _diff_plrs(p1, p2)
        assert len(fd.added_entities) >= 1
        assert 'Active slot 0' in fd.added_entities[0]

    def test_plrs_removed_character(self, tmp_path):
        """Populated slot in file1, empty in file2 -> removed."""
        d1 = bytearray(PLRS_FILE_SIZE)
        d2 = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            d1[i] = ord(ch) | 0x80
        d1[CHAR_STATUS] = ord('G')
        p1 = str(tmp_path / 'PLRS1')
        p2 = str(tmp_path / 'PLRS2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = _diff_plrs(p1, p2)
        assert len(fd.removed_entities) >= 1

    def test_plrs_changed_character(self, tmp_path):
        """Both slots populated but different -> field diffs."""
        d1 = bytearray(PLRS_FILE_SIZE)
        d2 = bytearray(PLRS_FILE_SIZE)
        for i, ch in enumerate('HERO'):
            d1[i] = ord(ch) | 0x80
            d2[i] = ord(ch) | 0x80
        d1[CHAR_STATUS] = ord('G')
        d2[CHAR_STATUS] = ord('G')
        d1[CHAR_STR] = int_to_bcd(25)
        d2[CHAR_STR] = int_to_bcd(50)
        p1 = str(tmp_path / 'PLRS1')
        p2 = str(tmp_path / 'PLRS2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = _diff_plrs(p1, p2)
        assert fd.changed
        assert any(e.changed for e in fd.entities)


class TestDiffTlkRemoved:
    """Cover line 312: diff_tlk with removed record."""

    def test_removed_record(self, tmp_path):
        d1 = encode_record(['HELLO']) + encode_record(['EXTRA'])
        d2 = encode_record(['HELLO'])
        p1 = str(tmp_path / 'TLKA1')
        p2 = str(tmp_path / 'TLKA2')
        with open(p1, 'wb') as f:
            f.write(d1)
        with open(p2, 'wb') as f:
            f.write(d2)
        fd = diff_tlk(p1, p2, 'A')
        assert len(fd.removed_entities) >= 1


class TestDetectFileTypeSaveSound:
    """Cover lines 370-374: detect_file_type for PLRS, SOSA, SOSM."""

    def test_detect_plrs(self, tmp_path):
        from ult3edit.diff import detect_file_type
        path = str(tmp_path / 'PLRS')
        with open(path, 'wb') as f:
            f.write(bytearray(PLRS_FILE_SIZE))
        assert detect_file_type(path) == 'PLRS'

    def test_detect_sosa(self, tmp_path):
        from ult3edit.diff import detect_file_type
        from ult3edit.constants import SOSA_FILE_SIZE
        path = str(tmp_path / 'SOSA')
        with open(path, 'wb') as f:
            f.write(bytearray(SOSA_FILE_SIZE))
        assert detect_file_type(path) == 'SOSA'

    def test_detect_sosm(self, tmp_path):
        from ult3edit.diff import detect_file_type
        from ult3edit.constants import SOSM_FILE_SIZE
        path = str(tmp_path / 'SOSM')
        with open(path, 'wb') as f:
            f.write(bytearray(SOSM_FILE_SIZE))
        assert detect_file_type(path) == 'SOSM'


class TestDiffFileDispatchExtended:
    """Cover lines 412, 424, 427: diff_file dispatch for MON, PLRS, and fallback."""

    def test_diff_file_mon(self, tmp_path):
        """diff_file dispatches to diff_bestiary for MON files."""
        data = bytearray(MON_FILE_SIZE)
        p1 = str(tmp_path / 'MONA')
        p2 = str(tmp_path / 'MONA2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        result = diff_file(p1, p2)
        assert result is not None
        assert result.file_type == 'MONA'

    def test_diff_file_plrs(self, tmp_path):
        """diff_file dispatches to _diff_plrs for PLRS files."""
        data = bytearray(PLRS_FILE_SIZE)
        p1 = str(tmp_path / 'PLRS')
        p2 = str(tmp_path / 'PLRS2')
        with open(p1, 'wb') as f:
            f.write(data)
        with open(p2, 'wb') as f:
            f.write(data)
        result = diff_file(p1, p2)
        assert result is not None
        assert result.file_type == 'PLRS'

    def test_diff_file_fallback_returns_none(self, tmp_path):
        """diff_file returns None for unrecognizable type (line 427)."""
        # Create a file that matches size but not name pattern
        p1 = str(tmp_path / 'WEIRD')
        p2 = str(tmp_path / 'WEIRD2')
        with open(p1, 'wb') as f:
            f.write(bytearray(7))
        with open(p2, 'wb') as f:
            f.write(bytearray(7))
        result = diff_file(p1, p2)
        assert result is None


class TestDiffDirectoriesExtended:
    """Cover lines 452, 459-460, 464, 485, 492: CON, MAP, save, special, TLK in dir diffs."""

    def test_dir_with_con_files(self, tmp_path):
        from ult3edit.diff import diff_directories
        d1 = tmp_path / 'g1'
        d2 = tmp_path / 'g2'
        d1.mkdir()
        d2.mkdir()
        data1 = bytearray(CON_FILE_SIZE)
        data2 = bytearray(CON_FILE_SIZE)
        data2[0] = 0x04
        (d1 / 'CONA').write_bytes(bytes(data1))
        (d2 / 'CONA').write_bytes(bytes(data2))
        gd = diff_directories(str(d1), str(d2))
        con_files = [f for f in gd.files if f.file_name.startswith('CON')]
        assert len(con_files) == 1
        assert con_files[0].tile_changes >= 1

    def test_dir_with_map_files(self, tmp_path):
        from ult3edit.diff import diff_directories
        d1 = tmp_path / 'g1'
        d2 = tmp_path / 'g2'
        d1.mkdir()
        d2.mkdir()
        data1 = bytearray(MAP_OVERWORLD_SIZE)
        data2 = bytearray(MAP_OVERWORLD_SIZE)
        data2[0] = 0xFF
        (d1 / 'MAPA').write_bytes(bytes(data1))
        (d2 / 'MAPA').write_bytes(bytes(data2))
        gd = diff_directories(str(d1), str(d2))
        map_files = [f for f in gd.files if f.file_name.startswith('MAP')]
        assert len(map_files) == 1
        assert map_files[0].tile_changes >= 1

    def test_dir_with_save_files(self, tmp_path):
        from ult3edit.diff import diff_directories
        d1 = tmp_path / 'g1'
        d2 = tmp_path / 'g2'
        d1.mkdir()
        d2.mkdir()
        data1 = bytearray(PRTY_FILE_SIZE)
        data2 = bytearray(PRTY_FILE_SIZE)
        data2[0] = 0x03
        (d1 / 'PRTY').write_bytes(bytes(data1))
        (d2 / 'PRTY').write_bytes(bytes(data2))
        gd = diff_directories(str(d1), str(d2))
        save_files = [f for f in gd.files if f.file_type == 'PRTY']
        assert len(save_files) >= 1

    def test_dir_with_special_files(self, tmp_path):
        from ult3edit.diff import diff_directories
        d1 = tmp_path / 'g1'
        d2 = tmp_path / 'g2'
        d1.mkdir()
        d2.mkdir()
        data1 = bytearray(SPECIAL_FILE_SIZE)
        data2 = bytearray(SPECIAL_FILE_SIZE)
        data2[0] = 0xFF
        (d1 / 'BRND').write_bytes(bytes(data1))
        (d2 / 'BRND').write_bytes(bytes(data2))
        gd = diff_directories(str(d1), str(d2))
        sp_files = [f for f in gd.files if f.file_name == 'BRND']
        assert len(sp_files) == 1
        assert sp_files[0].tile_changes >= 1

    def test_dir_with_tlk_files(self, tmp_path):
        from ult3edit.diff import diff_directories
        d1 = tmp_path / 'g1'
        d2 = tmp_path / 'g2'
        d1.mkdir()
        d2.mkdir()
        rec1 = encode_record(['HELLO'])
        rec2 = encode_record(['GOODBYE'])
        (d1 / 'TLKA').write_bytes(rec1)
        (d2 / 'TLKA').write_bytes(rec2)
        gd = diff_directories(str(d1), str(d2))
        tlk_files = [f for f in gd.files if f.file_name.startswith('TLK')]
        assert len(tlk_files) == 1
        assert tlk_files[0].changed


class TestFormatTextSkipUnchanged:
    """Cover line 520: format_text skips unchanged entities."""

    def test_unchanged_entity_not_in_output(self):
        gd = GameDiff()
        fd = FileDiff('ROST', 'ROST')
        # One changed entity, one unchanged
        ed1 = EntityDiff('character', 'Slot 0: HERO')
        ed1.fields.append(FieldDiff('hp', 100, 200))
        ed2 = EntityDiff('character', 'Slot 1: MAGE')
        # No fields -> unchanged
        fd.entities.extend([ed1, ed2])
        gd.files.append(fd)
        text = format_text(gd)
        assert 'Slot 0: HERO' in text
        assert 'Slot 1: MAGE' not in text


class TestFormatSummaryRemoved:
    """Cover line 557: format_summary with removed entities."""

    def test_summary_shows_removed(self):
        gd = GameDiff()
        fd = FileDiff('ROST', 'ROST')
        fd.removed_entities.append('Slot 5: THIEF')
        gd.files.append(fd)
        text = format_summary(gd)
        assert '1 removed' in text


class TestToJsonExtended:
    """Cover lines 581, 584, 595-596: to_json with removed, skip-unchanged, tile_changes."""

    def test_json_includes_removed(self):
        gd = GameDiff()
        fd = FileDiff('ROST', 'ROST')
        fd.removed_entities.append('Slot 1')
        gd.files.append(fd)
        result = to_json(gd)
        assert result['files'][0]['removed'] == ['Slot 1']

    def test_json_skips_unchanged_entity(self):
        gd = GameDiff()
        fd = FileDiff('ROST', 'ROST')
        ed = EntityDiff('character', 'Slot 0')
        # No fields -> unchanged -> should be skipped
        fd.entities.append(ed)
        fd.tile_changes = 1  # But file-level is changed due to tiles
        fd.tile_positions = [(0, 0)]
        gd.files.append(fd)
        result = to_json(gd)
        # The entity list should be empty (the unchanged one is skipped)
        assert result['files'][0]['entities'] == []

    def test_json_includes_tile_positions(self):
        gd = GameDiff()
        fd = FileDiff('MAPA', 'MAPA')
        fd.tile_changes = 2
        fd.tile_positions = [(3, 4), (5, 6)]
        gd.files.append(fd)
        result = to_json(gd)
        assert result['files'][0]['tile_changes'] == 2
        assert result['files'][0]['tile_positions'] == [
            {'x': 3, 'y': 4}, {'x': 5, 'y': 6}
        ]


class TestCmdDiffFileReturnsNone:
    """Cover line 621: cmd_diff exits when diff_file returns None."""

    def test_unknown_file_type_exits(self, tmp_path):
        p1 = str(tmp_path / 'UNKNOWN1')
        p2 = str(tmp_path / 'UNKNOWN2')
        with open(p1, 'wb') as f:
            f.write(bytearray(7))
        with open(p2, 'wb') as f:
            f.write(bytearray(7))
        args = argparse.Namespace(
            path1=p1, path2=p2, json=False, summary=False, output=None)
        with pytest.raises(SystemExit):
            cmd_diff(args)


class TestDiffDispatch:
    """Cover line 645: dispatch function."""

    def test_dispatch_calls_cmd_diff(self, tmp_path, capsys):
        data = bytearray(ROSTER_FILE_SIZE)
        d1 = tmp_path / 'a'
        d2 = tmp_path / 'b'
        d1.mkdir()
        d2.mkdir()
        (d1 / 'ROST').write_bytes(bytes(data))
        (d2 / 'ROST').write_bytes(bytes(data))
        args = argparse.Namespace(
            path1=str(d1 / 'ROST'), path2=str(d2 / 'ROST'),
            json=False, summary=False, output=None)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'No differences' in out


class TestDiffMain:
    """Cover lines 650-658: main() standalone entry point."""

    def test_main_with_files(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.diff import main
        data = bytearray(ROSTER_FILE_SIZE)
        d1 = tmp_path / 'a'
        d2 = tmp_path / 'b'
        d1.mkdir()
        d2.mkdir()
        p1 = str(d1 / 'ROST')
        p2 = str(d2 / 'ROST')
        (d1 / 'ROST').write_bytes(bytes(data))
        (d2 / 'ROST').write_bytes(bytes(data))
        monkeypatch.setattr(sys, 'argv', ['ult3-diff', p1, p2])
        main()
        out = capsys.readouterr().out
        assert 'No differences' in out

    def test_main_summary(self, tmp_path, capsys, monkeypatch):
        import sys
        from ult3edit.diff import main
        d1 = bytearray(ROSTER_FILE_SIZE)
        d2 = bytearray(ROSTER_FILE_SIZE)
        d2[CHAR_STR] = int_to_bcd(50)
        da = tmp_path / 'a'
        db = tmp_path / 'b'
        da.mkdir()
        db.mkdir()
        p1 = str(da / 'ROST')
        p2 = str(db / 'ROST')
        (da / 'ROST').write_bytes(bytes(d1))
        (db / 'ROST').write_bytes(bytes(d2))
        monkeypatch.setattr(sys, 'argv', ['ult3-diff', p1, p2, '--summary'])
        main()
        out = capsys.readouterr().out
        assert 'Total' in out

