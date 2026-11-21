"""Smoke tests for schema.sql (#119) and its consistency with the ER documentation."""

import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from bs_database.schema import load_schema_sql

TARGET_SCHEMA = Path(__file__).parent.parent / "docs" / "data-model" / "target-schema.md"
NAME_PATTERN = re.compile(r"^(pk|fk|uq|ck|ix)_[a-z0-9_]+$")


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(load_schema_sql())
    yield connection
    connection.close()


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {r[0] for r in rows if not r[0].startswith("sqlite_")}


def _columns(conn: sqlite3.Connection, table: str) -> dict[str, tuple[str, int]]:
    """Map column name to (declared type, notnull)."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1]: (r[2], r[3]) for r in rows}


def _er_entities() -> list[set[str]]:
    """Entity names of every erDiagram block of target-schema.md."""
    text = TARGET_SCHEMA.read_text(encoding="utf-8")
    blocks = re.findall(r"```mermaid\n(erDiagram\n.*?)```", text, flags=re.S)
    return [set(re.findall(r"^    (\w+) \{$", block, flags=re.M)) for block in blocks]


def test_loads_and_is_consistent(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert conn.execute("PRAGMA user_version").fetchone() == (100,)


def test_seeds_present(conn: sqlite3.Connection) -> None:
    def codes(table: str) -> list[tuple[int, str]]:
        return conn.execute(f"SELECT id, code FROM {table} ORDER BY id").fetchall()

    assert codes("translation_statuses") == [
        (1, "pending"),
        (2, "machine"),
        (3, "reviewed"),
        (4, "failed"),
    ]
    assert [c for _, c in codes("translation_sources")] == [
        "batspi",
        "official",
        "fandom",
        "manual",
        "machine",
    ]
    assert codes("variants") == [(1, "normal")]
    assert codes("sources") == [(1, "batspi")]
    assert codes("image_sizes") == [(1, "small"), (2, "large")]


def test_glossary_lookups_not_seeded(conn: sqlite3.Connection) -> None:
    for table in ("colors", "card_types", "rarities", "product_types", "families", "keywords"):
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)


def test_constraint_and_index_names(conn: sqlite3.Connection) -> None:
    sql = load_schema_sql()
    constraint_names = re.findall(r"CONSTRAINT (\w+)", sql)
    assert constraint_names
    index_names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"
        )
    ]
    assert index_names
    assert set(re.findall(r"CREATE (?:UNIQUE )?INDEX (\w+)", sql)) == set(index_names)
    for name in constraint_names + index_names:
        assert NAME_PATTERN.match(name), name
    assert len(set(constraint_names)) == len(constraint_names)
    # Every constraint is named: no anonymous PRIMARY KEY / UNIQUE / CHECK / FOREIGN KEY.
    for table in _tables(conn):
        row = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()
        body = row[0]
        stripped = re.sub(r"CONSTRAINT \w+ (PRIMARY KEY|UNIQUE|CHECK|FOREIGN KEY)", "", body)
        assert not re.search(r"\b(PRIMARY KEY|FOREIGN KEY|UNIQUE)\b", stripped), table


def test_constraint_name_matches_table(conn: sqlite3.Connection) -> None:
    for table in _tables(conn):
        row = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()
        for name in re.findall(r"CONSTRAINT (\w+)", row[0]):
            assert name.split("_", 1)[1].startswith(table), (table, name)


def test_tables_match_er_diagrams(conn: sqlite3.Connection) -> None:
    diagrams = _er_entities()
    assert len(diagrams) >= 2
    complete = diagrams[0]
    # schema_meta is drawn in the complete diagram (without relationships), so nothing is excluded.
    assert "schema_meta" in complete
    assert _tables(conn) == complete
    for partial in diagrams[1:]:
        assert partial <= complete


def test_adr_0010_columns(conn: sqlite3.Connection) -> None:
    assert _columns(conn, "cards")["card_class_jp"] == ("TEXT", 0)
    assert _columns(conn, "cards")["type_mark_jp"] == ("TEXT", 0)
    levels = _columns(conn, "card_levels")
    assert levels["count_condition_jp"] == ("TEXT", 0)
    assert levels["note_jp"] == ("TEXT", 0)
    assert levels["cores"] == ("INTEGER", 0)
    symbols = _columns(conn, "card_symbols")
    assert symbols["variant_jp"] == ("TEXT", 0)
    assert symbols["color_jp"] == ("TEXT", 0)
    assert _columns(conn, "card_credits") == {
        "id": ("INTEGER", 1),
        "card_id": ("INTEGER", 1),
        "position": ("INTEGER", 1),
        "role_jp": ("TEXT", 1),
        "name": ("TEXT", 1),
        "note": ("TEXT", 0),
    }


def test_card_credits_cascade_and_unique(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO card_types (id, code, name) VALUES (1, 'spirit', 'Spirit')")
    conn.execute("INSERT INTO cards (id, card_type_id, cost, name_jp) VALUES (1, 1, 1, 'x')")
    conn.execute(
        "INSERT INTO card_credits (card_id, position, role_jp, name) VALUES (1, 1, 'r', 'n')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO card_credits (card_id, position, role_jp, name) VALUES (1, 1, 'r', 'm')"
        )
    conn.execute("DELETE FROM cards WHERE id = 1")
    assert conn.execute("SELECT count(*) FROM card_credits").fetchone() == (0,)


def test_samples_load_against_schema(conn: sqlite3.Connection) -> None:
    text = (TARGET_SCHEMA.parent / "samples.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```sql\n(.*?)```", text, flags=re.S)
    assert blocks
    for block in blocks:
        conn.executescript(block)
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
