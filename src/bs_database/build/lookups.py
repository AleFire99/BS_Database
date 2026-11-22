"""Lookup tables of the database, filled from the glossary (#120, ADR 0011).

Ids are assigned from the sorted ``code`` so a build is content-deterministic. The rows
that ``schema.sql`` seeds (translation statuses and sources, ``normal`` variant, image sizes,
``batspi`` source) keep their ids and are read back by code.
"""

import sqlite3
from dataclasses import dataclass

from bs_database.build.diagnostics import BuildError
from bs_database.glossary import FamilyEntry, Glossary, RarityEntry, SymbolEntry

SOURCE_MANUAL = "manual"
SOURCE_MACHINE = "machine"
STATUS_PENDING = "pending"
STATUS_REVIEWED = "reviewed"

# (code, English name); the kind of an effect is derived by the loader (rule table in build.md).
EFFECT_KINDS = (
    ("constant", "Constant"),
    ("flash", "Flash"),
    ("keyword_block", "Keyword block"),
    ("level", "Level"),
    ("main", "Main"),
    ("other", "Other"),
    ("set_active", "Set active"),
)


@dataclass(frozen=True, slots=True)
class Lookups:
    """``code -> id`` maps of every lookup table."""

    colors: dict[str, int]
    card_types: dict[str, int]
    rarities: dict[str, int]
    product_types: dict[str, int]
    variants: dict[str, int]
    keywords: dict[str, int]
    families: dict[str, int]
    symbols: dict[str, int]
    effect_kinds: dict[str, int]
    translation_statuses: dict[str, int]
    translation_sources: dict[str, int]
    image_sizes: dict[str, int]
    sources: dict[str, int]

    def source_id(self, code: str | None) -> int | None:
        """Id of a translation source code (``None`` stays ``None``)."""
        return None if code is None else self.translation_sources[code]

    def status_id(self, code: str) -> int:
        """Id of a translation status code."""
        return self.translation_statuses[code]


def _simple(conn: sqlite3.Connection, table: str, rows: list[tuple[str, str]]) -> dict[str, int]:
    """Insert ``(code, name)`` rows in code order with ids from 1; return ``code -> id``."""
    ordered = sorted(rows)
    conn.executemany(
        f"INSERT INTO {table} (id, code, name) VALUES (?, ?, ?)",
        [(i, code, name) for i, (code, name) in enumerate(ordered, start=1)],
    )
    return {code: i for i, (code, _) in enumerate(ordered, start=1)}


def _read_back(conn: sqlite3.Connection, table: str) -> dict[str, int]:
    rows = conn.execute(f"SELECT code, id FROM {table}").fetchall()
    return {code: i for code, i in rows}


def _rows(glossary: Glossary, kind: str) -> list[tuple[str, str]]:
    """``(code, English name)`` of every curated row of ``kind`` (name falls back to the code)."""
    return [(e.code, e.en or e.code) for e in glossary.entries[kind] if e.code]


def insert_lookups(conn: sqlite3.Connection, glossary: Glossary) -> Lookups:
    """Fill every lookup table from ``glossary`` and return the id maps."""
    colors = _simple(conn, "colors", _rows(glossary, "colors"))
    card_types = _simple(conn, "card_types", _rows(glossary, "card_types"))
    product_types = _simple(conn, "product_types", _rows(glossary, "product_types"))
    keywords = _simple(conn, "keywords", _rows(glossary, "keywords"))
    effect_kinds = _simple(conn, "effect_kinds", list(EFFECT_KINDS))
    if "other" not in product_types:
        raise BuildError("product_types.csv needs the fallback code 'other'")

    rarities = _rarities(conn, glossary)
    symbols = _symbols(conn, glossary, colors)
    variants = _variants(conn, glossary)
    statuses = _read_back(conn, "translation_statuses")
    sources = _read_back(conn, "translation_sources")
    families = _families(conn, glossary, statuses, sources)
    return Lookups(
        colors=colors,
        card_types=card_types,
        rarities=rarities,
        product_types=product_types,
        variants=variants,
        keywords=keywords,
        families=families,
        symbols=symbols,
        effect_kinds=effect_kinds,
        translation_statuses=statuses,
        translation_sources=sources,
        image_sizes=_read_back(conn, "image_sizes"),
        sources=_read_back(conn, "sources"),
    )


def _rarities(conn: sqlite3.Connection, glossary: Glossary) -> dict[str, int]:
    rows = sorted(
        (e.code, e.en or e.code, e.sort_order)
        for e in glossary.entries["rarities"]
        if e.code and isinstance(e, RarityEntry)
    )
    ids = {code: i for i, (code, _, _) in enumerate(rows, start=1)}
    conn.executemany(
        "INSERT INTO rarities (id, code, name, sort_order) VALUES (?, ?, ?, ?)",
        [(ids[code], code, name, order) for code, name, order in rows],
    )
    return ids


def _symbols(
    conn: sqlite3.Connection, glossary: Glossary, colors: dict[str, int]
) -> dict[str, int]:
    rows = sorted(
        (e.code, e.en or e.code, e.color_code)
        for e in glossary.entries["symbols"]
        if e.code and isinstance(e, SymbolEntry)
    )
    ids = {code: i for i, (code, _, _) in enumerate(rows, start=1)}
    conn.executemany(
        "INSERT INTO symbols (id, code, name, color_id) VALUES (?, ?, ?, ?)",
        [(ids[code], code, name, colors[c] if c else None) for code, name, c in rows],
    )
    return ids


def _variants(conn: sqlite3.Connection, glossary: Glossary) -> dict[str, int]:
    """``normal`` is seeded as id 1 (the ``DEFAULT 1`` of ``printings.variant_id``)."""
    ids = _read_back(conn, "variants")
    others = sorted((e.code, e.en or e.code) for e in glossary.entries["variants"] if e.code)
    for code, name in others:
        if code in ids:
            continue
        ids[code] = max(ids.values()) + 1
        conn.execute(
            "INSERT INTO variants (id, code, name) VALUES (?, ?, ?)", (ids[code], code, name)
        )
    return ids


def _families(
    conn: sqlite3.Connection,
    glossary: Glossary,
    statuses: dict[str, int],
    sources: dict[str, int],
) -> dict[str, int]:
    entries = sorted(
        (e for e in glossary.entries["families"] if e.code and isinstance(e, FamilyEntry)),
        key=lambda e: e.code,
    )
    ids = {e.code: i for i, e in enumerate(entries, start=1)}
    manual, reviewed, pending = (
        sources[SOURCE_MANUAL],
        statuses[STATUS_REVIEWED],
        statuses[STATUS_PENDING],
    )
    conn.executemany(
        "INSERT INTO families (id, code, name_jp, name_en, en_source_id, en_status_id)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                ids[e.code],
                e.code,
                e.jp,
                e.en or None,
                manual if e.en else None,
                reviewed if e.en else pending,
            )
            for e in entries
        ],
    )
    aliases = sorted(
        {(ids[e.code], alias) for e in entries for alias in e.aliases_en if alias and alias != e.en}
    )
    conn.executemany(
        "INSERT INTO family_aliases (family_id, alias, lang, translation_source_id)"
        " VALUES (?, ?, 'en', ?)",
        [(family_id, alias, sources[SOURCE_MANUAL]) for family_id, alias in aliases],
    )
    return ids
