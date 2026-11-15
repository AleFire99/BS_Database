"""The DeepL engine (#94, ADR 0008): ``POST /v2/translate`` with retries and quota handling.

Only this module knows DeepL's language codes. The API key is a ``SecretStr``: it is read
only to build the ``Authorization`` header and never appears in a log, exception or repr.
"""

import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import requests
from pydantic import SecretStr

from bs_database.ingest.http import (
    RETRY_STATUSES,
    Clock,
    HttpResponse,
    SystemClock,
    TransportError,
)
from bs_database.translate.types import Lang, TranslationResult, check_pair

log = logging.getLogger(__name__)

FREE_HOST = "https://api-free.deepl.com"
PRO_HOST = "https://api.deepl.com"
_SOURCE_CODES = {"jp": "JA", "en": "EN"}
_TARGET_CODES = {"jp": "JA", "en": "EN-US"}
_RETRY_STATUSES = RETRY_STATUSES | {529}
_STOP_STATUSES = {400: "invalid request", 403: "authentication failed", 456: "quota exhausted"}
MAX_BATCH_TEXTS = 50
MAX_BATCH_BYTES = 100 * 1024  # DeepL's cap is 128 KiB
MAX_RETRY_AFTER = 300.0


class JsonTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout: tuple[float, float],
    ) -> HttpResponse: ...


class RequestsJsonTransport:
    """The only class that POSTs through ``requests`` (policy R1, "batspi traffic only")."""

    def __init__(self) -> None:
        self._session = requests.Session()

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout: tuple[float, float],
    ) -> HttpResponse:
        try:
            resp = self._session.post(
                url, headers=dict(headers), json=json_body, timeout=timeout, allow_redirects=False
            )
        except requests.Timeout as exc:
            raise TransportError(type(exc).__name__, timeout=True) from None
        except requests.RequestException as exc:
            # the message is dropped on purpose: it could echo request details
            raise TransportError(type(exc).__name__) from None
        return HttpResponse(resp.status_code, dict(resp.headers), resp.content)


def _header(resp: HttpResponse, name: str) -> str | None:
    for key, value in resp.headers.items():
        if key.lower() == name:
            return value
    return None


def _retry_after(resp: HttpResponse) -> float | None:
    value = _header(resp, "retry-after")
    if value is not None and re.fullmatch(r"\d+", value.strip()):
        return min(float(value.strip()), MAX_RETRY_AFTER)
    return None


class DeepLTranslator:
    name = "deepl"

    def __init__(
        self,
        api_key: SecretStr,
        *,
        transport: JsonTransport | None = None,
        clock: Clock | None = None,
        backoff: tuple[float, ...] = (2.0, 6.0, 18.0),
        batch_size: int = MAX_BATCH_TEXTS,
        batch_bytes: int = MAX_BATCH_BYTES,
        timeouts: tuple[float, float] = (10.0, 30.0),
    ) -> None:
        self._key = api_key
        host = FREE_HOST if api_key.get_secret_value().endswith(":fx") else PRO_HOST
        self._url = f"{host}/v2/translate"
        self._transport: JsonTransport = transport or RequestsJsonTransport()
        self._clock: Clock = clock or SystemClock()
        self._backoff = backoff
        self._batch_size = batch_size
        self._batch_bytes = batch_bytes
        self._timeouts = timeouts
        self._stopped = False

    def __repr__(self) -> str:
        return f"DeepLTranslator(url={self._url!r})"

    def _batches(self, texts: Sequence[str]) -> list[list[str]]:
        batches: list[list[str]] = []
        current: list[str] = []
        size = 0
        for t in texts:
            n = len(t.encode("utf-8"))
            if current and (len(current) >= self._batch_size or size + n > self._batch_bytes):
                batches.append(current)
                current, size = [], 0
            current.append(t)
            size += n
        if current:
            batches.append(current)
        return batches

    def _post(self, body: Mapping[str, Any]) -> HttpResponse | None:
        """One request with retries; None when the retries ran out."""
        headers = {
            "Authorization": f"DeepL-Auth-Key {self._key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        for attempt in range(len(self._backoff) + 1):
            try:
                resp = self._transport.post(
                    self._url, headers=headers, json_body=body, timeout=self._timeouts
                )
            except TransportError as exc:
                log.warning("deepl transport error: %s", exc)
                resp = None
            if resp is not None and resp.status not in _RETRY_STATUSES:
                return resp
            if attempt < len(self._backoff):
                wait = self._backoff[attempt]
                if resp is not None:
                    wait = _retry_after(resp) or wait
                    log.warning("deepl status %d, retrying in %.0fs", resp.status, wait)
                self._clock.sleep(wait)
        return None

    def _send(self, batch: list[str], src: Lang, tgt: Lang) -> list[str] | None:
        """Translations of one batch; None means the batch failed."""
        body = {
            "text": batch,
            "source_lang": _SOURCE_CODES[src],
            "target_lang": _TARGET_CODES[tgt],
        }
        resp = self._post(body)
        if resp is None:
            log.warning("deepl: retries exhausted, batch of %d failed", len(batch))
            return None
        trace = _header(resp, "x-trace-id")
        if trace:
            log.debug("deepl x-trace-id=%s status=%d", trace, resp.status)
        if resp.status in _STOP_STATUSES:
            self._stopped = True
            log.error(
                "deepl stopped for this run: %s (HTTP %d); remaining texts failed",
                _STOP_STATUSES[resp.status],
                resp.status,
            )
            return None
        if resp.status != 200:
            log.warning("deepl: unexpected HTTP %d, batch of %d failed", resp.status, len(batch))
            return None
        try:
            items = json.loads(resp.content)["translations"]
            out = [str(item["text"]) for item in items]
        except (ValueError, KeyError, TypeError):
            log.warning("deepl: unreadable response, batch of %d failed", len(batch))
            return None
        if len(out) != len(batch):
            log.warning("deepl: got %d translations for %d texts", len(out), len(batch))
            return None
        return out

    def translate(
        self, texts: Sequence[str], *, src: Lang = "jp", tgt: Lang = "en"
    ) -> list[TranslationResult]:
        check_pair(src, tgt)
        failed = TranslationResult(None, "failed", self.name)
        results: dict[int, TranslationResult] = {}
        indexed = [(i, t) for i, t in enumerate(texts) if t.strip()]
        pos = 0
        for batch in self._batches([t for _, t in indexed]):
            ids = [i for i, _ in indexed[pos : pos + len(batch)]]
            pos += len(batch)
            out = None if self._stopped else self._send(batch, src, tgt)
            for k, i in enumerate(ids):
                results[i] = (
                    failed if out is None else TranslationResult(out[k], "machine", self.name)
                )
        return [
            results.get(i, TranslationResult(None, "pending", self.name)) for i in range(len(texts))
        ]
