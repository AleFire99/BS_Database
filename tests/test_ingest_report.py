"""Run report: hit rate, truncation, exit codes (#73)."""

from bs_database.ingest.http import Blocked, BudgetExhausted, RetryAfterTooLong, RobotsUnavailable
from bs_database.ingest.report import MAX_LISTED_FAILURES, DiscoveryNote, RunReport, render
from bs_database.ingest.state import IngestState, PageKind, PageRecord


def test_hit_rate_arithmetic() -> None:
    report = RunReport()
    assert report.hit_rate is None
    assert "Cache hit rate: n/a" in render(report)
    report.cache_hits, report.network_pages = 3, 1
    assert report.hit_rate == 0.75
    assert "Cache hit rate: 75%" in render(report)


def test_exit_codes() -> None:
    assert RunReport().exit_code == 0
    assert RunReport(stop=BudgetExhausted("x")).exit_code == 0
    for stop in (Blocked("x"), RobotsUnavailable("x"), RetryAfterTooLong("x")):
        assert RunReport(stop=stop).exit_code == 3
    assert RunReport(index_unobtainable=True).exit_code == 1
    assert RunReport(failures=[("u", "r")]).exit_code == 0


def test_failures_are_truncated() -> None:
    failures = [(f"u{i}", "skipped: status 404") for i in range(MAX_LISTED_FAILURES + 5)]
    text = render(RunReport(failures=failures))
    assert f"Failures this run: {len(failures)}" in text
    assert f"u{MAX_LISTED_FAILURES - 1}:" in text
    assert f"u{MAX_LISTED_FAILURES}:" not in text
    assert "+5 more" in text


def test_stop_lines_and_sections() -> None:
    assert "budget spent, run again" in render(RunReport(stop=BudgetExhausted("5 used")))
    assert "stopped: Blocked: 403" in render(RunReport(stop=Blocked("403")))
    assert "Run: completed" in render(RunReport())
    exhausted = PageRecord(
        "https://x/a",
        PageKind.CARD,
        IngestState.FAILED,
        IngestState.DISCOVERED,
        3,
        "skipped: status 404",
        None,
        "t",
    )
    report = RunReport(
        exhausted=[exhausted],
        sets_without_cards=["Event"],
        index_missing_pages=2,
        notes=[DiscoveryNote("Promo", ("X1", "X2"), 1)],
        warnings=["careful"],
        counts={IngestState.PARSED: 4, IngestState.FAILED: 0},
        requests_made=7,
    )
    text = render(report)
    for needle in (
        "parsed: 4",
        "Exhausted (never retried): 1",
        "https://x/a: skipped: status 404",
        "Sets without a card list: Event",
        "does not exist yet: 2",
        "Note, Promo: 2 unknown numbers; X1, X2; 1 entries without a page",
        "Warning: careful",
        "Requests made: 7 (incl. robots.txt)",
    ):
        assert needle in text
    assert "failed: 0" not in text
