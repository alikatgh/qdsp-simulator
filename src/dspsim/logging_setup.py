from __future__ import annotations
import logging
import sys

def setup_logging(level: str = "WARNING") -> None:
    """
    Configure root logging with a terse, consistent format.
    Level: DEBUG|INFO|WARNING|ERROR|CRITICAL
    """
    lvl = getattr(logging, level.upper(), logging.WARNING)
    handler = logging.StreamHandler(stream=sys.stderr)
    formatter = logging.Formatter(
        fmt="%(levelname).1s %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(lvl)
    # Remove existing handlers to avoid duplicate logs in repeated runs.
    root.handlers.clear()
    root.addHandler(handler)
