from collections.abc import Mapping
from pathlib import Path

import pytest
import requests

from bs_database.ingest.http import (
    Blocked,
    BudgetExhausted,
    Fetched,
    Fetcher,
    HttpClient,
    HttpResponse,
    RequestsTransport,
    RetryAfterTooLong,
    RobotsUnavailable,
    Skipped,
    TransportError,
)
from bs_database.ingest.policy import local_check
from bs_database.settings import Settings

BASE = "https://batspi.com/"


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
    """Scripted responses per URL; records ``(time, url, headers)`` of every call."""

    def __init__(
        self, clock: FakeClock, script: Mapping[str, list[HttpResponse | TransportError]]
    ) -> None:
        self._clock = clock
        self._script = {url: list(items) for url, items in script.items()}
        self.calls: list[tuple[float, str, Mapping[str, str]]] = []

    def get(
        self, url: str, *, headers: Mapping[str, str], timeout: tuple[float, float]
    ) -> HttpResponse:
        self.calls.append((self._clock.monotonic(), url, headers))
        if url not in self._script or not self._script[url]:
            raise AssertionError(f"unscripted request: {url}")
        item = self._script[url].pop(0)
        if isinstance(item, TransportError):
            raise item
        return item


ROBOTS_URL = f"{BASE}robots.txt"
# batspi.com robots.txt as fetched on 2026-11-14 (docs/sources/batspi.md, "Robots policy").
ROBOTS = """User-agent: *
Disallow: /index.php?%E3%82%AB%E3%83%BC%E3%83%89%E6%83%85%E5%A0%B1%E7%B5%9E%E8%BE%BC%E3%81%BF&
Disallow: /?
Disallow: /index.php/

User-agent: bingbot
User-agent: Sogou web spider
User-agent: SemrushBot
User-agent: Baiduspider

Disallow: /
"""


def ok(body: str = "<html>ok</html>") -> HttpResponse:
    return HttpResponse(200, {}, body.encode())


def make(
    script: Mapping[str, list[HttpResponse | TransportError]],
    max_requests: int = 1000,
    with_robots: bool = True,
) -> tuple[HttpClient, FakeTransport, FakeClock]:
    clock = FakeClock()
    full = dict(script)
    if with_robots:
        full.setdefault(ROBOTS_URL, [HttpResponse(200, {}, ROBOTS.encode())])
    transport = FakeTransport(clock, full)
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, request_delay=3.0, max_requests=max_requests
    )
    return HttpClient(settings, transport=transport, clock=clock), transport, clock


def pages(transport: FakeTransport) -> list[tuple[float, str, Mapping[str, str]]]:
    """Recorded calls without the robots.txt request."""
    return [c for c in transport.calls if c[1] != ROBOTS_URL]


def test_user_agent_on_every_call() -> None:
    urls = [f"{BASE}index.php?p{i}" for i in range(3)]
    client, transport, _ = make({u: [ok()] for u in urls})
    for u in urls:
        assert isinstance(client.fetch(u), Fetched)
    assert len(transport.calls) == 4
    for _, _, headers in transport.calls:  # robots.txt included
        assert headers == {"User-Agent": client._settings.user_agent}
        assert headers["User-Agent"].startswith("bs-database/")


def test_fetched_content() -> None:
    url = f"{BASE}index.php?a"
    client, _, _ = make({url: [ok("héllo")]})
    result = client.fetch(url)
    assert isinstance(result, Fetched)
    assert result.url == url
    assert result.status == 200
    assert result.text == "héllo"


def test_pacing_between_requests() -> None:
    urls = [f"{BASE}index.php?p{i}" for i in range(20)]
    client, transport, _ = make({u: [ok()] for u in urls})
    for u in urls:
        client.fetch(u)
    times = [t for t, _, _ in pages(transport)]
    assert len(times) == 20
    assert all(b - a >= 3.0 for a, b in zip(times, times[1:], strict=False))


def test_budget_stops_cleanly() -> None:
    urls = [f"{BASE}index.php?p{i}" for i in range(5)]
    client, transport, _ = make({u: [ok()] for u in urls}, max_requests=4)
    for u in urls[:3]:
        assert isinstance(client.fetch(u), Fetched)
    with pytest.raises(BudgetExhausted):
        client.fetch(urls[3])
    assert client.requests_made == 4
    assert len(transport.calls) == 4


def resp(status: int, body: str = "", **headers: str) -> HttpResponse:
    return HttpResponse(status, headers, body.encode())


URL = f"{BASE}index.php?page"


