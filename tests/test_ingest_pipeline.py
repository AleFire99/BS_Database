"""End-to-end tests of the scrape pipeline on the fixture site (#73).

No sockets: ``FakeSite`` serves the cached fixtures through the real ``HttpClient`` (policy gate,
pacing, budget), ``CachedFetcher``, parsers, ``StateStore`` and parsed JSON store, on a fake clock.
The crawl is scoped to one set page (108 card links, of which 3 are real fixtures) so a full run
is 111 requests.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fakes import ROBOTS_URL, FakeClock, FakeSite, Killed, fixture_url, make_client, memoise_parsers

from bs_database.ingest.cache import OFFLINE_REASON, CachedFetcher, RawCache
from bs_database.ingest.http import (
    TRANSPORT_ERROR_REASON,
    Blocked,
    BudgetExhausted,
    HttpResponse,
    Skipped,
)
from bs_database.ingest.pipeline import INDEX_URL, PROMO_URL, RunOptions, _permanent, run_pipeline
from bs_database.ingest.report import RunReport, render
from bs_database.ingest.state import IngestState, PageKind, StateStore
from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.batspi.set_page import parse_set_page
from bs_database.parsers.errors import ParseError
from bs_database.settings import Settings

S = IngestState
SET_NAME = "契約編：環 第1章：廻帰再醒"
SET_URL = fixture_url("set.html")
SET_ENTRIES = parse_set_page((Path(__file__).parent / "fixtures/html/set.html").read_text()).entries
CARD_URLS = sorted({e.url for e in SET_ENTRIES})
PARSE = "bs_database.ingest.pipeline.parse_card_page"
ONLY_SET = RunOptions(sets=(SET_NAME,))
FIXTURE_CARDS = 3  # card_spirit, card_nexus, card_magic are linked from set.html


@pytest.fixture(autouse=True)
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``BSDB_*`` variables and no ``.env`` file can leak into ``Settings``."""
    for key in list(os.environ):
        if key.startswith("BSDB_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    memoise_parsers(monkeypatch)


def make_settings(tmp_path: Path, *, max_requests: int = 1000) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        request_delay=3.0,
        max_requests=max_requests,
    )


def crawl(
    settings: Settings,
    site: FakeSite,
    clock: FakeClock,
    options: RunOptions = ONLY_SET,
    *,
    refresh: bool = False,
    offline: bool = False,
) -> RunReport:
    client = make_client(settings, site, clock)
    fetcher = CachedFetcher(client, RawCache(settings.cache_dir), refresh=refresh, offline=offline)
    with StateStore(settings.state_db_path) as store:
        return run_pipeline(
            settings, fetcher, store, requests_made=lambda: client.requests_made, options=options
        )


def state_of(settings: Settings, url: str) -> Any:
    with StateStore(settings.state_db_path) as store:
        return store.get(url)


def counts(settings: Settings) -> dict[IngestState, int]:
    with StateStore(settings.state_db_path) as store:
        return store.counts()


def parsed_files(settings: Settings) -> dict[str, dict[str, Any]]:
    root = settings.parsed_dir / "batspi"
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*.json"))}


def test_index_url_pinned() -> None:
    assert fixture_url("index.html") == INDEX_URL
    assert fixture_url("list_promo.html") == PROMO_URL


def test_crawl_index_set_cards(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="fallback")
    report = crawl(settings, site, clock)
    assert report.stop is None and report.exit_code == 0
    assert report.cards_parsed == len(CARD_URLS)
    assert len(parsed_files(settings)) == len(CARD_URLS)
    assert len(site.calls) == 3 + len(CARD_URLS)  # robots, index, set, cards
    assert site.calls[0][1] == ROBOTS_URL
    assert report.requests_made == len(site.calls)
    assert report.hit_rate == 0.0
    assert report.index_missing_pages == 7
    assert state_of(settings, INDEX_URL).state is S.PARSED
    assert state_of(settings, SET_URL).state is S.PARSED
    assert state_of(settings, SET_URL).content_sha256 is not None
    assert counts(settings)[S.PARSED] == 2 + len(CARD_URLS)
    assert "Cards parsed this run" in render(report)


