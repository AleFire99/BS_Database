"""parse_card_page against the card fixtures and mutated pages."""

import json
import logging
from pathlib import Path

import pytest

from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.card_models import (
    SCHEMA_VERSION,
    CardPage,
    Gameplay,
    Level,
    Overclock,
    Reduction,
    SymbolCount,
)
from bs_database.parsers.errors import ParseError

HTML_DIR = Path(__file__).parent / "fixtures" / "html"
MANIFEST = json.loads((HTML_DIR / "fixtures.json").read_text(encoding="utf-8"))
LOGGER = "bs_database.parsers.batspi.card"


def load(name: str) -> str:
    return (HTML_DIR / name).read_text(encoding="utf-8")


def parse(stem: str) -> CardPage:
    name = f"{stem}.html"
    return parse_card_page(load(name), MANIFEST[name]["url"])


def identity(page: CardPage) -> list[tuple[str, str, str | None]]:
    return [(e.number, e.name_ja, e.name_en) for e in page.entries]


IDENTITIES = [
    ("card_spirit", [("BS72-007", "光爪の武芸者ヘルハウンド", None)]),
    ("card_nexus", [("BS72-069", "ゼウスの雷火山", None)]),
    ("card_nexus_soukaishin", [("BS44-X07", "創界神アポローン", None)]),
    ("card_magic", [("BS72-075", "ジャベリンドロー", None)]),
    (
        "card_magic_flash",
        [
            ("BS01-117", "ダブルドロー", "Double Draw"),
            ("BSC22-117", "ダブルドロー", "Double Draw"),
        ],
    ),
    (
        "card_brave",
        [
            ("BS10-062", "砲凰竜フェニック・キャノン", "The GunDragon Phoenix-Cannon"),
            ("BS38-RV022", "砲凰竜フェニック・キャノン", "The GunDragon Phoenix-Cannon"),
        ],
    ),
    (
        "card_ultimate",
        [
            ("SD19-X01", "アルティメット・ジークフリード", None),
            ("SD67-CP01", "アルティメット・ジークフリード", None),
        ],
    ),
    (
        "card_flip",
        [
            ("BS52-TX01(A)", "赤の世界", None),
            ("BS52-TX01(B)", "赤き神龍皇", None),
            ("BS73-TCP01(A)", "赤の世界", None),
            ("BS73-TCP01(B)", "赤き神龍皇", None),
        ],
    ),
    ("card_spirit_xx_bs31", [("BS31-XX02", "六絶神 鉄壁のクロム・リゼルファー", None)]),
    (
        "card_spirit_bs01",
        [("BS01-001", "ゴラドン", "Goradon"), ("BSC22-001", "ゴラドン", "Goradon")],
    ),
    (
        "card_promo",
        [
            ("P001", "焔竜翼人マ・ドー", "The FlameWingDragon Ma-Dwo"),
            ("EX001", "焔竜翼人マ・ドー", "The FlameWingDragon Ma-Dwo"),
            ("P20-19", "焔竜翼人マ・ドー", "The FlameWingDragon Ma-Dwo"),
        ],
    ),
]


