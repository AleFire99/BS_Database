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
from bs_database.parsers.card_models import CardPage


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
