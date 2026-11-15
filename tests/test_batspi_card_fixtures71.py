"""Text, credits, flavour (and later printings, images) of the 11 card fixtures (#71)."""

import dataclasses
import json
import logging
from pathlib import Path

import pytest

from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.card_models import (
    CardEntry,
    CardImage,
    CardPage,
    CardText,
    Printing,
)

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


# (rows from 収録, rows only in the block-icon section) per card number
PRINTING_COUNTS: dict[tuple[str, str], tuple[int, int]] = {
    ("card_spirit", "BS72-007"): (1, 0),
    ("card_nexus", "BS72-069"): (2, 0),
    ("card_magic", "BS72-075"): (1, 1),
    ("card_magic_flash", "BS01-117"): (11, 0),
    ("card_magic_flash", "BSC22-117"): (5, 0),
    ("card_nexus_soukaishin", "BS44-X07"): (5, 0),
    ("card_brave", "BS10-062"): (9, 0),
    ("card_brave", "BS38-RV022"): (4, 0),
    ("card_ultimate", "SD19-X01"): (12, 0),
    ("card_ultimate", "SD67-CP01"): (1, 1),
    ("card_flip", "BS52-TX01(A)"): (3, 0),
    ("card_flip", "BS52-TX01(B)"): (3, 0),
    ("card_flip", "BS73-TCP01(A)"): (1, 1),
    ("card_flip", "BS73-TCP01(B)"): (1, 1),
    ("card_spirit_xx_bs31", "BS31-XX02"): (3, 0),
    ("card_spirit_bs01", "BS01-001"): (3, 0),
    ("card_spirit_bs01", "BSC22-001"): (1, 0),
    ("card_promo", "P001"): (2, 0),
    ("card_promo", "EX001"): (1, 1),
    ("card_promo", "P20-19"): (3, 0),
}


@pytest.mark.parametrize(
    ("key", "expected"), list(PRINTING_COUNTS.items()), ids=[k[1] for k in PRINTING_COUNTS]
)
def test_printing_counts(key: tuple[str, str], expected: tuple[int, int]) -> None:
    stem, number = key
    mine = [p for p in parse(stem).printings if p.number == number]
    assert (
        sum(p.section == "収録" for p in mine),
        sum(p.section == "ブロックアイコン" for p in mine),
    ) == expected


def printings_of(stem: str, number: str) -> list[Printing]:
    return [p for p in parse(stem).printings if p.number == number]


@pytest.mark.parametrize("stem", STEMS)
def test_printing_numbers_are_entry_numbers(stem: str) -> None:
    page = parse(stem)
    numbers = {e.number for e in page.entries}
    assert {p.number for p in page.printings} <= numbers


def test_spirit_printing_values() -> None:
    (printing,) = printings_of("card_spirit", "BS72-007")
    assert printing == Printing(
        "BS72-007",
        "契約編：環 第1章：廻帰再醒",
        printing.product_href,
        "R",
        None,
        "SECRETあり",
        "BS72",
        "12",
        "2025-05-17",
        "収録",
    )
    assert printing.product_href is not None
    assert printing.product_href.startswith("https://batspi.com/index.php?%E5%A5%91")


def test_nexus_second_printing_and_note() -> None:
    first, second = printings_of("card_nexus", "BS72-069")
    assert (first.rarity, first.product_code, first.release_date) == ("C", "BS72", "2025-05-17")
    assert (second.rarity, second.note_ja, second.product_code, second.release_date) == (
        "C",
        "フルアート版",
        "BS74",
        "2025-11-22",
    )


def test_block_only_rows() -> None:
    extra = printings_of("card_magic", "BS72-075")[-1]
    assert (extra.product_name_ja, extra.rarity, extra.section) == (
        "バトルスキーイベント提供記念品",
        None,
        "ブロックアイコン",
    )
    promo = printings_of("card_ultimate", "SD67-CP01")[-1]
    assert (promo.product_name_ja, promo.block_icon, promo.rarity) == (
        "プロモーションカード",
        "10",
        None,
    )


def test_ultimate_detail_and_unlinked_rows() -> None:
    rows = printings_of("card_ultimate", "SD19-X01")
    max2013 = next(p for p in rows if p.product_name_ja == "バトスピMAX2013")
    assert (max2013.detail_ja, max2013.rarity, max2013.note_ja) == (
        "入場者特典",
        "X",
        "【灼熱のゼロ】発売日箔押し入り・先行配布",
    )
    club = next(p for p in rows if p.product_name_ja == "バトスピ部")
    assert (club.detail_ja, club.rarity, club.note_ja) == (
        "アルティメットトリガーキャンペーン",
        "X",
        "左向きゴールド仕様",
    )
    unlinked = next(
        p for p in rows if p.product_name_ja == "バトスピ部 アルティメットトリガーチャレンジ"
    )
    assert (unlinked.product_href, unlinked.rarity, unlinked.note_ja) == (
        None,
        None,
        "金色仕様・2013/11/28頃発送",
    )
    assert all(p.product_href is None or p.product_href.startswith("https://") for p in rows)


def test_second_distribution_does_not_inherit_the_first_date() -> None:
    rows = [
        p
        for p in printings_of("card_nexus_soukaishin", "BS44-X07")
        if p.product_name_ja == "メガデッキ【太陽神の顕現】"
    ]
    assert [(p.rarity, p.product_code, p.release_date) for p in rows] == [
        ("X", "SD68", "2024-03-30"),
        (None, None, None),
    ]
    assert rows[1].note_ja == "SECRETデザイン"


