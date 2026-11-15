"""Card list index parser, on the cached fixture."""

from collections import Counter
from pathlib import Path
from urllib.parse import unquote

import pytest

from bs_database.parsers.batspi.index import parse_index
from bs_database.parsers.errors import ParseError

PREFIX = "https://batspi.com/index.php?"


def _html(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / "html" / f"{name}.html").read_text("utf-8")


PATH_COUNTS = {
    ("ブースターパック",): 76,
    ("構築済みデッキ",): 79,
    ("テーマパック/再録パック",): 51,
    ("コラボブースター",): 34,
    ("コラボブースターEX",): 1,
    ("プレミアムカードセット",): 12,
    ("食玩", "ウエハース"): 38,
    ("食玩", "フィギュアコレクション"): 3,
    ("食玩", "食玩その他"): 1,
    ("限定商品", "プレミアムバンダイ"): 64,
    ("限定商品", "リミテッドパック"): 28,
    ("限定商品", "DVD-BOX/Blu-ray BOX"): 10,
    ("限定商品", "最強ジャンプ応募者全員サービス"): 4,
    ("限定商品", "限定品その他"): 12,
    ("配布品・付録",): 36,
    ("配布品・付録", "書籍特典"): 33,
    ("配布品・付録", "バトルスキーイベント"): 6,
    ("配布品・付録", "バトスピショップバトル・バトスピフレンドリーバトル"): 17,
    ("大会・イベント",): 4,
    ("大会・イベント", "オンライン"): 3,
    ("大会・イベント", "アニメイベント"): 5,
    ("大会・イベント", "大会"): 39,
    ("大会・イベント", "ショップバトル"): 19,
    ("ゲーム",): 2,
}


def test_counts_and_names() -> None:
    page = parse_index(_html("index"))
    assert len(page.products) == 577
    assert len({p.name for p in page.products}) == 571
    dupes = {n for n, c in Counter(p.name for p in page.products).items() if c > 1}
    assert dupes == {
        "光導デッキ コンプリートボックス",
        "プロモーションカード",
        "バトスピ部",
        "最強ヒーローデッキ",
        "バトスピショップバトル",
        "バトスピフレンドリーバトル",
    }


def test_first_last_and_urls() -> None:
    page = parse_index(_html("index"))
    assert page.products[0].name == "契約編：環 第4章：英雄傑集"
    assert page.products[0].path == ("ブースターパック",)
    assert page.products[-1].name == "バトルスピリッツ コネクテッドバトラーズ"
    assert page.products[-1].path == ("ゲーム",)
    for p in page.products:
        assert p.url.startswith(PREFIX)
        assert unquote(p.url[len(PREFIX) :]) == p.name
        assert not p.name.startswith("カードリスト/")


def test_path_counts() -> None:
    page = parse_index(_html("index"))
    counts = Counter(p.path for p in page.products)
    assert dict(counts) == PATH_COUNTS
    assert sum(counts.values()) == 577


def test_promotion_card_listed_twice() -> None:
    page = parse_index(_html("index"))
    paths = [p.path for p in page.products if p.name == "プロモーションカード"]
    assert paths == [("配布品・付録",), ("大会・イベント",)]


def test_missing_pages() -> None:
    page = parse_index(_html("index"))
    expected = (
        "BATTLE SPIRITS スペシャルスタッフトークショー 2025",
        "バトスピフェスタ2008",
        "ガンダムカップ2024",
        "バトルスピリッツ 覇者の咆哮",
        "バトルスピリッツ デジタルスターター",
        "バトルスピリッツ ヒーローズソウル",
        "バトルスピリッツ 輝石の覇者",
    )
    assert page.missing_pages == expected
    assert not set(expected) & {p.name for p in page.products}


@pytest.mark.parametrize(
    "html",
    ["", None, '<div id="body"><h2>x</h2><p>no h3</p></div>'],
)
def test_malformed(html: str | None) -> None:
    with pytest.raises(ParseError):
        parse_index(_html("set_bs01") if html is None else html)
