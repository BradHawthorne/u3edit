# [Your Conversion Name] — Story & World Design

## Setting

_2-3 paragraphs describing your world. What is it called? What happened to it?
What is the tone — heroic fantasy, cosmic horror, sci-fi, comedy?_

**World Name**: _______________
**Tone**: _______________
**Premise**: _______________

---

## Factions

The engine supports 4 marks (Fire, Force, Snake, Kings) and 4 cards (Sol, Moon,
Love, Death) as progression tokens. Map these to your world's factions or power
sources. Players must collect all 8 to reach the final encounter.

| Token | Vanilla Name | Your Name | Faction/Source | Location |
|-------|-------------|-----------|----------------|----------|
| Mark 1 | Fire | | | |
| Mark 2 | Force | | | |
| Mark 3 | Snake | | | |
| Mark 4 | Kings | | | |
| Card 1 | Sol | | | |
| Card 2 | Moon | | | |
| Card 3 | Love | | | |
| Card 4 | Death | | | |

---

## Main Quest

The engine enforces a linear quest structure:
1. Collect 4 marks (from shrines/special locations)
2. Collect 4 cards (from dungeon depths)
3. Access the final area (Exodus castle equivalent)
4. Defeat the final boss

### Act 1: [Name]
_How does the adventure begin? Where does the party start? What is the
initial objective?_

### Act 2: [Name] — The Marks/Tokens
_Describe the journey to collect the 4 marks. Each mark comes from a
shrine-type location. What guards each one? What story beats occur?_

| Mark | Location | Guardian/Challenge | Story Beat |
|------|----------|--------------------|------------|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |

### Act 3: [Name] — The Cards/Keys
_The 4 cards are found at the bottom of dungeons. Which dungeons? What
makes each one distinct?_

| Card | Dungeon | Theme | Depth | Story Beat |
|------|---------|-------|-------|------------|
| 1 | | | Level 8 | |
| 2 | | | Level 8 | |
| 3 | | | Level 8 | |
| 4 | | | Level 8 | |

### Act 4: [Name] — Final Confrontation
_With all 8 tokens, the party accesses the final area. What is it?
Who or what is the final boss? How does the story resolve?_

---

## Locations

Map every game location to your conversion's narrative. The engine has fixed
location types — you rename and re-theme them but cannot add new ones.

### Overworld
| Map | Vanilla Name | Your Name | Description |
|-----|-------------|-----------|-------------|
| MAPA | Sosaria | | Main overworld |
| MAPL | Ambrosia | | Hidden continent |

### Castles
| Map | Vanilla Name | Your Name | Role |
|-----|-------------|-----------|------|
| MAPB | Lord British Castle | | Home base, quest hub |
| MAPC | Castle of Death | | Mid-game challenge |
| MAPZ | Exodus Castle | | Final dungeon entrance |

### Towns (10 towns)
| Map | Vanilla Name | Your Name | Key NPCs | Shops |
|-----|-------------|-----------|----------|-------|
| MAPD | Dawn | | | |
| MAPE | Fawn | | | |
| MAPF | Grey | | | |
| MAPG | Moon | | | |
| MAPH | Yew | | | |
| MAPI | Montor East | | | |
| MAPJ | Montor West | | | |
| MAPK | Devil Guard | | | |

### Dungeons (7 dungeons, 8 levels each)
| Map | Vanilla Name | Your Name | Theme | Quest Item |
|-----|-------------|-----------|-------|------------|
| MAPM | Fire | | | |
| MAPN | Doom | | | |
| MAPO | Snake | | | |
| MAPP | Perinian | | | |
| MAPQ | Time | | | |
| MAPR | Mine | | | |
| MAPS | Darkling | | | |

### Special Locations
| File | Vanilla Name | Your Name | Purpose |
|------|-------------|-----------|---------|
| BRND | Brand Shrine | | Mark collection |
| SHRN | Shrines | | Mark collection |
| FNTN | Fountains | | Stat boost / puzzle |
| TIME | Time Lord | | Quest hint / gate |

---

## NPCs & Dialog

Each TLK file corresponds to a location. Plan your NPC dialog by file.

