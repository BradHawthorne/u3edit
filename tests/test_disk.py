"""Tests for diskiigs integration (mocked subprocess)."""

import os
import pytest
from unittest.mock import patch

from u3edit.disk import find_diskiigs, DiskContext


class TestFindDiskiigs:
    def test_env_var(self, tmp_dir):
        exe = os.path.join(tmp_dir, 'diskiigs.exe')
        with open(exe, 'w') as f:
            f.write('fake')
        with patch.dict(os.environ, {'DISKIIGS_PATH': exe}):
            result = find_diskiigs()
            assert result == exe

    def test_not_found(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch('shutil.which', return_value=None):
                with patch('os.path.isfile', return_value=False):
                    result = find_diskiigs()
                    assert result is None


class TestDiskContext:
    def test_context_manager(self, tmp_dir):
        """DiskContext should raise FileNotFoundError when diskiigs not found."""
        with patch('u3edit.disk.find_diskiigs', return_value=None):
            with pytest.raises(FileNotFoundError):
                with DiskContext('fake.po') as ctx:
                    pass
