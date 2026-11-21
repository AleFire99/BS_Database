"""Tests.

Goldens in tests/goldens/ were generated from the legacy code at 5ae5646
(legacy code removed in #23; see tag v0.1.0).
"""

import json
import logging
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from bs_database.db import (
    Base,
    Card,
    build_db,
    get_colors_from_symbol,
    insert_card,
    load_json_cards,
)

GOLDENS = Path(__file__).parent / "goldens"
LEGACY_JSON = Path(__file__).parent / "fixtures" / "legacy" / "card_json"


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((GOLDENS / "db.json").read_text(encoding="utf-8"))
    return data


@pytest.fixture
def built(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> sqlite3.Connection:
    with caplog.at_level(logging.WARNING, logger="bs_database.db"):
        build_db(LEGACY_JSON, tmp_path / "out.db")
    con = sqlite3.connect(tmp_path / "out.db")
    return con


def test_ddl_matches_legacy(built: sqlite3.Connection, golden: dict[str, Any]) -> None:
    rows = built.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    assert dict(rows) == golden["ddl"]


def test_counts_and_name_sets(built: sqlite3.Connection, golden: dict[str, Any]) -> None:
    for table, count in golden["counts"].items():
        assert built.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == count, table
    for table in ("card_types", "colors", "families"):
        names = sorted(r[0] for r in built.execute(f"SELECT name FROM {table}"))
        assert names == golden[f"{table}_names"], table


def test_per_card_relations(built: sqlite3.Connection, golden: dict[str, Any]) -> None:
    got: dict[str, Any] = {}
    for pk, name, card_id, cost, symbol, image, type_name in built.execute(
        "SELECT c.id, c.name, c.card_id, c.cost, c.symbol, c.image, t.name "
        "FROM cards c LEFT JOIN card_types t ON t.id = c.type_id"
    ):
        got[card_id] = {
            "name": name,
            "cost": cost,
            "symbol": symbol,
            "image": image,
            "type": type_name,
            "families": sorted(
                r[0]
                for r in built.execute(
                    "SELECT f.name FROM card_families cf JOIN families f ON f.id = cf.family_id "
                    "WHERE cf.card_id = ?",
                    (pk,),
                )
            ),
            "colors": sorted(
                r[0]
                for r in built.execute(
                    "SELECT c.name FROM card_colors cc JOIN colors c ON c.id = cc.color_id "
                    "WHERE cc.card_id = ?",
                    (pk,),
                )
            ),
            "core_requirements": sorted(
                list(r)
                for r in built.execute(
                    "SELECT level, battlePoints, cores FROM core_requirements WHERE card_id = ?",
                    (pk,),
                )
            ),
        }
    assert got == golden["cards"]


def test_duplicate_card_id_inserted_once_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "cards"
    root.mkdir()
    card = {"name": "A", "card_id": "X-1", "type": "Spirit", "cost": 1, "symbol": "Red"}
    (root / "a.json").write_text(json.dumps(card), encoding="utf-8")
    (root / "b.json").write_text(json.dumps(card), encoding="utf-8")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session, caplog.at_level(logging.WARNING, logger="bs_database.db"):
        load_json_cards(root, session)
        assert session.query(Card).count() == 1
        first = session.query(Card).one()
        assert insert_card(card, session) is first
    assert "already exists" in caplog.text


def test_invalid_json_raises(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        build_db(tmp_path, tmp_path / "x.db")


def test_get_colors_from_symbol() -> None:
    assert get_colors_from_symbol("PURPLE") == ["Purple"]
    assert get_colors_from_symbol("Rainbow") == []


def test_build_db_does_not_mutate_input(tmp_path: Path) -> None:
    src = tmp_path / "in"
    shutil.copytree(LEGACY_JSON, src)
    build_db(src, tmp_path / "o.db")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in", "o.db"]


def test_import_touches_no_files(tmp_path: Path) -> None:
    code = "import os, bs_database.db; print(sorted(os.listdir('.')))"
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]"
