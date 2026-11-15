"""Inputs of the review: normalized pages and the legacy v0.1.0 snapshot (#96).

Everything here is read-only. The legacy snapshot is the SQLite DB of release v0.1.0, whose
schema is in ``docs/data-model/current-schema.md``.
"""

import csv
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from bs_database.normalize.records import NORMALIZED_SCHEMA_VERSION


class ReviewError(Exception):
    """An input of the review is missing, unreadable or of another schema version."""


def iter_pages(normalized_dir: Path) -> Iterator[dict[str, Any]]:
    """Yield the ``page`` object of every ``<normalized_dir>/<source>/*.json``, sorted by path.

    Raises :class:`ReviewError` for a missing directory, an unreadable file or a file whose
    ``schema_version`` is not :data:`NORMALIZED_SCHEMA_VERSION`.
    """
    if not normalized_dir.is_dir():
        raise ReviewError(f"normalized directory not found: {normalized_dir}")
    for path in sorted(normalized_dir.glob("*/*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            version = document["schema_version"]
            page: dict[str, Any] = document["page"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ReviewError(f"cannot read {path}: {exc}") from exc
        if version != NORMALIZED_SCHEMA_VERSION:
            raise ReviewError(
                f"{path}: schema_version {version!r}, expected {NORMALIZED_SCHEMA_VERSION!r}; "
                "run `bsdb normalize` again"
            )
        yield page


_LEGACY_QUERY = (
    "SELECT c.card_id, f.name FROM cards c "
    "JOIN card_families cf ON cf.card_id = c.id "
    "JOIN families f ON f.id = cf.family_id "
    "ORDER BY c.card_id, f.name"
)


def load_legacy_families(db_path: Path) -> dict[str, tuple[str, ...]]:
    """``{card number: legacy English families}`` from the v0.1.0 snapshot (opened read-only)."""
    if not db_path.is_file():
        raise ReviewError(f"legacy database not found: {db_path}")
    try:
        connection = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            rows = connection.execute(_LEGACY_QUERY).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ReviewError(f"cannot read legacy database {db_path}: {exc}") from exc
    result: dict[str, list[str]] = {}
    for number, name in rows:
        result.setdefault(number, []).append(name)
    return {number: tuple(names) for number, names in result.items()}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """The rows of a glossary CSV as dicts (the header is the keys); ``[]`` when empty."""
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise ReviewError(f"cannot read {path}: {exc}") from exc
