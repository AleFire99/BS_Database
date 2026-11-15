"""Helpers shared by the batspi page parsers (#69)."""

from urllib.parse import parse_qs, unquote, urljoin

from bs4 import BeautifulSoup, Tag

from bs_database.ingest.policy import BASE_URL
from bs_database.parsers.errors import ParseError

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
