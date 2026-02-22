#!/usr/bin/env bash
# =============================================================================
# Voidborn Disk Image Builder
# =============================================================================
#
# Builds a complete Voidborn total conversion disk image from a vanilla
# Ultima III: Exodus ProDOS disk image.
#
# Usage: bash build_disk.sh <vanilla.po> [output.po]
#
# Requires:
#   - ult3edit installed (pip install -e .)
#   - asmiigs on PATH (optional, for source-level engine string patching)
#
# =============================================================================

set -euo pipefail

VANILLA="${1:?Usage: bash build_disk.sh <vanilla.po> [output.po]}"
OUTPUT="${2:-voidborn.po}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Validate prerequisites ---

if [ ! -f "$VANILLA" ]; then
    echo "ERROR: Vanilla disk image not found: $VANILLA"
    exit 1
fi

if ! command -v ult3edit &>/dev/null; then
    echo "ERROR: ult3edit not found. Run: pip install -e ."
    exit 1
fi

if [ -z "${PYTHON:-}" ]; then
    if python3 --version &>/dev/null 2>&1; then PYTHON=python3
    elif python --version &>/dev/null 2>&1; then PYTHON=python
    else echo "ERROR: Python not found."; exit 1; fi
fi

echo "=== Voidborn Disk Image Builder ==="
echo "Vanilla: $VANILLA"
echo "Output:  $OUTPUT"
echo ""

# --- Step 1: Extract vanilla files ---

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
GAME_DIR="$TMPDIR/game"
mkdir -p "$GAME_DIR"

echo "--- Extracting vanilla game files ---"

# Use Python ProDOS parser to extract (handles non-standard image sizes)
$PYTHON -c "
import os, sys

IMAGE = sys.argv[1]
OUTDIR = sys.argv[2]

with open(IMAGE, 'rb') as f:
    disk = f.read()

def read_block(blk):
    return disk[blk*512:(blk+1)*512]

def read_file_data(key_block, storage_type, eof):
    if storage_type == 1:
        return read_block(key_block)[:eof]
    elif storage_type == 2:
        idx = read_block(key_block)
        data = bytearray()
        for i in range(256):
            blk = idx[i] | (idx[256+i] << 8)
            if blk == 0: break
            data.extend(read_block(blk))
        return bytes(data[:eof])
    elif storage_type == 3:
        master = read_block(key_block)
        data = bytearray()
        for j in range(256):
            idx_blk = master[j] | (master[256+j] << 8)
            if idx_blk == 0: break
            idx = read_block(idx_blk)
            for i in range(256):
                blk = idx[i] | (idx[256+i] << 8)
                if blk == 0: break
                data.extend(read_block(blk))
        return bytes(data[:eof])
    return b''

def parse_dir_blocks(first_block):
    files = []
    blk_num = first_block
    first = True
    while blk_num > 0:
        blk = read_block(blk_num)
        next_blk = blk[2] | (blk[3] << 8)
        for i in range(13):
            offset = 4 + i * 0x27
            if offset + 0x27 > 512: break
            stype = blk[offset] >> 4
            nlen = blk[offset] & 0x0F
            if i == 0 and first: first = False; continue
            if stype == 0 or nlen == 0: continue
            name = blk[offset+1:offset+1+nlen].decode('ascii', errors='replace')
            ftype = blk[offset+0x10]
            key = blk[offset+0x11] | (blk[offset+0x12] << 8)
            eof = blk[offset+0x15] | (blk[offset+0x16] << 8) | (blk[offset+0x17] << 16)
            aux = blk[offset+0x1F] | (blk[offset+0x20] << 8)
            files.append((name, ftype, key, stype, eof, aux))
        blk_num = next_blk
    return files

count = 0
root_files = parse_dir_blocks(2)
for name, ftype, key, stype, eof, aux in root_files:
    if stype == 0xD:
        sub_files = parse_dir_blocks(key)
        for sname, sftype, skey, sstype, seof, saux in sub_files:
            if sstype == 0xD: continue
            fname = f'{sname}#{sftype:02X}{saux:04X}'
            data = read_file_data(skey, sstype, seof)
            with open(os.path.join(OUTDIR, fname), 'wb') as out:
                out.write(data)
            count += 1
    else:
        fname = f'{name}#{ftype:02X}{aux:04X}'
        data = read_file_data(key, stype, eof)
        with open(os.path.join(OUTDIR, fname), 'wb') as out:
            out.write(data)
        count += 1

