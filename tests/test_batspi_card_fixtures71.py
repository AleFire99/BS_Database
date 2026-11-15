"""Text, credits, flavour (and later printings, images) of the 11 card fixtures (#71)."""

import json
import logging
from pathlib import Path

import pytest

from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.card_models import CardEntry, CardPage, CardText

HTML_DIR = Path(__file__).parent / "fixtures" / "html"
MANIFEST = json.loads((HTML_DIR / "fixtures.json").read_text(encoding="utf-8"))
ATK = "『このスピリットのアタック時』"
START = "『自分のアタックステップ開始時』"
STEP = "『自分のアタックステップ』"
PLACE = "『このネクサスの配置時』"
ULT_ATK = "『このアルティメットのアタック時』"
SUMMON = "『このブレイヴの召喚時』"
CP = "『お互いのアタックステップ』"

STEMS = [
    "card_spirit",
    "card_nexus",
    "card_magic",
    "card_magic_flash",
    "card_nexus_soukaishin",
    "card_brave",
    "card_ultimate",
    "card_flip",
    "card_spirit_xx_bs31",
    "card_spirit_bs01",
    "card_promo",
]


def parse(stem: str) -> CardPage:
    name = f"{stem}.html"
    html = (HTML_DIR / name).read_text(encoding="utf-8")
    return parse_card_page(html, MANIFEST[name]["url"])


def entry(stem: str, number: str) -> CardEntry:
    return next(e for e in parse(stem).entries if e.number == number)


def text_of(stem: str, number: str) -> CardText:
    text = entry(stem, number).text
    assert text is not None
    return text


# (position, form, levels, label, keyword names, timing, lines of text)
EFFECTS: dict[
    tuple[str, str], list[tuple[int, str, tuple[int, ...], str | None, list[str], str | None, int]]
] = {
    ("card_spirit", "BS72-007"): [
        (1, "header", (1, 2), None, [], START, 1),
        (2, "header", (2,), None, [], STEP, 1),
    ],
    ("card_nexus", "BS72-069"): [
        (1, "header", (1, 2), None, [], PLACE, 3),
        (2, "header", (2,), None, [], None, 1),
    ],
    ("card_magic", "BS72-075"): [
        (1, "keyword_line", (), None, ["ミラージュ"], None, 1),
        (2, "header", (), None, ["セット中"], START, 2),
        (3, "header", (), "メイン", [], None, 4),
    ],
    ("card_magic_flash", "BS01-117"): [
        (1, "header", (), "メイン", [], None, 1),
        (2, "header", (), "フラッシュ", [], None, 1),
    ],
    ("card_magic_flash", "BSC22-117"): [
        (1, "header", (), "メイン", [], None, 2),
        (2, "header", (), "フラッシュ", [], None, 1),
    ],
    ("card_nexus_soukaishin", "BS44-X07"): [
        (1, "keyword_line", (), None, ["神託"], None, 1),
        (2, "plain", (), None, [], None, 2),
        (3, "header", (1, 2), None, [], None, 1),
        (4, "header", (1, 2), "フラッシュ", ["神技"], CP, 1),
        (5, "header", (2,), None, ["神域"], STEP, 1),
    ],
    ("card_brave", "BS10-062"): [
        (1, "header", (1,), None, [], SUMMON, 2),
        (2, "header", (), None, ["合体時", "激突"], ATK, 2),
    ],
    ("card_brave", "BS38-RV022"): [
        (1, "plain", (), None, [], None, 1),
        (2, "header", (1,), None, [], SUMMON, 2),
    ],
    ("card_ultimate", "SD19-X01"): [
        (1, "header", (3, 4, 5), None, ["Uトリガー"], ULT_ATK, 4),
        (2, "header", (4, 5), "フラッシュ", ["真・覚醒"], ULT_ATK, 1),
    ],
    ("card_ultimate", "SD67-CP01"): [
        (1, "header", (), "フラッシュ", ["契約煌臨"], "『自分のターン』", 1),
        (2, "header", (3, 4), None, ["Uトリガー"], ULT_ATK, 3),
        (3, "header", (3, 4), None, ["OC中"], ULT_ATK, 1),
    ],
    ("card_flip", "BS52-TX01(A)"): [
        (1, "header", (1,), None, ["転醒"], None, 1),
        (2, "header", (1,), None, [], PLACE, 1),
        (3, "header", (1,), None, [], STEP, 2),
    ],
    ("card_flip", "BS52-TX01(B)"): [
        (1, "plain", (), None, [], None, 1),
        (2, "header", (1,), None, [], "『このスピリットの転醒時』", 2),
        (3, "header", (1,), None, ["根幻回帰"], None, 1),
        (4, "header", (1,), None, [], None, 2),
    ],
    ("card_flip", "BS73-TCP01(A)"): [
        (1, "header", (1,), None, ["転醒"], None, 1),
        (2, "header", (1,), None, [], PLACE, 1),
        (3, "header", (1,), None, [], STEP, 1),
    ],
    ("card_flip", "BS73-TCP01(B)"): [
        (1, "plain", (), None, [], None, 1),
        (2, "header", (1, 2), None, [], "『このスピリットの転醒/アタック時』", 1),
        (3, "header", (1, 2), None, ["根幻回帰"], None, 1),
        (4, "header", (1, 2), None, [], None, 1),
    ],
    ("card_spirit_xx_bs31", "BS31-XX02"): [
        (1, "plain", (), None, [], None, 1),
        (2, "header", (1, 2), None, ["超装甲"], None, 1),
        (3, "header", (2,), None, [], None, 1),
    ],
    ("card_spirit_bs01", "BS01-001"): [],
    ("card_spirit_bs01", "BSC22-001"): [],
    ("card_promo", "P001"): [],
    ("card_promo", "EX001"): [],
    ("card_promo", "P20-19"): [
        (1, "plain", (), None, [], None, 1),
        (2, "header", (1, 2, 3), None, [], None, 1),
        (3, "header", (2, 3), None, [], "『このスピリットのアタック/ブロック時』", 1),
    ],
}


