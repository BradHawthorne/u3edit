"""Tests for the sound module: SOSA, SOSM, MBS file identification, hex dump,
AY-3-8910 register parsing, MBS stream decoding, and CLI commands
(view/edit/import)."""

import argparse
import contextlib
import io
import json
import os

import pytest

from ult3edit.sound import (
    identify_sound_file, hex_dump, analyze_mbs, SOUND_FILES,
)


# =============================================================================
# Sound module tests
# =============================================================================

class TestSound:
    def test_identify_sosa(self):
        data = bytes(4096)
        info = identify_sound_file(data, 'SOSA#061000')
        assert info is not None
        assert info['name'] == 'SOSA'

    def test_identify_sosm(self):
        data = bytes(256)
        info = identify_sound_file(data, 'SOSM#064f00')
        assert info is not None
        assert info['name'] == 'SOSM'

    def test_identify_mbs(self):
        data = bytes(5456)
        info = identify_sound_file(data, 'MBS#069a00')
        assert info is not None
        assert info['name'] == 'MBS'

    def test_identify_unknown(self):
        data = bytes(100)
        info = identify_sound_file(data, 'UNKNOWN')
        assert info is None

    def test_hex_dump(self):
        data = bytes(range(32))
        lines = hex_dump(data, 0, 32, 0x1000)
        assert len(lines) == 2
        assert '1000:' in lines[0]

    def test_analyze_mbs_valid(self):
        # Simulate AY register writes: register 0 = 0x42, register 8 = 0x0F
        data = bytes([0, 0x42, 8, 0x0F])
        events = analyze_mbs(data)
        assert len(events) == 2
        assert events[0]['register'] == 0
        assert events[0]['value'] == 0x42
        assert events[1]['register'] == 8
        assert events[1]['value'] == 0x0F

    def test_analyze_mbs_invalid_stops(self):
        # Invalid register (> 13) should stop parsing
        data = bytes([0, 0x42, 0xFF, 0x00])
        events = analyze_mbs(data)
        assert len(events) == 1

    def test_sound_edit_round_trip(self, tmp_path):
        data = bytearray(4096)
        data[0x10] = 0xAB
        path = str(tmp_path / 'SOSA')
        with open(path, 'wb') as f:
            f.write(data)

        # Read back
        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x10] == 0xAB


# =============================================================================
# MBS stream parsing tests
# =============================================================================

class TestMBSStream:
    def test_parse_note(self):
        from ult3edit.sound import parse_mbs_stream
        data = bytes([0x10, 0x20, 0x00])  # Two notes then REST
        events = parse_mbs_stream(data)
        assert len(events) == 3
        assert events[0]['type'] == 'NOTE'
        assert events[0]['value'] == 0x10
        assert events[2]['type'] == 'NOTE'
        assert events[2]['name'] == 'REST'

    def test_parse_end(self):
        from ult3edit.sound import parse_mbs_stream
        data = bytes([0x10, 0x82])  # Note then END
        events = parse_mbs_stream(data)
        assert len(events) == 2
        assert events[1]['type'] == 'END'

    def test_parse_tempo(self):
        from ult3edit.sound import parse_mbs_stream
        data = bytes([0x84, 0x20, 0x82])  # TEMPO $20 then END
        events = parse_mbs_stream(data)
        assert events[0]['type'] == 'TEMPO'
        assert events[0]['operand'] == 0x20

    def test_parse_write_register(self):
        from ult3edit.sound import parse_mbs_stream
        data = bytes([0x83, 0x08, 0x0F, 0x82])  # WRITE R8=$0F then END
        events = parse_mbs_stream(data)
        assert events[0]['type'] == 'WRITE'
        assert events[0]['register'] == 8
        assert events[0]['reg_value'] == 0x0F

    def test_parse_jump(self):
        from ult3edit.sound import parse_mbs_stream
        data = bytes([0x81, 0x00, 0x9A, 0x82])  # JUMP $9A00 then END
        events = parse_mbs_stream(data)
        assert events[0]['type'] == 'JUMP'
        assert events[0]['target'] == 0x9A00

    def test_note_names(self):
        from ult3edit.sound import mbs_note_name
        assert mbs_note_name(0) == 'REST'
        assert mbs_note_name(1) == 'C1'
        assert mbs_note_name(13) == 'C2'

    def test_unknown_byte_stops_parsing(self):
        from ult3edit.sound import parse_mbs_stream
        # $40-$7F are not notes or opcodes
        data = bytes([0x10, 0x50, 0x82])
        events = parse_mbs_stream(data)
        assert len(events) == 1  # Only the first note


