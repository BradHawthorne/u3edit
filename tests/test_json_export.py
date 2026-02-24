"""Tests for JSON export utility."""

import json
import os

from ult3edit.json_export import export_json


class TestExportToFile:
    def test_write_dict(self, tmp_dir):
        path = os.path.join(tmp_dir, 'out.json')
        export_json({'key': 'value'}, path)
        with open(path) as f:
            data = json.load(f)
        assert data == {'key': 'value'}

    def test_write_list(self, tmp_dir):
        path = os.path.join(tmp_dir, 'out.json')
        export_json([1, 2, 3], path)
        with open(path) as f:
            data = json.load(f)
        assert data == [1, 2, 3]

    def test_unicode(self, tmp_dir):
        path = os.path.join(tmp_dir, 'out.json')
        export_json({'name': 'caf\u00e9'}, path)
        with open(path, encoding='utf-8') as f:
            text = f.read()
        assert 'caf\u00e9' in text  # ensure_ascii=False preserves unicode


class TestExportToStdout:
    def test_prints_json(self, capsys):
        export_json({'a': 1})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {'a': 1}
