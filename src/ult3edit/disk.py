"""Disk image operations: read, write, build ProDOS disk images.

Supports both native Python ProDOS operations and diskiigs CLI wrapping
for reading/writing files from ProDOS and DOS 3.3 disk images (.po, .2mg).
"""

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile

from .json_export import export_json


def find_diskiigs() -> str | None:
    """Locate the diskiigs executable.

    Search order:
    1. DISKIIGS_PATH environment variable
    2. System PATH
    3. Common build paths relative to rosetta_v2
    """
    # Check environment variable
    env_path = os.environ.get('DISKIIGS_PATH')
    if env_path and os.path.isfile(env_path):
        return env_path

    # Check PATH
    found = shutil.which('diskiigs')
    if found:
        return found

    # Check common build paths
    for base in [os.path.expanduser('~/Projects/rosetta_v2'),
                 'D:/Projects/rosetta_v2', '/opt/rosetta']:
        for subpath in ['build/diskiigs/Release/diskiigs.exe',
                        'build/diskiigs/diskiigs',
                        'build/diskiigs/Release/diskiigs']:
            candidate = os.path.join(base, subpath)
            if os.path.isfile(candidate):
                return candidate

    return None


def _run_diskiigs(args: list[str], diskiigs_path: str | None = None) -> subprocess.CompletedProcess:
    """Run a diskiigs command and return the result."""
    exe = diskiigs_path or find_diskiigs()
    if not exe:
        raise FileNotFoundError(
            "diskiigs not found. Set DISKIIGS_PATH or add to PATH."
        )
    cmd = [exe] + args
    return subprocess.run(cmd, capture_output=True, text=True)


def disk_info(image_path: str, diskiigs_path: str | None = None) -> dict:
    """Get disk image info (volume name, format, blocks)."""
    result = _run_diskiigs(['info', image_path], diskiigs_path)
    if result.returncode != 0:
        return {'error': result.stderr.strip()}
    info = {}
    for line in result.stdout.splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            info[key.strip().lower()] = val.strip()
    return info


def disk_list(image_path: str, path: str = '/', diskiigs_path: str | None = None) -> list[dict]:
    """List files on disk image. Returns list of file info dicts."""
    result = _run_diskiigs(['list', '-l', image_path, path], diskiigs_path)
    if result.returncode != 0:
        return []
    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith('Name') or line.startswith('---'):
            continue
        parts = line.split()
        if len(parts) >= 3:
            entries.append({
                'name': parts[0],
                'type': parts[1] if len(parts) > 1 else '',
                'size': parts[2] if len(parts) > 2 else '',
                'raw': line,
            })
    return entries


def disk_read(image_path: str, prodos_path: str, diskiigs_path: str | None = None) -> bytes | None:
    """Read a file from a disk image, returns bytes or None on error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _run_diskiigs(
            ['extract', image_path, prodos_path, '-o', tmpdir],
            diskiigs_path
        )
        if result.returncode != 0:
            return None
        # Find the extracted file (may have #hash suffix)
        for f in os.listdir(tmpdir):
            fpath = os.path.join(tmpdir, f)
            if os.path.isfile(fpath):
                with open(fpath, 'rb') as fp:
                    return fp.read()
    return None


def disk_write(image_path: str, prodos_path: str, data: bytes,
               file_type: int = 0x06, aux_type: int = 0x0000,
               diskiigs_path: str | None = None) -> bool:
    """Write a file to a disk image. Returns True on success."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write data to temp file with ProDOS type suffix
        fname = f'{os.path.basename(prodos_path)}#{file_type:02X}{aux_type:04X}'
        tmp_path = os.path.join(tmpdir, fname)
        with open(tmp_path, 'wb') as f:
            f.write(data)
        result = _run_diskiigs(
            ['add', image_path, tmp_path, '--to', os.path.dirname(prodos_path) or '/'],
            diskiigs_path
        )
        return result.returncode == 0


def disk_extract_all(image_path: str, output_dir: str, diskiigs_path: str | None = None) -> bool:
    """Extract all files from a disk image to a directory."""
    os.makedirs(output_dir, exist_ok=True)
    result = _run_diskiigs(
        ['extract-all', image_path, '-o', output_dir],
        diskiigs_path
    )
    return result.returncode == 0


