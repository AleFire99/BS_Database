"""Tests for the ingestion state machine and store (#72)."""

from __future__ import annotations

import itertools
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bs_database.ingest.state import (
    TRANSITIONS,
    IllegalTransition,
    IngestState,
    PageKind,
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
