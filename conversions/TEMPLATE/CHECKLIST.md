# Ultima III Total Conversion Checklist

A complete checklist of every replaceable asset in Ultima III: Exodus.
Check off each item as you modify it for your total conversion.

Copy this file into your conversion directory and track progress.

---

## Prerequisites

- [ ] u3edit installed (`pip install -e .`)
- [ ] Extracted ProDOS game files in a working directory
- [ ] Backup of original game files

---

## 1. Characters & Party

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] Party roster (slots 0-3) | `roster create --slot N` | Name, race, class, gender, stats |
| [ ] Character stats (STR/DEX/INT/WIS) | `roster edit --slot N --str/--dex/--int/--wis` | BCD 0-99 |
| [ ] HP/MaxHP/EXP | `roster edit --hp/--max-hp/--exp` | BCD16 0-9999 |
| [ ] Equipment | `roster edit --weapon/--armor/--give-weapon/--give-armor` | Index or name |
| [ ] Resources (gold/food/gems/keys/powders/torches) | `roster edit --gold/--food/--gems/--keys/--powders/--torches` | |
| [ ] Marks and cards | `roster edit --marks/--cards` | Comma-separated names |
| [ ] In-party flags | `roster edit --in-party/--not-in-party` | |
| [ ] Bulk import from JSON | `roster import ROST party.json` | Full party definition |

## 2. Save State

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] Starting position (X, Y) | `save edit --x N --y N` | 0-63 |
| [ ] Transport mode | `save edit --transport foot/horse/ship` | Or raw hex |
| [ ] Location type | `save edit --location sosaria/town/dungeon` | |
| [ ] Party size | `save edit --party-size N` | 1-4 |
| [ ] Sentinel (active flag) | `save edit --sentinel 255` | 0xFF = active |
| [ ] Slot IDs | `save edit --slot-ids 0 1 2 3` | Roster slot indices |
| [ ] Bulk import from JSON | `save import DIR save.json` | |

## 3. Bestiary (Monster Stats)

8 encounter files (MON A-H+), 16 monsters each.

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] MONA — Grassland encounters | `bestiary edit MONA --monster N` | HP/ATK/DEF/SPD/flags |
| [ ] MONB — Forest encounters | `bestiary edit MONB --monster N` | |
| [ ] MONC — Mountain encounters | `bestiary edit MONC --monster N` | |
| [ ] MOND — Ocean encounters | `bestiary edit MOND --monster N` | |
| [ ] MONE — Town guard encounters | `bestiary edit MONE --monster N` | |
| [ ] MONF — Dungeon L1-2 encounters | `bestiary edit MONF --monster N` | |
| [ ] MONG — Dungeon L3-4 encounters | `bestiary edit MONG --monster N` | |
| [ ] MONH — Dungeon L5-6 encounters | `bestiary edit MONH --monster N` | |
| [ ] MONI — Dungeon L7-8 encounters | `bestiary edit MONI --monster N` | |
| [ ] MONJ — Castle encounters | `bestiary edit MONJ --monster N` | |
| [ ] MONK — Ambrosia encounters | `bestiary edit MONK --monster N` | |
| [ ] MONL — Special encounters | `bestiary edit MONL --monster N` | |
| [ ] MONZ — Boss encounters | `bestiary edit MONZ --monster N` | |
| [ ] Bulk edit (all monsters) | `bestiary edit FILE --all --hp N` | Apply to all 16 |
| [ ] Bulk import from JSON | `bestiary import FILE stats.json` | |

## 4. Combat Maps (Battlefields)

9 battlefield layouts (CON files), 11x11 tile grid + positions.

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] CONA — LB Castle battlefield | `combat edit CONA --tile X Y VAL` | |
| [ ] CONB — Castle of Death battlefield | `combat edit CONB --tile X Y VAL` | |
| [ ] CONF — Dungeon battlefield | `combat edit CONF --tile X Y VAL` | |
| [ ] CONG — Grassland battlefield | `combat edit CONG --tile X Y VAL` | |
| [ ] CONM — Mountain battlefield | `combat edit CONM --tile X Y VAL` | |
| [ ] CONQ — Water battlefield | `combat edit CONQ --tile X Y VAL` | |
| [ ] CONR — Forest battlefield | `combat edit CONR --tile X Y VAL` | |
| [ ] CONS — Town battlefield | `combat edit CONS --tile X Y VAL` | |
| [ ] Monster start positions | `combat edit FILE --monster-pos I X Y` | 8 monster slots |
| [ ] PC start positions | `combat edit FILE --pc-pos I X Y` | 4 PC slots |
| [ ] Bulk import from JSON | `combat import FILE layout.json` | |

