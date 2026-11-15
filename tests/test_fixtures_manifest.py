"""Consistency checks for the HTML fixture set and its manifest (``fixtures.json``)."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup

HTML = Path(__file__).parent / "fixtures" / "html"
MAX_FILE_BYTES = 300_000
MAX_TOTAL_BYTES = 2_500_000
NON_FIXTURES = {"fixtures.json", "README.md"}
REQUIRED = {"url", "fetched", "source", "kind", "trimmed"}
SOURCES = {"batspi", "synthetic"}
KINDS = {"card", "set", "list", "index", "image"}
CARD_TYPES = {"スピリット", "ネクサス", "マジック", "ブレイヴ", "アルティメット"}
CHALLENGE_MARKERS = ("Just a moment", "cf-chl", "challenge-platform", "cf-browser-verification")


def manifest() -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = json.loads((HTML / "fixtures.json").read_text("utf-8"))
    return data


def files() -> list[Path]:
    return sorted(p for p in HTML.iterdir() if p.name not in NON_FIXTURES)


def batspi_cards() -> list[str]:
    return sorted(
        n for n, e in manifest().items() if e["source"] == "batspi" and e["kind"] == "card"
    )


def test_files_and_manifest_match() -> None:
    assert {p.name for p in files()} == set(manifest())


@pytest.mark.parametrize("name", sorted(manifest()))
def test_entry_fields(name: str) -> None:
    entry = manifest()[name]
    assert set(entry) >= REQUIRED
    assert isinstance(entry["trimmed"], bool)
    assert entry["source"] in SOURCES
    assert entry["kind"] in KINDS
    date.fromisoformat(entry["fetched"])
    if entry["source"] == "batspi":
        assert entry["url"].startswith("https://batspi.com/")


def test_file_budget() -> None:
    too_big = {p.name: p.stat().st_size for p in files() if p.stat().st_size > MAX_FILE_BYTES}
    assert not too_big


def test_total_budget() -> None:
    assert sum(p.stat().st_size for p in files()) <= MAX_TOTAL_BYTES


@pytest.mark.parametrize(
    "name", sorted(n for n, e in manifest().items() if e["source"] == "batspi")
)
def test_no_challenge_page(name: str) -> None:
    text = (HTML / name).read_text(encoding="utf-8")
    assert not any(marker in text for marker in CHALLENGE_MARKERS)


@pytest.mark.parametrize("name", batspi_cards())
def test_card_first_pre_is_type(name: str) -> None:
    entry = manifest()[name]
    assert entry["card_type"] in CARD_TYPES
    soup = BeautifulSoup((HTML / name).read_text(encoding="utf-8"), "html.parser")
    pre = soup.find("pre")
    assert pre is not None
    first_line = pre.get_text().splitlines()[0].strip()
    assert first_line.startswith(entry["card_type"])
