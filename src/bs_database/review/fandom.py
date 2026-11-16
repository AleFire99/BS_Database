"""Fetch and store fandom names for the glossary review (ADR 0009, #104).

``fetch_names`` reads the family and keyword categories and the rarity page through the
``FandomApi`` and parses them; pages that do not parse are listed as unmatched. The result is a
sorted, deterministic JSON file that only the review reads (never normalize).
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from bs_database.ingest.atomic import atomic_write
from bs_database.parsers.fandom import (
    FandomName,
    FandomRarity,
    jp_key,
    parse_name,
    parse_rarities,
)

FANDOM_JSON = "fandom_names.json"
FAMILY_CATEGORY = "Category:Family"
KEYWORD_CATEGORY = "Category:Keywords"
RARITY_PAGE = "Card Rarity"


class NameSource(Protocol):
    """The part of ``FandomApi`` used here (tests pass a fake)."""

    requests_made: int

    def category_members(self, category: str) -> list[str]: ...

    def wikitext(self, titles: list[str]) -> dict[str, str]: ...


@dataclass
class FandomData:
    families: list[FandomName] = field(default_factory=list)
    keywords: list[FandomName] = field(default_factory=list)
    rarities: list[FandomRarity] = field(default_factory=list)
    unmatched_families: list[str] = field(default_factory=list)
    unmatched_keywords: list[str] = field(default_factory=list)
    requests_made: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "families": [asdict(n) for n in self.families],
            "keywords": [asdict(n) for n in self.keywords],
            "rarities": [asdict(r) for r in self.rarities],
            "unmatched": {
                "families": self.unmatched_families,
                "keywords": self.unmatched_keywords,
            },
            "requests_made": self.requests_made,
        }


def _names(api: NameSource, category: str) -> tuple[list[FandomName], list[str]]:
    texts = api.wikitext(api.category_members(category))
    names: list[FandomName] = []
    unmatched: list[str] = []
    for title, text in texts.items():
        parsed = parse_name(title, text)
        if parsed is None:
            unmatched.append(title)
        else:
            names.append(parsed)
    names.sort(key=lambda n: (jp_key(n.jp), n.title))
    return names, sorted(unmatched)


def fetch_names(api: NameSource) -> FandomData:
    """Family and keyword names plus rarities; ``requests_made`` is read after the last call."""
    families, unmatched_families = _names(api, FAMILY_CATEGORY)
    keywords, unmatched_keywords = _names(api, KEYWORD_CATEGORY)
    rarity_text = api.wikitext([RARITY_PAGE]).get(RARITY_PAGE, "")
    rarities = sorted(parse_rarities(rarity_text), key=lambda r: (jp_key(r.jp), r.en))
    return FandomData(
        families,
        keywords,
        rarities,
        unmatched_families,
        unmatched_keywords,
        api.requests_made,
    )


def write_names(path: Path, data: FandomData) -> None:
    text = json.dumps(data.to_json(), ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, text.encode("utf-8"))
