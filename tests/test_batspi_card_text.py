"""Effect, keyword and side-condition parsing of card text lines (#71)."""

import logging

import pytest

from bs_database.parsers.batspi.card_text import (
    parse_body,
    parse_card_text,
    parse_trailer,
    split_note,
    split_trailer,
)
from bs_database.parsers.card_models import Keyword
from bs_database.parsers.errors import ParseError

LOGGER = "bs_database.parsers.batspi.card_text"

# (header line, levels, label, keywords, timing)
HEADERS = [
    (
        "Lv1・Lv2『自分のアタックステップ開始時』",
        (1, 2),
        None,
        (),
        "『自分のアタックステップ開始時』",
    ),
    ("Lv1･Lv2『x』", (1, 2), None, (), "『x』"),
    ("Lv2", (2,), None, (), None),
    ("Lv1・Lv2・Lv3", (1, 2, 3), None, (), None),
    ("Lv1【根幻回帰】", (1,), None, (Keyword("【", "根幻回帰", None),), None),
    (
        "Lv1《転醒：自分のカウント5以下》",
        (1,),
        None,
        (Keyword("《", "転醒", "自分のカウント5以下"),),
        None,
    ),
    (
        "Lv1・Lv2【超装甲：赤/紫/緑/白/黄/青】",
        (1, 2),
        None,
        (Keyword("【", "超装甲", "赤/紫/緑/白/黄/青"),),
        None,
    ),
    (
        "【合体時】【激突】『このスピリットのアタック時』",
        (),
        None,
        (Keyword("【", "合体時", None), Keyword("【", "激突", None)),
        "『このスピリットのアタック時』",
    ),
    ("【セット中】『x』", (), None, (Keyword("【", "セット中", None),), "『x』"),
    (
        "【神技：2】Lv1・Lv2：フラッシュ『お互いのアタックステップ』",
        (1, 2),
        "フラッシュ",
        (Keyword("【", "神技", "2"),),
        "『お互いのアタックステップ』",
    ),
    ("【神域】Lv2『x』", (2,), None, (Keyword("【", "神域", None),), "『x』"),
    (
        "【Uトリガー】Lv3・Lv4・Lv5『x』",
        (3, 4, 5),
        None,
        (Keyword("【", "Uトリガー", None),),
        "『x』",
    ),
    (
        "Lv4・Lv5：フラッシュ【真・覚醒】『x』",
        (4, 5),
        "フラッシュ",
        (Keyword("【", "真・覚醒", None),),
        "『x』",
    ),
    (
        "フラッシュ《契約煌臨：極契約＆C3以上》『自分のターン』",
        (),
        "フラッシュ",
        (Keyword("《", "契約煌臨", "極契約＆C3以上"),),
        "『自分のターン』",
    ),
    ("【OC中】Lv3・Lv4『x』", (3, 4), None, (Keyword("【", "OC中", None),), "『x』"),
    ("メイン：", (), "メイン", (), None),
    ("フラッシュ：", (), "フラッシュ", (), None),
    # #108: a blank after the levels, an ascii colon, the timing before the parameter or keyword
    (
        "Lv1・Lv2・Lv3 【粉砕】『このスピリットのアタック時』",
        (1, 2, 3),
        None,
        (Keyword("【", "粉砕", None),),
        "『このスピリットのアタック時』",
    ),
    ("Lv1・Lv2 『x』", (1, 2), None, (), "『x』"),
    (
        "Lv1・Lv2・Lv3:フラッシュ【覚醒】",
        (1, 2, 3),
        "フラッシュ",
        (Keyword("【", "覚醒", None),),
        None,
    ),
    ("Lv2『x』〔ターン1回〕", (2,), None, (), "『x』"),
    ("Lv2『x』【起動：フラッシュ】", (2,), None, (Keyword("【", "起動", "フラッシュ"),), "『x』"),
    (
        "『x』【起動：フラッシュ】〔ターン1回〕",
        (),
        None,
        (Keyword("【", "起動", "フラッシュ"),),
        "『x』",
    ),
]


