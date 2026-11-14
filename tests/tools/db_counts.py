"""Print per-table row counts of a SQLite file as JSON.

Usage: ``uv run python tests/tools/db_counts.py <db>``
"""

import json
import sqlite3
import sys
from pathlib import Path


def table_counts(db: Path) -> dict[str, int]:
    """Return ``{table: row count}`` for every user table, sorted by table name."""
    uri = f"{db.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            name: int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
            for name in names
        }
    finally:
        conn.close()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: db_counts.py <db>", file=sys.stderr)
        return 2
    db = Path(argv[1])
    if not db.is_file():
        print(f"error: no such file: {db}", file=sys.stderr)
        return 1
    print(json.dumps(table_counts(db), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
