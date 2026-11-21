"""Access to the packaged SQLite schema (ADR 0011: schema.sql is the single source)."""

from importlib.resources import files


def load_schema_sql() -> str:
    """Return the full DDL and lookup seeds of ``schema.sql`` as text."""
    return files("bs_database").joinpath("schema.sql").read_text(encoding="utf-8")
