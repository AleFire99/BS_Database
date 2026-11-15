import json
import logging

import pytest
import requests
from fakes import FakeClock, FakeJsonTransport, ok_response
from pydantic import SecretStr

from bs_database.ingest.http import HttpResponse, TransportError
from bs_database.translate.deepl import DeepLTranslator, RequestsJsonTransport

KEY = "test-key:fx"


def engine(
    transport: FakeJsonTransport, key: str = KEY, **kw: object
) -> tuple[DeepLTranslator, FakeClock]:
    clock = FakeClock()
    return DeepLTranslator(SecretStr(key), transport=transport, clock=clock, **kw), clock  # type: ignore[arg-type]


def resp(status: int, headers: dict[str, str] | None = None, body: bytes = b"{}") -> HttpResponse:
    return HttpResponse(status, headers or {}, body)


def test_request_shape_free_key() -> None:
    t = FakeJsonTransport()
    e, _ = engine(t)
    out = e.translate(["こんにちは", "", "あ"])
    assert [r.text for r in out] == ["こんにちは".upper(), None, "あ".upper()]
    assert [r.status for r in out] == ["machine", "pending", "machine"]
    (call,) = t.calls
    assert call["url"] == "https://api-free.deepl.com/v2/translate"
    assert call["headers"]["Authorization"] == f"DeepL-Auth-Key {KEY}"
    assert call["body"] == {
        "text": ["こんにちは", "あ"],
        "source_lang": "JA",
        "target_lang": "EN-US",
    }


def test_pro_key_host_and_reverse_codes() -> None:
    t = FakeJsonTransport()
    e, _ = engine(t, key="test-key")
    e.translate(["a"], src="en", tgt="jp")
    assert t.calls[0]["url"] == "https://api.deepl.com/v2/translate"
    assert t.calls[0]["body"]["source_lang"] == "EN"
    assert t.calls[0]["body"]["target_lang"] == "JA"


def test_batches_split_by_count_and_bytes() -> None:
    t = FakeJsonTransport()
    e, _ = engine(t)
    e.translate([f"t{i}" for i in range(120)])
    assert [len(c["body"]["text"]) for c in t.calls] == [50, 50, 20]
    t2 = FakeJsonTransport()
    e2, _ = engine(t2, batch_bytes=7)
    e2.translate(["あい", "うえ", "お"])  # 6 + 6 bytes > 7 -> split; 6 + 3 > 7 -> split
    assert [c["body"]["text"] for c in t2.calls] == [["あい"], ["うえ"], ["お"]]


def test_429_then_200_uses_backoff() -> None:
    t = FakeJsonTransport([resp(429), ok_response(["a"])])
    e, clock = engine(t)
    assert e.translate(["a"])[0].status == "machine"
    assert clock.now == 2.0 and len(t.calls) == 2


def test_retry_after_is_honoured_and_capped() -> None:
    t = FakeJsonTransport([resp(429, {"Retry-After": "7"}), resp(503, {"retry-after": "9999"})])
    e, clock = engine(t)
    assert e.translate(["a"])[0].status == "machine"
    assert clock.now == 7.0 + 300.0


def test_retries_exhausted_fails_batch_and_continues() -> None:
    t = FakeJsonTransport([resp(500)] * 4)
    e, clock = engine(t, batch_size=1)
    out = e.translate(["a", "b"])
    assert [r.status for r in out] == ["failed", "machine"]
    assert out[0].text is None
    assert clock.now == 2 + 6 + 18 and len(t.calls) == 5


@pytest.mark.parametrize("status", [456, 403, 400])
def test_fatal_status_stops_the_run(status: int, caplog: pytest.LogCaptureFixture) -> None:
    t = FakeJsonTransport([resp(status, {"X-Trace-ID": "abc"})])
    e, _ = engine(t, batch_size=1)
    with caplog.at_level(logging.DEBUG):
        out = e.translate(["a", "b", "c"])
    assert [r.status for r in out] == ["failed"] * 3
    assert len(t.calls) == 1
    assert sum(r.levelno == logging.ERROR for r in caplog.records) == 1
    assert "x-trace-id=abc" in caplog.text
    assert [r.status for r in e.translate(["d"])] == ["failed"]  # still stopped
    assert len(t.calls) == 1


def test_unexpected_status_fails_batch_only() -> None:
    t = FakeJsonTransport([resp(404)])
    e, _ = engine(t, batch_size=1)
    assert [r.status for r in e.translate(["a", "b"])] == ["failed", "machine"]


def test_wrong_count_and_bad_json() -> None:
    t = FakeJsonTransport(
        [ok_response(["only one"]), resp(200, body=b"not json"), resp(200, body=b"[]")]
    )
    e, _ = engine(t, batch_size=2)
    out = e.translate(["a", "b", "c", "d", "e", "f"])
    assert [r.status for r in out] == ["failed"] * 6


def test_transport_error_is_retried() -> None:
    t = FakeJsonTransport([TransportError("timeout", timeout=True)])
    e, clock = engine(t)
    assert e.translate(["a"])[0].status == "machine"
    assert clock.now == 2.0


def test_unsupported_pair() -> None:
    e, _ = engine(FakeJsonTransport())
    with pytest.raises(ValueError):
        e.translate(["a"], src="en", tgt="en")


def test_secret_not_in_repr_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    t = FakeJsonTransport([resp(429), ok_response(["a"]), resp(456)])
    e, _ = engine(t, batch_size=1)
    with caplog.at_level(logging.DEBUG):
        e.translate(["a", "b"])
    assert KEY not in repr(e) and "test-key" not in caplog.text
    assert "test-key" not in repr(e)


class FakeSession:
    def __init__(self, result: object) -> None:
        self.result = result
        self.kwargs: dict[str, object] = {}

    def post(self, url: str, **kwargs: object) -> object:
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_requests_transport_maps_errors_and_hides_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = RequestsJsonTransport()
    fake = FakeSession(requests.Timeout("Authorization: DeepL-Auth-Key SECRET"))
    monkeypatch.setattr(transport, "_session", fake)
    with pytest.raises(TransportError) as ei:
        transport.post("https://x", headers={"A": "b"}, json_body={"text": []}, timeout=(1, 2))
    assert ei.value.timeout and "SECRET" not in str(ei.value)
    fake.result = requests.ConnectionError("boom SECRET")
    with pytest.raises(TransportError) as ei2:
        transport.post("https://x", headers={}, json_body={}, timeout=(1, 2))
    assert not ei2.value.timeout and "SECRET" not in str(ei2.value)


def test_requests_transport_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class R:
        status_code = 200
        headers = {"X": "y"}
        content = json.dumps({"ok": 1}).encode()

    transport = RequestsJsonTransport()
    fake = FakeSession(R())
    monkeypatch.setattr(transport, "_session", fake)
    out = transport.post("https://x", headers={"A": "b"}, json_body={"k": 1}, timeout=(1, 2))
    assert out.status == 200 and out.headers == {"X": "y"}
    assert fake.kwargs["json"] == {"k": 1} and fake.kwargs["allow_redirects"] is False
