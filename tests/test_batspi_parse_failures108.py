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