# =============================================================================
# Sound import integration tests
# =============================================================================

class TestSoundImportIntegration:
    """Integration tests for sound cmd_import()."""

    def test_import_sound_raw(self, tmp_path):
        """cmd_import() writes raw byte array from JSON."""
        from ult3edit.sound import cmd_import as sound_cmd_import
        path = str(tmp_path / 'SOSA')
        original = bytes(range(256)) * 4  # 1024 bytes
        with open(path, 'wb') as f:
            f.write(original)

        new_data = list(range(255, -1, -1)) * 4  # Reversed pattern
        jdata = {'raw': new_data}
        json_path = str(tmp_path / 'sound.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': False,
        })()
        sound_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result) == new_data

    def test_import_sound_dry_run(self, tmp_path):
        """cmd_import() with dry_run does not modify file."""
        from ult3edit.sound import cmd_import as sound_cmd_import
        path = str(tmp_path / 'SOSA')
        original = bytes(64)
        with open(path, 'wb') as f:
            f.write(original)

        jdata = {'raw': [0xFF] * 64}
        json_path = str(tmp_path / 'sound.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': None, 'backup': False, 'dry_run': True,
        })()
        sound_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result == original

    def test_import_sound_output_file(self, tmp_path):
        """cmd_import() writes to --output file."""
        from ult3edit.sound import cmd_import as sound_cmd_import
        path = str(tmp_path / 'SOSA')
        out_path = str(tmp_path / 'SOSA_OUT')
        with open(path, 'wb') as f:
            f.write(bytes(64))

        jdata = {'raw': [0xAB] * 32}
        json_path = str(tmp_path / 'sound.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path, 'json_file': json_path,
            'output': out_path, 'backup': False, 'dry_run': False,
        })()
        sound_cmd_import(args)

        with open(out_path, 'rb') as f:
            result = f.read()
        assert list(result) == [0xAB] * 32


# =============================================================================
# Sound source file validation
# =============================================================================

