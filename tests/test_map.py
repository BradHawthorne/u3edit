"""Tests for map tool."""


from ult3edit.constants import tile_char
from ult3edit.map import render_map, map_to_grid


class TestTileCharMapping:
    def test_water(self):
        assert tile_char(0x00) == '~'
        assert tile_char(0x01) == '~'  # animation frame

    def test_grass(self):
        assert tile_char(0x04) == '.'
        assert tile_char(0x05) == '.'

    def test_town(self):
        assert tile_char(0x18) == '#'

    def test_floor(self):
        """M-1 fix: floor tiles should render correctly."""
        assert tile_char(0x20) == '_'

    def test_chest(self):
        """M-1 fix: chests in towns should render."""
        assert tile_char(0x24) == '$'

    def test_guard(self):
        """M-1 fix: NPCs in towns should render."""
        assert tile_char(0x48) == 'G'

    def test_dungeon_wall(self):
        assert tile_char(0x01, is_dungeon=True) == '#'

    def test_dungeon_door(self):
        assert tile_char(0x02, is_dungeon=True) == 'D'


class TestRenderMap:
    def test_overworld(self, sample_overworld_bytes):
        result = render_map(sample_overworld_bytes, 64, 64)
        assert '~' in result  # Water
        assert '.' in result  # Grass
        assert '#' in result  # Town

    def test_crop(self, sample_overworld_bytes):
        result = render_map(sample_overworld_bytes, 64, 64, crop=(0, 0, 10, 10))
        lines = result.strip().split('\n')
        # Header + 10 rows
        assert len(lines) == 11

    def test_dungeon(self, sample_dungeon_bytes):
        result = render_map(sample_dungeon_bytes[:256], 16, 16, is_dungeon=True)
        assert '#' in result  # Wall
        assert '.' in result  # Open


class TestMapToGrid:
    def test_dimensions(self, sample_overworld_bytes):
        grid = map_to_grid(sample_overworld_bytes, 64, 64)
        assert len(grid) == 64
        assert len(grid[0]) == 64

    def test_tile_names(self, sample_overworld_bytes):
        grid = map_to_grid(sample_overworld_bytes, 64, 64)
        assert grid[0][0] == 'Water'
        assert grid[5][5] == 'Grass'
        assert grid[10][10] == 'Town'

    def test_dungeon_names(self, sample_dungeon_bytes):
        grid = map_to_grid(sample_dungeon_bytes[:256], 16, 16, is_dungeon=True)
        assert grid[0][0] == 'Wall'
        assert grid[1][1] == 'Open'
        assert grid[8][1] == 'Door'
