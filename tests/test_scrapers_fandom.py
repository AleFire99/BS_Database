"""Fandom scraper tests on synthetic HTML.

The wiki is behind a Cloudflare challenge, so no real page could be saved as a fixture and
there are no legacy-generated goldens (see the #21 report). Expected values here are derived
from reading the legacy code.
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path

import pytest
import requests

from bs_database.scrapers.fandom_images import (
    download_card_image,
    download_set_images,
    extract_card_infos,
)
from bs_database.scrapers.fandom_sets import (
    fetch_page,
    parse_table,
    save_to_json,
    scrape_battle_spirits,
)

Serve = Callable[[dict[str, bytes] | None], list[str]]


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code
        self.text = content.decode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


BASE = "https://wiki.example"
SET_URL = "https://wiki.example/wiki/BS47"

SET_HTML = """
<div id="mw-content-text"><div>
<p>intro</p>
<table><tbody>
<tr><th>Number</th><th>Name</th></tr>
<tr><td>1</td><td>Alpha</td></tr>
<tr><td>BS47-002</td><td>Beta</td></tr>
<tr><td>3</td></tr>
</tbody></table>
</div></div>
"""


def card_table(*rows: str) -> str:
    return (
        '<table align="center" border="1"><tr><th>h</th><th>h</th></tr>'
        + "".join(rows)
        + "</table>"
    )


def test_parse_table_builds_card_ids() -> None:
    assert parse_table(SET_HTML, SET_URL) == [
        {"Name": "Alpha", "Card_ID": "BS47-001"},
        {"Name": "Beta", "Card_ID": "BS47-002"},
    ]


@pytest.mark.parametrize(
    "html",
    ["<p>none</p>", "<table><tr><td>x</td></tr></table>", "<div id='a'></div><table></table>"],
)
def test_parse_table_missing_table_returns_empty(html: str) -> None:
    assert parse_table(html, SET_URL) == []


def test_scrape_battle_spirits_saves_json(serve: Serve, tmp_path: Path) -> None:
    serve({SET_URL: SET_HTML.encode()})
    out = tmp_path / "sub" / "bs47.json"
    data = scrape_battle_spirits(SET_URL, str(out))
    assert json.loads(out.read_text(encoding="utf-8")) == data
    assert len(data) == 2


def test_fetch_page_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(b"", 503))
    with pytest.raises(requests.HTTPError):
        fetch_page(SET_URL)


def test_save_to_json_keeps_unicode(tmp_path: Path) -> None:
    save_to_json([{"a": "日本"}], str(tmp_path / "x" / "o.json"))
    assert "日本" in (tmp_path / "x" / "o.json").read_text(encoding="utf-8")


def test_extract_card_infos_returns_only_last_table(serve: Serve) -> None:
    html = card_table('<tr><td>1</td><td><a href="/a">a</a></td></tr>') + card_table(
        '<tr><td>BS47-002</td><td><a href="http://full/b">b</a></td></tr>',
        "<tr><td>only one</td></tr>",
        "<tr><td>9</td><td>no link</td></tr>",
    )
    serve({SET_URL: html.encode()})
    assert extract_card_infos(SET_URL, BASE) == [("BS47-002", "http://full/b")]


def test_extract_card_infos_relative_and_missing(
    serve: Serve, caplog: pytest.LogCaptureFixture
) -> None:
    serve({SET_URL: card_table('<tr><td>1</td><td><a href="/a">a</a></td></tr>').encode()})
    assert extract_card_infos(SET_URL, BASE) == [("1", f"{BASE}/a")]
    serve({"http://none/": b"<p>x</p>"})
    with caplog.at_level(logging.WARNING):
        assert extract_card_infos("http://none/", BASE) == []
    assert "No tables" in caplog.text


def test_extract_card_infos_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(b"", 404))
    assert extract_card_infos(SET_URL, BASE) == []


def test_download_card_image_writes_bytes(serve: Serve, tmp_path: Path) -> None:
    page = '<img class="mw-file-element" data-src="/img/c.png" src="data:image/gif;base64,x">'
    serve(
        {"https://wiki.example/wiki/Card": page.encode(), "https://wiki.example/img/c.png": b"IMG"}
    )
    download_card_image("https://wiki.example/wiki/Card", "BS47-001", str(tmp_path))
    assert (tmp_path / "BS47-001.jpg").read_bytes() == b"IMG"


@pytest.mark.parametrize(
    "page",
    [
        '<img class="mw-file-element" src="data:image/gif;base64,x">',
        '<img class="mw-file-element">',
        "<p>no image</p>",
    ],
)
def test_download_card_image_skips(serve: Serve, tmp_path: Path, page: str) -> None:
    serve({"http://c/": page.encode()})
    download_card_image("http://c/", "BS47-001", str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_download_set_images_builds_urls_without_bs_prefix(serve: Serve, tmp_path: Path) -> None:
    index = card_table(
        '<tr><td>5</td><td><a href="/wiki/C5">c</a></td></tr>',
        '<tr><td>BS47-006</td><td><a href="/wiki/C6">c</a></td></tr>',
    )
    img = '<img class="mw-file-element" src="http://img/x.png">'
    requested = serve(
        {
            "https://wiki.example/wiki/47": index.encode(),
            "https://wiki.example/wiki/C5": img.encode(),
            "https://wiki.example/wiki/C6": img.encode(),
            "http://img/x.png": b"B",
        }
    )
    download_set_images([47], "https://wiki.example/wiki/", BASE, str(tmp_path))
    assert requested[0] == "https://wiki.example/wiki/47"
    assert (tmp_path / "BS47" / "BS47-5.jpg").read_bytes() == b"B"
    assert (tmp_path / "BS47" / "BS47-006.jpg").read_bytes() == b"B"
