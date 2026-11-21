"""Read the normalized documents of ``data/normalized`` (#120, ADR 0008).

The loader works on the JSON as written by ``bsdb normalize``; the dataclasses of
``normalize.records`` describe it, but plain dicts are enough here and keep the reader
tolerant to additive fields of a minor schema bump.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs_database.build.diagnostics import BuildError
from bs_database.normalize.records import NORMALIZED_SCHEMA_VERSION

Json = dict[str, Any]
SUPPORTED_MAJOR = NORMALIZED_SCHEMA_VERSION.split(".")[0]


@dataclass(frozen=True, slots=True)
class Document:
    """One normalized card page with its provenance."""

    url: str
    source: str
    fetched_at: str
    parsed_schema_version: str
    path: Path
    page: Json

    @property
    def entries(self) -> list[Json]:
        """The card number entries of the page, in page order."""
        return list(self.page["entries"])

    @property
    def printings(self) -> list[Json]:
        """The printing rows of the page, in page order."""
        return list(self.page["printings"])

    @property
    def images(self) -> list[Json]:
        """The gallery images of the page, in page order."""
        return list(self.page["images"])


def _document(path: Path) -> Document:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        version = str(data["schema_version"])
        provenance = data["provenance"]
        doc = Document(
            url=str(data["url"]),
            source=str(provenance["source"]),
            fetched_at=str(provenance["fetched_at"]),
            parsed_schema_version=str(data["parsed_schema_version"]),
            path=path,
            page=data["page"],
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BuildError(f"{path}: not a normalized document ({exc!r})") from exc
    if version.split(".")[0] != SUPPORTED_MAJOR:
        raise BuildError(
            f"{path}: schema_version {version}, this build reads major {SUPPORTED_MAJOR}"
        )
    return doc


def read_documents(directory: Path) -> list[Document]:
    """Every ``*.json`` under ``directory`` (files starting with ``_`` are reports), by url.

    A document of another schema major version, a repeated url and a card number that appears
    in two documents are errors.
    """
    paths = sorted(p for p in directory.rglob("*.json") if not p.name.startswith("_"))
    documents = sorted((_document(p) for p in paths), key=lambda d: (d.url, str(d.path)))
    return check_documents(documents)


def check_documents(documents: list[Document]) -> list[Document]:
    """Raise :class:`BuildError` on a repeated url or a number in two documents."""
    urls: set[str] = set()
    owner: dict[str, str] = {}
    for doc in documents:
        if doc.url in urls:
            raise BuildError(f"url in two documents: {doc.url}")
        urls.add(doc.url)
        for entry in doc.entries:
            number = entry["number"]
            if number in owner:
                raise BuildError(
                    f"card number {number} in two documents: {owner[number]}, {doc.url}"
                )
            owner[number] = doc.url
    return documents