class DiskContext:
    """Context manager for batch disk image operations.

    Caches extracted files and writes back modified ones on close.
    Usage:
        with DiskContext('game.po') as ctx:
            data = ctx.read('ROST')
            ctx.write('ROST', modified_data)
    """

    def __init__(self, image_path: str, diskiigs_path: str | None = None):
        self.image_path = image_path
        self.diskiigs_path = diskiigs_path
        self._cache: dict[str, bytes] = {}
        self._modified: dict[str, bytes] = {}
        self._file_types: dict[str, tuple[int, int]] = {}  # name → (file_type, aux_type)
        self._tmpdir: str | None = None

    def __enter__(self):
        self._tmpdir = tempfile.mkdtemp(prefix='ult3edit_')
        try:
            # Extract all files to cache directory
            disk_extract_all(self.image_path, self._tmpdir, self.diskiigs_path)
        except Exception:
            # Clean up temp dir if extraction fails (e.g. diskiigs not found)
            shutil.rmtree(self._tmpdir, ignore_errors=True)
            self._tmpdir = None
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Always write back modified files, even on exception, to avoid data loss
        if self._modified:
            for name, data in self._modified.items():
                try:
                    ft, at = self._file_types.get(name.upper(), (0x06, 0x0000))
                    disk_write(self.image_path, name, data,
                               file_type=ft, aux_type=at,
                               diskiigs_path=self.diskiigs_path)
                except Exception as e:
                    print(f'Warning: failed to write {name}: {e}',
                          file=sys.stderr)
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        return False

    @staticmethod
    def _parse_hash_suffix(filename: str) -> tuple[str, int, int]:
        """Parse 'NAME#TTAAAA' into (name, file_type, aux_type)."""
        if '#' in filename:
            base, suffix = filename.split('#', 1)
            if len(suffix) >= 6:
                try:
                    ft = int(suffix[:2], 16)
                    at = int(suffix[2:6], 16)
                    return base, ft, at
                except ValueError:
                    pass
            return base, 0x06, 0x0000
        return filename, 0x06, 0x0000

    def read(self, name: str) -> bytes | None:
        """Read a file from the disk image (cached)."""
        if name in self._modified:
            return self._modified[name]
        if name in self._cache:
            return self._cache[name]
        if self._tmpdir:
            # Search extracted files
            for f in os.listdir(self._tmpdir):
                base, ft, at = self._parse_hash_suffix(f)
                if base.upper() == name.upper():
                    fpath = os.path.join(self._tmpdir, f)
                    with open(fpath, 'rb') as fp:
                        data = fp.read()
                    self._cache[name] = data
                    self._file_types[name.upper()] = (ft, at)
                    return data
        return None

    def write(self, name: str, data: bytes) -> None:
        """Stage a file for writing back to disk image."""
        self._modified[name] = data


# =============================================================================
# Native ProDOS image builder
# =============================================================================

# ProDOS constants
PRODOS_BLOCK_SIZE = 512
PRODOS_ENTRY_LENGTH = 0x27  # 39 bytes per directory entry
PRODOS_ENTRIES_PER_BLOCK = 0x0D  # 13 entries per block


