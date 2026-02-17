"""Tests for special location tool."""

import pytest

from u3edit.special import render_special_map
from u3edit.constants import SPECIAL_MAP_WIDTH, SPECIAL_MAP_HEIGHT, SPECIAL_FILE_SIZE


class TestRenderSpecialMap:
    def test_dimensions(self, sample_special_bytes):
        rendered = render_special_map(sample_special_bytes)
        lines = rendered.strip().split('\n')
        # Header + 11 rows
        assert len(lines) == SPECIAL_MAP_HEIGHT + 1

    def test_content(self, sample_special_bytes):
        rendered = render_special_map(sample_special_bytes)
        assert '_' in rendered  # Floor tiles


class TestSizeHandling:
    def test_exact_size(self, sample_special_bytes):
        assert len(sample_special_bytes) == SPECIAL_FILE_SIZE

    def test_small_data(self):
        """Should handle data smaller than expected."""
        rendered = render_special_map(bytes(50))
        assert len(rendered) > 0