@pytest.mark.parametrize(("stem", "expected"), IDENTITIES)
def test_identity(
    stem: str, expected: list[tuple[str, str, str | None]], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        page = parse(stem)
    assert identity(page) == expected
    assert page.schema_version == SCHEMA_VERSION
    assert page.url == MANIFEST[f"{stem}.html"]["url"]
    assert not caplog.records


def test_flip_ignores_revival_block() -> None:
    assert len(parse("card_flip").entries) == 4


def test_magic_flash_ignores_trial_spec_block() -> None:
    assert [e.gameplay.families for e in parse("card_magic_flash").entries] == [(), ()]


def test_brave_skips_erratum_blocks() -> None:
    assert len(parse("card_brave").entries) == 2


def test_conflicting_h3_number_warns(caplog: pytest.LogCaptureFixture) -> None:
    html = load("card_brave.html").replace("&lt;BS10-062&gt;", "&lt;BS10-999&gt;")
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        page = parse_card_page(html, "u")
    assert page.entries[0].number == "BS10-999"
    warnings = [r.getMessage() for r in caplog.records]
    assert len(warnings) == 1
    assert "BS10-999" in warnings[0] and "number" in warnings[0] and "BS10-062" in warnings[0]


def test_title_name_conflict_warns(caplog: pytest.LogCaptureFixture) -> None:
    html = load("card_spirit.html").replace("<title>光爪の武芸者ヘルハウンド", "<title>別の名前")
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        parse_card_page(html, "u")
    messages = [r.getMessage() for r in caplog.records]
    assert len(messages) == 1
    assert "name_ja" in messages[0]
    assert "光爪の武芸者ヘルハウンド" in messages[0] and "別の名前" in messages[0]


def test_blank_heading_name_falls_back_to_title() -> None:
    html = (
        "<html><head><title>題名 - バトルスピリッツ wiki</title></head><body>"
        "<span class='cardno'>BS01-001</span>"
        "<h3><a class='anchor_super'>†</a></h3>"
        "<pre>マジック\n4(2)/赤\nシンボル：なし</pre></body></html>"
    )
    entry = parse_card_page(html, "u").entries[0]
    assert (entry.number, entry.name_ja) == ("BS01-001", "題名")


def test_page_without_card_block_raises() -> None:
    with pytest.raises(ParseError, match="no card <pre> found"):
        parse_card_page("<html><body><p>x</p></body></html>", "u")


def test_page_with_only_qa_blocks_raises() -> None:
    html = "<html><body><h3>t<a class='anchor_super'>†</a></h3><pre>Q. x\nA. y</pre></body></html>"
    with pytest.raises(ParseError, match="no card <pre> found"):
        parse_card_page(html, "u")


def test_headingless_page_with_number_mismatch_raises() -> None:
    block = "<pre>マジック\n4(2)/赤\nシンボル：なし</pre>"
    html = f"<html><body><span class='cardno'>BS01-001</span>{block}{block}</body></html>"
    with pytest.raises(ParseError, match="card numbers"):
        parse_card_page(html, "u")


def diff_fields(stem: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for d in parse(stem).differences:
        result.setdefault(d.name_ja, []).append(d.field)
    return result


def test_goradon_levels_differ(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER):
        page = parse("card_spirit_bs01")
    assert len(page.differences) == 1
    diff = page.differences[0]
    assert (diff.name_ja, diff.field) == ("ゴラドン", "levels")
    assert [number for number, _ in diff.values] == ["BS01-001", "BSC22-001"]
    assert any("per-number values differ" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("stem", ["card_spirit", "card_nexus", "card_magic"])
def test_no_differences(stem: str) -> None:
    assert parse(stem).differences == ()


def test_flip_compares_same_name_faces_only() -> None:
    assert diff_fields("card_flip") == {
        "赤の世界": ["families", "effects", "flavor"],
        "赤き神龍皇": ["families", "levels", "effects", "flavor"],
    }


def test_other_differences() -> None:
    assert diff_fields("card_brave") == {
        "砲凰竜フェニック・キャノン": [
            "symbols",
            "families",
            "levels",
            "effects",
            "fusion_conditions",
            "flavor",
        ]
    }
    assert diff_fields("card_ultimate") == {
        "アルティメット・ジークフリード": [
            "reduction",
            "families",
            "levels",
            "overclock",
            "effects",
            "summon_condition",
            "overclock_condition",
            "flavor",
        ]
    }
    assert diff_fields("card_promo") == {"焔竜翼人マ・ドー": ["families", "effects", "flavor"]}
    assert diff_fields("card_magic_flash") == {"ダブルドロー": ["effects", "flavor"]}


def sc(symbol: str, count: int = 1) -> SymbolCount:
    return SymbolCount(symbol, count)


def gp(
    card_type: str,
    cost: int,
    reduction: Reduction,
    families: tuple[str, ...],
    levels: tuple[Level, ...],
    *,
    colors: tuple[str, ...] = ("赤",),
    symbols: tuple[SymbolCount, ...] = (),
    deck_limit: int | None = None,
    fusion: int | None = None,
    overclock: Overclock | None = None,
) -> Gameplay:
    return Gameplay(
        card_type=card_type,
        deck_limit=deck_limit,
        cost=cost,
        reduction=reduction,
        colors=colors,
        symbols=symbols,
        families=families,
        levels=levels,
        fusion_bp_bonus=fusion,
        overclock=overclock,
    )


def plain(n: int | None) -> Reduction:
    return Reduction(n, ())


def gameplays(stem: str) -> list[Gameplay]:
    return [e.gameplay for e in parse(stem).entries]


def test_full_spirit() -> None:
    assert gameplays("card_spirit") == [
        gp(
            "スピリット",
            4,
            Reduction(None, (sc("赤", 2), sc("神"))),
            ("眷属", "武迅"),
            (Level(1, 1, 3000), Level(2, 3, 7000)),
            symbols=(sc("赤"),),
        )
    ]


def test_full_nexus() -> None:
    assert gameplays("card_nexus") == [
        gp(
            "ネクサス",
            3,
            plain(2),
            ("皇獣",),
            (Level(1, 0, None), Level(2, 1, None)),
            symbols=(sc("赤"),),
        )
    ]


def test_full_nexus_soukaishin() -> None:
    assert gameplays("card_nexus_soukaishin") == [
        gp(
            "ネクサス",
            2,
            plain(1),
            ("創界神", "オリン"),
            (Level(1, 0, None), Level(2, 5, None)),
            symbols=(sc("神"),),
        )
    ]


def test_full_magic() -> None:
    assert gameplays("card_magic") == [gp("マジック", 4, plain(2), ("武迅",), ())]


def test_full_magic_flash() -> None:
    assert gameplays("card_magic_flash") == [gp("マジック", 4, plain(2), (), ())] * 2


def test_full_brave() -> None:
    first, second = gameplays("card_brave")
    assert first == gp(
        "ブレイヴ",
        5,
        Reduction(None, (sc("赤", 2), sc("白", 2))),
        ("機竜", "星魂"),
        (Level(1, 1, 3000),),
        fusion=3000,
    )
    assert second == gp(
        "ブレイヴ",
        5,
        Reduction(None, (sc("赤", 2), sc("白", 2))),
        ("異魔神", "星魂", "機竜"),
        (Level(1, 0, 3000),),
        symbols=(sc("赤"),),
        fusion=3000,
    )


def test_full_ultimate() -> None:
    first, second = gameplays("card_ultimate")
    assert first == gp(
        "アルティメット",
        6,
        plain(3),
        ("新生", "古竜"),
        (Level(3, 1, 10000), Level(4, 3, 14000), Level(5, 5, 20000)),
        symbols=(sc("極"),),
    )
    assert second == gp(
        "アルティメット",
        6,
        Reduction(None, (sc("全"), sc("極", 3))),
        ("極契約", "新生", "古竜"),
        (Level(3, 1, 10000), Level(4, 3, 14000)),
        symbols=(sc("極"),),
        overclock=Overclock(5, 6000),
    )


def nexus_gp(
    card_type: str,
    cost: int,
    reduction: Reduction,
    families: tuple[str, ...],
    levels: tuple[Level, ...],
) -> Gameplay:
    return gp(card_type, cost, reduction, families, levels, symbols=(sc("赤"),), deck_limit=1)


def test_full_flip() -> None:
    a1, b1, a2, b2 = gameplays("card_flip")
    one = (Level(1, 0, None),)
    assert a1 == nexus_gp("ネクサス", 3, plain(2), ("起幻",), one)
    assert a2 == nexus_gp("ネクサス", 3, plain(2), ("起幻", "眷属"), one)
    assert b1 == nexus_gp("スピリット", 6, plain(None), ("起幻", "古竜"), (Level(1, 1, 6000),))
    assert b2 == nexus_gp(
        "スピリット",
        6,
        plain(None),
        ("起幻", "眷属", "古竜"),
        (Level(1, 1, 7000), Level(2, 3, 10000)),
    )


def test_full_spirit_xx_bs31() -> None:
    assert gameplays("card_spirit_xx_bs31") == [
        gp(
            "スピリット",
            0,
            plain(0),
            ("絶晶神",),
            (Level(1, 1, 5000), Level(2, 3, 10000)),
            colors=("白",),
            symbols=(sc("白"),),
        )
    ]


def test_full_spirit_bs01() -> None:
    first, second = gameplays("card_spirit_bs01")
    assert first == gp(
        "スピリット",
        0,
        plain(0),
        ("爬獣",),
        (Level(1, 1, 1000), Level(2, 3, 3000)),
        symbols=(sc("赤"),),
    )
    assert second == gp(
        "スピリット",
        0,
        plain(0),
        ("爬獣",),
        (Level(1, 1, 2000), Level(2, 3, 5000)),
        symbols=(sc("赤"),),
    )


def test_full_promo() -> None:
    levels = (Level(1, 1, 3000), Level(2, 2, 4000), Level(3, 5, 7000))
    families = [("竜人", "翼竜"), ("竜人", "翼竜"), ("起幻", "竜人", "翼竜")]
    assert gameplays("card_promo") == [
        gp("スピリット", 4, plain(2), f, levels, symbols=(sc("赤"),)) for f in families
    ]


SPIRIT_PRE = "<pre>スピリット\n4(2)/赤\n<1>Lv1 3000\nシンボル：赤</pre>"
MAGIC_PRE = "<pre>マジック\n4(2)/赤\nシンボル：なし</pre>"


def page(body: str) -> str:
    return (
        "<html><head><title>題名 - バトルスピリッツ wiki</title></head><body>"
        f"<span class='cardno'>BS01-001</span>{body}</body></html>"
    )


def test_headingless_page_ignores_pre_after_h4() -> None:
    entries = parse_card_page(page(f"{SPIRIT_PRE}<h4>x</h4>{SPIRIT_PRE}"), "u").entries
    assert len(entries) == 1


def test_headingless_page_skips_collapsed_blocks(caplog: pytest.LogCaptureFixture) -> None:
    collapsed = (
        "<div class='plugin-openclose'><div class='plugin-openclose-link'>"
        "<a><p>(エラッタ前) ▼</p></a></div>"
        f"<div class='plugin-openclose-contents'>{SPIRIT_PRE}</div></div>"
    )
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        entries = parse_card_page(page(SPIRIT_PRE + collapsed), "u").entries
    assert len(entries) == 1
    assert not caplog.records


def test_unknown_collapsed_block_warns_and_is_skipped(caplog: pytest.LogCaptureFixture) -> None:
    collapsed = (
        "<div class='plugin-openclose'><div class='plugin-openclose-link'>"
        "<a><p>謎の続き ▼</p></a></div>"
        f"<div class='plugin-openclose-contents'>{SPIRIT_PRE}</div></div>"
    )
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        entries = parse_card_page(page(MAGIC_PRE + collapsed), "u").entries
    assert len(entries) == 1
    assert [r.levelno for r in caplog.records] == [logging.WARNING]
    assert "謎の続き" in caplog.records[0].getMessage()


@pytest.mark.parametrize("card_type", ["スピリット", "ネクサス", "ブレイヴ", "アルティメット"])
def test_missing_level_line_raises(card_type: str) -> None:
    html = page(f"<pre>{card_type}\n4(2)/赤\nシンボル：なし</pre>")
    with pytest.raises(ParseError, match="level line"):
        parse_card_page(html, "u")