def build_prodos_image(output_path: str, files: list, vol_name: str = 'ULTIMA3',
                       boot_blocks: bytes = None, total_blocks: int = 1600) -> dict:
    """Build a ProDOS disk image from a list of files.

    files: list of dicts with keys:
        name (str): ProDOS filename (e.g., 'ROST')
        data (bytes): file content
        file_type (int): ProDOS file type (e.g., 0x06 for BIN)
        aux_type (int): ProDOS auxiliary type (e.g., 0x9500)
        subdir (str|None): subdirectory name or None for root

    vol_name: volume name (default 'ULTIMA3')
    boot_blocks: optional 1024 bytes for blocks 0-1 (boot code)
    total_blocks: disk size in 512-byte blocks (default: 1600 = 800K)

    Returns dict with build summary.
    """
    BS = PRODOS_BLOCK_SIZE
    EL = PRODOS_ENTRY_LENGTH

    # Separate root vs subdirectory files
    root_files = []  # (name, file_type, aux_type, data)
    subdir_map = {}  # subdir_name -> [(name, file_type, aux_type, data)]
    for f in files:
        name = f['name']
        data = f['data']
        ft = f.get('file_type', 0x06)
        aux = f.get('aux_type', 0x0000)
        subdir = f.get('subdir')
        if subdir:
            subdir_map.setdefault(subdir, []).append((name, ft, aux, data))
        else:
            root_files.append((name, ft, aux, data))

    # Sort root files: PRODOS first, then LOADER.SYSTEM, then alphabetical
    prodos_order = {'PRODOS': 0, 'LOADER.SYSTEM': 1}
    root_files.sort(key=lambda r: (prodos_order.get(r[0], 99), r[0]))

    # Initialize disk image
    disk = bytearray(total_blocks * BS)

    # Write boot blocks
    if boot_blocks:
        disk[0:len(boot_blocks)] = boot_blocks[:min(len(boot_blocks), 1024)]

    # Block allocator
    bitmap_block = 6
    vol_dir_blocks = [2, 3, 4, 5]
    next_free = [7]  # mutable for closure

    def alloc_block():
        if next_free[0] >= total_blocks:
            raise RuntimeError('Disk full')
        blk = next_free[0]
        next_free[0] += 1
        return blk

    def write_block(blk_num, data):
        offset = blk_num * BS
        disk[offset:offset + len(data)] = data

    # Write file data, return (key_block, storage_type, blocks_used)
    def write_file(data):
        eof = len(data)
        if eof == 0:
            blk = alloc_block()
            return blk, 1, 1
        data_blocks_needed = math.ceil(eof / BS)
        if data_blocks_needed == 1:
            # Seedling
            blk = alloc_block()
            padded = data + b'\x00' * (BS - len(data))
            write_block(blk, padded)
            return blk, 1, 1
        elif data_blocks_needed <= 256:
            # Sapling
            idx_blk = alloc_block()
            data_blks = []
            for i in range(data_blocks_needed):
                dblk = alloc_block()
                chunk = data[i * BS:(i + 1) * BS]
                if len(chunk) < BS:
                    chunk = chunk + b'\x00' * (BS - len(chunk))
                write_block(dblk, chunk)
                data_blks.append(dblk)
            idx = bytearray(BS)
            for i, dblk in enumerate(data_blks):
                idx[i] = dblk & 0xFF
                idx[256 + i] = (dblk >> 8) & 0xFF
            write_block(idx_blk, idx)
            return idx_blk, 2, 1 + data_blocks_needed
        else:
            # Tree
            master_blk = alloc_block()
            idx_blks = []
            total_written = 0
            remaining = data_blocks_needed
            while remaining > 0:
                chunk_count = min(256, remaining)
                idx_blk = alloc_block()
                data_blks = []
                for _i in range(chunk_count):
                    dblk = alloc_block()
                    start = total_written * BS
                    chunk = data[start:start + BS]
                    if len(chunk) < BS:
                        chunk = chunk + b'\x00' * (BS - len(chunk))
                    write_block(dblk, chunk)
                    data_blks.append(dblk)
                    total_written += 1
                idx = bytearray(BS)
                for i, dblk in enumerate(data_blks):
                    idx[i] = dblk & 0xFF
                    idx[256 + i] = (dblk >> 8) & 0xFF
                write_block(idx_blk, idx)
                idx_blks.append(idx_blk)
                remaining -= chunk_count
            master = bytearray(BS)
            for i, iblk in enumerate(idx_blks):
                master[i] = iblk & 0xFF
                master[256 + i] = (iblk >> 8) & 0xFF
            write_block(master_blk, master)
            return master_blk, 3, 1 + len(idx_blks) + data_blocks_needed

    # Build directory entry
    def make_entry(storage_type, name, file_type, key_block, blocks_used,
                   eof, aux_type, header_pointer=0):
        entry = bytearray(EL)
        name_bytes = name.encode('ascii')[:15]
        entry[0x00] = (storage_type << 4) | len(name_bytes)
        entry[0x01:0x01 + len(name_bytes)] = name_bytes
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
        entry[0x25] = header_pointer & 0xFF
        entry[0x26] = (header_pointer >> 8) & 0xFF
        return entry

    # Write root file data
    file_records = []  # (name, ft, aux, key, stype, blks, eof, is_root)
    for name, ft, aux, data in root_files:
        key_block, storage_type, blocks_used = write_file(data)
        file_records.append((name, ft, aux, key_block, storage_type,
                             blocks_used, len(data), True))

    # Process each subdirectory
    subdir_info = {}  # subdir_name -> (dir_blocks, file_count)
    for subdir_name in sorted(subdir_map.keys()):
        subdir_files = subdir_map[subdir_name]

        # Allocate subdirectory blocks
        if len(subdir_files) <= 12:
            dir_block_count = 1
        else:
            dir_block_count = 1 + math.ceil((len(subdir_files) - 12) / 13)
        dir_blocks = [alloc_block() for _ in range(dir_block_count)]

        # Write file data
        subdir_records = []
        for name, ft, aux, data in subdir_files:
            key_block, storage_type, blocks_used = write_file(data)
            subdir_records.append((name, ft, aux, key_block, storage_type,
                                   blocks_used, len(data)))
            file_records.append((name, ft, aux, key_block, storage_type,
                                 blocks_used, len(data), False))

        # Build subdirectory blocks
        for i, blk in enumerate(dir_blocks):
            prev_blk = dir_blocks[i - 1] if i > 0 else 0
            next_blk = dir_blocks[i + 1] if i < len(dir_blocks) - 1 else 0
            block_data = bytearray(BS)
            block_data[0] = prev_blk & 0xFF
            block_data[1] = (prev_blk >> 8) & 0xFF
            block_data[2] = next_blk & 0xFF
            block_data[3] = (next_blk >> 8) & 0xFF

            if i == 0:
                # Subdirectory header
                hdr = bytearray(EL)
                nb = subdir_name.encode('ascii')[:15]
                hdr[0x00] = (0x0E << 4) | len(nb)
                hdr[0x01:0x01 + len(nb)] = nb
                hdr[0x1C] = 0x00  # version
                hdr[0x1D] = 0x00  # min_version
                hdr[0x1E] = 0xE3  # access
                hdr[0x1F] = EL
                hdr[0x20] = PRODOS_ENTRIES_PER_BLOCK
                hdr[0x21] = len(subdir_records) & 0xFF
                hdr[0x22] = (len(subdir_records) >> 8) & 0xFF
                hdr[0x23] = vol_dir_blocks[0] & 0xFF
                hdr[0x24] = (vol_dir_blocks[0] >> 8) & 0xFF
                hdr[0x25] = 0x01  # placeholder, fixed later
                hdr[0x26] = EL
                block_data[4:4 + EL] = hdr

            entry_slot = 1 if i == 0 else 0
            if i == 0:
                file_idx = 0
            else:
                file_idx = 12 + (i - 1) * 13

            for slot in range(entry_slot, 13):
                if file_idx >= len(subdir_records):
                    break
                rec = subdir_records[file_idx]
                name, ft, aux, key, stype, blks, eof = rec
                entry = make_entry(stype, name, ft, key, blks, eof, aux,
                                   header_pointer=dir_blocks[0])
                offset = 4 + slot * EL
                block_data[offset:offset + EL] = entry
                file_idx += 1

            write_block(blk, block_data)

        subdir_info[subdir_name] = (dir_blocks, len(subdir_records))

    # Build volume directory
    root_entries = []

    # Root file entries
    root_recs = [r for r in file_records if r[7]]
    for rec in root_recs:
        name, ft, aux, key, stype, blks, eof, _ = rec
        entry = make_entry(stype, name, ft, key, blks, eof, aux,
                           header_pointer=vol_dir_blocks[0])
        root_entries.append(entry)

    # Subdirectory entries
    for subdir_name in sorted(subdir_info.keys()):
        dir_blocks, file_count = subdir_info[subdir_name]
        sd_entry = bytearray(EL)
        nb = subdir_name.encode('ascii')[:15]
        sd_entry[0x00] = (0x0D << 4) | len(nb)
        sd_entry[0x01:0x01 + len(nb)] = nb
        sd_entry[0x10] = 0x0F  # directory
        sd_entry[0x11] = dir_blocks[0] & 0xFF
        sd_entry[0x12] = (dir_blocks[0] >> 8) & 0xFF
        total_dir_blocks = len(dir_blocks)
        sd_entry[0x13] = total_dir_blocks & 0xFF
        sd_entry[0x14] = (total_dir_blocks >> 8) & 0xFF
        dir_eof = len(dir_blocks) * BS
        sd_entry[0x15] = dir_eof & 0xFF
        sd_entry[0x16] = (dir_eof >> 8) & 0xFF
        sd_entry[0x17] = (dir_eof >> 16) & 0xFF
        sd_entry[0x1E] = 0xE3
        sd_entry[0x25] = vol_dir_blocks[0] & 0xFF
        sd_entry[0x26] = (vol_dir_blocks[0] >> 8) & 0xFF
        root_entries.append(sd_entry)

    root_file_count = len(root_entries)

    # Write volume directory blocks
    for i, blk in enumerate(vol_dir_blocks):
        prev_blk = vol_dir_blocks[i - 1] if i > 0 else 0
        next_blk = vol_dir_blocks[i + 1] if i < len(vol_dir_blocks) - 1 else 0
        block_data = bytearray(BS)
        block_data[0] = prev_blk & 0xFF
        block_data[1] = (prev_blk >> 8) & 0xFF
        block_data[2] = next_blk & 0xFF
        block_data[3] = (next_blk >> 8) & 0xFF

        if i == 0:
            vol_name_bytes = vol_name.encode('ascii')[:15]
            hdr = bytearray(EL)
            hdr[0x00] = (0x0F << 4) | len(vol_name_bytes)
            hdr[0x01:0x01 + len(vol_name_bytes)] = vol_name_bytes
            hdr[0x1C] = 0x00
            hdr[0x1D] = 0x00
            hdr[0x1E] = 0xE3
            hdr[0x1F] = EL
            hdr[0x20] = PRODOS_ENTRIES_PER_BLOCK
            hdr[0x21] = root_file_count & 0xFF
            hdr[0x22] = (root_file_count >> 8) & 0xFF
            hdr[0x23] = bitmap_block & 0xFF
            hdr[0x24] = (bitmap_block >> 8) & 0xFF
            hdr[0x25] = total_blocks & 0xFF
            hdr[0x26] = (total_blocks >> 8) & 0xFF
            block_data[4:4 + EL] = hdr

        entry_slot = 1 if i == 0 else 0
        if i == 0:
            file_idx = 0
        else:
            file_idx = 12 + (i - 1) * 13

        for slot in range(entry_slot, 13):
            if file_idx >= len(root_entries):
                break
            offset = 4 + slot * EL
            block_data[offset:offset + EL] = root_entries[file_idx]
            file_idx += 1

        write_block(blk, block_data)

    # Fix subdirectory parent entry numbers
    for subdir_name, (dir_blocks, _fc) in subdir_info.items():
        # Find this subdir's position in root_entries
        for entry_idx, entry in enumerate(root_entries):
            nlen = entry[0x00] & 0x0F
            ename = entry[0x01:0x01 + nlen].decode('ascii', errors='replace')
            if ename == subdir_name:
                parent_entry = entry_idx + 2  # +1 for header, +1 for 1-based
                disk[dir_blocks[0] * BS + 4 + 0x25] = parent_entry
                break

    # Write volume bitmap
    bitmap_size = math.ceil(total_blocks / 8)
    bitmap_blocks_needed = math.ceil(bitmap_size / BS)
    bitmap = bytearray(bitmap_blocks_needed * BS)
    for i in range(len(bitmap)):
        bitmap[i] = 0xFF

    def mark_used(blk_num):
        byte_idx = blk_num // 8
        bit_idx = 7 - (blk_num % 8)
        bitmap[byte_idx] &= ~(1 << bit_idx)

    mark_used(0)
    mark_used(1)
    for blk in vol_dir_blocks:
        mark_used(blk)
    for i in range(bitmap_blocks_needed):
        mark_used(bitmap_block + i)
    for sd_name, (dir_blocks, _fc) in subdir_info.items():
        for blk in dir_blocks:
            mark_used(blk)
    for blk in range(7, next_free[0]):
        mark_used(blk)
    for blk in range(total_blocks, bitmap_blocks_needed * BS * 8):
        if blk // 8 < len(bitmap):
            mark_used(blk)

    for i in range(bitmap_blocks_needed):
        write_block(bitmap_block + i, bitmap[i * BS:(i + 1) * BS])

    # Write disk image
    with open(output_path, 'wb') as f:
        f.write(disk)

    total_file_count = len(files)
    data_blocks = next_free[0] - 7
    free_blocks = total_blocks - next_free[0]

    return {
        'total_blocks': total_blocks,
        'total_bytes': total_blocks * BS,
        'files': total_file_count,
        'data_blocks': data_blocks,
        'free_blocks': free_blocks,
    }


