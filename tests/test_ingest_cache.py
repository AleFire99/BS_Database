import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bs_database.ingest.cache import RawCache

URL = "https://batspi.com/index.php?%E3%82%AB%E3%83%BC%E3%83%89"
WHEN = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


def test_layout_and_sidecar(tmp_path: Path) -> None:
    cache = RawCache(tmp_path)
    cache.store(URL, "batspi", b"<html>", {"ETag": "x", "last-modified": "Mon"}, fetched_at=WHEN)
    stem = hashlib.sha256(URL.encode()).hexdigest()
    assert (tmp_path / "batspi" / f"{stem}.html").read_bytes() == b"<html>"
    meta = json.loads((tmp_path / "batspi" / f"{stem}.json").read_text())
    assert meta == {
        "url": URL,
        "fetched_at": "2026-11-15T12:00:00+00:00",
        "status": 200,
        "etag": "x",
        "last_modified": "Mon",
    }
    assert [p.name for p in (tmp_path / "batspi").iterdir()].count(f"{stem}.html") == 1


def test_missing_headers_are_null_and_default_time_is_utc(tmp_path: Path) -> None:
    cache = RawCache(tmp_path)
    page = cache.store(URL, "batspi", b"a", {})
    _, sidecar = cache.paths(URL, "batspi")
    meta = json.loads(sidecar.read_text())
    assert meta["etag"] is None and meta["last_modified"] is None
    assert page.fetched_at.utcoffset() is not None
    assert datetime.fromisoformat(meta["fetched_at"]) == page.fetched_at


def test_round_trip_bytes_including_non_utf8(tmp_path: Path) -> None:
    cache = RawCache(tmp_path)
    raw = b"\xff\xfe\x00bad\x82\xa0"
    cache.store(URL, "batspi", raw, {"ETag": "e"}, fetched_at=WHEN)
    page = cache.load(URL, "batspi")
    assert page is not None
    assert page.content == raw
    assert page.from_cache and page.status == 200
    assert page.fetched_at == WHEN
    assert page.etag == "e" and page.last_modified is None
    assert "�" in page.text


def test_sources_are_separate(tmp_path: Path) -> None:
    cache = RawCache(tmp_path)
    cache.store(URL, "batspi", b"a", {})
    assert cache.load(URL, "fandom") is None


def test_orphan_html_is_a_miss(tmp_path: Path) -> None:
    cache = RawCache(tmp_path)
    cache.store(URL, "batspi", b"a", {})
    cache.paths(URL, "batspi")[1].unlink()
    assert cache.load(URL, "batspi") is None


@pytest.mark.parametrize(
    "sidecar",
    [
        "not json",
        "[]",
        '{"url": "%URL%", "fetched_at": "nope", "status": 200}',
        '{"url": "%URL%", "status": 200}',
        '{"url": "other", "fetched_at": "2026-11-15T12:00:00+00:00", "status": 200}',
        '{"url": "%URL%", "fetched_at": "2026-11-15T12:00:00+00:00", "status": 404}',
        '{"url": "%URL%", "fetched_at": "2026-11-15T12:00:00+00:00", "status": 200, "etag": 5}',
    ],
)
def test_bad_sidecar_is_a_miss(tmp_path: Path, sidecar: str) -> None:
    cache = RawCache(tmp_path)
    cache.store(URL, "batspi", b"a", {})
    cache.paths(URL, "batspi")[1].write_text(sidecar.replace("%URL%", URL))
    assert cache.load(URL, "batspi") is None


def test_sidecar_without_html_is_a_miss(tmp_path: Path) -> None:
    cache = RawCache(tmp_path)
    cache.store(URL, "batspi", b"a", {})
    cache.paths(URL, "batspi")[0].unlink()
    assert cache.load(URL, "batspi") is None


def test_stray_tmp_files_are_ignored(tmp_path: Path) -> None:
    cache = RawCache(tmp_path)
    html, _ = cache.paths(URL, "batspi")
    html.parent.mkdir(parents=True)
    (html.parent / f"{html.name}.123.tmp").write_bytes(b"partial")
    assert cache.load(URL, "batspi") is None


def _fail_on(monkeypatch: pytest.MonkeyPatch, suffix: str) -> None:
    real = os.replace

    def replace(src: str | Path, dst: str | Path) -> None:
        if str(dst).endswith(suffix):
            raise OSError("boom")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)


def test_crash_before_sidecar_leaves_orphan_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = RawCache(tmp_path)
    _fail_on(monkeypatch, ".json")
    with pytest.raises(OSError):
        cache.store(URL, "batspi", b"a", {})
    html, sidecar = cache.paths(URL, "batspi")
    assert html.exists() and not sidecar.exists()
    assert cache.load(URL, "batspi") is None


def test_crash_on_html_leaves_no_entry_and_drops_old_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = RawCache(tmp_path)
    cache.store(URL, "batspi", b"old", {})
    _fail_on(monkeypatch, ".html")
    with pytest.raises(OSError):
        cache.store(URL, "batspi", b"new", {})
    assert cache.load(URL, "batspi") is None
    assert not cache.paths(URL, "batspi")[1].exists()