def test_warm_cache_zero_requests(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    first = FakeSite(clock, unmapped="fallback")
    crawl(settings, first, clock)
    before = parsed_files(settings)
    for path in settings.state_db_path.parent.glob("ingest.db*"):
        path.unlink()  # forget the state: everything is walked again, from the cache
    second = FakeSite(clock, unmapped="fallback")
    report = crawl(settings, second, clock)
    assert second.calls == []  # not even robots.txt
    assert report.requests_made == 0 and report.hit_rate == 1.0
    assert report.cards_parsed == len(CARD_URLS)
    after = parsed_files(settings)
    assert after.keys() == before.keys()
    for name, doc in after.items():
        assert doc["provenance"]["from_cache"] is True
        assert before[name]["provenance"]["from_cache"] is False
        doc["provenance"]["from_cache"] = before[name]["provenance"]["from_cache"]
        assert doc == before[name]


def test_resume_after_kill(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="fallback", kill_after=40)
    with pytest.raises(Killed):
        crawl(settings, site, clock)
    served = set(site.urls()) - {ROBOTS_URL}
    done = counts(settings)[S.PARSED]
    assert 2 < done < 2 + len(CARD_URLS)
    site.kill_after = None
    first_run_calls = len(site.calls)
    report = crawl(settings, site, clock)
    again = set(site.urls()[first_run_calls:]) - {ROBOTS_URL}
    assert again.isdisjoint(served)  # nothing served before the kill is fetched again
    assert report.cards_parsed == 2 + len(CARD_URLS) - done
    assert counts(settings)[S.PARSED] == 2 + len(CARD_URLS)
    assert len(parsed_files(settings)) == len(CARD_URLS)


def test_resume_between_fetch_and_parse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="fallback")
    real = parse_card_page
    seen: list[str] = []

    def killing(html: str, url: str) -> Any:
        seen.append(url)
        if len(seen) == 5:
            raise Killed
        return real(html, url)

    monkeypatch.setattr(PARSE, killing)
    with pytest.raises(Killed):
        crawl(settings, site, clock)
    victim = seen[-1]
    assert state_of(settings, victim).state is S.FETCHED
    monkeypatch.setattr(PARSE, real)
    first_run_calls = len(site.calls)
    crawl(settings, site, clock)
    assert victim not in site.urls()[first_run_calls:]  # parsed again from the cache
    assert state_of(settings, victim).state is S.PARSED
    assert counts(settings)[S.PARSED] == 2 + len(CARD_URLS)


def test_not_found_is_permanent(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="404")
    report = crawl(settings, site, clock)
    missing = len(CARD_URLS) - FIXTURE_CARDS
    assert report.cards_parsed == FIXTURE_CARDS
    assert len(report.failures) == missing
    assert {reason for _, reason in report.failures} == {"skipped: status 404"}
    assert len(report.exhausted) == missing and report.exit_code == 0
    assert f"Exhausted (never retried): {missing}" in render(report)
    record = state_of(settings, report.failures[0][0])
    assert record.state is S.FAILED and record.attempts == 3
    again = FakeSite(clock, unmapped="fallback")  # even if the site is fixed: never retried
    report2 = crawl(settings, again, clock)
    assert again.calls == [] and report2.failures == []
    assert len(report2.exhausted) == missing


def test_failure_then_retry_on_a_later_run(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="fallback")
    flaky = CARD_URLS[:2]
    for url in flaky:
        site.overrides[url] = HttpResponse(503, {}, b"busy")
    report = crawl(settings, site, clock)
    assert sorted(url for url, _ in report.failures) == flaky
    assert all(reason == "skipped: status 503" for _, reason in report.failures)
    for url in flaky:
        record = state_of(settings, url)
        assert record.state is S.FAILED and record.attempts == 1
    assert report.exhausted == []
    site.overrides.clear()
    first_run_calls = len(site.calls)
    report2 = crawl(settings, site, clock)
    assert report2.cards_parsed == 2 and report2.failures == []
    assert sorted(set(site.urls()[first_run_calls:]) - {ROBOTS_URL}) == flaky
    for url in flaky:
        record = state_of(settings, url)
        assert record.state is S.PARSED and record.attempts == 0
    assert len(parsed_files(settings)) == len(CARD_URLS)


