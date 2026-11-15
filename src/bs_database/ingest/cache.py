"""Raw HTML cache with sidecar metadata (#68), see ``docs/sources/policy.md`` 3.4.

Layout: ``<cache_dir>/<source>/<sha256(url)>.html`` plus ``<same>.json``. The page is stored as
the exact bytes received. The sidecar is written last and is the commit marker: a crash can
leave an html without a sidecar (a miss, overwritten later), never a sidecar without its html.
"""

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bs_database.ingest.http import Fetched, Fetcher, Skipped

CACHED_STATUS = 200


@dataclass(frozen=True)
class CachedPage:
    url: str
    source: str
    content: bytes
    status: int
    fetched_at: datetime
    from_cache: bool
    etag: str | None = None
    last_modified: str | None = None

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` via a same-directory temp file, fsync, then ``os.replace``."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with tmp.open("wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


class RawCache:
    """On-disk store of raw pages; knows nothing about the network."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def paths(self, url: str, source: str) -> tuple[Path, Path]:
        """``(html path, sidecar path)``; the url is hashed exactly as given."""
        stem = hashlib.sha256(url.encode("utf-8")).hexdigest()
        base = self.root / source
        return base / f"{stem}.html", base / f"{stem}.json"

    def store(
        self,
        url: str,
        source: str,
        content: bytes,
        headers: Mapping[str, str],
        *,
        fetched_at: datetime | None = None,
    ) -> CachedPage:
        html, sidecar = self.paths(url, source)
        html.parent.mkdir(parents=True, exist_ok=True)
        when = fetched_at or datetime.now(UTC)
        etag = _header(headers, "etag")
        last_modified = _header(headers, "last-modified")
        meta = {
            "url": url,
            "fetched_at": when.isoformat(),
            "status": CACHED_STATUS,
            "etag": etag,
            "last_modified": last_modified,
        }
        sidecar.unlink(missing_ok=True)  # no stale sidecar next to a new html
        _atomic_write(html, content)
        _atomic_write(sidecar, json.dumps(meta, indent=2).encode("utf-8"))
        return CachedPage(url, source, content, CACHED_STATUS, when, False, etag, last_modified)

    def load(self, url: str, source: str) -> CachedPage | None:
        """The valid entry for ``url`` or ``None`` (orphans, corrupt or mismatched = miss)."""
        html, sidecar = self.paths(url, source)
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            content = html.read_bytes()
            if (
                not isinstance(meta, dict)
                or meta.get("status") != CACHED_STATUS
                or meta.get("url") != url
            ):
                return None
            fetched_at = datetime.fromisoformat(meta["fetched_at"])
            etag, last_modified = meta.get("etag"), meta.get("last_modified")
            if not all(v is None or isinstance(v, str) for v in (etag, last_modified)):
                return None
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        return CachedPage(
            url, source, content, CACHED_STATUS, fetched_at, True, etag, last_modified
        )


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CachedFetcher:
    """A ``Fetcher`` behind the disk cache; the one entry point for the pipeline (#73).

    Lookup order: the network-free local gate (off-site, deny list) on every call; a valid,
    fresh entry is returned with no network at all (not even robots.txt); on a miss ``fetch``
    applies the full gate. Only status-200 pages are stored; ``Skipped`` and ``StopRun`` pass
    through untouched and write nothing.
    """

    def __init__(
        self,
        fetcher: Fetcher,
        cache: RawCache,
        *,
        refresh: bool = False,
        max_age: timedelta | None = None,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._fetcher = fetcher
        self._cache = cache
        self._refresh = refresh
        self._max_age = max_age
        self._now = now

    def _fresh(self, page: CachedPage) -> bool:
        return self._max_age is None or self._now() - page.fetched_at <= self._max_age

    def get(self, url: str, source: str = "batspi") -> CachedPage | Skipped:
        if (skipped := self._fetcher.local_gate(url)) is not None:
            return skipped
        page = None if self._refresh else self._cache.load(url, source)
        if page is not None and self._fresh(page):
            return page
        result = self._fetcher.fetch(url)
        if isinstance(result, Skipped):
            return result
        return self._store(result, source)

    def _store(self, fetched: Fetched, source: str) -> CachedPage:
        return self._cache.store(
            fetched.url, source, fetched.content, fetched.headers, fetched_at=self._now()
        )
