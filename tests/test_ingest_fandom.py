import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from bs_database.ingest.cache import RawCache
from bs_database.ingest.fandom import API_URL, FandomApi
from bs_database.ingest.http import (
    Blocked,
    BudgetExhausted,
    HttpResponse,
    TransportError,
)
from bs_database.settings import Settings


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeTransport:
    """Answers through a callable; records ``(time, url, headers)`` of every call."""

    def __init__(self, clock: FakeClock, answer: Any) -> None:
        self._clock = clock
        self._answer = answer
        self.calls: list[tuple[float, str, Mapping[str, str]]] = []

    def get(
        self, url: str, *, headers: Mapping[str, str], timeout: tuple[float, float]
    ) -> HttpResponse:
        self.calls.append((self._clock.monotonic(), url, headers))
        item = self._answer(url)
        if isinstance(item, TransportError):
            raise item
        assert isinstance(item, HttpResponse)
        return item


def ok(data: object) -> HttpResponse:
    return HttpResponse(200, {}, json.dumps(data).encode())


def make(
    tmp_path: Path, answer: Any, **settings: Any
) -> tuple[FandomApi, FakeTransport, FakeClock]:
    clock = FakeClock()
    transport = FakeTransport(clock, answer)
    cfg = Settings(data_dir=tmp_path, cache_dir=tmp_path / "cache", **settings)
    api = FandomApi(cfg, transport=transport, clock=clock, cache=RawCache(tmp_path / "cache"))
    return api, transport, clock


def pages_answer(url: str) -> HttpResponse:
    titles = parse_qs(urlsplit(url).query)["titles"][0].split("|")
    pages = {
        str(i): {"title": t, "revisions": [{"slots": {"main": {"*": f"text of {t}"}}}]}
        for i, t in enumerate(titles)
    }
    return ok({"query": {"pages": pages}})


def test_batches_of_fifty(tmp_path: Path) -> None:
    api, transport, _ = make(tmp_path, pages_answer)
    titles = [f"Page {i}" for i in range(120)]
    out = api.wikitext(titles)
    assert len(out) == 120
    assert out["Page 7"] == "text of Page 7"
    assert api.requests_made == 3
    sizes = [
        len(parse_qs(urlsplit(u).query)["titles"][0].split("|")) for _, u, _ in transport.calls
    ]
    assert sizes == [50, 50, 20]


def test_formatversion2_shape_is_understood(tmp_path: Path) -> None:
    def answer(url: str) -> HttpResponse:
        page = {"title": "X", "revisions": [{"slots": {"main": {"content": "hello"}}}]}
        return ok({"query": {"pages": [page, {"title": "Gone", "missing": True}]}})

    api, _, _ = make(tmp_path, answer)
    assert api.wikitext(["X", "Gone"]) == {"X": "hello"}


def test_pacing_user_agent_and_delay(tmp_path: Path) -> None:
    api, transport, clock = make(tmp_path, pages_answer, request_delay=3.0)
    api.wikitext([f"P{i}" for i in range(101)])
    assert [c[0] for c in transport.calls] == [0.0, 3.0, 6.0]
    assert clock.sleeps == [3.0, 3.0]
    assert transport.calls[0][2]["User-Agent"].startswith("bs-database/")


def test_budget_exhausted(tmp_path: Path) -> None:
    api, _, _ = make(tmp_path, pages_answer, max_requests=2)
    with pytest.raises(BudgetExhausted):
        api.wikitext([f"P{i}" for i in range(101)])
    assert api.requests_made == 2


def test_category_members_follow_continue(tmp_path: Path) -> None:
    def answer(url: str) -> HttpResponse:
        q = parse_qs(urlsplit(url).query)
        assert q["cmtitle"] == ["Category:Family"]
        assert q["cmlimit"] == ["500"]
        if "cmcontinue" not in q:
            return ok(
                {
                    "continue": {"cmcontinue": "page|X", "continue": "-||"},
                    "query": {"categorymembers": [{"title": "A"}, {"title": "B"}]},
                }
            )
        assert q["cmcontinue"] == ["page|X"]
        return ok({"query": {"categorymembers": [{"title": "C"}]}})

    api, _, _ = make(tmp_path, answer)
    assert api.category_members("Category:Family") == ["A", "B", "C"]
    assert api.requests_made == 2


def test_403_stops_the_run(tmp_path: Path) -> None:
    api, transport, _ = make(tmp_path, lambda url: HttpResponse(403, {}, b"{}"))
    with pytest.raises(Blocked):
        api.category_members("Category:Family")
    assert len(transport.calls) == 1


def test_challenge_body_stops_the_run(tmp_path: Path) -> None:
    body = b"<html><title>Just a moment...</title></html>"
    api, _, _ = make(tmp_path, lambda url: HttpResponse(200, {}, body))
    with pytest.raises(Blocked):
        api.category_members("Category:Family")


def test_wikitext_mentioning_a_challenge_marker_is_not_blocked(tmp_path: Path) -> None:
    page = {"title": "X", "revisions": [{"slots": {"main": {"*": "Just a moment"}}}]}
    api, _, _ = make(tmp_path, lambda url: ok({"query": {"pages": {"1": page}}}))
    assert api.wikitext(["X"]) == {"X": "Just a moment"}


def test_retry_on_503_then_ok(tmp_path: Path) -> None:
    answers = [HttpResponse(503, {}, b""), ok({"query": {"categorymembers": [{"title": "A"}]}})]
    api, _, clock = make(tmp_path, lambda url: answers.pop(0))
    assert api.category_members("Category:Family") == ["A"]
    assert 5.0 in clock.sleeps
    assert api.requests_made == 2


def test_cache_hit_makes_no_request(tmp_path: Path) -> None:
    api, _, _ = make(tmp_path, pages_answer)
    api.wikitext(["A", "B"])
    api2, transport2, _ = make(tmp_path, lambda url: pytest.fail("network used"))
    assert api2.wikitext(["A", "B"]) == {"A": "text of A", "B": "text of B"}
    assert api2.requests_made == 0
    assert transport2.calls == []


@pytest.mark.parametrize(
    "url",
    [
        "https://battle-spirits.fandom.com/wiki/Machine_Beast",
        "https://battle-spirits.fandom.com/robots.txt",
        "https://battle-spirits.fandom.com/api.php?action=parse&page=X",
        "https://battle-spirits.fandom.com/api.php?action=query&action=parse",
        "https://example.com/api.php?action=query",
        "https://battle-spirits.fandom.com/api.php",
    ],
)
def test_disallowed_url_rejected(tmp_path: Path, url: str) -> None:
    api, transport, _ = make(tmp_path, lambda u: pytest.fail("network used"))
    with pytest.raises(ValueError, match="disallowed"):
        api.get_json(url)
    assert transport.calls == []


def test_allowed_url_prefix_constant() -> None:
    assert API_URL == "https://battle-spirits.fandom.com/api.php"
