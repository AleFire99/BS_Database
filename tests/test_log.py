import logging
from collections.abc import Iterator

import pytest

from bs_database.log import configure_logging


@pytest.fixture(autouse=True)
def restore_root() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def test_sets_level_and_is_idempotent() -> None:
    root = logging.getLogger()
    configure_logging("DEBUG")
    count = len(root.handlers)
    assert root.level == logging.DEBUG
    configure_logging("warning")
    assert len(root.handlers) == count
    assert root.level == logging.WARNING
    configure_logging(logging.ERROR)
    assert root.level == logging.ERROR
