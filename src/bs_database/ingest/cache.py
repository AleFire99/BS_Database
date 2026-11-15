"""Raw HTML cache with sidecar metadata (#68), see ``docs/sources/policy.md`` 3.4.

Layout: ``<cache_dir>/<source>/<sha256(url)>.html`` plus ``<same>.json``. The page is stored as
the exact bytes received. The sidecar is written last and is the commit marker: a crash can
leave an html without a sidecar (a miss, overwritten later), never a sidecar without its html.
"""

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

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
