"""Records and the unmapped collector (#93)."""

import dataclasses
import json

import pytest

from bs_database.normalize.records import (
    CodedTerm,
    NormalizedPage,
    UnmappedCollector,
    UnmappedTerm,
)


def test_collector_deduplicates_and_sorts() -> None:
    collector = UnmappedCollector()
    collector.add("keywords", "b", "BS01-002")
    collector.add("families", "z", "BS01-001")
    collector.add("keywords", "b", "BS01-002")
    collector.add("families", "a", "BS01-003")
    assert collector.terms() == (
        UnmappedTerm("families", "a", "BS01-003"),
        UnmappedTerm("families", "z", "BS01-001"),
        UnmappedTerm("keywords", "b", "BS01-002"),
    )


def test_collector_is_empty_by_default() -> None:
    assert UnmappedCollector().terms() == ()


@pytest.mark.parametrize(
    ("kind", "closed"),
    [
        ("colors", True),
        ("symbols", True),
        ("card_types", True),
        ("rarities", True),
        ("variants", True),
        ("product_types", True),
        ("families", False),
        ("keywords", False),
    ],
)
def test_closed_classification(kind: str, closed: bool) -> None:
    assert UnmappedTerm(kind, "x", "N").closed is closed


def test_page_is_json_ready() -> None:
    page = NormalizedPage("u", "t", (), (), (), (), (UnmappedTerm("families", "x", "N"),))
    assert json.dumps(dataclasses.asdict(page), ensure_ascii=False)


def test_records_are_frozen() -> None:
    term = CodedTerm("赤", "red")
    with pytest.raises(dataclasses.FrozenInstanceError):
        term.code = "x"  # type: ignore[misc]