## 5. Overworld Maps

4 surface maps (64x64 tiles each).

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] MAPA — Sosaria (main overworld) | `map set/fill/replace/import` | 64x64 |
| [ ] MAPB — Lord British Castle | `map set/fill/replace/import` | 64x64 |
| [ ] MAPC — Castle of Death | `map set/fill/replace/import` | 64x64 |
| [ ] MAPD — Town of Dawn | `map set/fill/replace/import` | 64x64 |
| [ ] MAPE-MAPK — Other towns | `map set/fill/replace/import` | 64x64 each |
| [ ] MAPL — Ambrosia | `map set/fill/replace/import` | 64x64 |
| [ ] MAPZ — Exodus Castle | `map set/fill/replace/import` | 64x64 |

## 6. Dungeon Maps

8 dungeons, 16x16 tiles per level, 8 levels each.

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] MAPM — Dungeon of Fire | `map set/fill/replace/import --level N` | 8 levels |
| [ ] MAPN — Dungeon of Doom | `map set/fill/replace/import --level N` | |
| [ ] MAPO — Dungeon of Snake | `map set/fill/replace/import --level N` | |
| [ ] MAPP — Dungeon of Perinian | `map set/fill/replace/import --level N` | |
| [ ] MAPQ — Dungeon of Time | `map set/fill/replace/import --level N` | |
| [ ] MAPR — Dungeon of Mine | `map set/fill/replace/import --level N` | |
| [ ] MAPS — Dungeon of Darkling | `map set/fill/replace/import --level N` | |

## 7. Special Locations

4 special location files, 11x11 tile grid each.

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] BRND — Brand Shrine | `special edit BRND --tile X Y VAL` | |
| [ ] SHRN — Shrines | `special edit SHRN --tile X Y VAL` | |
| [ ] FNTN — Fountains | `special edit FNTN --tile X Y VAL` | |
| [ ] TIME — Time Lord | `special edit TIME --tile X Y VAL` | |
| [ ] Bulk import from JSON | `special import FILE layout.json` | |

## 8. Dialog (NPC Text)

19 TLK files, one per location type.

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] TLKA — Lord British Castle | `tlk edit/extract/build` | |
| [ ] TLKB — Castle of Death | `tlk edit/extract/build` | |
| [ ] TLKC — Castle Arena | `tlk edit/extract/build` | |
| [ ] TLKD — Town of Dawn | `tlk edit/extract/build` | |
| [ ] TLKE — Town of Fawn | `tlk edit/extract/build` | |
| [ ] TLKF — Town of Grey | `tlk edit/extract/build` | |
| [ ] TLKG — Town of Moon | `tlk edit/extract/build` | |
| [ ] TLKH — Town of Yew | `tlk edit/extract/build` | |
| [ ] TLKI — Town of Montor East | `tlk edit/extract/build` | |
| [ ] TLKJ — Town of Montor West | `tlk edit/extract/build` | |
| [ ] TLKK — Town of Devil Guard | `tlk edit/extract/build` | |
| [ ] TLKL — Ambrosia | `tlk edit/extract/build` | |
| [ ] TLKM — Dungeon of Fire | `tlk edit/extract/build` | |
| [ ] TLKN — Dungeon of Doom | `tlk edit/extract/build` | |
| [ ] TLKO — Dungeon of Snake | `tlk edit/extract/build` | |
| [ ] TLKP — Dungeon of Perinian | `tlk edit/extract/build` | |
| [ ] TLKQ — Dungeon of Time | `tlk edit/extract/build` | |
| [ ] TLKR — Dungeon of Mine | `tlk edit/extract/build` | |
| [ ] TLKS — Dungeon of Darkling | `tlk edit/extract/build` | |

**Dialog workflow** (full rewrite):
```bash
u3edit tlk extract TLKA tlka.txt    # Extract to editable text
# Edit tlka.txt with any text editor
u3edit tlk build tlka.txt TLKA      # Compile back to binary
```

**Dialog workflow** (find/replace):
```bash
u3edit tlk edit TLKA --find "OLD TEXT" --replace "NEW TEXT" --ignore-case
```

## 9. Tile Graphics

256 glyphs in SHPS (7 visible pixels wide x 8 rows, 8 bytes per glyph).

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] Terrain tiles (0x00-0x13) | `shapes edit --glyph N --data HEX` | Water, grass, forest, etc. |
| [ ] Building tiles (0x14-0x1F) | `shapes edit --glyph N --data HEX` | Towns, castles, doors |
| [ ] NPC tiles (0x20-0x3F) | `shapes edit --glyph N --data HEX` | Characters, merchants |
| [ ] Monster tiles (0x40-0x7F) | `shapes edit --glyph N --data HEX` | All creature sprites |
| [ ] UI tiles (0x80-0xFF) | `shapes edit --glyph N --data HEX` | Effects, walls, items |
| [ ] Bulk import from JSON | `shapes import SHPS tiles.json` | Full tileset replacement |

