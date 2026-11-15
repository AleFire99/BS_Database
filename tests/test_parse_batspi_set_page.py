"""Set page parser, on the cached fixtures and on synthetic pages."""

from collections import Counter
from pathlib import Path

import pytest

from bs_database.parsers.batspi.numbers import parse_number
from bs_database.parsers.batspi.promo_list import parse_promo_list
from bs_database.parsers.batspi.set_page import parse_set_page
from bs_database.parsers.errors import ParseError
from bs_database.parsers.models import ListEntry, SetPage


def _html(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / "html" / f"{name}.html").read_text("utf-8")


def _entry(page: SetPage, number: str) -> ListEntry:
    return next(e for e in page.entries if e.number == number)


# fixture, title, entries, first (number, name, section), last number, code, date
SETS = [
    (
        "set_bs01",
        "第一弾",
        116,
        ("BS01-001", "ゴラドン", ("赤", "スピリット")),
        "BS01-X04",
        "BS01",
        "2008-09-13",
    ),
    (
        "set_bs52",
        "転醒編 第1章：輪廻転生",
        116,
        ("BS52-001", "リューマン・ダッシュ", ("赤", "スピリット")),
        "BS52-CP14",
        "BS52",
        "2020-04-25",
    ),
    (
        "set_sd54",
        "コラボスターター【ガンダム ～OPERATION UC～】",
        19,
        ("SD54-001", "ロト", ("スピリット",)),
        "SD06-016",
        "SD54",
        "2020-03-14",
    ),
    (
        "set_cb34",
        "コラボブースター【仮面ライダー ～善悪の選択～】",
        93,
        ("CB34-001", "仮面ライダークウガ グローイングフォーム ［3］", ("赤", "スピリット")),
        "CB17-X06",
        "CB34",
        "2025-03-29",
    ),
    (
        "set_wafer",
        "バトルスピリッツ ウエハース ～蛇皇襲来～",
        25,
        ("SD43-RV001", "ブレイドラ", ("赤",)),
        "BSC34-015",
        None,
        "2026-01-12",
    ),
    (
        "set",
        "契約編:環 第1章：廻帰再醒",
        108,
        ("BS72-001", "サンダー・Z・ジャンガリア", ("赤", "スピリット")),
        "BS49-RV012",
        "BS72",
        "2025-05-17",
    ),
]


@pytest.mark.parametrize(("fixture", "title", "count", "first", "last", "code", "date"), SETS)
def test_fixture_pages(
    fixture: str,
    title: str,
    count: int,
    first: tuple[str, str, tuple[str, ...]],
    last: str,
    code: str | None,
    date: str,
) -> None:
    page = parse_set_page(_html(fixture))
    assert page.title == title
    assert len(page.entries) == count
    assert (page.entries[0].number, page.entries[0].name, page.entries[0].section) == first
    assert page.entries[-1].number == last
    assert page.set_code == code
    assert page.release_date == date
    assert page.unknown_numbers == ()
    assert all(e.url.startswith("https://batspi.com/index.php?") for e in page.entries)
    assert all("リスト解析表示" not in e.name for e in page.entries)


def test_bs01_details() -> None:
    page = parse_set_page(_html("set_bs01"))
    first = page.entries[0]
    assert (first.rarity, first.copies, first.note) == (None, None, None)
    last = page.entries[-1]
    assert (last.rarity, last.section) == ("X", ("Xレア",))
    assert Counter(e.rarity for e in page.entries) == {None: 74, "U": 17, "R": 14, "M": 7, "X": 4}


def test_bs52_details() -> None:
    page = parse_set_page(_html("set_bs52"))
    rarities = Counter(e.rarity for e in page.entries)
    assert rarities["転醒R"] == 12
    assert rarities["転醒X"] == 3
    assert rarities["CP"] == 17
    tx = _entry(page, "BS52-TX01")
    assert tx.name == "赤の世界／赤き神龍皇"
    assert (tx.rarity, tx.section) == ("転醒X", ("転醒Xレア",))
    assert _entry(page, "BS52-TCP01").rarity == "CP"
    assert _entry(page, "BS52-X01").note == "(パラレルあり)"
    last = page.entries[-1]
    assert last.section == ("BOX購入特典キャンペーンカード",)


def test_sd54_details() -> None:
    page = parse_set_page(_html("set_sd54"))
    assert page.entries[0].copies == 3
    assert page.entries[-1].copies == 3
    assert page.entries[-1].section == ("差し替えカード",)
    assert Counter(e.rarity for e in page.entries) == {None: 14, "R": 2, "X": 2, "M": 1}
    m = _entry(page, "SD54-009")
    assert (m.rarity, m.copies, m.note) == ("M", 2, None)
    x = _entry(page, "SD54-X01")
    assert (x.rarity, x.copies, x.note) == ("X", 2, "(パラレルあり)")


