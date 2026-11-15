"""Parser for batspi.com set pages (#69)."""

import re
from collections import Counter

from bs4 import Tag

from bs_database.parsers.batspi._entries import heading_text, iter_entries, soup_body
from bs_database.parsers.errors import ParseError
from bs_database.parsers.models import ListEntry, SetPage

_CARDS = "収録カード"
_STOP = {"リンク", "外部リンク"}
_DATE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日発売")


def _set_code(entries: list[ListEntry]) -> str | None:
    series = Counter(e.parsed.series for e in entries if e.parsed and e.parsed.series)
    if not series:
        return None
    code, count = series.most_common(1)[0]
    return code if count * 2 > len(entries) else None


def parse_set_page(html: str) -> SetPage:
    """Parse a set page into title, release date, set code and card entries."""
    body = soup_body(html)
    elements = [e for e in body.find_all(["h2", "h3", "h4", "p"]) if isinstance(e, Tag)]
    h2s = [e for e in elements if e.name == "h2"]
    if not h2s:
        raise ParseError("no title heading")
    cards = next((e for e in h2s if heading_text(e) == _CARDS), None)
    if cards is None:
        raise ParseError(f"no {_CARDS} heading")
    start = elements.index(cards)

    release_date = None
    for el in elements[:start]:
        if el.name == "p":
            m = _DATE.search(el.get_text())
            if m:
                release_date = f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
                break

    selected: list[Tag] = []
    for el in elements[start + 1 :]:
        if el.name != "p" and heading_text(el) in _STOP:
            break
        selected.append(el)
    entries = iter_entries(selected)
    return SetPage(heading_text(h2s[0]), release_date, _set_code(entries), tuple(entries))