def test_parse_error_then_retry_from_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="fallback")
    real = parse_card_page
    bad = CARD_URLS[7]

    def broken(html: str, url: str) -> Any:
        if url == bad:
            raise ParseError("no card block")
        return real(html, url)

    monkeypatch.setattr(PARSE, broken)
    report = crawl(settings, site, clock)
    assert report.failures == [(bad, "parse error: no card block")]
    record = state_of(settings, bad)
    assert record.state is S.FAILED and record.failed_from is S.FETCHED and record.attempts == 1
    monkeypatch.setattr(PARSE, real)
    again = FakeSite(clock, unmapped="fallback")
    report2 = crawl(settings, again, clock)
    assert again.calls == []  # the retry runs from the cache
    assert report2.cards_parsed == 1
    assert state_of(settings, bad).state is S.PARSED


def test_retries_exhausted_reported(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    stuck = CARD_URLS[0]
    site = FakeSite(clock, unmapped="fallback")
    site.overrides[stuck] = HttpResponse(503, {}, b"busy")
    reports = [crawl(settings, site, clock) for _ in range(3)]
    assert [len(r.exhausted) for r in reports] == [0, 0, 1]
    assert reports[2].exhausted[0].url == stuck
    assert state_of(settings, stuck).attempts == 3
    first_run_calls = len(site.calls)
    report = crawl(settings, site, clock)
    assert len(site.calls) == first_run_calls  # no further request
    assert [r.url for r in report.exhausted] == [stuck] and report.failures == []


def test_request_rate_and_budget_respected(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="fallback")
    crawl(settings, site, clock)
    times = [t for t, _ in site.calls]
    assert all(b - a >= settings.request_delay for a, b in zip(times, times[1:], strict=False))
    assert len(times) <= settings.max_requests


def test_budget_stop_then_continue(tmp_path: Path) -> None:
    small = make_settings(tmp_path, max_requests=5)
    clock = FakeClock()
    site = FakeSite(clock, unmapped="fallback")
    report = crawl(small, site, clock)
    assert isinstance(report.stop, BudgetExhausted) and report.exit_code == 0
    assert "budget spent, run again" in render(report)
    assert len(site.calls) == 5 and report.cards_parsed == 2
    assert counts(small)[S.PARSED] == 4  # index, set, two cards: committed
    served = set(site.urls()) - {ROBOTS_URL}
    big = make_settings(tmp_path)
    second = FakeSite(clock, unmapped="fallback")
    report2 = crawl(big, second, clock)
    assert report2.stop is None
    assert served.isdisjoint(second.urls())
    assert counts(big)[S.PARSED] == 2 + len(CARD_URLS)


def test_blocked_stop_is_not_a_page_failure(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="fallback")
    victim = CARD_URLS[3]
    site.overrides[victim] = HttpResponse(403, {}, b"forbidden")
    report = crawl(settings, site, clock)
    assert isinstance(report.stop, Blocked) and report.exit_code == 3
    assert report.failures == []
    record = state_of(settings, victim)
    assert record.state is S.DISCOVERED and record.attempts == 0
    assert "stopped: Blocked" in render(report)


def test_set_without_card_list_is_parsed_with_no_cards(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock)
    site.pages[SET_URL] = b'<div id="body"><h2>Event</h2><p>no cards here</p></div>'
    report = crawl(settings, site, clock)
    assert report.sets_without_cards == [SET_NAME] and report.failures == []
    assert state_of(settings, SET_URL).state is S.PARSED
    assert counts(settings)[S.DISCOVERED] == 570  # the other sets; no card rows
    assert not settings.parsed_dir.exists()


def test_broken_set_page_fails(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock)
    site.pages[SET_URL] = b'<div id="body"><p>nothing</p></div>'
    report = crawl(settings, site, clock)
    assert report.failures == [(SET_URL, "parse error: no title heading")]
    record = state_of(settings, SET_URL)
    assert record.state is S.FAILED and record.attempts == 1


def test_set_page_not_found_fails(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock)
    del site.pages[SET_URL]
    report = crawl(settings, site, clock)
    assert report.failures == [(SET_URL, "skipped: status 404")]
    assert [r.url for r in report.exhausted] == [SET_URL]


def test_discovery_notes_for_the_promo_list(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock)
    report = crawl(settings, site, clock, RunOptions(sets=("プロモーションカード",), limit=0))
    (note,) = report.notes
    assert note.set_title == "プロモーションカード"
    assert len(note.unknown_numbers) == 9
    assert "9 unknown numbers" in render(report)
    assert state_of(settings, PROMO_URL).state is S.PARSED
    assert counts(settings)[S.DISCOVERED] > 1000  # promo cards discovered, none fetched
    assert PROMO_URL in site.urls()


def test_set_filter_and_limit(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="fallback")
    report = crawl(settings, site, clock, RunOptions(sets=(SET_NAME.lower(),), limit=10))
    assert report.cards_parsed == 10 and len(site.calls) == 3 + 10
    assert state_of(settings, fixture_url("set_sd54.html")).state is S.DISCOVERED
    other = FakeSite(clock, unmapped="fallback")  # another set: this set's cards are left alone
    crawl(settings, other, clock, RunOptions(sets=("operation uc",), limit=0))
    assert state_of(settings, fixture_url("set_sd54.html")).state is S.PARSED
    assert not set(other.urls()) & set(CARD_URLS)
    third = FakeSite(clock, unmapped="fallback")  # the set is walked again, from the cache
    report3 = crawl(settings, third, clock)
    assert report3.cards_parsed == len(CARD_URLS) - 10
    assert not {INDEX_URL, SET_URL} & set(third.urls())
    assert counts(settings)[S.PARSED] == 3 + len(CARD_URLS)


def test_refresh_fetches_discovery_pages_again(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    crawl(settings, FakeSite(clock), clock, RunOptions(sets=(SET_NAME,), limit=0))
    site = FakeSite(clock)
    report = crawl(settings, site, clock, RunOptions(sets=(SET_NAME,), limit=0), refresh=True)
    assert site.urls() == [ROBOTS_URL, INDEX_URL, SET_URL]
    assert report.network_pages == 2 and report.hit_rate == 0.0


def test_index_unobtainable_on_empty_state(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock)
    del site.pages[INDEX_URL]
    report = crawl(settings, site, clock)
    assert report.index_unobtainable and report.exit_code == 1
    assert report.failures == [(INDEX_URL, "skipped: status 404")]
    assert "nothing to resume" in render(report)
    assert state_of(settings, INDEX_URL).state is S.FAILED


def test_index_gone_later_keeps_the_state(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    crawl(settings, FakeSite(clock), clock, RunOptions(sets=(SET_NAME,), limit=0))
    site = FakeSite(clock)
    del site.pages[INDEX_URL]
    report = crawl(settings, site, clock, ONLY_SET, refresh=True)
    assert not report.index_unobtainable and report.exit_code == 0
    assert any("index revisit failed" in w for w in report.warnings)
    assert any("--set cannot be applied" in w for w in report.warnings)
    assert state_of(settings, INDEX_URL).state is S.PARSED


def test_pending_sets_resume_when_the_index_is_exhausted(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    crawl(settings, FakeSite(clock), clock, RunOptions(sets=(SET_NAME,), limit=0))
    with StateStore(settings.state_db_path) as store:
        store.mark_failed(INDEX_URL, "gone", permanent=True)
        for record in store.iter_pending(kind=PageKind.SET):
            if record.url != SET_URL:
                store.mark_failed(record.url, "x", permanent=True)  # keep the walk short
    site = FakeSite(clock, unmapped="fallback")
    report = crawl(settings, site, clock, RunOptions())
    assert any("index page exhausted" in w for w in report.warnings)
    assert report.cards_parsed == len(CARD_URLS)  # from the sets already in the state
    assert not report.index_unobtainable


def test_garbage_index_fails_then_revisit_warns(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock)
    site.pages[INDEX_URL] = b"<html></html>"
    report = crawl(settings, site, clock)
    assert report.failures and report.failures[0][1].startswith("parse error:")
    assert report.index_unobtainable
    good = make_settings(tmp_path / "other")
    crawl(good, FakeSite(clock), clock, RunOptions(limit=0, sets=(SET_NAME,)))
    broken = FakeSite(clock)
    broken.pages[INDEX_URL] = b"<html></html>"
    again = crawl(good, broken, clock, RunOptions(limit=0, sets=(SET_NAME,)), refresh=True)
    assert any("index revisit failed: parse error" in w for w in again.warnings)


def test_set_revisit_failures_only_warn(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    opts = RunOptions(sets=(SET_NAME,), limit=0)
    crawl(settings, FakeSite(clock), clock, opts)
    gone = FakeSite(clock)
    del gone.pages[SET_URL]
    report = crawl(settings, gone, clock, opts, refresh=True)
    assert any("set revisit failed" in w and "404" in w for w in report.warnings)
    broken = FakeSite(clock)
    broken.pages[SET_URL] = b'<div id="body"></div>'
    report = crawl(settings, broken, clock, opts, refresh=True)
    assert any("set revisit failed" in w and "parse error" in w for w in report.warnings)
    assert report.failures == []
    assert state_of(settings, SET_URL).state is S.PARSED


def test_only_transport_errors_are_retryable_skips() -> None:
    assert not _permanent(Skipped("u", "transport error: timeout"))
    assert not _permanent(Skipped("u", "status 503", 503))
    assert _permanent(Skipped("u", "status 404", 404))
    assert _permanent(Skipped("u", "disallowed: deny list"))


def test_set_filter_without_a_match_warns(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock)
    report = crawl(settings, site, clock, RunOptions(sets=("zzz-nothing",), limit=0))
    assert "no product matches --set zzz-nothing" in report.warnings
    assert site.urls() == [ROBOTS_URL, INDEX_URL]
    assert "Warning: no product matches --set zzz-nothing" in render(report)


def test_transport_error_reason_is_the_shared_constant() -> None:
    assert _permanent(Skipped("u", f"{TRANSPORT_ERROR_REASON}: timeout")) is False


def test_exhausted_set_is_skipped(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    opts = RunOptions(sets=(SET_NAME,), limit=0)
    crawl(settings, FakeSite(clock), clock, opts)
    with StateStore(settings.state_db_path) as store:
        store.mark_failed(SET_URL, "gone", permanent=True)
    site = FakeSite(clock)
    report = crawl(settings, site, clock, opts)
    assert SET_URL not in site.urls()
    assert [r.url for r in report.exhausted] == [SET_URL]


def test_without_a_filter_every_set_is_visited(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path, max_requests=4), FakeClock()
    site = FakeSite(clock)
    report = crawl(settings, site, clock, RunOptions(limit=0))
    assert isinstance(report.stop, BudgetExhausted)
    assert len(site.calls) == 4  # robots, index, then sets in index order


def test_retry_failed_resets_only_parse_errors_and_offline_makes_no_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="fallback")
    real = parse_card_page
    bad, gone = CARD_URLS[7], CARD_URLS[9]
    site.overrides[gone] = HttpResponse(404, {}, b"not found")

    def broken(html: str, url: str) -> Any:
        if url == bad:
            raise ParseError("no card block")
        return real(html, url)

    monkeypatch.setattr(PARSE, broken)
    for _ in range(3):  # three failures: exhausted
        crawl(settings, site, clock)
    assert {r.url for r in crawl(settings, site, clock).exhausted} == {bad, gone}
    monkeypatch.setattr(PARSE, real)
    # a plain run does not touch an exhausted page
    assert crawl(settings, site, clock).cards_parsed == 0
    offline_site = FakeSite(clock, unmapped="fallback")
    report = crawl(
        settings, offline_site, clock, RunOptions(sets=(SET_NAME,), retry_failed=True), offline=True
    )
    assert offline_site.calls == [] and report.requests_made == 0  # not even robots.txt
    assert report.cards_parsed == 1
    assert state_of(settings, bad).state is S.PARSED
    record = state_of(settings, gone)
    assert record.state is S.FAILED and record.attempts == 3  # the 404 stays exhausted
    assert [r.url for r in report.exhausted] == [gone]


def test_offline_miss_is_a_retryable_skip(tmp_path: Path) -> None:
    settings, clock = make_settings(tmp_path), FakeClock()
    site = FakeSite(clock, unmapped="fallback")
    report = crawl(settings, site, clock, offline=True)
    assert site.calls == [] and report.requests_made == 0
    record = state_of(settings, INDEX_URL)
    assert record.state is S.FAILED and record.attempts == 1  # not exhausted at once
    assert report.index_unobtainable and report.exit_code == 1
    assert not _permanent(Skipped("u", OFFLINE_REASON))
