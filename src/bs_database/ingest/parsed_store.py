"""Parsed card pages as versioned JSON (#73).

Layout: ``<parsed_dir>/<source>/<sha256(url)>.json``, the same digest as the raw cache stem, so
one URL maps to ``cache/html/<source>/<d>.html`` and ``parsed/<source>/<d>.json``. The URL is
recovered by reading the ``url`` field. The page name is not used: Japanese names are up to
three bytes per character (255-byte file name limit) and differ by percent-encoding form.
"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from bs_database.ingest.atomic import atomic_write
from bs_database.ingest.cache import CachedPage
from bs_database.parsers.card_models import (
    SCHEMA_VERSION,
    CardEntry,
    CardImage,
    CardPage,
    CardText,
    Credit,
    Effect,
    Gameplay,
    Keyword,
    Level,
    Overclock,
    Printing,
    Reduction,
    SymbolCount,
    ValueDifference,
)


def parsed_path(parsed_dir: Path, source: str, url: str) -> Path:
    """Path of the parsed JSON for ``url`` (the url is hashed exactly as given)."""
    stem = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return parsed_dir / source / f"{stem}.json"


def write_card_json(parsed_dir: Path, page: CardPage, cached: CachedPage) -> Path:
    """Write ``page`` atomically and return the file path.

    ``from_cache`` describes the read that produced this file, not the original fetch;
    ``fetched_at`` is the time of the original fetch (the cache sidecar).
    """
    path = parsed_path(parsed_dir, cached.source, page.url)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": page.schema_version,
        "url": page.url,
        "provenance": {
            "source": cached.source,
            "fetched_at": cached.fetched_at.isoformat(),
            "from_cache": cached.from_cache,
        },
        "page": asdict(page),
    }
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    atomic_write(path, text.encode("utf-8"))
    return path


def read_card_json(path: Path) -> dict[str, Any]:
    """The JSON document stored at ``path``."""
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def _symbol(d: dict[str, Any]) -> SymbolCount:
    return SymbolCount(d["symbol"], d["count"], d["variant"], d["color"])


def _overclock(d: dict[str, Any] | None) -> Overclock | None:
    return None if d is None else Overclock(d["count_min"], d["bp_bonus"])


def _gameplay(d: dict[str, Any]) -> Gameplay:
    return Gameplay(
        card_type=d["card_type"],
        deck_limit=d["deck_limit"],
        cost=d["cost"],
        reduction=Reduction(
            d["reduction"]["plain"], tuple(_symbol(p) for p in d["reduction"]["parts"])
        ),
        colors=tuple(d["colors"]),
        symbols=tuple(_symbol(s) for s in d["symbols"]),
        families=tuple(d["families"]),
        levels=tuple(
            Level(
                x["level"],
                x["cores"],
                x["battle_points"],
                x["count_condition"],
                x["note"],
            )
            for x in d["levels"]
        ),
        fusion_bp_bonus=d["fusion_bp_bonus"],
        overclock=_overclock(d["overclock"]),
        card_class=d["card_class"],
        type_mark=d["type_mark"],
    )


def _effect(d: dict[str, Any]) -> Effect:
    return Effect(
        position=d["position"],
        form=d["form"],
        levels=tuple(d["levels"]),
        label=d["label"],
        keywords=tuple(Keyword(k["bracket"], k["name"], k["parameter"]) for k in d["keywords"]),
        timing=d["timing"],
        header=d["header"],
        text=d["text"],
    )


def _credit(d: dict[str, Any]) -> Credit:
    return Credit(d["name"], d["note"])


def _text(d: dict[str, Any] | None) -> CardText | None:
    if d is None:
        return None
    return CardText(
        effects=tuple(_effect(e) for e in d["effects"]),
        fusion_conditions=tuple(d["fusion_conditions"]),
        summon_condition=d["summon_condition"],
        overclock_condition=d["overclock_condition"],
        illustrators=tuple(_credit(c) for c in d["illustrators"]),
        concepts=tuple(_credit(c) for c in d["concepts"]),
        flavor=d["flavor"],
        flavor_note=d["flavor_note"],
    )


def _entry(d: dict[str, Any]) -> CardEntry:
    return CardEntry(
        number=d["number"],
        name_jp=d["name_jp"],
        name_en=d["name_en"],
        gameplay=_gameplay(d["gameplay"]),
        text=_text(d["text"]),
    )


def _printing(d: dict[str, Any]) -> Printing:
    return Printing(
        number=d["number"],
        product_name_jp=d["product_name_jp"],
        product_href=d["product_href"],
        rarity=d["rarity"],
        detail_jp=d["detail_jp"],
        note_jp=d["note_jp"],
        product_code=d["product_code"],
        block_icon=d["block_icon"],
        release_date=d["release_date"],
        section=d["section"],
    )


def _image(d: dict[str, Any]) -> CardImage:
    return CardImage(d["number"], d["large_url"], d["small_url"], tuple(d["caption"]))


def read_card_page(path: Path) -> tuple[CardPage, dict[str, Any]]:
    """Rebuild the :class:`CardPage` stored at ``path`` and return it with its provenance.

    A document written under another ``schema_version`` is rejected; the parsed tree must then
    be rebuilt from the HTML cache.
    """
    document = read_card_json(path)
    found = document.get("schema_version")
    if found != SCHEMA_VERSION:
        raise ValueError(
            f"{path}: parsed schema_version {found!r}, expected {SCHEMA_VERSION!r}; "
            "re-parse from the HTML cache"
        )
    p = document["page"]
    if p.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"{path}: page schema_version {p.get('schema_version')!r}, expected {SCHEMA_VERSION!r}"
        )
    page = CardPage(
        schema_version=p["schema_version"],
        url=p["url"],
        title_jp=p["title_jp"],
        entries=tuple(_entry(e) for e in p["entries"]),
        differences=tuple(
            ValueDifference(d["name_jp"], d["field"], tuple((n, v) for n, v in d["values"]))
            for d in p["differences"]
        ),
        printings=tuple(_printing(x) for x in p["printings"]),
        images=tuple(_image(i) for i in p["images"]),
    )
    provenance: dict[str, Any] = document["provenance"]
    return page, provenance
