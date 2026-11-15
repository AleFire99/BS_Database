"""Normalized goldens: html -> parse -> parsed store -> normalize_tree (#93)."""

from pathlib import Path

import pytest
from golden_support import (
    NORMALIZED_GOLDENS,
    REGEN_COMMAND,
    card_fixture_names,
    golden_path,
    normalized_documents,
)


@pytest.fixture(scope="module")
def documents(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return normalized_documents(tmp_path_factory.mktemp("goldens"))


@pytest.mark.parametrize("name", card_fixture_names())
def test_matches_golden(documents: dict[str, str], name: str) -> None:
    path = golden_path(name)
    assert path.is_file(), f"missing golden {path.name}; regenerate with {REGEN_COMMAND}"
    assert documents[name] == path.read_text(encoding="utf-8"), (
        f"{path.name} differs; regenerate with {REGEN_COMMAND}"
    )


def test_no_stale_goldens() -> None:
    expected = {golden_path(n).name for n in card_fixture_names()}
    assert {p.name for p in NORMALIZED_GOLDENS.glob("*.json")} == expected


def test_second_run_is_byte_equal(documents: dict[str, str], tmp_path: Path) -> None:
    assert normalized_documents(tmp_path) == documents
