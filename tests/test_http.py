from collections.abc import Mapping

import pytest
import requests

from bs_database.ingest.http import (
    BudgetExhausted,
    Fetched,
    HttpClient,
    HttpResponse,
    RequestsTransport,
    Skipped,
    TransportError,
)
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


def ok(body: str = "<html>ok</html>") -> HttpResponse:
    return HttpResponse(200, {}, body.encode())


def make(
    script: Mapping[str, list[HttpResponse | TransportError]], max_requests: int = 1000
) -> tuple[HttpClient, FakeTransport, FakeClock]:
    clock = FakeClock()
    transport = FakeTransport(clock, script)
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, request_delay=3.0, max_requests=max_requests
    )
    return HttpClient(settings, transport=transport, clock=clock), transport, clock


def test_user_agent_on_every_call() -> None:
    urls = [f"{BASE}index.php?p{i}" for i in range(3)]
    client, transport, _ = make({u: [ok()] for u in urls})
    for u in urls:
        assert isinstance(client.fetch(u), Fetched)
    assert len(transport.calls) == 3
    for _, _, headers in transport.calls:
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
    times = [t for t, _, _ in transport.calls]
    assert len(times) == 20
    assert all(b - a >= 3.0 for a, b in zip(times, times[1:], strict=False))


def test_budget_stops_cleanly() -> None:
    urls = [f"{BASE}index.php?p{i}" for i in range(5)]
    client, transport, _ = make({u: [ok()] for u in urls}, max_requests=3)
    for u in urls[:3]:
        assert isinstance(client.fetch(u), Fetched)
    with pytest.raises(BudgetExhausted):
        client.fetch(urls[3])
    assert client.requests_made == 3
    assert len(transport.calls) == 3


def test_non_200_is_skipped() -> None:
    url = f"{BASE}index.php?gone"
    client, _, _ = make({url: [HttpResponse(404, {}, b"")]})
    assert client.fetch(url) == Skipped(url, "status 404", 404)


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
    [(requests.Timeout("t"), True), (requests.ConnectionError("c"), False)],
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
