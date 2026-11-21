"""``bsdb scrape`` through the CLI, on the fixture site (#73)."""

import logging
from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path

import pytest
import typer
from fakes import ROBOTS_URL, FakeClock, FakeSite, fixture_url, make_client, memoise_parsers
from typer.testing import CliRunner

from bs_database import cli
from bs_database.cli import app, parse_duration
from bs_database.ingest.http import HttpClient, HttpResponse
from bs_database.settings import Settings

runner = CliRunner()
SET_NAME = "契約編：環 第1章：廻帰再醒"
SET_URL = fixture_url("set.html")


@pytest.fixture(autouse=True)
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("BSDB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BSDB_REQUEST_DELAY", "3.0")
    memoise_parsers(monkeypatch)
    root = logging.getLogger()
    level, handlers = root.level, list(root.handlers)
    yield
    for h in list(root.handlers):
        if h not in handlers:
            root.removeHandler(h)
    root.setLevel(level)


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch) -> FakeSite:
    clock = FakeClock()
    fake = FakeSite(clock, unmapped="fallback")
    built: Callable[[Settings], HttpClient] = lambda settings: make_client(settings, fake, clock)  # noqa: E731
    monkeypatch.setattr(cli, "_build_http_client", built)
    return fake


def scrape(*args: str) -> tuple[int, str]:
    result = runner.invoke(app, ["scrape", *args])
    return result.exit_code, result.output


def test_scrape_prints_the_summary(tmp_path: Path, site: FakeSite) -> None:
    code, out = scrape("--set", SET_NAME)
    assert code == 0, out
    assert "Cards parsed this run: 108" in out
    assert "Requests made: 111 (incl. robots.txt)" in out
    assert "Cache hit rate: 0%" in out
    assert "Run: completed" in out
    assert len(list((tmp_path / "data" / "parsed" / "batspi").glob("*.json"))) == 108
    assert (tmp_path / "data" / "state" / "ingest.db").exists()


def test_scrape_again_is_free(site: FakeSite) -> None:
    scrape("--set", SET_NAME)
    calls = len(site.calls)
    code, out = scrape("--set", SET_NAME)
    assert code == 0
    assert len(site.calls) == calls
    assert "Requests made: 0" in out and "Cache hit rate: 100%" in out


def test_limit_and_refresh(site: FakeSite) -> None:
    code, out = scrape("--set", SET_NAME, "--limit", "4")
    assert code == 0 and "Cards parsed this run: 4" in out
    assert len(site.calls) == 3 + 4
    before = len(site.calls)
    code, out = scrape("--set", SET_NAME, "--limit", "1", "--refresh")
    assert code == 0
    new = site.urls()[before:]
    assert new[:3] == [ROBOTS_URL, fixture_url("index.html"), SET_URL]
    assert len(new) == 4  # robots, index, set, one card


def test_max_age_is_accepted(site: FakeSite) -> None:
    code, out = scrape("--set", SET_NAME, "--limit", "1", "--max-age", "7d")
    assert code == 0, out
    code, out = scrape("--set", SET_NAME, "--limit", "1", "--max-age", "0s")
    assert code == 0, out
    assert "Cache hit rate: 0%" in out  # every cached page is older than 0 seconds


def test_bad_max_age_is_a_usage_error(site: FakeSite) -> None:
    code, out = scrape("--max-age", "xyz")
    assert code == 2
    assert site.calls == []


def test_limit_must_be_positive(site: FakeSite) -> None:
    assert scrape("--limit", "0")[0] == 2


def test_budget_stop_is_exit_zero(site: FakeSite, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSDB_MAX_REQUESTS", "5")
    code, out = scrape("--set", SET_NAME)
    assert code == 0
    assert "budget spent, run again" in out


def test_blocked_is_exit_three(site: FakeSite) -> None:
    site.overrides[SET_URL] = HttpResponse(403, {}, b"forbidden")
    code, out = scrape("--set", SET_NAME)
    assert code == 3
    assert "stopped: Blocked" in out


def test_index_unobtainable_is_exit_one(site: FakeSite) -> None:
    del site.pages[fixture_url("index.html")]
    code, out = scrape()
    assert code == 1
    assert "nothing to resume" in out


def test_per_page_failures_are_exit_zero(site: FakeSite) -> None:
    site.unmapped = "404"
    code, out = scrape("--set", SET_NAME)
    assert code == 0
    assert "Exhausted (never retried): 105" in out
    assert "+85 more" in out


def test_real_client_is_the_default() -> None:
    client = cli._build_http_client(Settings())
    assert isinstance(client, HttpClient)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("30s", timedelta(seconds=30)),
        ("5m", timedelta(minutes=5)),
        ("12h", timedelta(hours=12)),
        ("30d", timedelta(days=30)),
        ("2w", timedelta(weeks=2)),
        (" 7D ", timedelta(days=7)),
    ],
)
def test_parse_duration_units(text: str, expected: timedelta) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "7", "d", "7x", "-1d", "1.5h", "1d2h"])
def test_parse_duration_rejects(text: str) -> None:
    with pytest.raises(typer.BadParameter):
        parse_duration(text)


def test_offline_and_retry_failed_flags(site: FakeSite) -> None:
    scrape("--set", SET_NAME, "--limit", "2")
    calls = len(site.calls)
    code, out = scrape("--offline", "--retry-failed", "--set", SET_NAME, "--limit", "2")
    assert code == 0, out
    assert len(site.calls) == calls
    assert "Requests made: 0" in out


def test_reparse_flag_parses_again_from_the_cache(site: FakeSite) -> None:
    scrape("--set", SET_NAME, "--limit", "2")
    calls = len(site.calls)
    code, out = scrape("--offline", "--reparse")
    assert code == 0, out
    assert len(site.calls) == calls
    assert "Requests made: 0" in out
    assert "Cards parsed this run: 2" in out
