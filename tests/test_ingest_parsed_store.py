"""Parsed card JSON store (#73)."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bs_database.ingest import parsed_store
from bs_database.ingest.atomic import atomic_write
from bs_database.ingest.cache import CachedPage, RawCache
from bs_database.ingest.parsed_store import parsed_path, read_card_json, write_card_json
from bs_database.parsers.batspi.card import parse_card_page

HTML_DIR = Path(__file__).parent / "fixtures" / "html"
MANIFEST = json.loads((HTML_DIR / "fixtures.json").read_text(encoding="utf-8"))
WHEN = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


def _cached(name: str = "card_spirit.html", *, from_cache: bool = True) -> CachedPage:
    url = MANIFEST[name]["url"]
    content = (HTML_DIR / name).read_bytes()
    return CachedPage(url, "batspi", content, 200, WHEN, from_cache)


def test_name_is_the_cache_stem(tmp_path: Path) -> None:
    cached = _cached()
    html, _ = RawCache(tmp_path / "c").paths(cached.url, "batspi")
    path = parsed_path(tmp_path / "p", "batspi", cached.url)
    assert path.stem == html.stem == hashlib.sha256(cached.url.encode()).hexdigest()
    assert path == tmp_path / "p" / "batspi" / f"{path.stem}.json"


def test_content_and_provenance(tmp_path: Path) -> None:
    cached = _cached()
    page = parse_card_page(cached.text, cached.url)
    path = write_card_json(tmp_path, page, cached)
    raw = path.read_text(encoding="utf-8")
    assert "光爪の武芸者" in raw  # ensure_ascii=False
    doc = read_card_json(path)
    assert doc["schema_version"] == page.schema_version
    assert doc["url"] == cached.url
    assert doc["provenance"] == {
        "source": "batspi",
        "fetched_at": "2026-11-15T12:00:00+00:00",
        "from_cache": True,
    }
    assert doc["page"]["title_jp"] == page.title_jp
    assert doc["page"]["url"] == cached.url
    assert len(doc["page"]["entries"]) == len(page.entries)


def test_provenance_records_network_read(tmp_path: Path) -> None:
    cached = _cached(from_cache=False)
    page = parse_card_page(cached.text, cached.url)
    doc = read_card_json(write_card_json(tmp_path, page, cached))
    assert doc["provenance"]["from_cache"] is False


def test_round_trip_back_to_the_url(tmp_path: Path) -> None:
    cached = _cached("card_nexus.html")
    page = parse_card_page(cached.text, cached.url)
    path = write_card_json(tmp_path, page, cached)
    assert read_card_json(path)["url"] == cached.url
    assert parsed_path(tmp_path, "batspi", read_card_json(path)["url"]) == path


def test_no_temp_file_left(tmp_path: Path) -> None:
    cached = _cached()
    page = parse_card_page(cached.text, cached.url)
    write_card_json(tmp_path, page, cached)
    assert [p.suffix for p in (tmp_path / "batspi").iterdir()] == [".json"]


def test_failing_write_keeps_the_old_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cached = _cached()
    page = parse_card_page(cached.text, cached.url)
    path = write_card_json(tmp_path, page, cached)
    before = path.read_bytes()

    def boom(target: Path, data: bytes) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(parsed_store, "atomic_write", boom)
    with pytest.raises(OSError, match="disk full"):
        write_card_json(tmp_path, page, cached)
    assert path.read_bytes() == before


def test_atomic_write_removes_temp_on_failure(tmp_path: Path) -> None:
    target = tmp_path / "missing" / "f.json"  # parent does not exist: open fails
    with pytest.raises(OSError):
        atomic_write(target, b"x")
    assert list(tmp_path.rglob("*.tmp")) == []
