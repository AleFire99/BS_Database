"""Review inputs and the legacy family vote (#96), on a tiny in-test SQLite snapshot."""

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from bs_database.normalize.records import NORMALIZED_SCHEMA_VERSION
from bs_database.review.legacy import FamilyLink, link_families
from bs_database.review.source import (
    ReviewError,
    iter_pages,
    load_legacy_families,
)

LEGACY_SCHEMA = """
CREATE TABLE cards (id INTEGER PRIMARY KEY, name TEXT, card_id TEXT UNIQUE);
CREATE TABLE families (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE card_families (card_id INTEGER, family_id INTEGER, PRIMARY KEY (card_id, family_id));
"""


def make_legacy(path: Path, cards: dict[str, list[str]]) -> Path:
    """Build a v0.1.0-shaped snapshot: ``{card_id: [family names]}``."""
    connection = sqlite3.connect(path)
    connection.executescript(LEGACY_SCHEMA)
    family_ids: dict[str, int] = {}
    for card_pk, (number, names) in enumerate(cards.items(), start=1):
        connection.execute("INSERT INTO cards VALUES (?, ?, ?)", (card_pk, "x", number))
        for name in names:
            fid = family_ids.setdefault(name, len(family_ids) + 1)
            connection.execute("INSERT OR IGNORE INTO families VALUES (?, ?)", (fid, name))
            connection.execute("INSERT INTO card_families VALUES (?, ?)", (card_pk, fid))
    connection.commit()
    connection.close()
    return path


def write_page(
    directory: Path, stem: str, entries: list[dict[str, Any]], *, version: str | None = None
) -> Path:
    target = directory / "batspi" / f"{stem}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": version or NORMALIZED_SCHEMA_VERSION,
        "page": {"entries": entries, "printings": []},
    }
    target.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return target


def entry(number: str, *families: str) -> dict[str, Any]:
    return {"number": number, "gameplay": {"families": [{"jp": f} for f in families]}}


def test_load_legacy_families_groups_by_card(tmp_path: Path) -> None:
    db = make_legacy(tmp_path / "legacy.db", {"BS01-001": ["Rebirth", "Flood"], "BS01-002": []})
    assert load_legacy_families(db) == {"BS01-001": ("Flood", "Rebirth")}


def test_load_legacy_families_errors(tmp_path: Path) -> None:
    with pytest.raises(ReviewError, match="not found"):
        load_legacy_families(tmp_path / "missing.db")
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    with pytest.raises(ReviewError, match="cannot read legacy database"):
        load_legacy_families(empty)


def test_iter_pages_checks_schema_and_directory(tmp_path: Path) -> None:
    with pytest.raises(ReviewError, match="not found"):
        list(iter_pages(tmp_path / "nope"))
    write_page(tmp_path, "a", [entry("N-1", "爬獣")])
    assert [p["entries"][0]["number"] for p in iter_pages(tmp_path)] == ["N-1"]
    write_page(tmp_path, "b", [], version="1.0.0")
    with pytest.raises(ReviewError, match="schema_version '1.0.0'"):
        list(iter_pages(tmp_path))


def test_iter_pages_rejects_unreadable_file(tmp_path: Path) -> None:
    (tmp_path / "batspi").mkdir()
    (tmp_path / "batspi" / "x.json").write_text("{", encoding="utf-8")
    with pytest.raises(ReviewError, match="cannot read"):
        list(iter_pages(tmp_path))


def test_report_files_outside_the_glob_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "_report.json").write_text("{}", encoding="utf-8")
    assert list(iter_pages(tmp_path)) == []


def test_one_to_one_votes_are_strong_with_votes_and_share() -> None:
    cards = {f"N-{i}": frozenset({"爬獣"}) for i in range(5)}
    legacy = {f"N-{i}": ("Rebirth",) for i in range(4)}
    legacy["N-4"] = ("Flood",)
    link = link_families(cards, legacy).links["爬獣"]
    assert link.candidates == (("Rebirth", 4), ("Flood", 1))
    assert link.total == 5
    assert link.best == ("Rebirth", 4)
    assert link.strong


def test_below_share_or_votes_is_weak() -> None:
    cards = {f"N-{i}": frozenset({"A"}) for i in range(6)}
    legacy = {f"N-{i}": ("x",) for i in range(4)}
    legacy |= {"N-4": ("y",), "N-5": ("y",)}
    assert not link_families(cards, legacy).links["A"].strong  # 4 of 6 is 66%
    assert not link_families({"N-1": frozenset({"B"})}, {"N-1": ("z",)}).links["B"].strong


def test_ties_are_weak_and_sorted_by_name() -> None:
    cards = {f"N-{i}": frozenset({"A"}) for i in range(4)}
    legacy = {"N-0": ("b",), "N-1": ("b",), "N-2": ("a",), "N-3": ("a",)}
    link = link_families(cards, legacy).links["A"]
    assert link.candidates == (("a", 2), ("b", 2))
    assert not link.strong


def test_multi_family_cards_do_not_vote_and_unmatched_are_listed() -> None:
    cards = {
        "N-1": frozenset({"A", "B"}),
        "N-2": frozenset({"A"}),
        "N-3": frozenset({"A"}),
        "N-4": frozenset(),
        "N-9": frozenset({"C"}),
    }
    legacy = {"N-1": ("x", "y"), "N-2": ("x", "y"), "N-3": ("x",), "N-4": ("x",)}
    result = link_families(cards, legacy)
    assert result.links == {"A": FamilyLink("A", (("x", 1),))}
    assert result.unmatched == ("N-9",)
