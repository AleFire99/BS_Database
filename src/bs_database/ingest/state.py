"""Ingestion run state and resume (#72): state machine and SQLite store."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Self


class IngestState(StrEnum):
    """Lifecycle stage of one page."""

    DISCOVERED = "discovered"
    FETCHED = "fetched"
    PARSED = "parsed"
    NORMALIZED = "normalized"
    TRANSLATED = "translated"
    LOADED = "loaded"
    FAILED = "failed"


class PageKind(StrEnum):
    """Kind of page tracked by the store."""

    INDEX = "index"
    SET = "set"
    CARD = "card"


S = IngestState

_CHAIN = (S.DISCOVERED, S.FETCHED, S.PARSED, S.NORMALIZED, S.TRANSLATED, S.LOADED)
_STAGES = _CHAIN[:-1]

TRANSITIONS: dict[IngestState, frozenset[IngestState]] = {
    S.DISCOVERED: frozenset({S.FETCHED, S.FAILED}),
    S.FETCHED: frozenset({S.PARSED, S.FAILED}),
    S.PARSED: frozenset({S.NORMALIZED, S.FAILED}),
    S.NORMALIZED: frozenset({S.TRANSLATED, S.FAILED}),
    S.TRANSLATED: frozenset({S.LOADED, S.FAILED}),
    S.LOADED: frozenset(),
    S.FAILED: frozenset(_STAGES),
}


class IllegalTransition(ValueError):
    """Raised when a state change is not allowed by TRANSITIONS."""


def check_transition(src: IngestState, dst: IngestState) -> None:
    """Raise IllegalTransition unless src -> dst is in the table."""
    if dst not in TRANSITIONS[src]:
        raise IllegalTransition(f"{src.value} -> {dst.value} is not allowed")


class UnknownPage(KeyError):
    """Raised when a URL is not tracked by the store."""


class RetriesExhausted(RuntimeError):
    """Raised when a failed page has used all its attempts."""


class SchemaTooNew(RuntimeError):
    """Raised when the database was written by a newer version of the code."""


DEFAULT_MAX_ATTEMPTS = 3

MIGRATIONS: tuple[tuple[str, ...], ...] = (
    (
        """
        CREATE TABLE pages (
          url TEXT PRIMARY KEY,
          kind TEXT NOT NULL CHECK (kind IN ('index','set','card')),
          state TEXT NOT NULL,
          failed_from TEXT,
          attempts INTEGER NOT NULL DEFAULT 0,
          last_error TEXT,
          content_sha256 TEXT,
          updated_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX pages_state ON pages(state, kind)",
    ),
)


@dataclass(frozen=True)
class PageRecord:
    """One row of the pages table."""

    url: str
    kind: PageKind
    state: IngestState
    failed_from: IngestState | None
    attempts: int
    last_error: str | None
    content_sha256: str | None
    updated_at: str


_COLUMNS = "url, kind, state, failed_from, attempts, last_error, content_sha256, updated_at"