@pytest.mark.parametrize("status", [404, 410, 301, 501])
def test_other_statuses_skip_without_retry(status: int) -> None:
    client, transport, clock = make({URL: [resp(status)]})
    assert client.fetch(URL) == Skipped(URL, f"status {status}", status)
    assert len(pages(transport)) == 1
    assert clock.sleeps == [3.0]  # only the pacing wait after robots.txt


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retry_then_success(status: int) -> None:
    client, transport, clock = make({URL: [resp(status), resp(status), resp(status), ok()]})
    assert isinstance(client.fetch(URL), Fetched)
    assert clock.sleeps == [3.0, 5.0, 3.0, 15.0, 3.0, 45.0, 3.0]
    times = [t for t, _, _ in pages(transport)]
    assert [b - a for a, b in zip(times, times[1:], strict=False)] == [8.0, 18.0, 48.0]
    assert client.requests_made == 5  # robots.txt + 4 page requests


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retries_exhausted_is_skipped(status: int) -> None:
    client, transport, clock = make({URL: [resp(status)] * 4})
    assert client.fetch(URL) == Skipped(URL, f"status {status}", status)
    assert len(pages(transport)) == 4
    assert clock.sleeps == [3.0, 5.0, 3.0, 15.0, 3.0, 45.0, 3.0]


def test_timeout_and_connection_errors_retry() -> None:
    client, transport, _ = make(
        {URL: [TransportError("t", timeout=True), TransportError("c"), ok()]}
    )
    assert isinstance(client.fetch(URL), Fetched)
    assert len(pages(transport)) == 3


def test_transport_errors_exhausted_is_skipped() -> None:
    client, _, _ = make({URL: [TransportError("t", timeout=True)] * 4})
    result = client.fetch(URL)
    assert isinstance(result, Skipped)
    assert result.status is None


def test_retries_count_against_budget() -> None:
    client, transport, _ = make({URL: [resp(500)] * 4}, max_requests=3)
    with pytest.raises(BudgetExhausted):
        client.fetch(URL)
    assert len(pages(transport)) == 2  # robots.txt took one request of the budget


def test_retry_after_overrides_shorter_backoff() -> None:
    client, transport, _ = make({URL: [resp(429, **{"Retry-After": "20"}), ok()]})
    client.fetch(URL)
    times = [t for t, _, _ in pages(transport)]
    assert times[1] - times[0] == 23.0


def test_retry_after_shorter_than_backoff_is_ignored() -> None:
    client, transport, _ = make({URL: [resp(429, **{"retry-after": "1"}), ok()]})
    client.fetch(URL)
    times = [t for t, _, _ in pages(transport)]
    assert times[1] - times[0] == 8.0


def test_retry_after_too_long_stops() -> None:
    client, transport, _ = make({URL: [resp(429, **{"Retry-After": "400"})]})
    with pytest.raises(RetryAfterTooLong):
        client.fetch(URL)
    assert len(pages(transport)) == 1


def test_retry_after_http_date_is_ignored() -> None:
    date = "Wed, 21 Oct 2026 07:28:00 GMT"
    client, transport, _ = make({URL: [resp(503, **{"Retry-After": date}), ok()]})
    client.fetch(URL)
    times = [t for t, _, _ in pages(transport)]
    assert times[1] - times[0] == 8.0


@pytest.mark.parametrize(
    "response",
    [
        resp(403),
        resp(200, "<title>Just a moment...</title>"),
        resp(503, "<script src='/cdn-cgi/challenge-platform/x'></script>"),
    ],
)
def test_blocked_stops_without_further_request(response: HttpResponse) -> None:
    client, transport, _ = make({URL: [response, ok()]})
    with pytest.raises(Blocked):
        client.fetch(URL)
    assert len(pages(transport)) == 1


def test_pacing_holds_across_retry_sequences() -> None:
    urls = [f"{BASE}index.php?p{i}" for i in range(6)]
    script: dict[str, list[HttpResponse | TransportError]] = {
        u: [resp(500), ok()] if i % 2 else [ok()] for i, u in enumerate(urls)
    }
    client, transport, _ = make(script)
    for u in urls:
        client.fetch(u)
    times = [t for t, _, _ in pages(transport)]
    assert all(b - a >= 3.0 for a, b in zip(times, times[1:], strict=False))


