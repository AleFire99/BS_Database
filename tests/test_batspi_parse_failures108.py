"""Parser failures found by the full scrape (#108), each on the real trimmed page of its class."""

import json
import logging
from pathlib import Path

import pytest

from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.batspi.card_sections import _targets
from bs_database.parsers.card_models import CardPage
from bs_database.parsers.errors import ParseError

HTML_DIR = Path(__file__).parent / "fixtures" / "html"
SECTIONS_LOGGER = "bs_database.parsers.batspi.card_sections"
MANIFEST = json.loads((HTML_DIR / "fixtures.json").read_text(encoding="utf-8"))


def parse(stem: str) -> CardPage:
    name = f"{stem}.html"
    return parse_card_page((HTML_DIR / name).read_text(encoding="utf-8"), MANIFEST[name]["url"])


def test_cost_line_with_a_trailing_slash() -> None:
    """巨獣の森 prints ``4(2)/白/``."""
    entry = parse("card_nexus_cost_slash").entries[0]
    assert entry.number == "BS18-067"
    assert entry.gameplay.cost == 4
    assert entry.gameplay.colors == ("白",)
    assert entry.gameplay.families == ()


def effect_headers(stem: str, number: str) -> list[str | None]:
    entry = next(e for e in parse(stem).entries if e.number == number)
    assert entry.text is not None
    return [e.header for e in entry.text.effects]


def test_header_with_a_blank_after_the_levels() -> None:
    """コジロンド・ゴレム: ``Lv1・Lv2・Lv3 【粉砕】『…』``."""
    headers = effect_headers("card_spirit_header_space", "BS15-053")
    assert "Lv1・Lv2・Lv3 【粉砕】『このスピリットのアタック時』" in headers


def test_header_with_an_ascii_colon() -> None:
    """紅玉の巨龍ボルガンド: ``Lv1・Lv2・Lv3:フラッシュ【覚醒】``."""
    page = parse("card_spirit_header_colon")
    entry = page.entries[0]
    assert entry.text is not None
    flash = next(e for e in entry.text.effects if e.header == "Lv1・Lv2・Lv3:フラッシュ【覚醒】")
    assert (flash.label, flash.levels) == ("フラッシュ", (1, 2, 3))
    assert [k.name for k in flash.keywords] == ["覚醒"]


def test_header_with_the_timing_before_the_keyword_and_parameter() -> None:
    """仮面ライダーマリカ: ``『…』【起動：フラッシュ】〔ターン1回〕``."""
    page = parse("card_spirit_header_timing")
    headers = [h for e in page.entries for h in effect_headers_of(e)]
    assert any(h and h.endswith("【起動：フラッシュ】〔ターン1回〕") for h in headers)


def effect_headers_of(entry: object) -> list[str | None]:
    text = getattr(entry, "text", None)
    return [e.header for e in text.effects] if text is not None else []


def printings(page: CardPage) -> list[tuple[str, str, str | None]]:
    return [(p.number, p.product_name_jp, p.rarity) for p in page.printings]


def test_printing_rows_resolve_by_the_number_in_their_text() -> None:
    """クリスタルクラック: ``<a>…</a> <C> (BS18-076)`` has no bold label."""
    page = parse("card_magic_printing_note_number")
    assert [e.number for e in page.entries] == ["BS18-076", "BS56-RV002"]
    rows = printings(page)
    assert ("BS18-076", "覇王編 第5弾：覇王大決戦", "C") in rows
    assert ("BS56-RV002", "真・転醒編 第1章：世界の真実", "C") in rows
    assert ("BS56-RV002", "覇王編 第5弾：覇王大決戦", "C") not in rows


def test_printing_row_without_a_number_goes_to_every_number_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """魔刃将ヘル・ブレド: the 参加賞 rows print no number (decision 3 of #108)."""
    with caplog.at_level(logging.WARNING, logger=SECTIONS_LOGGER):
        page = parse("card_spirit_printing_unnumbered")
    assert [e.number for e in page.entries] == ["P004", "P20-07"]
    rows = printings(page)
    assert ("P004", "ブースタードラフト参加賞", None) in rows
    assert ("P20-07", "ブースタードラフト参加賞", None) in rows
    assert sum("attached to all numbers" in r.message for r in caplog.records) == 4


NUMBERS = ["X003A", "X003D", "X003E", "X003S", "X003T"]


@pytest.mark.parametrize(
    ("label", "text", "expected"),
    [
        (None, " <C> (BS18-076)", ["BS18-076"]),
        (None, " <C>(シキツルさんイラスト) (BS18-076)", ["BS18-076"]),
        (None, " <X>(X003T,X003S)", ["X003S", "X003T"]),
        (None, " <X> (X003A、X003E)", ["X003A", "X003E"]),
        ("X003", "自販機ブースター(X003D)", ["X003D"]),
        ("X003", " <X>", NUMBERS),
        ("X003", "", NUMBERS),
        ("X003D", " <X>", ["X003D"]),
    ],
)
def test_targets_by_label_and_printed_numbers(
    label: str | None, text: str, expected: list[str]
) -> None:
    numbers = NUMBERS if "X003" in (label or text) else ["BS18-076", "BS56-RV002"]
    assert sorted(_targets(label, numbers, "ctx", text=text)) == sorted(expected)


def test_targets_without_a_number_raise_unless_told_to_attach_to_all() -> None:
    numbers = ["BS18-076", "BS56-RV002"]
    with pytest.raises(ParseError):
        _targets(None, numbers, "ctx", text=" <C>")
    assert _targets(None, numbers, "ctx", text=" <C>", fallback_all=True) == numbers
    assert _targets(None, ["BS01-001(A)", "BS01-001(B)"], "ctx", text=" <C>") == [
        "BS01-001(A)",
        "BS01-001(B)",
    ]


def test_one_block_shared_by_two_numbers_gives_each_number_an_entry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """巨人皇子アレクサンダー4世: one ``<pre>``, an h3 without a number, numbers EX023 and P027."""
    with caplog.at_level(logging.WARNING, logger="bs_database.parsers.batspi.card"):
        page = parse("card_spirit_shared_block")
    assert [e.number for e in page.entries] == ["EX023", "P027"]
    first, second = page.entries
    assert first.name_jp == second.name_jp
    assert first.gameplay == second.gameplay and first.text == second.text
    assert page.differences == ()
    assert {p.number for p in page.printings} <= {"EX023", "P027"}
    assert "one card block shared by the numbers" in caplog.text