def _parse_hash_filename(filename: str) -> tuple:
    """Parse 'NAME#TTAAAA' into (prodos_name, file_type, aux_type)."""
    if '#' in filename:
        base, suffix = filename.split('#', 1)
        if len(suffix) >= 6:
            try:
                ft = int(suffix[:2], 16)
                aux = int(suffix[2:6], 16)
                return base, ft, aux
            except ValueError:
                pass
        return base, 0x06, 0x0000
    return filename, 0x06, 0x0000


def collect_build_files(input_dir: str, subdir_name: str = 'GAME') -> list:
    """Collect files from a directory for disk image building.

    Parses ProDOS #hash suffixes. Files named PRODOS, LOADER.SYSTEM, or U3
    go in root; all others go in the specified subdirectory.

    Returns list of file dicts suitable for build_prodos_image().
    """
    root_names = {'PRODOS', 'LOADER.SYSTEM', 'U3'}
    files = []

    for fname in sorted(os.listdir(input_dir)):
        fpath = os.path.join(input_dir, fname)
        if not os.path.isfile(fpath) or fname.endswith('.bak'):
            continue
        if '#' not in fname:
            continue

        prodos_name, file_type, aux_type = _parse_hash_filename(fname)
        with open(fpath, 'rb') as f:
            data = f.read()

        is_root = prodos_name in root_names
        files.append({
            'name': prodos_name,
            'data': data,
            'file_type': file_type,
            'aux_type': aux_type,
            'subdir': None if is_root else subdir_name,
        })

    return files


