"""Tests for disk module (diskiigs integration + native ProDOS builder)."""

import argparse
import json
import os
import pytest
from unittest.mock import patch, MagicMock

from ult3edit.disk import (
    find_diskiigs, disk_info, disk_list, DiskContext,
    build_prodos_image, collect_build_files, _parse_hash_filename,
    cmd_build, PRODOS_BLOCK_SIZE, PRODOS_ENTRY_LENGTH,
)


class TestFindDiskiigs:
    def test_env_var(self, tmp_dir):
        exe = os.path.join(tmp_dir, 'diskiigs.exe')
        with open(exe, 'w') as f:
            f.write('fake')
        with patch.dict(os.environ, {'DISKIIGS_PATH': exe}):
            result = find_diskiigs()
            assert result == exe

    def test_path_lookup(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch('shutil.which', return_value='/usr/local/bin/diskiigs'):
                result = find_diskiigs()
                assert result == '/usr/local/bin/diskiigs'

    def test_not_found(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch('shutil.which', return_value=None):
                with patch('os.path.isfile', return_value=False):
                    result = find_diskiigs()
                    assert result is None


class TestDiskInfo:
    def test_parse_output(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Volume: ULTIMA3\nFormat: ProDOS\nBlocks: 280\n"
        with patch('ult3edit.disk._run_diskiigs', return_value=mock_result):
            info = disk_info('game.po')
            assert info['volume'] == 'ULTIMA3'
            assert info['format'] == 'ProDOS'
            assert info['blocks'] == '280'

    def test_error(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "File not found"
        with patch('ult3edit.disk._run_diskiigs', return_value=mock_result):
            info = disk_info('missing.po')
            assert 'error' in info


class TestDiskList:
    def test_parse_entries(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "Name                 Type    Size\n"
            "---                  ----    ----\n"
            "ROST                 BIN     1280\n"
            "MAPA                 BIN     4096\n"
        )
        with patch('ult3edit.disk._run_diskiigs', return_value=mock_result):
            entries = disk_list('game.po')
            assert len(entries) == 2
            assert entries[0]['name'] == 'ROST'
            assert entries[1]['name'] == 'MAPA'

    def test_empty_on_error(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch('ult3edit.disk._run_diskiigs', return_value=mock_result):
            entries = disk_list('bad.po')
            assert entries == []


class TestDiskContext:
    def test_context_manager(self, tmp_dir):
        """DiskContext should raise FileNotFoundError when diskiigs not found."""
        with patch('ult3edit.disk.find_diskiigs', return_value=None):
            with pytest.raises(FileNotFoundError):
                with DiskContext('fake.po') as _ctx:
                    pass

    def test_write_stages_data(self):
        """DiskContext.write() should stage data for writeback."""
        ctx = DiskContext('fake.po')
        ctx._cache = {}
        ctx._modified = {}
        ctx.write('ROST', b'\x00' * 10)
        assert ctx._modified['ROST'] == b'\x00' * 10

    def test_read_modified_returns_staged(self):
        """Reading a file that was written should return staged data."""
        ctx = DiskContext('fake.po')
        ctx._cache = {}
        ctx._modified = {'ROST': b'\xFF' * 5}
        assert ctx.read('ROST') == b'\xFF' * 5


# =============================================================================
# Native ProDOS builder tests
# =============================================================================

class TestParseHashFilename:
    """Test ProDOS hash suffix parsing."""

    def test_standard_format(self):
        name, ft, aux = _parse_hash_filename('ROST#069500')
        assert name == 'ROST'
        assert ft == 0x06
        assert aux == 0x9500

    def test_system_file(self):
        name, ft, aux = _parse_hash_filename('LOADER.SYSTEM#FF2000')
        assert name == 'LOADER.SYSTEM'
        assert ft == 0xFF
        assert aux == 0x2000

    def test_no_hash(self):
        name, ft, aux = _parse_hash_filename('ROST')
        assert name == 'ROST'
        assert ft == 0x06
        assert aux == 0x0000


class TestBuildProdosImage:
    """Test native ProDOS image builder."""

    def test_empty_image(self, tmp_dir):
        """Build image with no files produces valid 800K image."""
        out = os.path.join(tmp_dir, 'test.po')
        result = build_prodos_image(out, [])
        assert os.path.isfile(out)
        assert os.path.getsize(out) == 1600 * 512
        assert result['total_blocks'] == 1600
        assert result['files'] == 0

    def test_seedling_file(self, tmp_dir):
        """Single small file (<=512 bytes) stored as seedling."""
        out = os.path.join(tmp_dir, 'test.po')
        files = [{'name': 'TEST', 'data': b'\xAA' * 100,
                  'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None}]
        result = build_prodos_image(out, files)
        assert result['files'] == 1
        assert result['data_blocks'] >= 1

        # Verify volume header
        with open(out, 'rb') as f:
            f.seek(2 * 512 + 4)  # block 2, skip prev/next pointers
            hdr = f.read(PRODOS_ENTRY_LENGTH)
        stype = hdr[0] >> 4
        nlen = hdr[0] & 0x0F
        assert stype == 0x0F  # volume header
        assert hdr[1:1 + nlen] == b'ULTIMA3'

    def test_sapling_file(self, tmp_dir):
        """File >512 bytes stored as sapling (index + data blocks)."""
        out = os.path.join(tmp_dir, 'test.po')
        data = bytes(range(256)) * 8  # 2048 bytes = 4 blocks
        files = [{'name': 'BIG', 'data': data,
                  'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None}]
        result = build_prodos_image(out, files)
        assert result['data_blocks'] == 5  # 1 index + 4 data

    def test_subdirectory(self, tmp_dir):
        """Files in subdirectory get proper directory structure."""
        out = os.path.join(tmp_dir, 'test.po')
        files = [
            {'name': 'PRODOS', 'data': b'\x00' * 100,
             'file_type': 0xFF, 'aux_type': 0x0000, 'subdir': None},
            {'name': 'ROST', 'data': b'\xBB' * 200,
             'file_type': 0x06, 'aux_type': 0x9500, 'subdir': 'GAME'},
            {'name': 'MAPA', 'data': b'\xCC' * 300,
             'file_type': 0x06, 'aux_type': 0x0000, 'subdir': 'GAME'},
        ]
        result = build_prodos_image(out, files)
        assert result['files'] == 3

    def test_boot_blocks(self, tmp_dir):
        """Boot blocks are copied from provided data."""
        out = os.path.join(tmp_dir, 'test.po')
        boot = b'\xEB' * 512 + b'\xFE' * 512
        build_prodos_image(out, [], boot_blocks=boot)
        with open(out, 'rb') as f:
            data = f.read(1024)
        assert data[:512] == b'\xEB' * 512
        assert data[512:1024] == b'\xFE' * 512

    def test_custom_vol_name(self, tmp_dir):
        """Custom volume name appears in header."""
        out = os.path.join(tmp_dir, 'test.po')
        build_prodos_image(out, [], vol_name='VOIDBORN')
        with open(out, 'rb') as f:
            f.seek(2 * 512 + 4)
            hdr = f.read(PRODOS_ENTRY_LENGTH)
        nlen = hdr[0] & 0x0F
        assert hdr[1:1 + nlen] == b'VOIDBORN'

    def test_bitmap_marks_used_blocks(self, tmp_dir):
        """Volume bitmap correctly marks allocated blocks as used."""
        out = os.path.join(tmp_dir, 'test.po')
        files = [{'name': 'TEST', 'data': b'\x00' * 100,
                  'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None}]
        build_prodos_image(out, files)
        with open(out, 'rb') as f:
            f.seek(6 * 512)  # bitmap block
            bitmap = f.read(512)
        # Block 0 should be marked used (bit 7 of byte 0 should be 0)
        assert bitmap[0] & 0x80 == 0  # block 0 used
        assert bitmap[0] & 0x40 == 0  # block 1 used

    def test_prodos_first_in_root(self, tmp_dir):
        """PRODOS entry appears before other root files."""
        out = os.path.join(tmp_dir, 'test.po')
        files = [
            {'name': 'U3', 'data': b'\x00' * 50,
             'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None},
            {'name': 'PRODOS', 'data': b'\x00' * 100,
             'file_type': 0xFF, 'aux_type': 0x0000, 'subdir': None},
        ]
        build_prodos_image(out, files)
        # Read first file entry in volume directory (slot 1, after header)
        with open(out, 'rb') as f:
            f.seek(2 * 512 + 4 + PRODOS_ENTRY_LENGTH)
            entry = f.read(PRODOS_ENTRY_LENGTH)
        nlen = entry[0] & 0x0F
        assert entry[1:1 + nlen] == b'PRODOS'


class TestCollectBuildFiles:
    """Test file collection from directory."""

    def test_collects_hash_files(self, tmp_dir):
        """Collects files with #hash suffixes."""
        with open(os.path.join(tmp_dir, 'ROST#069500'), 'wb') as f:
            f.write(b'\x00' * 100)
        with open(os.path.join(tmp_dir, 'MAPA#060000'), 'wb') as f:
            f.write(b'\x00' * 200)
        files = collect_build_files(tmp_dir)
        assert len(files) == 2
        names = {f['name'] for f in files}
        assert names == {'ROST', 'MAPA'}

    def test_root_vs_game(self, tmp_dir):
        """PRODOS/LOADER.SYSTEM/U3 go to root, others to GAME."""
        for name in ['PRODOS#FF0000', 'ROST#069500', 'U3#060000']:
            with open(os.path.join(tmp_dir, name), 'wb') as f:
                f.write(b'\x00' * 10)
        files = collect_build_files(tmp_dir)
        root = [f for f in files if f['subdir'] is None]
        game = [f for f in files if f['subdir'] == 'GAME']
        assert len(root) == 2  # PRODOS, U3
        assert len(game) == 1  # ROST

    def test_skips_bak_files(self, tmp_dir):
        """Backup files are skipped."""
        with open(os.path.join(tmp_dir, 'ROST#069500'), 'wb') as f:
            f.write(b'\x00')
        with open(os.path.join(tmp_dir, 'ROST#069500.bak'), 'wb') as f:
            f.write(b'\x00')
        files = collect_build_files(tmp_dir)
        assert len(files) == 1

    def test_skips_no_hash(self, tmp_dir):
        """Files without #hash suffix are skipped."""
        with open(os.path.join(tmp_dir, 'README'), 'wb') as f:
            f.write(b'\x00')
        files = collect_build_files(tmp_dir)
        assert len(files) == 0


class TestBuildRoundtrip:
    """Test build → read-back data integrity."""

    def test_file_data_preserved(self, tmp_dir):
        """File data can be read back from built image."""
        out = os.path.join(tmp_dir, 'test.po')
        test_data = bytes(range(256))
        files = [{'name': 'TEST', 'data': test_data,
                  'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None}]
        build_prodos_image(out, files)

        # Read back: file is at block 7 (first allocated), seedling
        with open(out, 'rb') as f:
            # Read root directory entry to find key block
            f.seek(2 * 512 + 4 + PRODOS_ENTRY_LENGTH)  # first file entry
            entry = f.read(PRODOS_ENTRY_LENGTH)
            key_block = entry[0x11] | (entry[0x12] << 8)
            eof = entry[0x15] | (entry[0x16] << 8) | (entry[0x17] << 16)

            # Read key block data
            f.seek(key_block * 512)
            data = f.read(eof)
        assert data == test_data

    def test_multiple_game_files(self, tmp_dir):
        """Multiple game files in subdirectory are all accessible."""
        out = os.path.join(tmp_dir, 'test.po')
        files = []
        for i in range(5):
            files.append({
                'name': f'FILE{i}',
                'data': bytes([i]) * 100,
                'file_type': 0x06,
                'aux_type': 0x0000,
                'subdir': 'GAME',
            })
        result = build_prodos_image(out, files)
        assert result['files'] == 5

        # Verify GAME directory exists in root
        with open(out, 'rb') as f:
            f.seek(2 * 512 + 4 + PRODOS_ENTRY_LENGTH)
            entry = f.read(PRODOS_ENTRY_LENGTH)
        stype = entry[0] >> 4
        nlen = entry[0] & 0x0F
        assert stype == 0x0D  # directory file
        assert entry[1:1 + nlen] == b'GAME'


class TestBuildCLI:
    """Test build subcommand argument parsing."""

    def test_build_parse(self):
        """Parse 'disk build output.po input_dir'."""
        from ult3edit.disk import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['disk', 'build', 'out.po', '/tmp/game'])
        assert args.disk_command == 'build'
        assert args.output == 'out.po'
        assert args.input_dir == '/tmp/game'

    def test_build_options(self):
        """Parse build with --vol-name and --boot-from."""
        from ult3edit.disk import register_parser
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='tool')
        register_parser(subs)
        args = parser.parse_args(['disk', 'build', 'v.po', '/dir',
                                  '--vol-name', 'VOIDBORN',
                                  '--boot-from', 'vanilla.po'])
        assert args.vol_name == 'VOIDBORN'
        assert args.boot_from == 'vanilla.po'


# ── Migrated from test_new_features.py ──

class TestDiskAudit:
    def test_audit_output_format(self):
        """Verify the audit function imports cleanly."""
        from ult3edit.disk import cmd_audit
        # Just verify it's callable
        assert callable(cmd_audit)


# =============================================================================
# CLI parity tests — main() matches register_parser()
# =============================================================================



class TestDiskContextParseHash:
    """Test DiskContext._parse_hash_suffix."""

    def test_with_hash_suffix(self):
        from ult3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('ROST#069500')
        assert name == 'ROST'
        assert ft == 0x06
        assert at == 0x9500

    def test_without_hash(self):
        from ult3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('ROST')
        assert name == 'ROST'
        assert ft == 0x06
        assert at == 0x0000

    def test_short_suffix(self):
        from ult3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('FOO#AB')
        assert name == 'FOO'
        assert ft == 0x06  # fallback
        assert at == 0x0000

    def test_all_zeros(self):
        from ult3edit.disk import DiskContext
        name, ft, at = DiskContext._parse_hash_suffix('MAP#000000')
        assert name == 'MAP'
        assert ft == 0x00
        assert at == 0x0000


class TestDiskContextLeakGuard:
    """Tests for DiskContext temp directory cleanup on __enter__ failure."""

    def test_enter_failure_cleans_tmpdir(self, tmp_path):
        """DiskContext cleans up temp dir when disk extraction raises."""
        from ult3edit.disk import DiskContext
        # Use a non-existent image path and non-existent tool
        fake_image = str(tmp_path / 'nonexistent.po')
        ctx = DiskContext(fake_image, diskiigs_path='/nonexistent/tool')
        with pytest.raises(Exception):
            ctx.__enter__()
        # After failure, _tmpdir should be cleaned up (set to None)
        assert ctx._tmpdir is None


class TestDiskContextReadWrite:
    """Test DiskContext cache, modified, and _parse_hash_suffix edge cases."""

    def test_parse_hash_suffix_valid(self):
        from ult3edit.disk import DiskContext
        base, ft, at = DiskContext._parse_hash_suffix('ROST#069500')
        assert base == 'ROST'
        assert ft == 0x06
        assert at == 0x9500

    def test_parse_hash_suffix_no_hash(self):
        from ult3edit.disk import DiskContext
        base, ft, at = DiskContext._parse_hash_suffix('ROST')
        assert base == 'ROST'
        assert ft == 0x06
        assert at == 0x0000

    def test_parse_hash_suffix_short(self):
        from ult3edit.disk import DiskContext
        base, ft, at = DiskContext._parse_hash_suffix('FOO#06')
        assert base == 'FOO'
        assert ft == 0x06
        assert at == 0x0000

    def test_parse_hash_suffix_invalid_hex(self):
        """Non-hex characters in suffix with len >= 6 fall back to defaults."""
        from ult3edit.disk import DiskContext
        base, ft, at = DiskContext._parse_hash_suffix('FOO#GGGG00')
        assert base == 'FOO'
        assert ft == 0x06
        assert at == 0x0000

    def test_write_stages_data(self):
        """DiskContext.write() stages data in _modified dict."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx.write('ROST', b'\x00' * 10)
        assert 'ROST' in ctx._modified
        assert ctx._modified['ROST'] == b'\x00' * 10

    def test_read_returns_modified_data(self):
        """read() returns staged modified data over cache."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx._cache['ROST'] = b'\x01' * 10
        ctx.write('ROST', b'\x02' * 10)
        assert ctx.read('ROST') == b'\x02' * 10

    def test_read_returns_cached_data(self):
        """read() returns cached data when not modified."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx._cache['ROST'] = b'\x03' * 10
        assert ctx.read('ROST') == b'\x03' * 10

    def test_read_returns_none_no_tmpdir(self):
        """read() returns None when _tmpdir is None and no cache."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        assert ctx.read('MISSING') is None

    def test_read_from_tmpdir(self, tmp_path):
        """read() scans _tmpdir files and populates cache + file_types."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx._tmpdir = str(tmp_path)
        # Create a file with hash suffix in tmpdir
        rost_path = os.path.join(str(tmp_path), 'ROST#069500')
        with open(rost_path, 'wb') as f:
            f.write(b'\xAB' * 20)
        result = ctx.read('ROST')
        assert result == b'\xAB' * 20
        assert 'ROST' in ctx._cache
        assert ctx._file_types['ROST'] == (0x06, 0x9500)

    def test_read_case_insensitive(self, tmp_path):
        """read() matches filenames case-insensitively."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx._tmpdir = str(tmp_path)
        fpath = os.path.join(str(tmp_path), 'rost#060000')
        with open(fpath, 'wb') as f:
            f.write(b'\xCD' * 5)
        result = ctx.read('ROST')
        assert result == b'\xCD' * 5


class TestDiskContextExit:
    """Test DiskContext.__exit__ writeback and cleanup behavior."""

    def test_exit_cleans_tmpdir(self, tmp_path):
        """__exit__ removes the tmpdir."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        tmpdir = os.path.join(str(tmp_path), 'ult3edit_test')
        os.makedirs(tmpdir)
        ctx._tmpdir = tmpdir
        ctx.__exit__(None, None, None)
        assert not os.path.exists(tmpdir)

    def test_exit_returns_false(self):
        """__exit__ returns False (does not suppress exceptions)."""
        from ult3edit.disk import DiskContext
        ctx = DiskContext('fake.po')
        ctx._tmpdir = None
        result = ctx.__exit__(None, None, None)
        assert result is False


class TestDiskAuditLogic:
    """Test cmd_audit logic with mocked disk_info/disk_list."""

    def test_audit_text_output(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'blocks': '280',
            'volume': 'TEST',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [
            {'name': 'ROST', 'type': 'BIN', 'size': '1280'},
            {'name': 'MAPA', 'type': 'BIN', 'size': '4096'},
        ])
        args = argparse.Namespace(
            image='test.po', json=False, output=None, detail=False)
        disk.cmd_audit(args)
        out = capsys.readouterr().out
        assert 'Disk Audit' in out
        assert '280' in out  # total blocks shown

    def test_audit_json_output(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'blocks': '280',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [
            {'name': 'ROST', 'type': 'BIN', 'size': '1280'},
        ])
        args = argparse.Namespace(
            image='test.po', json=True, output=None, detail=False)
        disk.cmd_audit(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data['total_blocks'] == 280
        assert data['used_blocks'] == 3  # ceil(1280/512) = 3
        assert data['free_blocks'] == 277
        assert 'capacity_estimates' in data

    def test_audit_detail_flag(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'blocks': '100',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [
            {'name': 'TEST', 'type': 'BIN', 'size': '256'},
        ])
        args = argparse.Namespace(
            image='test.po', json=False, output=None, detail=True)
        disk.cmd_audit(args)
        out = capsys.readouterr().out
        assert 'TEST' in out
        assert 'BIN' in out

    def test_audit_error(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'error': 'bad image',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [])
        args = argparse.Namespace(
            image='test.po', json=False, output=None, detail=False)
        with pytest.raises(SystemExit):
            disk.cmd_audit(args)


class TestDiskCmdHandlers:
    """Test disk CLI handler functions."""

    def test_cmd_info_error(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'error': 'not found',
        })
        args = argparse.Namespace(image='bad.po', json=False, output=None)
        with pytest.raises(SystemExit):
            disk.cmd_info(args)

    def test_cmd_info_text(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'volume': 'GAME',
            'format': 'ProDOS',
        })
        args = argparse.Namespace(image='game.po', json=False, output=None)
        disk.cmd_info(args)
        out = capsys.readouterr().out
        assert 'GAME' in out
        assert 'ProDOS' in out

    def test_cmd_info_json(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'volume': 'GAME',
        })
        args = argparse.Namespace(image='game.po', json=True, output=None)
        disk.cmd_info(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data['volume'] == 'GAME'

    def test_cmd_list_empty(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_list', lambda image, path, **kw: [])
        args = argparse.Namespace(image='empty.po', path='/', json=False, output=None)
        with pytest.raises(SystemExit):
            disk.cmd_list(args)

    def test_cmd_list_text(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_list', lambda image, path, **kw: [
            {'name': 'ROST', 'type': 'BIN', 'size': '1280'},
        ])
        args = argparse.Namespace(image='game.po', path='/', json=False, output=None)
        disk.cmd_list(args)
        out = capsys.readouterr().out
        assert 'ROST' in out
        assert '1 files' in out

    def test_cmd_list_json(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_list', lambda image, path, **kw: [
            {'name': 'ROST', 'type': 'BIN', 'size': '1280'},
        ])
        args = argparse.Namespace(image='game.po', path='/', json=True, output=None)
        disk.cmd_list(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert len(data) == 1
        assert data[0]['name'] == 'ROST'

    def test_cmd_extract_success(self, monkeypatch, capsys, tmp_path):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_extract_all', lambda *a, **kw: True)
        args = argparse.Namespace(image='game.po', output=str(tmp_path))
        disk.cmd_extract(args)
        out = capsys.readouterr().out
        assert 'Extracted' in out

    def test_cmd_extract_failure(self, monkeypatch, capsys):
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_extract_all', lambda *a, **kw: False)
        args = argparse.Namespace(image='bad.po', output=None)
        with pytest.raises(SystemExit):
            disk.cmd_extract(args)


class TestDiskDispatchFallback:
    """disk dispatch with unknown command prints usage."""

    def test_dispatch_unknown(self, capsys):
        from ult3edit.disk import dispatch
        args = argparse.Namespace(disk_command='unknown')
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err


# =============================================================================
# Batch 14: Grade-A upgrade tests
# =============================================================================


# =============================================================================
# Disk native builder tests
# =============================================================================


class TestDiskBuildNative:
    """Tests for the native Python ProDOS disk image builder (no diskiigs)."""

    def test_collect_build_files_finds_hash_suffixes(self, tmp_dir):
        """collect_build_files() finds files with #hash suffixes."""
        for name in ['ROST#069500', 'MONA#069900', 'TLKA#060000']:
            with open(os.path.join(tmp_dir, name), 'wb') as f:
                f.write(b'\x00' * 64)
        # Also create a plain file without hash — should be skipped
        with open(os.path.join(tmp_dir, 'README'), 'wb') as f:
            f.write(b'text')
        files = collect_build_files(tmp_dir)
        assert len(files) == 3
        names = {f['name'] for f in files}
        assert 'ROST' in names
        assert 'MONA' in names
        assert 'TLKA' in names
        # Verify file types are parsed
        rost = [f for f in files if f['name'] == 'ROST'][0]
        assert rost['file_type'] == 0x06
        assert rost['aux_type'] == 0x9500

    def test_build_prodos_image_140k(self, tmp_dir):
        """build_prodos_image() creates a valid 140K (280-block) disk image."""
        out = os.path.join(tmp_dir, 'test.po')
        files = [{'name': 'TEST', 'data': b'\xAA' * 100,
                  'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None}]
        result = build_prodos_image(out, files, total_blocks=280)
        assert os.path.isfile(out)
        assert os.path.getsize(out) == 280 * PRODOS_BLOCK_SIZE  # 143360 bytes
        assert result['total_blocks'] == 280
        assert result['total_bytes'] == 143360
        assert result['files'] == 1

    def test_cmd_build_creates_output(self, tmp_dir):
        """cmd_build with valid input directory creates output file."""
        # Create input files with #hash suffixes
        input_dir = os.path.join(tmp_dir, 'input')
        os.makedirs(input_dir)
        with open(os.path.join(input_dir, 'ROST#069500'), 'wb') as f:
            f.write(b'\x00' * 100)
        with open(os.path.join(input_dir, 'MONA#069900'), 'wb') as f:
            f.write(b'\x00' * 256)
        output_path = os.path.join(tmp_dir, 'game.po')
        args = argparse.Namespace(
            output=output_path, input_dir=input_dir,
            vol_name='ULTIMA3', boot_from=None)
        cmd_build(args)
        assert os.path.isfile(output_path)
        assert os.path.getsize(output_path) > 0

    def test_built_image_has_volume_header(self, tmp_dir):
        """Built image starts with expected ProDOS volume directory signature."""
        out = os.path.join(tmp_dir, 'test.po')
        files = [{'name': 'DATA', 'data': b'\x55' * 50,
                  'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None}]
        build_prodos_image(out, files, vol_name='ULTIMA3')
        with open(out, 'rb') as f:
            # Volume directory is at block 2
            f.seek(2 * PRODOS_BLOCK_SIZE + 4)  # skip prev/next pointers
            hdr = f.read(PRODOS_ENTRY_LENGTH)
        # Storage type should be 0x0F (volume header)
        storage_type = hdr[0] >> 4
        assert storage_type == 0x0F
        # Volume name should be present
        name_len = hdr[0] & 0x0F
        assert hdr[1:1 + name_len] == b'ULTIMA3'


# =============================================================================
# Coverage-targeted tests for uncovered lines in disk.py
# =============================================================================


class TestFindDiskiigsCommonPaths:
    """Cover line 44: find_diskiigs() returns candidate from common build paths."""

    def test_common_build_path_found(self, tmp_path):
        """When env and PATH fail, find_diskiigs checks common build paths."""
        # We mock os.path.isfile to return True for a specific candidate
        real_isfile = os.path.isfile

        def fake_isfile(path):
            if 'rosetta_v2' in str(path) and 'diskiigs' in str(path):
                return True
            return real_isfile(path)

        with patch.dict(os.environ, {}, clear=True):
            with patch('shutil.which', return_value=None):
                with patch('os.path.isfile', side_effect=fake_isfile):
                    result = find_diskiigs()
                    assert result is not None
                    assert 'diskiigs' in result


class TestDiskReadWriteExtract:
    """Cover lines 96-126, 136: disk_read, disk_write, disk_extract_all."""

    def test_disk_read_success(self, tmp_path):
        """disk_read extracts a file via diskiigs and returns its bytes."""
        test_data = b'\xAB\xCD\xEF' * 10

        def fake_run_diskiigs(args, diskiigs_path=None):
            # Simulate extract: write a file into the -o directory
            if args[0] == 'extract':
                output_dir = args[4]  # args = ['extract', image, path, '-o', dir]
                fpath = os.path.join(output_dir, 'TEST#060000')
                with open(fpath, 'wb') as f:
                    f.write(test_data)
            result = MagicMock()
            result.returncode = 0
            return result

        from ult3edit import disk
        with patch.object(disk, '_run_diskiigs', side_effect=fake_run_diskiigs):
            data = disk.disk_read('game.po', '/GAME/TEST')
            assert data == test_data

    def test_disk_read_failure_returns_none(self):
        """disk_read returns None on diskiigs error."""
        from ult3edit import disk
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch.object(disk, '_run_diskiigs', return_value=mock_result):
            result = disk.disk_read('bad.po', '/GAME/MISSING')
            assert result is None

    def test_disk_read_no_files_extracted(self):
        """disk_read returns None when extract succeeds but no files found."""
        from ult3edit import disk
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch.object(disk, '_run_diskiigs', return_value=mock_result):
            result = disk.disk_read('game.po', '/GAME/EMPTY')
            assert result is None

    def test_disk_write_success(self):
        """disk_write returns True on successful add."""
        from ult3edit import disk
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch.object(disk, '_run_diskiigs', return_value=mock_result):
            ok = disk.disk_write('game.po', '/GAME/ROST', b'\x00' * 10,
                                 file_type=0x06, aux_type=0x9500)
            assert ok is True

    def test_disk_write_failure(self):
        """disk_write returns False on diskiigs error."""
        from ult3edit import disk
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch.object(disk, '_run_diskiigs', return_value=mock_result):
            ok = disk.disk_write('game.po', '/GAME/ROST', b'\x00' * 10)
            assert ok is False

    def test_disk_extract_all_success(self, tmp_path):
        """disk_extract_all returns True on success."""
        from ult3edit import disk
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch.object(disk, '_run_diskiigs', return_value=mock_result):
            ok = disk.disk_extract_all('game.po', str(tmp_path))
            assert ok is True

    def test_disk_extract_all_failure(self, tmp_path):
        """disk_extract_all returns False on failure."""
        from ult3edit import disk
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch.object(disk, '_run_diskiigs', return_value=mock_result):
            ok = disk.disk_extract_all('game.po', str(tmp_path))
            assert ok is False


class TestDiskContextEnterSuccess:
    """Cover line 167: DiskContext.__enter__ returns self on success."""

    def test_enter_returns_self(self, tmp_path):
        """__enter__ returns self when extraction succeeds."""
        from ult3edit import disk
        with patch.object(disk, 'disk_extract_all', return_value=True):
            ctx = disk.DiskContext('game.po')
            result = ctx.__enter__()
            assert result is ctx
            # Clean up
            ctx.__exit__(None, None, None)


class TestDiskContextExitWriteback:
    """Cover lines 172-179: __exit__ writes back modified files."""

    def test_exit_writes_back_modified_files(self, tmp_path):
        """__exit__ calls disk_write for each modified file."""
        from ult3edit import disk
        ctx = disk.DiskContext('game.po')
        ctx._tmpdir = str(tmp_path)
        ctx._modified = {'ROST': b'\xAA' * 10, 'MONA': b'\xBB' * 20}
        ctx._file_types = {'ROST': (0x06, 0x9500), 'MONA': (0x06, 0x9900)}

        written = []
        with patch.object(disk, 'disk_write',
                          side_effect=lambda *a, **kw: written.append(a)):
            ctx.__exit__(None, None, None)

        assert len(written) == 2
        names = {w[1] for w in written}
        assert names == {'ROST', 'MONA'}

    def test_exit_handles_write_failure(self, tmp_path, capsys):
        """__exit__ prints warning when disk_write fails."""
        from ult3edit import disk
        ctx = disk.DiskContext('game.po')
        ctx._tmpdir = str(tmp_path)
        ctx._modified = {'ROST': b'\xAA' * 10}
        ctx._file_types = {'ROST': (0x06, 0x9500)}

        with patch.object(disk, 'disk_write',
                          side_effect=RuntimeError('write failed')):
            ctx.__exit__(None, None, None)

        err = capsys.readouterr().err
        assert 'Warning' in err
        assert 'ROST' in err

    def test_exit_uses_default_file_type(self, tmp_path):
        """__exit__ uses default (0x06, 0x0000) when file type not cached."""
        from ult3edit import disk
        ctx = disk.DiskContext('game.po')
        ctx._tmpdir = str(tmp_path)
        ctx._modified = {'NEWFILE': b'\x00' * 5}
        ctx._file_types = {}  # no entry for NEWFILE

        calls = []
        with patch.object(disk, 'disk_write',
                          side_effect=lambda *a, **kw: calls.append((a, kw))):
            ctx.__exit__(None, None, None)

        assert len(calls) == 1
        # Check file_type and aux_type kwargs
        assert calls[0][1]['file_type'] == 0x06
        assert calls[0][1]['aux_type'] == 0x0000


class TestProdosBuilderDiskFull:
    """Cover line 286: alloc_block raises RuntimeError when disk full."""

    def test_disk_full_error(self, tmp_dir):
        """Building with too many files for disk size raises RuntimeError."""
        out = os.path.join(tmp_dir, 'tiny.po')
        # Use a very small disk (8 blocks: 0-1 boot, 2-5 vol dir, 6 bitmap, 7 only data)
        # One seedling file uses 1 block. Two files need 2 blocks but only 1 available.
        big_data = b'\x00' * 512  # 1 block each
        files = [
            {'name': f'F{i}', 'data': big_data,
             'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None}
            for i in range(10)  # Need 10 blocks, but only ~1 free
        ]
        with pytest.raises(RuntimeError, match='Disk full'):
            build_prodos_image(out, files, total_blocks=10)


class TestProdosBuilderEmptyFile:
    """Cover lines 299-300: write_file with empty data allocates 1 block."""

    def test_empty_file_seedling(self, tmp_dir):
        """Empty file is stored as seedling with 1 allocated block."""
        out = os.path.join(tmp_dir, 'test.po')
        files = [{'name': 'EMPTY', 'data': b'',
                  'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None}]
        result = build_prodos_image(out, files)
        assert result['data_blocks'] == 1  # 1 block allocated for empty file

        # Verify the file entry has storage_type=1 (seedling) and EOF=0
        with open(out, 'rb') as f:
            f.seek(2 * 512 + 4 + PRODOS_ENTRY_LENGTH)
            entry = f.read(PRODOS_ENTRY_LENGTH)
        stype = entry[0] >> 4
        assert stype == 1  # seedling
        eof = entry[0x15] | (entry[0x16] << 8) | (entry[0x17] << 16)
        assert eof == 0


class TestProdosBuilderSaplingPadding:
    """Cover line 316: sapling last chunk padded when < 512 bytes."""

    def test_sapling_partial_last_block(self, tmp_dir):
        """Sapling file with non-block-aligned size pads last chunk."""
        out = os.path.join(tmp_dir, 'test.po')
        # 513 bytes = 2 data blocks (second block has 1 byte + 511 padding)
        data = b'\xAA' * 513
        files = [{'name': 'SAP', 'data': data,
                  'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None}]
        result = build_prodos_image(out, files)
        assert result['data_blocks'] == 3  # 1 index + 2 data


class TestProdosBuilderTreeFile:
    """Cover lines 327-356: tree file storage for files > 128KB."""

    def test_tree_file(self, tmp_dir):
        """File >128KB stored as tree (master index + sub-indexes + data)."""
        out = os.path.join(tmp_dir, 'tree.po')
        # 257 blocks = 131584 bytes (> 256 blocks, triggers tree)
        data = b'\xBB' * (257 * 512)
        files = [{'name': 'HUGE', 'data': data,
                  'file_type': 0x06, 'aux_type': 0x0000, 'subdir': None}]
        # Need enough blocks: 7 + 1 master + 2 sub-index + 257 data = 267
        result = build_prodos_image(out, files, total_blocks=1600)
        # 1 master + 2 sub-index + 257 data = 260 data blocks
        assert result['data_blocks'] == 260

        # Verify the entry has storage_type=3 (tree)
        with open(out, 'rb') as f:
            f.seek(2 * 512 + 4 + PRODOS_ENTRY_LENGTH)
            entry = f.read(PRODOS_ENTRY_LENGTH)
        stype = entry[0] >> 4
        assert stype == 3  # tree
        eof = entry[0x15] | (entry[0x16] << 8) | (entry[0x17] << 16)
        assert eof == 257 * 512


class TestProdosBuilderLargeSubdir:
    """Cover lines 396 and 441: subdirectory with >12 files needs multiple blocks."""

    def test_subdir_multiple_blocks(self, tmp_dir):
        """Subdirectory with 14 files needs 2 directory blocks."""
        out = os.path.join(tmp_dir, 'test.po')
        files = []
        for i in range(14):
            files.append({
                'name': f'F{i:02d}',
                'data': b'\x00' * 10,
                'file_type': 0x06,
                'aux_type': 0x0000,
                'subdir': 'GAME',
            })
        result = build_prodos_image(out, files, total_blocks=1600)
        assert result['files'] == 14

        # Verify GAME directory entry exists in root
        with open(out, 'rb') as f:
            f.seek(2 * 512 + 4 + PRODOS_ENTRY_LENGTH)
            entry = f.read(PRODOS_ENTRY_LENGTH)
        stype = entry[0] >> 4
        nlen = entry[0] & 0x0F
        assert stype == 0x0D  # directory
        assert entry[1:1 + nlen] == b'GAME'


class TestParseHashFilenameValueError:
    """Cover lines 603-605: _parse_hash_filename ValueError on bad hex."""

    def test_invalid_hex_suffix(self):
        """Non-hex chars in suffix with len>=6 fall back to defaults."""
        name, ft, aux = _parse_hash_filename('FOO#ZZZZZZ')
        assert name == 'FOO'
        assert ft == 0x06
        assert aux == 0x0000

    def test_short_hash_suffix(self):
        """Short hash suffix (< 6 chars) falls back to defaults."""
        name, ft, aux = _parse_hash_filename('BAR#06')
        assert name == 'BAR'
        assert ft == 0x06
        assert aux == 0x0000


class TestCollectBuildFilesSubdirDefault:
    """Cover line 441 indirectly: collect_build_files custom subdir name."""

    def test_custom_subdir_name(self, tmp_dir):
        """collect_build_files uses custom subdir_name for non-root files."""
        with open(os.path.join(tmp_dir, 'ROST#069500'), 'wb') as f:
            f.write(b'\x00' * 10)
        files = collect_build_files(tmp_dir, subdir_name='DATA')
        assert len(files) == 1
        assert files[0]['subdir'] == 'DATA'


class TestCmdBuildErrorPaths:
    """Cover lines 701-714, 718-725, 736: cmd_build error/boot paths."""

    def test_build_input_dir_not_found(self, capsys):
        """cmd_build exits with error when input directory doesn't exist."""
        from ult3edit.disk import cmd_build
        args = argparse.Namespace(
            output='out.po', input_dir='/nonexistent/path',
            vol_name='ULTIMA3', boot_from=None)
        with pytest.raises(SystemExit):
            cmd_build(args)
        err = capsys.readouterr().err
        assert 'Input directory not found' in err

    def test_build_boot_from_not_found(self, tmp_dir, capsys):
        """cmd_build exits with error when --boot-from file doesn't exist."""
        from ult3edit.disk import cmd_build
        input_dir = os.path.join(tmp_dir, 'input')
        os.makedirs(input_dir)
        with open(os.path.join(input_dir, 'ROST#069500'), 'wb') as f:
            f.write(b'\x00' * 10)
        args = argparse.Namespace(
            output=os.path.join(tmp_dir, 'out.po'), input_dir=input_dir,
            vol_name='ULTIMA3', boot_from='/nonexistent/vanilla.po')
        with pytest.raises(SystemExit):
            cmd_build(args)
        err = capsys.readouterr().err
        assert 'Boot source not found' in err

    def test_build_no_files_found(self, tmp_dir, capsys):
        """cmd_build exits with error when no #hash files found."""
        from ult3edit.disk import cmd_build
        input_dir = os.path.join(tmp_dir, 'empty')
        os.makedirs(input_dir)
        args = argparse.Namespace(
            output=os.path.join(tmp_dir, 'out.po'), input_dir=input_dir,
            vol_name='ULTIMA3', boot_from=None)
        with pytest.raises(SystemExit):
            cmd_build(args)
        err = capsys.readouterr().err
        assert 'No files found' in err

    def test_build_with_boot_blocks(self, tmp_dir, capsys):
        """cmd_build copies boot blocks and prints confirmation."""
        from ult3edit.disk import cmd_build
        input_dir = os.path.join(tmp_dir, 'input')
        os.makedirs(input_dir)
        with open(os.path.join(input_dir, 'ROST#069500'), 'wb') as f:
            f.write(b'\x00' * 10)
        # Create a fake vanilla disk for boot blocks
        boot_file = os.path.join(tmp_dir, 'vanilla.po')
        with open(boot_file, 'wb') as f:
            f.write(b'\xEB' * 1024)
        output_path = os.path.join(tmp_dir, 'out.po')
        args = argparse.Namespace(
            output=output_path, input_dir=input_dir,
            vol_name='ULTIMA3', boot_from=boot_file)
        cmd_build(args)
        out = capsys.readouterr().out
        assert 'Boot blocks copied from vanilla' in out

        # Verify boot blocks are in the image
        with open(output_path, 'rb') as f:
            boot_data = f.read(1024)
        assert boot_data[:512] == b'\xEB' * 512

    def test_build_truncates_tlk_to_256(self, tmp_dir, capsys):
        """cmd_build truncates TLK files to 256 bytes."""
        from ult3edit.disk import cmd_build
        input_dir = os.path.join(tmp_dir, 'input')
        os.makedirs(input_dir)
        with open(os.path.join(input_dir, 'TLKA#060000'), 'wb') as f:
            f.write(b'\x00' * 300)  # > 256 bytes
        output_path = os.path.join(tmp_dir, 'out.po')
        args = argparse.Namespace(
            output=output_path, input_dir=input_dir,
            vol_name='ULTIMA3', boot_from=None)
        cmd_build(args)
        assert os.path.isfile(output_path)


class TestCmdAuditJsonOutput:
    """Cover lines 755-771: cmd_audit JSON output path with capacity estimates."""

    def test_audit_json_has_capacity_estimates(self, monkeypatch, capsys):
        """JSON audit output includes capacity_estimates with all fields."""
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'blocks': '1600',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [
            {'name': 'ROST', 'type': 'BIN', 'size': '1280'},
            {'name': 'MAPA', 'type': 'BIN', 'size': '4096'},
        ])
        args = argparse.Namespace(
            image='test.po', json=True, output=None, detail=False)
        disk.cmd_audit(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert 'capacity_estimates' in data
        ce = data['capacity_estimates']
        assert 'tlk_records' in ce
        assert 'map_files' in ce
        assert 'mon_files' in ce
        assert 'extra_tiles_8x8' in ce
        assert data['image'] == 'test.po'
        assert data['total_bytes'] == 1600 * 512

    def test_audit_json_with_invalid_size(self, monkeypatch, capsys):
        """JSON audit handles non-numeric file sizes gracefully."""
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'blocks': '280',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [
            {'name': 'WEIRD', 'type': 'DIR', 'size': 'n/a'},
        ])
        args = argparse.Namespace(
            image='test.po', json=True, output=None, detail=False)
        disk.cmd_audit(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        # File with invalid size should have size=0
        assert data['files'][0]['size'] == 0

    def test_audit_json_to_file(self, monkeypatch, tmp_dir):
        """JSON audit can write to file via --output."""
        from ult3edit import disk
        monkeypatch.setattr(disk, 'disk_info', lambda image, **kw: {
            'blocks': '280',
        })
        monkeypatch.setattr(disk, 'disk_list', lambda image, **kw: [
            {'name': 'ROST', 'type': 'BIN', 'size': '1280'},
        ])
        outfile = os.path.join(tmp_dir, 'audit.json')
        args = argparse.Namespace(
            image='test.po', json=True, output=outfile, detail=False)
        disk.cmd_audit(args)
        with open(outfile, 'r') as f:
            data = json.loads(f.read())
        assert data['total_blocks'] == 280


class TestDiskDispatch:
    """Cover lines 877-888: dispatch() routing to all subcommands."""

    def test_dispatch_info(self, monkeypatch):
        """dispatch routes 'info' to cmd_info."""
        from ult3edit import disk
        called = []
        monkeypatch.setattr(disk, 'cmd_info', lambda args: called.append('info'))
        args = argparse.Namespace(disk_command='info')
        disk.dispatch(args)
        assert called == ['info']

    def test_dispatch_list(self, monkeypatch):
        """dispatch routes 'list' to cmd_list."""
        from ult3edit import disk
        called = []
        monkeypatch.setattr(disk, 'cmd_list', lambda args: called.append('list'))
        args = argparse.Namespace(disk_command='list')
        disk.dispatch(args)
        assert called == ['list']

    def test_dispatch_extract(self, monkeypatch):
        """dispatch routes 'extract' to cmd_extract."""
        from ult3edit import disk
        called = []
        monkeypatch.setattr(disk, 'cmd_extract', lambda args: called.append('extract'))
        args = argparse.Namespace(disk_command='extract')
        disk.dispatch(args)
        assert called == ['extract']

    def test_dispatch_audit(self, monkeypatch):
        """dispatch routes 'audit' to cmd_audit."""
        from ult3edit import disk
        called = []
        monkeypatch.setattr(disk, 'cmd_audit', lambda args: called.append('audit'))
        args = argparse.Namespace(disk_command='audit')
        disk.dispatch(args)
        assert called == ['audit']

    def test_dispatch_build(self, monkeypatch):
        """dispatch routes 'build' to cmd_build."""
        from ult3edit import disk
        called = []
        monkeypatch.setattr(disk, 'cmd_build', lambda args: called.append('build'))
        args = argparse.Namespace(disk_command='build')
        disk.dispatch(args)
        assert called == ['build']

    def test_dispatch_none(self, capsys):
        """dispatch with no command prints usage."""
        from ult3edit.disk import dispatch
        args = argparse.Namespace(disk_command=None)
        dispatch(args)
        err = capsys.readouterr().err
        assert 'Usage' in err


class TestDiskMain:
    """Cover lines 891-927: main() entry point."""

    def test_main_no_args(self, monkeypatch, capsys):
        """main() with no arguments dispatches with disk_command=None."""
        from ult3edit import disk
        monkeypatch.setattr('sys.argv', ['ult3-disk'])
        # dispatch with no subcommand prints usage to stderr
        disk.main()
        err = capsys.readouterr().err
        assert 'Usage' in err

    def test_main_info_subcommand(self, monkeypatch):
        """main() parses 'info game.po' and routes to cmd_info."""
        from ult3edit import disk
        monkeypatch.setattr('sys.argv', ['ult3-disk', 'info', 'game.po'])
        called = []
        monkeypatch.setattr(disk, 'cmd_info', lambda args: called.append(args))
        disk.main()
        assert len(called) == 1
        assert called[0].image == 'game.po'

    def test_main_list_subcommand(self, monkeypatch):
        """main() parses 'list game.po' and routes to cmd_list."""
        from ult3edit import disk
        monkeypatch.setattr('sys.argv', ['ult3-disk', 'list', 'game.po'])
        called = []
        monkeypatch.setattr(disk, 'cmd_list', lambda args: called.append(args))
        disk.main()
        assert len(called) == 1
        assert called[0].image == 'game.po'

    def test_main_extract_subcommand(self, monkeypatch):
        """main() parses 'extract game.po' and routes to cmd_extract."""
        from ult3edit import disk
        monkeypatch.setattr('sys.argv', ['ult3-disk', 'extract', 'game.po'])
        called = []
        monkeypatch.setattr(disk, 'cmd_extract', lambda args: called.append(args))
        disk.main()
        assert len(called) == 1

    def test_main_audit_subcommand(self, monkeypatch):
        """main() parses 'audit game.po --json' and routes to cmd_audit."""
        from ult3edit import disk
        monkeypatch.setattr('sys.argv', ['ult3-disk', 'audit', 'game.po', '--json'])
        called = []
        monkeypatch.setattr(disk, 'cmd_audit', lambda args: called.append(args))
        disk.main()
        assert len(called) == 1
        assert called[0].json is True

    def test_main_build_subcommand(self, monkeypatch):
        """main() parses 'build out.po /dir' and routes to cmd_build."""
        from ult3edit import disk
        monkeypatch.setattr('sys.argv', [
            'ult3-disk', 'build', 'out.po', '/dir',
            '--vol-name', 'VOIDBORN', '--boot-from', 'vanilla.po'])
        called = []
        monkeypatch.setattr(disk, 'cmd_build', lambda args: called.append(args))
        disk.main()
        assert len(called) == 1
        assert called[0].vol_name == 'VOIDBORN'
        assert called[0].boot_from == 'vanilla.po'