def test_flip_faces_get_one_row_each() -> None:
    a = printings_of("card_flip", "BS52-TX01(A)")
    b = printings_of("card_flip", "BS52-TX01(B)")
    assert [p.product_name_ja for p in a] == [p.product_name_ja for p in b]
    assert (a[0].rarity, a[0].product_code, a[0].block_icon, a[0].release_date) == (
        "転醒X",
        "BS52",
        "7",
        "2020-04-25",
    )
    assert a[1].note_ja == "パラレルあり"


def test_promo_labels_resolve_per_number() -> None:
    p001 = printings_of("card_promo", "P001")
    assert (p001[0].rarity, p001[0].block_icon, p001[0].release_date) == ("P", "7", None)
    assert p001[1].product_name_ja == "「バトルスピリッツ専用バインダー」付属"
    assert p001[1].product_href is None
    (ex001,) = [p for p in printings_of("card_promo", "EX001") if p.section == "収録"]
    assert (ex001.rarity, ex001.product_code, ex001.release_date) == ("EX", "BSC01", "2010-03-18")
    p2019 = printings_of("card_promo", "P20-19")
    assert [p.detail_ja for p in p2019] == [None, "2021年4月参加記念品", "2021年8月参加記念品"]


def test_magic_flash_unmatched_rarity_and_dates() -> None:
    rows = printings_of("card_magic_flash", "BS01-117")
    assert (rows[0].product_name_ja, rows[0].rarity) == ("ケロケロスターター", "C")
    assert all(p.rarity == "C" for p in rows)
    first = next(p for p in rows if p.product_name_ja == "第一弾")
    assert (first.product_code, first.release_date) == ("BS01", "2008-09-13")
    revival = printings_of("card_magic_flash", "BSC22-117")
    assert any(p.product_code == "BSC22" and p.block_icon == "2" for p in revival)
    assert [p.rarity for p in revival if p.rarity is None] == [None]


IMAGE_COUNTS = {
    ("card_spirit", "BS72-007"): 2,
    ("card_nexus", "BS72-069"): 2,
    ("card_magic", "BS72-075"): 1,
    ("card_magic_flash", "BS01-117"): 7,
    ("card_magic_flash", "BSC22-117"): 2,
    ("card_nexus_soukaishin", "BS44-X07"): 3,
    ("card_brave", "BS10-062"): 8,
    ("card_brave", "BS38-RV022"): 5,
    ("card_ultimate", "SD19-X01"): 9,
    ("card_ultimate", "SD67-CP01"): 1,
    ("card_flip", "BS52-TX01(A)"): 3,
    ("card_flip", "BS52-TX01(B)"): 3,
    ("card_flip", "BS73-TCP01(A)"): 2,
    ("card_flip", "BS73-TCP01(B)"): 2,
    ("card_spirit_xx_bs31", "BS31-XX02"): 2,
    ("card_spirit_bs01", "BS01-001"): 3,
    ("card_spirit_bs01", "BSC22-001"): 1,
    ("card_promo", "P001"): 1,
    ("card_promo", "EX001"): 1,
    ("card_promo", "P20-19"): 1,
}


@pytest.mark.parametrize(
    ("key", "expected"), list(IMAGE_COUNTS.items()), ids=[k[1] for k in IMAGE_COUNTS]
)
def test_image_counts(key: tuple[str, str], expected: int) -> None:
    stem, number = key
    assert sum(i.number == number for i in parse(stem).images) == expected


def test_spirit_images() -> None:
    first, second = parse("card_spirit").images
    assert first == CardImage(
        "BS72-007",
        "https://batspi.com/card/BS7/BS72-007.jpg",
        "https://batspi.com/card/BS7/small/BS72-007.jpg",
        ("契約編：環 第1章：廻帰再醒",),
    )
    assert second.large_url == "https://batspi.com/card/BS7/BS72-007-2.jpg"
    assert second.caption == ("契約編：環 第1章：廻帰再醒", "シークレット")


def test_promo_caption_keeps_second_line() -> None:
    (image,) = [i for i in parse("card_promo").images if i.number == "EX001"]
    assert image.caption == ("Xレアパック 【龍皇ジークフリード】", "プロモーションカード")


@pytest.mark.parametrize("stem", STEMS)
def test_image_urls_are_read_not_built(stem: str) -> None:
    page = parse(stem)
    html = (HTML_DIR / f"{stem}.html").read_text(encoding="utf-8")
    numbers = {e.number for e in page.entries}
    assert page.images
    for image in page.images:
        assert image.number in numbers
        assert image.large_url.startswith("https://batspi.com/")
        assert f'href="{image.large_url.removeprefix("https://batspi.com")}"' in html
        assert image.small_url is not None
        assert f'src="{image.small_url.removeprefix("https://batspi.com")}"' in html


@pytest.mark.parametrize("stem", STEMS)
def test_page_round_trips_through_json(stem: str) -> None:
    page = parse(stem)
    data = json.loads(json.dumps(dataclasses.asdict(page), ensure_ascii=False))
    assert data["schema_version"] == "1.1.0"
    assert len(data["printings"]) == len(page.printings)
