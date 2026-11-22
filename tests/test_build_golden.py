"""Count golden and determinism of the build on the normalized goldens (#120)."""

import json
import sqlite3
from pathlib import Path

from build_support import (
    BUILD_GOLDEN,
    BUILD_REGEN_COMMAND,
    build,
    build_summary,
    golden_documents,
    query,
)


def _dump(path: Path, skip_meta: bool = True) -> list[str]:
    with sqlite3.connect(path) as conn:
        lines = list(conn.iterdump())
    return [ln for ln in lines if not (skip_meta and "schema_meta" in ln)]


def test_counts_match_the_golden(tmp_path: Path) -> None:
    expected = json.loads(BUILD_GOLDEN.read_text(encoding="utf-8"))
    actual = build_summary(tmp_path / "x.db")
    assert len(actual["tables"]) == 34
    assert actual == expected, f"build golden is stale; regenerate with: {BUILD_REGEN_COMMAND}"


def test_build_is_consistent(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    build(out, golden_documents())
    assert query(out, "PRAGMA foreign_key_check") == []
    assert query(out, "PRAGMA integrity_check") == [("ok",)]
    assert query(out, "PRAGMA user_version") == [(100,)]


def test_two_builds_have_the_same_dump(tmp_path: Path) -> None:
    build(tmp_path / "a.db", golden_documents(), built_at=None)
    build(tmp_path / "b.db", golden_documents(), built_at=None)
    assert _dump(tmp_path / "a.db") == _dump(tmp_path / "b.db")


def test_fixed_built_at_gives_identical_files(tmp_path: Path) -> None:
    build(tmp_path / "a.db", golden_documents(), built_at="2026-01-01T00:00:00+00:00")
    build(tmp_path / "b.db", golden_documents(), built_at="2026-01-01T00:00:00+00:00")
    assert (tmp_path / "a.db").read_bytes() == (tmp_path / "b.db").read_bytes()


def test_document_order_does_not_change_the_dump(tmp_path: Path) -> None:
    build(tmp_path / "a.db", golden_documents())
    build(tmp_path / "b.db", golden_documents()[::-1])
    assert _dump(tmp_path / "a.db") == _dump(tmp_path / "b.db")
    assert (tmp_path / "a.db").read_bytes() == (tmp_path / "b.db").read_bytes()