@pytest.mark.parametrize(("key", "expected"), list(EFFECTS.items()), ids=[k[1] for k in EFFECTS])
def test_effects(key: tuple[str, str], expected: list[tuple[object, ...]]) -> None:
    effects = text_of(*key).effects
    actual = [
        (
            e.position,
            e.form,
            e.levels,
            e.label,
            [k.name for k in e.keywords],
            e.timing,
            len(e.text.split("\n")) if e.text else 0,
        )
        for e in effects
    ]
    assert actual == expected


def test_every_fixture_number_is_covered() -> None:
    assert {(s, e.number) for s in STEMS for e in parse(s).entries} == set(EFFECTS)


def test_keyword_parameters_as_printed() -> None:
    magic = text_of("card_magic", "BS72-075").effects[0]
    assert (magic.keywords[0].bracket, magic.keywords[0].parameter) == (
        "【",
        "コスト2(1)(このカードは手札からセットできる)",
    )
    assert magic.text == magic.header
    oracle = text_of("card_nexus_soukaishin", "BS44-X07").effects
    assert (oracle[0].keywords[0].bracket, oracle[0].keywords[0].parameter) == ("《", None)
    assert oracle[0].text == "《神託》〔星竜/界渡/化神＆コスト3以上〕"
    assert oracle[3].keywords[0].parameter == "2"
    flip = text_of("card_flip", "BS52-TX01(A)").effects[0].keywords[0]
    assert flip.parameter == "自分のカウント5以下(転醒は同時に使えない)"
    contract = text_of("card_ultimate", "SD67-CP01").effects[0].keywords[0]
    assert (contract.bracket, contract.parameter) == ("《", "極契約＆C3以上")
    armor = text_of("card_spirit_xx_bs31", "BS31-XX02").effects[1].keywords[0]
    assert armor.parameter == "赤/紫/緑/白/黄/青"


