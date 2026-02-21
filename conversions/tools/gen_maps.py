#!/usr/bin/env python
"""Generate all Voidborn map source files with guaranteed exact dimensions."""
import os
import random

SRCDIR = os.path.join(os.path.dirname(__file__), '..', 'voidborn', 'sources')


def write_surface_map(filename, comment_header, rows):
    """Write a 64x64 surface map with comment header."""
    assert len(rows) == 64, f'{filename}: {len(rows)} rows'
    for i, r in enumerate(rows):
        assert len(r) == 64, f'{filename} row {i}: {len(r)} chars'
    path = os.path.join(SRCDIR, filename)
    with open(path, 'w', newline='\n') as f:
        f.write(comment_header)
        for r in rows:
            f.write(r + '\n')
    print(f'  {filename}: 64x64 OK')


def write_dungeon_map(filename, comment_header, levels):
    """Write an 8-level 16x16 dungeon map."""
    assert len(levels) == 8, f'{filename}: {len(levels)} levels'
    for li, level in enumerate(levels):
        assert len(level) == 16, f'{filename} L{li}: {len(level)} rows'
        for ri, r in enumerate(level):
            assert len(r) == 16, f'{filename} L{li} row {ri}: {len(r)} chars'
    path = os.path.join(SRCDIR, filename)
    with open(path, 'w', newline='\n') as f:
        f.write(comment_header)
        for li, level in enumerate(levels):
            f.write(f'# Level {li + 1}\n')
            for r in level:
                f.write(r + '\n')
    print(f'  {filename}: 8x16x16 OK')


# ============ SURFACE MAP GENERATORS ============

def gen_castle(ankh_row=None):
    """Generic castle: water moat, walls, rooms, throne."""
    rows = []
    W = '~' * 64
    # Water border top
    for _ in range(8):
        rows.append(W)
    # Approach
    for _ in range(3):
        rows.append('~' * 18 + '.' * 28 + '~' * 18)
    # Outer wall top
    rows.append('~' * 18 + '|' * 28 + '~' * 18)
    # Interior rows
    for i in range(24):
        inner = '_' * 26
        if i == 0:
            inner = ':' * 26
        elif i == 4:
            # Shop counters
            inner = '_' * 5 + 'c' + '_' * 7 + '|' + '_' * 5 + 'c' + '_' * 6
        elif i == 8:
            # Corridor wall
            inner = '|' * 12 + '/' + '|' * 13
        elif i == 12:
            # Throne
            inner = '_' * 12 + '%' + '_' * 13
        elif i == 16:
            # Another corridor
            inner = '|' * 12 + '/' + '|' * 13
        elif i == 20:
            inner = '_' * 5 + 'b' + '_' * 5 + 'b' + '_' * 5 + 'b' + '_' * 5 + 'b' + '_' * 2
        rows.append('~' * 18 + '|' + inner + '|' + '~' * 18)
    # Outer wall bottom with gate
    rows.append('~' * 18 + '|' * 13 + '/' + '|' * 14 + '~' * 18)
    # Approach bottom
    for _ in range(3):
        rows.append('~' * 18 + '.' * 28 + '~' * 18)
    # Water border bottom
    while len(rows) < 64:
        rows.append(W)
    return rows[:64]


def gen_town(variant=0):
    """Generic town: water border, walls, main street, shops."""
    rows = []
    W = '~' * 64
    # Water border
    for _ in range(10):
        rows.append(W)
    # Approach
    for _ in range(3):
        rows.append('~' * 16 + '.' * 32 + '~' * 16)
    # Town wall top
    rows.append('~' * 16 + '|' * 32 + '~' * 16)
    # Interior - 24 rows
    for i in range(24):
        inner = '_' * 30
        if i == 0 or i == 23:
            inner = ':' * 30
        elif i == 4:
            # Shop row 1
            inner = '_' * 4 + 'c' + '_' * 7 + '|' + '_' * 4 + 'c' + '_' * 6 + '|' + '_' * 5
        elif i == 5:
            # Doors
            inner = '_' * 11 + '/' + '_' * 11 + '/' + '_' * 6
        elif i == 12:
            # Mid corridor
            inner = '|' * 14 + '/' + '|' * 15
        elif i == 16:
            # Shop row 2
            inner = '_' * 4 + 'c' + '_' * 7 + '|' + '_' * 4 + 'c' + '_' * 6 + '|' + '_' * 5
        elif i == 17:
            inner = '_' * 11 + '/' + '_' * 11 + '/' + '_' * 6
        rows.append('~' * 16 + '|' + inner + '|' + '~' * 16)
    # Town wall bottom with gate
    rows.append('~' * 16 + '|' * 15 + '/' + '|' * 16 + '~' * 16)
    # Approach bottom
    for _ in range(3):
        rows.append('~' * 16 + '.' * 32 + '~' * 16)
    # Water
    while len(rows) < 64:
        rows.append(W)
    return rows[:64]


def gen_mapz():
    """Voidborn's Nexus (final castle) - void-surrounded fortress."""
    rows = []
    V = '*' * 64
    for _ in range(10):
        rows.append(V)
    for _ in range(4):
        rows.append('*' * 18 + '.' * 28 + '*' * 18)
    # Outer walls
    rows.append('*' * 18 + '|' * 28 + '*' * 18)
    for i in range(18):
        inner = '_' * 26
        if i == 8:
            inner = '_' * 12 + '%' + '_' * 13
        elif i == 4 or i == 14:
            inner = '|' * 12 + '/' + '|' * 13
        rows.append('*' * 18 + '|' + inner + '|' + '*' * 18)
    rows.append('*' * 18 + '|' * 13 + '/' + '|' * 14 + '*' * 18)
    for _ in range(4):
        rows.append('*' * 18 + '.' * 28 + '*' * 18)
    while len(rows) < 64:
        rows.append(V)
    return rows[:64]


