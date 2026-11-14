"""Fetch batspi.com pages as test fixtures, trim them and record them in the manifest.

Run by hand, never imported by tests. Follows ``docs/sources/policy.md``: robots.txt check,
deny list, policy User-Agent, at least 3 s between requests, stop on a 403 or a challenge page,
no images.

Each page is given as ``FILE|PAGE NAME|KIND|CARD TYPE`` (the card type may be empty)::

    uv run python tests/tools/fixture_fetch.py --raw-dir <dir> \\
        "card_brave.html|砲凰竜フェニック・キャノン|card|ブレイヴ"

Raw downloads are kept in ``--raw-dir`` (outside the repo), so a page can be trimmed again
with ``--offline`` and no request.
"""

import argparse
import json
import sys
import time
import urllib.robotparser
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup, Comment

BASE = "https://batspi.com/"
USER_AGENT = "bs-database/0.2.0 (+https://github.com/AleFire99/BS_Database)"
DELAY = 3.0
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
DENY_MARKERS = ("cmd=", "plugin=", "word=", "NextCard.php", "bbs/")
CHALLENGE_MARKERS = ("Just a moment", "cf-chl", "challenge-platform", "cf-browser-verification")


class StopRun(Exception):
    """Raised when the policy requires the run to stop."""


def page_url(page: str) -> str:
    return f"{BASE}index.php?{quote(page, safe='')}"


def split_robots(text: str) -> tuple[list[str], list[str]]:
    """Return ``(lines for urllib.robotparser, raw Disallow prefixes ending in "?")``.

    ``urllib.robotparser`` normalises the rule ``/?`` to ``/`` and would block the whole site,
    so such rules are checked here by plain prefix match instead.
    """
    lines: list[str] = []
    prefixes: list[str] = []
    for line in text.splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        if key.strip().lower() == "disallow" and value.endswith("?") and "&" not in value:
            prefixes.append(value)
        else:
            lines.append(line)
    return lines, prefixes


def check_allowed(
    url: str, robots: urllib.robotparser.RobotFileParser, query_prefixes: list[str]
) -> None:
    if any(marker in url for marker in DENY_MARKERS):
        raise StopRun(f"deny list: {url}")
    rest = url.removeprefix(BASE.rstrip("/"))
    if any(rest.startswith(prefix) for prefix in query_prefixes):
        raise StopRun(f"robots.txt disallows: {url}")
    if not robots.can_fetch(USER_AGENT, url):
        raise StopRun(f"robots.txt disallows: {url}")


def is_challenge(text: str) -> bool:
    return any(marker in text for marker in CHALLENGE_MARKERS)


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
    parser.add_argument("--raw-dir", type=Path, required=True, help="where raw pages are kept")
    parser.add_argument("--offline", action="store_true", help="re-trim from --raw-dir only")
    parser.add_argument("--max-bytes", type=int, default=300_000)
    parser.add_argument("--partial", action="store_true", help="allow partial trimming")
    args = parser.parse_args(argv[1:])

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    robots = urllib.robotparser.RobotFileParser()
    requests_made = 0
    query_prefixes: list[str] = []
    if not args.offline:
        resp = session.get(f"{BASE}robots.txt", timeout=30)
        requests_made += 1
        print(f"GET robots.txt -> {resp.status_code}")
        if resp.status_code != 200:
            print("error: robots.txt not fetched, stopping", file=sys.stderr)
            return 1
        robot_lines, query_prefixes = split_robots(resp.text)
        robots.parse(robot_lines)
        robots.modified()

    manifest = load_manifest()
    for spec in args.specs:
        name, page, kind, card_type = spec.split("|")
        url = page_url(page)
        raw_path = args.raw_dir / name
        if not args.offline:
            try:
                check_allowed(url, robots, query_prefixes)
            except StopRun as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            time.sleep(DELAY)
            resp = session.get(url, timeout=30)
            requests_made += 1
            print(f"GET {page} -> {resp.status_code}")
            if resp.status_code == 403 or is_challenge(resp.text):
                print("error: 403 or challenge page, stopping", file=sys.stderr)
                return 1
            if resp.status_code != 200:
                print(f"skip {page}: status {resp.status_code}", file=sys.stderr)
                continue
            raw_path.write_bytes(resp.content)
        raw = raw_path.read_bytes().decode("utf-8")
        trimmed = trim(raw)
        entry: dict[str, Any] = {
            "url": url,
            "fetched": date.today().isoformat(),
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
    save_manifest(manifest)
    print(f"live requests: {requests_made}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
