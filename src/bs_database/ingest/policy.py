"""Scraping policy helpers (R1-R8, #66), see ``docs/sources/policy.md``."""

import urllib.robotparser

BASE_URL = "https://batspi.com/"
USER_AGENT = "bs-database/0.2.0 (+https://github.com/AleFire99/BS_Database)"
DENY_MARKERS = ("cmd=", "plugin=", "word=", "NextCard.php", "bbs/")
CHALLENGE_MARKERS = ("Just a moment", "cf-chl", "challenge-platform", "cf-browser-verification")


class StopRun(Exception):
    """Raised when the policy requires the run to stop."""


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
    rest = url.removeprefix(BASE_URL.rstrip("/"))
    if any(rest.startswith(prefix) for prefix in query_prefixes):
        raise StopRun(f"robots.txt disallows: {url}")
    if not robots.can_fetch(USER_AGENT, url):
        raise StopRun(f"robots.txt disallows: {url}")


def is_challenge(text: str) -> bool:
    return any(marker in text for marker in CHALLENGE_MARKERS)
