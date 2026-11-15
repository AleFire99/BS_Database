"""Shared fakes: a fake clock and a fake batspi.com that serves the cached fixtures."""

import functools
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import pytest

from bs_database.ingest.http import HttpClient, HttpResponse
from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.batspi.index import parse_index
from bs_database.settings import Settings
from bs_database.translate.types import Lang, TranslationResult

HTML_DIR = Path(__file__).parent / "fixtures" / "html"
MANIFEST: dict[str, dict[str, object]] = json.loads(
    (HTML_DIR / "fixtures.json").read_text(encoding="utf-8")
)
ROBOTS_URL = "https://batspi.com/robots.txt"
# batspi.com robots.txt as fetched on 2026-11-14 (docs/sources/batspi.md, "Robots policy").
ROBOTS = """User-agent: *
Disallow: /index.php?%E3%82%AB%E3%83%BC%E3%83%89%E6%83%85%E5%A0%B1%E7%B5%9E%E8%BE%BC%E3%81%BF&
Disallow: /?
Disallow: /index.php/
"""


def fixture_url(name: str) -> str:
    """The URL of a fixture file, e.g. ``fixture_url("set.html")``."""
    return str(MANIFEST[name]["url"])


class Killed(BaseException):
    """Simulates the process being killed: not an ``Exception``, nothing catches it."""


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeSite:
    """A transport serving the fixture pages by URL.

    ``unmapped``: what a URL without a fixture returns, ``"404"`` or ``"fallback"`` (the
    ``card_spirit`` page, so that every card link resolves). ``pages`` and ``overrides`` can be
    edited between runs. ``calls`` lists ``(time, url)`` of every served request;
    ``kill_after`` raises ``Killed`` instead of serving the call after that many.
    """

    def __init__(
        self,
        clock: FakeClock,
        *,
        unmapped: Literal["404", "fallback"] = "404",
        kill_after: int | None = None,
    ) -> None:
        self._clock = clock
        self.unmapped = unmapped
        self.kill_after = kill_after
        self.pages: dict[str, bytes] = {ROBOTS_URL: ROBOTS.encode()}
        for name, meta in MANIFEST.items():
            if name.endswith(".html"):
                self.pages[str(meta["url"])] = (HTML_DIR / name).read_bytes()
        self.overrides: dict[str, HttpResponse] = {}
        self.calls: list[tuple[float, str]] = []

    def get(
        self, url: str, *, headers: Mapping[str, str], timeout: tuple[float, float]
    ) -> HttpResponse:
        if self.kill_after is not None and len(self.calls) >= self.kill_after:
            raise Killed
        self.calls.append((self._clock.monotonic(), url))
        if url in self.overrides:
            return self.overrides[url]
        if url in self.pages:
            return HttpResponse(200, {}, self.pages[url])
        if self.unmapped == "fallback":
            return HttpResponse(200, {}, self.pages[fixture_url("card_spirit.html")])
        return HttpResponse(404, {}, b"not found")

    def urls(self) -> list[str]:
        return [url for _, url in self.calls]


def make_client(settings: Settings, site: FakeSite, clock: FakeClock) -> HttpClient:
    return HttpClient(settings, transport=site, clock=clock)


# Pure parsers memoised across tests: the same fixture HTML is parsed hundreds of times otherwise.
_CACHED_CARD = functools.cache(parse_card_page)
_CACHED_INDEX = functools.cache(parse_index)


def memoise_parsers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the pipeline use memoised (identical) card and index parsers."""
    monkeypatch.setattr("bs_database.ingest.pipeline.parse_card_page", _CACHED_CARD)
    monkeypatch.setattr("bs_database.ingest.pipeline.parse_index", _CACHED_INDEX)


class FakeEngine:
    """A translator that upper-cases and records every call; ``fail`` texts come back failed."""

    name = "fake"

    def __init__(self, fail: frozenset[str] = frozenset()) -> None:
        self.calls: list[list[str]] = []
        self.fail = fail

    def translate(
        self, texts: Sequence[str], *, src: Lang = "jp", tgt: Lang = "en"
    ) -> list[TranslationResult]:
        self.calls.append(list(texts))
        return [
            TranslationResult(None, "failed", self.name)
            if t in self.fail
            else TranslationResult(f"<{t}>", "machine", self.name)
            for t in texts
        ]


class FakeJsonTransport:
    """Scripted JSON POST transport: each entry of ``script`` is a response or an exception.

    When the script is used up, the default answer upper-cases the texts (HTTP 200).
    """

    def __init__(self, script: Sequence[HttpResponse | Exception] = ()) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout: tuple[float, float],
    ) -> HttpResponse:
        self.calls.append({"url": url, "headers": dict(headers), "body": dict(json_body)})
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return ok_response(json_body["text"])


def ok_response(texts: Sequence[str]) -> HttpResponse:
    payload = {
        "translations": [{"detected_source_language": "JA", "text": t.upper()} for t in texts]
    }
    return HttpResponse(200, {}, json.dumps(payload).encode())
