"""Polite client for the fandom wiki ``api.php`` (names only, ADR 0009, #104).

``robots.txt`` of the wiki is behind a Cloudflare challenge, so instead of reading it this client
uses a fixed allow-list: only ``https://battle-spirits.fandom.com/api.php`` with
``action=query``. Everything else raises ``ValueError``. Pacing, budget and backoff mirror
``HttpClient`` (serial, ``request_delay``, ``max_requests``); a 403 or a challenge page stops the
run (``Blocked``), no bypass. Raw JSON answers are cached (source ``fandom``) and a cache hit
costs no request.
"""

import json
import logging
import re
from collections.abc import Iterator, Mapping
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from bs_database.ingest.cache import RawCache
from bs_database.ingest.http import (
    MAX_RETRY_AFTER,
    RETRY_STATUSES,
    Blocked,
    BudgetExhausted,
    Clock,
    HttpResponse,
    RequestsTransport,
    RetryAfterTooLong,
    SystemClock,
    Transport,
    TransportError,
)
from bs_database.ingest.policy import StopRun, is_challenge
from bs_database.settings import Settings

log = logging.getLogger(__name__)

API_URL = "https://battle-spirits.fandom.com/api.php"
CACHE_SOURCE = "fandom"
BATCH_SIZE = 50
CATEGORY_LIMIT = 500


class FandomError(StopRun):
    """An answer the client cannot use (bad status, retries exhausted, not JSON)."""


def _check_url(url: str) -> None:
    """The allow-list: ``api.php?...action=query...`` on the fandom host, nothing else."""
    if not url.startswith(f"{API_URL}?"):
        raise ValueError(f"disallowed fandom url: {url}")
    if parse_qs(urlsplit(url).query).get("action") != ["query"]:
        raise ValueError(f"disallowed fandom action (only action=query): {url}")


def _retry_after(resp: HttpResponse) -> float | None:
    for key, value in resp.headers.items():
        if key.lower() == "retry-after" and re.fullmatch(r"\d+", value.strip()):
            return float(value.strip())
    return None


class FandomApi:
    def __init__(
        self,
        settings: Settings,
        transport: Transport | None = None,
        clock: Clock | None = None,
        cache: RawCache | None = None,
        *,
        backoff: tuple[float, ...] = (5.0, 15.0, 45.0),
    ) -> None:
        self._settings = settings
        self._transport: Transport = transport or RequestsTransport()
        self._clock: Clock = clock or SystemClock()
        self._cache = cache if cache is not None else RawCache(settings.cache_dir)
        self._backoff = backoff
        self._last_request: float | None = None
        self.requests_made = 0

    # -- network ---------------------------------------------------------------------------

    def _request(self, url: str) -> HttpResponse:
        if self.requests_made >= self._settings.max_requests:
            raise BudgetExhausted(f"request budget of {self._settings.max_requests} used up")
        if self._last_request is not None:
            wait = self._last_request + self._settings.request_delay - self._clock.monotonic()
            if wait > 0:
                self._clock.sleep(wait)
        self.requests_made += 1
        try:
            return self._transport.get(
                url,
                headers={"User-Agent": self._settings.user_agent},
                timeout=(self._settings.connect_timeout, self._settings.read_timeout),
            )
        finally:
            self._last_request = self._clock.monotonic()

    def _fetch(self, url: str) -> bytes:
        for attempt in range(len(self._backoff) + 1):
            try:
                resp = self._request(url)
            except TransportError as exc:
                reason, retry_after = f"transport error: {exc}", None
            else:
                body_is_json = resp.content.lstrip().startswith(b"{")
                if resp.status == 403 or (not body_is_json and is_challenge(resp.text)):
                    raise Blocked(f"403 or challenge page: {url}")
                if resp.status == 200:
                    if not body_is_json:
                        raise FandomError(f"answer is not JSON: {url}")
                    return resp.content
                if resp.status not in RETRY_STATUSES:
                    raise FandomError(f"status {resp.status}: {url}")
                reason, retry_after = f"status {resp.status}", _retry_after(resp)
                if retry_after is not None and retry_after > MAX_RETRY_AFTER:
                    raise RetryAfterTooLong(f"Retry-After {retry_after:g} s: {url}")
            if attempt == len(self._backoff):
                raise FandomError(f"{reason}, retries exhausted: {url}")
            wait = self._backoff[attempt]
            if retry_after is not None:
                wait = max(wait, retry_after)
            log.info("retry %s in %g s: %s", url, wait, reason)
            self._clock.sleep(wait)
            self._last_request = self._clock.monotonic()
        raise AssertionError("unreachable")  # pragma: no cover

    def get_json(self, url: str) -> dict[str, Any]:
        """Cache first (0 requests on a hit), then the network; the allow-list applies always."""
        _check_url(url)
        page = self._cache.load(url, CACHE_SOURCE)
        if page is not None:
            content = page.content
        else:
            content = self._fetch(url)
            self._cache.store(url, CACHE_SOURCE, content, {})
        try:
            data = json.loads(content)
        except ValueError as exc:
            raise FandomError(f"answer is not valid JSON: {url}") from exc
        if not isinstance(data, dict):
            raise FandomError(f"unexpected JSON shape: {url}")
        return data

    def _pages(self, params: Mapping[str, str]) -> Iterator[dict[str, Any]]:
        """Every answer of a query, following MediaWiki's ``continue`` blocks."""
        extra: dict[str, str] = {}
        while True:
            url = f"{API_URL}?{urlencode({**params, **extra})}"
            data = self.get_json(url)
            yield data
            cont = data.get("continue")
            if not isinstance(cont, dict) or not cont:
                return
            extra = {str(k): str(v) for k, v in cont.items()}

    # -- queries ---------------------------------------------------------------------------

    def category_members(self, category: str) -> list[str]:
        """Titles of the pages in ``category`` (e.g. ``Category:Family``)."""
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmlimit": str(CATEGORY_LIMIT),
            "cmnamespace": "0",
            "format": "json",
        }
        titles: list[str] = []
        for data in self._pages(params):
            members = data.get("query", {}).get("categorymembers", [])
            titles.extend(m["title"] for m in members if isinstance(m.get("title"), str))
        return titles

    def wikitext(self, titles: list[str]) -> dict[str, str]:
        """Current wikitext per title, fetched in batches of ``BATCH_SIZE``."""
        out: dict[str, str] = {}
        for start in range(0, len(titles), BATCH_SIZE):
            params = {
                "action": "query",
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "format": "json",
                "titles": "|".join(titles[start : start + BATCH_SIZE]),
            }
            for data in self._pages(params):
                pages = data.get("query", {}).get("pages", {})
                for page in pages.values() if isinstance(pages, dict) else pages:
                    text = _content(page)
                    if text is not None and isinstance(page.get("title"), str):
                        out[page["title"]] = text
        return out


def _content(page: Mapping[str, Any]) -> str | None:
    revisions = page.get("revisions")
    if not revisions:
        return None
    main = revisions[0].get("slots", {}).get("main", {})
    text = main.get("*", main.get("content"))
    return text if isinstance(text, str) else None
