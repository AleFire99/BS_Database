import json
from pathlib import Path
from typing import Any

import pytest

from bs_database.parsers.fandom import (
    FandomName,
    FandomRarity,
    jp_key,
    parse_name,
    parse_rarities,
)

FIXTURES = Path(__file__).parent / "fixtures" / "fandom"


def pages(name: str) -> dict[str, str]:
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text("utf-8"))
    return {
        p["title"]: p["revisions"][0]["slots"]["main"]["*"] for p in data["query"]["pages"].values()
    }


FAMILIES = pages("families")
KEYWORDS = pages("keywords")


def name(group: dict[str, str], title: str) -> FandomName | None:
    return parse_name(title, group[title])


@pytest.mark.parametrize(
    ("group", "title", "jp", "en", "romaji"),
    [
        (FAMILIES, "Machine Beast", "機獣", "Machine Beast", "kijuu"),  # italic JP; romaji
        (FAMILIES, "Abyssen", "深淵", "Abyssen", "shin-en"),  # full-width semicolon
        (FAMILIES, "A-LAWS", "アロウズ", "A-LAWS", None),  # no romaji
        (FAMILIES, "Baby", "幼年期", "Baby", "Yōnenki"),
        (FAMILIES, "Armor (Family)", "アーマー体", "Armor", "Āmā-tai"),  # disambiguator
        (KEYWORDS, "Accel", "アクセル", "Accel", "Akuseru"),  # comma
        (KEYWORDS, "Brave Engage", "合体結誓", "Brave Engage", "bureivu engēji"),  # ruby
        (KEYWORDS, "Bunshin", "分身", "Bunshin", None),  # space inside the bold
        (KEYWORDS, "Armor (Keyword)", "装甲", "Armor", "Soukou"),
        (KEYWORDS, "A.T. Field", "A.T.フィールド", "A.T. Field", None),
    ],
)
def test_parse_name_variants(
    group: dict[str, str], title: str, jp: str, en: str, romaji: str | None
) -> None:
    assert name(group, title) == FandomName(jp=jp, en=en, romaji=romaji, title=title)


@pytest.mark.parametrize(
    ("text", "jp", "en", "romaji"),
    [
        # bold JP inside the parentheses (Mirror Monster)
        (
            "'''Mirror Monster''' ('''ミラーモンスター'''; mila-monsutar) is a family",
            "ミラーモンスター",
            "Mirror Monster",
            "mila-monsutar",
        ),
        # "short for": the bold right before the parentheses is the name (NZ)
        (
            "'''NZ''', short for '''Neo Zeon''' (ネオ・ジオン), is a family",
            "ネオ・ジオン",
            "Neo Zeon",
            None,
        ),
        # italic opening glued to the closing bold (Creation Deity)
        (
            "'''Creation Deity '''''(創造神; sousoushin)'' is a family",
            "創造神",
            "Creation Deity",
            "sousoushin",
        ),
    ],
)
def test_parse_name_strips_wiki_markup(text: str, jp: str, en: str, romaji: str | None) -> None:
    assert parse_name("T", text) == FandomName(jp=jp, en=en, romaji=romaji, title="T")


def test_page_without_a_parenthesised_name_is_unmatched() -> None:
    assert name(KEYWORDS, "AFO") is None


@pytest.mark.parametrize("text", ["", "no bold here (ジェム)", "'''Foo''' (only latin; text)"])
def test_parse_name_rejects_junk(text: str) -> None:
    assert parse_name("Foo", text) is None


def test_jp_key_nfkc_and_whitespace() -> None:
    assert jp_key("衣装 ") == jp_key("衣装")
    assert jp_key("Ａ　Ｂ") == "AB"
    assert jp_key("ｱｸｾﾙ") == jp_key("アクセル")
    assert jp_key("機 獣") == "機獣"


def test_parse_rarities() -> None:
    text = next(iter(pages("rarity").values()))
    rarities = parse_rarities(text)
    by_en = {r.en: r for r in rarities}
    assert by_en["Common"] == FandomRarity(jp="コモン", en="Common", letter="C")
    assert by_en["Master Rare"] == FandomRarity("マスターレア", "Master Rare", "M")
    assert by_en["X-Rare"] == FandomRarity("Xレア", "X-Rare", "X")
    assert by_en["Rebirth Rare"].letter == "転醒R"
    assert by_en["Rebirth X-Rare"].jp == "転醒Xレア"  # level 3 heading
    assert by_en["Promotional Cards"].letter is None
    assert "Secret Rare" not in by_en  # no JP paren: skipped
    assert "Mythic X-Rare" not in by_en


def test_non_breaking_spaces_are_whitespace() -> None:
    parsed = parse_name("Armor (Keyword)", "'''Armor'''\xa0(装甲;\xa0''Soukou'') is")
    assert parsed is not None
    assert (parsed.jp, parsed.romaji) == ("装甲", "Soukou")


SHAPES = pages("shapes")


@pytest.mark.parametrize(
    ("title", "jp", "en", "romaji"),
    [
        ("Amahara", "アマハラ", "Amahara", None),  # template, no romaji
        ("Avatar", "化神", "Avatar", "Keshin"),  # template
        ("Birthgem Deity", "誕晶神", "Birthgem Deity", "Tanjōshin"),  # template, bold-italic
        ("Clown Deity", "道化神", "Clown Deity", "Dōke-shin"),
        ("Egyt", "エジット", "Egyt", "Ejitto"),
        ("Olym", "オリン", "Olym", "Orin"),
        ("Superstar", "超星", "Superstar", "Chōsei"),
        ("Tri-Heaven Deity", "三天神", "Tri-Heaven Deity", "Santenjin"),  # template after a file
        ("Soul Drive", "ソウルドライブ", "Soul Drive", "Sōru Doraibu"),
        (
            "Light-Dark Soul Drive",
            "ソウルドライブ・光闇",
            "Light-Dark Soul Drive",
            "Sōru Doraibu Kōan",
        ),
        ("Extreme", "極限", "Extreme", "Kyokugen"),  # italic parentheses, trailing space
        ("Master", "マスター", "Master", "masutaa"),
        ("Firing Squad", "游擊隊", "Firing Squad", "yuugekitai"),
        ("Jade Emperor Dragon", "玉帝龍", "Jade Emperor Dragon", "gyokuteiryuu"),
        ("Sengoku God", "戦国神", "Sengoku God", "sengokushin"),
        ("DNA Digivolution", "ジョグレス進化", "DNA Digivolution", "Joguresu Shinka"),
        ("Heavenly Demon King", "天魔王", "Heavenly Demon King", "Tenmaou"),  # full-width
        ("Card Slash", "カードスラッシュ", "Card Slash", "Kādosurasshu"),
    ],
)
def test_parse_name_template_italic_and_fullwidth(
    title: str, jp: str, en: str, romaji: str | None
) -> None:
    assert name(SHAPES, title) == FandomName(jp=jp, en=en, romaji=romaji, title=title)


@pytest.mark.parametrize("title", ["MS", "Family"])
def test_parse_name_shapes_without_japanese_stay_unmatched(title: str) -> None:
    assert name(SHAPES, title) is None