def test_plain_text_and_trailing_space() -> None:
    effects = text_of("card_spirit_xx_bs31", "BS31-XX02").effects
    assert effects[0].text == "自分の白以外のスピリットがいる間、このカードをコスト8にする。"
    assert effects[1].header is not None and not effects[1].header.endswith(" ")
    assert text_of("card_promo", "P20-19").effects[0].text.startswith("このカードの軽減シンボルは")


SIDE: dict[tuple[str, str], tuple[tuple[str, ...], str | None, str | None]] = {
    ("card_brave", "BS10-062"): (("合体条件：コスト3以上",), None, None),
    ("card_brave", "BS38-RV022"): (
        ("右合体条件：コスト5以上", "左合体条件：コスト3以上"),
        None,
        None,
    ),
    ("card_ultimate", "SD19-X01"): ((), "【召喚条件：自分の赤スピリット1体以上】", None),
    ("card_ultimate", "SD67-CP01"): (
        (),
        "【召喚条件：魂状態/煌臨元を含む自分の赤スピリット/アルティメット1体以上】",
        "OC条件：カウント5以上",
    ),
}


@pytest.mark.parametrize("key", list(EFFECTS), ids=[k[1] for k in EFFECTS])
def test_side_conditions(key: tuple[str, str]) -> None:
    text = text_of(*key)
    assert (text.fusion_conditions, text.summon_condition, text.overclock_condition) == SIDE.get(
        key, ((), None, None)
    )


# (illustrators, concepts) as (name, note) pairs
CREDITS: dict[
    tuple[str, str], tuple[list[tuple[str, str | None]], list[tuple[str, str | None]]]
] = {
    ("card_spirit", "BS72-007"): ([("伊藤正市", None)], []),
    ("card_nexus", "BS72-069"): (
        [("藤原ひさし", None), ("平坂康也", "契約編：環 第3章：覇極来臨")],
        [],
    ),
    ("card_magic", "BS72-075"): (
        [("高梨かりた", None), ("ikuyoan", "プロモーションカード・ルー")],
        [],
    ),
    ("card_magic_flash", "BS01-117"): ([], []),
    ("card_magic_flash", "BSC22-117"): ([("しもがさ美穂", "バトスピ15周年スペシャルパック")], []),
    ("card_nexus_soukaishin", "BS44-X07"): ([("安達洋介", None)], []),
    ("card_brave", "BS10-062"): ([("斉藤和衛", None)], [("石垣純哉", None)]),
    ("card_brave", "BS38-RV022"): (
        [("斉藤和衛", None), ("SUNRISE D.I.D.", None)],
        [("石垣純哉", None)],
    ),
    ("card_ultimate", "SD19-X01"): (
        [
            ("安達洋介", None),
            (
                "SUNRISE D.I.D.",
                "最強銀河究極ゼロバトルスピリッツウエハース/〃～疾風の王者～/〃～宇宙の覇者～",
            ),
        ],
        [("石垣純哉", None)],
    ),
    ("card_ultimate", "SD67-CP01"): ([("安達洋介", None)], [("石垣純哉", None)]),
    ("card_flip", "BS52-TX01(A)"): ([("船弥さ吉", None)], []),
    ("card_flip", "BS52-TX01(B)"): ([("船弥さ吉", None)], []),
    ("card_flip", "BS73-TCP01(A)"): ([("船弥さ吉", None)], []),
    ("card_flip", "BS73-TCP01(B)"): ([("船弥さ吉", None)], []),
    ("card_spirit_xx_bs31", "BS31-XX02"): ([("森下直親", None)], []),
    ("card_spirit_bs01", "BS01-001"): ([("丸山浩", None)], []),
    ("card_spirit_bs01", "BSC22-001"): ([("丸山浩", None)], [("丸山浩", None)]),
    ("card_promo", "P001"): ([("藤井英俊", None)], []),
    ("card_promo", "EX001"): ([("藤井英俊", None)], []),
    ("card_promo", "P20-19"): ([("藤井英俊", None)], []),
}


