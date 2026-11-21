"""Skeleton of the build (#120): lookups from the glossary and the atomic fresh output."""

import sqlite3
from pathlib import Path

import pytest
from golden_support import real_glossary

from bs_database import __version__
from bs_database.build import BuildError, build_database
from bs_database.build.builder import schema_version_text, source_snapshot, utc_timestamp
from bs_database.build.reader import Document
from bs_database.normalize.records import NORMALIZED_SCHEMA_VERSION


def _rows(path: Path, sql: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as conn:
        return conn.execute(sql).fetchall()


def test_lookups_come_from_the_glossary(tmp_path: Path) -> None:
    result = build_database(
        tmp_path / "x.db", real_glossary(), built_at="2026-01-01T00:00:00+00:00"
    )
    counts = result.table_counts
    assert len(counts) == 34
    assert counts["colors"] == 6
    assert counts["card_types"] == 5
    assert counts["rarities"] == 32
    assert counts["product_types"] == 8
    assert counts["variants"] == 4
    assert counts["keywords"] == 320
    assert counts["families"] == 313
    assert counts["symbols"] == 9
    assert counts["effect_kinds"] == 7
    assert counts["schema_meta"] == 1


def test_seeded_ids_are_kept(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    build_database(out, real_glossary())
    assert _rows(out, "SELECT id FROM variants WHERE code = 'normal'") == [(1,)]
    assert _rows(out, "SELECT code FROM variants ORDER BY id")[0] == ("normal",)
    assert _rows(out, "SELECT id FROM translation_statuses WHERE code = 'pending'") == [(1,)]
    # symbol colours point to the colour lookup, the god symbol has none
    assert _rows(out, "SELECT color_id FROM symbols WHERE code = 'god'") == [(None,)]
    assert _rows(
        out, "SELECT c.code FROM symbols s JOIN colors c ON c.id = s.color_id WHERE s.code = 'red'"
    ) == [("red",)]


def test_schema_meta_and_checks(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    build_database(out, real_glossary(), built_at="2026-01-01T00:00:00+00:00")
    ((version, data, built, snapshot, generator),) = _rows(
        out,
        "SELECT schema_version, data_version, built_at, source_snapshot, generator"
        " FROM schema_meta",
    )
    assert (version, data, built, snapshot) == ("0.1.0", "dev", "2026-01-01T00:00:00Z", None)
    assert generator == __version__
    assert _rows(out, "PRAGMA foreign_key_check") == []
    assert _rows(out, "PRAGMA user_version") == [(100,)]


def test_schema_version_text() -> None:
    assert schema_version_text(10200) == "1.2.0"
    assert schema_version_text(307) == "0.3.7"


def test_output_is_fresh_not_appended(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    out.write_bytes(b"not a database")
    build_database(out, real_glossary())
    build_database(out, real_glossary())
    assert _rows(out, "SELECT count(*) FROM schema_meta") == [(1,)]
    assert not list(tmp_path.glob("*.tmp"))


def test_error_keeps_the_old_file_and_removes_the_temp(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    build_database(out, real_glossary(), built_at="2026-01-01T00:00:00Z")
    before = out.read_bytes()

    def boom(*_: object) -> None:
        raise BuildError("boom")

    with pytest.raises(BuildError):
        build_database(out, real_glossary(), built_at="2026-01-02T00:00:00Z", load=boom)
    assert out.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_foreign_key_violation_is_an_error(tmp_path: Path) -> None:
    def bad(conn: sqlite3.Connection, *_: object) -> None:
        conn.execute("PRAGMA defer_foreign_keys = ON")
        conn.execute("INSERT INTO card_numbers (number, card_id) VALUES ('A-1', 99)")

    with pytest.raises(BuildError, match="foreign key"):
        build_database(tmp_path / "x.db", real_glossary(), load=bad)
    assert not (tmp_path / "x.db").exists()


def test_user_version_formula_round_trips() -> None:
    # ADR 0003: user_version = major * 10000 + minor * 100 + patch
    for text, number in (("1.2.0", 10200), ("0.3.7", 307), ("0.1.0", 100)):
        major, minor, patch = (int(p) for p in text.split("."))
        assert major * 10000 + minor * 100 + patch == number
        assert schema_version_text(number) == text


def test_utc_timestamp_has_a_z_suffix() -> None:
    assert utc_timestamp("2026-11-21T11:35:20+01:00") == "2026-11-21T10:35:20Z"
    assert utc_timestamp("2026-11-21T10:35:20") == "2026-11-21T10:35:20Z"
    assert utc_timestamp().endswith("Z")


def _doc(fetched_at: str, url: str) -> Document:
    return Document(
        url=url,
        source="batspi",
        fetched_at=fetched_at,
        parsed_schema_version="2.1.0",
        path=Path("x.json"),
        page={},
    )


def test_source_snapshot_is_the_fetch_date_range() -> None:
    docs = [_doc("2026-11-16T09:00:00Z", "b"), _doc("2026-11-15T20:52:00Z", "a")]
    assert source_snapshot(docs) == (
        f"batspi 2026-11-15..2026-11-16; 2 pages; normalized {NORMALIZED_SCHEMA_VERSION}"
    )
    assert source_snapshot([]) is None


def test_data_version_is_written(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    build_database(out, real_glossary(), data_version="v0.5.0")
    assert _rows(out, "SELECT data_version FROM schema_meta") == [("v0.5.0",)]
