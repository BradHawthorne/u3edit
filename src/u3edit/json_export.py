"""Shared JSON export utility for u3edit tools."""

import json
import sys


def export_json(data, path: str | None = None) -> None:
    """Write data as formatted JSON to a file or stdout.

    Args:
        data: Any JSON-serializable data structure.
        path: Output file path, or None for stdout.
    """
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if path:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        print(text)