print(f'    Extracted {count} files')
" "$VANILLA" "$GAME_DIR"

# --- Step 2: Apply Voidborn conversion ---

echo "--- Applying Voidborn conversion ---"
echo ""
bash "$SCRIPT_DIR/apply.sh" "$GAME_DIR"
echo ""

# --- Step 3: Build output disk image ---

echo "--- Building disk image ---"

# Build a correct ProDOS disk image using Python (no external tools needed).
# diskiigs creates non-standard volume headers, so we write standard ProDOS
# format directly.

$PYTHON -c "
import os, sys, struct, math

VANILLA = sys.argv[1]
GAME_DIR = sys.argv[2]
OUTPUT = sys.argv[3]

# --- Configuration ---
TOTAL_BLOCKS = 1600  # 800K (3.5\" disk)
BLOCK_SIZE = 512
ENTRY_LENGTH = 0x27  # 39 bytes per directory entry
ENTRIES_PER_BLOCK = 0x0D  # 13 entries per block (first entry = header)
VOL_NAME = b'ULTIMA3'

# --- Read boot blocks from vanilla ---
with open(VANILLA, 'rb') as f:
    boot_blocks = f.read(1024)

# --- Collect files to add ---
root_files = []  # (prodos_name, file_type, aux_type, data)
game_files = []

for fname in sorted(os.listdir(GAME_DIR)):
    fpath = os.path.join(GAME_DIR, fname)
    if not os.path.isfile(fpath) or fname.endswith('.bak'):
        continue
    if '#' not in fname:
        continue
    prodos_name = fname.split('#')[0]
    suffix = fname.split('#')[1]
    file_type = int(suffix[:2], 16)
    aux_type = int(suffix[2:6], 16)
    with open(fpath, 'rb') as f:
        data = f.read()
    if prodos_name in ('PRODOS', 'LOADER.SYSTEM', 'U3'):
        root_files.append((prodos_name, file_type, aux_type, data))
    else:
        game_files.append((prodos_name, file_type, aux_type, data))

# --- Initialize disk image ---
disk = bytearray(TOTAL_BLOCKS * BLOCK_SIZE)

# Write boot blocks from vanilla
disk[0:len(boot_blocks)] = boot_blocks

# --- Block allocator ---
# Blocks 0-1: boot, 2-5: volume directory (4 blocks),
# 6: volume bitmap, 7+: available
bitmap_block = 6
vol_dir_blocks = [2, 3, 4, 5]
next_free = 7  # first allocatable block

def alloc_block():
    global next_free
    if next_free >= TOTAL_BLOCKS:
        raise RuntimeError('Disk full')
    blk = next_free
    next_free += 1
    return blk

# Pre-allocate GAME subdirectory blocks (need enough for 96+ entries)
# Each block holds 12 file entries (13 - 1 header/continuation)
game_dir_block_count = max(1, math.ceil((len(game_files) + 1) / 12))
game_dir_blocks = [alloc_block() for _ in range(game_dir_block_count)]

def write_block(blk_num, data):
    offset = blk_num * BLOCK_SIZE
    disk[offset:offset + len(data)] = data

