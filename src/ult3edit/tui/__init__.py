"""TUI editors for ult3edit. Requires prompt_toolkit (install with pip install ult3edit[tui])."""


def require_prompt_toolkit():  # pragma: no cover
    """Check that prompt_toolkit is available. Exit with helpful message if not."""
    try:
        import prompt_toolkit  # noqa: F401
        return
    except ImportError:
        import sys
        print(
            "Error: TUI editors require prompt_toolkit.\n"
            "Install with: pip install ult3edit[tui]",
            file=sys.stderr,
        )
        sys.exit(1)