def _record(row: tuple[object, ...]) -> PageRecord:
    url, kind, state, failed_from, attempts, last_error, sha, updated_at = row
    return PageRecord(
        url=str(url),
        kind=PageKind(str(kind)),
        state=IngestState(str(state)),
        failed_from=IngestState(str(failed_from)) if failed_from is not None else None,
        attempts=int(str(attempts)),
        last_error=None if last_error is None else str(last_error),
        content_sha256=None if sha is None else str(sha),
        updated_at=str(updated_at),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


class StateStore:
    """Durable per-page state in SQLite. Every API call is one transaction.

    ``max_attempts`` counts failures of one page in the pipeline (3 failures,
    then exhausted). It is distinct from the HTTP retries of policy 3.5, which
    live in the HTTP client.
    """

    def __init__(
        self,
        path: Path,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._now = now
        self.max_attempts = max_attempts
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        try:
            self._migrate()
        except BaseException:
            self._conn.close()
            raise

    def _migrate(self) -> None:
        with self._tx():
            row = self._conn.execute("PRAGMA user_version").fetchone()
            version = int(row[0])
            if version > len(MIGRATIONS):
                raise SchemaTooNew(
                    f"database schema {version} is newer than supported {len(MIGRATIONS)}"
                )
            for number, statements in enumerate(MIGRATIONS[version:], start=version + 1):
                for statement in statements:
                    self._conn.execute(statement)
                self._conn.execute(f"PRAGMA user_version = {number}")

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    def _stamp(self) -> str:
        return self._now().astimezone(UTC).isoformat()

    def upsert_discovered(self, url: str, kind: PageKind) -> bool:
        """Insert a new page as discovered; leave an existing row untouched."""
        with self._tx() as conn:
            cur = conn.execute(
                f"INSERT OR IGNORE INTO pages ({_COLUMNS}) "
                "VALUES (?, ?, ?, NULL, 0, NULL, NULL, ?)",
                (url, kind.value, IngestState.DISCOVERED.value, self._stamp()),
            )
            return cur.rowcount == 1

    def get(self, url: str) -> PageRecord:
        row = self._conn.execute(f"SELECT {_COLUMNS} FROM pages WHERE url = ?", (url,)).fetchone()
        if row is None:
            raise UnknownPage(url)
        return _record(row)

    def advance(
        self,
        url: str,
        new_state: IngestState,
        *,
        content_sha256: str | None = None,
    ) -> None:
        """Move a page one step forward; failure and retry have their own calls."""
        if new_state is IngestState.FAILED:
            raise IllegalTransition("use mark_failed to fail a page")
        with self._tx() as conn:
            current = self._locked_get(conn, url)
            if current.state is IngestState.FAILED:
                raise IllegalTransition("use retry")
            check_transition(current.state, new_state)
            conn.execute(
                "UPDATE pages SET state = ?, failed_from = NULL, attempts = 0, "
                "last_error = NULL, content_sha256 = COALESCE(?, content_sha256), "
                "updated_at = ? WHERE url = ?",
                (new_state.value, content_sha256, self._stamp(), url),
            )

    def mark_failed(self, url: str, reason: str, *, permanent: bool = False) -> None:
        """Record a failure of the stage the page was in; counts one attempt.

        ``permanent=True`` (a 404, policy 3.5: no retry) sets the attempts to ``max_attempts``,
        so the page is exhausted at once: reported by ``iter_exhausted``, never retried.
        """
        with self._tx() as conn:
            current = self._locked_get(conn, url)
            check_transition(current.state, IngestState.FAILED)
            attempts = (
                self.max_attempts if permanent else min(current.attempts + 1, self.max_attempts)
            )
            conn.execute(
                "UPDATE pages SET state = ?, failed_from = ?, attempts = ?, "
                "last_error = ?, updated_at = ? WHERE url = ?",
                (
                    IngestState.FAILED.value,
                    current.state.value,
                    attempts,
                    reason,
                    self._stamp(),
                    url,
                ),
            )

    def retry(self, url: str) -> None:
        """Return a failed page to the stage that failed, unless attempts ran out."""
        with self._tx() as conn:
            current = self._locked_get(conn, url)
            if current.state is not IngestState.FAILED or current.failed_from is None:
                raise IllegalTransition(f"{url} is not failed")
            if current.attempts >= self.max_attempts:
                raise RetriesExhausted(f"{url} failed {current.attempts} times")
            check_transition(IngestState.FAILED, current.failed_from)
            conn.execute(
                "UPDATE pages SET state = ?, updated_at = ? WHERE url = ?",
                (current.failed_from.value, self._stamp(), url),
            )

    def reset_failed(self, *, prefix: str) -> int:
        """Give a fresh set of attempts to failed pages whose error starts with ``prefix``.

        Only those rows are touched (``attempts`` back to 0, state stays ``failed``), so a
        permanent failure (404, policy skip) stays exhausted. Returns the number of rows.
        """
        escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE pages SET attempts = 0, updated_at = ? "
                "WHERE state = ? AND last_error LIKE ? ESCAPE '\\'",
                (self._stamp(), IngestState.FAILED.value, escaped + "%"),
            )
            return cur.rowcount

    def iter_exhausted(self) -> list[PageRecord]:
        """Failed pages that used all attempts, for reporting."""
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM pages WHERE state = ? AND attempts >= ? ORDER BY url",
            (IngestState.FAILED.value, self.max_attempts),
        ).fetchall()
        return [_record(r) for r in rows]

    def _locked_get(self, conn: sqlite3.Connection, url: str) -> PageRecord:
        row = conn.execute(f"SELECT {_COLUMNS} FROM pages WHERE url = ?", (url,)).fetchone()
        if row is None:
            raise UnknownPage(url)
        return _record(row)

    def iter_pending(
        self,
        kind: PageKind | None = None,
        state: IngestState | None = None,
    ) -> list[PageRecord]:
        """Pages with work left: unfinished ones plus failed ones still retryable.

        Failed pages are returned in state ``failed`` (call ``retry`` on them),
        regardless of the ``state`` filter, which matches the current state only
        and never ``failed_from``.
        """
        sql = f"SELECT {_COLUMNS} FROM pages WHERE state != ? AND (state != ? OR attempts < ?)"
        args: list[str | int] = [
            IngestState.LOADED.value,
            IngestState.FAILED.value,
            self.max_attempts,
        ]
        if kind is not None:
            sql += " AND kind = ?"
            args.append(kind.value)
        if state is not None:
            sql += " AND state = ?"
            args.append(state.value)
        rows = self._conn.execute(sql + " ORDER BY url", args).fetchall()
        return [_record(r) for r in rows]

    def counts(self) -> dict[IngestState, int]:
        """Number of pages per state (all states present)."""
        result = dict.fromkeys(IngestState, 0)
        for state, n in self._conn.execute("SELECT state, COUNT(*) FROM pages GROUP BY state"):
            result[IngestState(state)] = n
        return result

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
