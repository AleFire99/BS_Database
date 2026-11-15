"""Printing and block-icon parsing on synthetic pages (#71)."""

import logging

import pytest
from bs4 import BeautifulSoup

from bs_database.parsers.batspi.card_sections import parse_images, parse_printings
from bs_database.parsers.card_models import CardImage, Printing
from bs_database.parsers.errors import ParseError

LOGGER = "bs_database.parsers.batspi.card_sections"
URL = "https://batspi.com/index.php?card"
ES = " "


def run(html: str, numbers: list[str]) -> tuple[Printing, ...]:
    return parse_printings(BeautifulSoup(html, "html.parser"), URL, numbers)


def page(printings: str = "", blocks: str = "") -> str:
    out = "<html><body>"
    if printings:
        out += f'<h4>収録<a class="anchor_super">†</a></h4>{printings}'
    if blocks:
        out += (
            '<div class="jumpmenu"></div><h4>収録/掲載/配布 ブロックアイコン '
            f'<a class="anchor_super">†</a></h4>{blocks}'
        )
    return out + '<div class="jumpmenu"></div><h4>関連リンク</h4></body></html>'


def test_row_shapes() -> None:
    rows = (
        '<p><a href="index.php?a">契約編</a> &lt;R&gt; (SECRETあり)<br/>'
        '<a href="index.php?b">バトスピMAX</a>入場者特典　 &lt;X&gt; (【ゼロ】先行(配布))<br/>'
        '<a href="index.php?c">メガデッキ</a>記念品(SECRETデザイン)<br/>'
        '<a href="index.php?d">全角</a> &lt;C&gt;（全角注）<br/>'
        "バトスピ部 チャレンジ (金色仕様)</p>"
    )
    got = run(page(rows), ["A-001"])
    assert [(p.product_name_jp, p.detail_jp, p.rarity, p.note_jp) for p in got] == [
        ("契約編", None, "R", "SECRETあり"),
        ("バトスピMAX", "入場者特典", "X", "【ゼロ】先行(配布)"),
        ("メガデッキ", "記念品", None, "SECRETデザイン"),
        ("全角", None, "C", "全角注"),
        ("バトスピ部 チャレンジ", None, None, "金色仕様"),
    ]
    assert got[0].product_href == "https://batspi.com/index.php?a"
    assert got[-1].product_href is None
    assert {p.section for p in got} == {"収録"}


def test_list_shape_with_labels() -> None:
    rows = (
        '<ul class="list1"><li><strong>A-001</strong><br/><a href="x">P1</a> &lt;C&gt;</li>'
        '<li><strong>A-002</strong><br/><a href="x">P2</a> &lt;R&gt;</li></ul>'
    )
    got = run(page(rows), ["A-001", "A-002"])
    assert [(p.number, p.product_name_jp) for p in got] == [("A-001", "P1"), ("A-002", "P2")]


def test_nested_promo_list_shape() -> None:
    rows = (
        '<ul class="list1"><li><strong>P1</strong><ul class="list2"><li>'
        '<a href="x">P</a> &lt;P&gt;<br/>付属品</li></ul></li></ul>'
    )
    got = run(page(rows), ["P1"])
    assert [(p.product_name_jp, p.product_href) for p in got] == [
        ("P", "https://batspi.com/x"),
        ("付属品", None),
    ]


def test_ads_are_skipped() -> None:
    html = page('<p><a href="x">P</a> &lt;C&gt;</p><div><ins class="adsbygoogle"></ins></div>')
    assert len(run(html, ["A-001"])) == 1


def test_no_section_gives_no_printings() -> None:
    assert run("<html><body></body></html>", ["A-001"]) == ()


def test_face_less_label_fans_out_and_exact_label_does_not() -> None:
    rows = (
        '<ul><li><strong>F-01</strong><br/><a href="x">P</a> &lt;C&gt;</li>'
        '<li><strong>F-01(A)</strong><br/><a href="x">Q</a> &lt;C&gt;</li></ul>'
    )
    got = run(page(rows), ["F-01(A)", "F-01(B)"])
    assert [(p.number, p.product_name_jp) for p in got] == [
        ("F-01(A)", "P"),
        ("F-01(B)", "P"),
        ("F-01(A)", "Q"),
    ]


def test_missing_label_on_multi_number_page_raises() -> None:
    with pytest.raises(ParseError, match="without a card number"):
        run(page('<p><a href="x">P</a> &lt;C&gt;</p>'), ["A-001", "A-002"])


def test_block_icon_join_and_formats() -> None:
    blocks = (
        f'[BS01]{ES}<a href="b">P1</a>{ES}(A-001){ES}ブロックアイコン:&lt;12&gt;{ES}'
        "2025年05月17日<br/>\n"
        f'<a href="b">P2</a>{ES}(A-001){ES}{ES}2008年9月3日<br/>\n'
        f'<a href="b">P3</a>{ES}{ES}ブロックアイコン:&lt;3&gt;{ES}<br/><br/>'
    )
    rows = (
        "<p>" + "<br/>".join(f'<a href="x">{n}</a> &lt;C&gt;' for n in ("P1", "P2", "P3")) + "</p>"
    )
    got = run(page(rows, blocks), ["A-001"])
    assert [(p.product_code, p.block_icon, p.release_date) for p in got] == [
        ("BS01", "12", "2025-05-17"),
        (None, None, "2008-09-03"),
        (None, "3", None),
    ]


