"""BCD (Binary Coded Decimal) encoding/decoding for Ultima III data files.

Ultima III stores most numeric values as BCD: two decimal digits per byte,
high nibble = tens, low nibble = ones. Multi-byte BCD fields are big-endian
(most significant byte first).
"""


def bcd_to_int(b: int) -> int:
    """Decode a single BCD byte to integer (0-99)."""
    return ((b >> 4) & 0x0F) * 10 + (b & 0x0F)


def bcd16_to_int(hi: int, lo: int) -> int:
    """Decode a two-byte BCD value to integer (0-9999). hi=hundreds, lo=ones."""
    return bcd_to_int(hi) * 100 + bcd_to_int(lo)


def int_to_bcd(val: int) -> int:
    """Encode an integer (0-99) as a single BCD byte."""
    val = max(0, min(99, val))
    return ((val // 10) << 4) | (val % 10)


def int_to_bcd16(val: int) -> tuple[int, int]:
    """Encode an integer (0-9999) as two BCD bytes (hi, lo)."""
    val = max(0, min(9999, val))
    hi = int_to_bcd(val // 100)
    lo = int_to_bcd(val % 100)
    return hi, lo


def is_valid_bcd(b: int) -> bool:
    """Check if a byte contains valid BCD (each nibble 0-9)."""
    return (b & 0x0F) <= 9 and ((b >> 4) & 0x0F) <= 9
