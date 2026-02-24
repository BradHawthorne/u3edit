"""Tests for GameSession catalog scanning (no disk image needed)."""

import os
import pytest

from ult3edit.disk import DiskContext
from ult3edit.tui.game_session import GameSession


class MockCtx:
    """Mock DiskContext for testing without actual disk images."""

    def __init__(self, tmpdir):
        self._tmpdir = tmpdir
        self._cache = {}
        self._modified = {}

    def read(self, name):
        # Check modified cache first
        if name in self._modified:
            return self._modified[name]
        for f in os.listdir(self._tmpdir):
            if f.split('#')[0].upper() == name.upper():
                fpath = os.path.join(self._tmpdir, f)
                with open(fpath, 'rb') as fp:
                    return fp.read()
        return None

    def write(self, name, data):
        self._modified[name] = data


def _make_session(tmp_dir, files=None):
    """Create a GameSession with a mock tmpdir."""
    if files is None:
        files = {
            'MAPA#061000': 4096,
            'MAPB#061000': 2048,
            'MAPM#061000': 2048,
            'CONA#069900': 192,
            'CONG#069900': 192,
            'BRND#060000': 128,
            'FNTN#060000': 128,
            'TLKA#060800': 1024,
            'TLKD#060800': 1024,
            'TEXT#060800': 1024,
            'ROST#069500': 1280,
            'MONA#069900': 256,
            'MONZ#069900': 256,
            'PRTY#060000': 16,
        }

    session = GameSession.__new__(GameSession)
    session.image_path = 'fake.po'
    session.catalog = {}

    for fname, size in files.items():
        path = os.path.join(tmp_dir, fname)
        with open(path, 'wb') as f:
            f.write(bytes(size))

    session.ctx = MockCtx(tmp_dir)
    session._scan_catalog()
    return session


@pytest.fixture
def mock_session(tmp_dir):
    return _make_session(tmp_dir)


class TestCatalogScanning:
    def test_maps_detected(self, mock_session):
        assert mock_session.has_category('maps')
        names = [n for n, _ in mock_session.files_in('maps')]
        assert 'MAPA' in names
        assert 'MAPB' in names
        assert 'MAPM' in names

    def test_combat_detected(self, mock_session):
        assert mock_session.has_category('combat')
        names = [n for n, _ in mock_session.files_in('combat')]
        assert 'CONA' in names
        assert 'CONG' in names

    def test_special_detected(self, mock_session):
        assert mock_session.has_category('special')
        names = [n for n, _ in mock_session.files_in('special')]
        assert 'BRND' in names
        assert 'FNTN' in names
        assert 'SHRN' not in names

    def test_dialog_detected(self, mock_session):
        assert mock_session.has_category('dialog')
        names = [n for n, _ in mock_session.files_in('dialog')]
        assert 'TLKA' in names
        assert 'TLKD' in names

    def test_text_detected(self, mock_session):
        assert mock_session.has_category('text')
        assert mock_session.files_in('text') == [('TEXT', 'Game Text')]

    def test_roster_detected(self, mock_session):
        assert mock_session.has_category('roster')
        assert mock_session.files_in('roster') == [('ROST', 'Character Roster')]

    def test_bestiary_detected(self, mock_session):
        assert mock_session.has_category('bestiary')
        names = [n for n, _ in mock_session.files_in('bestiary')]
        assert 'MONA' in names
        assert 'MONZ' in names

    def test_party_detected(self, mock_session):
        assert mock_session.has_category('party')
        assert mock_session.files_in('party') == [('PRTY', 'Party State')]

    def test_missing_category(self, mock_session):
        assert not mock_session.has_category('nonexistent')
        assert mock_session.files_in('nonexistent') == []

    def test_display_names(self, mock_session):
        maps = dict(mock_session.files_in('maps'))
        assert maps['MAPA'] == 'Sosaria (Overworld)'
        assert maps['MAPB'] == 'Lord British Castle'
        assert maps['MAPM'] == 'Dungeon of Fire'