# --- Write file data blocks, return (key_block, storage_type, blocks_used) ---
def write_file(data):
    eof = len(data)
    if eof == 0:
        # Empty file: seedling with no data block
        blk = alloc_block()
        return blk, 1, 1
    data_blocks_needed = math.ceil(eof / BLOCK_SIZE)
    if data_blocks_needed == 1:
        # Seedling: single data block
        blk = alloc_block()
        padded = data + b'\\x00' * (BLOCK_SIZE - len(data))
        write_block(blk, padded)
        return blk, 1, 1
    elif data_blocks_needed <= 256:
        # Sapling: index block + data blocks
        idx_blk = alloc_block()
        data_blks = []
        for i in range(data_blocks_needed):
            dblk = alloc_block()
            chunk = data[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE]
            if len(chunk) < BLOCK_SIZE:
                chunk = chunk + b'\\x00' * (BLOCK_SIZE - len(chunk))
            write_block(dblk, chunk)
            data_blks.append(dblk)
        # Build index block: low bytes at 0-255, high bytes at 256-511
        idx = bytearray(BLOCK_SIZE)
        for i, dblk in enumerate(data_blks):
            idx[i] = dblk & 0xFF
            idx[256 + i] = (dblk >> 8) & 0xFF
        write_block(idx_blk, idx)
        return idx_blk, 2, 1 + data_blocks_needed
    else:
        # Tree: master index + index blocks + data blocks
        master_blk = alloc_block()
        idx_blks = []
        total_written = 0
        remaining = data_blocks_needed
        while remaining > 0:
            chunk_count = min(256, remaining)
            idx_blk = alloc_block()
            data_blks = []
            for i in range(chunk_count):
                dblk = alloc_block()
                start = total_written * BLOCK_SIZE
                chunk = data[start:start+BLOCK_SIZE]
                if len(chunk) < BLOCK_SIZE:
                    chunk = chunk + b'\\x00' * (BLOCK_SIZE - len(chunk))
                write_block(dblk, chunk)
                data_blks.append(dblk)
                total_written += 1
            idx = bytearray(BLOCK_SIZE)
            for i, dblk in enumerate(data_blks):
                idx[i] = dblk & 0xFF
                idx[256 + i] = (dblk >> 8) & 0xFF
            write_block(idx_blk, idx)
            idx_blks.append(idx_blk)
            remaining -= chunk_count
        master = bytearray(BLOCK_SIZE)
        for i, iblk in enumerate(idx_blks):
            master[i] = iblk & 0xFF
            master[256 + i] = (iblk >> 8) & 0xFF
        write_block(master_blk, master)
        return master_blk, 3, 1 + len(idx_blks) + data_blocks_needed

# --- Build directory entry ---
def make_entry(storage_type, name, file_type, key_block, blocks_used, eof, aux_type):
    entry = bytearray(ENTRY_LENGTH)
    name_bytes = name.encode('ascii')[:15]
    entry[0x00] = (storage_type << 4) | len(name_bytes)
    entry[0x01:0x01+len(name_bytes)] = name_bytes
    entry[0x10] = file_type
    entry[0x11] = key_block & 0xFF
    entry[0x12] = (key_block >> 8) & 0xFF
    entry[0x13] = blocks_used & 0xFF
    entry[0x14] = (blocks_used >> 8) & 0xFF
    entry[0x15] = eof & 0xFF
    entry[0x16] = (eof >> 8) & 0xFF
    entry[0x17] = (eof >> 16) & 0xFF
    entry[0x1E] = 0xE3  # access: read/write/rename/destroy
    entry[0x1F] = aux_type & 0xFF
    entry[0x20] = (aux_type >> 8) & 0xFF
    return entry

# --- Write all file data ---
file_records = []  # (prodos_name, file_type, aux_type, key_block, storage_type, blocks_used, eof, is_root)

# Write root files first — PRODOS must be earliest on disk (boot code loads it)
prodos_order = {'PRODOS': 0, 'LOADER.SYSTEM': 1}
root_files.sort(key=lambda r: (prodos_order.get(r[0], 99), r[0]))
for prodos_name, file_type, aux_type, data in root_files:
    key_block, storage_type, blocks_used = write_file(data)
    file_records.append((prodos_name, file_type, aux_type, key_block, storage_type, blocks_used, len(data), True))

for prodos_name, file_type, aux_type, data in game_files:
    key_block, storage_type, blocks_used = write_file(data)
    file_records.append((prodos_name, file_type, aux_type, key_block, storage_type, blocks_used, len(data), False))

