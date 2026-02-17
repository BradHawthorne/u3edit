"""Tests for BCD encode/decode."""

from u3edit.bcd import bcd_to_int, bcd16_to_int, int_to_bcd, int_to_bcd16, is_valid_bcd


class TestBcdToInt:
    def test_zero(self):
        assert bcd_to_int(0x00) == 0

    def test_simple(self):
        assert bcd_to_int(0x25) == 25

    def test_max(self):
        assert bcd_to_int(0x99) == 99

    def test_tens_only(self):
        assert bcd_to_int(0x50) == 50

    def test_ones_only(self):
        assert bcd_to_int(0x07) == 7


class TestBcd16ToInt:
    def test_zero(self):
        assert bcd16_to_int(0x00, 0x00) == 0

    def test_simple(self):
        assert bcd16_to_int(0x01, 0x50) == 150

    def test_max(self):
        assert bcd16_to_int(0x99, 0x99) == 9999

    def test_hundreds_only(self):
        assert bcd16_to_int(0x05, 0x00) == 500


class TestIntToBcd:
    def test_zero(self):
        assert int_to_bcd(0) == 0x00

    def test_simple(self):
        assert int_to_bcd(25) == 0x25

    def test_max(self):
        assert int_to_bcd(99) == 0x99

    def test_clamp_high(self):
        assert int_to_bcd(150) == 0x99

    def test_clamp_low(self):
        assert int_to_bcd(-5) == 0x00


class TestIntToBcd16:
    def test_zero(self):
        assert int_to_bcd16(0) == (0x00, 0x00)

    def test_simple(self):
        assert int_to_bcd16(150) == (0x01, 0x50)

    def test_max(self):
        assert int_to_bcd16(9999) == (0x99, 0x99)

    def test_clamp_high(self):
        assert int_to_bcd16(20000) == (0x99, 0x99)

    def test_clamp_low(self):
        assert int_to_bcd16(-1) == (0x00, 0x00)


class TestRoundTrips:
    def test_single_roundtrip(self):
        for val in range(100):
            assert bcd_to_int(int_to_bcd(val)) == val

    def test_double_roundtrip(self):
        for val in [0, 1, 99, 100, 500, 1234, 9999]:
            hi, lo = int_to_bcd16(val)
            assert bcd16_to_int(hi, lo) == val


class TestIsValidBcd:
    def test_valid(self):
        assert is_valid_bcd(0x00)
        assert is_valid_bcd(0x99)
        assert is_valid_bcd(0x42)

    def test_invalid_low(self):
        assert not is_valid_bcd(0x0A)
        assert not is_valid_bcd(0x0F)

    def test_invalid_high(self):
        assert not is_valid_bcd(0xA0)
        assert not is_valid_bcd(0xF0)

    def test_invalid_both(self):
        assert not is_valid_bcd(0xFF)
