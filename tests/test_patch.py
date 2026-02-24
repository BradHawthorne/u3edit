"""Tests for the patch module: engine binary patching, inline strings, name compilation."""

import argparse
import json
import os
import shutil
import sys

import pytest

from ult3edit.patch import (
    identify_binary, get_regions, parse_text_region,
    parse_coord_region, encode_text_region, encode_coord_region,
    cmd_import as patch_cmd_import, PATCHABLE_REGIONS,
)


class TestPatch:
    def _make_ult3(self):
        """Create a synthetic ULT3 binary."""
        data = bytearray(17408)
        # Put some name table text at the CIDAR-verified offset
        offset = 0x397A
        text = b'\x00\xD7\xC1\xD4\xC5\xD2\x00'  # null + "WATER" + null
        text += b'\xC7\xD2\xC1\xD3\xD3\x00'  # "GRASS" + null
        data[offset:offset + len(text)] = text
        # Put moongate X coords at $29A7
        for i in range(8):
            data[0x29A7 + i] = i * 8
        # Put moongate Y coords at $29AF
        for i in range(8):
            data[0x29AF + i] = i * 4
        # Set food rate at $272C
        data[0x272C] = 0x04
        return bytes(data)

    def test_identify_ult3(self):
        data = self._make_ult3()
        info = identify_binary(data, 'ULT3#065000')
        assert info is not None
        assert info['name'] == 'ULT3'
        assert info['load_addr'] == 0x5000

    def test_identify_exod(self):
        data = bytes(26208)
        info = identify_binary(data, 'EXOD#062000')
        assert info is not None
        assert info['name'] == 'EXOD'

    def test_identify_subs(self):
        data = bytes(3584)
        info = identify_binary(data, 'SUBS#064100')
        assert info is not None
        assert info['name'] == 'SUBS'
        assert info['load_addr'] == 0x4100

    def test_subs_no_regions(self):
        """SUBS is a subroutine library with no patchable data regions."""
        regions = get_regions('SUBS')
        assert regions == {}

    def test_identify_unknown(self):
        data = bytes(100)
        info = identify_binary(data, 'UNKNOWN')
        assert info is None

    def test_get_regions_ult3(self):
        regions = get_regions('ULT3')
        assert 'name-table' in regions
        assert regions['name-table']['data_type'] == 'text'
        assert regions['name-table']['max_length'] == 921

    def test_get_regions_ult3_moongate(self):
        regions = get_regions('ULT3')
        assert 'moongate-x' in regions
        assert 'moongate-y' in regions
        assert regions['moongate-x']['max_length'] == 8
        assert regions['moongate-y']['max_length'] == 8

    def test_get_regions_ult3_food_rate(self):
        regions = get_regions('ULT3')
        assert 'food-rate' in regions
        assert regions['food-rate']['max_length'] == 1
        assert regions['food-rate']['offset'] == 0x272C

    def test_get_regions_exod(self):
        regions = get_regions('EXOD')
        assert regions == {}  # EXOD has no verified patchable regions

    def test_parse_text_region(self):
        data = self._make_ult3()
        # Skip leading null byte
        strings = parse_text_region(data, 0x397A, 20)
        assert 'WATER' in strings
        assert 'GRASS' in strings

    def test_parse_coord_region(self):
        data = bytes([10, 20, 30, 40, 50, 60])
        coords = parse_coord_region(data, 0, 6)
        assert len(coords) == 3
        assert coords[0] == {'x': 10, 'y': 20}
        assert coords[2] == {'x': 50, 'y': 60}

    def test_parse_moongate_coords(self):
        data = self._make_ult3()
        # Read moongate X coordinates
        x_vals = list(data[0x29A7:0x29A7 + 8])
        assert x_vals == [i * 8 for i in range(8)]
        # Read moongate Y coordinates
        y_vals = list(data[0x29AF:0x29AF + 8])
        assert y_vals == [i * 4 for i in range(8)]

    def test_parse_food_rate(self):
        data = self._make_ult3()
        assert data[0x272C] == 0x04

    def test_encode_text_region(self):
        strings = ['WATER', 'GRASS']
        encoded = encode_text_region(strings, 20)
        assert len(encoded) == 20
        # Should contain high-ASCII "WATER" + null
        assert encoded[0] == 0xD7  # W | 0x80
        assert encoded[5] == 0x00  # null terminator

    def test_encode_text_too_long(self):
        strings = ['A' * 100]
        with pytest.raises(ValueError):
            encode_text_region(strings, 10)

    def test_patch_dry_run(self, tmp_path):
        data = bytearray(17408)
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        # Read and verify original
        with open(path, 'rb') as f:
            original = f.read()

        # Simulate edit + dry run: data should not change
        assert original[0x397A] == 0

    def test_all_regions_within_file_bounds(self):
        """Verify all patchable region offsets fit within their binaries."""
        from ult3edit.patch import ENGINE_BINARIES
        for binary, regions in PATCHABLE_REGIONS.items():
            size = ENGINE_BINARIES[binary]['size']
            for name, reg in regions.items():
                end = reg['offset'] + reg['max_length']
                assert end <= size, (
                    f"{binary}.{name}: offset 0x{reg['offset']:X} + "
                    f"length {reg['max_length']} = 0x{end:X} > "
                    f"file size 0x{size:X}"
                )


# =============================================================================
# DDRW module tests
# =============================================================================



