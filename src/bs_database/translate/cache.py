"""SQLite translation cache keyed by (engine, src, tgt, sha256 of the text), ADR 0008."""

import hashlib
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1
_SQLITE_VARS = 400  # stay well under SQLite's bound-variable limit

_DDL = """
CREATE TABLE IF NOT EXISTS translations (
    engine TEXT NOT NULL,
    src TEXT NOT NULL,
    tgt TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (engine, src, tgt, sha256)
) WITHOUT ROWID
"""


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TranslationCache:
    """Created lazily: opening the object touches no file until the first read or write.

    ``sqlite3`` errors propagate: the cache is a local file, not an engine, so a failure
    there is an environment problem and must not be reported as a failed translation.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.execute(_DDL)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return conn

    def get_many(self, engine: str, src: str, tgt: str, texts: Sequence[str]) -> dict[str, str]:
        """Cached translations of ``texts`` (only the hits). A hash collision is a miss."""
        if not texts or not self.path.exists():
            return {}
        by_hash = {text_hash(t): t for t in texts}
        hashes = list(by_hash)
        found: dict[str, str] = {}
        conn = self._connect()
        try:
            for i in range(0, len(hashes), _SQLITE_VARS):
                chunk = hashes[i : i + _SQLITE_VARS]
                marks = ",".join("?" * len(chunk))
                rows = conn.execute(
                    "SELECT sha256, source_text, translated_text FROM translations "
                    f"WHERE engine=? AND src=? AND tgt=? AND sha256 IN ({marks})",
                    (engine, src, tgt, *chunk),
                )
                for sha, source, translated in rows:
                    if by_hash[sha] == source:
                        found[source] = translated
        finally:
            conn.close()
        return found

    def put_many(self, engine: str, src: str, tgt: str, pairs: Iterable[tuple[str, str]]) -> None:
        """Store ``(source, translation)`` pairs in one committed transaction."""
        rows = [
            (engine, src, tgt, text_hash(s), s, t, datetime.now(UTC).isoformat()) for s, t in pairs
        ]
        if not rows:
            return
        conn = self._connect()
        try:
            with conn:
                conn.executemany("INSERT OR REPLACE INTO translations VALUES (?,?,?,?,?,?,?)", rows)
        finally:
            conn.close()
