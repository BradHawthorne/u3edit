"""File resolution, validation, and Apple II text utilities."""

import glob
import os
import shutil


def hex_int(x: str) -> int:
    """Parse an integer from string, accepting both decimal and hex (0x) prefix.

    Use as argparse type= for arguments where hex input is natural
    (tile values, byte offsets, raw flag bytes).
    """
    return int(x, 0)


def resolve_game_file(directory: str, prefix: str, letter: str) -> str | None:
    """Find a game file by prefix and letter, handling ProDOS #hash suffixes.

    Searches for files like 'MAPA#061000' or just 'MAPA' in the directory.
    Excludes .dproj files.

    Returns the path or None if not found.
    """
    pattern = os.path.join(directory, f'{prefix}{letter}#*')
    matches = [m for m in glob.glob(pattern) if not m.endswith('.dproj')]
    if matches:
        return matches[0]
    # Try without hash suffix
    plain = os.path.join(directory, f'{prefix}{letter}')
    if os.path.isfile(plain):
        return plain
    return None


def find_game_files(directory: str, prefix: str, letters: str) -> list[tuple[str, str]]:
    """Find all game files for a prefix across multiple letters.

    Returns list of (letter, path) tuples for found files.
    """
    results = []
    for letter in letters:
        path = resolve_game_file(directory, prefix, letter)
        if path:
            results.append((letter, path))
    return results


def resolve_single_file(directory: str, name: str) -> str | None:
    """Find a single game file by name (with or without #hash suffix)."""
    pattern = os.path.join(directory, f'{name}#*')
    matches = [m for m in glob.glob(pattern) if not m.endswith('.dproj')]
    if matches:
        return matches[0]
    plain = os.path.join(directory, name)
    if os.path.isfile(plain):
        return plain
    return None


def decode_high_ascii(data: bytes) -> str:
    """Decode Apple II high-bit ASCII text to a Python string.

    Strips bit 7, converts printable range to characters, stops at null.
    """
    chars = []
    for b in data:
        if b == 0x00:
            break
        ch = b & 0x7F
        if 0x20 <= ch < 0x7F:
            chars.append(chr(ch))
    return ''.join(chars).rstrip()


def backup_file(path: str) -> str:
    """Create a .bak backup of a file before overwriting.

    Returns the backup path, or raises FileNotFoundError if original missing.
    """
    bak = path + '.bak'
    shutil.copy2(path, bak)
    return bak


def encode_high_ascii(text: str, length: int) -> bytearray:
    """Encode a Python string to Apple II high-bit ASCII, padded to length.

    Unused bytes are filled with 0xA0 (high-ASCII space) to match the game format.
    """
    result = bytearray([0xA0] * length)
    for i, ch in enumerate(text[:length]):
        result[i] = ord(ch.upper()) | 0x80
    return result
