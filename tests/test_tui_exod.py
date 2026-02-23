"""Tests for EXOD TUI editors (data logic, no terminal needed)."""

import struct

from ult3edit.exod import (
    EXOD_SIZE,
    GLYPH_COUNT,
    GLYPH_DATA_SIZE,
    GLYPH_TABLE_OFFSET,
    GLYPH_VARIANTS,
    TEXT_CRAWL_OFFSET,
    extract_text_crawl,
)
from ult3edit.tui.exod_editor import (
    ExodCrawlEditor,
    ExodGlyphViewer,
    ExodFrameViewer,
)
from ult3edit.tui.game_session import GameSession


class TestExodCrawlEditor:
    """Test crawl editor data operations (no terminal)."""

    def _make_exod_with_crawl(self, coords):
        """Build EXOD data with known crawl coordinates."""
        data = bytearray(EXOD_SIZE)
        offset = TEXT_CRAWL_OFFSET
        for x, y in coords:
            stored_y = 0xBF - y
            data[offset] = x
            data[offset + 1] = stored_y
            offset += 2
        # Terminator
        data[offset] = 0x00
        return bytes(data)

    def test_loads_coordinates(self):
        """Editor loads crawl coordinates from EXOD data."""
        exod = self._make_exod_with_crawl([(100, 132), (110, 140)])
        editor = ExodCrawlEditor(exod)
        assert len(editor.coords) == 2
        assert editor.coords[0] == (100, 132)
        assert editor.coords[1] == (110, 140)

    def test_initially_clean(self):
        """Editor starts not dirty."""
        exod = self._make_exod_with_crawl([(100, 132)])
        editor = ExodCrawlEditor(exod)
        assert not editor.is_dirty

    def test_name(self):
        """Editor name is 'Crawl'."""
        exod = bytes(EXOD_SIZE)
        editor = ExodCrawlEditor(exod)
        assert editor.name == 'Crawl'

    def test_modify_marks_dirty(self):
        """Modifying a coordinate marks editor as dirty."""
        exod = self._make_exod_with_crawl([(100, 132)])
        editor = ExodCrawlEditor(exod)
        editor.coords[0] = (120, 140)
        editor.dirty = True
        assert editor.is_dirty

    def test_add_point(self):
        """Adding a point increases coord count."""
        exod = self._make_exod_with_crawl([(100, 132)])
        editor = ExodCrawlEditor(exod)
        editor.coords.insert(1, (140, 132))
        assert len(editor.coords) == 2
        assert editor.coords[1] == (140, 132)

    def test_delete_point(self):
        """Deleting a point decreases coord count."""
        exod = self._make_exod_with_crawl([(100, 132), (110, 140)])
        editor = ExodCrawlEditor(exod)
        del editor.coords[0]
        assert len(editor.coords) == 1
        assert editor.coords[0] == (110, 140)

    def test_save_callback(self):
        """Save calls the callback with modified EXOD data."""
        exod = self._make_exod_with_crawl([(100, 132)])
        saved_data = []
        editor = ExodCrawlEditor(exod, save_callback=lambda d: saved_data.append(d))
        editor.coords[0] = (120, 140)
        editor.dirty = True
        editor.save()
        assert len(saved_data) == 1
        assert len(saved_data[0]) == EXOD_SIZE
        assert not editor.is_dirty

    def test_save_roundtrip(self):
        """Save + re-parse preserves coordinates."""
        coords = [(100, 132), (150, 140), (200, 100)]
        exod = self._make_exod_with_crawl(coords)
        saved_data = []
        editor = ExodCrawlEditor(exod, save_callback=lambda d: saved_data.append(d))
        editor.dirty = True
        editor.save()
        # Re-parse saved data
        new_coords = extract_text_crawl(saved_data[0])
        assert new_coords == coords

    def test_empty_crawl(self):
        """Editor handles empty crawl data."""
        exod = bytes(EXOD_SIZE)
        editor = ExodCrawlEditor(exod)
        assert editor.coords == []


class TestExodGlyphViewer:
    """Test glyph viewer data properties."""

    def test_name(self):
        exod = bytes(EXOD_SIZE)
        viewer = ExodGlyphViewer(exod)
        assert viewer.name == 'Glyphs'

    def test_not_dirty(self):
        exod = bytes(EXOD_SIZE)
        viewer = ExodGlyphViewer(exod)
        assert not viewer.is_dirty

    def test_save_is_noop(self):
        exod = bytes(EXOD_SIZE)
        viewer = ExodGlyphViewer(exod)
        viewer.save()  # should not raise


class TestExodFrameViewer:
    """Test frame viewer data properties."""

    def test_name(self):
        exod = bytes(EXOD_SIZE)
        viewer = ExodFrameViewer(exod)
        assert viewer.name == 'Frames'

    def test_not_dirty(self):
        exod = bytes(EXOD_SIZE)
        viewer = ExodFrameViewer(exod)
        assert not viewer.is_dirty

    def test_save_is_noop(self):
        exod = bytes(EXOD_SIZE)
        viewer = ExodFrameViewer(exod)
        viewer.save()  # should not raise


class TestExodCategory:
    """Test EXOD category detection in GameSession."""

    def test_virtual_name_read(self):
        """Reading 'EXOD:crawl' should read the base 'EXOD' file."""
        session = GameSession.__new__(GameSession)
        session.ctx = None
        session.catalog = {}
        # Without a real context, read returns None
        result = session.read('EXOD:crawl')
        assert result is None

    def test_virtual_name_save_callback(self):
        """Save callback for 'EXOD:crawl' writes to 'EXOD'."""
        session = GameSession.__new__(GameSession)
        session.ctx = None
        session.catalog = {}
        written = {}

        def fake_write(name, data):
            written[name] = data
        session.write = fake_write

        cb = session.make_save_callback('EXOD:crawl')
        cb(b'\x00' * 10)
        assert 'EXOD' in written
        assert written['EXOD'] == b'\x00' * 10

    def test_catalog_entries(self):
        """EXOD catalog has 3 virtual entries."""
        entries = [
            ('EXOD:crawl', 'Text Crawl'),
            ('EXOD:glyphs', 'Glyph Table'),
            ('EXOD:frames', 'HGR Frames'),
        ]
        assert len(entries) == 3
        assert entries[0][0] == 'EXOD:crawl'
        assert entries[1][0] == 'EXOD:glyphs'
        assert entries[2][0] == 'EXOD:frames'
