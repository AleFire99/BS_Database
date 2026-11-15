"""Parser for the batspi.com card list index (#69)."""

from bs4 import Tag

from bs_database.parsers.batspi._entries import (
    edit_target,
    heading_text,
    page_href,
    page_name,
    page_url,
    soup_body,
)
from bs_database.parsers.errors import ParseError
from bs_database.parsers.models import IndexPage, IndexProduct

_SUB_INDEX = "カードリスト/"


def parse_index(html: str) -> IndexPage:
    """Parse the card list index into product links and missing pages."""
    body = soup_body(html)
    first_h2: Tag | None = None
    in_first = False
    h3 = h4 = None
    products: list[IndexProduct] = []
    missing: list[str] = []
    seen_h3 = False

    for el in body.find_all(["h2", "h3", "h4", "a"]):
        if el.name == "h2":
            if first_h2 is None:
                first_h2 = el
                in_first = True
            else:
                in_first = False
            h3 = h4 = None
            continue
        if not in_first:
            continue
        if el.name == "h3":
            h3, h4, seen_h3 = heading_text(el), None, True
            continue
        if el.name == "h4":
            h4 = heading_text(el)
            continue
        if h3 is None:
            continue
        if "anchor_super" in (el.get("class") or []):
            continue
        target = edit_target(el)
        if target is not None:
            missing.append(target)
            continue
        href = page_href(el)
        if href is None:
            continue
        name = page_name(href)
        if name.startswith(_SUB_INDEX):
            continue
        path = tuple(p for p in (h3, h4) if p)
        products.append(IndexProduct(name, page_url(href), path))

    if not seen_h3 or not products:
        raise ParseError("not a card list index")
    return IndexPage(tuple(products), tuple(missing))