@pytest.mark.parametrize(("key", "expected"), list(CREDITS.items()), ids=[k[1] for k in CREDITS])
def test_credits(
    key: tuple[str, str],
    expected: tuple[list[tuple[str, str | None]], list[tuple[str, str | None]]],
) -> None:
    text = text_of(*key)
    assert [(c.name, c.note) for c in text.illustrators] == expected[0]
    assert [(c.name, c.note) for c in text.concepts] == expected[1]


# (number of lines, first line, flavor_note); None when the card has no flavour
FLAVOR: dict[tuple[str, str], tuple[int, str, str | None] | None] = {
    ("card_spirit", "BS72-007"): (
        2,
        "ルーの下に集った武芸者たちは、各々自慢の武器を携えている。その武器",
        None,
    ),
    ("card_nexus", "BS72-069"): (
        2,
        "噴火すると、周囲に雷火を落とすオリン随一の山。その有様は、",
        None,
    ),
    ("card_magic", "BS72-075"): None,
    ("card_magic_flash", "BS01-117"): (
        1,
        "「ショーメン突破で、イセカイ界トオォォタル！」",
        "バトルスピリッツ メモリアルカードダスセット Hero Ver.",
    ),
    ("card_magic_flash", "BSC22-117"): None,
    ("card_nexus_soukaishin", "BS44-X07"): None,
    ("card_brave", "BS10-062"): (2, "星空の闇と静寂を切り裂く業火。正に炎のブレイヴ。", None),
    ("card_brave", "BS38-RV022"): None,
    ("card_ultimate", "SD19-X01"): (1, "金に輝くドラゴン！　あいつがアルティメットか！", None),
    ("card_ultimate", "SD67-CP01"): None,
    ("card_flip", "BS52-TX01(A)"): (1, "赤の世界は、竜が支配する炎渦巻く戦いの世界。", None),
    ("card_flip", "BS52-TX01(B)"): (1, "赤の世界が生み出した、竜の中の竜の神。", None),
    ("card_flip", "BS73-TCP01(A)"): (1, "赤の世界。強きものだけが生き残る弱肉強食の世界。", None),
    ("card_flip", "BS73-TCP01(B)"): (1, "竜の神は、赤の世界に君臨する。", None),
    ("card_spirit_xx_bs31", "BS31-XX02"): (1, "運命というものは時に残酷に道を閉ざす。", None),
    ("card_spirit_bs01", "BS01-001"): (3, "いけすかない竜人たち。乱暴極まる恐竜たち。", None),
    ("card_spirit_bs01", "BSC22-001"): (3, "いけすかない竜人たち。乱暴極まる恐竜たち。", None),
    ("card_promo", "P001"): (3, "望むのはすべての破壊……。", None),
    ("card_promo", "EX001"): (3, "望むのはすべての破壊……。", None),
    ("card_promo", "P20-19"): (
        2,
        "時空の彼方より飛来した2体の未確認生態。それは、時空の大神の宣戦",
        None,
    ),
}


@pytest.mark.parametrize(("key", "expected"), list(FLAVOR.items()), ids=[k[1] for k in FLAVOR])
def test_flavor(key: tuple[str, str], expected: tuple[int, str, str | None] | None) -> None:
    text = text_of(*key)
    if expected is None:
        assert (text.flavor, text.flavor_note) == (None, None)
        return
    assert text.flavor is not None
    lines = text.flavor.split("\n")
    assert (len(lines), lines[0], text.flavor_note) == expected
    assert text.flavor == text.flavor.strip("\n")


def test_flavor_keeps_source_breaks() -> None:
    flavor = text_of("card_brave", "BS10-062").flavor
    assert flavor is not None
    assert flavor.endswith("\n―星文学者リリア『八十八星夜話』鳳凰座―")


@pytest.mark.parametrize("stem", STEMS)
def test_no_warning_on_fixtures(stem: str, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        parse(stem)
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