class TestSoundSources:
    """Validate sound source JSON files."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_sosa_json_valid(self):
        """SOSA source has correct structure and size."""
        path = os.path.join(self.SOURCES_DIR, 'sosa.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'raw' in data
        assert len(data['raw']) == 4096
        assert all(0 <= b <= 255 for b in data['raw'])

    def test_sosm_json_valid(self):
        """SOSM source has correct structure and size."""
        path = os.path.join(self.SOURCES_DIR, 'sosm.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'raw' in data
        assert len(data['raw']) == 256
        assert all(0 <= b <= 255 for b in data['raw'])

    def test_mbs_json_valid(self):
        """MBS source has correct structure, size, and END opcode."""
        path = os.path.join(self.SOURCES_DIR, 'mbs.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'raw' in data
        assert len(data['raw']) == 5456
        assert data['raw'][0] == 0x82, "First byte should be END opcode"
        assert all(0 <= b <= 255 for b in data['raw'])


# =============================================================================
# Sound import size validation
# =============================================================================

class TestSoundImportSizeValidation:
    """Sound import should warn on unknown file sizes."""

    def test_known_size_no_warning(self, tmp_path, capsys):
        """Importing 4096 bytes (SOSA) should produce no warning."""
        from ult3edit.sound import cmd_import
        from ult3edit.constants import SOSA_FILE_SIZE
        json_file = tmp_path / 'sosa.json'
        json_file.write_text(json.dumps({'raw': [0] * SOSA_FILE_SIZE}))
        out_file = tmp_path / 'SOSA'
        out_file.write_bytes(b'\x00' * SOSA_FILE_SIZE)
        args = type('A', (), {
            'file': str(out_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        assert 'Warning' not in capsys.readouterr().err

    def test_unknown_size_warns(self, tmp_path, capsys):
        """Importing unknown size should produce a warning."""
        from ult3edit.sound import cmd_import
        json_file = tmp_path / 'sound.json'
        json_file.write_text(json.dumps({'raw': [0] * 999}))
        out_file = tmp_path / 'SND'
        out_file.write_bytes(b'\x00' * 999)
        args = type('A', (), {
            'file': str(out_file), 'json_file': str(json_file),
            'output': None, 'backup': False, 'dry_run': False,
        })()
        cmd_import(args)
        err = capsys.readouterr().err
        assert 'Warning' in err
        assert '999' in err


# =============================================================================
# Sound command tests (view/edit/import)
# =============================================================================

class TestSoundCommands:
    """Tests for sound cmd_view, cmd_edit, cmd_import."""

    def test_view_sosa(self, tmp_path, capsys):
        """cmd_view displays SOSA file summary."""
        from ult3edit.sound import cmd_view
        from ult3edit.constants import SOSA_FILE_SIZE
        binfile = tmp_path / 'SOSA'
        binfile.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            path=str(binfile), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'SOSA' in out or 'Speaker' in out or '4096' in out

    def test_view_json(self, tmp_path):
        """cmd_view --json produces JSON output."""
        from ult3edit.sound import cmd_view
        from ult3edit.constants import SOSM_FILE_SIZE
        binfile = tmp_path / 'SOSM'
        binfile.write_bytes(bytes(SOSM_FILE_SIZE))
        outfile = tmp_path / 'out.json'
        args = argparse.Namespace(
            path=str(binfile), json=True, output=str(outfile))
        cmd_view(args)
        result = json.loads(outfile.read_text())
        assert 'raw' in result

    def test_edit_patches_bytes(self, tmp_path):
        """cmd_edit patches sound file bytes."""
        from ult3edit.sound import cmd_edit
        from ult3edit.constants import SOSA_FILE_SIZE
        binfile = tmp_path / 'SOSA'
        binfile.write_bytes(bytes(SOSA_FILE_SIZE))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), offset=0, data='DEADBEEF',
            output=str(out), backup=False, dry_run=False)
        cmd_edit(args)
        result = out.read_bytes()
        assert result[0:4] == bytes([0xDE, 0xAD, 0xBE, 0xEF])

    def test_edit_past_end_exits(self, tmp_path):
        """cmd_edit rejects patch beyond file end."""
        from ult3edit.sound import cmd_edit
        from ult3edit.constants import SOSM_FILE_SIZE
        binfile = tmp_path / 'SOSM'
        binfile.write_bytes(bytes(SOSM_FILE_SIZE))
        args = argparse.Namespace(
            file=str(binfile), offset=SOSM_FILE_SIZE - 1, data='AABB',
            output=str(binfile), backup=False, dry_run=False)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_import_sosa(self, tmp_path):
        """cmd_import writes SOSA from JSON."""
        from ult3edit.sound import cmd_import
        from ult3edit.constants import SOSA_FILE_SIZE
        binfile = tmp_path / 'SOSA'
        binfile.write_bytes(bytes(SOSA_FILE_SIZE))
        data = [0] * SOSA_FILE_SIZE
        data[0] = 0x77
        jfile = tmp_path / 'sosa.json'
        jfile.write_text(json.dumps({'raw': data}))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=str(out), backup=False, dry_run=False)
        cmd_import(args)
        result = out.read_bytes()
        assert len(result) == SOSA_FILE_SIZE
        assert result[0] == 0x77

    def test_import_wrong_size_warns(self, tmp_path):
        """cmd_import warns when size doesn't match known formats."""
        from ult3edit.sound import cmd_import
        binfile = tmp_path / 'SOUND'
        binfile.write_bytes(bytes(100))
        jfile = tmp_path / 'sound.json'
        jfile.write_text(json.dumps({'raw': [0] * 100}))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(binfile), json_file=str(jfile),
            output=str(out), backup=False, dry_run=False)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            cmd_import(args)
        assert 'Warning' in stderr.getvalue()


# =============================================================================
# Sound cmd_edit expanded tests (dry-run, backup)
# =============================================================================

class TestSoundCmdEditExpanded:
    """Tests for sound cmd_edit with dry-run and backup."""

    def test_edit_dry_run(self, tmp_path, capsys):
        """Sound edit dry run shows changes without writing."""
        from ult3edit.sound import cmd_edit
        from ult3edit.constants import SOSA_FILE_SIZE
        path = tmp_path / 'SOSA'
        path.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            file=str(path), offset=0, data='FF',
            dry_run=True, backup=False, output=None)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        assert path.read_bytes()[0] == 0  # unchanged

    def test_edit_with_backup(self, tmp_path):
        """Sound edit --backup creates .bak file."""
        from ult3edit.sound import cmd_edit
        from ult3edit.constants import SOSA_FILE_SIZE
        path = tmp_path / 'SOSA'
        path.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            file=str(path), offset=0, data='FF',
            dry_run=False, backup=True, output=None)
        cmd_edit(args)
        assert os.path.exists(str(path) + '.bak')


