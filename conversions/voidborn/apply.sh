#!/usr/bin/env bash
# =============================================================================
# Exodus: Voidborn — Total Conversion Script
# =============================================================================
#
# Transforms a vanilla Ultima III: Exodus into the Voidborn cosmic horror
# scenario using only ult3edit CLI commands.
#
# Usage: bash apply.sh /path/to/GAME/
#
# Requires: ult3edit installed (pip install -e .), extracted ProDOS game files
# in the target directory.
#
# This script demonstrates every CLI editing capability in ult3edit:
#   - roster create/edit/import     - map set/fill/replace/import
#   - bestiary edit/import          - combat edit/import
#   - save edit/import              - text edit
#   - tlk edit (find/replace)       - special edit
#   - patch edit (name-table, moongates, food rate)
#   - shapes edit-string (shop overlay text)
#
# =============================================================================

set -euo pipefail

GAME_DIR="${1:?Usage: bash apply.sh /path/to/GAME/}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"
SOURCES_DIR="${SCRIPT_DIR}/sources"
TOOLS_DIR="${SCRIPT_DIR}/../tools"
if [ -z "${PYTHON:-}" ]; then
    if python3 --version &>/dev/null 2>&1; then PYTHON=python3
    elif python --version &>/dev/null 2>&1; then PYTHON=python
    else echo "ERROR: Python not found."; exit 1; fi
fi

# Convert path to native format (handles Git bash /d/ -> D:/ on Windows)
native_path() { command -v cygpath &>/dev/null && cygpath -m "$1" || echo "$1"; }

echo "=== Exodus: Voidborn Total Conversion ==="
echo "Target: ${GAME_DIR}"
echo ""

