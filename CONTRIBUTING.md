# Contributing to ult3edit

Thanks for your interest in contributing to ult3edit, a data file toolkit for Ultima III: Exodus (Apple II, 1983). Python 3.10+, no runtime dependencies, MIT license.

## Development Setup

```bash
git clone https://github.com/BradHawthorne/ult3edit.git
cd ult3edit
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev,tui]"
```

Python 3.10 is the minimum supported version. Do not use `match` statements, `StrEnum`, or any features introduced in 3.11+.

## Running Tests

```bash
pytest -v                        # Run all 2512 tests
pytest tests/test_roster.py      # Run one module
pytest -v tests/test_bcd.py::TestBcdToInt::test_zero   # Run a single test

# Coverage report (100% enforced in CI)
pytest --cov=ult3edit --cov-report=term-missing
```

All tests must pass and 100% code coverage must be maintained before submitting a pull request. New code should include tests — coverage will fail in CI if any lines are left uncovered.

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting:

```bash
ruff check src/ tests/
```

Rules: E, F, W with ignores for E501 (line length), E702, E741, and E402.
Target line length is 120 characters.

## Module Conventions

Each game data type lives in its own module under `src/ult3edit/`. Most modules follow a standard contract:

- **Data class** (e.g., `Character`, `Monster`) -- wraps a `bytearray` with `@property` accessors for fields.
- **`load_*(path)` / `save_*(path, obj)`** -- file I/O.
- **`cmd_view(args)` / `cmd_edit(args)` / `cmd_import(args)`** -- CLI command handlers.
- **`register_parser(subparsers)`** -- registers argparse subcommands for `cli.py`.
- **`dispatch(args)`** -- routes parsed args to the correct handler.
- **`main()`** -- standalone entry point with full parity to `register_parser()`.

All shared constants (tile tables, attribute lists, format layouts) live in `constants.py` as the single source of truth.

See `CLAUDE.md` for detailed architecture documentation including binary encoding conventions, file format layouts, and engine internals.

## Testing Conventions

- Tests use **synthesized binary data** -- no real game files are needed or included.
- Fixtures in `tests/conftest.py` build exact binary blobs matching Ultima III formats.
- Each fixture produces known values so tests can assert decoded fields directly.
- Setter tests should verify validation behavior (clamping, length limits, BCD encoding).
- When adding a new feature, add tests that cover both the happy path and edge cases.

## Submitting Changes

1. Fork the repository and create a feature branch from `main`.
2. Make your changes, following the conventions above.
3. Add or update tests for any new or changed behavior.
4. Run `pytest -v` and `ruff check src/ tests/` -- both must pass cleanly.
5. Write a clear commit message describing what changed and why.
6. Open a pull request against `main`.

If you are unsure about an approach, feel free to open an issue first to discuss it.