| TLK | Location | NPC Count | Key Characters | Dialog Theme |
|-----|----------|-----------|----------------|--------------|
| A | LB Castle | | | Quest exposition |
| B | Castle of Death | | | Warnings, lore |
| C | Castle Arena | | | Combat hints |
| D | Dawn | | | Town gossip |
| E | Fawn | | | |
| F | Grey | | | |
| G | Moon | | | |
| H | Yew | | | |
| I | Montor East | | | |
| J | Montor West | | | |
| K | Devil Guard | | | |
| L | Ambrosia | | | Hidden lore |
| M-S | Dungeons | | | Dungeon encounters |

**Dialog constraints**:
- Text is high-bit ASCII (uppercase only in original, but lower works)
- `\n` for line breaks within a record
- Each TLK file has a fixed size — records must fit within the file
- Use `tlk extract/build` for full dialog replacement

---

## Naming Conventions

All names must fit within the engine's 921-byte name table.
Use `encode_nametable.py` to validate your budget.

### Terrain Names (39 slots)
| Index | Vanilla | Yours | Max Length |
|-------|---------|-------|-----------|
| 0 | Ground | | ~8 chars |
| 1 | Water | | |
| 2 | Grass | | |
| ... | ... | | |

### Monster Names (16 primary + 16 alternate)
| Index | Vanilla | Yours |
|-------|---------|-------|
| 0 | Brigand | |
| 1 | Goblin | |
| ... | ... | |

### Weapon Names (16 slots)
| Index | Vanilla | Yours |
|-------|---------|-------|
| 0 | Hands | |
| 1 | Dagger | |
| ... | ... | |

### Armor Names (8 slots)
| Index | Vanilla | Yours |
|-------|---------|-------|
| 0 | Skin | |
| 1 | Cloth | |
| ... | ... | |

### Spell Names (15 wizard + 16 cleric)
| Type | Index | Vanilla | Yours |
|------|-------|---------|-------|
| Wizard | 0 | Repond | |
| Wizard | 1 | Mittar | |
| ... | | ... | |
| Cleric | 0 | Sanctu | |
| ... | | ... | |

**Budget check**: Run `python encode_nametable.py` to verify total byte count
stays under 891 bytes (921 - 30 reserved for BLOAD tail).

---

## The Party

| Slot | Name | Race | Class | Role | Backstory |
|------|------|------|-------|------|-----------|
| 0 | | | | Leader | |
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

**Available races**: Human, Elf, Dwarf, Bobbit, Fuzzy
**Available classes**: Fighter, Cleric, Wizard, Thief, Lark, Illusionist, Druid,
Alchemist, Ranger, Paladin, Barbarian

---

## Combat Balance

Design your encounter difficulty curve:

| Area | Encounter File | Target Level | Monster HP Range | Notes |
|------|---------------|-------------|-----------------|-------|
| Starting area | MONA | 1-3 | 20-60 | Easy, tutorial |
| Forest | MONB | 3-5 | 40-100 | Moderate |
| Mountains | MONC | 5-7 | 80-150 | Challenging |
| Ocean | MOND | 4-6 | 60-120 | Ship battles |
| Dungeon L1-2 | MONF | 5-7 | 80-150 | |
| Dungeon L3-4 | MONG | 7-9 | 120-200 | |
| Dungeon L5-6 | MONH | 9-11 | 160-300 | |
| Dungeon L7-8 | MONI | 11-13 | 200-400 | Endgame |
| Bosses | MONZ | 13+ | 400-999 | Final tier |

---

## Implementation Checklist

Track your progress converting each asset category:

- [ ] Story document complete (this file)
- [ ] Name table defined and budget validated
- [ ] Party roster designed
- [ ] All maps designed (overworld + towns + dungeons)
- [ ] All combat maps designed
- [ ] All special locations designed
- [ ] All dialog written
- [ ] All bestiary stats balanced
- [ ] Tile graphics created
- [ ] Sound effects created
- [ ] Music created
- [ ] Shop overlay text written
- [ ] Engine patches applied (names, moongates, food rate)
- [ ] Title screen text set
- [ ] `apply.sh` script written and tested
- [ ] Full verification pass completed
