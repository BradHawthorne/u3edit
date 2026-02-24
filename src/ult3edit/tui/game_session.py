"""GameSession: coordinates all game data from a disk image.

Wraps DiskContext for read/write and catalogs available files by category
(maps, combat, special, dialog, text, roster, bestiary, party).
"""

import os

from ..constants import (
    MAP_LETTERS, MAP_NAMES, CON_LETTERS, CON_NAMES,
    TLK_LETTERS, TLK_NAMES,
    MON_LETTERS, MON_GROUP_NAMES,
    SPECIAL_NAMES,
)
from ..disk import DiskContext


class GameSession:
    """Manages all game data loaded from a disk image.

    Usage:
        with GameSession('game.po') as session:
            data = session.read('MAPA')
            session.write('MAPA', modified_data)
    """

    def __init__(self, image_path: str):
        self.image_path = image_path
        self.ctx = None
        self.catalog = {}  # category -> [(file_name, display_name), ...]

    def __enter__(self):  # pragma: no cover
        self.ctx = DiskContext(self.image_path)
        self.ctx.__enter__()
        self._scan_catalog()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # pragma: no cover
        if self.ctx:
            return self.ctx.__exit__(exc_type, exc_val, exc_tb)
        return False

    def _scan_catalog(self):
        """Scan extracted files and categorize them."""
        if not self.ctx or not self.ctx._tmpdir:
            return

        # Build a set of available base names from extracted files
        available = set()
        for f in os.listdir(self.ctx._tmpdir):
            if os.path.isfile(os.path.join(self.ctx._tmpdir, f)):
                available.add(f.split('#')[0].upper())

        # Maps
        maps = []
        for letter in MAP_LETTERS:
            name = f'MAP{letter}'
            if name in available:
                display = MAP_NAMES.get(letter, f'Map {letter}')
                maps.append((name, display))
        if maps:
            self.catalog['maps'] = maps

        # Combat
        combat = []
        for letter in CON_LETTERS:
            name = f'CON{letter}'
            if name in available:
                display = CON_NAMES.get(letter, f'Combat {letter}')
                combat.append((name, display))
        if combat:
            self.catalog['combat'] = combat

        # Special
        special = []
        for sname, display in SPECIAL_NAMES.items():
            if sname in available:
                special.append((sname, display))
        if special:
            self.catalog['special'] = special

        # Dialog (TLK)
        dialog = []
        for letter in TLK_LETTERS:
            name = f'TLK{letter}'
            if name in available:
                display = TLK_NAMES.get(letter, f'Dialog {letter}')
                dialog.append((name, display))
        if dialog:
            self.catalog['dialog'] = dialog

        # Text
        if 'TEXT' in available:
            self.catalog['text'] = [('TEXT', 'Game Text')]

        # Roster
        if 'ROST' in available:
            self.catalog['roster'] = [('ROST', 'Character Roster')]

        # Bestiary (MON)
        bestiary = []
        for letter in MON_LETTERS:
            name = f'MON{letter}'
            if name in available:
                display = MON_GROUP_NAMES.get(letter, f'Monsters {letter}')
                bestiary.append((name, display))
        if bestiary:
            self.catalog['bestiary'] = bestiary

        # Party / Save state
        party = []
        if 'PRTY' in available:
            party.append(('PRTY', 'Party State'))
        if party:
            self.catalog['party'] = party

        # EXOD (title screen / boot loader)
        if 'EXOD' in available:
            self.catalog['exod'] = [
                ('EXOD:crawl', 'Text Crawl'),
                ('EXOD:glyphs', 'Glyph Table'),
                ('EXOD:frames', 'HGR Frames'),
            ]

    def read(self, name: str) -> bytes | None:
        """Read a file from the disk image (cached).

        Handles virtual names like 'EXOD:crawl' by reading the base file.
        """
        if self.ctx:
            # Virtual names: 'FILE:sub' reads the base FILE
            base = name.split(':')[0] if ':' in name else name
            return self.ctx.read(base)
        return None

    def write(self, name: str, data: bytes) -> None:
        """Stage a file for writing back to disk image."""
        if self.ctx:
            self.ctx.write(name, data)

    def make_save_callback(self, file_name: str):
        """Return a callable that writes data to this file in the session.

        Handles virtual names like 'EXOD:crawl' by writing to the base file.
        """
        base = file_name.split(':')[0] if ':' in file_name else file_name
        def callback(data: bytes):
            self.write(base, data)
        return callback

    def has_category(self, category: str) -> bool:
        """Check if a category has any files."""
        return category in self.catalog and len(self.catalog[category]) > 0

    def files_in(self, category: str) -> list[tuple[str, str]]:
        """Get list of (file_name, display_name) for a category."""
        return self.catalog.get(category, [])