**Tile compiler workflow** (text-art source):
```bash
python conversions/tools/tile_compiler.py decompile SHPS --output vanilla.tiles
# Edit vanilla.tiles with text editor
python conversions/tools/tile_compiler.py compile custom.tiles --format json > tiles.json
u3edit shapes import SHPS tiles.json
```

## 10. Shop Overlays (SHP0-SHP7)

Inline text strings in shop overlay code files.

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] SHP0 — Weapons shop text | `shapes edit-string SHP0 --offset HEX --text "..."` | |
| [ ] SHP1 — Armor shop text | `shapes edit-string SHP1 --offset HEX --text "..."` | |
| [ ] SHP2-SHP7 — Other shop text | `shapes edit-string SHPN --offset HEX --text "..."` | |

**Find available string offsets**: `u3edit shapes view SHP0 --strings`

## 11. Sound Effects

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] SOSA — Speaker sound patterns | `sound edit SOSA --offset HEX --data HEX` | 4096 bytes |
| [ ] SOSM — Sound map table | `sound edit SOSM --offset HEX --data HEX` | 256 bytes |
| [ ] Bulk import from JSON | `sound import FILE data.json` | |

## 12. Music

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] MBS — Mockingboard sequences | `sound edit MBS --offset HEX --data HEX` | 5456 bytes, AY-3-8910 |
| [ ] Bulk import from JSON | `sound import MBS data.json` | |

See `conversions/tools/MUSIC_FORMAT.md` for the MBS byte format reference.

## 13. Engine Binary Patches

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] Name table (921 bytes) | `patch edit ULT3 --region name-table --data HEX` | All game entity names |
| [ ] Moongate X coords (8 bytes) | `patch edit ULT3 --region moongate-x --data HEX` | 8 lunar phases |
| [ ] Moongate Y coords (8 bytes) | `patch edit ULT3 --region moongate-y --data HEX` | 8 lunar phases |
| [ ] Food depletion rate (1 byte) | `patch edit ULT3 --region food-rate --data HEX` | Default: 04 |

**Name table workflow**:
```bash
# Edit encode_nametable.py with your conversion's names
python encode_nametable.py /path/to/ULT3 > nametable.hex
u3edit patch edit ULT3 --region name-table --data "$(cat nametable.hex)"
```

## 14. Title Screen Text

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] Game title (record 0) | `text edit TEXT --record 0 --text "YOUR TITLE"` | |
| [ ] Subtitle (record 1) | `text edit TEXT --record 1 --text "YOUR SUBTITLE"` | |

## 15. Dungeon Rendering

| Item | u3edit Command | Notes |
|------|----------------|-------|
| [ ] DDRW perspective data | `ddrw edit DDRW --offset HEX --data HEX` | 1792 bytes total |
| [ ] Bulk import from JSON | `ddrw import DDRW data.json` | |

---

## Verification

After applying all modifications:

```bash
# Verify all files are modified from vanilla
python conversions/tools/verify.py /path/to/GAME/

# Run u3edit validation on key files
u3edit roster view ROST --validate
u3edit save view DIR --validate
u3edit combat view CONG --validate
```

---

## Asset Count Summary

| Category | Files | Items |
|----------|-------|-------|
| Characters | 1 (ROST) | 20 slots |
| Save State | 2 (PRTY, PLRS) | Party config |
| Bestiary | 13 (MON A-L,Z) | 208 monsters |
| Combat Maps | 9 (CON files) | 9 battlefields |
| Overworld Maps | ~13 (MAP A-L,Z) | 13 locations |
| Dungeon Maps | 7 (MAP M-S) | 56 levels |
| Special Locations | 4 (BRND/SHRN/FNTN/TIME) | 4 layouts |
| Dialog | 19 (TLK A-S) | All NPC text |
| Tile Graphics | 1 (SHPS) | 256 glyphs |
| Shop Overlays | 8 (SHP0-SHP7) | Inline strings |
| Sound Effects | 2 (SOSA, SOSM) | Audio data |
| Music | 1 (MBS) | Mockingboard |
| Engine Names | 1 (ULT3) | 921-byte table |
| Engine Config | 1 (ULT3) | Moongates, food |
| Title Text | 1 (TEXT) | 2 records |
| Dungeon Drawing | 1 (DDRW) | Rendering data |
| **Total** | **~84 files** | **All game data** |