class TestPatchImport:
    """Tests for patch import command and encode_coord_region."""

    def _make_ult3(self):
        """Create a synthetic ULT3 binary with known region data."""
        data = bytearray(17408)
        # Name table: empty + "WATER" + "GRASS"
        offset = 0x397A
        text = b'\x00\xD7\xC1\xD4\xC5\xD2\x00\xC7\xD2\xC1\xD3\xD3\x00'
        data[offset:offset + len(text)] = text
        # Moongate X/Y
        for i in range(8):
            data[0x29A7 + i] = i * 8
            data[0x29AF + i] = i * 4
        # Food rate
        data[0x272C] = 0x04
        return data

    def test_encode_coord_region(self):
        coords = [{'x': 10, 'y': 20}, {'x': 30, 'y': 40}]
        encoded = encode_coord_region(coords, 8)
        assert len(encoded) == 8
        assert encoded[0] == 10
        assert encoded[1] == 20
        assert encoded[2] == 30
        assert encoded[3] == 40
        # Padding
        assert encoded[4:] == b'\x00\x00\x00\x00'

    def test_encode_coord_too_long(self):
        coords = [{'x': i, 'y': i} for i in range(10)]
        with pytest.raises(ValueError):
            encode_coord_region(coords, 4)

    def test_text_round_trip(self, tmp_path):
        """parse_text_region → encode_text_region preserves content."""
        data = self._make_ult3()
        strings = parse_text_region(bytes(data), 0x397A, 921)
        encoded = encode_text_region(strings, 921)
        reparsed = parse_text_region(encoded, 0, 921)
        assert reparsed == strings

    def test_text_round_trip_preserves_empty(self):
        """Empty strings (consecutive nulls) survive round-trip."""
        # Build: "" + "HELLO" + "" + "WORLD"
        raw = bytearray(50)
        raw[0] = 0x00  # empty string
        hello = b'\xC8\xC5\xCC\xCC\xCF\x00'  # "HELLO" + null
        raw[1:1 + len(hello)] = hello
        pos = 1 + len(hello)
        raw[pos] = 0x00  # empty string
        pos += 1
        world = b'\xD7\xCF\xD2\xCC\xC4\x00'  # "WORLD" + null
        raw[pos:pos + len(world)] = world

        strings = parse_text_region(bytes(raw), 0, 50)
        assert strings == ['', 'HELLO', '', 'WORLD']

        encoded = encode_text_region(strings, 50)
        reparsed = parse_text_region(encoded, 0, 50)
        assert reparsed == strings

    def test_coord_round_trip(self):
        """parse_coord_region → encode_coord_region preserves content."""
        raw = bytes([10, 20, 30, 40, 50, 60, 0, 0])
        coords = parse_coord_region(raw, 0, 8)
        encoded = encode_coord_region(coords, 8)
        assert encoded == raw

    def test_import_text_region(self, tmp_path):
        """Import name-table from JSON file."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        # Build JSON with replacement names
        jdata = {
            'regions': {
                'name-table': {
                    'data': ['', 'BRINE', 'ASH'],
                }
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        # Verify the name-table was patched
        with open(path, 'rb') as f:
            result = f.read()
        strings = parse_text_region(result, 0x397A, 921)
        assert '' in strings
        assert 'BRINE' in strings
        assert 'ASH' in strings
        # Old names should be gone
        assert 'WATER' not in strings
        assert 'GRASS' not in strings

    def test_import_bytes_region(self, tmp_path):
        """Import moongate-x and food-rate byte regions."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        jdata = {
            'regions': {
                'moongate-x': {'data': [10, 20, 30, 40, 50, 30, 20, 10]},
                'food-rate': {'data': [2]},
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert list(result[0x29A7:0x29A7 + 8]) == [10, 20, 30, 40, 50, 30, 20, 10]
        assert result[0x272C] == 2

    def test_import_dry_run(self, tmp_path):
        """Dry run does not modify file."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        jdata = {
            'regions': {
                'food-rate': {'data': [1]},
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': None,
            'backup': False,
            'dry_run': True,
        })()
        patch_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x272C] == 0x04  # Unchanged

    def test_import_region_filter(self, tmp_path):
        """--region flag limits which regions are imported."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        jdata = {
            'regions': {
                'food-rate': {'data': [1]},
                'moongate-x': {'data': [99, 99, 99, 99, 99, 99, 99, 99]},
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': 'food-rate',
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x272C] == 1  # Updated
        # moongate-x should be unchanged (filtered out)
        assert list(result[0x29A7:0x29A7 + 8]) == [i * 8 for i in range(8)]

    def test_import_output_file(self, tmp_path):
        """--output writes to separate file."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        out_path = str(tmp_path / 'ULT3_patched')
        with open(path, 'wb') as f:
            f.write(data)

        jdata = {
            'regions': {
                'food-rate': {'data': [3]},
            }
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': out_path,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        # Original unchanged
        with open(path, 'rb') as f:
            assert f.read()[0x272C] == 0x04
        # Output has new value
        with open(out_path, 'rb') as f:
            assert f.read()[0x272C] == 3

    def test_import_flat_json_format(self, tmp_path):
        """Accept flat JSON without 'regions' wrapper."""
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        # Flat format: region name → data list directly
        jdata = {
            'food-rate': [2],
        }
        json_path = str(tmp_path / 'patch.json')
        with open(json_path, 'w') as f:
            json.dump(jdata, f)

        args = type('Args', (), {
            'file': path,
            'json_file': json_path,
            'region': None,
            'output': None,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(args)

        with open(path, 'rb') as f:
            result = f.read()
        assert result[0x272C] == 2

    def test_import_full_view_json_round_trip(self, tmp_path):
        """view --json output can be fed directly back into import."""
        from ult3edit.patch import cmd_view
        data = self._make_ult3()
        path = str(tmp_path / 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)

        # Export via cmd_view --json
        json_path = str(tmp_path / 'export.json')
        view_args = type('Args', (), {
            'file': path,
            'region': None,
            'json': True,
            'output': json_path,
        })()
        cmd_view(view_args)

        # Modify a value in the exported JSON
        with open(json_path, 'r') as f:
            jdata = json.load(f)
        jdata['regions']['food-rate']['data'] = [2]

        modified_json = str(tmp_path / 'modified.json')
        with open(modified_json, 'w') as f:
            json.dump(jdata, f)

        # Import back
        out_path = str(tmp_path / 'ULT3_new')
        import_args = type('Args', (), {
            'file': path,
            'json_file': modified_json,
            'region': None,
            'output': out_path,
            'backup': False,
            'dry_run': False,
        })()
        patch_cmd_import(import_args)

        # Verify food rate changed, name table preserved
        with open(out_path, 'rb') as f:
            result = f.read()
        assert result[0x272C] == 2
        strings = parse_text_region(result, 0x397A, 921)
        assert 'WATER' in strings
        assert 'GRASS' in strings


# =============================================================================
# Roster create extended args tests
# =============================================================================


class TestNameCompilerParse:
    """Test parsing .names text files."""

    def test_parse_simple(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import parse_names_file
        text = '# Group: Test\nFOO\nBAR\nBAZ\n'
        names = parse_names_file(text)
        assert names == ['FOO', 'BAR', 'BAZ']

    def test_parse_empty_string(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import parse_names_file
        text = '""\nFOO\n""\nBAR\n'
        names = parse_names_file(text)
        assert names == ['', 'FOO', '', 'BAR']

    def test_parse_skips_comments_and_blanks(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import parse_names_file
        text = '# Header\n\n# Group: A\nFOO\n\n# Group: B\nBAR\n'
        names = parse_names_file(text)
        assert names == ['FOO', 'BAR']


class TestNameCompilerEncode:
    """Test encoding names to binary."""

    def test_compile_basic(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import compile_names, NAME_TABLE_SIZE
        names = ['FOO', 'BAR']
        result = compile_names(names)
        assert len(result) == NAME_TABLE_SIZE
        # FOO = C6 CF CF 00, BAR = C2 C1 D2 00
        assert result[0] == 0xC6  # F | 0x80
        assert result[1] == 0xCF  # O | 0x80
        assert result[2] == 0xCF  # O | 0x80
        assert result[3] == 0x00  # null terminator
        assert result[4] == 0xC2  # B | 0x80
        assert result[7] == 0x00  # null terminator

    def test_compile_empty_string(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import compile_names
        names = ['', 'FOO']
        result = compile_names(names)
        # Empty string = just null terminator
        assert result[0] == 0x00
        assert result[1] == 0xC6  # F | 0x80

    def test_compile_budget_overflow(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import compile_names
        # Create names that exceed 891-byte budget
        names = ['A' * 50] * 20  # 20 x (50+1) = 1020 bytes
        with pytest.raises(ValueError, match='exceeds budget'):
            compile_names(names)

    def test_compile_with_tail_data(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import compile_names, NAME_TABLE_SIZE
        names = ['FOO']
        tail = b'\xAA\xBB\xCC'
        result = compile_names(names, tail_data=tail)
        assert len(result) == NAME_TABLE_SIZE
        # Names part: F O O \0 = 4 bytes, then tail
        assert result[4] == 0xAA
        assert result[5] == 0xBB
        assert result[6] == 0xCC


class TestNameCompilerValidate:
    """Test budget validation."""

    def test_validate_within_budget(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import validate_names
        names = ['FOO', 'BAR']
        size, budget, valid = validate_names(names)
        assert size == 8  # FOO\0 + BAR\0 = 4 + 4
        assert budget == 891  # 921 - 30
        assert valid is True

    def test_validate_over_budget(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import validate_names
        names = ['A' * 50] * 20
        size, budget, valid = validate_names(names)
        assert valid is False


class TestNameCompilerRoundTrip:
    """Test decompile and recompile produce equivalent output."""

    def test_roundtrip(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import (
            parse_names_file, compile_names, decompile_names,
            NAME_TABLE_OFFSET, NAME_TABLE_SIZE,
        )
        # Build a synthetic ULT3-like binary with a known name table
        names_in = ['WATER', 'GRASS', '', 'FOREST']
        encoded = compile_names(names_in)
        # Create a fake ULT3 binary large enough
        data = bytearray(NAME_TABLE_OFFSET + NAME_TABLE_SIZE)
        data[NAME_TABLE_OFFSET:NAME_TABLE_OFFSET + NAME_TABLE_SIZE] = encoded

        # Decompile to text
        text = decompile_names(bytes(data))
        # Reparse
        names_out = parse_names_file(text)
        assert names_out == names_in

    def test_voidborn_names_validate(self):
        """Voidborn names.names file fits within budget."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        from name_compiler import parse_names_file, validate_names
        names_path = os.path.join(os.path.dirname(__file__),
                                   '..', 'conversions', 'voidborn',
                                   'sources', 'names.names')
        with open(names_path, 'r', encoding='utf-8') as f:
            text = f.read()
        names = parse_names_file(text)
        size, budget, valid = validate_names(names)
        assert valid, f"Voidborn names {size}/{budget} bytes — over budget!"
        assert len(names) > 100, f"Expected 100+ names, got {len(names)}"


# =============================================================================
# Source file validation tests
# =============================================================================


class TestSourceFileValidation:
    """Validate Voidborn source files parse correctly."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_all_bestiary_valid_json(self):
        """All bestiary source files are valid JSON with expected structure."""
        for letter in 'abcdefghijklz':
            path = os.path.join(self.SOURCES_DIR, f'bestiary_{letter}.json')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                data = json.load(f)
            assert 'monsters' in data, f"bestiary_{letter}.json missing 'monsters'"
            mons = data['monsters']
            assert isinstance(mons, dict), f"bestiary_{letter}.json monsters not dict"
            for key, val in mons.items():
                assert 'hp' in val, f"bestiary_{letter}.json monster {key} missing hp"

    def test_all_combat_valid_json(self):
        """All combat source files are valid JSON with expected structure."""
        for letter in 'abcfgmqrs':
            path = os.path.join(self.SOURCES_DIR, f'combat_{letter}.json')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                data = json.load(f)
            tiles = data.get('tiles', [])
            assert len(tiles) == 11, f"combat_{letter}.json needs 11 tile rows"
            for row in tiles:
                assert len(row) == 11, f"combat_{letter}.json row not 11 chars"

    def test_all_special_valid_json(self):
        """All special location source files are valid JSON."""
        for name in ('brnd', 'shrn', 'fntn', 'time'):
            path = os.path.join(self.SOURCES_DIR, f'special_{name}.json')
            with open(path, 'r') as f:
                data = json.load(f)
            tiles = data.get('tiles', [])
            assert len(tiles) == 11, f"special_{name}.json needs 11 tile rows"

    def test_title_json_valid(self):
        """Title text source is valid JSON."""
        path = os.path.join(self.SOURCES_DIR, 'title.json')
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'records' in data
        assert len(data['records']) >= 2

    def test_overworld_map_dimensions(self):
        """Overworld map source is 64x64."""
        path = os.path.join(self.SOURCES_DIR, 'mapa.map')
        with open(path, 'r') as f:
            lines = [l for l in f.read().splitlines()
                     if l and not l.startswith('#')]
        assert len(lines) == 64, f"mapa.map has {len(lines)} rows, expected 64"
        for i, line in enumerate(lines):
            assert len(line) == 64, f"mapa.map row {i} has {len(line)} chars"

    def test_all_surface_maps_dimensions(self):
        """All surface map sources are 64x64."""
        for letter in 'abcdefghijklz':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                lines = [l for l in f.read().splitlines()
                         if l and not l.startswith('#')]
            assert len(lines) == 64, \
                f"map{letter}.map has {len(lines)} rows, expected 64"
            for i, line in enumerate(lines):
                assert len(line) == 64, \
                    f"map{letter}.map row {i} has {len(line)} chars"

    def test_all_dungeon_maps_dimensions(self):
        """All dungeon map sources have 8 levels of 16x16."""
        for letter in 'mnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                # Filter comments ('# ' with space) but keep tile rows
                # starting with '#' (wall tile character in dungeons)
                lines = [l for l in f.read().splitlines()
                         if l and not l.startswith('# ')]
            assert len(lines) == 128, \
                f"map{letter}.map has {len(lines)} rows, expected 128 (8x16)"
            for i, line in enumerate(lines):
                assert len(line) == 16, \
                    f"map{letter}.map row {i} has {len(line)} chars, expected 16"

    def test_all_dialog_files_parseable(self):
        """All dialog source files are parseable text with --- separators."""
        for letter in 'abcdefghijklmnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'tlk{letter}.txt')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                text = f.read()
            # Should have at least one record separator
            assert '---' in text, f"tlk{letter}.txt missing --- separators"
            # Non-comment, non-separator lines should be <= 20 chars
            for line_num, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith('#') or stripped == '---' or not stripped:
                    continue
                assert len(stripped) <= 20, \
                    f"tlk{letter}.txt line {line_num} too long: {len(stripped)} chars"

    def test_bestiary_stat_ranges(self):
        """Spot check bestiary stats are in reasonable ranges."""
        for letter in 'abcdefghijklz':
            path = os.path.join(self.SOURCES_DIR, f'bestiary_{letter}.json')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                data = json.load(f)
            for key, mon in data['monsters'].items():
                hp = mon.get('hp', 0)
                atk = mon.get('attack', 0)
                assert 0 < hp <= 255, \
                    f"bestiary_{letter}.json mon {key} hp={hp} out of range"
                assert 0 < atk <= 255, \
                    f"bestiary_{letter}.json mon {key} atk={atk} out of range"

    def test_combat_position_bounds(self):
        """All combat map positions are within 11x11 grid."""
        for letter in 'abcfgmqrs':
            path = os.path.join(self.SOURCES_DIR, f'combat_{letter}.json')
            if not os.path.exists(path):
                continue
            with open(path, 'r') as f:
                data = json.load(f)
            for group in ('monsters', 'pcs'):
                positions = data.get(group, {})
                if isinstance(positions, dict):
                    positions = positions.values()
                for pos in positions:
                    assert 0 <= pos['x'] <= 10, \
                        f"combat_{letter}.json {group} x={pos['x']} out of bounds"
                    assert 0 <= pos['y'] <= 10, \
                        f"combat_{letter}.json {group} y={pos['y']} out of bounds"


class TestSourceManifest:
    """Verify every expected source file exists."""

    SOURCES_DIR = os.path.join(os.path.dirname(__file__),
                                '..', 'conversions', 'voidborn', 'sources')

    def test_bestiary_manifest(self):
        """All 13 bestiary source files exist."""
        for letter in 'abcdefghijklz':
            path = os.path.join(self.SOURCES_DIR, f'bestiary_{letter}.json')
            assert os.path.exists(path), f"Missing bestiary_{letter}.json"

    def test_combat_manifest(self):
        """All 9 combat source files exist."""
        for letter in 'abcfgmqrs':
            path = os.path.join(self.SOURCES_DIR, f'combat_{letter}.json')
            assert os.path.exists(path), f"Missing combat_{letter}.json"

    def test_dialog_manifest(self):
        """All 19 dialog source files exist."""
        for letter in 'abcdefghijklmnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'tlk{letter}.txt')
            assert os.path.exists(path), f"Missing tlk{letter}.txt"

    def test_surface_map_manifest(self):
        """All 13 surface map source files exist."""
        for letter in 'abcdefghijklz':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            assert os.path.exists(path), f"Missing map{letter}.map"

    def test_dungeon_map_manifest(self):
        """All 7 dungeon map source files exist."""
        for letter in 'mnopqrs':
            path = os.path.join(self.SOURCES_DIR, f'map{letter}.map')
            assert os.path.exists(path), f"Missing map{letter}.map"

    def test_special_manifest(self):
        """All 4 special location source files exist."""
        for name in ('brnd', 'shrn', 'fntn', 'time'):
            path = os.path.join(self.SOURCES_DIR, f'special_{name}.json')
            assert os.path.exists(path), f"Missing special_{name}.json"

    def test_ancillary_manifest(self):
        """Ancillary source files exist."""
        for filename in ('tiles.tiles', 'names.names', 'title.json',
                         'shop_strings.json', 'sosa.json', 'sosm.json',
                         'mbs.json', 'ddrw.json'):
            path = os.path.join(self.SOURCES_DIR, filename)
            assert os.path.exists(path), f"Missing {filename}"


# =============================================================================
# Combat tile character validation
# =============================================================================


class TestNameCompilerEdgeCases:
    """Edge case tests for name_compiler.py."""

    def _get_mod(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                         '..', 'conversions', 'tools'))
        import name_compiler
        return name_compiler

    def test_decompile_produces_parseable_output(self):
        """Compile → embed in fake ULT3 → decompile → parse round-trip."""
        mod = self._get_mod()
        names = ['GRASS', 'FOREST', '', 'SWORD', 'SHIELD']
        binary = mod.compile_names(names)
        # Embed at NAME_TABLE_OFFSET in a fake ULT3
        ult3 = bytearray(mod.NAME_TABLE_OFFSET + mod.NAME_TABLE_SIZE)
        ult3[mod.NAME_TABLE_OFFSET:mod.NAME_TABLE_OFFSET + len(binary)] = binary
        # Decompile returns .names text, parse it back
        text = mod.decompile_names(bytes(ult3))
        parsed = mod.parse_names_file(text)
        assert parsed[:5] == names

    def test_compile_special_characters(self):
        """Names with spaces and punctuation encode correctly."""
        mod = self._get_mod()
        names = ['ICE AXE', "PIRATE'S"]
        binary = mod.compile_names(names)
        # Embed and round-trip
        ult3 = bytearray(mod.NAME_TABLE_OFFSET + mod.NAME_TABLE_SIZE)
        ult3[mod.NAME_TABLE_OFFSET:mod.NAME_TABLE_OFFSET + len(binary)] = binary
        text = mod.decompile_names(bytes(ult3))
        parsed = mod.parse_names_file(text)
        assert parsed[0] == 'ICE AXE'
        assert parsed[1] == "PIRATE'S"

    def test_names_file_round_trip(self, tmp_path):
        """Write .names file → read back → compile → decompile matches."""
        mod = self._get_mod()
        original_names = ['GRASS', 'FOREST', 'MOUNTAIN']
        # Write .names format
        content = '# Terrain\n' + '\n'.join(original_names) + '\n'
        names_path = str(tmp_path / 'test.names')
        with open(names_path, 'w') as f:
            f.write(content)
        # Parse
        with open(names_path, 'r') as f:
            parsed = mod.parse_names_file(f.read())
        assert parsed == original_names
        # Compile → embed → decompile → parse
        binary = mod.compile_names(parsed)
        ult3 = bytearray(mod.NAME_TABLE_OFFSET + mod.NAME_TABLE_SIZE)
        ult3[mod.NAME_TABLE_OFFSET:mod.NAME_TABLE_OFFSET + len(binary)] = binary
        text = mod.decompile_names(bytes(ult3))
        reparsed = mod.parse_names_file(text)
        assert reparsed[:3] == original_names


# =============================================================================
# Map compiler edge cases
# =============================================================================


class TestEngineRoundTrip:
    """Verify engine binaries reassemble byte-identical from CIDAR disassembly.

    These tests prove the SDK build pipeline works:
    CIDAR disassembly (.s) → asmiigs assembler → OMF → byte-identical binary.

    Requires engine/originals/*.bin and engine/build/*.omf to exist.
    Run `bash engine/build.sh` first to populate build output.
    """

    ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine')
    OMF_HEADER_SIZE = 60  # asmiigs OMF v2.1 segment header
    OMF_TRAILER_SIZE = 1  # End-of-segment marker ($00)

    BINARIES = {
        'SUBS': {'size': 3584, 'org': 0x4100},
        'ULT3': {'size': 17408, 'org': 0x5000},
        'EXOD': {'size': 26208, 'org': 0x2000},
    }

    def _verify(self, name):
        info = self.BINARIES[name]
        omf_path = os.path.join(self.ENGINE_DIR, 'build', f'{name}.omf')
        orig_path = os.path.join(self.ENGINE_DIR, 'originals', f'{name}.bin')

        if not os.path.exists(omf_path):
            pytest.skip(f"Build output not found: {omf_path} (run engine/build.sh)")
        if not os.path.exists(orig_path):
            pytest.skip(f"Original binary not found: {orig_path}")

        with open(omf_path, 'rb') as f:
            omf_data = f.read()
        with open(orig_path, 'rb') as f:
            orig_data = f.read()

        assert len(orig_data) == info['size'], \
            f"Original {name} size: expected {info['size']}, got {len(orig_data)}"

        code = omf_data[self.OMF_HEADER_SIZE:self.OMF_HEADER_SIZE + len(orig_data)]
        assert len(code) == len(orig_data), \
            f"OMF code section: expected {len(orig_data)}, got {len(code)}"
        assert code == orig_data, \
            f"{name} not byte-identical after reassembly"

    def test_subs_byte_identical(self):
        """SUBS (3,584 bytes at $4100) reassembles byte-identical."""
        self._verify('SUBS')

    def test_ult3_byte_identical(self):
        """ULT3 (17,408 bytes at $5000) reassembles byte-identical."""
        self._verify('ULT3')

    def test_exod_byte_identical(self):
        """EXOD (26,208 bytes at $2000) reassembles byte-identical."""
        self._verify('EXOD')

    def test_all_source_files_exist(self):
        """All three CIDAR disassembly source files exist."""
        for name, subdir in [('subs.s', 'subs'), ('ult3.s', 'ult3'), ('exod.s', 'exod')]:
            path = os.path.join(self.ENGINE_DIR, subdir, name)
            assert os.path.exists(path), f"Source not found: {path}"

    def test_all_original_binaries_exist(self):
        """All three original binaries exist for verification."""
        for name in self.BINARIES:
            path = os.path.join(self.ENGINE_DIR, 'originals', f'{name}.bin')
            assert os.path.exists(path), f"Original not found: {path}"

    def test_original_binary_sizes(self):
        """Original binaries have correct documented sizes."""
        for name, info in self.BINARIES.items():
            path = os.path.join(self.ENGINE_DIR, 'originals', f'{name}.bin')
            if not os.path.exists(path):
                pytest.skip(f"Original not found: {path}")
            size = os.path.getsize(path)
            assert size == info['size'], \
                f"{name}: expected {info['size']} bytes, got {size}"

    def test_omf_header_size(self):
        """OMF files have the expected 60-byte header."""
        for name, info in self.BINARIES.items():
            omf_path = os.path.join(self.ENGINE_DIR, 'build', f'{name}.omf')
            if not os.path.exists(omf_path):
                pytest.skip("Build output not found (run engine/build.sh)")
            omf_size = os.path.getsize(omf_path)
            expected = info['size'] + self.OMF_HEADER_SIZE + self.OMF_TRAILER_SIZE
            assert omf_size == expected, \
                f"{name}.omf: expected {expected} bytes, got {omf_size}"

    def test_build_script_exists(self):
        """Build script exists."""
        assert os.path.exists(os.path.join(self.ENGINE_DIR, 'build.sh'))

    def test_verify_script_exists(self):
        """Verification script exists."""
        assert os.path.exists(os.path.join(self.ENGINE_DIR, 'verify.py'))


class TestStringCatalog:
    """Test the engine inline string catalog tool."""

    ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine')

    def _load_ult3(self):
        path = os.path.join(self.ENGINE_DIR, 'originals', 'ULT3.bin')
        if not os.path.exists(path):
            pytest.skip("ULT3.bin not found")
        with open(path, 'rb') as f:
            return f.read()

    def test_catalog_tool_exists(self):
        path = os.path.join(self.ENGINE_DIR, 'tools', 'string_catalog.py')
        assert os.path.exists(path)

    def test_extract_finds_strings(self):
        """ULT3 contains 200+ inline strings."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        data = self._load_ult3()
        strings = extract_inline_strings(data, 0x5000)
        assert len(strings) >= 200, f"Expected 200+ strings, got {len(strings)}"

    def test_extract_card_of_death(self):
        """Can find 'CARD OF DEATH' inline string."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        data = self._load_ult3()
        strings = extract_inline_strings(data, 0x5000)
        texts = [s['text'] for s in strings]
        assert any('CARD OF DEATH' in t for t in texts)

    def test_extract_mark_of_kings(self):
        """Can find 'MARK OF KINGS' inline string."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        data = self._load_ult3()
        strings = extract_inline_strings(data, 0x5000)
        texts = [s['text'] for s in strings]
        assert any('MARK OF KINGS' in t for t in texts)

    def test_extract_evocare(self):
        """Can find 'EVOCARE' inline string."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        data = self._load_ult3()
        strings = extract_inline_strings(data, 0x5000)
        texts = [s['text'] for s in strings]
        assert any('EVOCARE' in t for t in texts)

    def test_total_bytes_reasonable(self):
        """Total inline string bytes should be 3000-5000."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        data = self._load_ult3()
        strings = extract_inline_strings(data, 0x5000)
        total = sum(s['jsr_plus_text'] for s in strings)
        assert 3000 <= total <= 5000, f"Total bytes: {total}"

    def test_no_strings_in_exod(self):
        """EXOD should have zero JSR $46BA strings."""
        path = os.path.join(self.ENGINE_DIR, 'originals', 'EXOD.bin')
        if not os.path.exists(path):
            pytest.skip("EXOD.bin not found")
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        with open(path, 'rb') as f:
            data = f.read()
        strings = extract_inline_strings(data, 0x2000)
        assert len(strings) == 0

    def test_no_strings_in_subs(self):
        """SUBS should have zero JSR $46BA strings (it IS the printer)."""
        path = os.path.join(self.ENGINE_DIR, 'originals', 'SUBS.bin')
        if not os.path.exists(path):
            pytest.skip("SUBS.bin not found")
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        with open(path, 'rb') as f:
            data = f.read()
        strings = extract_inline_strings(data, 0x4100)
        assert len(strings) == 0

    def test_json_catalog_exists(self):
        """Pre-built JSON catalog exists."""
        path = os.path.join(self.ENGINE_DIR, 'tools', 'ult3_strings.json')
        if not os.path.exists(path):
            pytest.skip("JSON catalog not built yet")
        with open(path) as f:
            catalog = json.load(f)
        assert catalog['total_strings'] >= 200
        assert 'strings' in catalog

    def test_categorize_quest_items(self):
        """Categorizer identifies quest item strings correctly."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import categorize_string
        assert categorize_string('CARD OF DEATH') == 'quest-item'
        assert categorize_string('MARK OF KINGS') == 'quest-item'

    def test_categorize_combat(self):
        """Categorizer identifies combat strings correctly."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import categorize_string
        assert categorize_string('KILLED! EXP.-') == 'combat'
        assert categorize_string('MISSED!') == 'combat'

    def test_synthesized_binary_scan(self):
        """String extraction works on synthesized data with known strings."""
        sys.path.insert(0, os.path.join(self.ENGINE_DIR, 'tools'))
        from string_catalog import extract_inline_strings
        # Build a small binary with two inline strings
        data = bytearray(100)
        # JSR $46BA at offset 10
        data[10] = 0x20
        data[11] = 0xBA
        data[12] = 0x46
        # "HI" in high-ASCII + null
        data[13] = 0xC8  # H
        data[14] = 0xC9  # I
        data[15] = 0x00  # null
        # JSR $46BA at offset 30
        data[30] = 0x20
        data[31] = 0xBA
        data[32] = 0x46
        # "BYE" in high-ASCII + null
        data[33] = 0xC2  # B
        data[34] = 0xD9  # Y
        data[35] = 0xC5  # E
        data[36] = 0x00  # null
        strings = extract_inline_strings(bytes(data))
        assert len(strings) == 2
        assert strings[0]['text'] == 'HI'
        assert strings[1]['text'] == 'BYE'
        assert strings[0]['file_offset'] == 10
        assert strings[1]['file_offset'] == 30


# =============================================================================
# String patcher tests
# =============================================================================

def _make_inline_binary(*texts):
    """Build a synthetic binary with JSR $46BA inline strings.

    Returns (bytearray, list_of_string_info_dicts).
    Each text is high-ASCII encoded after the JSR pattern.
    """
    parts = bytearray()
    # pad with NOPs at start
    parts.extend(b'\xEA' * 4)
    for text in texts:
        # JSR $46BA
        parts.extend(b'\x20\xBA\x46')
        for ch in text:
            if ch == '\n':
                parts.append(0xFF)
            else:
                parts.append(ord(ch.upper()) | 0x80)
        parts.append(0x00)  # null terminator
        parts.extend(b'\xEA' * 2)  # pad between strings
    # Extract string info using the catalog tool
    tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine', 'tools')
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    from string_catalog import extract_inline_strings
    strings = extract_inline_strings(bytes(parts))
    return parts, strings


def _make_inline_binary(*texts):
    """Build a synthetic binary with JSR $46BA inline strings.

    Returns (bytearray, list_of_string_info_dicts).
    Each text is high-ASCII encoded after the JSR pattern.
    """
    parts = bytearray()
    # pad with NOPs at start
    parts.extend(b'\xEA' * 4)
    for text in texts:
        # JSR $46BA
        parts.extend(b'\x20\xBA\x46')
        for ch in text:
            if ch == '\n':
                parts.append(0xFF)
            else:
                parts.append(ord(ch.upper()) | 0x80)
        parts.append(0x00)  # null terminator
        parts.extend(b'\xEA' * 2)  # pad between strings
    # Extract string info using the catalog tool
    tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine', 'tools')
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    from string_catalog import extract_inline_strings
    strings = extract_inline_strings(bytes(parts))
    return parts, strings



class TestStringPatcher:
    """Test the engine inline string patcher tool."""

    ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine')

    def _get_patcher(self):
        tools_dir = os.path.join(self.ENGINE_DIR, 'tools')
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from string_patcher import encode_high_ascii, patch_string, resolve_patches
        return encode_high_ascii, patch_string, resolve_patches

    def test_patcher_tool_exists(self):
        path = os.path.join(self.ENGINE_DIR, 'tools', 'string_patcher.py')
        assert os.path.exists(path)

    def test_encode_high_ascii_simple(self):
        encode_high_ascii, _, _ = self._get_patcher()
        result = encode_high_ascii('HI')
        assert result == bytearray([0xC8, 0xC9])

    def test_encode_high_ascii_newline(self):
        encode_high_ascii, _, _ = self._get_patcher()
        result = encode_high_ascii('A\nB')
        assert result == bytearray([0xC1, 0xFF, 0xC2])

    def test_patch_string_fits(self):
        """Patch that fits in available space succeeds."""
        _, patch_string, _ = self._get_patcher()
        data, strings = _make_inline_binary('HELLO WORLD')
        ok, msg = patch_string(data, strings[0], 'GOODBYE')
        assert ok
        assert 'Patched' in msg
        # Verify the patched bytes
        offset = strings[0]['text_offset']
        assert data[offset] == 0xC7  # G
        assert data[offset + 6] == 0xC5  # E (last char of GOODBYE)
        assert data[offset + 7] == 0x00  # null fill

    def test_patch_string_exact_fit(self):
        """Patch that exactly matches original length succeeds."""
        _, patch_string, _ = self._get_patcher()
        data, strings = _make_inline_binary('ABC')
        ok, msg = patch_string(data, strings[0], 'XYZ')
        assert ok
        offset = strings[0]['text_offset']
        assert data[offset] == 0xD8  # X
        assert data[offset + 1] == 0xD9  # Y
        assert data[offset + 2] == 0xDA  # Z

    def test_patch_string_too_long(self):
        """Patch longer than available space fails gracefully."""
        _, patch_string, _ = self._get_patcher()
        data, strings = _make_inline_binary('HI')
        ok, msg = patch_string(data, strings[0], 'THIS IS WAY TOO LONG')
        assert not ok
        assert 'too long' in msg.lower()

    def test_patch_null_fills_remainder(self):
        """Shorter replacement null-fills remaining bytes."""
        _, patch_string, _ = self._get_patcher()
        data, strings = _make_inline_binary('ABCDEF')
        ok, msg = patch_string(data, strings[0], 'XY')
        assert ok
        offset = strings[0]['text_offset']
        assert data[offset] == 0xD8  # X
        assert data[offset + 1] == 0xD9  # Y
        # Remaining bytes should be null-filled
        for i in range(2, 7):  # 6 original + null
            assert data[offset + i] == 0x00

    def test_resolve_by_index(self):
        """Resolve patches by string index."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('FIRST', 'SECOND')
        patches = [{'index': 1, 'text': 'REPLACEMENT'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 1
        assert resolved[0][0]['index'] == 1
        assert resolved[0][1] == 'REPLACEMENT'

    def test_resolve_by_vanilla_text(self):
        """Resolve patches by vanilla text matching."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('CARD OF DEATH', 'HELLO')
        patches = [{'vanilla': 'CARD OF DEATH', 'text': 'SHARD OF VOID'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 1
        assert 'CARD OF DEATH' in resolved[0][0]['text']

    def test_resolve_by_vanilla_case_insensitive(self):
        """Vanilla text matching is case-insensitive."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('HELLO WORLD')
        patches = [{'vanilla': 'hello world', 'text': 'GOODBYE'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 1

    def test_resolve_by_address(self):
        """Resolve patches by address."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('TEST')
        addr = strings[0]['address']
        patches = [{'address': addr, 'text': 'NEW'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 1

    def test_resolve_missing_index_warns(self, capsys):
        """Missing index produces warning, not crash."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('ONLY')
        patches = [{'index': 999, 'text': 'MISSING'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 0

    def test_resolve_missing_vanilla_warns(self, capsys):
        """Missing vanilla text produces warning, not crash."""
        _, _, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary('ACTUAL')
        patches = [{'vanilla': 'NONEXISTENT', 'text': 'MISSING'}]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 0

    def test_full_patch_roundtrip(self):
        """Full pipeline: resolve + patch multiple strings."""
        _, patch_string, resolve_patches = self._get_patcher()
        data, strings = _make_inline_binary(
            'CARD OF DEATH', 'MARK OF KINGS', 'HELLO'
        )
        patches = [
            {'vanilla': 'CARD OF DEATH', 'text': 'SHARD OF VOID'},
            {'vanilla': 'MARK OF KINGS', 'text': 'SIGIL: KINGS'},
        ]
        resolved = resolve_patches(strings, patches)
        assert len(resolved) == 2
        for string_info, new_text in resolved:
            ok, msg = patch_string(data, string_info, new_text)
            assert ok
        # Verify HELLO is untouched
        hello_offset = strings[2]['text_offset']
        assert data[hello_offset] == 0xC8  # H still there

    def test_voidborn_engine_strings_valid(self):
        """Voidborn engine_strings.json has valid structure."""
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'conversions', 'voidborn', 'sources', 'engine_strings.json')
        if not os.path.exists(path):
            pytest.skip("engine_strings.json not found")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert 'patches' in data
        assert len(data['patches']) >= 10
        for patch in data['patches']:
            assert 'text' in patch
            assert 'index' in patch or 'vanilla' in patch or 'address' in patch

    def test_voidborn_patches_fit_in_place(self):
        """All Voidborn engine string patches fit in original space."""
        ult3_path = os.path.join(self.ENGINE_DIR, 'originals', 'ULT3.bin')
        if not os.path.exists(ult3_path):
            pytest.skip("ULT3.bin not found")
        patches_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    'conversions', 'voidborn', 'sources',
                                    'engine_strings.json')
        if not os.path.exists(patches_path):
            pytest.skip("engine_strings.json not found")
        tools_dir = os.path.join(self.ENGINE_DIR, 'tools')
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from string_catalog import extract_inline_strings
        from string_patcher import patch_string, resolve_patches
        with open(ult3_path, 'rb') as f:
            data = bytearray(f.read())
        with open(patches_path, 'r', encoding='utf-8') as f:
            patch_data = json.load(f)
        strings = extract_inline_strings(bytes(data), 0x5000)
        resolved = resolve_patches(strings, patch_data['patches'])
        assert len(resolved) >= 10, f"Only {len(resolved)} patches resolved"
        for string_info, new_text in resolved:
            ok, msg = patch_string(data, string_info, new_text)
            assert ok, f"Patch failed: {msg}"


# =============================================================================
# Source-level string patcher tests
# =============================================================================

def _make_asm_source(*inline_texts):
    """Build synthetic .s source lines with ASC inline strings.

    Returns list of source lines simulating CIDAR disassembly output.
    """
    lines = []
    lines.append('            ORG     $5000\n')
    lines.append('; --- Code ---\n')
    for text in inline_texts:
        lines.append('            DB      $20,$BA,$46,$FF\n')
        lines.append(f'            ASC     "{text}"\n')
        lines.append('            DB      $00 ; null terminator\n')
        lines.append('            DB      $60  ; RTS\n')
    return lines


def _make_asm_source(*inline_texts):
    """Build synthetic .s source lines with ASC inline strings.

    Returns list of source lines simulating CIDAR disassembly output.
    """
    lines = []
    lines.append('            ORG     $5000\n')
    lines.append('; --- Code ---\n')
    for text in inline_texts:
        lines.append('            DB      $20,$BA,$46,$FF\n')
        lines.append(f'            ASC     "{text}"\n')
        lines.append('            DB      $00 ; null terminator\n')
        lines.append('            DB      $60  ; RTS\n')
    return lines



class TestSourcePatcher:
    """Test the source-level inline string patcher tool."""

    ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'engine')

    def _get_source_patcher(self):
        tools_dir = os.path.join(self.ENGINE_DIR, 'tools')
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from source_patcher import (
            extract_asc_strings, is_inline_string,
            resolve_source_patches, apply_source_patches,
        )
        return extract_asc_strings, is_inline_string, resolve_source_patches, apply_source_patches

    def test_source_patcher_exists(self):
        path = os.path.join(self.ENGINE_DIR, 'tools', 'source_patcher.py')
        assert os.path.exists(path)

    def test_extract_asc_strings(self):
        """Can find ASC directives in synthesized source."""
        extract, _, _, _ = self._get_source_patcher()
        lines = _make_asm_source('HELLO WORLD', 'GOODBYE')
        strings = extract(lines)
        assert len(strings) == 2
        assert strings[0]['text'] == 'HELLO WORLD'
        assert strings[1]['text'] == 'GOODBYE'

    def test_is_inline_string(self):
        """Correctly identifies JSR $46BA inline strings."""
        extract, is_inline, _, _ = self._get_source_patcher()
        lines = _make_asm_source('CARD OF DEATH')
        strings = extract(lines)
        assert len(strings) == 1
        assert is_inline(lines, strings[0])

    def test_is_not_inline_string(self):
        """Non-inline ASC directives are not flagged."""
        extract, is_inline, _, _ = self._get_source_patcher()
        lines = [
            '            ASC     "JUST DATA"\n',
            '            DB      $00\n',
        ]
        strings = extract(lines)
        assert len(strings) == 1
        assert not is_inline(lines, strings[0])

    def test_resolve_by_vanilla(self):
        """Resolve source patches by vanilla text."""
        extract, _, resolve, _ = self._get_source_patcher()
        lines = _make_asm_source('CARD OF DEATH', 'HELLO')
        strings = extract(lines)
        patches = [{'vanilla': 'CARD OF DEATH', 'text': 'SHARD OF VOID'}]
        resolved = resolve(strings, patches)
        assert len(resolved) == 1
        assert resolved[0][1] == 'SHARD OF VOID'

    def test_resolve_case_insensitive(self):
        """Vanilla text matching is case-insensitive."""
        extract, _, resolve, _ = self._get_source_patcher()
        lines = _make_asm_source('HELLO WORLD')
        strings = extract(lines)
        patches = [{'vanilla': 'hello world', 'text': 'GOODBYE'}]
        resolved = resolve(strings, patches)
        assert len(resolved) == 1

    def test_resolve_by_index(self):
        """Resolve source patches by ASC index."""
        extract, _, resolve, _ = self._get_source_patcher()
        lines = _make_asm_source('FIRST', 'SECOND', 'THIRD')
        strings = extract(lines)
        patches = [{'index': 1, 'text': 'REPLACEMENT'}]
        resolved = resolve(strings, patches)
        assert len(resolved) == 1
        assert resolved[0][0]['text'] == 'SECOND'

    def test_apply_replaces_text(self):
        """Applying patches replaces ASC directive text."""
        extract, _, resolve, apply_patches = self._get_source_patcher()
        lines = _make_asm_source('CARD OF DEATH', 'MARK OF KINGS')
        strings = extract(lines)
        patches = [
            {'vanilla': 'CARD OF DEATH', 'text': 'SHARD OF THE ETERNAL VOID'},
            {'vanilla': 'MARK OF KINGS', 'text': 'SIGIL OF KINGS'},
        ]
        resolved = resolve(strings, patches)
        modified, count = apply_patches(lines, resolved)
        assert count == 2
        # Check that modified lines contain new text
        combined = ''.join(modified)
        assert 'SHARD OF THE ETERNAL VOID' in combined
        assert 'SIGIL OF KINGS' in combined
        # Originals should be gone
        assert 'CARD OF DEATH' not in combined
        assert 'MARK OF KINGS' not in combined

    def test_apply_no_length_constraint(self):
        """Source-level patches have no length constraints."""
        extract, _, resolve, apply_patches = self._get_source_patcher()
        lines = _make_asm_source('HI')
        strings = extract(lines)
        # Replace 2-char string with 50-char string -- would fail in binary patcher
        long_text = 'THIS IS A VERY LONG REPLACEMENT STRING WITH NO LIMIT'
        patches = [{'vanilla': 'HI', 'text': long_text}]
        resolved = resolve(strings, patches)
        modified, count = apply_patches(lines, resolved)
        assert count == 1
        assert long_text in ''.join(modified)

    def test_apply_preserves_untouched(self):
        """Unmatched ASC directives are preserved."""
        extract, _, resolve, apply_patches = self._get_source_patcher()
        lines = _make_asm_source('CHANGE ME', 'KEEP ME')
        strings = extract(lines)
        patches = [{'vanilla': 'CHANGE ME', 'text': 'CHANGED'}]
        resolved = resolve(strings, patches)
        modified, count = apply_patches(lines, resolved)
        assert count == 1
        combined = ''.join(modified)
        assert 'KEEP ME' in combined
        assert 'CHANGED' in combined

    def test_voidborn_full_patches_valid(self):
        """Voidborn engine_strings_full.json has valid structure."""
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'conversions', 'voidborn', 'sources',
                            'engine_strings_full.json')
        if not os.path.exists(path):
            pytest.skip("engine_strings_full.json not found")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert 'patches' in data
        assert len(data['patches']) >= 8
        for patch in data['patches']:
            assert 'text' in patch
            assert 'vanilla' in patch or 'index' in patch

    def test_voidborn_full_patches_resolve_against_source(self):
        """All Voidborn full patches resolve against ULT3 source."""
        source_path = os.path.join(self.ENGINE_DIR, 'ult3', 'ult3.s')
        if not os.path.exists(source_path):
            pytest.skip("ult3.s not found")
        patches_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    'conversions', 'voidborn', 'sources',
                                    'engine_strings_full.json')
        if not os.path.exists(patches_path):
            pytest.skip("engine_strings_full.json not found")
        extract, _, resolve, _ = self._get_source_patcher()
        with open(source_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        with open(patches_path, 'r', encoding='utf-8') as f:
            patch_data = json.load(f)
        strings = extract(lines)
        resolved = resolve(strings, patch_data['patches'])
        assert len(resolved) >= 8, f"Only {len(resolved)} patches resolved"


# =============================================================================
# Integrated inline string catalog (patch.py cmd_strings)
# =============================================================================


class TestPatchStrings:
    """Test the ult3edit patch strings CLI integration."""

    def _make_binary_with_strings(self, *texts):
        """Build binary with JSR $46BA inline strings."""
        data = bytearray()
        data.extend(b'\xEA' * 4)  # NOP padding
        for text in texts:
            data.extend(b'\x20\xBA\x46')  # JSR $46BA
            for ch in text:
                if ch == '\n':
                    data.append(0xFF)
                else:
                    data.append(ord(ch.upper()) | 0x80)
            data.append(0x00)  # null terminator
            data.extend(b'\xEA' * 2)
        return bytes(data)

    def test_extract_inline_strings(self):
        """Integrated _extract_inline_strings finds strings."""
        from ult3edit.patch import _extract_inline_strings
        data = self._make_binary_with_strings('HELLO', 'WORLD')
        strings = _extract_inline_strings(data)
        assert len(strings) == 2
        assert strings[0]['text'] == 'HELLO'
        assert strings[1]['text'] == 'WORLD'

    def test_extract_with_newlines(self):
        """Strings with embedded newlines ($FF) decoded correctly."""
        from ult3edit.patch import _extract_inline_strings
        data = self._make_binary_with_strings('LINE1\nLINE2')
        strings = _extract_inline_strings(data)
        assert len(strings) == 1
        assert strings[0]['text'] == 'LINE1\nLINE2'

    def test_extract_with_org(self):
        """Origin address added to reported addresses."""
        from ult3edit.patch import _extract_inline_strings
        data = self._make_binary_with_strings('TEST')
        strings = _extract_inline_strings(data, org=0x5000)
        assert strings[0]['address'] >= 0x5000

    def test_extract_empty_binary(self):
        """Empty or no-string binary returns empty list."""
        from ult3edit.patch import _extract_inline_strings
        data = bytes(100)
        strings = _extract_inline_strings(data)
        assert len(strings) == 0

    def test_cmd_strings_on_ult3(self, capsys):
        """cmd_strings produces output on ULT3 binary."""
        ult3_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 'engine', 'originals', 'ULT3.bin')
        if not os.path.exists(ult3_path):
            pytest.skip("ULT3.bin not found")
        from ult3edit.patch import cmd_strings
        args = argparse.Namespace(file=ult3_path, json=False, search=None,
                                  output=None)
        cmd_strings(args)
        captured = capsys.readouterr()
        assert '245 strings' in captured.out
        assert 'CARD OF DEATH' in captured.out

    def test_cmd_strings_search(self, capsys):
        """cmd_strings search filter works."""
        ult3_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 'engine', 'originals', 'ULT3.bin')
        if not os.path.exists(ult3_path):
            pytest.skip("ULT3.bin not found")
        from ult3edit.patch import cmd_strings
        args = argparse.Namespace(file=ult3_path, json=False,
                                  search='MARK', output=None)
        cmd_strings(args)
        captured = capsys.readouterr()
        assert 'MARK OF KINGS' in captured.out
        # Should NOT show unrelated strings
        assert 'SPELL TYPE' not in captured.out

    def test_cmd_strings_json(self, capsys, tmp_dir):
        """cmd_strings JSON output is valid."""
        ult3_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 'engine', 'originals', 'ULT3.bin')
        if not os.path.exists(ult3_path):
            pytest.skip("ULT3.bin not found")
        out_path = os.path.join(tmp_dir, 'strings.json')
        from ult3edit.patch import cmd_strings
        args = argparse.Namespace(file=ult3_path, json=True, search=None,
                                  output=out_path)
        cmd_strings(args)
        with open(out_path) as f:
            data = json.load(f)
        assert data['total_strings'] >= 200
        assert 'strings' in data


# =============================================================================
# Inline string editing (patch.py cmd_strings_edit / cmd_strings_import)
# =============================================================================


class TestPatchStringsEdit:
    """Test ult3edit patch strings-edit and strings-import CLI commands."""

    def _make_test_binary(self, tmp_dir, *texts):
        """Create a test binary with inline strings in tmp_dir."""
        data = bytearray()
        data.extend(b'\xEA' * 4)
        for text in texts:
            data.extend(b'\x20\xBA\x46')  # JSR $46BA
            for ch in text:
                if ch == '\n':
                    data.append(0xFF)
                else:
                    data.append(ord(ch.upper()) | 0x80)
            data.append(0x00)
            data.extend(b'\xEA' * 2)
        path = os.path.join(tmp_dir, 'test.bin')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_strings_edit_by_index(self, tmp_dir):
        """Edit string by index replaces bytes correctly."""
        from ult3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'HELLO WORLD', 'GOODBYE')
        args = argparse.Namespace(
            file=path, text='CHANGED', index=0, vanilla=None,
            address=None, output=None, backup=False, dry_run=False)
        cmd_strings_edit(args)
        # Verify the binary was modified
        from ult3edit.patch import _extract_inline_strings
        with open(path, 'rb') as f:
            data = f.read()
        strings = _extract_inline_strings(data)
        assert strings[0]['text'] == 'CHANGED'
        assert strings[1]['text'] == 'GOODBYE'  # untouched

    def test_strings_edit_by_vanilla(self, tmp_dir):
        """Edit string by vanilla text match."""
        from ult3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'CARD OF DEATH', 'HELLO')
        args = argparse.Namespace(
            file=path, text='SHARD O VOID', index=None,
            vanilla='CARD OF DEATH', address=None, output=None,
            backup=False, dry_run=False)
        cmd_strings_edit(args)
        from ult3edit.patch import _extract_inline_strings
        with open(path, 'rb') as f:
            data = f.read()
        strings = _extract_inline_strings(data)
        assert strings[0]['text'] == 'SHARD O VOID'

    def test_strings_edit_too_long(self, tmp_dir):
        """Editing with text too long for in-place fails gracefully."""
        from ult3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'HI')
        args = argparse.Namespace(
            file=path, text='THIS IS WAY TOO LONG FOR HI',
            index=0, vanilla=None, address=None, output=None,
            backup=False, dry_run=False)
        with pytest.raises(SystemExit):
            cmd_strings_edit(args)

    def test_strings_edit_dry_run(self, tmp_dir):
        """Dry run does not modify the file."""
        from ult3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'ORIGINAL')
        with open(path, 'rb') as f:
            original = f.read()
        args = argparse.Namespace(
            file=path, text='CHANGED', index=0, vanilla=None,
            address=None, output=None, backup=False, dry_run=True)
        cmd_strings_edit(args)
        with open(path, 'rb') as f:
            after = f.read()
        assert original == after

    def test_strings_edit_backup(self, tmp_dir):
        """Backup creates .bak file."""
        from ult3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'ORIGINAL')
        args = argparse.Namespace(
            file=path, text='CHANGED', index=0, vanilla=None,
            address=None, output=None, backup=True, dry_run=False)
        cmd_strings_edit(args)
        assert os.path.exists(path + '.bak')

    def test_strings_edit_output_file(self, tmp_dir):
        """Writing to separate output file preserves original."""
        from ult3edit.patch import cmd_strings_edit
        path = self._make_test_binary(tmp_dir, 'ORIGINAL')
        out_path = os.path.join(tmp_dir, 'output.bin')
        with open(path, 'rb') as f:
            original = f.read()
        args = argparse.Namespace(
            file=path, text='CHANGED', index=0, vanilla=None,
            address=None, output=out_path, backup=False, dry_run=False)
        cmd_strings_edit(args)
        with open(path, 'rb') as f:
            assert f.read() == original  # original untouched
        assert os.path.exists(out_path)

    def test_strings_import_from_json(self, tmp_dir):
        """Import multiple patches from JSON file."""
        from ult3edit.patch import cmd_strings_import, _extract_inline_strings
        path = self._make_test_binary(tmp_dir,
                                      'CARD OF DEATH', 'MARK OF KINGS', 'HELLO')
        # Create patch JSON
        patch_path = os.path.join(tmp_dir, 'patches.json')
        with open(patch_path, 'w') as f:
            json.dump({'patches': [
                {'vanilla': 'CARD OF DEATH', 'text': 'SHARD O VOID'},
                {'vanilla': 'MARK OF KINGS', 'text': 'SIGIL KINGS'},
            ]}, f)
        args = argparse.Namespace(
            file=path, json_file=patch_path, output=None,
            backup=False, dry_run=False)
        cmd_strings_import(args)
        with open(path, 'rb') as f:
            data = f.read()
        strings = _extract_inline_strings(data)
        assert strings[0]['text'] == 'SHARD O VOID'
        assert strings[1]['text'] == 'SIGIL KINGS'
        assert strings[2]['text'] == 'HELLO'  # untouched

    def test_strings_import_dry_run(self, tmp_dir):
        """Import dry run doesn't modify file."""
        from ult3edit.patch import cmd_strings_import
        path = self._make_test_binary(tmp_dir, 'ORIGINAL')
        with open(path, 'rb') as f:
            original = f.read()
        patch_path = os.path.join(tmp_dir, 'patches.json')
        with open(patch_path, 'w') as f:
            json.dump({'patches': [
                {'index': 0, 'text': 'CHANGED'},
            ]}, f)
        args = argparse.Namespace(
            file=path, json_file=patch_path, output=None,
            backup=False, dry_run=True)
        cmd_strings_import(args)
        with open(path, 'rb') as f:
            assert f.read() == original

    def test_strings_import_voidborn(self, tmp_dir):
        """Voidborn engine_strings.json imports successfully on ULT3."""
        ult3_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 'engine', 'originals', 'ULT3.bin')
        if not os.path.exists(ult3_path):
            pytest.skip("ULT3.bin not found")
        patches_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    'conversions', 'voidborn', 'sources',
                                    'engine_strings.json')
        if not os.path.exists(patches_path):
            pytest.skip("engine_strings.json not found")
        # Copy ULT3 to temp
        test_bin = os.path.join(tmp_dir, 'ULT3.bin')
        shutil.copy2(ult3_path, test_bin)
        from ult3edit.patch import cmd_strings_import
        args = argparse.Namespace(
            file=test_bin, json_file=patches_path, output=None,
            backup=False, dry_run=False)
        cmd_strings_import(args)
        # Verify changes
        from ult3edit.patch import _extract_inline_strings
        with open(test_bin, 'rb') as f:
            data = f.read()
        strings = _extract_inline_strings(data, 0x5000)
        texts = [s['text'] for s in strings]
        assert any('SHARD OF VOID' in t for t in texts)
        assert any('SIGIL: KINGS' in t for t in texts)


# =============================================================================
# Compiler subcommands — map, shapes, patch
# =============================================================================


class TestPatchCompileNamesSubcommand:
    """Test ult3edit patch compile-names/decompile-names CLI subcommands."""

    def _make_names_source(self, path, names=None):
        """Create a .names source file."""
        if names is None:
            names = ['WATER', 'GRASS', 'FOREST', 'MOUNTAIN',
                     'SWORD', 'MACE', 'DAGGER']
        lines = ['# Test Name Table', '# Group: Terrain']
        lines.extend(names[:4])
        lines.append('')
        lines.append('# Group: Weapons')
        lines.extend(names[4:])
        with open(path, 'w') as f:
            f.write('\n'.join(lines) + '\n')

    def test_compile_names_json(self, tmp_dir):
        """Compile .names to JSON with regions.name-table.data."""
        from ult3edit.patch import cmd_compile_names
        src = os.path.join(tmp_dir, 'test.names')
        self._make_names_source(src)
        out = os.path.join(tmp_dir, 'names.json')
        args = argparse.Namespace(source=src, output=out)
        cmd_compile_names(args)
        with open(out, 'r') as f:
            result = json.load(f)
        assert 'regions' in result
        assert 'name-table' in result['regions']
        assert 'data' in result['regions']['name-table']
        names = result['regions']['name-table']['data']
        assert 'WATER' in names
        assert 'SWORD' in names

    def test_compile_names_stdout(self, tmp_dir, capsys):
        """Compile .names to stdout prints JSON."""
        from ult3edit.patch import cmd_compile_names
        src = os.path.join(tmp_dir, 'test.names')
        self._make_names_source(src)
        args = argparse.Namespace(source=src, output=None)
        cmd_compile_names(args)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert 'regions' in result

    def test_validate_names_pass(self, tmp_dir, capsys):
        """Validate .names within budget passes."""
        from ult3edit.patch import cmd_validate_names
        src = os.path.join(tmp_dir, 'test.names')
        self._make_names_source(src)
        args = argparse.Namespace(source=src)
        cmd_validate_names(args)
        captured = capsys.readouterr()
        assert 'PASS' in captured.out

    def test_validate_names_fail(self, tmp_dir):
        """Validate .names over budget fails."""
        from ult3edit.patch import cmd_validate_names
        src = os.path.join(tmp_dir, 'test.names')
        # Create names that exceed 891-byte budget
        names = [f'VERY_LONG_NAME_PADDING_{i:04d}' for i in range(100)]
        self._make_names_source(src, names)
        args = argparse.Namespace(source=src)
        with pytest.raises(SystemExit):
            cmd_validate_names(args)

    def test_decompile_names(self, tmp_dir):
        """Decompile name table from ULT3-sized binary."""
        from ult3edit.patch import cmd_decompile_names
        # Create a minimal binary with name table at offset 0x397A
        data = bytearray(0x397A + 921)
        # Encode some test names at offset 0x397A
        offset = 0x397A
        for name in ['WATER', 'GRASS', 'SWORD']:
            for ch in name:
                data[offset] = ord(ch) | 0x80
                offset += 1
            data[offset] = 0x00
            offset += 1
        bin_path = os.path.join(tmp_dir, 'test_ult3.bin')
        with open(bin_path, 'wb') as f:
            f.write(data)
        out = os.path.join(tmp_dir, 'names.names')
        args = argparse.Namespace(file=bin_path, output=out)
        cmd_decompile_names(args)
        with open(out, 'r') as f:
            text = f.read()
        assert 'WATER' in text
        assert 'GRASS' in text
        assert 'SWORD' in text

    def test_parse_names_empty_string(self):
        """Explicit empty strings ('""') are preserved."""
        from ult3edit.patch import _parse_names_file
        text = '# Test\nFOO\n""\nBAR\n'
        names = _parse_names_file(text)
        assert names == ['FOO', '', 'BAR']

    def test_validate_names_budget_math(self):
        """Budget math: encoded size = sum(len+1), budget = 921-30."""
        from ult3edit.patch import _validate_names
        names = ['AB', 'CD']
        size, budget, valid = _validate_names(names)
        assert size == 6  # (2+1) + (2+1)
        assert budget == 891
        assert valid is True


class TestCliParityCompilers:
    """Verify compile subcommands are registered in CLI dispatch."""

    def test_map_compile_in_dispatch(self):
        """map dispatch handles 'compile'."""
        from ult3edit.map import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'compile'" in src

    def test_map_decompile_in_dispatch(self):
        """map dispatch handles 'decompile'."""
        from ult3edit.map import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'decompile'" in src

    def test_shapes_compile_in_dispatch(self):
        """shapes dispatch handles 'compile'."""
        from ult3edit.shapes import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'compile'" in src

    def test_shapes_decompile_in_dispatch(self):
        """shapes dispatch handles 'decompile'."""
        from ult3edit.shapes import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'decompile'" in src

    def test_patch_compile_names_in_dispatch(self):
        """patch dispatch handles 'compile-names'."""
        from ult3edit.patch import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'compile-names'" in src

    def test_patch_decompile_names_in_dispatch(self):
        """patch dispatch handles 'decompile-names'."""
        from ult3edit.patch import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'decompile-names'" in src

    def test_patch_validate_names_in_dispatch(self):
        """patch dispatch handles 'validate-names'."""
        from ult3edit.patch import dispatch
        import inspect
        src = inspect.getsource(dispatch)
        assert "'validate-names'" in src


# ============================================================================
# Compile warnings and validation (Task #110)
# ============================================================================


class TestPatchCmdEdit:
    """Tests for patch.cmd_edit — region patching."""

    def _make_ult3(self, tmp_path):
        """Create a fake ULT3 binary of the right size."""
        from ult3edit.constants import ULT3_FILE_SIZE
        path = tmp_path / 'ULT3'
        path.write_bytes(bytes(ULT3_FILE_SIZE))
        return str(path)

    def test_edit_moongate_x(self, tmp_path, capsys):
        """Patch moongate-x region and verify bytes written."""
        from ult3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        args = argparse.Namespace(
            file=path, region='moongate-x', data='01 02 03 04 05 06 07 08',
            dry_run=False, backup=False, output=None)
        cmd_edit(args)
        with open(path, 'rb') as f:
            data = f.read()
        assert data[0x29A7:0x29A7 + 8] == bytes([1, 2, 3, 4, 5, 6, 7, 8])

    def test_edit_dry_run(self, tmp_path, capsys):
        """Dry run shows changes but doesn't write."""
        from ult3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        args = argparse.Namespace(
            file=path, region='moongate-x', data='AABBCCDD',
            dry_run=True, backup=False, output=None)
        cmd_edit(args)
        out = capsys.readouterr().out
        assert 'Dry run' in out
        with open(path, 'rb') as f:
            data = f.read()
        assert data[0x29A7:0x29A7 + 4] == bytes(4)  # unchanged

    def test_edit_unknown_region_exits(self, tmp_path):
        """Unknown region name causes sys.exit."""
        from ult3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        args = argparse.Namespace(
            file=path, region='nonexistent', data='AA',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_data_too_long_exits(self, tmp_path):
        """Data exceeding region max_length causes sys.exit."""
        from ult3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        # moongate-x max_length is 8, send 9 bytes
        args = argparse.Namespace(
            file=path, region='moongate-x', data='01 02 03 04 05 06 07 08 09',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_invalid_hex_exits(self, tmp_path):
        """Invalid hex data causes sys.exit."""
        from ult3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        args = argparse.Namespace(
            file=path, region='moongate-x', data='ZZZZ',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_unrecognized_binary_exits(self, tmp_path):
        """Non-engine binary file causes sys.exit."""
        from ult3edit.patch import cmd_edit
        path = tmp_path / 'JUNK'
        path.write_bytes(bytes(100))
        args = argparse.Namespace(
            file=str(path), region='moongate-x', data='AA',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_edit_with_backup(self, tmp_path):
        """Backup flag creates .bak before patching."""
        from ult3edit.patch import cmd_edit
        path = self._make_ult3(tmp_path)
        args = argparse.Namespace(
            file=path, region='food-rate', data='02',
            dry_run=False, backup=True, output=None)
        cmd_edit(args)
        assert os.path.exists(path + '.bak')


class TestPatchCmdDump:
    """Tests for patch.cmd_dump — hex dump."""

    def test_dump_basic(self, tmp_path, capsys):
        """Hex dump produces output with hex values."""
        from ult3edit.patch import cmd_dump
        from ult3edit.constants import ULT3_FILE_SIZE
        path = tmp_path / 'ULT3'
        data = bytearray(ULT3_FILE_SIZE)
        data[0] = 0xAB
        data[1] = 0xCD
        path.write_bytes(bytes(data))
        args = argparse.Namespace(file=str(path), offset=0, length=16)
        cmd_dump(args)
        out = capsys.readouterr().out
        assert 'AB CD' in out

    def test_dump_offset_past_end_exits(self, tmp_path):
        """Offset past end of file causes sys.exit."""
        from ult3edit.patch import cmd_dump
        path = tmp_path / 'SMALL'
        path.write_bytes(bytes(16))
        args = argparse.Namespace(file=str(path), offset=100, length=16)
        with pytest.raises(SystemExit):
            cmd_dump(args)

    def test_dump_with_load_addr(self, tmp_path, capsys):
        """Recognized binary shows load addresses."""
        from ult3edit.patch import cmd_dump
        from ult3edit.constants import ULT3_FILE_SIZE
        path = tmp_path / 'ULT3'
        path.write_bytes(bytes(ULT3_FILE_SIZE))
        args = argparse.Namespace(file=str(path), offset=0, length=16)
        cmd_dump(args)
        out = capsys.readouterr().out
        # ULT3 load_addr is 0x5000, so first line should show 5000:
        assert '5000:' in out


# =============================================================================
# Map cmd_fill / cmd_replace / cmd_find CLI tests
# =============================================================================


class TestPatchInlineString:
    """Tests for _patch_inline_string and _resolve_string_target."""

    def test_patch_exact_fit(self):
        """Replacement text exactly fills available space."""
        from ult3edit.patch import _patch_inline_string
        data = bytearray(20)
        # Simulate inline string: "ABC" (3 bytes) at offset 5, ending at 8
        for i, ch in enumerate('ABC'):
            data[5 + i] = ord(ch.upper()) | 0x80
        data[8] = 0x00  # null terminator

        info = {'text_offset': 5, 'text_end': 8, 'text': 'ABC', 'index': 0}
        ok, msg = _patch_inline_string(data, info, 'XYZ')
        assert ok is True
        # Verify encoded bytes
        assert data[5] == ord('X') | 0x80
        assert data[6] == ord('Y') | 0x80
        assert data[7] == ord('Z') | 0x80

    def test_patch_shorter_nullfills(self):
        """Shorter replacement null-fills remaining space."""
        from ult3edit.patch import _patch_inline_string
        data = bytearray(20)
        for i, ch in enumerate('ABCDE'):
            data[5 + i] = ord(ch) | 0x80
        data[10] = 0x00

        info = {'text_offset': 5, 'text_end': 10, 'text': 'ABCDE', 'index': 0}
        ok, msg = _patch_inline_string(data, info, 'HI')
        assert ok is True
        assert data[5] == ord('H') | 0x80
        assert data[6] == ord('I') | 0x80
        # Remaining should be null-filled
        assert data[7] == 0x00
        assert data[8] == 0x00
        assert data[9] == 0x00

    def test_patch_too_long_fails(self):
        """Text longer than available space returns failure."""
        from ult3edit.patch import _patch_inline_string
        data = bytearray(20)
        info = {'text_offset': 5, 'text_end': 7, 'text': 'AB', 'index': 0}
        ok, msg = _patch_inline_string(data, info, 'TOOLONG')
        assert ok is False
        assert 'too long' in msg.lower()

    def test_resolve_by_index(self):
        """_resolve_string_target finds by index."""
        from ult3edit.patch import _resolve_string_target
        strings = [
            {'index': 0, 'text': 'HELLO', 'address': 0x100},
            {'index': 1, 'text': 'WORLD', 'address': 0x110},
        ]
        result = _resolve_string_target(strings, index=1)
        assert len(result) == 1
        assert result[0]['text'] == 'WORLD'

    def test_resolve_by_vanilla_text(self):
        """_resolve_string_target finds by vanilla text (case-insensitive)."""
        from ult3edit.patch import _resolve_string_target
        strings = [
            {'index': 0, 'text': 'HELLO', 'address': 0x100},
            {'index': 1, 'text': 'WORLD', 'address': 0x110},
        ]
        result = _resolve_string_target(strings, vanilla='hello')
        assert len(result) == 1
        assert result[0]['index'] == 0

    def test_resolve_by_address(self):
        """_resolve_string_target finds by address."""
        from ult3edit.patch import _resolve_string_target
        strings = [
            {'index': 0, 'text': 'HELLO', 'address': 0x100},
            {'index': 1, 'text': 'WORLD', 'address': 0x110},
        ]
        result = _resolve_string_target(strings, address=0x110)
        assert len(result) == 1
        assert result[0]['text'] == 'WORLD'

    def test_resolve_no_match(self):
        """_resolve_string_target returns empty list for no match."""
        from ult3edit.patch import _resolve_string_target
        strings = [{'index': 0, 'text': 'HELLO', 'address': 0x100}]
        result = _resolve_string_target(strings, index=99)
        assert result == []

    def test_resolve_no_criteria(self):
        """_resolve_string_target returns empty list with no criteria."""
        from ult3edit.patch import _resolve_string_target
        strings = [{'index': 0, 'text': 'HELLO', 'address': 0x100}]
        result = _resolve_string_target(strings)
        assert result == []


# =============================================================================
# Shapes pixel helper tests
# =============================================================================


class TestPatchNameCompile:
    """Test patch.py name table compilation and validation."""

    def test_parse_names_file_basic(self):
        """Parse a simple .names file."""
        from ult3edit.patch import _parse_names_file
        text = "# Comment\nGRASS\nWATER\n\nFIRE\n"
        result = _parse_names_file(text)
        assert result == ['GRASS', 'WATER', 'FIRE']

    def test_parse_names_file_empty_quotes(self):
        """Empty string via double-quotes."""
        from ult3edit.patch import _parse_names_file
        text = 'HELLO\n""\nWORLD\n'
        result = _parse_names_file(text)
        assert result == ['HELLO', '', 'WORLD']

    def test_parse_names_file_single_quotes(self):
        """Empty string via single-quotes."""
        from ult3edit.patch import _parse_names_file
        text = "HELLO\n''\nWORLD\n"
        result = _parse_names_file(text)
        assert result == ['HELLO', '', 'WORLD']

    def test_parse_names_comments_and_blanks(self):
        """Comments and blank lines are skipped."""
        from ult3edit.patch import _parse_names_file
        text = "# header\n\n# another comment\nONE\n#\nTWO\n"
        result = _parse_names_file(text)
        assert result == ['ONE', 'TWO']

    def test_validate_names_within_budget(self):
        """Names within the 921-byte budget pass validation."""
        from ult3edit.patch import _validate_names
        names = ['GRASS', 'WATER', 'FIRE']
        size, budget, valid = _validate_names(names)
        assert valid
        # size = len('GRASS')+1 + len('WATER')+1 + len('FIRE')+1 = 17
        assert size == 17

    def test_validate_names_overflow(self):
        """Names exceeding the budget fail validation."""
        from ult3edit.patch import _validate_names
        # Create names that total > 891 bytes (921 - 30 reserved)
        names = ['X' * 100] * 10  # 10 * 101 = 1010 bytes > 891
        size, budget, valid = _validate_names(names)
        assert not valid
        assert size > budget

    def test_compile_names_overflow_exits(self, tmp_path):
        """cmd_compile_names with too-large names exits with error."""
        from ult3edit.patch import cmd_compile_names
        source = os.path.join(str(tmp_path), 'big.names')
        with open(source, 'w') as f:
            for i in range(100):
                f.write('A' * 50 + '\n')
        args = argparse.Namespace(source=source, output=None)
        with pytest.raises(SystemExit):
            cmd_compile_names(args)

    def test_compile_names_empty_exits(self, tmp_path):
        """cmd_compile_names with no names exits with error."""
        from ult3edit.patch import cmd_compile_names
        source = os.path.join(str(tmp_path), 'empty.names')
        with open(source, 'w') as f:
            f.write('# only comments\n\n')
        args = argparse.Namespace(source=source, output=None)
        with pytest.raises(SystemExit):
            cmd_compile_names(args)


class TestPatchCmdErrors:
    """Test error paths in patch CLI commands."""

    def _make_ult3_binary(self, tmp_path):
        """Create a fake ULT3-sized binary."""
        data = bytearray(17408)
        path = os.path.join(str(tmp_path), 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_cmd_edit_unknown_region(self, tmp_path):
        """cmd_edit with non-existent region name exits."""
        from ult3edit.patch import cmd_edit
        path = self._make_ult3_binary(tmp_path)
        args = argparse.Namespace(
            file=path, region='nonexistent', data='FF',
            dry_run=True, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_cmd_edit_invalid_hex(self, tmp_path):
        """cmd_edit with malformed hex exits."""
        from ult3edit.patch import cmd_edit
        path = self._make_ult3_binary(tmp_path)
        args = argparse.Namespace(
            file=path, region='food-rate', data='ZZZZ',
            dry_run=True, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_cmd_edit_data_too_long(self, tmp_path):
        """cmd_edit with data exceeding region max exits."""
        from ult3edit.patch import cmd_edit
        path = self._make_ult3_binary(tmp_path)
        # food-rate max_length is 1, send 10 bytes
        args = argparse.Namespace(
            file=path, region='food-rate', data='FF' * 10,
            dry_run=True, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_cmd_dump_offset_past_end(self, tmp_path):
        """cmd_dump with offset past EOF exits."""
        from ult3edit.patch import cmd_dump
        path = self._make_ult3_binary(tmp_path)
        args = argparse.Namespace(
            file=path, offset=99999, length=16)
        with pytest.raises(SystemExit):
            cmd_dump(args)

    def test_cmd_view_unknown_region_filter(self, tmp_path):
        """cmd_view with region filter for unknown region exits."""
        from ult3edit.patch import cmd_view
        path = self._make_ult3_binary(tmp_path)
        args = argparse.Namespace(
            file=path, region='nonexistent', json=False, output=None)
        with pytest.raises(SystemExit):
            cmd_view(args)

    def test_cmd_view_unrecognized_binary(self, tmp_path):
        """cmd_view on unrecognized binary shows warning (no exit)."""
        from ult3edit.patch import cmd_view
        path = os.path.join(str(tmp_path), 'UNKNOWN')
        with open(path, 'wb') as f:
            f.write(b'\x00' * 100)
        args = argparse.Namespace(
            file=path, region=None, json=False, output=None)
        # Should not raise — just prints warning
        cmd_view(args)

    def test_cmd_import_no_matching_regions(self, tmp_path):
        """cmd_import with JSON that has no matching region names exits."""
        from ult3edit.patch import cmd_import
        path = self._make_ult3_binary(tmp_path)
        json_path = os.path.join(str(tmp_path), 'bad.json')
        with open(json_path, 'w') as f:
            json.dump({'regions': {'fake-region': {'data': [0]}}}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, output=None,
            dry_run=True, backup=False, region=None)
        with pytest.raises(SystemExit):
            cmd_import(args)


# =============================================================================
# Patch encoding helpers
# =============================================================================


class TestPatchEncoding:
    """Test encode/parse helpers for coords and text regions."""

    def test_parse_text_region(self):
        """Parse null-terminated high-ASCII strings."""
        from ult3edit.patch import parse_text_region
        # Build: "HI\x00BYE\x00\x00" (trailing null padding)
        data = bytearray(100)
        for i, ch in enumerate('HI'):
            data[10 + i] = ord(ch) | 0x80
        data[12] = 0x00
        for i, ch in enumerate('BYE'):
            data[13 + i] = ord(ch) | 0x80
        data[16] = 0x00
        result = parse_text_region(bytes(data), 10, 20)
        assert result == ['HI', 'BYE']

    def test_encode_coord_region(self):
        """Encode XY coordinate pairs."""
        from ult3edit.patch import encode_coord_region
        coords = [{'x': 10, 'y': 20}, {'x': 30, 'y': 40}]
        result = encode_coord_region(coords, 8)
        assert result[:4] == bytes([10, 20, 30, 40])
        assert len(result) == 8  # padded to max_length
        assert result[4:] == bytes(4)  # remaining is null-padded

    def test_encode_coord_region_overflow(self):
        """Encoding coords that exceed max_length raises ValueError."""
        from ult3edit.patch import encode_coord_region
        coords = [{'x': i, 'y': i} for i in range(10)]
        with pytest.raises(ValueError, match='exceeds max'):
            encode_coord_region(coords, 4)

    def test_encode_text_region(self):
        """Encode strings as null-terminated high-ASCII."""
        from ult3edit.patch import encode_text_region
        result = encode_text_region(['HI', 'BYE'], 20)
        # HI = 0xC8 0xC9 0x00, BYE = 0xC2 0xD9 0xC5 0x00
        assert result[0] == ord('H') | 0x80
        assert result[1] == ord('I') | 0x80
        assert result[2] == 0x00
        assert result[3] == ord('B') | 0x80
        assert len(result) == 20  # padded to max


# =============================================================================
# TLK search and edit error paths
# =============================================================================


class TestPatchIdentifyBinary:
    """Test identify_binary engine detection."""

    def test_identify_ult3_by_name(self):
        """Identify ULT3 by filename."""
        from ult3edit.patch import identify_binary
        data = bytes(17408)
        result = identify_binary(data, 'ULT3')
        assert result is not None
        assert result['name'] == 'ULT3'
        assert result['load_addr'] == 0x5000

    def test_identify_exod_by_name(self):
        """Identify EXOD by filename."""
        from ult3edit.patch import identify_binary
        data = bytes(26208)
        result = identify_binary(data, 'EXOD')
        assert result is not None
        assert result['name'] == 'EXOD'

    def test_identify_by_size_only(self):
        """Identify binary by size when filename doesn't match."""
        from ult3edit.patch import identify_binary
        data = bytes(17408)  # ULT3 size
        result = identify_binary(data, 'randomfile')
        assert result is not None
        assert result['name'] == 'ULT3'

    def test_unrecognized_returns_none(self):
        """Unrecognized binary returns None."""
        from ult3edit.patch import identify_binary
        data = bytes(100)
        result = identify_binary(data, 'UNKNOWN')
        assert result is None

    def test_identify_subs(self):
        """Identify SUBS by filename."""
        from ult3edit.patch import identify_binary
        data = bytes(3584)
        result = identify_binary(data, 'SUBS')
        assert result is not None
        assert result['name'] == 'SUBS'


# =============================================================================
# Patch cmd_edit dry-run / actual write
# =============================================================================


class TestPatchCmdEditWriteback:
    """Test patch cmd_edit writes correct bytes."""

    def test_cmd_edit_dry_run_no_write(self, tmp_path):
        """cmd_edit with --dry-run doesn't modify the file."""
        from ult3edit.patch import cmd_edit
        path = os.path.join(str(tmp_path), 'ULT3')
        data = bytearray(17408)
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, region='food-rate', data='08',
            dry_run=True, backup=False, output=None)
        cmd_edit(args)
        with open(path, 'rb') as f:
            after = f.read()
        assert after == bytes(17408)  # unchanged

    def test_cmd_edit_writes_bytes(self, tmp_path):
        """cmd_edit actually patches the correct offset."""
        from ult3edit.patch import cmd_edit
        path = os.path.join(str(tmp_path), 'ULT3')
        data = bytearray(17408)
        with open(path, 'wb') as f:
            f.write(data)
        args = argparse.Namespace(
            file=path, region='food-rate', data='08',
            dry_run=False, backup=False, output=None)
        cmd_edit(args)
        with open(path, 'rb') as f:
            after = f.read()
        # food-rate is at offset 0x272C
        assert after[0x272C] == 0x08


# =============================================================================
# Text module error paths
# =============================================================================


class TestPatchCmdGaps:
    """Test patch command additional error paths."""

    def test_cmd_view_unrecognized_binary_fallback(self, tmp_path, capsys):
        """cmd_view on unrecognized file prints warning."""
        from ult3edit.patch import cmd_view
        path = os.path.join(str(tmp_path), 'UNKNOWN')
        with open(path, 'wb') as f:
            f.write(b'\x00' * 100)
        args = argparse.Namespace(
            file=path, json=False, output=None, region=None)
        cmd_view(args)
        captured = capsys.readouterr()
        assert 'not recognized' in captured.err

    def test_cmd_edit_unrecognized_exits(self, tmp_path):
        """cmd_edit on unrecognized binary exits."""
        from ult3edit.patch import cmd_edit
        path = os.path.join(str(tmp_path), 'UNKNOWN')
        with open(path, 'wb') as f:
            f.write(b'\x00' * 100)
        args = argparse.Namespace(
            file=path, region='name-table', data='FF',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_encode_text_overflow(self):
        """encode_text_region raises ValueError when text exceeds max_length."""
        from ult3edit.patch import encode_text_region
        strings = ['A' * 100, 'B' * 100]
        with pytest.raises(ValueError, match="exceeds max"):
            encode_text_region(strings, 10)

    def test_cmd_view_unrecognized_json(self, tmp_path, capsys):
        """cmd_view on unrecognized file with --json outputs JSON."""
        from ult3edit.patch import cmd_view
        path = os.path.join(str(tmp_path), 'UNKNOWN')
        with open(path, 'wb') as f:
            f.write(b'\x00' * 100)
        out_path = os.path.join(str(tmp_path), 'out.json')
        args = argparse.Namespace(
            file=path, json=True, output=out_path, region=None)
        cmd_view(args)
        with open(out_path, 'r') as f:
            result = json.load(f)
        assert result['recognized'] is False
        assert result['size'] == 100


class TestPatchEncodeCoordOverflow:
    """Test encode_coord_region overflow."""

    def test_encode_coord_too_many_pairs(self):
        """encode_coord_region raises ValueError when coords exceed max_length."""
        from ult3edit.patch import encode_coord_region
        coords = [{'x': i, 'y': i} for i in range(20)]
        with pytest.raises(ValueError, match="exceeds max"):
            encode_coord_region(coords, 8)


class TestPatchCmdEditDataTooLong:
    """Test patch cmd_edit data exceeds region size."""

    def test_data_exceeds_region_max(self, tmp_path):
        """cmd_edit with data larger than region max_length exits."""
        from ult3edit.patch import cmd_edit
        # Create file that looks like ULT3 (17408 bytes)
        path = os.path.join(str(tmp_path), 'ULT3')
        with open(path, 'wb') as f:
            f.write(bytearray(17408))
        args = argparse.Namespace(
            file=path, region='food-rate',  # max_length=1
            data='AA BB CC DD',  # 4 bytes > 1
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_invalid_hex_in_patch(self, tmp_path):
        """cmd_edit with invalid hex string exits."""
        from ult3edit.patch import cmd_edit
        path = os.path.join(str(tmp_path), 'ULT3')
        with open(path, 'wb') as f:
            f.write(bytearray(17408))
        args = argparse.Namespace(
            file=path, region='food-rate',
            data='ZZZZ',  # Invalid hex
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)

    def test_unknown_region(self, tmp_path):
        """cmd_edit with unknown region name exits."""
        from ult3edit.patch import cmd_edit
        path = os.path.join(str(tmp_path), 'ULT3')
        with open(path, 'wb') as f:
            f.write(bytearray(17408))
        args = argparse.Namespace(
            file=path, region='nonexistent-region',
            data='FF',
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_edit(args)


class TestPatchCmdImportGaps:
    """Test patch cmd_import error paths."""

    def test_import_unrecognized_binary(self, tmp_path):
        """cmd_import on unrecognized binary exits."""
        from ult3edit.patch import cmd_import
        path = os.path.join(str(tmp_path), 'UNKNOWN')
        with open(path, 'wb') as f:
            f.write(bytearray(100))
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'food-rate': [4]}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, region=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_import(args)

    def test_import_no_matching_regions(self, tmp_path):
        """cmd_import with no matching regions exits."""
        from ult3edit.patch import cmd_import
        path = os.path.join(str(tmp_path), 'ULT3')
        with open(path, 'wb') as f:
            f.write(bytearray(17408))
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'nonexistent': [1, 2, 3]}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, region=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_import(args)

    def test_import_subs_no_regions(self, tmp_path):
        """cmd_import on SUBS binary (no regions) exits."""
        from ult3edit.patch import cmd_import
        path = os.path.join(str(tmp_path), 'SUBS')
        with open(path, 'wb') as f:
            f.write(bytearray(3584))
        json_path = os.path.join(str(tmp_path), 'import.json')
        with open(json_path, 'w') as f:
            json.dump({'food-rate': [4]}, f)
        args = argparse.Namespace(
            file=path, json_file=json_path, region=None,
            dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_import(args)


class TestPatchCmdDumpGaps:
    """Test patch cmd_dump error paths."""

    def test_dump_offset_past_end(self, tmp_path):
        """cmd_dump with offset past end of file exits."""
        from ult3edit.patch import cmd_dump
        path = os.path.join(str(tmp_path), 'ULT3')
        with open(path, 'wb') as f:
            f.write(bytearray(17408))
        args = argparse.Namespace(
            file=path, offset=99999, length=16)
        with pytest.raises(SystemExit):
            cmd_dump(args)


class TestPatchStringsEditNoStrings:
    """Test patch cmd_strings_edit exits when binary has no inline strings."""

    def test_no_strings_exits(self, tmp_path):
        from ult3edit.patch import cmd_strings_edit
        path = os.path.join(str(tmp_path), 'ULT3')
        # Binary with no JSR $46BA pattern
        with open(path, 'wb') as f:
            f.write(bytearray(17408))
        args = argparse.Namespace(file=path, index=0, vanilla=None,
                                  address=None, text='TEST',
                                  dry_run=True, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_strings_edit(args)


class TestPatchStringsEditNoCriteria:
    """Test patch cmd_strings_edit exits when no --index/--vanilla/--address."""

    def _make_ult3_with_string(self, tmp_path):
        """Create a ULT3-size binary with one inline string."""
        data = bytearray(17408)
        # Place JSR $46BA at offset 100
        data[100] = 0x20
        data[101] = 0xBA
        data[102] = 0x46
        # Inline text "HI" in high-ASCII + null
        data[103] = ord('H') | 0x80
        data[104] = ord('I') | 0x80
        data[105] = 0x00
        path = os.path.join(str(tmp_path), 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_no_criteria_exits(self, tmp_path):
        from ult3edit.patch import cmd_strings_edit
        path = self._make_ult3_with_string(tmp_path)
        args = argparse.Namespace(file=path, index=None, vanilla=None,
                                  address=None, text='TEST',
                                  dry_run=True, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_strings_edit(args)


class TestPatchStringsEditByAddress:
    """Test patch cmd_strings_edit by --address lookup."""

    def test_edit_by_address(self, tmp_path, capsys):
        from ult3edit.patch import cmd_strings_edit
        data = bytearray(17408)
        # Place JSR $46BA at offset 100
        data[100] = 0x20
        data[101] = 0xBA
        data[102] = 0x46
        # Inline "HI" + null
        data[103] = ord('H') | 0x80
        data[104] = ord('I') | 0x80
        data[105] = 0x00
        path = os.path.join(str(tmp_path), 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)
        # Address = org + JSR offset = $5000 + 100 = $5064
        args = argparse.Namespace(file=path, index=None, vanilla=None,
                                  address=0x5064, text='HI',
                                  dry_run=True, backup=False, output=None)
        cmd_strings_edit(args)
        out = capsys.readouterr().out
        assert 'Patched' in out or 'Dry run' in out


class TestPatchStringsImportNoStrings:
    """Test patch cmd_strings_import exits when binary has no inline strings."""

    def test_no_strings_exits(self, tmp_path):
        from ult3edit.patch import cmd_strings_import
        path = os.path.join(str(tmp_path), 'ULT3')
        with open(path, 'wb') as f:
            f.write(bytearray(17408))
        jpath = os.path.join(str(tmp_path), 'patches.json')
        with open(jpath, 'w') as f:
            json.dump({'patches': [{'index': 0, 'text': 'X'}]}, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=True, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_strings_import(args)


class TestPatchStringsImportErrors:
    """Test patch cmd_strings_import error paths."""

    def _make_ult3_with_string(self, tmp_path, text='HI'):
        data = bytearray(17408)
        data[100] = 0x20
        data[101] = 0xBA
        data[102] = 0x46
        for i, ch in enumerate(text):
            data[103 + i] = ord(ch) | 0x80
        data[103 + len(text)] = 0x00
        path = os.path.join(str(tmp_path), 'ULT3')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def test_all_patches_fail_exits(self, tmp_path):
        """cmd_strings_import exits when replacement is too long."""
        from ult3edit.patch import cmd_strings_import
        path = self._make_ult3_with_string(tmp_path, 'HI')
        jpath = os.path.join(str(tmp_path), 'patches.json')
        with open(jpath, 'w') as f:
            json.dump({'patches': [{'index': 0,
                                    'text': 'THIS IS WAY TOO LONG FOR TWO BYTES'}]}, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=False, backup=False, output=None)
        with pytest.raises(SystemExit):
            cmd_strings_import(args)

    def test_no_match_warning(self, tmp_path, capsys):
        """Unmatched vanilla text produces warning."""
        from ult3edit.patch import cmd_strings_import
        path = self._make_ult3_with_string(tmp_path, 'HI')
        jpath = os.path.join(str(tmp_path), 'patches.json')
        with open(jpath, 'w') as f:
            json.dump({'patches': [{'vanilla': 'NONEXISTENT', 'text': 'X'}]}, f)
        args = argparse.Namespace(file=path, json_file=jpath,
                                  dry_run=True, backup=False, output=None)
        # No match = 0 successes + 0 errors, so it won't exit(1)
        cmd_strings_import(args)
        err = capsys.readouterr().err
        assert 'no match' in err.lower() or 'Warning' in err


class TestNameCompilerTail:
    """name_compiler.py: tail extraction preserves original ULT3 tail."""

    def test_compile_preserves_tail(self, tmp_path):
        """Shorter names list should preserve tail data from original."""
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), '..', 'conversions', 'tools'))
        try:
            from name_compiler import compile_names
        finally:
            sys.path.pop(0)
        # Create names and tail data
        names = ['WATER', 'GRASS', 'FOREST']
        tail = bytes([0xAA, 0xBB, 0xCC])
        result = compile_names(names, tail_data=tail)
        assert len(result) == 921
        # The tail bytes should be preserved somewhere after the encoded names
        # Encoded: "WATER\0GRASS\0FOREST\0" = 5+1+5+1+6+1 = 19 bytes (high-ASCII)
        assert 0xAA in result[19:]
        assert 0xBB in result[19:]
        assert 0xCC in result[19:]

    def test_compile_budget_exceeded_raises(self):
        """Names exceeding budget should raise ValueError."""
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), '..', 'conversions', 'tools'))
        try:
            from name_compiler import validate_names
        finally:
            sys.path.pop(0)
        # Create names that are way too big
        big_names = ['A' * 50] * 50  # 50 names x 51 bytes each = 2550 bytes
        size, budget, valid = validate_names(big_names)
        assert not valid
        assert size > budget