def gen_mapl():
    """Deep Reef - underwater special surface."""
    rows = []
    W = '~' * 64
    for _ in range(12):
        rows.append(W)
    for _ in range(5):
        rows.append('~' * 22 + '.' * 20 + '~' * 22)
    # Reef structure
    rows.append('~' * 22 + '|' * 20 + '~' * 22)
    for i in range(12):
        inner = '_' * 18
        if i == 4:
            inner = '_' * 4 + 'c' + '_' * 5 + '|' + '_' * 4 + 'c' + '_' * 2
        elif i == 8:
            inner = '_' * 8 + '%' + '_' * 9
        rows.append('~' * 22 + '|' + inner + '|' + '~' * 22)
    rows.append('~' * 22 + '|' * 9 + '/' + '|' * 10 + '~' * 22)
    for _ in range(5):
        rows.append('~' * 22 + '.' * 20 + '~' * 22)
    while len(rows) < 64:
        rows.append(W)
    return rows[:64]


# ============ DUNGEON MAP GENERATOR ============

def gen_dungeon(has_mark=True, seed=0):
    """Generate 8-level dungeon. Mark on L7 if has_mark."""
    rng = random.Random(seed)
    levels = []
    for level_idx in range(8):
        complexity = min(level_idx + 1, 5)
        grid = [['#'] * 16 for _ in range(16)]

        # Carve main corridors
        for x in range(1, 15):
            grid[8][x] = '.'
        for y in range(1, 15):
            grid[y][8] = '.'

        # Carve rooms based on complexity
        rooms = [(2, 2, 5, 5), (10, 2, 5, 5), (2, 10, 5, 5), (10, 10, 5, 5)]
        for ri, (rx, ry, rw, rh) in enumerate(rooms):
            if ri < complexity:
                for dy in range(rh):
                    for dx in range(rw):
                        if ry + dy < 16 and rx + dx < 16:
                            grid[ry + dy][rx + dx] = '.'
                # Door to corridor
                if rx < 8:
                    grid[ry + rh // 2][rx + rw] = 'D'
                else:
                    grid[ry + rh // 2][rx - 1] = 'D'

        # Add features based on level
        if level_idx < 7:
            grid[1][1] = 'V'   # Down ladder
        if level_idx > 0:
            grid[1][14] = '^'  # Up ladder
        if level_idx >= 2:
            grid[14][7] = '$'  # Chest
        if level_idx >= 3:
            grid[12][3] = 'T'  # Trap
        if level_idx >= 4:
            grid[3][12] = 'F'  # Fountain
        if level_idx == 6 and has_mark:
            grid[8][8] = 'M'   # Mark on L7
        if level_idx == 7:
            grid[14][14] = '$'  # Boss treasure

        # Secret doors on deeper levels
        if level_idx >= 1:
            grid[4][7] = '>'

        levels.append([''.join(row) for row in grid])
    return levels


# ============ MAIN ============

def main():
    print('Generating surface maps...')

    # Castles
    write_surface_map('mapb.map',
        "# MAPB - Prophet's Bastion (Lord British Castle, 64x64)\n"
        "# Fortified castle with water moat, walls, shops, throne room\n",
        gen_castle())

    write_surface_map('mapc.map',
        "# MAPC - Eyeless Spire (Castle 2, 64x64)\n"
        "# Dark fortress of the Void Cult\n",
        gen_castle())

    # Towns
    town_names = [
        ('d', 'Ashfall'),
        ('e', 'Duskhollow'),
        ('f', 'Grimwall'),
        ('g', 'Riftwatch'),
        ('h', 'Thornhaven'),
        ('i', 'Ironhold East'),
        ('j', 'Ironhold West'),
        ('k', 'The Last Wall'),
    ]
    for letter, name in town_names:
        write_surface_map(f'map{letter}.map',
            f"# MAP{letter.upper()} - {name} (Town, 64x64)\n"
            f"# Town with shops, NPCs, and local landmarks\n",
            gen_town())

    # Special surface
    write_surface_map('mapl.map',
        "# MAPL - Deep Reef (Special Surface, 64x64)\n"
        "# Underwater reef settlement\n",
        gen_mapl())

    # Final castle
    write_surface_map('mapz.map',
        "# MAPZ - Voidborn's Nexus (Final Castle, 64x64)\n"
        "# Void-surrounded fortress of the Voidborn\n",
        gen_mapz())

    print('\nGenerating dungeon maps...')
    dungeons = [
        ('m', 'Abyss of Flame', True, 100),
        ('n', 'Abyss of Madness', True, 200),
        ('o', 'Abyss of Serpents', True, 300),
        ('p', 'Abyss of Chains', False, 400),
        ('q', 'Abyss of Time', True, 500),
        ('r', 'Abyss of Echoes', False, 600),
        ('s', 'Abyss of Shadows', False, 700),
    ]
    for letter, name, has_mark, seed in dungeons:
        write_dungeon_map(f'map{letter}.map',
            f"# MAP{letter.upper()} - {name} (Dungeon, 8 levels x 16x16)\n"
            f"# .=Open #=Wall D=Door >=Secret $=Chest V=Down ^=Up T=Trap F=Fountain M=Mark\n",
            gen_dungeon(has_mark, seed))

    print('\nDone! All maps generated.')


if __name__ == '__main__':
    main()
