"""Shared fixtures for ult3edit tests.

Builds synthesized binary data matching real Ultima III file formats.
No real game files are needed to run the test suite.
"""

import os
import tempfile
import pytest

from ult3edit.bcd import int_to_bcd, int_to_bcd16
from ult3edit.constants import (
    CHAR_RECORD_SIZE, ROSTER_FILE_SIZE,
    MON_FILE_SIZE, MAP_OVERWORLD_SIZE, MAP_DUNGEON_SIZE,
    CON_FILE_SIZE, SPECIAL_FILE_SIZE, TEXT_FILE_SIZE,
    PRTY_FILE_SIZE, CHAR_NAME_OFFSET, CHAR_STATUS, CHAR_STR, CHAR_DEX,
    CHAR_INT, CHAR_WIS, CHAR_RACE, CHAR_CLASS, CHAR_GENDER,
    CHAR_HP_HI, CHAR_HP_LO, CHAR_MAX_HP_HI, CHAR_MAX_HP_LO,
    CHAR_FOOD_HI, CHAR_FOOD_LO, CHAR_GOLD_HI, CHAR_GOLD_LO,
    CHAR_MARKS_CARDS,
)


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sample_character_bytes():
    """Build a single 64-byte character record with known values."""
    rec = bytearray(CHAR_RECORD_SIZE)
    # Name: "HERO" in high-bit ASCII
    name = b'\xC8\xC5\xD2\xCF'  # H E R O
    rec[CHAR_NAME_OFFSET:CHAR_NAME_OFFSET + len(name)] = name
    # Status: Good
    rec[CHAR_STATUS] = ord('G')
    # Stats: STR=25, DEX=30, INT=15, WIS=20 (BCD)
    rec[CHAR_STR] = int_to_bcd(25)
    rec[CHAR_DEX] = int_to_bcd(30)
    rec[CHAR_INT] = int_to_bcd(15)
    rec[CHAR_WIS] = int_to_bcd(20)
    # Race=Human, Class=Fighter, Gender=Male
    rec[CHAR_RACE] = ord('H')
    rec[CHAR_CLASS] = ord('F')
    rec[CHAR_GENDER] = ord('M')
    # HP: 150 (BCD16)
    hi, lo = int_to_bcd16(150)
    rec[CHAR_HP_HI] = hi
    rec[CHAR_HP_LO] = lo
    rec[CHAR_MAX_HP_HI] = hi
    rec[CHAR_MAX_HP_LO] = lo
    # Food: 200
    hi, lo = int_to_bcd16(200)
    rec[CHAR_FOOD_HI] = hi
    rec[CHAR_FOOD_LO] = lo
    # Gold: 100
    hi, lo = int_to_bcd16(100)
    rec[CHAR_GOLD_HI] = hi
    rec[CHAR_GOLD_LO] = lo
    # Marks: Kings (bit 7) + Force (bit 4) = 0x90, Cards: none
    rec[CHAR_MARKS_CARDS] = 0x90
    return bytes(rec)


@pytest.fixture
def sample_roster_bytes(sample_character_bytes):
    """Build a full 1280-byte roster with 1 character in slot 0."""
    data = bytearray(ROSTER_FILE_SIZE)
    data[:CHAR_RECORD_SIZE] = sample_character_bytes
    return bytes(data)


@pytest.fixture
def sample_roster_file(tmp_dir, sample_roster_bytes):
    """Write a roster file to tmp_dir and return its path."""
    path = os.path.join(tmp_dir, 'ROST#069500')
    with open(path, 'wb') as f:
        f.write(sample_roster_bytes)
    return path


@pytest.fixture
def sample_mon_bytes():
    """Build a 256-byte MON file with 3 monsters."""
    data = bytearray(MON_FILE_SIZE)
    # Monster 0: Guard (tile1=0x48), HP=50, ATK=30, DEF=20, SPD=15
    data[0 * 16 + 0] = 0x48   # tile1
    data[1 * 16 + 0] = 0x48   # tile2
    data[4 * 16 + 0] = 50     # hp
    data[5 * 16 + 0] = 30     # attack
    data[6 * 16 + 0] = 20     # defense
    data[7 * 16 + 0] = 15     # speed
    # Monster 1: Dragon (tile1=0x74), HP=200, ATK=80, DEF=50, SPD=25, Boss flag
    data[0 * 16 + 1] = 0x74
    data[1 * 16 + 1] = 0x74
    data[2 * 16 + 1] = 0x80   # flags1: Boss
    data[4 * 16 + 1] = 200
    data[5 * 16 + 1] = 80
    data[6 * 16 + 1] = 50
    data[7 * 16 + 1] = 25
    # Monster 2: Skeleton (tile1=0x64), HP=30, undead
    data[0 * 16 + 2] = 0x64
    data[1 * 16 + 2] = 0x64
    data[2 * 16 + 2] = 0x04   # flags1: Undead
    data[4 * 16 + 2] = 30
    data[5 * 16 + 2] = 15
    data[6 * 16 + 2] = 10
    data[7 * 16 + 2] = 10
    return bytes(data)


