"""diskiigs integration for direct disk image access.

Wraps the diskiigs CLI tool via subprocess to read/write files from
ProDOS and DOS 3.3 disk images (.po, .2mg, .dsk, .do).
"""

import os
import shutil
import subprocess
import sys
import tempfile


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
        self._tmpdir: str | None = None

    def __enter__(self):
        self._tmpdir = tempfile.mkdtemp(prefix='u3edit_')
        # Extract all files to cache directory
        disk_extract_all(self.image_path, self._tmpdir, self.diskiigs_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Write back modified files
            for name, data in self._modified.items():
                disk_write(self.image_path, name, data, diskiigs_path=self.diskiigs_path)
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        return False

    def read(self, name: str) -> bytes | None:
        """Read a file from the disk image (cached)."""
        if name in self._modified:
            return self._modified[name]
        if name in self._cache:
            return self._cache[name]
        if self._tmpdir:
            # Search extracted files
            for f in os.listdir(self._tmpdir):
                basename = f.split('#')[0]
                if basename.upper() == name.upper():
                    fpath = os.path.join(self._tmpdir, f)
                    with open(fpath, 'rb') as fp:
                        data = fp.read()
                    self._cache[name] = data
                    return data
        return None

    def write(self, name: str, data: bytes) -> None:
        """Stage a file for writing back to disk image."""
        self._modified[name] = data
