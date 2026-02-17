"""Tests for diskiigs integration (mocked subprocess)."""

import os
import pytest
from unittest.mock import patch, MagicMock

from u3edit.disk import find_diskiigs, disk_info, disk_list, DiskContext


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
        with patch('u3edit.disk._run_diskiigs', return_value=mock_result):
            info = disk_info('game.po')
            assert info['volume'] == 'ULTIMA3'
            assert info['format'] == 'ProDOS'
            assert info['blocks'] == '280'

    def test_error(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "File not found"
        with patch('u3edit.disk._run_diskiigs', return_value=mock_result):
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
        with patch('u3edit.disk._run_diskiigs', return_value=mock_result):
            entries = disk_list('game.po')
            assert len(entries) == 2
            assert entries[0]['name'] == 'ROST'
            assert entries[1]['name'] == 'MAPA'

    def test_empty_on_error(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch('u3edit.disk._run_diskiigs', return_value=mock_result):
            entries = disk_list('bad.po')
            assert entries == []


class TestDiskContext:
    def test_context_manager(self, tmp_dir):
        """DiskContext should raise FileNotFoundError when diskiigs not found."""
        with patch('u3edit.disk.find_diskiigs', return_value=None):
            with pytest.raises(FileNotFoundError):
                with DiskContext('fake.po') as ctx:
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
