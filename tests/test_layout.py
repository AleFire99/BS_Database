"""The target ingestion layout exists and every module names the issue that owns it."""

import importlib

import pytest

MODULES = [
    "bs_database.ingest",
    "bs_database.ingest.policy",
    "bs_database.ingest.http",
    "bs_database.ingest.cache",
    "bs_database.ingest.state",
    "bs_database.ingest.pipeline",
    "bs_database.parsers",
    "bs_database.parsers.models",
    "bs_database.parsers.batspi",
    "bs_database.parsers.batspi.index",
    "bs_database.parsers.batspi.set_page",
    "bs_database.parsers.batspi.card",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports_and_names_its_owner(name: str) -> None:
    module = importlib.import_module(name)
    assert module.__doc__ and "#" in module.__doc__
