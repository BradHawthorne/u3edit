"""TUI bestiary editor: form-based monster list with field editing."""

from ..constants import MON_FILE_SIZE, MON_MONSTERS_PER_FILE, MON_ATTR_COUNT
from ..bestiary import Monster, load_mon_file, save_mon_file
from .form_editor import FormField, FormEditorTab


def _monster_label(monster, index):
    """Generate display label for a monster in the record list."""
    if monster.is_empty:
        return f'[{index:2d}] (empty)'
    return (f'[{index:2d}] {monster.name:<16s}  '
            f'HP:{monster.hp:3d}  ATK:{monster.attack:3d}  '
            f'DEF:{monster.defense:3d}  SPD:{monster.speed:3d}')


def _byte_clamp(v):
    """Parse string as int (auto-detect hex with 0x/$) and clamp 0-255."""
    s = v.strip()
    if s.startswith('$'):
        s = '0x' + s[1:]
    return max(0, min(255, int(s, 0)))


def _monster_fields(monster):
    """Generate FormField list for editing a monster."""
    return [
        FormField('Tile 1',
                   lambda: f'${monster.tile1:02X} ({monster.name})',
                   lambda v: setattr(monster, 'tile1', _byte_clamp(v)),
                   fmt='int'),
        FormField('Tile 2',
                   lambda: f'${monster.tile2:02X}',
                   lambda v: setattr(monster, 'tile2', _byte_clamp(v)),
                   fmt='int'),
        FormField('HP',
                   lambda: monster.hp,
                   lambda v: setattr(monster, 'hp', _byte_clamp(v)),
                   fmt='int'),
        FormField('Attack',
                   lambda: monster.attack,
                   lambda v: setattr(monster, 'attack', _byte_clamp(v)),
                   fmt='int'),
        FormField('Defense',
                   lambda: monster.defense,
                   lambda v: setattr(monster, 'defense', _byte_clamp(v)),
                   fmt='int'),
        FormField('Speed',
                   lambda: monster.speed,
                   lambda v: setattr(monster, 'speed', _byte_clamp(v)),
                   fmt='int'),
        FormField('Flags 1',
                   lambda: f'${monster.flags1:02X} ({monster.flag_desc})',
                   lambda v: setattr(monster, 'flags1', _byte_clamp(v)),
                   fmt='int'),
        FormField('Flags 2',
                   lambda: f'${monster.flags2:02X}',
                   lambda v: setattr(monster, 'flags2', _byte_clamp(v)),
                   fmt='int'),
        FormField('Ability 1',
                   lambda: f'${monster.ability1:02X} ({monster.ability_desc})',
                   lambda v: setattr(monster, 'ability1', _byte_clamp(v)),
                   fmt='int'),
        FormField('Ability 2',
                   lambda: f'${monster.ability2:02X}',
                   lambda v: setattr(monster, 'ability2', _byte_clamp(v)),
                   fmt='int'),
    ]


def make_bestiary_tab(data, file_letter, save_callback):
    """Create a FormEditorTab for a single MON file."""
    original_data = bytes(data)

    # Parse monsters from columnar format
    monsters = []
    for i in range(MON_MONSTERS_PER_FILE):
        attrs = []
        for row in range(MON_ATTR_COUNT):
            offset = row * MON_MONSTERS_PER_FILE + i
            attrs.append(data[offset] if offset < len(data) else 0)
        monsters.append(Monster(attrs, i, file_letter))

    def get_save_data():
        out = bytearray(original_data)  # Preserve unknown rows
        for m in monsters:
            attrs = [m.tile1, m.tile2, m.flags1, m.flags2,
                     m.hp, m.attack, m.defense, m.speed,
                     m.ability1, m.ability2]
            for row, val in enumerate(attrs):
                out[row * MON_MONSTERS_PER_FILE + m.index] = val
        return bytes(out)

    return FormEditorTab(
        tab_name=f'MON{file_letter}',
        records=monsters,
        record_label_fn=_monster_label,
        field_factory=_monster_fields,
        save_callback=save_callback,
        get_save_data=get_save_data,
    )
