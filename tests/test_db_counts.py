"""Tests for the ``tests/tools/db_counts.py`` helper."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).parent / "tools" / "db_counts.py"


def test_counts_per_table(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE b (id INTEGER)")
        conn.execute("CREATE TABLE a (id INTEGER)")
        conn.executemany("INSERT INTO a VALUES (?)", [(1,), (2,)])
    out = subprocess.run(
        [sys.executable, str(TOOL), str(db)], capture_output=True, text=True, check=True
    )
    assert json.loads(out.stdout) == {"a": 2, "b": 0}


def test_missing_file(tmp_path: Path) -> None:
    out = subprocess.run(
        [sys.executable, str(TOOL), str(tmp_path / "nope.db")], capture_output=True
    )
    assert out.returncode == 1