# =============================================================================
# CLI Commands
# =============================================================================

def cmd_info(args) -> None:
    """Show disk image info."""
    info = disk_info(args.image)
    if 'error' in info:
        print(f"Error: {info['error']}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        export_json(info, args.output)
        return

    print(f"\n=== Disk Image: {os.path.basename(args.image)} ===\n")
    for key, val in info.items():
        print(f"  {key:<20s}  {val}")
    print()


def cmd_list(args) -> None:
    """List files on disk image."""
    entries = disk_list(args.image, args.path)
    if not entries:
        print("No files found (or diskiigs error).", file=sys.stderr)
        sys.exit(1)

    if args.json:
        export_json(entries, args.output)
        return

    print(f"\n=== {os.path.basename(args.image)}:{args.path} ===\n")
    print(f"  {'Name':<20s}  {'Type':<6s}  {'Size':>8s}")
    print(f"  {'----':<20s}  {'----':<6s}  {'----':>8s}")
    for e in entries:
        print(f"  {e['name']:<20s}  {e['type']:<6s}  {e['size']:>8s}")
    print(f"\n  {len(entries)} files\n")


def cmd_extract(args) -> None:
    """Extract all files from disk image."""
    output_dir = args.output or '.'
    ok = disk_extract_all(args.image, output_dir)
    if ok:
        print(f"Extracted to {output_dir}")
    else:
        print("Extract failed.", file=sys.stderr)
        sys.exit(1)


def cmd_build(args) -> None:
    """Build a ProDOS disk image from a directory of game files."""
    input_dir = args.input_dir
    output_path = args.output
    vol_name = getattr(args, 'vol_name', 'ULTIMA3') or 'ULTIMA3'

    if not os.path.isdir(input_dir):
        print(f"Error: Input directory not found: {input_dir}",
              file=sys.stderr)
        sys.exit(1)

    # Load boot blocks from vanilla disk if specified
    boot_blocks = None
    boot_from = getattr(args, 'boot_from', None)
    if boot_from:
        if not os.path.isfile(boot_from):
            print(f"Error: Boot source not found: {boot_from}",
                  file=sys.stderr)
            sys.exit(1)
        with open(boot_from, 'rb') as f:
            boot_blocks = f.read(1024)

    files = collect_build_files(input_dir)
    if not files:
        print("Error: No files found in input directory "
              "(expected NAME#TTAAAA format)", file=sys.stderr)
        sys.exit(1)

    # Enforce TLK memory constraint (256 bytes max)
    for f in files:
        if f['name'].startswith('TLK') and len(f['data']) > 256:
            f['data'] = f['data'][:256]

    result = build_prodos_image(output_path, files, vol_name=vol_name,
                                boot_blocks=boot_blocks)

    print(f"  Built ProDOS image: {result['total_blocks']} blocks "
          f"({result['total_bytes']} bytes)")
    print(f"  Added {result['files']} files "
          f"({result['data_blocks']} data blocks used, "
          f"{result['free_blocks']} free)")
    if boot_blocks:
        print("  Boot blocks copied from vanilla")
    print(f"  Written: {output_path}")


def cmd_audit(args) -> None:
    """Analyze disk image for space usage and total conversion capacity."""
    info = disk_info(args.image)
    entries = disk_list(args.image)

    if 'error' in info:
        print(f"Error: {info['error']}", file=sys.stderr)
        sys.exit(1)

    # Parse disk size info
    total_blocks = 0
    for key in ('blocks', 'total blocks', 'total_blocks'):
        if key in info:
            try:
                total_blocks = int(info[key].split()[0])
            except (ValueError, IndexError):
                pass
            break

    # ProDOS block = 512 bytes
    block_size = 512
    total_bytes = total_blocks * block_size

    # Calculate per-file space usage
    file_details = []
    total_used = 0
    for entry in entries:
        size_str = entry.get('size', '0')
        try:
            size = int(size_str.replace(',', ''))
        except ValueError:
            size = 0
        blocks_needed = (size + block_size - 1) // block_size if size > 0 else 0
        wasted = blocks_needed * block_size - size
        file_details.append({
            'name': entry['name'],
            'type': entry.get('type', ''),
            'size': size,
            'blocks': blocks_needed,
            'wasted': wasted,
        })
        total_used += blocks_needed

    free_blocks = total_blocks - total_used if total_blocks else 0
    free_bytes = free_blocks * block_size
    total_wasted = sum(f['wasted'] for f in file_details)

    if args.json:
        result = {
            'image': os.path.basename(args.image),
            'disk_info': info,
            'total_blocks': total_blocks,
            'total_bytes': total_bytes,
            'used_blocks': total_used,
            'free_blocks': free_blocks,
            'free_bytes': free_bytes,
            'alignment_waste': total_wasted,
            'files': file_details,
            'capacity_estimates': {
                'tlk_records': free_bytes // 256,
                'map_files': free_bytes // 4096,
                'mon_files': free_bytes // 256,
                'extra_tiles_8x8': free_bytes // 8,
            },
        }
        export_json(result, args.output)
        return

    print(f"\n=== Disk Audit: {os.path.basename(args.image)} ===\n")

    if total_blocks:
        print(f"  Total capacity:  {total_blocks} blocks "
              f"({total_bytes:,} bytes)")
        print(f"  Used:            {total_used} blocks "
              f"({total_used * block_size:,} bytes)")
        print(f"  Free:            {free_blocks} blocks "
              f"({free_bytes:,} bytes)")
        print(f"  Alignment waste: {total_wasted:,} bytes "
              f"(reclaimable padding)")
    print()

    if getattr(args, 'detail', False):
        print(f"  {'File':<20s}  {'Type':<6s}  {'Size':>8s}  "
              f"{'Blocks':>6s}  {'Waste':>6s}")
        print(f"  {'----':<20s}  {'----':<6s}  {'----':>8s}  "
              f"{'------':>6s}  {'-----':>6s}")
        for f in file_details:
            print(f"  {f['name']:<20s}  {f['type']:<6s}  "
                  f"{f['size']:>8,}  {f['blocks']:>6}  {f['wasted']:>6}")
        print()

    if free_bytes > 0:
        print(f"  Capacity estimates (with {free_bytes:,} free bytes):")
        print(f"    TLK dialog files (256 bytes):    {free_bytes // 256}")
        print(f"    Town maps (4096 bytes):           {free_bytes // 4096}")
        print(f"    Monster files (256 bytes):        {free_bytes // 256}")
        print(f"    Extra glyphs (8 bytes):           {free_bytes // 8}")
    print()


def register_parser(subparsers) -> None:
    p = subparsers.add_parser('disk', help='Disk image operations (requires diskiigs)')
    sub = p.add_subparsers(dest='disk_command')

    p_info = sub.add_parser('info', help='Show disk image info')
    p_info.add_argument('image', help='Disk image file (.po, .2mg, .dsk)')
    p_info.add_argument('--json', action='store_true', help='Output as JSON')
    p_info.add_argument('--output', '-o', help='Output file (for --json)')

    p_list = sub.add_parser('list', help='List files on disk image')
    p_list.add_argument('image', help='Disk image file')
    p_list.add_argument('--path', default='/', help='ProDOS directory path (default: /)')
    p_list.add_argument('--json', action='store_true', help='Output as JSON')
    p_list.add_argument('--output', '-o', help='Output file (for --json)')

    p_extract = sub.add_parser('extract', help='Extract all files from disk image')
    p_extract.add_argument('image', help='Disk image file')
    p_extract.add_argument('--output', '-o', help='Output directory (default: current)')

    p_audit = sub.add_parser('audit', help='Analyze disk space usage')
    p_audit.add_argument('image', help='Disk image file')
    p_audit.add_argument('--detail', action='store_true',
                         help='Show per-file allocation details')
    p_audit.add_argument('--json', action='store_true', help='Output as JSON')
    p_audit.add_argument('--output', '-o', help='Output file (for --json)')

    p_build = sub.add_parser('build', help='Build ProDOS disk image from files')
    p_build.add_argument('output', help='Output disk image path (.po)')
    p_build.add_argument('input_dir', help='Directory containing game files')
    p_build.add_argument('--vol-name', default='ULTIMA3',
                         help='Volume name (default: ULTIMA3)')
    p_build.add_argument('--boot-from',
                         help='Copy boot blocks from this disk image')


def dispatch(args) -> None:
    if args.disk_command == 'info':
        cmd_info(args)
    elif args.disk_command == 'list':
        cmd_list(args)
    elif args.disk_command == 'extract':
        cmd_extract(args)
    elif args.disk_command == 'audit':
        cmd_audit(args)
    elif args.disk_command == 'build':
        cmd_build(args)
    else:
        print("Usage: ult3edit disk {info|list|extract|audit|build} ...",
              file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ultima III: Exodus - Disk Image Operations')
    sub = parser.add_subparsers(dest='disk_command')

    p_info = sub.add_parser('info', help='Show disk image info')
    p_info.add_argument('image', help='Disk image file (.po, .2mg, .dsk)')
    p_info.add_argument('--json', action='store_true', help='Output as JSON')
    p_info.add_argument('--output', '-o', help='Output file (for --json)')

    p_list = sub.add_parser('list', help='List files on disk image')
    p_list.add_argument('image', help='Disk image file')
    p_list.add_argument('--path', default='/', help='ProDOS directory path (default: /)')
    p_list.add_argument('--json', action='store_true', help='Output as JSON')
    p_list.add_argument('--output', '-o', help='Output file (for --json)')

    p_extract = sub.add_parser('extract', help='Extract all files')
    p_extract.add_argument('image', help='Disk image file')
    p_extract.add_argument('--output', '-o', help='Output directory (default: current)')

    p_audit = sub.add_parser('audit', help='Analyze disk space usage')
    p_audit.add_argument('image', help='Disk image file')
    p_audit.add_argument('--detail', action='store_true',
                         help='Show per-file allocation details')
    p_audit.add_argument('--json', action='store_true', help='Output as JSON')
    p_audit.add_argument('--output', '-o', help='Output file (for --json)')

    p_build = sub.add_parser('build', help='Build ProDOS disk image from files')
    p_build.add_argument('output', help='Output disk image path (.po)')
    p_build.add_argument('input_dir', help='Directory containing game files')
    p_build.add_argument('--vol-name', default='ULTIMA3',
                         help='Volume name (default: ULTIMA3)')
    p_build.add_argument('--boot-from',
                         help='Copy boot blocks from this disk image')

    args = parser.parse_args()
    dispatch(args)


if __name__ == '__main__':
    main()
