"""Discovery DTOs are immutable and report unknown numbers."""

from dataclasses import FrozenInstanceError

import pytest

from bs_database.parsers.errors import ParseError
from bs_database.parsers.models import ListEntry, ParsedNumber, PromoList, SetPage


def _entry(number: str, parsed: ParsedNumber | None) -> ListEntry:
    return ListEntry(number, parsed, "n", "u", None, None, None, ())


_P = ParsedNumber("BS", "BS01", "", "001", None, None)


def test_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        _P.family = "SD"  # type: ignore[misc]


def test_unknown_numbers_in_order() -> None:
    entries = (_entry("A", None), _entry("B", _P), _entry("C", None))
    assert PromoList(entries).unknown_numbers == ("A", "C")
    assert SetPage("t", None, None, entries).unknown_numbers == ("A", "C")


def test_parse_error_is_value_error() -> None:
    assert issubclass(ParseError, ValueError)