# --- Build GAME subdirectory ---
# Link the directory blocks
for i, blk in enumerate(game_dir_blocks):
    prev_blk = game_dir_blocks[i-1] if i > 0 else 0
    next_blk = game_dir_blocks[i+1] if i < len(game_dir_blocks) - 1 else 0
    block_data = bytearray(BLOCK_SIZE)
    block_data[0] = prev_blk & 0xFF
    block_data[1] = (prev_blk >> 8) & 0xFF
    block_data[2] = next_blk & 0xFF
    block_data[3] = (next_blk >> 8) & 0xFF

    if i == 0:
        # Subdirectory header (first entry of first block)
        hdr = bytearray(ENTRY_LENGTH)
        name_bytes = b'GAME'
        hdr[0x00] = (0x0E << 4) | len(name_bytes)  # 0xE = subdirectory header
        hdr[0x01:0x01+len(name_bytes)] = name_bytes
        hdr[0x1C] = 0x00  # version
        hdr[0x1D] = 0x00  # min_version
        hdr[0x1E] = 0xE3  # access
        hdr[0x1F] = ENTRY_LENGTH
        hdr[0x20] = ENTRIES_PER_BLOCK
        game_file_count = len([r for r in file_records if not r[7]])
        hdr[0x21] = game_file_count & 0xFF
        hdr[0x22] = (game_file_count >> 8) & 0xFF
        # Parent pointer (volume directory key block) and parent entry number
        hdr[0x23] = vol_dir_blocks[0] & 0xFF  # parent block
        hdr[0x24] = (vol_dir_blocks[0] >> 8) & 0xFF
        # parent entry number will be set after we know the GAME entry position
        hdr[0x25] = 0x01  # placeholder, fixed below
        hdr[0x26] = ENTRY_LENGTH  # parent entry length
        block_data[4:4+ENTRY_LENGTH] = hdr

    # Fill file entries
    entry_slot = 1 if i == 0 else 0
    file_idx = i * 12 + (0 if i == 0 else -1 + 12)  # adjust for header in first block
    if i == 0:
        file_idx = 0
    else:
        file_idx = 12 + (i - 1) * 13  # first block: 12 files, subsequent: 13

    game_entries = [r for r in file_records if not r[7]]
    for slot in range(entry_slot, 13):
        if file_idx >= len(game_entries):
            break
        rec = game_entries[file_idx]
        name, ftype, aux, key, stype, blks, eof, _ = rec
        entry = make_entry(stype, name, ftype, key, blks, eof, aux)
        offset = 4 + slot * ENTRY_LENGTH
        block_data[offset:offset+ENTRY_LENGTH] = entry
        file_idx += 1

    write_block(blk, block_data)

# --- Build volume directory ---
# Root directory entries — PRODOS must be first (boot code expects it)
# Vanilla order: PRODOS, LOADER.SYSTEM, U3, GAME
root_entries = []

# Root file entries first (PRODOS, then others)
root_recs = [r for r in file_records if r[7]]
# Sort: PRODOS first, then LOADER.SYSTEM, then alphabetical
prodos_order = {'PRODOS': 0, 'LOADER.SYSTEM': 1}
root_recs.sort(key=lambda r: (prodos_order.get(r[0], 99), r[0]))
for rec in root_recs:
    name, ftype, aux, key, stype, blks, eof, _ = rec
    entry = make_entry(stype, name, ftype, key, blks, eof, aux)
    root_entries.append(entry)

# GAME subdirectory entry last
game_entry = bytearray(ENTRY_LENGTH)
name_bytes = b'GAME'
game_entry[0x00] = (0x0D << 4) | len(name_bytes)  # 0xD = directory file
game_entry[0x01:0x01+len(name_bytes)] = name_bytes
game_entry[0x10] = 0x0F  # file type = directory
game_entry[0x11] = game_dir_blocks[0] & 0xFF
game_entry[0x12] = (game_dir_blocks[0] >> 8) & 0xFF
game_total_blocks = len(game_dir_blocks)
game_entry[0x13] = game_total_blocks & 0xFF
game_entry[0x14] = (game_total_blocks >> 8) & 0xFF
game_entry[0x15] = (len(game_dir_blocks) * BLOCK_SIZE) & 0xFF
game_entry[0x16] = ((len(game_dir_blocks) * BLOCK_SIZE) >> 8) & 0xFF
game_entry[0x17] = ((len(game_dir_blocks) * BLOCK_SIZE) >> 16) & 0xFF
game_entry[0x1E] = 0xE3  # access
root_entries.append(game_entry)

root_file_count = len(root_entries)