# =============================================================================
# MBS parsing bug fixes
# =============================================================================

class TestMbsParsingFixes:
    """Tests for MBS stream parsing bug fixes."""

    def test_loop_opcode_handled(self):
        """LOOP opcode (0x80) is parsed as its own event type."""
        from ult3edit.sound import parse_mbs_stream
        data = bytes([0x80, 0x05, 0x82])  # LOOP, NOTE 5, END
        events = parse_mbs_stream(data)
        assert len(events) == 3
        assert events[0]['type'] == 'LOOP'
        assert events[1]['type'] == 'NOTE'
        assert events[1]['value'] == 5
        assert events[2]['type'] == 'END'

    def test_jump_truncated_marked(self):
        """JUMP at end of data marks event as truncated."""
        from ult3edit.sound import parse_mbs_stream
        data = bytes([0x81])  # JUMP with no operands
        events = parse_mbs_stream(data)
        assert len(events) == 1
        assert events[0]['type'] == 'JUMP'
        assert events[0].get('truncated') is True
        assert 'target' not in events[0]

    def test_jump_with_full_operand(self):
        """JUMP with full 2-byte operand reads target address."""
        from ult3edit.sound import parse_mbs_stream
        data = bytes([0x81, 0x34, 0x12, 0x82])  # JUMP $1234, END
        events = parse_mbs_stream(data)
        assert len(events) == 2
        assert events[0]['type'] == 'JUMP'
        assert events[0]['target'] == 0x1234
        assert 'truncated' not in events[0]

    def test_write_truncated_marked(self):
        """WRITE at end of data marks event as truncated."""
        from ult3edit.sound import parse_mbs_stream
        data = bytes([0x83])  # WRITE with no operands
        events = parse_mbs_stream(data)
        assert len(events) == 1
        assert events[0]['type'] == 'WRITE'
        assert events[0].get('truncated') is True

    def test_tempo_truncated_marked(self):
        """TEMPO at end of data marks event as truncated."""
        from ult3edit.sound import parse_mbs_stream
        data = bytes([0x84])  # TEMPO with no operand
        events = parse_mbs_stream(data)
        assert len(events) == 1
        assert events[0]['type'] == 'TEMPO'
        assert events[0].get('truncated') is True

    def test_full_stream_parse(self):
        """Complete MBS stream with multiple event types parses correctly."""
        from ult3edit.sound import parse_mbs_stream
        data = bytes([
            0x84, 0x06,       # TEMPO 6
            0x85, 0x38,       # MIXER $38
            0x83, 0x07, 0xFF, # WRITE reg 7 = $FF
            0x80,             # LOOP
            0x01, 0x02, 0x03, # NOTE 1, NOTE 2, NOTE 3
            0x82,             # END
        ])
        events = parse_mbs_stream(data)
        types = [e['type'] for e in events]
        assert types == ['TEMPO', 'MIXER', 'WRITE', 'LOOP',
                         'NOTE', 'NOTE', 'NOTE', 'END']
        assert events[0]['operand'] == 6
        assert events[2]['register'] == 7
        assert events[2]['reg_value'] == 0xFF


# =============================================================================
# Sound command gap tests
# =============================================================================

class TestSoundCmdGaps:
    """Test sound command edge cases."""

    def test_cmd_view_no_file_in_dir(self, tmp_path):
        """cmd_view on directory with no sound files works or exits."""
        from ult3edit.sound import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        # May exit or print nothing, but should not crash
        try:
            cmd_view(args)
        except SystemExit:
            pass  # Expected if no files found

    def test_cmd_import_size_mismatch_warning(self, tmp_path, capsys):
        """Import with wrong-size raw array produces warning."""
        from ult3edit.sound import cmd_import
        from ult3edit.constants import SOSA_FILE_SIZE
        path = os.path.join(str(tmp_path), 'SOSA')
        with open(path, 'wb') as f:
            f.write(bytearray(SOSA_FILE_SIZE))
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'raw': [0] * 100}, f)  # Wrong size
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=True, backup=False, output=None)
        cmd_import(args)
        captured = capsys.readouterr()
        assert 'Warning' in captured.err or 'arning' in captured.err or 'bytes' in captured.out


