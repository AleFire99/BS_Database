"""parse_card_page against the card fixtures and mutated pages."""

import json
import logging
from pathlib import Path

import pytest

from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.card_models import SCHEMA_VERSION, CardPage
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
