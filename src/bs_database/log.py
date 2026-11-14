"""Logging setup."""

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_handler: logging.Handler | None = None


def configure_logging(level: str | int = "INFO") -> None:
    """Configure the root logger to write to stderr. Safe to call repeatedly."""
    global _handler
    root = logging.getLogger()
    if _handler is not None:
        root.removeHandler(_handler)
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(_handler)
    root.setLevel(level.upper() if isinstance(level, str) else level)