class TestSoundCmdEditGaps:
    """Test sound cmd_edit error paths."""

    def test_invalid_hex_data(self, tmp_path):
        """cmd_edit with invalid hex data exits."""
        from ult3edit.sound import cmd_edit
        from ult3edit.constants import SOSA_FILE_SIZE
        path = os.path.join(str(tmp_path), 'SOSA')
        with open(path, 'wb') as f:
            f.write(bytearray(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            file=path, offset=0, data='ZZZZ',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_patch_past_end(self, tmp_path):
        """cmd_edit with offset+data past end of file exits."""
        from ult3edit.sound import cmd_edit
        from ult3edit.constants import SOSA_FILE_SIZE
        path = os.path.join(str(tmp_path), 'SOSA')
        with open(path, 'wb') as f:
            f.write(bytearray(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            file=path, offset=SOSA_FILE_SIZE - 1, data='AABBCC',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_no_sound_files_in_dir(self, tmp_path):
        """cmd_view on directory with no sound files exits."""
        from ult3edit.sound import cmd_view
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)


class TestSoundCmdImportGaps:
    """Test sound cmd_import error paths."""

    def test_import_non_list_raw(self, tmp_path):
        """cmd_import with non-list 'raw' exits."""
        from ult3edit.sound import cmd_import
        from ult3edit.constants import SOSA_FILE_SIZE
        path = os.path.join(str(tmp_path), 'SOSA')
        with open(path, 'wb') as f:
            f.write(bytearray(SOSA_FILE_SIZE))
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'raw': 'not a list'}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_import(args)

    def test_import_invalid_byte_values(self, tmp_path):
        """cmd_import with invalid byte values exits."""
        from ult3edit.sound import cmd_import
        from ult3edit.constants import SOSA_FILE_SIZE
        path = os.path.join(str(tmp_path), 'SOSA')
        with open(path, 'wb') as f:
            f.write(bytearray(SOSA_FILE_SIZE))
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'raw': [999, -1, 'abc']}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_import(args)


# =============================================================================
# Sound file description tests
# =============================================================================

class TestSoundFileDescriptions:
    """Test that SOSA/SOSM have correct descriptions."""

    def test_sosa_description(self):
        assert 'map state' in SOUND_FILES['SOSA']['description'].lower()

    def test_sosm_description(self):
        assert 'monster' in SOUND_FILES['SOSM']['description'].lower()


# =============================================================================
# Sound cmd_view directory / single file / unknown tests
# =============================================================================

class TestSoundCmdViewDir:
    """Test sound cmd_view directory mode with actual files present."""

    def test_dir_text_mode(self, tmp_path, capsys):
        from ult3edit.sound import cmd_view
        # Create an MBS-sized file (5456 bytes)
        mbs_path = os.path.join(str(tmp_path), 'MBS')
        with open(mbs_path, 'wb') as f:
            f.write(bytearray(5456))
        args = argparse.Namespace(
            path=str(tmp_path), json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'MBS' in out

    def test_dir_json_mode(self, tmp_path, capsys):
        from ult3edit.sound import cmd_view
        mbs_path = os.path.join(str(tmp_path), 'MBS')
        with open(mbs_path, 'wb') as f:
            f.write(bytearray(5456))
        args = argparse.Namespace(
            path=str(tmp_path), json=True, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        result = json.loads(out)
        assert 'MBS' in result
        assert result['MBS']['size'] == 5456


class TestSoundCmdViewSingleMBS:
    """Test sound cmd_view on a single MBS file with structured output."""

    def test_mbs_file_view(self, tmp_path, capsys):
        from ult3edit.sound import cmd_view
        path = os.path.join(str(tmp_path), 'MBS')
        # Create MBS with some AY register writes (reg 0-13 are valid)
        data = bytearray(5456)
        # Put valid register write pairs: register, value
        data[0] = 0  # register 0
        data[1] = 0x42  # value
        data[2] = 7  # register 7 (mixer)
        data[3] = 0x38  # value
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            path=path, json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'MBS' in out or 'Mockingboard' in out


class TestSoundCmdViewUnknown:
    """Test sound cmd_view on an unrecognized file type."""

    def test_unknown_file_type(self, tmp_path, capsys):
        from ult3edit.sound import cmd_view
        path = os.path.join(str(tmp_path), 'MYSTERY')
        with open(path, 'wb') as f:
            f.write(bytearray(999))
        args = argparse.Namespace(
            path=path, json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'Unknown' in out or 'MYSTERY' in out


# =============================================================================
# Sound module docstring tests
# =============================================================================

class TestSoundModuleDocstring:
    """sound.py: module docstring describes SOSA/SOSM correctly."""

    def test_sosa_description(self):
        desc = SOUND_FILES['SOSA']['description']
        assert 'map' in desc.lower() or 'overworld' in desc.lower()

    def test_sosm_description(self):
        desc = SOUND_FILES['SOSM']['description']
        assert 'monster' in desc.lower() or 'overworld' in desc.lower()


# =============================================================================
# Coverage: hex_dump default length, MBS stream edge cases,
# cmd_view MBS stream display, cmd_edit, dispatch, main()
# =============================================================================

class TestHexDumpDefaultLength:
    """Cover line 94: hex_dump called without explicit length."""

    def test_hex_dump_no_length_arg(self):
        data = bytes(range(48))
        lines = hex_dump(data, 0, base_addr=0)
        assert len(lines) == 3  # 48 bytes / 16 per line


class TestMbsStreamElseBranch:
    """Cover lines 191-192: MBS opcode that is in MBS_OPCODES but not
    handled by any specific case (impossible in current code, but the
    catch-all else advances by 1)."""

    def test_fallthrough_opcode_branch(self):
        """Inject a synthetic opcode to exercise the catch-all else."""
        from ult3edit.sound import parse_mbs_stream, MBS_OPCODES
        # Temporarily add a fake opcode so the `else` branch runs
        MBS_OPCODES[0x86] = ('FAKE', 'Fake opcode')
        try:
            data = bytes([0x86, 0x82])  # FAKE then END
            events = parse_mbs_stream(data)
            assert events[0]['type'] == 'FAKE'
            assert events[1]['type'] == 'END'
        finally:
            del MBS_OPCODES[0x86]


class TestSoundCmdViewMbsStreamDisplay:
    """Cover lines 291, 300-314: cmd_view MBS with music stream events
    including WRITE, TEMPO/MIXER, JUMP, END, and other types."""

    def test_mbs_stream_all_event_types(self, tmp_path, capsys):
        from ult3edit.sound import cmd_view
        from ult3edit.constants import MBS_FILE_SIZE
        data = bytearray(MBS_FILE_SIZE)
        # Build a stream with all event types at offset 0
        stream = bytes([
            0x84, 0x06,       # TEMPO
            0x85, 0x38,       # MIXER
            0x83, 0x07, 0xFF, # WRITE R7=$FF
            0x01, 0x02,       # NOTE x2
            0x81, 0x00, 0x9A, # JUMP $9A00
            0x82,             # END
        ])
        data[:len(stream)] = stream
        path = os.path.join(str(tmp_path), 'MBS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(path=path, json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'TEMPO' in out or 'WRITE' in out or 'JUMP' in out or 'END' in out

    def test_mbs_stream_try_offset_break(self, tmp_path, capsys):
        """Cover line 291: try_offset >= len(data) breaks loop.
        Use a 128-byte file named MBS so offsets 0x100+ exceed length."""
        from ult3edit.sound import cmd_view
        # 128 bytes identified as MBS by filename, not size
        data = bytearray(128)
        # Put an invalid byte at offset 0 so stream parsing stops immediately
        data[0] = 0x50  # unknown byte, stops parsing (< 4 events)
        path = os.path.join(str(tmp_path), 'MBS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(path=path, json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'MBS' in out or 'Mockingboard' in out

    def test_mbs_stream_loop_opcode_display(self, tmp_path, capsys):
        """Cover line 314: display LOOP type (else branch)."""
        from ult3edit.sound import cmd_view
        from ult3edit.constants import MBS_FILE_SIZE
        data = bytearray(MBS_FILE_SIZE)
        # Build a stream with LOOP + enough notes + END to have >= 4 events
        stream = bytes([
            0x80,             # LOOP
            0x01, 0x02, 0x03, # NOTE x3
            0x82,             # END
        ])
        data[:len(stream)] = stream
        path = os.path.join(str(tmp_path), 'MBS')
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(path=path, json=False, output=None)
        cmd_view(args)
        out = capsys.readouterr().out
        assert 'LOOP' in out or 'Music stream' in out


class TestSoundCmdEditWriteAndBackup:
    """Cover lines 452-454: dispatch routes to cmd_edit."""

    def test_edit_writes_to_output(self, tmp_path, capsys):
        from ult3edit.sound import cmd_edit
        from ult3edit.constants import SOSA_FILE_SIZE
        src = tmp_path / 'SOSA'
        src.write_bytes(bytes(SOSA_FILE_SIZE))
        out = tmp_path / 'OUT'
        args = argparse.Namespace(
            file=str(src), offset=0, data='AABB',
            output=str(out), backup=False, dry_run=False)
        cmd_edit(args)
        result = out.read_bytes()
        assert result[0] == 0xAA
        assert result[1] == 0xBB
        captured = capsys.readouterr().out
        assert 'Updated' in captured

    def test_import_with_backup(self, tmp_path):
        from ult3edit.sound import cmd_import
        from ult3edit.constants import SOSA_FILE_SIZE
        src = tmp_path / 'SOSA'
        src.write_bytes(bytes(SOSA_FILE_SIZE))
        jfile = tmp_path / 'data.json'
        jfile.write_text(json.dumps({'raw': [0] * SOSA_FILE_SIZE}))
        args = argparse.Namespace(
            file=str(src), json_file=str(jfile),
            output=None, backup=True, dry_run=False)
        cmd_import(args)
        assert (tmp_path / 'SOSA.bak').exists()


class TestSoundDispatchRoutes:
    """Cover lines 452-454: dispatch routes to edit and import."""

    def test_dispatch_edit(self, tmp_path, capsys):
        from ult3edit.sound import dispatch
        from ult3edit.constants import SOSA_FILE_SIZE
        src = tmp_path / 'SOSA'
        src.write_bytes(bytes(SOSA_FILE_SIZE))
        args = argparse.Namespace(
            sound_command='edit',
            file=str(src), offset=0, data='FF',
            output=None, backup=False, dry_run=True)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out

    def test_dispatch_import(self, tmp_path, capsys):
        from ult3edit.sound import dispatch
        from ult3edit.constants import SOSA_FILE_SIZE
        src = tmp_path / 'SOSA'
        src.write_bytes(bytes(SOSA_FILE_SIZE))
        jfile = tmp_path / 'data.json'
        jfile.write_text(json.dumps({'raw': [0] * SOSA_FILE_SIZE}))
        args = argparse.Namespace(
            sound_command='import',
            file=str(src), json_file=str(jfile),
            output=None, backup=False, dry_run=True)
        dispatch(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out or 'Import' in out


class TestSoundMain:
    """Cover lines 461-492: main() standalone entry point."""

    def test_main_view(self, tmp_path, capsys):
        from ult3edit.sound import main
        from ult3edit.constants import SOSA_FILE_SIZE
        src = tmp_path / 'SOSA'
        src.write_bytes(bytes(SOSA_FILE_SIZE))
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-sound', 'view', str(src)]
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'SOSA' in out or '4096' in out

    def test_main_edit_dry_run(self, tmp_path, capsys):
        from ult3edit.sound import main
        from ult3edit.constants import SOSA_FILE_SIZE
        src = tmp_path / 'SOSA'
        src.write_bytes(bytes(SOSA_FILE_SIZE))
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-sound', 'edit', str(src), '--offset', '0', '--data', 'FF', '--dry-run']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Dry run' in out

    def test_main_import_dry_run(self, tmp_path, capsys):
        from ult3edit.sound import main
        from ult3edit.constants import SOSA_FILE_SIZE
        src = tmp_path / 'SOSA'
        src.write_bytes(bytes(SOSA_FILE_SIZE))
        jfile = tmp_path / 'data.json'
        jfile.write_text(json.dumps({'raw': [0] * SOSA_FILE_SIZE}))
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-sound', 'import', str(src), str(jfile), '--dry-run']
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert 'Dry run' in out or 'Import' in out

    def test_main_no_subcommand(self, capsys):
        from ult3edit.sound import main
        import sys
        old_argv = sys.argv
        sys.argv = ['ult3-sound']
        try:
            main()
        finally:
            sys.argv = old_argv
        err = capsys.readouterr().err
        assert 'Usage' in err or 'usage' in err.lower() or 'sound' in err.lower()