# Write volume directory blocks
for i, blk in enumerate(vol_dir_blocks):
    prev_blk = vol_dir_blocks[i-1] if i > 0 else 0
    next_blk = vol_dir_blocks[i+1] if i < len(vol_dir_blocks) - 1 else 0
    block_data = bytearray(BLOCK_SIZE)
    block_data[0] = prev_blk & 0xFF
    block_data[1] = (prev_blk >> 8) & 0xFF
    block_data[2] = next_blk & 0xFF
    block_data[3] = (next_blk >> 8) & 0xFF

    if i == 0:
        # Volume directory header (first entry of first block)
        hdr = bytearray(ENTRY_LENGTH)
        hdr[0x00] = (0x0F << 4) | len(VOL_NAME)  # 0xF = volume header
        hdr[0x01:0x01+len(VOL_NAME)] = VOL_NAME
        hdr[0x1C] = 0x00  # version
        hdr[0x1D] = 0x00  # min_version
        hdr[0x1E] = 0xE3  # access
        hdr[0x1F] = ENTRY_LENGTH
        hdr[0x20] = ENTRIES_PER_BLOCK
        hdr[0x21] = root_file_count & 0xFF
        hdr[0x22] = (root_file_count >> 8) & 0xFF
        hdr[0x23] = bitmap_block & 0xFF
        hdr[0x24] = (bitmap_block >> 8) & 0xFF
        hdr[0x25] = TOTAL_BLOCKS & 0xFF
        hdr[0x26] = (TOTAL_BLOCKS >> 8) & 0xFF
        block_data[4:4+ENTRY_LENGTH] = hdr

    # Fill file entries
    entry_slot = 1 if i == 0 else 0
    file_idx = i * 12 + (0 if i == 0 else -1 + 12)
    if i == 0:
        file_idx = 0
    else:
        file_idx = 12 + (i - 1) * 13

    for slot in range(entry_slot, 13):
        if file_idx >= len(root_entries):
            break
        offset = 4 + slot * ENTRY_LENGTH
        block_data[offset:offset+ENTRY_LENGTH] = root_entries[file_idx]
        file_idx += 1

    write_block(blk, block_data)

# Fix GAME subdir parent entry number (which slot is GAME in the volume dir?)
# GAME is the last root entry = slot len(root_entries) (slot 0 is volume header)
game_parent_entry = len(root_entries)
disk[game_dir_blocks[0] * BLOCK_SIZE + 4 + 0x25] = game_parent_entry

# --- Write volume bitmap ---
bitmap_size = math.ceil(TOTAL_BLOCKS / 8)
bitmap_blocks_needed = math.ceil(bitmap_size / BLOCK_SIZE)
bitmap = bytearray(bitmap_blocks_needed * BLOCK_SIZE)
# Mark all blocks as free (1 = free)
for i in range(len(bitmap)):
    bitmap[i] = 0xFF
# Mark used blocks as allocated (0 = used)
def mark_used(blk_num):
    byte_idx = blk_num // 8
    bit_idx = 7 - (blk_num % 8)  # ProDOS: MSB = lowest block
    bitmap[byte_idx] &= ~(1 << bit_idx)

# Boot blocks
mark_used(0)
mark_used(1)
# Volume directory
for blk in vol_dir_blocks:
    mark_used(blk)
# Bitmap block(s)
for i in range(bitmap_blocks_needed):
    mark_used(bitmap_block + i)
# GAME subdirectory blocks
for blk in game_dir_blocks:
    mark_used(blk)
# All allocated data/index blocks (7 through next_free-1)
for blk in range(7, next_free):
    mark_used(blk)
# Mark blocks beyond disk end as used
for blk in range(TOTAL_BLOCKS, bitmap_blocks_needed * BLOCK_SIZE * 8):
    if blk // 8 < len(bitmap):
        mark_used(blk)

# Write bitmap to disk
for i in range(bitmap_blocks_needed):
    write_block(bitmap_block + i, bitmap[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE])

# --- Write disk image ---
with open(OUTPUT, 'wb') as f:
    f.write(disk)

total_files = len(root_files) + len(game_files)
free_blocks = TOTAL_BLOCKS - next_free
print(f'    Built ProDOS image: {TOTAL_BLOCKS} blocks ({TOTAL_BLOCKS * 512} bytes)')
print(f'    Added {total_files} files ({next_free - 7} data blocks used, {free_blocks} free)')
print(f'    Boot blocks copied from vanilla')
" "$VANILLA" "$GAME_DIR" "$OUTPUT"

# --- Step 4: Summary ---

OUTPUT_SIZE=$(stat -c%s "$OUTPUT" 2>/dev/null || stat -f%z "$OUTPUT" 2>/dev/null || echo "unknown")

echo ""
echo "=== Build complete ==="
echo "Output: $OUTPUT ($OUTPUT_SIZE bytes)"
echo ""
echo "Test in an Apple II emulator to verify playability."
