"""Scrape pipeline (#73): index, set pages, card pages, resumable through the state store.

Discovery (index and set pages) is walked again on every run through the cache: free when warm,
refreshed by ``--max-age`` / ``--refresh``. Card pages are worked from the state store, so a
killed run resumes where it stopped and a failed page is retried on a later run. Every store
call is its own transaction; ``StopRun`` ends the run cleanly with the state already committed.
"""

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass

from bs_database.ingest.cache import OFFLINE_REASON, CachedFetcher, CachedPage
from bs_database.ingest.http import TRANSPORT_ERROR_REASON, Skipped
from bs_database.ingest.parsed_store import write_card_json
from bs_database.ingest.policy import StopRun
from bs_database.ingest.report import DiscoveryNote, RunReport
from bs_database.ingest.state import (
    IngestState,
    PageKind,
    PageRecord,
    RetriesExhausted,
    StateStore,
)
from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.batspi.index import parse_index
from bs_database.parsers.batspi.promo_list import parse_promo_list
from bs_database.parsers.batspi.set_page import parse_set_page
from bs_database.parsers.errors import NoCardList, ParseError
from bs_database.parsers.models import IndexProduct, ListEntry, MissingEntry
from bs_database.settings import Settings

log = logging.getLogger(__name__)

SOURCE = "batspi"
# Both equal the manifest form of tests/fixtures/html/fixtures.json (pinned by a test).
INDEX_URL = "https://batspi.com/index.php?カードリスト"
PROMO_URL = "https://batspi.com/index.php?%E3%83%97%E3%83%AD%E3%83%A2%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3%E3%82%AB%E3%83%BC%E3%83%89"

_S = IngestState
_CARD_WORK = frozenset({_S.DISCOVERED, _S.FETCHED, _S.FAILED})
_PERMANENT_STATUSES = frozenset({404, 410})
PARSE_ERROR_PREFIX = "parse error:"


@dataclass(frozen=True)
class RunOptions:
    """``sets``: case-insensitive substrings of the Japanese product name (empty = all).

    ``limit``: maximum card pages taken this run (cache hits count).
    ``retry_failed``: first give a fresh set of attempts to the pages that failed with a
    ``parse error:`` (the cache holds their HTML, so a parser fix can be applied with no request).
    """

    sets: tuple[str, ...] = ()
    limit: int | None = None
    retry_failed: bool = False


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _permanent(skipped: Skipped) -> bool:
    """404 and policy skips cannot be fixed by retrying (policy 3.5: log and skip)."""
    if skipped.status is None:
        if skipped.reason.startswith(OFFLINE_REASON):
            return False
        return not skipped.reason.startswith(TRANSPORT_ERROR_REASON)
    return skipped.status in _PERMANENT_STATUSES