@pytest.mark.parametrize(("header", "levels", "label", "keywords", "timing"), HEADERS)
def test_header_shapes(
    header: str,
    levels: tuple[int, ...],
    label: str | None,
    keywords: tuple[Keyword, ...],
    timing: str | None,
) -> None:
    effects, *_ = parse_body([header, "本文"], levels=range(1, 7))
    assert len(effects) == 1
    effect = effects[0]
    assert (effect.form, effect.header, effect.text) == ("header", header, "本文")
    assert (effect.levels, effect.label, effect.keywords, effect.timing) == (
        levels,
        label,
        keywords,
        timing,
    )
    assert effect.position == 1


def test_keyword_lines() -> None:
    lines = ["《神託》〔星竜/界渡/化神＆コスト3以上〕", "◆一つ目", "◆二つ目", "Lv1・Lv2"]
    effects, *_ = parse_body(lines, levels=(1, 2))
    assert [(e.position, e.form) for e in effects] == [
        (1, "keyword_line"),
        (2, "plain"),
        (3, "header"),
    ]
    assert effects[0].keywords == (Keyword("《", "神託", None),)
    assert effects[0].text == effects[0].header == lines[0]
    assert effects[1].text == "◆一つ目\n◆二つ目"
    assert effects[1].header is None
    assert effects[2].text == ""


def test_mirage_keeps_parameter_as_printed() -> None:
    line = "【ミラージュ：コスト2(1)(このカードは手札からセットできる)】"
    effects, *_ = parse_body([line])
    assert effects[0].form == "keyword_line"
    assert effects[0].keywords == (
        Keyword("【", "ミラージュ", "コスト2(1)(このカードは手札からセットできる)"),
    )


def test_main_and_flash_together() -> None:
    effects, *_ = parse_body(["メイン：", "A", "フラッシュ：", "B", "C"])
    assert [(e.label, e.text) for e in effects] == [("メイン", "A"), ("フラッシュ", "B\nC")]


def test_plain_before_headers_and_trailing_space() -> None:
    effects, *_ = parse_body(["自分の白以外のスピリットがいる間。 ", "", "Lv1・Lv2", "x"], (1, 2))
    assert (effects[0].form, effects[0].text) == ("plain", "自分の白以外のスピリットがいる間。")
    assert effects[1].position == 2


def test_side_lines_end_blocks_and_are_not_effects() -> None:
    lines = [
        "右合体条件：コスト5以上",
        "左合体条件：コスト3以上",
        "【召喚条件：自分の赤スピリット1体以上】",
        "OC条件：カウント5以上",
        "Lv1",
        "効果",
        "合体条件：コスト3以上",
        "続き",
    ]
    effects, fusion, summon, overclock = parse_body(lines, (1,))
    assert fusion == ("右合体条件：コスト5以上", "左合体条件：コスト3以上", "合体条件：コスト3以上")
    assert summon == "【召喚条件：自分の赤スピリット1体以上】"
    assert overclock == "OC条件：カウント5以上"
    assert [(e.form, e.text) for e in effects] == [("header", "効果"), ("plain", "続き")]


def test_level_prose_stays_text() -> None:
    effects, *_ = parse_body(["Lv1", "Lv2以上のとき、ドローする。"], (1, 2))
    assert effects[0].text == "Lv2以上のとき、ドローする。"


def test_empty_and_vanilla() -> None:
    assert parse_body([]) == ((), (), None, None)
    assert parse_body(["", " "]) == ((), (), None, None)


@pytest.mark.parametrize("line", ["Lv1：効果です", "Lv1・Lv2 x", "Lv2『x』続き"])
def test_malformed_header_is_an_error(line: str) -> None:
    with pytest.raises(ParseError, match="malformed effect header"):
        parse_body([line], (1, 2), "BS00-001")


def test_unknown_level_scope_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        effects, *_ = parse_body(["Lv3"], (1, 2), "BS00-001 https://x/")
    assert effects[0].levels == (3,)
    assert "BS00-001" in caplog.text
    assert "field=levels" in caplog.text
    assert "scope=(3,)" in caplog.text


