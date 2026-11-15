"""Offline tests of the robots.txt, deny-list and challenge logic in ``ingest.policy``."""

import urllib.robotparser
from urllib.parse import quote

import pytest

from bs_database.ingest.policy import (
    BASE_URL,
    StopRun,
    check_allowed,
    is_challenge,
    split_robots,
)

# batspi.com robots.txt as fetched on 2026-11-14 (docs/sources/batspi.md, "Robots policy").
ROBOTS = """User-agent: *
Disallow: /index.php?%E3%82%AB%E3%83%BC%E3%83%89%E6%83%85%E5%A0%B1%E7%B5%9E%E8%BE%BC%E3%81%BF&
Disallow: /?
Disallow: /index.php/

User-agent: bingbot
User-agent: Sogou web spider
User-agent: SemrushBot
User-agent: Baiduspider

Disallow: /
"""


@pytest.fixture(scope="module")
def rules() -> tuple[urllib.robotparser.RobotFileParser, list[str]]:
    lines, prefixes = split_robots(ROBOTS)
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(lines)
    parser.modified()
    return parser, prefixes


def test_split_robots_moves_bare_query_rule() -> None:
    lines, prefixes = split_robots(ROBOTS)
    assert prefixes == ["/?"]
    assert "Disallow: /?" not in lines
    assert "Disallow: /index.php/" in lines


@pytest.mark.parametrize("page", ["ゴラドン", "第一弾", "プロモーションカード"])
def test_card_and_set_pages_allowed(
    rules: tuple[urllib.robotparser.RobotFileParser, list[str]], page: str
) -> None:
    parser, prefixes = rules
    check_allowed(f"{BASE_URL}index.php?{quote(page, safe='')}", parser, prefixes)


@pytest.mark.parametrize(
    "url",
    [
        "https://batspi.com/?cmd=list",
        "https://batspi.com/index.php/foo",
        "https://batspi.com/index.php?%E3%82%AB%E3%83%BC%E3%83%89%E6%83%85%E5%A0%B1%E7%B5%9E%E8%BE%BC%E3%81%BF&color=red",
        "https://batspi.com/index.php?cmd=edit&page=x",
        "https://batspi.com/index.php?plugin=template",
        "https://batspi.com/NextCard.php?mode=0&no=BS01-001",
        "https://batspi.com/bbs/index.php",
    ],
)
def test_disallowed_urls_stop_the_run(
    rules: tuple[urllib.robotparser.RobotFileParser, list[str]], url: str
) -> None:
    parser, prefixes = rules
    with pytest.raises(StopRun):
        check_allowed(url, parser, prefixes)


def test_challenge_detection() -> None:
    assert is_challenge("<title>Just a moment...</title>")
    assert not is_challenge("<pre>スピリット</pre>")


def test_local_check_is_network_free() -> None:
    from bs_database.ingest.policy import local_check

    assert local_check(f"{BASE_URL}index.php?x") is None
    assert local_check("https://example.com/") == "disallowed: off-site"
    reason = local_check(f"{BASE_URL}index.php?cmd=x")
    assert reason is not None and "deny list" in reason
