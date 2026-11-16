"""Tests for the ingestion state machine and store (#72)."""

from __future__ import annotations

import itertools
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bs_database.ingest.state import (
    TRANSITIONS,
    IllegalTransition,
    IngestState,
    PageKind,
    RetriesExhausted,
    SchemaTooNew,
    StateStore,
    UnknownPage,
    check_transition,
)

S = IngestState
CHAIN = [S.DISCOVERED, S.FETCHED, S.PARSED, S.NORMALIZED, S.TRANSLATED, S.LOADED]
ALL_PAIRS = list(itertools.product(IngestState, IngestState))


def test_forward_chain_is_legal() -> None:
    for src, dst in itertools.pairwise(CHAIN):
        check_transition(src, dst)


@pytest.mark.parametrize(("src", "dst"), ALL_PAIRS)
def test_every_pair_matches_table(src: IngestState, dst: IngestState) -> None:
    if dst in TRANSITIONS[src]:
        check_transition(src, dst)
    else:
        with pytest.raises(IllegalTransition):
            check_transition(src, dst)


def test_all_pairs_count() -> None:
    assert len(ALL_PAIRS) == 49


@pytest.mark.parametrize("src", CHAIN[:-1])
def test_non_terminal_can_fail(src: IngestState) -> None:
    check_transition(src, S.FAILED)


def test_skips_backward_and_terminal_are_illegal() -> None:
    for src, dst in [
        (S.DISCOVERED, S.PARSED),
        (S.PARSED, S.FETCHED),
        (S.LOADED, S.DISCOVERED),
        (S.LOADED, S.FAILED),
        (S.FAILED, S.LOADED),
    ]:
        with pytest.raises(IllegalTransition):
            check_transition(src, dst)


T0 = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def make_store(path: Path) -> StateStore:
    return StateStore(path, now=lambda: T0)


def test_schema_version_and_parent_dir(tmp_path: Path) -> None:
    db = tmp_path / "a" / "b" / "ingest.db"
    make_store(db).close()
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_newer_db_is_refused(tmp_path: Path) -> None:
    db = tmp_path / "ingest.db"
    make_store(db).close()
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA user_version = 99")
    with pytest.raises(SchemaTooNew):
        make_store(db)


def test_upsert_is_idempotent_and_keeps_progress(tmp_path: Path) -> None:
    with make_store(tmp_path / "s.db") as store:
        assert store.upsert_discovered("u1", PageKind.CARD) is True
        store.advance("u1", S.FETCHED)
        assert store.upsert_discovered("u1", PageKind.CARD) is False
        assert store.get("u1").state is S.FETCHED


def test_advance_validates(tmp_path: Path) -> None:
    with make_store(tmp_path / "s.db") as store:
        store.upsert_discovered("u1", PageKind.SET)
        with pytest.raises(IllegalTransition):
            store.advance("u1", S.PARSED)
        with pytest.raises(IllegalTransition):
            store.advance("u1", S.FAILED)
        assert store.get("u1").state is S.DISCOVERED


def test_unknown_page(tmp_path: Path) -> None:
    with make_store(tmp_path / "s.db") as store:
        with pytest.raises(UnknownPage):
            store.get("nope")
        with pytest.raises(UnknownPage):
            store.advance("nope", S.FETCHED)


def test_clock_and_sha_are_stored(tmp_path: Path) -> None:
    with make_store(tmp_path / "s.db") as store:
        store.upsert_discovered("u1", PageKind.INDEX)
        store.advance("u1", S.FETCHED, content_sha256="abc")
        rec = store.get("u1")
        assert rec.content_sha256 == "abc"
        assert rec.updated_at == T0.isoformat()
        store.advance("u1", S.PARSED)
        assert store.get("u1").content_sha256 == "abc"


def test_iter_pending_and_counts(tmp_path: Path) -> None:
    with make_store(tmp_path / "s.db") as store:
        store.upsert_discovered("a", PageKind.CARD)
        store.upsert_discovered("b", PageKind.SET)
        store.advance("b", S.FETCHED)
        assert [r.url for r in store.iter_pending()] == ["a", "b"]
        assert [r.url for r in store.iter_pending(kind=PageKind.SET)] == ["b"]
        assert [r.url for r in store.iter_pending(state=S.DISCOVERED)] == ["a"]
        counts = store.counts()
        assert counts[S.DISCOVERED] == 1 and counts[S.FETCHED] == 1
        assert counts[S.LOADED] == 0


def test_failure_is_recorded(tmp_path: Path) -> None:
    with make_store(tmp_path / "s.db") as store:
        store.upsert_discovered("u", PageKind.CARD)
        store.advance("u", S.FETCHED)
        store.mark_failed("u", "boom")
        rec = store.get("u")
        assert rec.state is S.FAILED
        assert rec.failed_from is S.FETCHED
        assert rec.attempts == 1
        assert rec.last_error == "boom"
        assert rec.updated_at == T0.isoformat()
        with pytest.raises(IllegalTransition):
            store.mark_failed("u", "again")


def test_permanent_failure_is_exhausted_at_once(tmp_path: Path) -> None:
    with make_store(tmp_path / "s.db") as store:
        store.upsert_discovered("u", PageKind.CARD)
        store.mark_failed("u", "skipped: status 404", permanent=True)
        rec = store.get("u")
        assert rec.state is S.FAILED and rec.failed_from is S.DISCOVERED
        assert rec.attempts == store.max_attempts
        assert rec.last_error == "skipped: status 404"
        with pytest.raises(RetriesExhausted):
            store.retry("u")
        assert [r.url for r in store.iter_exhausted()] == ["u"]
        assert store.iter_pending() == []