def test_block_row_is_consumed_once_per_number() -> None:
    blocks = (
        f'[SD68]{ES}<a href="b">M</a>{ES}(A-001){ES}ブロックアイコン:&lt;11&gt;{ES}'
        "2024年03月30日<br/>"
    )
    rows = '<p><a href="x">M</a> &lt;X&gt;<br/><a href="x">M</a>記念(SECRET)</p>'
    got = run(page(rows, blocks), ["A-001"])
    assert [p.product_code for p in got] == ["SD68", None]


def test_block_only_rows_and_comma_list() -> None:
    blocks = f'<a href="b">配布</a>{ES}(A-001,A-002){ES}ブロックアイコン:&lt;7&gt;{ES}<br/>'
    got = run(page("", blocks), ["A-001", "A-002"])
    assert [(p.number, p.rarity, p.section, p.block_icon) for p in got] == [
        ("A-001", None, "ブロックアイコン", "7"),
        ("A-002", None, "ブロックアイコン", "7"),
    ]


def test_block_row_for_unknown_number_warns(caplog: pytest.LogCaptureFixture) -> None:
    blocks = f'<a href="b">配布</a>{ES}(Z-9){ES}<br/>'
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert run(page("", blocks), ["A-001"]) == ()
    assert "Z-9" in caplog.text


def test_block_row_without_number_on_multi_number_page_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    blocks = f'<a href="b">配布</a>{ES}<br/>'
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert run(page("", blocks), ["A-001", "A-002"]) == ()
    assert "field=blockicon" in caplog.text


def test_unparseable_block_line_warns(caplog: pytest.LogCaptureFixture) -> None:
    blocks = f'<a href="b">P</a>{ES}(A-001) 変な行 (x)<br/>謎のテキスト<br/>'
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert run(page("", blocks), ["A-001"]) == ()
    assert caplog.text.count("unparseable block-icon line") == 2


GALLERY = (
    '<ul class="ppy-imglist">'
    '<li><a href="/card/A-001.jpg"><img src="/card/small/A-001.jpg"/></a>'
    '<span class="ppy-extcaption">A-001<br />製品<br />シークレット<br /><br /></span></li>'
    "{extra}</ul>"
)


def images(html: str, numbers: list[str]) -> tuple[CardImage, ...]:
    return parse_images(BeautifulSoup(html, "html.parser"), URL, numbers)


def test_gallery_image() -> None:
    (image,) = images(GALLERY.format(extra=""), ["A-001"])
    assert image == CardImage(
        "A-001",
        "https://batspi.com/card/A-001.jpg",
        "https://batspi.com/card/small/A-001.jpg",
        ("製品", "シークレット"),
    )


def test_gallery_inside_a_list_item_is_ignored() -> None:
    assert images(f"<ul><li>{GALLERY.format(extra='')}</li></ul>", ["A-001"]) == ()


def test_no_gallery() -> None:
    assert images("<html></html>", ["A-001"]) == ()


def test_gallery_item_without_small_image() -> None:
    html = GALLERY.format(extra="").replace('<img src="/card/small/A-001.jpg"/>', "")
    assert images(html, ["A-001"])[0].small_url is None


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('<a href="/card/A-001.jpg">', "<a>", "without a link"),
        ('<span class="ppy-extcaption">A-001', '<span class="x">A-001', "without a caption"),
        ('extcaption">A-001<br />', 'extcaption"><br />', "without a card number"),
    ],
)
def test_malformed_gallery_item_raises(old: str, new: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        images(GALLERY.format(extra="").replace(old, new), ["A-001"])


def test_gallery_number_unknown_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert images(GALLERY.format(extra=""), ["B-002"]) == ()
    assert "field=number" in caplog.text
    assert "A-001" in caplog.text


def test_all_rows_unresolvable_raises() -> None:
    rows = '<ul><li><strong>Z-999</strong><br/><a href="x">P</a> &lt;C&gt;</li></ul>'
    with pytest.raises(ParseError, match="none resolves"):
        run(page(rows), ["A-001"])


def test_one_unresolvable_row_still_only_warns(caplog: pytest.LogCaptureFixture) -> None:
    rows = (
        '<ul><li><strong>Z-999</strong><br/><a href="x">P</a> &lt;C&gt;</li>'
        '<li><strong>A-001</strong><br/><a href="x">Q</a> &lt;C&gt;</li></ul>'
    )
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        got = run(page(rows), ["A-001"])
    assert [p.product_name_jp for p in got] == ["Q"]
    assert "Z-999" in caplog.text


def test_gallery_faceless_caption_fans_out_to_both_faces() -> None:
    html = GALLERY.format(extra="").replace("A-001<br", "F-01<br")
    got = images(html, ["F-01(A)", "F-01(B)"])
    assert [i.number for i in got] == ["F-01(A)", "F-01(B)"]
    assert got[0].large_url == got[1].large_url


def test_block_join_normalises_product_names() -> None:
    blocks = f'[BS01]{ES}<a href="b">ＢＳ　Ｐ１</a>{ES}(A-001){ES}ブロックアイコン:&lt;3&gt;{ES}'
    rows = '<p><a href="x">BS P1</a> &lt;C&gt;</p>'
    (got,) = run(page(rows, blocks), ["A-001"])
    assert (got.product_name_jp, got.product_code, got.block_icon) == ("BS P1", "BS01", "3")
