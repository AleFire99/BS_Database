"""Orchestration of one build: fresh temp file, one transaction, checks, atomic replace."""

import os
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from bs_database import __version__
from bs_database.build.cards import load_cards
from bs_database.build.diagnostics import BuildError, BuildWarnings
from bs_database.build.effects import load_effects
from bs_database.build.grouping import group_entries
from bs_database.build.images import load_images, load_source_pages
from bs_database.build.lookups import Lookups, insert_lookups
from bs_database.build.products import load_products_and_printings
from bs_database.build.reader import Document, printings_by_number, read_documents
from bs_database.glossary import Glossary, load_glossary
from bs_database.ingest.cache import RawCache
from bs_database.normalize.records import NORMALIZED_SCHEMA_VERSION
from bs_database.schema import load_schema_sql

# Inserts every data table inside the open transaction; later steps extend ``_load``.
Loader = Callable[[sqlite3.Connection, Lookups, BuildWarnings], None]


@dataclass(frozen=True, slots=True)
class BuildResult:
    """What a build produced: the file, rows per table and the warning counts."""

    path: Path
    table_counts: dict[str, int]
    warnings: dict[str, int]
    image_levels: dict[str, int]  # images decided by each level of the association cascade


DEFAULT_DATA_VERSION = "dev"


def schema_version_text(user_version: int) -> str:
    """``major * 10000 + minor * 100 + patch`` back to ``major.minor.patch`` (ADR 0003)."""
    return f"{user_version // 10000}.{user_version // 100 % 100}.{user_version % 100}"


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Row count of every table, sorted by name."""
    names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            " ORDER BY name"
        )
    ]
    return {n: conn.execute(f"SELECT count(*) FROM {n}").fetchone()[0] for n in names}


def utc_timestamp(value: str | None = None) -> str:
    """ISO 8601 UTC with a ``Z`` suffix (ADR 0003): ``value`` converted, or now."""
    moment = datetime.fromisoformat(value) if value is not None else datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def source_snapshot(documents: Sequence[Document]) -> str | None:
    """``batspi <first>..<last fetched date>; <N> pages; normalized <schema>``, or ``None``."""
    if not documents:
        return None
    dates = sorted(d.fetched_at[:10] for d in documents)
    sources = "+".join(sorted({d.source for d in documents}))
    return (
        f"{sources} {dates[0]}..{dates[-1]}; {len(documents)} pages;"
        f" normalized {NORMALIZED_SCHEMA_VERSION}"
    )


def _insert_meta(
    conn: sqlite3.Connection, built_at: str, snapshot: str | None, data_version: str
) -> None:
    """The single ``schema_meta`` row (ADR 0003, #121)."""
    (user_version,) = conn.execute("PRAGMA user_version").fetchone()
    conn.execute(
        "INSERT INTO schema_meta (id, schema_version, data_version, built_at, source_snapshot,"
        " generator) VALUES (1, ?, ?, ?, ?, ?)",
        (schema_version_text(user_version), data_version, built_at, snapshot, __version__),
    )


def _remove(path: Path) -> None:
    for suffix in ("", "-journal", "-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def _load_data(
    conn: sqlite3.Connection,
    lookups: Lookups,
    warnings: BuildWarnings,
    documents: Sequence[Document],
    cache_dir: Path | None,
) -> dict[str, int]:
    """Insert every data table (the order follows the foreign keys); return the image levels."""
    groups = group_entries(list(documents))
    printings = printings_by_number(list(documents))
    cards = load_cards(conn, lookups, warnings, groups, printings)
    load_effects(conn, lookups, warnings, groups, cards)
    illustrators = {
        m.number: m.entry["text"]["illustrators"]
        for g in groups
        for m in g.members
        if m.entry["text"]
    }
    index = load_products_and_printings(
        conn, lookups, warnings, list(documents), cards.number_ids, illustrators
    )
    image_levels = load_images(conn, lookups, warnings, documents, index)
    cache = RawCache(cache_dir) if cache_dir is not None else None
    load_source_pages(conn, lookups, warnings, documents, cards, index, cache)
    return dict(sorted(image_levels.items()))


def build_from_directories(
    out: Path,
    normalized_dir: Path,
    glossary_dir: Path,
    *,
    cache_dir: Path | None = None,
    built_at: str | None = None,
    data_version: str = DEFAULT_DATA_VERSION,
) -> BuildResult:
    """Read the glossary and the normalized documents, then :func:`build_database`."""
    glossary = load_glossary(glossary_dir)
    documents = read_documents(normalized_dir)
    if not documents:
        raise BuildError(f"no normalized documents in {normalized_dir}; run `bsdb normalize` first")
    return build_database(
        out,
        glossary,
        documents,
        cache_dir=cache_dir,
        built_at=built_at,
        data_version=data_version,
    )


def build_database(
    out: Path,
    glossary: Glossary,
    documents: Sequence[Document] = (),
    *,
    cache_dir: Path | None = None,
    built_at: str | None = None,
    data_version: str = DEFAULT_DATA_VERSION,
    load: Loader | None = None,
) -> BuildResult:
    """Build a fresh database at ``out``.

    The data goes to ``<out>.tmp`` (never appended to), is inserted in one transaction and
    checked (foreign keys, integrity) before ``os.replace`` puts it at ``out``. On any error
    the temp file is deleted and an existing ``out`` stays as it was.
    """
    tmp = out.with_name(out.name + ".tmp")
    out.parent.mkdir(parents=True, exist_ok=True)
    _remove(tmp)
    warnings = BuildWarnings()
    stamp = utc_timestamp(built_at)
    conn = sqlite3.connect(tmp, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.executescript(load_schema_sql())
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN")
        lookups = insert_lookups(conn, glossary)
        if load is not None:
            load(conn, lookups, warnings)
        image_levels = _load_data(conn, lookups, warnings, documents, cache_dir)
        _insert_meta(conn, stamp, source_snapshot(documents), data_version)
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise BuildError(f"foreign key violations: {violations[:5]}")
        conn.execute("COMMIT")
        if conn.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise BuildError("integrity_check failed")
        counts = table_counts(conn)
        conn.close()
        os.replace(tmp, out)
    except BaseException:
        conn.close()
        _remove(tmp)
        raise
    return BuildResult(out, counts, warnings.counts(), image_levels)
