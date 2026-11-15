"""Pure line parsers of the batspi card parser."""

import pytest

from bs_database.parsers.batspi.card import (
    parse_cost_line,
    parse_level_line,
    parse_symbol_line,
    parse_type_line,
)
from bs_database.parsers.card_models import Level, Overclock, Reduction, SymbolCount
from bs_database.parsers.errors import ParseError


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("スピリット", ("スピリット", None)),
        ("スピリット ", ("スピリット", None)),
        ("ネクサス(制限カード<1>)", ("ネクサス", 1)),
        ("アルティメット", ("アルティメット", None)),
    ],
)
def test_type_line(line: str, expected: tuple[str, int | None]) -> None:
    assert parse_type_line(line) == expected


@pytest.mark.parametrize("line", ["コスト", "スピリットX", ""])
def test_type_line_errors(line: str) -> None:
    with pytest.raises(ParseError):
        parse_type_line(line)


def sc(*pairs: tuple[str, int]) -> tuple[SymbolCount, ...]:
    return tuple(SymbolCount(s, c) for s, c in pairs)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "4(赤2神1)/赤/眷属・武迅",
            (4, Reduction(None, sc(("赤", 2), ("神", 1))), ("赤",), ("眷属", "武迅")),
        ),
        ("3(2)/赤/皇獣", (3, Reduction(2, ()), ("赤",), ("皇獣",))),
        ("6()/赤/起幻・古竜", (6, Reduction(None, ()), ("赤",), ("起幻", "古竜"))),
        ("0(0)/赤/爬獣", (0, Reduction(0, ()), ("赤",), ("爬獣",))),
        (
            "6(全1極3)/赤/極契約・新生・古竜",
            (6, Reduction(None, sc(("全", 1), ("極", 3))), ("赤",), ("極契約", "新生", "古竜")),
        ),
        ("4(2)/赤", (4, Reduction(2, ()), ("赤",), ())),
        (
            "4(赤1紫1)/赤紫",
            (4, Reduction(None, sc(("赤", 1), ("紫", 1))), ("赤", "紫"), ()),
        ),
        ("1(1)/赤紫緑白黄青", (1, Reduction(1, ()), tuple("赤紫緑白黄青"), ())),
        ("0(0)/白/絶晶神", (0, Reduction(0, ()), ("白",), ("絶晶神",))),
    ],
)
def test_cost_line(line: str, expected: object) -> None:
    assert parse_cost_line(line) == expected


@pytest.mark.parametrize("line", ["4/赤", "4(2)/X/眷属", "4(Q1)/赤", "abc"])
def test_cost_line_errors(line: str) -> None:
    with pytest.raises(ParseError):
        parse_cost_line(line)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "<1>Lv1 3000 <3>Lv2 7000",
            ((Level(1, 1, 3000), Level(2, 3, 7000)), None, None),
        ),
        ("<0>Lv1 <1>Lv2", ((Level(1, 0, None), Level(2, 1, None)), None, None)),
        ("<1>Lv1 3000 <0>合体+3000", ((Level(1, 1, 3000),), 3000, None)),
        (
            "<1>Lv3 10000 <3>Lv4 14000 OC<5+>+6000",
            ((Level(3, 1, 10000), Level(4, 3, 14000)), None, Overclock(5, 6000)),
        ),
        ("<0>Lv1 3000 <0>合体+3000", ((Level(1, 0, 3000),), 3000, None)),
    ],
)
def test_level_line(line: str, expected: object) -> None:
    assert parse_level_line(line) == expected


@pytest.mark.parametrize("line", ["<1>Lvx 3000", "<1>Lv1 3000 foo"])
def test_level_line_errors(line: str) -> None:
    with pytest.raises(ParseError):
        parse_level_line(line)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("シンボル：なし", ()),
        ("シンボル：赤", sc(("赤", 1))),
        ("シンボル：神", sc(("神", 1))),
        ("シンボル：極", sc(("極", 1))),
        ("シンボル：赤赤", sc(("赤", 2))),
        ("シンボル：赤2", sc(("赤", 2))),
    ],
)
def test_symbol_line(line: str, expected: object) -> None:
    assert parse_symbol_line(line) == expected


@pytest.mark.parametrize("line", ["シンボル：X", "赤"])
def test_symbol_line_errors(line: str) -> None:
    with pytest.raises(ParseError):
        parse_symbol_line(line)
