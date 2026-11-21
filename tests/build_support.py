"""Helpers to build a database from the normalized goldens or from edited copies (#120)."""

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

from golden_support import NORMALIZED_GOLDENS, real_glossary

from bs_database.build import BuildResult, build_database
from bs_database.build.reader import Document, Json, check_documents, read_documents


def golden_json(name: str) -> Json:
    """A deep copy of one normalized golden (``card_spirit`` for ``card_spirit.json``)."""
    data = json.loads((NORMALIZED_GOLDENS / f"{name}.json").read_text(encoding="utf-8"))
    return copy.deepcopy(data)


def as_document(data: Json, path: Path | None = None) -> Document:
    """Wrap a normalized document dict as the reader would."""
    return Document(
        url=data["url"],
        source=data["provenance"]["source"],
        fetched_at=data["provenance"]["fetched_at"],
        parsed_schema_version=data["parsed_schema_version"],
        path=path or Path(f"{data['url']}.json"),
        page=data["page"],
    )


def golden_documents() -> list[Document]:
    """The 32 golden documents."""
    return read_documents(NORMALIZED_GOLDENS)


def build(out: Path, documents: list[Document], **kwargs: Any) -> BuildResult:
    """Build ``out`` from ``documents`` with the real glossary and a fixed ``built_at``."""
    kwargs.setdefault("built_at", "2026-01-01T00:00:00+00:00")
    return build_database(out, real_glossary(), check_documents(documents), **kwargs)


def query(path: Path, sql: str, *args: object) -> list[tuple[Any, ...]]:
    """Run a read-only query on a built database."""
    with sqlite3.connect(path) as conn:
        return conn.execute(sql, args).fetchall()
