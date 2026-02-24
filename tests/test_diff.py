"""Tests for diff tool."""

import argparse
import json
import os
import pytest

from ult3edit.diff import (
    FieldDiff, EntityDiff, FileDiff, GameDiff,
    diff_dicts, diff_roster, diff_bestiary, diff_map, diff_special,
    _diff_prty, detect_file_type, diff_directories,
    format_text, format_summary, to_json, cmd_diff,
)
from ult3edit.constants import (
    CHAR_RECORD_SIZE, ROSTER_FILE_SIZE, CHAR_STR, MON_FILE_SIZE, PRTY_FILE_SIZE, SPECIAL_FILE_SIZE,
)
from ult3edit.bcd import int_to_bcd


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
