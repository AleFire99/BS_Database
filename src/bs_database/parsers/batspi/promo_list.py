"""Parser for the batspi.com promotion card list (#69)."""

from bs4 import Tag

from bs_database.parsers.batspi._entries import iter_entries, soup_body
from bs_database.parsers.errors import ParseError
from bs_database.parsers.models import PromoList


def parse_promo_list(html: str) -> PromoList:
    """Parse the promotion list into card entries grouped by (h3, h4) section."""
    body = soup_body(html)
    elements = [e for e in body.find_all(["h2", "h3", "h4", "p"]) if isinstance(e, Tag)]
    first = next((i for i, e in enumerate(elements) if e.name == "h2"), None)
    if first is None:
        raise ParseError("no title heading")
    entries = iter_entries(elements[first + 1 :])
    if not entries:
        raise ParseError("no card entries")
    return PromoList(tuple(entries))