def test_retry_returns_to_failed_from_and_success_resets_attempts(tmp_path: Path) -> None:
    with make_store(tmp_path / "s.db") as store:
        store.upsert_discovered("u", PageKind.CARD)
        store.advance("u", S.FETCHED)
        store.mark_failed("u", "x")
        store.retry("u")
        assert store.get("u").state is S.FETCHED
        store.advance("u", S.PARSED)
        rec = store.get("u")
        assert rec.attempts == 0 and rec.last_error is None and rec.failed_from is None


def test_retry_requires_failed(tmp_path: Path) -> None:
    with make_store(tmp_path / "s.db") as store:
        store.upsert_discovered("u", PageKind.CARD)
        with pytest.raises(IllegalTransition):
            store.retry("u")


def test_retry_after_max_attempts_raises(tmp_path: Path) -> None:
    with StateStore(tmp_path / "s.db", max_attempts=2, now=lambda: T0) as store:
        store.upsert_discovered("u", PageKind.CARD)
        for _ in range(2):
            store.mark_failed("u", "x")
            if store.get("u").attempts < 2:
                store.retry("u")
        with pytest.raises(RetriesExhausted):
            store.retry("u")
        assert [r.url for r in store.iter_exhausted()] == ["u"]
        assert store.iter_pending() == []
        assert store.counts()[S.FAILED] == 1


def test_later_run_sees_failed_row_as_retryable(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    with make_store(db) as run1:
        run1.upsert_discovered("u", PageKind.CARD)
        run1.mark_failed("u", "net")
    with make_store(db) as run2:
        pending = run2.iter_pending()
        assert [(r.url, r.state) for r in pending] == [("u", S.FAILED)]
        run2.retry("u")
        assert run2.get("u").state is S.DISCOVERED
        assert run2.iter_exhausted() == []


_KILL_SCRIPT = """
import os
import sys
from pathlib import Path

from bs_database.ingest.state import IngestState, PageKind, StateStore

store = StateStore(Path(sys.argv[1]))
for i in range(5):
    url = f"u{i}"
    store.upsert_discovered(url, PageKind.CARD)
    if i < 3:
        store.advance(url, IngestState.FETCHED)
        store.advance(url, IngestState.PARSED)
with store._tx() as conn:
    conn.execute("UPDATE pages SET state = 'fetched' WHERE url = 'u3'")
    os._exit(1)
"""


def test_resume_after_kill_does_not_redo_completed_pages(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    proc = subprocess.run(
        [sys.executable, "-I", "-c", _KILL_SCRIPT, str(db)],
        check=False,
        timeout=60,
    )
    assert proc.returncode == 1

    fetched: list[str] = []
    with make_store(db) as store:
        assert store.get("u3").state is S.DISCOVERED  # half-done update rolled back
        for rec in store.iter_pending(state=S.DISCOVERED):
            fetched.append(rec.url)
            store.advance(rec.url, S.FETCHED)
        assert [r.url for r in store.iter_pending(state=S.PARSED)] == ["u0", "u1", "u2"]
    assert fetched == ["u3", "u4"]


def test_advance_on_failed_row_raises_and_exhausted_stays_failed(tmp_path: Path) -> None:
    with StateStore(tmp_path / "s.db", max_attempts=1, now=lambda: T0) as store:
        store.upsert_discovered("u", PageKind.CARD)
        store.mark_failed("u", "x")
        with pytest.raises(IllegalTransition):
            store.advance("u", S.FETCHED)
        with pytest.raises(RetriesExhausted):
            store.retry("u")
        rec = store.get("u")
        assert rec.state is S.FAILED and rec.attempts == 1


def test_failed_migration_closes_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "s.db"
    make_store(db).close()
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA user_version = 99")
    closed: list[bool] = []
    real_connect = sqlite3.connect

    class Spy:
        def __init__(self, conn: sqlite3.Connection) -> None:
            self._c = conn

        def __getattr__(self, name: str) -> object:
            if name == "close":
                closed.append(True)
            return getattr(self._c, name)

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: Spy(real_connect(*a, **k)))
    with pytest.raises(SchemaTooNew):
        make_store(db)
    assert closed


def test_reset_failed_touches_only_matching_rows(tmp_path: Path) -> None:
    with make_store(tmp_path / "s.db") as store:
        for url in ("p", "gone", "other"):
            store.upsert_discovered(url, PageKind.CARD)
        for _ in range(store.max_attempts):
            store.mark_failed("p", "parse error: no card block")
            if store.get("p").attempts < store.max_attempts:
                store.retry("p")
        store.mark_failed("gone", "skipped: status 404", permanent=True)
        store.mark_failed("other", "transport error: timeout")
        assert store.reset_failed(prefix="parse error:") == 1
        assert store.get("p").attempts == 0 and store.get("p").state is S.FAILED
        assert store.get("gone").attempts == store.max_attempts
        assert store.get("other").attempts == 1
        assert [r.url for r in store.iter_exhausted()] == ["gone"]
        store.retry("p")
        assert store.get("p").state is S.DISCOVERED
        assert store.reset_failed(prefix="parse error:") == 0
