import importlib
import json
import logging
import pkgutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import bs_database.scrapers
from bs_database.scrapers import batspi_card
from bs_database.scrapers.batspi_card import (
    extract_card_name,
    extract_spirit_info_and_core_requirements,
    save_card_data_to_json,
    scrape_card_data,
    translate,
)
from bs_database.scrapers.batspi_links import extract_links
from bs_database.scrapers.batspi_sets import extract_set_urls

GOLDENS = Path(__file__).parent / "goldens" / "scrapers"
BATSPI = "https://batspi.com/"
Serve = Callable[[dict[str, bytes] | None], list[str]]


def golden(name: str) -> Any:
    return json.loads((GOLDENS / name).read_text(encoding="utf-8"))


def test_importing_modules_makes_no_requests(serve: Serve) -> None:
    requested = serve(None)
    for info in pkgutil.iter_modules(bs_database.scrapers.__path__):
        importlib.reload(importlib.import_module(f"bs_database.scrapers.{info.name}"))
    assert requested == []


def test_set_urls_match_golden(serve: Serve, fixture_urls: dict[str, str], tmp_path: Path) -> None:
    serve(None)
    out = tmp_path / "urls.txt"
    extract_set_urls(fixture_urls["index.html"], out)
    assert out.read_text(encoding="utf-8").splitlines() == golden("set_urls.json")


def test_set_urls_missing_h3_logs_error(
    serve: Serve, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    serve({"http://x/": b"<html><body>nothing</body></html>"})
    out = tmp_path / "urls.txt"
    with caplog.at_level(logging.ERROR):
        extract_set_urls("http://x/", out)
    assert not out.exists()
    assert "content_1_1" in caplog.text


def test_card_links_match_golden(serve: Serve, fixture_urls: dict[str, str]) -> None:
    serve(None)
    links = extract_links(fixture_urls["set.html"], BATSPI)
    assert [list(t) for t in links] == golden("card_links.json")


@pytest.mark.parametrize(
    ("fixture", "card_id"),
    [
        ("card_spirit.html", "BS72-007"),
        ("card_nexus.html", "BS72-069"),
        ("card_magic.html", "BS72-075"),
    ],
)
def test_card_json_matches_golden(
    serve: Serve,
    stub_translator: None,
    fixture_urls: dict[str, str],
    tmp_path: Path,
    fixture: str,
    card_id: str,
) -> None:
    serve(None)
    scrape_card_data(card_id, fixture_urls[fixture], str(tmp_path))
    written = json.loads(
        (tmp_path / "card_json" / "BS72" / f"{card_id}.json").read_text(encoding="utf-8")
    )
    assert written == golden(f"card_{card_id}.json")
    assert written["image"] == f"data/images/BS72/{card_id}.jpg"


def test_image_root_is_a_parameter(
    serve: Serve, stub_translator: None, fixture_urls: dict[str, str], tmp_path: Path
) -> None:
    serve(None)
    scrape_card_data("BS72-069", fixture_urls["card_nexus.html"], str(tmp_path), image_root="img")
    data = json.loads((tmp_path / "card_json" / "BS72" / "BS72-069.json").read_text("utf-8"))
    assert data["image"] == "img/BS72/BS72-069.jpg"


def test_missing_name_logs_and_writes_nothing(
    serve: Serve, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    serve({"http://x/": b"<html><body><pre>a\nb</pre></body></html>"})
    with caplog.at_level(logging.ERROR):
        scrape_card_data("BS01-001", "http://x/", str(tmp_path))
    assert not (tmp_path / "card_json").exists()
    assert "card name" in caplog.text


def test_missing_pre_gives_none_fields(serve: Serve, stub_translator: None, tmp_path: Path) -> None:
    html = b'<html><h1 class="title"><a>Name</a></h1></html>'
    serve({"http://x/": html})
    scrape_card_data("BS01-001", "http://x/", str(tmp_path))
    data = json.loads((tmp_path / "card_json" / "BS01" / "BS01-001.json").read_text("utf-8"))
    assert data["name"] == "ENName"
    for key in ("type", "cost", "reduction", "symbol", "family", "core_requirements"):
        assert data[key] is None


def test_extract_card_name_none_without_title() -> None:
    from bs4 import BeautifulSoup

    assert extract_card_name(BeautifulSoup("<h1 class='title'>x</h1>", "html.parser")) is None


@pytest.mark.usefixtures("stub_translator")
class TestReduction:
    @staticmethod
    def parse(info: str) -> Any:
        return extract_spirit_info_and_core_requirements(["スピリット", info])

    def test_zero_is_none(self) -> None:
        cost, reduction, symbol, *_ = self.parse("3(0)/赤/爬獣")
        assert (cost, reduction, symbol) == (3, None, "EN赤")

    def test_number_repeats_symbol(self) -> None:
        assert self.parse("5(2)/赤/爬獣")[1] == ["EN赤", "EN赤"]

    def test_mixed_expands_per_colour(self) -> None:
        assert self.parse("5(2 紫, 1 神)/赤/爬獣")[1] == ["EN紫", "EN紫", "EN神"]

    def test_unspaced_mixed_is_empty_legacy_quirk(self) -> None:
        assert self.parse("4(赤2神1)/赤/眷属")[1] == []

    def test_family_split_and_levels(self) -> None:
        lines = ["スピリット", "1(0)/赤/甲竜 ", "<1>Lv1 3000 <3>Lv2 7000"]
        _, _, _, family, spirit_type, cores = extract_spirit_info_and_core_requirements(lines)
        assert family == ["EN甲竜"]
        assert spirit_type == "ENスピリット"
        assert cores == [
            {"level": 1, "battlePoints": 3000, "cores": 1},
            {"level": 2, "battlePoints": 7000, "cores": 3},
        ]

    def test_no_info_line(self) -> None:
        assert extract_spirit_info_and_core_requirements(["x"]) == (
            None,
            None,
            None,
            None,
            None,
            [],
        )


def test_translate_failure_returns_error_string(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        def __init__(self, source: str, target: str) -> None:
            pass

        def translate(self, text: str) -> str:
            raise RuntimeError("offline")

    monkeypatch.setattr(batspi_card, "GoogleTranslator", Boom)
    assert translate("赤") == "Error: offline"


def test_save_card_data_creates_folders(tmp_path: Path) -> None:
    save_card_data_to_json({"a": "日本"}, "BS09-001", str(tmp_path))
    text = (tmp_path / "card_json" / "BS09" / "BS09-001.json").read_text(encoding="utf-8")
    assert "日本" in text


def test_guard_blocks_real_requests() -> None:
    import requests

    with pytest.raises(AssertionError, match="network"):
        requests.get("https://example.invalid/")
