# Exodus: Voidborn

## Total Conversion Scenario for Ultima III: Exodus

**Theme**: Cosmic horror. An alien entity — the Voidborn — has torn through
the fabric of reality, corrupting the land of Sosaria into a nightmare realm.
Forests are now fungal growths, mountains are crystalline spires, and the
few surviving towns are desperate havens. The party must gather forbidden
relics and close the Void Rifts before reality collapses entirely.

---

## What Changes

| Layer | Scope | Method |
|-------|-------|--------|
| **Names** | All terrain, monster, weapon, armor, spell names | `patch edit --region name-table` |
| **Monsters** | Stats rebalanced, tougher encounters | `bestiary edit` / `bestiary import` |
| **Party** | 4 custom characters with themed names | `roster create` / `roster import` |
| **Dialog** | All NPC text rewritten for horror tone | `tlk edit --find/--replace` / `tlk build` |
| **Maps** | Overworld corrupted, towns redesigned | `map fill/replace/set` / `map import` |
| **Combat** | Battlefield layouts redesigned | `combat edit` / `combat import` |
| **Save** | Fresh start at new location | `save edit` / `save import` |
| **Text** | Title screen text rewritten | `text edit` |
| **Specials** | Shrines/fountains redesigned | `special edit` / `special import` |
| **Moongates** | Rift positions relocated | `patch edit --region moongate-x/y` |
| **Food rate** | Harsher survival (faster depletion) | `patch edit --region food-rate` |
| **Shop text** | Shop overlay strings rewritten | `shapes edit-string` |

## Renamed Entities

### Terrain
| Vanilla | Voidborn |
|---------|----------|
| Water | Brine |
| Grass | Ash |
| Brush | Thorns |
| Forest | Mycelium |
| Mountains | Spires |
| Dungeon | Abyss |
| Towne | Haven |
| Castle | Bastion |
| Moongate | Rift |
| Lava | Ichor |
| Force Field | Null Field |

### Monsters
| Vanilla | Voidborn | Notes |
|---------|----------|-------|
| Orc | Thrall | Mind-controlled husks |
| Skeleton | Husk | Desiccated shells |
| Giant | Brute | Mutated berserkers |
| Daemon | Horror | Void manifestations |
| Pincher | Lurker | Ambush predators |
| Dragon | Watcher | All-seeing sentinels |
| Balron | Abyssal | Deep void entities |
| Exodus | Voidborn | The alien entity itself |
| Brigand | Marauder | Desperate survivors |
| Goblin | Gremlin | Corrupted fey |
| Ghoul | Wraith | Spectral remnants |
| Zombie | Risen | Void-animated dead |

### Weapons
| Vanilla | Voidborn |
|---------|----------|
| Hands | Fist |
| Dagger | Shiv |
| Mace | Club |
| Sword | Blade |
| 2H Sword | Glaive |
| +2 variants | V- (Void-touched) |
| +4 variants | D- (Doom) |
| Exotic | Null |

### Armor
| Vanilla | Voidborn |
|---------|----------|
| Cloth | Rags |
| Leather | Hide |
| Chain | Links |
| +2 variants | V- (Void-warded) |
| Exotic | Ward |

### Spells
**Void Arts** (Wizard): Spark, Shard, Warp, Rend, Drain, Tear, Crush,
Scry, Blight, Scour, Toxin, Unmake, Shift, Rift, Annul

**Warding Rites** (Cleric): Mend, Glow, Ward, Shield, Slow, Rest, Heal,
Purge, Follow, Sleep, Bless, Guide, Banish, Cleanse, Veil, Restore

## The Party

| Slot | Name | Race | Class | Role |
|------|------|------|-------|------|
| 0 | KAEL | Human | Ranger | The Warden — scout and survivor |
| 1 | LYRA | Elf | Wizard | The Seer — void-touched oracle |
| 2 | THARN | Dwarf | Fighter | The Bulwark — unbreakable defender |
| 3 | MIRA | Bobbit | Thief | The Ghost — unseen infiltrator |

## How to Apply

```bash
cd conversions/voidborn/

# 1. Generate name-table hex (the one CLI gap)
python encode_nametable.py > nametable_hex.txt

# 2. Run the master conversion script
bash apply.sh /path/to/GAME/
```

Requires a directory of extracted Ultima III ProDOS files.

## Limitations

- **Data-only**: Cannot change game logic, spell effects, or combat mechanics
- **Same tile types**: Tiles are renamed but render with the same glyphs
- **Same monster sprites**: Monsters use existing sprite tiles (renamed only)
- **Name-table budget**: All names must fit within 921 bytes total
- **BLOAD DDRW tail**: The last ~25 bytes of the name-table contain a loader
  string and code fragment that must be preserved