def test_known_level_scope_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        parse_body(["Lv1・Lv2", "x"], (1, 2))
    assert caplog.records == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ikuyoan(プロモ)", ("ikuyoan", "プロモ")),
        ("SUNRISE D.I.D.(a/〃～b～)", ("SUNRISE D.I.D.", "a/〃～b～")),
        ("名前（全角）", ("名前", "全角")),
        ("名前(a(b)c)", ("名前", "a(b)c")),
        ("(only)", ("", "only")),
        ("plain", ("plain", None)),
        ("", ("", None)),
        ("名前)", ("名前)", None)),
        (" 名前 ", ("名前", None)),
    ],
)
def test_split_note(text: str, expected: tuple[str, str | None]) -> None:
    assert split_note(text) == expected


def test_split_trailer() -> None:
    lines = ["効果", "シンボル：なし", "イラスト：x"]
    assert split_trailer(lines) == (["効果"], ["シンボル：なし", "イラスト：x"])
    assert split_trailer(["効果"]) == (["効果"], ())


def test_trailer_credits_and_flavor() -> None:
    lines = [
        "シンボル：赤",
        "コンセプト：石垣純哉",
        "イラスト：a",
        "イラスト：b(note)",
        "フレーバーテキスト：(メモ)",
        "一行目 ",
        "二行目",
        "",
    ]
    illustrators, concepts, flavor, note, others = parse_trailer(lines)
    assert [(c.name, c.note) for c in illustrators] == [("a", None), ("b", "note")]
    assert [c.name for c in concepts] == ["石垣純哉"]
    assert (flavor, note, others) == ("一行目\n二行目", "メモ", ())


def test_trailer_flavor_note_without_parentheses_and_empty() -> None:
    assert parse_trailer(["フレーバーテキスト：そのまま", "x"])[2:4] == ("x", "そのまま")
    assert parse_trailer(["フレーバーテキスト：", ""])[2:4] == (None, None)
    assert parse_trailer([])[2:4] == (None, None)


def test_trailer_other_credits_and_ascii_colons() -> None:
    lines = [
        "イラスト:SUNRIZE",
        "コンセプト:やまだたかひろ",
        "プロデュース：杉田智和",
        "ペイント：a(b)",
        "書：c",
        "写真：d",
        "コラボレート：アイドルマスター",
    ]
    illustrators, concepts, _, _, others = parse_trailer(lines)
    assert [c.name for c in illustrators] == ["SUNRIZE"]
    assert [c.name for c in concepts] == ["やまだたかひろ"]
    assert [(c.role, c.name, c.note) for c in others] == [
        ("プロデュース", "杉田智和", None),
        ("ペイント", "a", "b"),
        ("書", "c", None),
        ("写真", "d", None),
        ("コラボレート", "アイドルマスター", None),
    ]


def test_trailer_empty_illustrator_is_ignored_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    result = parse_trailer(["イラスト：", "イラスト：x"], "BS00-001")
    assert [c.name for c in result[0]] == ["x"]
    assert "empty illustrator ignored" in caplog.text


def test_split_trailer_at_other_credits() -> None:
    assert split_trailer(["効果", "書：x"]) == (["効果"], ["書：x"])


def test_trailer_errors() -> None:
    with pytest.raises(ParseError, match="unexpected trailer line"):
        parse_trailer(["イラスト：a", "謎の行"], "BS00-001")
    with pytest.raises(ParseError, match="empty illustrator"):
        parse_trailer(["イラスト：(only)"], "BS00-001")
    with pytest.raises(ParseError, match="empty concept"):
        parse_trailer(["コンセプト："], "BS00-001")


def test_parse_card_text() -> None:
    lines = ["Lv1", "効果", "シンボル：赤", "イラスト：a", "フレーバーテキスト：", "f"]
    text = parse_card_text(lines, (1,), "BS00-001")
    assert [e.text for e in text.effects] == ["効果"]
    assert text.flavor == "f"
    assert text.illustrators[0].name == "a"