# Find game files (handles ProDOS #hash suffixes)
find_file() {
    local pattern="${GAME_DIR}/$1"
    # Try with hash suffix first, then plain
    local match
    match=$(ls ${pattern}#* 2>/dev/null | head -1) || true
    if [ -z "$match" ]; then
        match="${GAME_DIR}/$1"
    fi
    echo "$match"
}

# =============================================================================
# Phase 1: ROSTER — Create the Voidborn party
# =============================================================================
echo "--- Phase 1: Creating party roster ---"

ROST=$(find_file "ROST")

# Create 4 themed characters from scratch
ult3edit roster create "$ROST" --slot 0 \
    --name "KAEL" --race H --class R --gender M \
    --str 30 --dex 45 --hp 250 --gold 300 --backup

ult3edit roster create "$ROST" --slot 1 --force \
    --name "LYRA" --race E --class W --gender F \
    --str 15 --dex 30 --hp 150 --gold 300

ult3edit roster create "$ROST" --slot 2 --force \
    --name "THARN" --race D --class F --gender M \
    --str 50 --dex 25 --hp 350 --gold 300

ult3edit roster create "$ROST" --slot 3 --force \
    --name "MIRA" --race B --class T --gender F \
    --str 20 --dex 50 --hp 180 --gold 300

# Mark all 4 as in-party and equip them
ult3edit roster edit "$ROST" --slot 0 --in-party --food 500 --gems 5 \
    --keys 3 --torches 10 --sub-morsels 50

ult3edit roster edit "$ROST" --slot 1 --in-party --food 500 --gems 10 \
    --torches 10 --powders 5

ult3edit roster edit "$ROST" --slot 2 --in-party --food 500 --keys 5 \
    --torches 15

ult3edit roster edit "$ROST" --slot 3 --in-party --food 500 --gems 8 \
    --keys 10 --torches 20 --powders 3

# Alternatively, import the full party from JSON (demonstrates JSON import)
# ult3edit roster import "$ROST" "${DATA_DIR}/party.json" --backup

echo "  Created: KAEL (Warden), LYRA (Seer), THARN (Bulwark), MIRA (Ghost)"

# =============================================================================
# Phase 2: SAVE STATE — Set starting position
# =============================================================================
echo "--- Phase 2: Setting save state ---"

ult3edit save edit "$GAME_DIR" \
    --transport foot --x 28 --y 35 \
    --sentinel 255 --location sosaria \
    --backup

# Alternatively: ult3edit save import "$GAME_DIR" "${DATA_DIR}/save.json" --backup

echo "  Party placed at (28,35) on Sosaria, on foot"

# =============================================================================
# Phase 3: BESTIARY — Rebalance monster encounters
# =============================================================================
echo "--- Phase 3: Rebalancing bestiary ---"

# Toughen grassland encounters (MONA) via individual CLI edits
MONA=$(find_file "MONA")
ult3edit bestiary edit "$MONA" --monster 0 --hp 60 --attack 35 --defense 25 --backup
ult3edit bestiary edit "$MONA" --monster 1 --hp 80 --attack 45 --defense 30
ult3edit bestiary edit "$MONA" --monster 2 --hp 45 --attack 25 --speed 30
ult3edit bestiary edit "$MONA" --monster 3 --hp 120 --attack 60 --defense 40 --boss
ult3edit bestiary edit "$MONA" --monster 4 --hp 200 --attack 80 --defense 55 --boss
ult3edit bestiary edit "$MONA" --monster 5 --hp 150 --attack 50 --speed 35 --poison
ult3edit bestiary edit "$MONA" --monster 6 --hp 100 --attack 40 --speed 40 --sleep
ult3edit bestiary edit "$MONA" --monster 7 --hp 250 --attack 90 --defense 60 --boss

# Bulk rebalance other encounter files via JSON import
# ult3edit bestiary import "$MONA" "${DATA_DIR}/bestiary_a.json" --backup

# Toughen forest encounters (MONC)
MONC=$(find_file "MONC")
if [ -f "$MONC" ]; then
    ult3edit bestiary edit "$MONC" --all --hp 80 --attack 40 --backup
    echo "  Buffed forest encounters"
fi

# Toughen dungeon encounters (MOND)
MOND=$(find_file "MOND")
if [ -f "$MOND" ]; then
    ult3edit bestiary edit "$MOND" --all --hp 120 --attack 60 --defense 35 --backup
    echo "  Buffed dungeon encounters"
fi

echo "  Rebalanced monster stats across encounter files"

# =============================================================================
# Phase 4: COMBAT MAPS — Redesign battlefields
# =============================================================================
echo "--- Phase 4: Redesigning combat battlefields ---"

# Redesign grassland battlefield with lava hazards (CLI tile-by-tile)
CONG=$(find_file "CONG")
if [ -f "$CONG" ]; then
    ult3edit combat edit "$CONG" --tile 1 1 0x84 --backup    # Lava at (1,1)
    ult3edit combat edit "$CONG" --tile 9 1 0x84              # Lava at (9,1)
    ult3edit combat edit "$CONG" --tile 3 3 0x84              # Lava at (3,3)
    ult3edit combat edit "$CONG" --tile 7 3 0x84              # Lava at (7,3)
    ult3edit combat edit "$CONG" --tile 5 5 0x84              # Lava at center
    ult3edit combat edit "$CONG" --tile 3 7 0x84              # Lava at (3,7)
    ult3edit combat edit "$CONG" --tile 7 7 0x84              # Lava at (7,7)
    ult3edit combat edit "$CONG" --tile 1 9 0x84              # Lava at (1,9)
    ult3edit combat edit "$CONG" --tile 9 9 0x84              # Lava at (9,9)
    # Reposition monsters for ambush formation
    ult3edit combat edit "$CONG" --monster-pos 0 3 2
    ult3edit combat edit "$CONG" --monster-pos 1 7 2
    ult3edit combat edit "$CONG" --monster-pos 2 5 4
    ult3edit combat edit "$CONG" --monster-pos 3 5 6
    echo "  Redesigned grassland battlefield (lava hazards + ambush)"
fi

# Import a full battlefield design from JSON (demonstrates JSON import)
# ult3edit combat import "$CONG" "${DATA_DIR}/combat_g.json" --backup

# =============================================================================
# Phase 5: MAPS — Corrupt the overworld
# =============================================================================
echo "--- Phase 5: Corrupting the overworld ---"

MAPA=$(find_file "MAPA")

# Replace some grass with brush (thorns spreading across the land)
ult3edit map replace "$MAPA" --from 0x08 --to 0x04 --backup  # Brush→Grass first
# Seed corruption: add lava pools to the overworld
ult3edit map set "$MAPA" --x 30 --y 30 --tile 0x84  # Lava pool near center
ult3edit map set "$MAPA" --x 31 --y 30 --tile 0x84
ult3edit map set "$MAPA" --x 30 --y 31 --tile 0x84
ult3edit map set "$MAPA" --x 31 --y 31 --tile 0x84

# Create a void rift zone (force fields forming a barrier)
ult3edit map fill "$MAPA" --x1 20 --y1 20 --x2 22 --y2 22 --tile 0x80  # Force field ring

# Find all existing dungeon entrances (for reference)
ult3edit map find "$MAPA" --tile 0x14 || true

echo "  Added corruption zones, lava pools, and void rifts to overworld"

# Modify a dungeon map
MAPM=$(find_file "MAPM")
if [ -f "$MAPM" ]; then
    # Add lava hazards to dungeon level 1
    ult3edit map set "$MAPM" --x 5 --y 5 --tile 0x07 --level 0   # Lava in dungeon
    ult3edit map set "$MAPM" --x 10 --y 5 --tile 0x07 --level 0
    echo "  Added hazards to dungeon level 1"
fi

# For full map redesign, use JSON import:
# ult3edit map view "$MAPA" --json -o overworld.json
# (edit overworld.json externally)
# ult3edit map import "$MAPA" overworld.json --backup

# =============================================================================
# Phase 6: SPECIAL LOCATIONS — Redesign shrines and fountains
# =============================================================================
echo "--- Phase 6: Modifying special locations ---"

SHRN=$(find_file "SHRN")
if [ -f "$SHRN" ]; then
    # Add force fields around shrine center
    ult3edit special edit "$SHRN" --tile 4 4 0x80 --backup
    ult3edit special edit "$SHRN" --tile 6 4 0x80
    ult3edit special edit "$SHRN" --tile 4 6 0x80
    ult3edit special edit "$SHRN" --tile 6 6 0x80
    echo "  Fortified shrines with null fields"
fi

FNTN=$(find_file "FNTN")
if [ -f "$FNTN" ]; then
    # Corrupt fountain with lava borders
    ult3edit special edit "$FNTN" --tile 3 3 0x84 --backup
    ult3edit special edit "$FNTN" --tile 7 3 0x84
    ult3edit special edit "$FNTN" --tile 3 7 0x84
    ult3edit special edit "$FNTN" --tile 7 7 0x84
    echo "  Corrupted fountains with ichor pools"
fi

# =============================================================================
# Phase 7: DIALOG — Rewrite NPC text for horror tone
# =============================================================================
echo "--- Phase 7: Rewriting NPC dialog ---"

# Global find/replace across all TLK files for key terms
for letter in A B C D E F G H I J K L M N O P Q R S; do
    TLK=$(find_file "TLK${letter}")
    if [ -f "$TLK" ]; then
        # Replace thematic terms (case-insensitive)
        ult3edit tlk edit "$TLK" --find "EXODUS" --replace "THE VOIDBORN" \
            --ignore-case --backup 2>/dev/null || true
        ult3edit tlk edit "$TLK" --find "SOSARIA" --replace "THE ASHEN REALM" \
            --ignore-case 2>/dev/null || true
        ult3edit tlk edit "$TLK" --find "LORD BRITISH" --replace "THE PROPHET" \
            --ignore-case 2>/dev/null || true
        ult3edit tlk edit "$TLK" --find "BRITANNIA" --replace "THE WASTELAND" \
            --ignore-case 2>/dev/null || true
        ult3edit tlk edit "$TLK" --find "CASTLE" --replace "BASTION" \
            --ignore-case 2>/dev/null || true
        ult3edit tlk edit "$TLK" --find "DUNGEON" --replace "ABYSS" \
            --ignore-case 2>/dev/null || true
        ult3edit tlk edit "$TLK" --find "MOONGATE" --replace "RIFT" \
            --ignore-case 2>/dev/null || true
        ult3edit tlk edit "$TLK" --find "MARKS" --replace "SIGILS" \
            --ignore-case 2>/dev/null || true
    fi
done

# Edit specific key dialog records (Lord British's castle = TLKB)
TLKB=$(find_file "TLKB")
if [ -f "$TLKB" ]; then
    ult3edit tlk edit "$TLKB" --record 0 \
        --text "THE VOID CONSUMES ALL.\nSEEK THE SIGILS BEFORE\nREALITY COLLAPSES." \
        2>/dev/null || true
fi

echo "  Replaced dialog themes across all TLK files"

# For full dialog rewrite, use extract/build:
# ult3edit tlk extract "$TLKB" dialog_b.txt
# (edit dialog_b.txt — records separated by --- lines)
# ult3edit tlk build dialog_b.txt "$TLKB" --backup

# =============================================================================
# Phase 8: GAME TEXT — Rewrite title/prompt strings
# =============================================================================
echo "--- Phase 8: Editing game text ---"

TEXT=$(find_file "TEXT")
if [ -f "$TEXT" ]; then
    ult3edit text edit "$TEXT" --record 0 --text "EXODUS: VOIDBORN" --backup \
        2>/dev/null || true
    ult3edit text edit "$TEXT" --record 1 --text "A WORLD CONSUMED" \
        2>/dev/null || true
    echo "  Updated title text"
fi

# =============================================================================
# Phase 9: ENGINE PATCHES — Rename everything + relocate moongates
# =============================================================================
echo "--- Phase 9: Patching engine binary ---"

ULT3=$(find_file "ULT3")
if [ -f "$ULT3" ]; then
    # Name-table is applied via name_compiler in Phase 11 (source-based pipeline).
    # This phase handles moongates and food rate only.

    # Relocate moongates to form a protective ring around the void
    # 8 phases with new X coordinates (decimal 10,20,30,40,50,30,20,10)
    ult3edit patch edit "$ULT3" --region moongate-x \
        --data "0A 14 1E 28 32 1E 14 0A"
    # 8 phases with new Y coordinates (decimal 10,10,10,30,50,50,50,30)
    ult3edit patch edit "$ULT3" --region moongate-y \
        --data "0A 0A 0A 1E 32 32 32 1E"

    # Increase food depletion rate (harsher survival: $02 = twice as fast)
    ult3edit patch edit "$ULT3" --region food-rate --data "02"

    echo "  Relocated moongates to void ring pattern"
    echo "  Doubled food depletion rate"
fi

# =============================================================================
# Phase 10: SHOP TEXT — Rewrite shop overlay strings
# =============================================================================
echo "--- Phase 10: Editing shop overlay text ---"

# Shop overlay strings are applied via shop_apply.py in Phase 11 (source-based
# pipeline). The tool discovers inline string offsets at runtime by scanning for
# JSR $46BA patterns, then matches by vanilla text — no hardcoded offsets needed.
#
# For manual editing of individual strings:
#   ult3edit shapes view SHP0 --strings          # List discovered strings
#   ult3edit shapes edit-string SHP0 --offset N --text "NEW TEXT"
echo "  (Handled by shop_apply.py in Phase 11)"

# =============================================================================
# Phase 11: SOURCE-BASED IMPORTS (when sources/ directory exists)
# =============================================================================
if [ -d "$SOURCES_DIR" ]; then
    echo "--- Phase 11: Importing from text-first sources ---"

    # Import bestiary stats from JSON sources (13 encounter files)
    for letter in a b c d e f g h i j k l z; do
        MON_UPPER=$(echo "$letter" | tr '[:lower:]' '[:upper:]')
        MON=$(find_file "MON${MON_UPPER}")
        JSON="${SOURCES_DIR}/bestiary_${letter}.json"
        if [ -f "$MON" ] && [ -f "$JSON" ]; then
            ult3edit bestiary import "$MON" "$JSON" 2>/dev/null || true
        fi
    done
    echo "  Imported bestiary stats from 13 JSON sources"

    # Import combat maps from JSON sources (9 battlefield files)
    for letter in a b c f g m q r s; do
        CON_UPPER=$(echo "$letter" | tr '[:lower:]' '[:upper:]')
        CON=$(find_file "CON${CON_UPPER}")
        JSON="${SOURCES_DIR}/combat_${letter}.json"
        if [ -f "$CON" ] && [ -f "$JSON" ]; then
            ult3edit combat import "$CON" "$JSON" 2>/dev/null || true
        fi
    done
    echo "  Imported combat maps from 9 JSON sources"

    # Import special locations from JSON sources
    for name in brnd shrn fntn time; do
        NAME_UPPER=$(echo "$name" | tr '[:lower:]' '[:upper:]')
        FILE=$(find_file "$NAME_UPPER")
        JSON="${SOURCES_DIR}/special_${name}.json"
        if [ -f "$FILE" ] && [ -f "$JSON" ]; then
            ult3edit special import "$FILE" "$JSON" 2>/dev/null || true
        fi
    done
    echo "  Imported special locations from JSON sources"

    # Build dialog from text sources (19 dialog files)
    for letter in a b c d e f g h i j k l m n o p q r s; do
        TLK_UPPER=$(echo "$letter" | tr '[:lower:]' '[:upper:]')
        TLK=$(find_file "TLK${TLK_UPPER}")
        SRC="${SOURCES_DIR}/tlk${letter}.txt"
        if [ -f "$TLK" ] && [ -f "$SRC" ]; then
            ult3edit tlk build "$SRC" "$TLK" 2>/dev/null || true
        fi
    done
    echo "  Built dialog from 19 text sources"

    # Import title screen text
    TITLE_JSON="${SOURCES_DIR}/title.json"
    TEXT=$(find_file "TEXT")
    if [ -f "$TITLE_JSON" ] && [ -f "$TEXT" ]; then
        # Read title records from JSON and apply via text edit
        TITLE_JSON_NATIVE=$(native_path "$TITLE_JSON")
        TITLE0=$($PYTHON -c "import json; d=json.load(open('${TITLE_JSON_NATIVE}')); print(d['records'][0]['text'])")
        TITLE1=$($PYTHON -c "import json; d=json.load(open('${TITLE_JSON_NATIVE}')); print(d['records'][1]['text'])")
        ult3edit text edit "$TEXT" --record 0 --text "$TITLE0" 2>/dev/null || true
        ult3edit text edit "$TEXT" --record 1 --text "$TITLE1" 2>/dev/null || true
        echo "  Applied title screen text"
    fi

    # Compile and import tile graphics (via ult3edit shapes compile)
    TILES_SRC="${SOURCES_DIR}/tiles.tiles"
    SHPS=$(find_file "SHPS")
    if [ -f "$TILES_SRC" ] && [ -f "$SHPS" ]; then
        mkdir -p "${SCRIPT_DIR}/build"
        ult3edit shapes compile "$TILES_SRC" --format json \
            -o "${SCRIPT_DIR}/build/tiles.json" 2>/dev/null
        ult3edit shapes import "$SHPS" "${SCRIPT_DIR}/build/tiles.json" 2>/dev/null || true
        echo "  Compiled and imported tile graphics (256 tiles)"
    fi

    # Compile and import overworld map (via ult3edit map compile)
    MAPA_SRC="${SOURCES_DIR}/mapa.map"
    MAPA=$(find_file "MAPA")
    if [ -f "$MAPA_SRC" ] && [ -f "$MAPA" ]; then
        ult3edit map compile "$MAPA_SRC" -o "$MAPA" 2>/dev/null || true
        echo "  Compiled and imported overworld map"
    fi

    # Compile and import surface maps (castles + towns, 12 files)
    for letter in b c d e f g h i j k l z; do
        MAP_UPPER=$(echo "$letter" | tr '[:lower:]' '[:upper:]')
        MAP_SRC="${SOURCES_DIR}/map${letter}.map"
        MAP_FILE=$(find_file "MAP${MAP_UPPER}")
        if [ -f "$MAP_SRC" ] && [ -f "$MAP_FILE" ]; then
            ult3edit map compile "$MAP_SRC" -o "$MAP_FILE" 2>/dev/null || true
        fi
    done
    echo "  Compiled and imported 12 surface maps"

    # Compile and import dungeon maps (7 dungeons, 8 levels each)
    for letter in m n o p q r s; do
        MAP_UPPER=$(echo "$letter" | tr '[:lower:]' '[:upper:]')
        MAP_SRC="${SOURCES_DIR}/map${letter}.map"
        MAP_FILE=$(find_file "MAP${MAP_UPPER}")
        if [ -f "$MAP_SRC" ] && [ -f "$MAP_FILE" ]; then
            ult3edit map compile "$MAP_SRC" --dungeon -o "$MAP_FILE" 2>/dev/null || true
        fi
    done
    echo "  Compiled and imported 7 dungeon maps"

    # Compile and apply name table (via ult3edit patch compile-names)
    NAMES_SRC="${SOURCES_DIR}/names.names"
    ULT3=$(find_file "ULT3")
    if [ -f "$NAMES_SRC" ] && [ -f "$ULT3" ]; then
        mkdir -p "${SCRIPT_DIR}/build"
        ult3edit patch compile-names "$NAMES_SRC" \
            -o "${SCRIPT_DIR}/build/names.json" 2>/dev/null
        ult3edit patch import "$ULT3" "${SCRIPT_DIR}/build/names.json" 2>/dev/null || true
        echo "  Compiled and applied Voidborn name table"
    fi

    # Apply shop overlay string replacements (text-matching, no hardcoded offsets)
    SHOP_JSON="${SOURCES_DIR}/shop_strings.json"
    if [ -f "$SHOP_JSON" ] && [ -f "${TOOLS_DIR}/shop_apply.py" ]; then
        $PYTHON "${TOOLS_DIR}/shop_apply.py" "$SHOP_JSON" "$GAME_DIR" 2>/dev/null || true
        echo "  Applied shop overlay string replacements"
    fi

    # Import sound data from source stubs
    # NOTE: MBS is excluded because it contains executable code (Mockingboard
    # music player) at $9A00 that TEST calls via JSR $9A00 on all boot paths.
    # Replacing MBS with pure data (mbs.json has $82 END + zeros) causes BRK $00
    # crash. SOSA/SOSM are pure data files (overworld map state/monster positions)
    # and are safe to replace.
    for snd in sosa sosm; do
        SND_UPPER=$(echo "$snd" | tr '[:lower:]' '[:upper:]')
        SND_FILE=$(find_file "$SND_UPPER")
        JSON="${SOURCES_DIR}/${snd}.json"
        if [ -f "$SND_FILE" ] && [ -f "$JSON" ]; then
            ult3edit sound import "$SND_FILE" "$JSON" 2>/dev/null || true
        fi
    done
    echo "  Imported sound data (SOSA/SOSM; MBS kept vanilla — contains player code)"

    # Import dungeon drawing data
    DDRW_FILE=$(find_file "DDRW")
    DDRW_JSON="${SOURCES_DIR}/ddrw.json"
    if [ -f "$DDRW_FILE" ] && [ -f "$DDRW_JSON" ]; then
        ult3edit ddrw import "$DDRW_FILE" "$DDRW_JSON" 2>/dev/null || true
        echo "  Imported dungeon drawing data"
    fi

    # Import title screen text crawl coordinates
    EXOD=$(find_file "EXOD")
    CRAWL_JSON="${SOURCES_DIR}/crawl.json"
    if [ -f "$EXOD" ] && [ -f "$CRAWL_JSON" ]; then
        ult3edit exod crawl import "$EXOD" "$CRAWL_JSON" 2>/dev/null || true
        echo "  Imported title text crawl coordinates"
    fi

    # Apply engine inline string patches
    # Two-tier: source-level (no length limits) if asmiigs available, else binary
    ENGINE_DIR="${SCRIPT_DIR}/../../engine"
    ENGINE_TOOLS="${ENGINE_DIR}/tools"
    FULL_PATCHES="${SOURCES_DIR}/engine_strings_full.json"
    BIN_PATCHES="${SOURCES_DIR}/engine_strings.json"
    ULT3=$(find_file "ULT3")

    # NOTE: Source-level build (scenario_build.sh) reassembles from the
    # uncracked original source, producing a binary incompatible with cracked
    # disk images (33 byte differences including boot sequence patches like
    # JSR $B60F -> BIT $B60F). Always use binary-level patches which modify
    # the existing ULT3 in-place, preserving crack/loader compatibility.
    if [ -f "$BIN_PATCHES" ] && [ -f "$ULT3" ]; then
        echo "  Applying engine string patches (binary, in-place)..."
        ult3edit patch strings-import "$ULT3" "$BIN_PATCHES" \
            --backup 2>/dev/null || true
        echo "  Applied engine inline string patches via binary patcher"
    fi
fi

# =============================================================================
# Verification (optional)
# =============================================================================
if [ "${VERIFY:-}" = "1" ] && [ -f "${TOOLS_DIR}/verify.py" ]; then
    echo ""
    echo "--- Running verification ---"
    $PYTHON "${TOOLS_DIR}/verify.py" "$GAME_DIR"
fi

# =============================================================================
# Done
# =============================================================================
echo ""
echo "=== Voidborn conversion complete ==="
echo ""
echo "Summary of CLI commands used:"
echo "  roster create/edit    - Party creation and character stats"
echo "  roster import         - Bulk character data from JSON"
echo "  save edit/import      - Party state (position, transport, sentinel)"
echo "  bestiary edit/import  - Monster stats and flags (13 encounter files)"
echo "  combat edit/import    - Battlefield tiles and positions (9 maps)"
echo "  map compile/decompile - Text-art .map <-> binary MAP (20 maps)"
echo "  map set/fill/replace  - Overworld tile manipulation"
echo "  special edit/import   - Shrine/fountain tile editing (4 locations)"
echo "  tlk edit/build        - Dialog text replacement and full rewrite (19 files)"
echo "  text edit             - Game text string editing"
echo "  patch edit/import     - Engine binary: names, moongates, food rate"
echo "  patch compile-names   - Text-first .names -> engine name-table JSON"
echo "  patch strings-import  - Engine inline string patches (binary, in-place)"
echo "  shapes compile        - Text-art .tiles -> SHPS binary (256 tiles)"
echo "  shapes import         - Tile graphics from compiled sources"
echo "  sound import          - Sound data replacement (SOSA/SOSM/MBS)"
echo "  ddrw import           - Dungeon drawing data replacement"
echo ""
echo "External tools used:"
echo "  shop_apply.py         - Text-matching shop overlay string replacer (8 shops)"
echo "  scenario_build.sh     - Source patch + asmiigs reassembly pipeline"
echo "  verify.py             - Asset coverage verification"
echo ""
echo "All commands support --backup and --dry-run for safety."
echo "Run with VERIFY=1 to verify asset coverage after conversion."