def test_cb34_details() -> None:
    page = parse_set_page(_html("set_cb34"))
    last = page.entries[-1]
    assert (last.rarity, last.note, last.section) == ("X", "(SECRETあり)", ("BOX購入特典",))
    cx = _entry(page, "CB34-CX01")
    assert (cx.name, cx.rarity, cx.note) == ("仮面ライダーファイズ ［4］", "契約X", "(SECRETあり)")


def test_wafer_details() -> None:
    page = parse_set_page(_html("set_wafer"))
    first = page.entries[0]
    assert first.note == "（※ブロックアイコン<5>）(新規CGイラスト)"
    assert first.rarity is None
    last = page.entries[-1]
    assert (last.rarity, last.note, last.section) == ("M", "（※ブロックアイコン<6>）", ("6色",))
    xv = _entry(page, "P25-06")
    assert xv.rarity == "XV"
    assert xv.parsed is not None
    assert (xv.parsed.family, xv.parsed.series) == ("P", "P25")
    leo = _entry(page, "BSC45-095")
    assert leo.rarity == "R"
    assert (
        leo.note == "（※ブロックアイコン<11>）(新規CGイラスト「光龍騎神サジット・アポロドラゴン」)"
    )


def test_bs72_details() -> None:
    page = parse_set_page(_html("set"))
    assert page.entries[-1].note == "(SECRETあり)"
    assert page.entries[-1].section == ("キャンペーンカード",)
    assert _entry(page, "BS72-AX01").rarity == "AX"
    assert all(e.section != ("赤",) or e.parsed for e in page.entries)
    assert "赤" not in {e.name for e in page.entries}


def _page(cards: str) -> str:
    return (
        '<div id="body"><h2>Title</h2><p>2020年3月4日発売</p>'
        f"<h2>収録カード</h2><h3>赤</h3>{cards}<h3>リンク</h3>"
        '<p>X-1 <a href="index.php?after">after</a></p></div>'
    )


def test_unknown_number_kept() -> None:
    page = parse_set_page(_page('<p>ZZ99-001 <a href="index.php?a">A</a><br/></p>'))
    assert page.release_date == "2020-03-04"
    assert len(page.entries) == 1
    assert page.entries[0].parsed is None
    assert page.unknown_numbers == ("ZZ99-001",)
    assert page.set_code is None


def test_faces() -> None:
    page = parse_set_page(
        _page(
            '<p>BS73-TCP01(A) <a href="index.php?a">A</a><br/>'
            'BS73-TCP01(B) <a href="index.php?b">B</a></p>'
        )
    )
    assert [e.parsed.face for e in page.entries if e.parsed] == ["(A)", "(B)"]
    assert page.set_code == "BS73"


def test_missing_cards_heading() -> None:
    with pytest.raises(ParseError):
        parse_set_page('<div id="body"><h2>Title</h2><p>x</p></div>')
    with pytest.raises(ParseError):
        parse_set_page("")


def test_every_fixture_number_parses() -> None:
    for fixture, *_ in SETS:
        for e in parse_set_page(_html(fixture)).entries:
            assert parse_number(e.number) is not None, e.number


def test_invalid_release_date_is_none() -> None:
    html = _page('<p>A-01 <a href="index.php?a">A</a></p>').replace("2020年3月4日", "2020年2月30日")
    assert parse_set_page(html).release_date is None


_EDIT = '<a href="index.php?cmd=edit&amp;page=New%20Card&amp;refer=x">New Card</a>'


def test_missing_card_page_is_recorded() -> None:
    page = parse_set_page(
        _page(
            f'<p>BS01-001 <a href="index.php?a">A</a><br/>BS01-002 {_EDIT}<br/>'
            'Some prose <a href="index.php?cmd=edit&amp;page=p">edit</a></p>'
        )
    )
    assert [e.number for e in page.entries] == ["BS01-001"]
    assert [(m.number, m.name, m.section) for m in page.missing] == [
        ("BS01-002", "New Card", ("赤",))
    ]


def test_missing_card_page_in_promo_list() -> None:
    html = (
        '<div id="body"><h2>t</h2><h3>P</h3><p>P001 <a href="index.php?a">A</a><br/>'
        f"P002 {_EDIT}</p></div>"
    )
    page = parse_promo_list(html)
    assert len(page.entries) == 1
    assert [m.number for m in page.missing] == ["P002"]
