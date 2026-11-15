import hashlib
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from bs_database.ingest.cache import CachedFetcher, CachedPage, RawCache
from bs_database.ingest.http import Blocked, Fetched, HttpClient, HttpResponse, Skipped
from bs_database.ingest.policy import local_check
from bs_database.settings import Settings

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


# --- CachedFetcher -------------------------------------------------------------------------

BASE = "https://batspi.com/"
ROBOTS_URL = f"{BASE}robots.txt"
PAGE = f"{BASE}index.php?%E3%82%AB"


class FakeFetcher:
    def __init__(self, result: Fetched | Skipped | Exception | None = None) -> None:
        self.result = result
        self.fetches = 0
        self.gates = 0

    def local_gate(self, url: str) -> Skipped | None:
        self.gates += 1
        reason = local_check(url)
        return Skipped(url, reason) if reason else None

    def allowed(self, url: str) -> Skipped | None:  # pragma: no cover
        raise AssertionError("allowed() must not be used by the cache")

    def fetch(self, url: str) -> Fetched | Skipped:
        self.fetches += 1
        result = self.result or Fetched(url, 200, b"body", {"ETag": "x"})
        if isinstance(result, Exception):
            raise result
        return result


class Clock:
    def __init__(self) -> None:
        self.t = WHEN

    def __call__(self) -> datetime:
        return self.t


class NoSleepClock:
    def monotonic(self) -> float:
        return 0.0

    def sleep(self, seconds: float) -> None:
        pass


class ScriptedTransport:
    def __init__(self, script: Mapping[str, HttpResponse]) -> None:
        self.script = script
        self.calls: list[str] = []

    def get(
        self, url: str, *, headers: Mapping[str, str], timeout: tuple[float, float]
    ) -> HttpResponse:
        self.calls.append(url)
        return self.script[url]


def make(
    tmp_path: Path,
    fetcher: FakeFetcher,
    *,
    refresh: bool = False,
    max_age: timedelta | None = None,
) -> tuple[CachedFetcher, Clock]:
    clock = Clock()
    cf = CachedFetcher(fetcher, RawCache(tmp_path), refresh=refresh, max_age=max_age, now=clock)
    return cf, clock


def test_warm_cache_makes_no_fetch(tmp_path: Path) -> None:
    fake = FakeFetcher()
    cf, _ = make(tmp_path, fake)
    first = cf.get(PAGE)
    second = cf.get(PAGE)
    assert isinstance(first, CachedPage) and isinstance(second, CachedPage)
    assert fake.fetches == 1
    assert not first.from_cache and second.from_cache
    assert first.content == second.content == b"body"
    assert first.fetched_at == second.fetched_at == WHEN
    assert second.etag == "x"


def test_warm_cache_with_real_client_makes_zero_transport_calls(tmp_path: Path) -> None:
    transport = ScriptedTransport(
        {
            ROBOTS_URL: HttpResponse(200, {}, b"User-agent: *\nDisallow: /index.php/\n"),
            PAGE: HttpResponse(200, {"ETag": "e"}, b"<html>"),
        }
    )
    client = HttpClient(Settings(data_dir=tmp_path), transport=transport, clock=NoSleepClock())
    cf = CachedFetcher(client, RawCache(tmp_path / "c"))
    cold = cf.get(PAGE)
    assert isinstance(cold, CachedPage) and not cold.from_cache
    assert [u for u in transport.calls] == [ROBOTS_URL, PAGE]
    warm_client = HttpClient(Settings(data_dir=tmp_path), transport=transport, clock=NoSleepClock())
    warm = CachedFetcher(warm_client, RawCache(tmp_path / "c")).get(PAGE)
    assert isinstance(warm, CachedPage) and warm.from_cache and warm.content == b"<html>"
    assert len(transport.calls) == 2  # nothing new, robots.txt included
    assert warm_client.requests_made == 0


def test_local_gate_applies_on_warm_cache(tmp_path: Path) -> None:
    fake = FakeFetcher()
    cf, _ = make(tmp_path, fake)
    denied = f"{BASE}index.php?cmd=x"
    RawCache(tmp_path).store(denied, "batspi", b"a", {})  # even if it somehow is cached
    result = cf.get(denied)
    assert isinstance(result, Skipped) and "deny list" in result.reason
    off = cf.get("https://example.com/")
    assert isinstance(off, Skipped) and "off-site" in off.reason
    assert fake.fetches == 0


def test_refresh_refetches_and_rewrites_fetched_at(tmp_path: Path) -> None:
    fake = FakeFetcher()
    cf, clock = make(tmp_path, fake, refresh=True)
    cf.get(PAGE)
    clock.t = WHEN + timedelta(days=1)
    page = cf.get(PAGE)
    assert isinstance(page, CachedPage) and not page.from_cache
    assert fake.fetches == 2
    loaded = RawCache(tmp_path).load(PAGE, "batspi")
    assert loaded is not None and loaded.fetched_at == WHEN + timedelta(days=1)


def test_max_age(tmp_path: Path) -> None:
    fake = FakeFetcher()
    cf, clock = make(tmp_path, fake, max_age=timedelta(days=7))
    cf.get(PAGE)
    clock.t = WHEN + timedelta(days=6)
    hit = cf.get(PAGE)
    assert isinstance(hit, CachedPage) and hit.from_cache and fake.fetches == 1
    clock.t = WHEN + timedelta(days=8)
    stale = cf.get(PAGE)
    assert isinstance(stale, CachedPage) and not stale.from_cache and fake.fetches == 2


def test_no_max_age_never_expires(tmp_path: Path) -> None:
    fake = FakeFetcher()
    cf, clock = make(tmp_path, fake)
    cf.get(PAGE)
    clock.t = WHEN + timedelta(days=3650)
    page = cf.get(PAGE)
    assert isinstance(page, CachedPage) and page.from_cache and fake.fetches == 1


def test_skipped_and_stoprun_write_nothing(tmp_path: Path) -> None:
    for result in (Skipped(PAGE, "status 404", 404), Skipped(PAGE, "disallowed: robots")):
        cf, _ = make(tmp_path, FakeFetcher(result))
        assert cf.get(PAGE) == result
    cf, _ = make(tmp_path, FakeFetcher(Blocked("403")))
    with pytest.raises(Blocked):
        cf.get(PAGE)
    assert not list(tmp_path.rglob("*.html")) and not list(tmp_path.rglob("*.json"))


def test_sources_get_separate_directories(tmp_path: Path) -> None:
    fake = FakeFetcher()
    cf, _ = make(tmp_path, fake)
    cf.get(PAGE, "batspi")
    cf.get(PAGE, "other")
    assert fake.fetches == 2
    assert {p.parent.name for p in tmp_path.rglob("*.html")} == {"batspi", "other"}
