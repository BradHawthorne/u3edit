"""Tests for game data constants."""

from u3edit.constants import (
    TILES, DUNGEON_TILES, WEAPONS, ARMORS, RACES, CLASSES,
    MARKS_BITS, CARDS_BITS, MONSTER_NAMES, MAP_NAMES, MON_TERRAIN,
    WEAPON_DAMAGE, WEAPON_PRICE, ARMOR_EVASION, CLASS_MAX_WEAPON, CLASS_MAX_ARMOR,
    WIZARD_SPELLS, CLERIC_SPELLS, MON_GROUP_NAMES,
    tile_char, tile_name,
)


class TestTileTable:
    def test_completeness(self):
        """Tile table should cover all common tile IDs."""
        assert 0x00 in TILES  # Water
        assert 0x04 in TILES  # Grass
        assert 0x18 in TILES  # Town
        assert 0x20 in TILES  # Floor
        assert 0x48 in TILES  # Guard
        assert 0xFC in TILES  # Hidden

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
        assert tile_char(0xE3) == '?'


class TestTileName:
    def test_known(self):
        assert tile_name(0x04) == 'Grass'
        assert tile_name(0x18) == 'Town'

    def test_dungeon(self):
        assert tile_name(0x01, is_dungeon=True) == 'Wall'

    def test_unknown(self):
        name = tile_name(0xE0)
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

    def test_weapon_damage_matches(self):
        assert len(WEAPON_DAMAGE) == len(WEAPONS)
        assert WEAPON_DAMAGE[0] == 0  # Hands do no base damage

    def test_weapon_price_matches(self):
        assert len(WEAPON_PRICE) == len(WEAPONS)
        assert WEAPON_PRICE[0] == 0  # Hands are free

    def test_armor_evasion_matches(self):
        assert len(ARMOR_EVASION) == len(ARMORS)
        assert ARMOR_EVASION[0] == 50.0  # Skin = 50%
        assert ARMOR_EVASION[-1] > ARMOR_EVASION[0]  # Better armor = higher evasion

    def test_class_restrictions(self):
        for cls in CLASSES.values():
            assert cls in CLASS_MAX_WEAPON
            assert cls in CLASS_MAX_ARMOR


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
        assert MONSTER_NAMES[0x48] == 'Fighter'
        assert MONSTER_NAMES[0x74] == 'Dragon'
        assert MONSTER_NAMES[0x78] == 'Balron'
        assert MONSTER_NAMES[0xFC] == 'Devil'

    def test_not_empty(self):
        assert len(MONSTER_NAMES) > 15

    def test_group_names(self):
        assert 'A' in MON_GROUP_NAMES
        assert 'Z' in MON_GROUP_NAMES


class TestSpells:
    def test_wizard_count(self):
        assert len(WIZARD_SPELLS) == 16

    def test_cleric_count(self):
        assert len(CLERIC_SPELLS) == 16

    def test_spell_format(self):
        for name, cost in WIZARD_SPELLS:
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(cost, int) and cost >= 0

    def test_costs_increase(self):
        costs = [cost for _, cost in WIZARD_SPELLS]
        assert costs[-1] >= costs[0]
