#!/usr/bin/env bash
# =============================================================================
# [Your Conversion Name] — Total Conversion Script
# =============================================================================
#
# Transforms a vanilla Ultima III: Exodus into [your conversion].
#
# Usage: bash apply.sh /path/to/GAME/
#
# Requires: u3edit installed (pip install -e .), extracted ProDOS game files
# in the target directory.
#
# Copy this template and fill in each phase with your conversion's data.
# =============================================================================

set -euo pipefail

GAME_DIR="${1:?Usage: bash apply.sh /path/to/GAME/}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"
SOURCES_DIR="${SCRIPT_DIR}/sources"

echo "=== [Your Conversion Name] ==="
echo "Target: ${GAME_DIR}"
echo ""

# Find game files (handles ProDOS #hash suffixes)
find_file() {
    local pattern="${GAME_DIR}/$1"
    local match
    match=$(ls ${pattern}#* 2>/dev/null | head -1) || true
    if [ -z "$match" ]; then
        match="${GAME_DIR}/$1"
    fi
    echo "$match"
}

# =============================================================================
# Phase 1: ROSTER — Create your party
# =============================================================================
echo "--- Phase 1: Creating party roster ---"

ROST=$(find_file "ROST")

# Option A: Create characters via CLI
# u3edit roster create "$ROST" --slot 0 \
#     --name "HERO" --race H --class F --gender M \
#     --str 30 --dex 25 --hp 200 --gold 300 --backup
#
# u3edit roster edit "$ROST" --slot 0 --in-party --food 500

# Option B: Import from JSON
# u3edit roster import "$ROST" "${DATA_DIR}/party.json" --backup

echo "  TODO: Create party characters"

# =============================================================================
# Phase 2: SAVE STATE — Set starting position
# =============================================================================
echo "--- Phase 2: Setting save state ---"

# u3edit save edit "$GAME_DIR" \
#     --transport foot --x 28 --y 35 \
#     --sentinel 255 --location sosaria --backup

echo "  TODO: Set starting position"

# =============================================================================
# Phase 3: BESTIARY — Design monster encounters
# =============================================================================
echo "--- Phase 3: Configuring bestiary ---"

# Option A: Edit individual monsters
# MONA=$(find_file "MONA")
# u3edit bestiary edit "$MONA" --monster 0 --hp 60 --attack 35 --backup

# Option B: Import from JSON (create one JSON per encounter file)
# for letter in A B C D E F G H I J K L Z; do
#     MON=$(find_file "MON${letter}")
#     JSON="${SOURCES_DIR}/bestiary_${letter,,}.json"
#     if [ -f "$MON" ] && [ -f "$JSON" ]; then
#         u3edit bestiary import "$MON" "$JSON" --backup
#     fi
# done

echo "  TODO: Configure monster stats"

# =============================================================================
# Phase 4: COMBAT MAPS — Design battlefields
# =============================================================================
echo "--- Phase 4: Designing combat battlefields ---"

# Option A: Edit tiles individually
# CONG=$(find_file "CONG")
# u3edit combat edit "$CONG" --tile 5 5 0x84 --backup

# Option B: Import from JSON
# for letter in A B F G M Q R S; do
#     CON=$(find_file "CON${letter}")
#     JSON="${SOURCES_DIR}/combat_${letter,,}.json"
#     if [ -f "$CON" ] && [ -f "$JSON" ]; then
#         u3edit combat import "$CON" "$JSON" --backup
#     fi
# done

echo "  TODO: Design combat battlefields"

# =============================================================================
# Phase 5: MAPS — Design the world
# =============================================================================
echo "--- Phase 5: Building world maps ---"

# Option A: Edit tiles with CLI
# MAPA=$(find_file "MAPA")
# u3edit map fill "$MAPA" --x1 0 --y1 0 --x2 63 --y2 63 --tile 0x04 --backup
# u3edit map set "$MAPA" --x 30 --y 30 --tile 0x1C

# Option B: Compile from text-art sources and import
# for letter in A B C D E F G H I J K L Z; do
#     MAP=$(find_file "MAP${letter}")
#     SRC="${SOURCES_DIR}/map${letter,,}.map"
#     if [ -f "$MAP" ] && [ -f "$SRC" ]; then
#         python "${SCRIPT_DIR}/../tools/map_compiler.py" compile "$SRC" \
#             --output "/tmp/map${letter,,}.json"
#         u3edit map import "$MAP" "/tmp/map${letter,,}.json" --backup
#     fi
# done

# Dungeons (separate tile encoding)
# for letter in M N O P Q R S; do
#     MAP=$(find_file "MAP${letter}")
#     SRC="${SOURCES_DIR}/map${letter,,}.map"
#     if [ -f "$MAP" ] && [ -f "$SRC" ]; then
#         python "${SCRIPT_DIR}/../tools/map_compiler.py" compile "$SRC" \
#             --dungeon --output "/tmp/map${letter,,}.json"
#         u3edit map import "$MAP" "/tmp/map${letter,,}.json" --backup
#     fi
# done

echo "  TODO: Design world maps"

# =============================================================================
# Phase 6: SPECIAL LOCATIONS — Design shrines and fountains
# =============================================================================
echo "--- Phase 6: Modifying special locations ---"

# for name in BRND SHRN FNTN TIME; do
#     FILE=$(find_file "$name")
#     JSON="${SOURCES_DIR}/special_${name,,}.json"
#     if [ -f "$FILE" ] && [ -f "$JSON" ]; then
#         u3edit special import "$FILE" "$JSON" --backup
#     fi
# done

echo "  TODO: Design special locations"

# =============================================================================
# Phase 7: DIALOG — Write NPC conversations
# =============================================================================
echo "--- Phase 7: Writing NPC dialog ---"

# Option A: Find/replace across all files
# for letter in A B C D E F G H I J K L M N O P Q R S; do
#     TLK=$(find_file "TLK${letter}")
#     if [ -f "$TLK" ]; then
#         u3edit tlk edit "$TLK" --find "EXODUS" --replace "YOUR VILLAIN" \
#             --ignore-case --backup 2>/dev/null || true
#     fi
# done

# Option B: Build from text sources (full dialog rewrite)
# for letter in A B C D E F G H I J K L M N O P Q R S; do
#     TLK=$(find_file "TLK${letter}")
#     SRC="${SOURCES_DIR}/tlk${letter,,}.txt"
#     if [ -f "$TLK" ] && [ -f "$SRC" ]; then
#         u3edit tlk build "$SRC" "$TLK" --backup
#     fi
# done

echo "  TODO: Write NPC dialog"

# =============================================================================
# Phase 8: TILE GRAPHICS — Create custom tileset
# =============================================================================
echo "--- Phase 8: Applying tile graphics ---"

# SHPS=$(find_file "SHPS")

# Option A: Compile from text-art and import
# python "${SCRIPT_DIR}/../tools/tile_compiler.py" compile \
#     "${SOURCES_DIR}/tiles.tiles" --format json > /tmp/tiles.json
# u3edit shapes import "$SHPS" /tmp/tiles.json --backup

# Option B: Edit individual glyphs
# u3edit shapes edit "$SHPS" --glyph 0 --data "00 14 08 14 22 08 14 00" --backup

echo "  TODO: Create tile graphics"

# =============================================================================
# Phase 9: ENGINE PATCHES — Rename entities and configure
# =============================================================================
echo "--- Phase 9: Patching engine binary ---"

ULT3=$(find_file "ULT3")

# Apply name table
# NAMETABLE_HEX=$(python3 "${SCRIPT_DIR}/encode_nametable.py" "$ULT3")
# u3edit patch edit "$ULT3" --region name-table --data "$NAMETABLE_HEX" --backup

# Relocate moongates (8 X + 8 Y coordinates, hex bytes)
# u3edit patch edit "$ULT3" --region moongate-x --data "0A 14 1E 28 32 1E 14 0A"
# u3edit patch edit "$ULT3" --region moongate-y --data "0A 0A 0A 1E 32 32 32 1E"

# Adjust food depletion rate (default 04, higher = faster drain)
# u3edit patch edit "$ULT3" --region food-rate --data "04"

echo "  TODO: Apply engine patches"

# =============================================================================
# Phase 10: SHOP TEXT — Rewrite shop overlay strings
# =============================================================================
echo "--- Phase 10: Editing shop overlay text ---"

# Find available string offsets first:
# u3edit shapes view SHP0 --strings
# Then edit by offset:
# u3edit shapes edit-string "$SHP0" --offset 0x1A3 --text "YOUR SHOP TEXT"

echo "  TODO: Edit shop overlay strings"

# =============================================================================
# Phase 11: TITLE SCREEN
# =============================================================================
echo "--- Phase 11: Setting title text ---"

# TEXT=$(find_file "TEXT")
# u3edit text edit "$TEXT" --record 0 --text "YOUR GAME TITLE" --backup
# u3edit text edit "$TEXT" --record 1 --text "YOUR SUBTITLE"

echo "  TODO: Set title text"

# =============================================================================
# Verification (optional)
# =============================================================================

# Uncomment to verify after applying:
# python "${SCRIPT_DIR}/../tools/verify.py" "$GAME_DIR"

# =============================================================================
# Done
# =============================================================================
echo ""
echo "=== Conversion complete ==="
echo "All commands support --backup and --dry-run for safety."