@pytest.fixture
def sample_mon_file(tmp_dir, sample_mon_bytes):
    path = os.path.join(tmp_dir, 'MONA#069900')
    with open(path, 'wb') as f:
        f.write(sample_mon_bytes)
    return path


@pytest.fixture
def sample_overworld_bytes():
    """Build a 4096-byte overworld map (64x64, all grass)."""
    data = bytearray(MAP_OVERWORLD_SIZE)
    for i in range(MAP_OVERWORLD_SIZE):
        data[i] = 0x04  # Grass
    # Add some water at top-left
    for y in range(4):
        for x in range(4):
            data[y * 64 + x] = 0x00  # Water
    # Town at (10, 10)
    data[10 * 64 + 10] = 0x18  # Town
    return bytes(data)


@pytest.fixture
def sample_map_file(tmp_dir, sample_overworld_bytes):
    path = os.path.join(tmp_dir, 'MAPA#061000')
    with open(path, 'wb') as f:
        f.write(sample_overworld_bytes)
    return path


@pytest.fixture
def sample_dungeon_bytes():
    """Build a 2048-byte dungeon map (8 levels of 16x16)."""
    data = bytearray(MAP_DUNGEON_SIZE)
    for level in range(8):
        base = level * 256
        for y in range(16):
            for x in range(16):
                if x == 0 or x == 15 or y == 0 or y == 15:
                    data[base + y * 16 + x] = 0x01  # Wall
                else:
                    data[base + y * 16 + x] = 0x00  # Open
        # Door at (1, 8)
        data[base + 8 * 16 + 1] = 0x02
    return bytes(data)


@pytest.fixture
def sample_tlk_bytes():
    """Build a TLK file with 2 dialog records."""
    # Record 0: "HELLO ADVENTURER" (one line)
    rec0 = bytearray()
    for ch in 'HELLO ADVENTURER':
        rec0.append(ord(ch) | 0x80)
    rec0.append(0x00)
    # Record 1: "WELCOME" / "TO MY SHOP" (two lines)
    rec1 = bytearray()
    for ch in 'WELCOME':
        rec1.append(ord(ch) | 0x80)
    rec1.append(0xFF)  # line break
    for ch in 'TO MY SHOP':
        rec1.append(ord(ch) | 0x80)
    rec1.append(0x00)
    return bytes(rec0 + rec1)


@pytest.fixture
def sample_tlk_file(tmp_dir, sample_tlk_bytes):
    path = os.path.join(tmp_dir, 'TLKA#060000')
    with open(path, 'wb') as f:
        f.write(sample_tlk_bytes)
    return path


@pytest.fixture
def sample_con_bytes():
    """Build a 192-byte combat map."""
    data = bytearray(CON_FILE_SIZE)
    # 11x11 tiles: floor (0x20) with wall border (0x8C)
    for y in range(11):
        for x in range(11):
            offset = y * 11 + x
            if x == 0 or x == 10 or y == 0 or y == 10:
                data[offset] = 0x8C  # Wall
            else:
                data[offset] = 0x20  # Floor
    # Monster positions
    data[0x80] = 5; data[0x81] = 6  # monster 0 at (5,3), monster 1 at (6,3)
    data[0x88] = 3; data[0x89] = 3
    # PC positions
    data[0xA0] = 2; data[0xA1] = 3  # PC 0 at (2,8), PC 1 at (3,8)
    data[0xA4] = 8; data[0xA5] = 8
    return bytes(data)


@pytest.fixture
def sample_special_bytes():
    """Build a 128-byte special location file."""
    data = bytearray(SPECIAL_FILE_SIZE)
    # 11x11 tiles: all floor
    for i in range(121):
        data[i] = 0x20  # Floor
    return bytes(data)


@pytest.fixture
def sample_text_bytes():
    """Build a 1024-byte TEXT file with 3 strings."""
    data = bytearray(TEXT_FILE_SIZE)
    offset = 0
    for text in ['ULTIMA III', 'EXODUS', 'PRESS ANY KEY']:
        for ch in text:
            data[offset] = ord(ch) | 0x80
            offset += 1
        data[offset] = 0x00  # null terminator
        offset += 1
    return bytes(data)


@pytest.fixture
def sample_prty_bytes():
    """Build a 16-byte PRTY file matching engine layout ($E0-$EF)."""
    data = bytearray(PRTY_FILE_SIZE)
    data[0] = 0x01  # $E0: Transport = On Foot
    data[1] = 4     # $E1: Party size = 4
    data[2] = 0x00  # $E2: Location type = Sosaria
    data[3] = 32    # $E3: Saved overworld X
    data[4] = 32    # $E4: Saved overworld Y
    data[5] = 0xFF  # $E5: Sentinel (active party)
    data[6] = 0     # $E6: Slot 0
    data[7] = 1     # $E7: Slot 1
    data[8] = 2     # $E8: Slot 2
    data[9] = 3     # $E9: Slot 3
    return bytes(data)
