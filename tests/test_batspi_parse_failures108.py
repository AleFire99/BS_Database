"""Parser failures found by the full scrape (#108), each on the real trimmed page of its class."""

import json
from pathlib import Path

from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.card_models import CardPage

HTML_DIR = Path(__file__).parent / "fixtures" / "html"
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
