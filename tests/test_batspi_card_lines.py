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
        ("スピリット", ("スピリット", None, None, None)),
        ("スピリット ", ("スピリット", None, None, None)),
        ("ネクサス(制限カード<1>)", ("ネクサス", 1, None, None)),
        ("アルティメット", ("アルティメット", None, None, None)),
        ("契約スピリット", ("スピリット", None, "契約", None)),
        ("契約ネクサス", ("ネクサス", None, "契約", None)),
        ("契約アルティメット", ("アルティメット", None, "契約", None)),
        ("トークンネクサス", ("ネクサス", None, "トークン", None)),
        ("スピリット(闇)", ("スピリット", None, None, "闇")),
        ("スピリット(禁止カード)", ("スピリット", None, None, "禁止カード")),
        ("スピリット(光)(制限カード<1>)", ("スピリット", 1, None, "光")),
    ],
)
def test_type_line(line: str, expected: tuple[str, int | None, str | None, str | None]) -> None:
    assert parse_type_line(line) == expected


@pytest.mark.parametrize("line", ["コスト", "スピリットX", "", "スピリット()", "契約マジックX"])
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
        # #108: colourless card, trailing blank, stray trailing slash
        ("15(0)/(なし)", (15, Reduction(0, ()), (), ())),
        ("4(2)/青 ", (4, Reduction(2, ()), ("青",), ())),
        ("4(2)/白/", (4, Reduction(2, ()), ("白",), ())),
        ("3(紫1極1)/紫 ", (3, Reduction(None, sc(("紫", 1), ("極", 1))), ("紫",), ())),
        ("2(1)/白/眷属 ", (2, Reduction(1, ()), ("白",), ("眷属",))),
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
        ("<1>Lv1 5000 <0>合体 +5000", ((Level(1, 1, 5000),), 5000, None)),
        (
            "<1>Lv1 6000 <5>Lv2/真界放 10000",
            ((Level(1, 1, 6000), Level(2, 5, 10000, None, "真界放")), None, None),
        ),
        (
            "<1>Lv3 12000 <7> Lv6 30000",
            ((Level(3, 1, 12000), Level(6, 7, 30000)), None, None),
        ),
        ("<1>Lv1 X0000", ((Level(1, 1, None, None, "X0000"),), None, None)),
        (
            "<0>Lv1 <C2>Lv2",
            ((Level(1, 0, None), Level(2, None, None, "C2", None)), None, None),
        ),
        (
            "<1>Lv1 7000 <2>条件:赤赤 Lv2 9000",
            ((Level(1, 1, 7000), Level(2, 2, 9000, "条件:赤赤", None)), None, None),
        ),
        ("<1>Lv1　3000 <3>Lv2　5000", ((Level(1, 1, 3000), Level(2, 3, 5000)), None, None)),
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
        ("シンボル：EX赤", (SymbolCount("赤", 1, "EX"),)),
        ("シンボル：EX赤 赤", (SymbolCount("赤", 1, "EX"), SymbolCount("赤", 1))),
        (
            "シンボル：神(青)神(白)",
            (SymbolCount("神", 1, None, "青"), SymbolCount("神", 1, None, "白")),
        ),
        ("シンボル：神(青)神(青)", (SymbolCount("神", 2, None, "青"),)),
    ],
)
def test_symbol_line(line: str, expected: object) -> None:
    assert parse_symbol_line(line) == expected


@pytest.mark.parametrize("line", ["シンボル：X", "赤"])
def test_symbol_line_errors(line: str) -> None:
    with pytest.raises(ParseError):
        parse_symbol_line(line)


def test_families_split_on_the_half_width_middle_dot() -> None:
    # 歌鳥･漂精 uses U+FF65 instead of U+30FB (#109)
    assert parse_cost_line("4(2)/緑/歌鳥･漂精")[3] == ("歌鳥", "漂精")
    assert parse_cost_line("4(2)/緑/歌鳥・漂精")[3] == ("歌鳥", "漂精")