class TestReadWrite:
    def test_read_file(self, mock_session):
        data = mock_session.read('ROST')
        assert data is not None
        assert len(data) == 1280

    def test_read_missing(self, mock_session):
        data = mock_session.read('NONEXIST')
        assert data is None

    def test_save_callback(self, mock_session):
        cb = mock_session.make_save_callback('MAPA')
        cb(b'\x01\x02\x03')
        assert mock_session.ctx._modified['MAPA'] == b'\x01\x02\x03'

    def test_write_then_read(self, mock_session):
        """Write should stage data that read returns."""
        mock_session.write('MAPA', b'\xAA\xBB\xCC')
        data = mock_session.read('MAPA')
        assert data == b'\xAA\xBB\xCC'


class TestEmptyDisk:
    def test_empty_catalog(self, tmp_dir):
        """An empty disk image should produce no categories."""
        session = _make_session(tmp_dir, files={})
        assert not session.has_category('maps')
        assert not session.has_category('combat')
        assert not session.has_category('text')
        assert not session.has_category('roster')
        assert not session.has_category('party')
        assert session.files_in('maps') == []

    def test_partial_catalog(self, tmp_dir):
        """A disk with only some files should only have those categories."""
        session = _make_session(tmp_dir, files={
            'TEXT#060800': 1024,
            'ROST#069500': 1280,
        })
        assert session.has_category('text')
        assert session.has_category('roster')
        assert not session.has_category('maps')
        assert not session.has_category('combat')
        assert not session.has_category('bestiary')


class TestDiskContextHashParsing:
    def test_parse_hash_suffix(self):
        name, ft, at = DiskContext._parse_hash_suffix('ROST#069500')
        assert name == 'ROST'
        assert ft == 0x06
        assert at == 0x9500

    def test_parse_no_hash(self):
        name, ft, at = DiskContext._parse_hash_suffix('MAPA')
        assert name == 'MAPA'
        assert ft == 0x06
        assert at == 0x0000

    def test_parse_short_suffix(self):
        name, ft, at = DiskContext._parse_hash_suffix('FOO#06')
        assert name == 'FOO'
        assert ft == 0x06
        assert at == 0x0000


# =============================================================================
# Coverage: game_session.py lines 28-30 (__init__), 33-36 (__enter__),
# 39-41 (__exit__), 46 (_scan_catalog guard), 119 (EXOD catalog entry)
# =============================================================================


class TestGameSessionInit:
    """Cover lines 28-30: GameSession.__init__ sets attributes."""

    def test_init_attributes(self):
        session = GameSession('fake.po')
        assert session.image_path == 'fake.po'
        assert session.ctx is None
        assert session.catalog == {}


class TestGameSessionExitWithoutCtx:
    """Cover lines 39-41: __exit__ when ctx is None returns False."""

    def test_exit_no_ctx(self):
        session = GameSession('fake.po')
        result = session.__exit__(None, None, None)
        assert result is False


class TestGameSessionScanNoCtx:
    """Cover line 46: _scan_catalog returns early when ctx or tmpdir is None."""

    def test_scan_no_ctx(self):
        session = GameSession('fake.po')
        session._scan_catalog()
        assert session.catalog == {}

    def test_scan_ctx_no_tmpdir(self):
        session = GameSession('fake.po')
        session.ctx = type('Ctx', (), {'_tmpdir': None})()
        session._scan_catalog()
        assert session.catalog == {}


class TestGameSessionExodCatalog:
    """Cover line 119: EXOD catalog entry with virtual sub-editors."""

    def test_exod_detected(self, tmp_dir):
        session = _make_session(tmp_dir, files={
            'EXOD#062000': 26208,
        })
        assert session.has_category('exod')
        exod_files = session.files_in('exod')
        names = [n for n, _ in exod_files]
        assert 'EXOD:crawl' in names
        assert 'EXOD:glyphs' in names
        assert 'EXOD:frames' in names

    def test_exod_virtual_read(self, tmp_dir):
        """Reading EXOD:crawl should read the base EXOD file."""
        session = _make_session(tmp_dir, files={
            'EXOD#062000': 26208,
        })
        data = session.read('EXOD:crawl')
        assert data is not None
        assert len(data) == 26208

    def test_exod_virtual_save_callback(self, tmp_dir):
        """Save callback for EXOD:crawl writes to base EXOD."""
        session = _make_session(tmp_dir, files={
            'EXOD#062000': 26208,
        })
        cb = session.make_save_callback('EXOD:crawl')
        cb(b'\x00' * 26208)
        assert 'EXOD' in session.ctx._modified