def test_requests_transport_maps_response(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[requests.PreparedRequest] = []

    def send(
        self: requests.Session, request: requests.PreparedRequest, **kw: object
    ) -> requests.Response:
        seen.append(request)
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b"body"
        resp.headers["X-Test"] = "1"
        return resp

    monkeypatch.setattr(requests.Session, "send", send)
    out = RequestsTransport().get(BASE, headers={"User-Agent": "ua"}, timeout=(1.0, 2.0))
    assert out.status == 200
    assert out.content == b"body"
    assert out.headers["X-Test"] == "1"
    assert seen[0].headers["User-Agent"] == "ua"


@pytest.mark.parametrize(
    ("exc", "is_timeout"),
    [
        (requests.Timeout("t"), True),
        (requests.ConnectionError("c"), False),
        (requests.exceptions.ChunkedEncodingError("x"), False),
        (requests.exceptions.ContentDecodingError("d"), False),
    ],
)
def test_requests_transport_maps_errors(
    monkeypatch: pytest.MonkeyPatch, exc: Exception, is_timeout: bool
) -> None:
    def send(
        self: requests.Session, request: requests.PreparedRequest, **kw: object
    ) -> requests.Response:
        raise exc

    monkeypatch.setattr(requests.Session, "send", send)
    with pytest.raises(TransportError) as info:
        RequestsTransport().get(BASE, headers={}, timeout=(1.0, 2.0))
    assert info.value.timeout is is_timeout


def test_client_satisfies_fetcher() -> None:
    client, _, _ = make({})
    fetcher: Fetcher = client
    assert fetcher.allowed(f"{BASE}index.php?ok") is None


def test_robots_fetched_once_for_many_urls() -> None:
    urls = [f"{BASE}index.php?p{i}" for i in range(5)]
    client, transport, _ = make({u: [ok()] for u in urls})
    for u in urls:
        assert client.allowed(u) is None
        assert isinstance(client.fetch(u), Fetched)
    assert [c[1] for c in transport.calls].count(ROBOTS_URL) == 1
    assert transport.calls[0][1] == ROBOTS_URL
    assert client.requests_made == len(transport.calls) == 6


def test_allowed_sends_no_page_request() -> None:
    client, transport, _ = make({})
    assert client.allowed(f"{BASE}index.php?%E3%82%B4") is None
    assert [c[1] for c in transport.calls] == [ROBOTS_URL]


def test_robots_404_allows_all() -> None:
    client, _, _ = make({ROBOTS_URL: [resp(404)], URL: [ok()]})
    assert isinstance(client.fetch(URL), Fetched)


@pytest.mark.parametrize(
    "response",
    [
        resp(403),
        resp(500),
        resp(301),
        TransportError("t", timeout=True),
        resp(200, "Just a moment..."),
    ],
)
def test_robots_unavailable_stops(response: HttpResponse | TransportError) -> None:
    client, transport, _ = make({ROBOTS_URL: [response]})
    with pytest.raises(RobotsUnavailable):
        client.fetch(URL)
    assert len(transport.calls) == 1  # no retry, no page request


def test_robots_counts_in_budget() -> None:
    client, transport, _ = make({URL: [ok()]}, max_requests=1)
    with pytest.raises(BudgetExhausted):
        client.fetch(URL)
    assert [c[1] for c in transport.calls] == [ROBOTS_URL]


@pytest.mark.parametrize(
    "url",
    [
        f"{BASE}index.php?cmd=edit&page=x",
        f"{BASE}index.php?word=abc",
        f"{BASE}NextCard.php?x=1",
        f"{BASE}bbs/thread",
        f"{BASE}index.php/foo",
        f"{BASE}?x",
        f"{BASE}index.php?%E3%82%AB%E3%83%BC%E3%83%89%E6%83%85%E5%A0%B1%E7%B5%9E%E8%BE%BC%E3%81%BF&c=1",
    ],
)
def test_disallowed_urls_skipped_and_never_requested(url: str) -> None:
    client, transport, _ = make({})
    result = client.fetch(url)
    assert isinstance(result, Skipped)
    assert result.reason.startswith("disallowed")
    assert client.allowed(url) == result
    # deny-list URLs are refused by the local gate before robots.txt is even loaded
    expected = [] if local_check(url) else [ROBOTS_URL]
    assert [c[1] for c in transport.calls] == expected


def test_only_http_module_imports_requests() -> None:
    src = Path(__file__).resolve().parent.parent / "src"
    offenders = [
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if any(
            line.startswith(("import requests", "from requests"))
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    ]
    assert offenders == ["bs_database/ingest/http.py"]


@pytest.mark.parametrize(
    "url", ["https://example.com/index.php?x", "http://batspi.com/index.php?x", "/index.php?x"]
)
def test_off_site_urls_skipped_and_never_requested(url: str) -> None:
    client, transport, _ = make({}, with_robots=False)
    result = client.fetch(url)
    assert result == Skipped(url, "disallowed: off-site")
    assert client.allowed(url) == result
    assert transport.calls == []


@pytest.mark.parametrize("value", ["-5", "1.5", "abc", "\u00b2"])
def test_malformed_retry_after_falls_back_to_backoff(value: str) -> None:
    client, transport, _ = make({URL: [resp(429, **{"Retry-After": value}), ok()]})
    assert isinstance(client.fetch(URL), Fetched)
    times = [t for t, _, _ in pages(transport)]
    assert times[1] - times[0] == 8.0


def test_redirect_is_skipped_not_followed() -> None:
    target = f"{BASE}index.php?elsewhere"
    client, transport, _ = make({URL: [resp(301, Location=target)]})
    assert client.fetch(URL) == Skipped(URL, "status 301", 301)
    assert [c[1] for c in pages(transport)] == [URL]


def test_requests_transport_does_not_follow_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[bool] = []

    def send(
        self: requests.Session, request: requests.PreparedRequest, **kw: object
    ) -> requests.Response:
        sent.append(bool(kw.get("allow_redirects")))
        r = requests.Response()
        r.status_code = 301
        r.headers["Location"] = "https://batspi.com/other"
        return r

    monkeypatch.setattr(requests.Session, "send", send)
    out = RequestsTransport().get(BASE, headers={}, timeout=(1.0, 2.0))
    assert out.status == 301
    assert sent == [False]
