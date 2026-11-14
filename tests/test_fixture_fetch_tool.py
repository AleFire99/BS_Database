"""Offline tests of the robots.txt and deny-list logic in ``tests/tools/fixture_fetch.py``."""

import importlib.util
import urllib.robotparser
from pathlib import Path
from types import ModuleType

import pytest

TOOL = Path(__file__).parent / "tools" / "fixture_fetch.py"

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


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fixture_fetch", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    return load_tool()


@pytest.fixture(scope="module")
def rules(tool: ModuleType) -> tuple[urllib.robotparser.RobotFileParser, list[str]]:
    lines, prefixes = tool.split_robots(ROBOTS)
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(lines)
    parser.modified()
    return parser, prefixes


def test_split_robots_moves_bare_query_rule(tool: ModuleType) -> None:
    lines, prefixes = tool.split_robots(ROBOTS)
    assert prefixes == ["/?"]
    assert "Disallow: /?" not in lines
    assert "Disallow: /index.php/" in lines


@pytest.mark.parametrize("page", ["ゴラドン", "第一弾", "プロモーションカード"])
def test_card_and_set_pages_allowed(
    tool: ModuleType, rules: tuple[urllib.robotparser.RobotFileParser, list[str]], page: str
) -> None:
    parser, prefixes = rules
    tool.check_allowed(tool.page_url(page), parser, prefixes)


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
    tool: ModuleType, rules: tuple[urllib.robotparser.RobotFileParser, list[str]], url: str
) -> None:
    parser, prefixes = rules
    with pytest.raises(tool.StopRun):
        tool.check_allowed(url, parser, prefixes)


def test_challenge_detection(tool: ModuleType) -> None:
    assert tool.is_challenge("<title>Just a moment...</title>")
    assert not tool.is_challenge("<pre>スピリット</pre>")
