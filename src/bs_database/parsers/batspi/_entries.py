"""Helpers shared by the batspi page parsers (#69)."""

import re
from collections.abc import Iterable
from urllib.parse import parse_qs, unquote, urljoin

from bs4 import BeautifulSoup, Tag

from bs_database.ingest.policy import BASE_URL
from bs_database.parsers.batspi.numbers import parse_number
from bs_database.parsers.errors import ParseError
from bs_database.parsers.models import ListEntry, MissingEntry

_PREFIX = "index.php?"


def soup_body(html: str) -> Tag:
    """Return the ``<div id="body">`` of a page, or raise ``ParseError``."""
    body = BeautifulSoup(html, "html.parser").find("div", id="body")
    if not isinstance(body, Tag):
        raise ParseError('no <div id="body">')
    return body


def heading_text(tag: Tag) -> str:
    """Heading text without ruby readings and the ``anchor_super`` dagger."""
    parts: list[str] = []
    for s in tag.find_all(string=True):
        if s.find_parent(["rt", "rp"]) is not None:
            continue
        if s.find_parent("a", class_="anchor_super") is not None:
            continue
        parts.append(str(s))
    return " ".join("".join(parts).split())


def page_href(a: Tag) -> str | None:
    """The href of a normal wiki page link, or None (anchors, tools, external)."""
    href = a.get("href")
    if not isinstance(href, str) or not href.startswith(_PREFIX):
        return None
    if "cmd=" in href or "plugin=" in href:
        return None
    return href


def page_name(href: str) -> str:
    """Page name of an ``index.php?<name>`` href."""
    return unquote(href[len(_PREFIX) :])


def page_url(href: str) -> str:
    """Absolute URL of a wiki href, kept percent-encoded."""
    return urljoin(BASE_URL, href)


def edit_target(a: Tag) -> str | None:
    """The ``page=`` value of a ``cmd=edit`` link, or None."""
    href = a.get("href")
    if not isinstance(href, str) or not href.startswith(_PREFIX) or "cmd=edit" not in href:
        return None
    values = parse_qs(href[len(_PREFIX) :]).get("page")
    return values[0] if values else None


_NUMBER = re.compile(r"^(?=.*\d)[0-9A-Za-z][0-9A-Za-z()\- ]{0,24}$")
_RARITY = re.compile(r"^[^\s()（）]+")
_COPIES = re.compile(r"\((\d+)\)")


def _lines(p: Tag) -> list[list[object]]:
    lines: list[list[object]] = [[]]
    for child in p.children:
        if isinstance(child, Tag) and child.name == "br":
            lines.append([])
        else:
            lines[-1].append(child)
    return lines


def _text(node: object) -> str:
    return node.get_text() if isinstance(node, Tag) else str(node)


def _entry(line: list[object], section: tuple[str, ...]) -> ListEntry | MissingEntry | None:
    idx = next((i for i, n in enumerate(line) if isinstance(n, Tag) and n.name == "a"), None)
    if idx is None:
        return None
    a = line[idx]
    assert isinstance(a, Tag)
    number = "".join(_text(n) for n in line[:idx]).strip()
    if not _NUMBER.match(number):
        return None
    href = page_href(a)
    if href is None:
        if edit_target(a) is not None:
            return MissingEntry(number, a.get_text().strip(), section)
        return None
    after = "".join(_text(n) for n in line[idx + 1 :]).strip()
    rarity = None
    m = _RARITY.match(after)
    if m:
        rarity = m.group(0)
        after = after[m.end() :]
    copies = None
    m = _COPIES.search(after)
    if m:
        copies = int(m.group(1))
        after = after[: m.start()] + after[m.end() :]
    note = " ".join(after.split()) or None
    return ListEntry(
        number,
        parse_number(number),
        a.get_text().strip(),
        page_url(href),
        rarity,
        copies,
        note,
        section,
    )


def iter_entries(elements: Iterable[Tag]) -> tuple[list[ListEntry], list[MissingEntry]]:
    """Collect card lines from ``h2/h3/h4/p`` elements given in document order.

    ``section`` of each entry is the current (h3, h4) heading texts.
    """
    h3: str | None = None
    h4: str | None = None
    entries: list[ListEntry] = []
    missing: list[MissingEntry] = []
    for el in elements:
        if el.name == "h2":
            h3 = h4 = None
        elif el.name == "h3":
            h3, h4 = heading_text(el), None
        elif el.name == "h4":
            h4 = heading_text(el)
        elif el.name == "p":
            section = tuple(x for x in (h3, h4) if x)
            for line in _lines(el):
                entry = _entry(line, section)
                if isinstance(entry, MissingEntry):
                    missing.append(entry)
                elif entry is not None:
                    entries.append(entry)
    return entries, missing
