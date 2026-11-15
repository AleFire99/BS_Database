"""HTTP client with the policy gate (R1-R8, #67), see ``docs/sources/policy.md``.

This is the only module that imports ``requests`` (R1). Everything is serial: one request at
a time, paced by ``Settings.request_delay`` and capped by ``Settings.max_requests``.
"""

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

import requests

from bs_database.ingest.policy import StopRun, is_challenge
from bs_database.settings import Settings

log = logging.getLogger(__name__)


class BudgetExhausted(StopRun):
    """The per-run request budget is used up: a clean stop, resume on the next run."""


class Blocked(StopRun):
    """A 403 or a challenge page: the site blocks us, stop the run (policy 3.5)."""


class RetryAfterTooLong(StopRun):
    """The server asks to wait longer than ``MAX_RETRY_AFTER`` seconds."""


MAX_RETRY_AFTER = 300
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class TransportError(Exception):
    """A network failure (timeout, connection error) reported by a ``Transport``."""

    def __init__(self, message: str, *, timeout: bool = False) -> None:
        super().__init__(message)
        self.timeout = timeout


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    content: bytes

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class Transport(Protocol):
    def get(
        self, url: str, *, headers: Mapping[str, str], timeout: tuple[float, float]
    ) -> HttpResponse: ...


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class RequestsTransport:
    """The only class that talks to ``requests``; redirects are never followed."""

    def __init__(self) -> None:
        self._session = requests.Session()

    def get(
        self, url: str, *, headers: Mapping[str, str], timeout: tuple[float, float]
    ) -> HttpResponse:
        try:
            resp = self._session.get(
                url, headers=dict(headers), timeout=timeout, allow_redirects=False
            )
        except requests.Timeout as exc:
            raise TransportError(str(exc), timeout=True) from exc
        except requests.ConnectionError as exc:
            raise TransportError(str(exc)) from exc
        return HttpResponse(resp.status_code, dict(resp.headers), resp.content)


@dataclass(frozen=True)
class Fetched:
    url: str
    status: int
    content: bytes
    headers: Mapping[str, str]

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class Skipped:
    """A URL that was not fetched; the run goes on."""

    url: str
    reason: str
    status: int | None = None


class Fetcher(Protocol):
    def allowed(self, url: str) -> Skipped | None: ...

    def fetch(self, url: str) -> Fetched | Skipped: ...


class HttpClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: Transport | None = None,
        clock: Clock | None = None,
        backoff: tuple[float, ...] = (5.0, 15.0, 45.0),
    ) -> None:
        self._settings = settings
        self._backoff = backoff
        self._transport: Transport = transport or RequestsTransport()
        self._clock: Clock = clock or SystemClock()
        self._last_request: float | None = None
        self.requests_made = 0

    def _request(self, url: str) -> HttpResponse:
        """One paced, budgeted, network request. Raises ``TransportError`` on failure."""
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

    @staticmethod
    def _retry_after(resp: HttpResponse) -> float | None:
        """``Retry-After`` in integer seconds; an HTTP-date (or junk) is ignored."""
        for key, value in resp.headers.items():
            if key.lower() == "retry-after" and value.strip().isdigit():
                return float(value.strip())
        return None

    def _wait(self, seconds: float) -> None:
        """Back off; the delay then counts from the end of the backoff ("on top")."""
        self._clock.sleep(seconds)
        self._last_request = self._clock.monotonic()

    def fetch(self, url: str) -> Fetched | Skipped:
        """Fetch one URL with retries; may raise ``Blocked``, ``RetryAfterTooLong``, ``StopRun``."""
        for attempt in range(len(self._backoff) + 1):
            try:
                resp = self._request(url)
            except TransportError as exc:
                reason, status, retry_after = f"transport error: {exc}", None, None
            else:
                if resp.status == 403 or is_challenge(resp.text):
                    raise Blocked(f"403 or challenge page: {url}")
                if resp.status == 200:
                    return Fetched(url, resp.status, resp.content, resp.headers)
                if resp.status not in RETRY_STATUSES:
                    log.warning("skip %s: status %s", url, resp.status)
                    return Skipped(url, f"status {resp.status}", resp.status)
                reason, status = f"status {resp.status}", resp.status
                retry_after = self._retry_after(resp)
                if retry_after is not None and retry_after > MAX_RETRY_AFTER:
                    raise RetryAfterTooLong(f"Retry-After {retry_after:g} s: {url}")
            if attempt == len(self._backoff):
                log.warning("skip %s: %s, retries exhausted", url, reason)
                return Skipped(url, reason, status)
            wait = self._backoff[attempt]
            if retry_after is not None:
                wait = max(wait, retry_after)
            log.info("retry %s in %g s: %s", url, wait, reason)
            self._wait(wait)
        raise AssertionError("unreachable")  # pragma: no cover