class _Run:
    def __init__(
        self,
        settings: Settings,
        fetcher: CachedFetcher,
        store: StateStore,
        options: RunOptions,
    ) -> None:
        self.settings = settings
        self.fetcher = fetcher
        self.store = store
        self.options = options
        self.report = RunReport()
        self.visited_cards: set[str] = set()

    # -- helpers -----------------------------------------------------------------------

    def obtain(self, url: str) -> CachedPage | Skipped:
        result = self.fetcher.get(url, SOURCE)
        if isinstance(result, CachedPage):
            if result.from_cache:
                self.report.cache_hits += 1
            else:
                self.report.network_pages += 1
        return result

    def fail(self, url: str, reason: str, *, permanent: bool = False) -> None:
        log.warning("failed %s: %s", url, reason)
        self.store.mark_failed(url, reason, permanent=permanent)
        self.report.failures.append((url, reason))

    def fail_skipped(self, url: str, skipped: Skipped) -> None:
        self.fail(url, f"skipped: {skipped.reason}", permanent=_permanent(skipped))

    def revive(self, url: str) -> PageRecord | None:
        """The record of ``url``, a failed one returned to its stage; ``None`` if exhausted."""
        record = self.store.get(url)
        if record.state is _S.FAILED:
            try:
                self.store.retry(url)
            except RetriesExhausted:
                return None
            record = self.store.get(url)
        return record

    # -- discovery ---------------------------------------------------------------------

    def index(self) -> tuple[IndexProduct, ...] | None:
        url = INDEX_URL
        self.store.upsert_discovered(url, PageKind.INDEX)
        record = self.revive(url)
        if record is None:
            self.report.warnings.append(f"index page exhausted its attempts: {url}")
            return None
        page = self.obtain(url)
        if isinstance(page, Skipped):
            if record.state is not _S.PARSED:
                self.fail_skipped(url, page)
            else:
                self.report.warnings.append(f"index revisit failed: {page.reason}")
            return None
        if record.state is _S.DISCOVERED:
            self.store.advance(url, _S.FETCHED, content_sha256=_sha256(page.content))
        try:
            parsed = parse_index(page.text)
        except ParseError as exc:
            if record.state is not _S.PARSED:
                self.fail(url, f"parse error: {exc}")
            else:
                self.report.warnings.append(f"index revisit failed: parse error: {exc}")
            return None
        seen: set[str] = set()
        products: list[IndexProduct] = []
        for product in parsed.products:
            if product.url not in seen:
                seen.add(product.url)
                products.append(product)
                self.store.upsert_discovered(product.url, PageKind.SET)
        self.report.index_missing_pages = len(parsed.missing_pages)
        if record.state is not _S.PARSED:
            self.store.advance(url, _S.PARSED)
        return tuple(products)

    def selected(self, products: tuple[IndexProduct, ...]) -> list[IndexProduct]:
        if not self.options.sets:
            return list(products)
        chosen: list[IndexProduct] = []
        for text in self.options.sets:
            found = [p for p in products if text.casefold() in p.name.casefold()]
            if not found:
                self.report.warnings.append(f"no product matches --set {text}")
            chosen += [p for p in found if p not in chosen]
        return chosen

    def set_page(self, product_url: str, name: str) -> None:
        record = self.revive(product_url)
        if record is None:
            return
        page = self.obtain(product_url)
        done = record.state is _S.PARSED
        if isinstance(page, Skipped):
            if done:
                self.report.warnings.append(f"set revisit failed: {name}: {page.reason}")
            else:
                self.fail_skipped(product_url, page)
            return
        if record.state is _S.DISCOVERED:
            self.store.advance(product_url, _S.FETCHED, content_sha256=_sha256(page.content))
        entries: tuple[ListEntry, ...] = ()
        missing: tuple[MissingEntry, ...] = ()
        unknown: tuple[str, ...] = ()
        try:
            if product_url == PROMO_URL:
                promo = parse_promo_list(page.text)
                entries, missing, unknown = promo.entries, promo.missing, promo.unknown_numbers
            else:
                parsed = parse_set_page(page.text)
                entries, missing, unknown = parsed.entries, parsed.missing, parsed.unknown_numbers
        except NoCardList:
            self.report.sets_without_cards.append(name)
        except ParseError as exc:
            if done:
                self.report.warnings.append(f"set revisit failed: {name}: parse error: {exc}")
            else:
                self.fail(product_url, f"parse error: {exc}")
            return
        for entry in entries:
            self.store.upsert_discovered(entry.url, PageKind.CARD)
            self.visited_cards.add(entry.url)
        if unknown or missing:
            log.warning(
                "%s: %d unknown numbers, %d without a page", name, len(unknown), len(missing)
            )
            self.report.notes.append(DiscoveryNote(name, unknown, len(missing)))
        if not done:
            self.store.advance(product_url, _S.PARSED)

    def sets(self, products: tuple[IndexProduct, ...] | None) -> None:
        if products is None:
            if self.options.sets:
                self.report.warnings.append("index unavailable: --set cannot be applied")
                return
            pending = self.store.iter_pending(kind=PageKind.SET)
            for record in pending:
                self.set_page(record.url, record.url)
            return
        for product in self.selected(products):
            self.set_page(product.url, product.name)

    # -- cards -------------------------------------------------------------------------

    def cards(self) -> None:
        pending = [r for r in self.store.iter_pending(kind=PageKind.CARD) if r.state in _CARD_WORK]
        if self.options.sets:
            pending = [r for r in pending if r.url in self.visited_cards]
        for record in pending[: self.options.limit]:
            self.card(record.url)

    def card(self, url: str) -> None:
        record = self.revive(url)
        if record is None:  # pragma: no cover (iter_pending never lists exhausted pages)
            return
        page = self.obtain(url)
        if isinstance(page, Skipped):
            self.fail_skipped(url, page)
            return
        if record.state is _S.DISCOVERED:
            self.store.advance(url, _S.FETCHED, content_sha256=_sha256(page.content))
        try:
            card = parse_card_page(page.text, url)
        except ParseError as exc:
            self.fail(url, f"parse error: {exc}")
            return
        write_card_json(self.settings.parsed_dir, card, page)
        self.store.advance(url, _S.PARSED)
        self.report.cards_parsed += 1

    # -- run ---------------------------------------------------------------------------

    def run(self) -> None:
        if self.options.retry_failed:
            n = self.store.reset_failed(prefix=PARSE_ERROR_PREFIX)
            log.info("retry-failed: %d pages with a parse error get new attempts", n)
        products = self.index()
        self.sets(products)
        self.cards()


def run_pipeline(
    settings: Settings,
    fetcher: CachedFetcher,
    store: StateStore,
    *,
    requests_made: Callable[[], int] = lambda: 0,
    options: RunOptions = RunOptions(),  # noqa: B008 (frozen dataclass)
) -> RunReport:
    """Run the three phases once and return the report.

    ``StopRun`` (budget, block, robots, Retry-After) ends the run normally with the state
    committed; any other exception propagates and the state stays resumable.
    """
    run = _Run(settings, fetcher, store, options)
    try:
        run.run()
    except StopRun as exc:
        log.warning("run stopped: %s: %s", type(exc).__name__, exc)
        run.report.stop = exc
    report = run.report
    report.requests_made = requests_made()
    report.counts = store.counts()
    report.exhausted = store.iter_exhausted()
    others = sum(n for state, n in report.counts.items()) - 1  # all rows but the index
    report.index_unobtainable = (
        store.get(INDEX_URL).state is not _S.PARSED and others <= 0 and report.stop is None
    )
    return report
