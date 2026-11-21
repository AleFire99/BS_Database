"""Parsers for the batspi.com promotion card list and year-sectioned lists (#69, #108)."""

from bs4 import Tag

from bs_database.parsers.batspi._entries import iter_entries, soup_body
from bs_database.parsers.errors import ParseError
from bs_database.parsers.models import PromoList


def _elements(html: str) -> list[Tag]:
    body = soup_body(html)
    return [e for e in body.find_all(["h2", "h3", "h4", "p"]) if isinstance(e, Tag)]


def parse_promo_list(html: str) -> PromoList:
    """Parse the promotion list into card entries grouped by (h3, h4) section."""
    elements = _elements(html)
    first = next((i for i, e in enumerate(elements) if e.name == "h2"), None)
    if first is None:
        raise ParseError("no title heading")
    entries, missing = iter_entries(elements[first + 1 :])
    if not entries:
        raise ParseError("no card entries")
    return PromoList(tuple(entries), tuple(missing))


def parse_year_list(html: str) -> PromoList:
    """Parse a list split by year (``h3`` title, ``h4`` years, no ``h2``), e.g. 提供記念品.

    Same entries as the promotion list; the page has no ``h2`` title heading.
    """
    entries, missing = iter_entries(_elements(html))
    if not entries:
        raise ParseError("no card entries")
    return PromoList(tuple(entries), tuple(missing))
