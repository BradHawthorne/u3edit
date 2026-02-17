"""Tests for game data constants."""

from u3edit.constants import (
    TILES, DUNGEON_TILES, WEAPONS, ARMORS, RACES, CLASSES,
    MARKS_BITS, CARDS_BITS, MONSTER_NAMES, MAP_NAMES, MON_TERRAIN,
    tile_char, tile_name,
)


class TestTileTable:
    def test_completeness(self):
        """Tile table should cover all common tile IDs."""
        # Key tiles that must be present
        assert 0x00 in TILES  # Water
        assert 0x04 in TILES  # Grass
        assert 0x18 in TILES  # Town
        assert 0x20 in TILES  # Floor
        assert 0x48 in TILES  # Guard

    def test_all_multiples_of_4(self):
        """All tile IDs should be multiples of 4."""
        for tid in TILES:
            assert tid % 4 == 0, f"Tile ID ${tid:02X} is not a multiple of 4"

    def test_each_has_char_and_name(self):
        for tid, entry in TILES.items():
            assert len(entry) == 2
            assert isinstance(entry[0], str) and len(entry[0]) == 1
            assert isinstance(entry[1], str) and len(entry[1]) > 0


class TestDungeonTiles:
    def test_count(self):
        assert len(DUNGEON_TILES) == 16

    def test_range(self):
        for tid in DUNGEON_TILES:
            assert 0 <= tid <= 0x0F


class TestTileChar:
    def test_grass(self):
        assert tile_char(0x04) == '.'
        assert tile_char(0x05) == '.'  # animation frame stripped

    def test_water(self):
        assert tile_char(0x00) == '~'

    def test_dungeon_wall(self):
        assert tile_char(0x01, is_dungeon=True) == '#'

    def test_unknown(self):
        assert tile_char(0xFF) == '?'


class TestTileName:
    def test_known(self):
        assert tile_name(0x04) == 'Grass'
        assert tile_name(0x18) == 'Town'

    def test_dungeon(self):
        assert tile_name(0x01, is_dungeon=True) == 'Wall'

    def test_unknown(self):
        name = tile_name(0xFF)
        assert 'Unknown' in name


class TestEquipment:
    def test_weapons_count(self):
        assert len(WEAPONS) == 16

    def test_weapons_start_with_hands(self):
        assert WEAPONS[0] == 'Hands'

    def test_armors_count(self):
        assert len(ARMORS) == 8

    def test_armors_start_with_skin(self):
        assert ARMORS[0] == 'Skin'


class TestCharacterEnums:
    def test_races(self):
        assert len(RACES) == 5
        assert ord('H') in RACES

    def test_classes(self):
        assert len(CLASSES) == 11

    def test_marks_high_nibble(self):
        """Marks should use bits 7-4."""
        for bit in MARKS_BITS:
            assert bit >= 4

    def test_cards_low_nibble(self):
        """Cards should use bits 3-0."""
        for bit in CARDS_BITS:
            assert bit <= 3


class TestMonsterNames:
    def test_known_creatures(self):
        assert MONSTER_NAMES[0x48] == 'Guard'
        assert MONSTER_NAMES[0x74] == 'Dragon'
        assert MONSTER_NAMES[0x78] == 'Balron'

    def test_not_empty(self):
        assert len(MONSTER_NAMES) > 10
