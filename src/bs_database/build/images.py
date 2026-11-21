"""Printing images and source page provenance (#120).

A batspi image is tied to a card number, not to a printing: the link is the caption and the file
suffix. The association is a cascade (the first level that decides wins):

- L0 the number has one printing;
- L1 caption[0] is the name of exactly one printing's product;
- L2 several printings of that product: the variant word in the caption picks the variant;
- L3 no product match: the variant word alone picks a unique printing;
- L4 several printings of the product, no variant word: the first one (``normal`` first);
- L5 nothing matches: the first printing of the number (``normal`` first).

Several images of one printing and size get ``position`` 1, 2, ... in page order.
"""

import hashlib
import json
import sqlite3
from collections import Counter
from collections.abc import Sequence

from bs_database.build.cards import CardIds
from bs_database.build.diagnostics import BuildWarnings
from bs_database.build.lookups import Lookups
from bs_database.build.products import Printing, PrintingIndex
from bs_database.build.reader import Document, Json
from bs_database.ingest.cache import RawCache

VARIANT_WORDS = {
    "secret": ("シークレット", "SECRET"),
    "parallel": ("パラレル",),
    "full_art": ("フルアート",),
}
NORMAL = "normal"


def _normal_first(printings: Sequence[Printing]) -> list[Printing]:
    return sorted(printings, key=lambda p: p.variant != NORMAL)  # stable: keeps page order


def associate(image: Json, candidates: Sequence[Printing]) -> tuple[Printing, str]:
    """The printing of ``image`` among the printings of its number and the cascade level used."""
    if len(candidates) == 1:
        return candidates[0], "L0"
    caption: list[str] = image["caption"]
    named = [p for p in candidates if caption and caption[0] in p.names]
    if len(named) == 1:
        return named[0], "L1"
    pool = named or list(candidates)
    text = " ".join(caption[1:])
    by_variant = [p for p in pool if any(w in text for w in VARIANT_WORDS.get(p.variant, ()))]
    if named and by_variant:
        return by_variant[0], "L2"
    if not named and len(by_variant) == 1:
        return by_variant[0], "L3"
    if named:
        return _normal_first(named)[0], "L4"
    return _normal_first(candidates)[0], "L5"


def load_images(
    conn: sqlite3.Connection,
    lookups: Lookups,
    warnings: BuildWarnings,
    documents: Sequence[Document],
    index: PrintingIndex,
) -> Counter[str]:
    """Insert ``printing_images``; return how many images each cascade level decided."""
    levels: Counter[str] = Counter()
    positions: Counter[tuple[int, str]] = Counter()
    seen: set[tuple[int, str, str]] = set()
    rows: list[tuple[int, int, int, str]] = []
    for doc in sorted(documents, key=lambda d: d.url):
        for image in doc.images:
            candidates = index.by_number.get(image["number"], [])
            if not candidates:
                warnings.add("image_without_printing", f"{image['number']} {image['large_url']}")
                continue
            printing, level = associate(image, candidates)
            levels[level] += 1
            if level == "L4":
                warnings.add("image_fallback_first_of_product", image["number"])
            elif level == "L5":
                warnings.add("image_fallback_first_of_number", image["number"])
            for size, url in (("small", image["small_url"]), ("large", image["large_url"])):
                if url is None or (printing.id, size, url) in seen:
                    continue
                seen.add((printing.id, size, url))
                positions[(printing.id, size)] += 1
                rows.append(
                    (printing.id, lookups.image_sizes[size], positions[(printing.id, size)], url)
                )
    rows.sort()
    conn.executemany(
        "INSERT INTO printing_images (id, printing_id, image_size_id, position, source_url)"
        " VALUES (?, ?, ?, ?, ?)",
        [(i, *row) for i, row in enumerate(rows, start=1)],
    )
    return levels


def _content_hash(doc: Document, cache: RawCache | None, warnings: BuildWarnings) -> str:
    """sha256 of the cached raw HTML; else of the normalized document (counted as a warning)."""
    cached = cache.load(doc.url, doc.source) if cache is not None else None
    if cached is not None:
        return hashlib.sha256(cached.content).hexdigest()
    warnings.add("source_page_without_raw_html", doc.url)
    try:
        data = doc.path.read_bytes()
    except OSError:
        data = json.dumps(doc.page, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_source_pages(
    conn: sqlite3.Connection,
    lookups: Lookups,
    warnings: BuildWarnings,
    documents: Sequence[Document],
    cards: CardIds,
    index: PrintingIndex,
    cache: RawCache | None,
) -> None:
    """Insert ``source_pages`` and the card and product links."""
    docs = sorted(documents, key=lambda d: d.url)
    page_ids = {d.url: i for i, d in enumerate(docs, start=1)}
    conn.executemany(
        "INSERT INTO source_pages (id, source_id, url, fetched_at, content_sha256, parser_version)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                page_ids[d.url],
                lookups.sources[d.source],
                d.url,
                d.fetched_at,
                _content_hash(d, cache, warnings),
                d.parsed_schema_version,
            )
            for d in docs
        ],
    )
    card_links = sorted(
        {(cards.by_number[e["number"]], page_ids[d.url]) for d in docs for e in d.entries}
    )
    conn.executemany(
        "INSERT INTO card_source_pages (card_id, source_page_id) VALUES (?, ?)", card_links
    )
    product_links = sorted({(p.id, page_ids[url]) for p in index.products for url in p.urls})
    conn.executemany(
        "INSERT INTO product_source_pages (product_id, source_page_id) VALUES (?, ?)", product_links
    )
