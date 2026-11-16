"""Promotion list parser, on the cached (partial) fixture."""

from collections import Counter
from pathlib import Path

import pytest

from bs_database.parsers.batspi.promo_list import parse_promo_list, parse_year_list
from bs_database.parsers.errors import ParseError


def _html(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / "html" / f"{name}.html").read_text("utf-8")


def test_counts_and_ends() -> None:
    entries = parse_promo_list(_html("list_promo")).entries
    assert len(entries) == 1210
    assert len({e.number for e in entries}) == 1210
    first, last = entries[0], entries[-1]
    assert (first.number, first.name) == ("P001", "焔竜翼人マ・ドー")
    assert first.section == ("Pナンバー", "Pナンバー")
    assert first.parsed is not None
    assert (first.parsed.family, first.parsed.series) == ("P", None)
    assert (last.number, last.name) == ("BS48-SP02", "月光のバローネ")
    assert last.section == ("BS-SPナンバー",)


def test_count_by_h3() -> None:
    entries = parse_promo_list(_html("list_promo")).entries
    assert Counter(e.section[0] for e in entries) == {
        "Pナンバー": 382,
        "CPナンバー": 411,
        "PBナンバー": 197,
        "PXナンバー": 120,
        "Xナンバー": 53,
        "EXナンバー": 45,
        "BS-SPナンバー": 2,
    }


def test_unknown_numbers_and_shapes() -> None:
    page = parse_promo_list(_html("list_promo"))
    assert page.unknown_numbers == (
        "PB17-RV X01",
        "PB17-RV X02",
        "PB17-RV X03",
        *(f"PB39-RV X0{i}" for i in range(1, 6)),
        "PB44-RV X01",
    )
    by_number = {e.number: e for e in page.entries}
    for number in ("P17-EXG01", "P17-EXG06", "CP14-X01R", "X003A", "26RBS02-CP01"):
        assert by_number[number].parsed is not None, number


def test_prose_lines_are_not_entries() -> None:
    for e in parse_promo_list(_html("list_promo")).entries:
        assert not e.name.startswith(("キャンペーン", "データベース"))
        assert e.number.isascii()


@pytest.mark.parametrize("html", ["", '<div id="body"><h2>t</h2><p>no cards</p></div>'])
def test_malformed(html: str) -> None:
    with pytest.raises(ParseError):
        parse_promo_list(html)


def test_index_page_is_rejected() -> None:
    with pytest.raises(ParseError):
        parse_promo_list(_html("index"))


def test_year_list_has_no_h2_and_is_read_by_parse_year_list() -> None:
    """バトルスキーイベント提供記念品 (#108): an h3 title and h4 years."""
    html = _html("list_year_event_gifts")
    with pytest.raises(ParseError, match="no title heading"):
        parse_promo_list(html)
    listing = parse_year_list(html)
    assert listing.entries
    assert {e.section[-1] for e in listing.entries} >= {"2016年", "2017年"}
    assert all(e.section[0] == "バトルスキーイベント提供記念品" for e in listing.entries)
    first = listing.entries[0]
    assert (first.number, first.name) == ("SD26-013", "フェイタルドロー")


def test_year_list_without_entries_raises() -> None:
    with pytest.raises(ParseError, match="no card entries"):
        parse_year_list('<div id="body"><h3>t</h3></div>')
