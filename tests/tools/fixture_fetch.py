"""Fetch batspi.com pages as test fixtures, trim them and record them in the manifest.

Run by hand, never imported by tests. Fetches through the shared ``HttpClient``
(``bs_database.ingest.http``), which enforces ``docs/sources/policy.md``: robots.txt check,
deny list, policy User-Agent, ``BSDB_REQUEST_DELAY`` between requests, stop on a 403 or a
challenge page, no images. Stricter than the policy: no retries (a 429 or 5xx page is
skipped). The manifest is saved even when a run stops early.

Each page is given as ``FILE|PAGE NAME|KIND|CARD TYPE`` (the card type may be empty)::

    uv run python tests/tools/fixture_fetch.py --raw-dir <dir> \\
        "card_brave.html|砲凰竜フェニック・キャノン|card|ブレイヴ"

Raw downloads are kept in ``--raw-dir`` (outside the repo), so a page can be trimmed again
with ``--offline`` and no request. ``--from-cache`` takes the pages from the local scrape cache
(``BSDB_DATA_DIR``) instead: no request either, and no ``--raw-dir`` needed.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup, Comment

from bs_database.ingest.cache import RawCache
from bs_database.ingest.http import HttpClient, Skipped
from bs_database.ingest.policy import BASE_URL as BASE
from bs_database.ingest.policy import StopRun
from bs_database.settings import Settings

HTML_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "html"
STRIP_TAGS = ("script", "style", "noscript", "iframe", "link", "meta")
STRIP_IDS = (
    "menubar",
    "header",
    "footer",
    "navigator",
    "navigator2",
    "toolbar",
    "lastmodified",
)


def page_url(page: str) -> str:
    return f"{BASE}index.php?{quote(page, safe='')}"


def trim(html: str) -> str:
    """Drop scripts, styles, comments and navigation blocks; keep the content DOM unchanged."""
    soup = BeautifulSoup(html, "html.parser")
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()
    for element_id in STRIP_IDS:
        for tag in soup.find_all(id=element_id):
            tag.decompose()
    return str(soup)


def trim_partial(html: str, limit: int) -> str:
    """Keep the leading top-level content of the trimmed page until ``limit`` bytes."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body or soup
    container = body.find(id="body") or body
    kept = 0
    for child in list(container.children):
        kept += len(str(child).encode("utf-8"))
        if kept > limit:
            child.extract()
    return str(soup)


def load_manifest() -> dict[str, Any]:
    path = HTML_DIR / "fixtures.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def save_manifest(manifest: dict[str, Any]) -> None:
    text = json.dumps(dict(sorted(manifest.items())), indent=2, ensure_ascii=False)
    (HTML_DIR / "fixtures.json").write_text(text + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("specs", nargs="+", help="FILE|PAGE NAME|KIND|CARD TYPE")
    parser.add_argument("--raw-dir", type=Path, help="where raw pages are kept")
    parser.add_argument("--offline", action="store_true", help="re-trim from --raw-dir only")
    parser.add_argument(
        "--from-cache", action="store_true", help="read the pages from the scrape cache, no request"
    )
    parser.add_argument("--max-bytes", type=int, default=300_000)
    parser.add_argument("--partial", action="store_true", help="allow partial trimming")
    args = parser.parse_args(argv[1:])

    if args.raw_dir is None and not args.from_cache:
        parser.error("--raw-dir is required unless --from-cache is given")
    cache = RawCache(Settings().cache_dir) if args.from_cache else None
    if args.raw_dir is not None:
        args.raw_dir.mkdir(parents=True, exist_ok=True)
    client = None if args.offline or args.from_cache else HttpClient(Settings(), backoff=())

    manifest = load_manifest()
    try:
        for spec in args.specs:
            name, page, kind, card_type = spec.split("|")
            url = page_url(page)
            if cache is not None:
                cached = cache.load(url, "batspi")
                if cached is None:
                    print(f"skip {page}: not in the cache", file=sys.stderr)
                    continue
                raw = cached.text
                fetched = cached.fetched_at.date().isoformat()
            else:
                raw_path = args.raw_dir / name
                fetched = date.today().isoformat()
            if client is not None:
                result = client.fetch(url)
                if isinstance(result, Skipped):
                    print(f"skip {page}: {result.reason}", file=sys.stderr)
                    continue
                print(f"GET {page} -> {result.status}")
                raw_path.write_bytes(result.content)
            if cache is None:
                raw = raw_path.read_bytes().decode("utf-8")
            trimmed = trim(raw)
            entry: dict[str, Any] = {
                "url": url,
                "fetched": fetched,
                "source": "batspi",
                "kind": kind,
            }
            if card_type:
                entry["card_type"] = card_type
            entry["trimmed"] = True
            if len(trimmed.encode("utf-8")) > args.max_bytes:
                if not args.partial:
                    print(f"error: {name} is over {args.max_bytes} bytes", file=sys.stderr)
                    return 1
                trimmed = trim_partial(trimmed, args.max_bytes - 10_000)
                entry["partial"] = True
            (HTML_DIR / name).write_text(trimmed, encoding="utf-8")
            manifest[name] = entry
            print(f"wrote {name}: {len(trimmed.encode('utf-8')) / 1024:.1f} KB")
    except StopRun as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        save_manifest(manifest)
    print(f"live requests: {client.requests_made if client else 0}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
