"""Printings (収録 and block-icon sections) and gallery images of a card page (#71).

Pure functions over a parsed page. Product links are read from the page and made
absolute with ``urljoin``; no URL is built from a name.
"""

import logging
import re
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, PageElement, Tag

from bs_database.parsers.card_models import CardImage, Printing
from bs_database.parsers.errors import ParseError

log = logging.getLogger(__name__)

_PLACEHOLDER = "NOTFOUND.jpg"  # the wiki's image for a missing scan
SECTION_PRINTINGS = "収録"
SECTION_BLOCK_ICON = "ブロックアイコン"

_FACE_RE = re.compile(r"\([A-Z]\)$")
_RARITY_RE = re.compile(r"<([^<>]*)>")
_OPEN, _CLOSE = "(（", ")）"
# a parenthesised date: ``(2018年7月)``, ``(2012/12/～)``
_DATE_RE = re.compile(r"[(（]\d{4}(?:年|/\d)")
_LINK = "\x00"
_BLOCK_RE = re.compile(
    rf"^(?:\[(?P<code>[^\]]+)\])?\s*{_LINK}\s*(?:\((?P<nums>[^)]*)\))?\s*"
    r"(?:ブロックアイコン:<(?P<icon>[^>]*)>)?\s*"
    r"(?:(?P<y>\d{4})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日)?$"
)

# A token is ("t", text), ("a", text, href), ("strong", text) or ("br",).
_Token = tuple[str, ...]


def _faceless(number: str) -> str:
    return _FACE_RE.sub("", number)


def _attr(tag: Tag, name: str) -> str | None:
    value = tag.get(name)
    return value if isinstance(value, str) else None


_STOP: _Token = ("stop",)


def _is_boundary(tag: Tag) -> bool:
    """A heading or a jump menu ends a section, even when malformed HTML nests it (#138)."""
    return tag.name == "h4" or "jumpmenu" in (tag.get("class") or [])


def _tokens(node: Tag) -> Iterator[_Token]:
    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            yield ("t", str(child))
        elif isinstance(child, Tag):
            if _is_boundary(child):
                yield _STOP
                return
            if child.name == "ins" or (child.name == "div" and child.find("ins") is not None):
                continue
            if child.name == "br":
                yield ("br",)
            elif child.name == "a":
                yield ("a", child.get_text().strip(), _attr(child, "href") or "")
            elif child.name == "strong":
                yield ("strong", child.get_text().strip())
            elif child.name in ("ul", "li", "p"):
                yield ("br",)
                yield from _tokens(child)
                yield ("br",)
            else:
                yield from _tokens(child)


def _find_section(soup: BeautifulSoup, exact: str | None, prefix: str | None) -> Tag | None:
    for heading in soup.find_all("h4"):
        text = heading.get_text().replace("†", "").strip()
        if (exact is not None and text == exact) or (
            prefix is not None and text.startswith(prefix)
        ):
            return heading
    return None


def _section_lines(heading: Tag) -> list[list[_Token]]:
    """Lines of tokens between a section heading and the next heading or jump menu."""
    tokens: list[_Token] = []
    sibling: PageElement | None = heading.next_sibling
    while sibling is not None:
        if isinstance(sibling, Tag):
            if sibling.name == "h4" or "jumpmenu" in (sibling.get("class") or []):
                break
            if sibling.name == "div" and sibling.find("ins") is not None:
                sibling = sibling.next_sibling
                continue
            if sibling.name == "br":
                tokens.append(("br",))
            elif sibling.name == "a":
                tokens.append(("a", sibling.get_text().strip(), _attr(sibling, "href") or ""))
            else:
                wrapper = ("br",) if sibling.name in ("ul", "p") else None
                if wrapper:
                    tokens.append(wrapper)
                tokens.extend(_tokens(sibling))
                if wrapper:
                    tokens.append(wrapper)
        elif isinstance(sibling, NavigableString) and not isinstance(sibling, Comment):
            tokens.append(("t", str(sibling)))
        sibling = sibling.next_sibling
    if _STOP in tokens:
        tokens = tokens[: tokens.index(_STOP)]
    lines: list[list[_Token]] = [[]]
    for token in tokens:
        if token[0] == "a" and not token[1]:
            continue  # an empty link (an anchor or a jump menu) is never content
        if token[0] == "br":
            lines.append([])
        else:
            lines[-1].append(token)
    return [line for line in lines if line]


@dataclass(frozen=True, slots=True)
class _Row:
    label: str | None
    name: str
    href: str | None
    detail: str | None
    rarity: str | None
    note: str | None
    text: str  # the whole row text outside the link: it may print the card number(s)


@dataclass(frozen=True, slots=True)
class _BlockRow:
    code: str | None
    name: str
    numbers: tuple[str, ...]
    icon: str | None
    date: str | None


def _trailing_group(text: str) -> tuple[str, str] | None:
    """Split a balanced ``(...)`` group off the end of ``text``: ``(rest, inner)``."""
    if not text.endswith(tuple(_CLOSE)):
        return None
    depth = 0
    for index in range(len(text) - 1, -1, -1):
        if text[index] in _CLOSE:
            depth += 1
        elif text[index] in _OPEN:
            depth -= 1
            if depth == 0:
                return text[:index].rstrip(), text[index + 1 : -1].strip()
    return None


def _only_groups(tail: str) -> list[str] | None:
    """The inner texts of ``tail`` when it is balanced ``(...)`` groups only, else ``None``."""
    groups: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(tail):
        if depth == 0:
            if char.isspace() or char in _CLOSE:  # a stray ``)`` is a typo of the page
                continue
            if char not in _OPEN:
                return None
            start = index + 1
        depth += (char in _OPEN) - (char in _CLOSE)
        if depth == 0:
            groups.append(tail[start:index].strip())
    return groups if depth == 0 else None


def _split_row(text: str, context: str) -> tuple[str | None, str | None, str | None]:
    """Split a row text into ``(detail, rarity, note)`` from the end (#144).

    The last ``<rarity>`` followed only by balanced groups gives the rarity and the notes;
    without one, a single trailing group is the note. Whatever remains, its own parentheses
    included, is the detail. An empty ``<>`` leaves the rarity ``None`` and logs a warning.
    """
    text = text.strip()
    marks = list(_RARITY_RE.finditer(text))
    groups = _only_groups(text[marks[-1].end() :]) if marks else None
    if marks and groups is not None:
        mark = marks[-1]
        rarity = mark[1].strip() or None
        if rarity is None:
            log.warning("empty rarity: %s field=rarity value=%r", context, text)
        note = " ".join(g for g in groups if g) or None
        return text[: mark.start()].strip() or None, rarity, note
    split = _trailing_group(text)
    if split is not None:
        return split[0] or None, None, split[1] or None
    return text or None, None, None


def _row_text(line: list[_Token]) -> str:
    """The row text with the text of every link in place (#144).

    Only a product link at the start of the row is left out (its text is the product name);
    a link inside the text, such as ``公認イベント「<a>...</a>」``, is printed content.
    """
    parts: list[str] = []
    first_link = True
    for token in line:
        if token[0] == "t":
            parts.append(token[1])
        elif token[0] == "a":
            if not (first_link and not "".join(parts).strip()):
                parts.append(token[1])
            first_link = False
    return "".join(parts).replace("　", " ").strip()


def _name_and_date(name: str, detail: str | None) -> tuple[str, str | None]:
    """Cut a parenthesised date off the name of a row without a product link (to the detail).

    A bare date (``Vジャンプ2012年1月号付録``) stays in the name: those are distinct products.
    """
    match = _DATE_RE.search(name)
    if match is None or match.start() == 0:
        return name, detail
    date = name[match.start() :].strip()
    return name[: match.start()].strip(), date if detail is None else f"{date} {detail}"


def _printing_rows(heading: Tag, context: str = "") -> list[_Row]:
    rows: list[_Row] = []
    label: str | None = None
    for line in _section_lines(heading):
        strong = next((t[1] for t in line if t[0] == "strong"), None)
        if strong:
            label = strong
        link = next((t for t in line if t[0] == "a"), None)
        text = "".join(t[1] for t in line if t[0] == "t").replace("　", " ").strip()
        detail, rarity, note = _split_row(_row_text(line), context)
        if link is not None:
            rows.append(_Row(label, link[1], link[2], detail, rarity, note, text))
        elif text:
            name, detail = _name_and_date(detail or text, None)
            rows.append(_Row(label, name, None, detail, rarity, note, text))
    return rows


def _block_rows(heading: Tag, context: str) -> list[_BlockRow]:
    rows: list[_BlockRow] = []
    for line in _section_lines(heading):
        link = next((t for t in line if t[0] == "a"), None)
        text = "".join(_LINK if t[0] == "a" else t[1] for t in line if t[0] != "strong")
        text = re.sub(r"[ 　 ]", " ", text).strip()
        match = _BLOCK_RE.match(text) if link is not None else None
        if link is None or match is None:
            if text:
                log.warning(
                    "unparseable block-icon line: %s field=blockicon value=%r", context, text
                )
            continue
        numbers = tuple(n.strip() for n in (match["nums"] or "").split(",") if n.strip())
        date = f"{match['y']}-{int(match['m']):02d}-{int(match['d']):02d}" if match["y"] else None
        rows.append(_BlockRow(match["code"], link[1], numbers, match["icon"] or None, date))
    return rows


def _printed_numbers(text: str, numbers: Sequence[str]) -> list[str]:
    """The page numbers a row prints in its text, e.g. ``<C> (BS18-076)`` or ``(X005A、X005D)``."""
    found: list[str] = []
    for number in numbers:
        bare = re.escape(_faceless(number))
        if re.search(rf"(?<![A-Za-z0-9-]){bare}(?![A-Za-z0-9-])", text) and number not in found:
            found.append(number)
    return found


def _label_numbers(label: str, numbers: Sequence[str]) -> list[str]:
    exact = [n for n in numbers if n == label]
    if exact:
        return exact
    found = [n for n in numbers if _faceless(n) == label]
    if found:
        return found
    # a label without the variant letter (``X003``) stands for ``X003A``, ``X003D``, ...
    return [n for n in numbers if re.fullmatch(re.escape(label) + r"[A-Z](?:\([AB]\))?", n)]


def _targets(
    label: str | None,
    numbers: Sequence[str],
    context: str,
    *,
    text: str = "",
    fallback_all: bool = False,
) -> list[str]:
    """Entry numbers a label (or the card numbers printed in the row ``text``) applies to.

    The label gives the candidates (one per face for a face-less label); numbers printed in
    the row text narrow them down, or stand in when there is no label. A row without any
    number on a multi-number page raises ``ParseError``, or with ``fallback_all`` applies to
    every number of the page and logs a warning (#108).
    """
    printed = _printed_numbers(text, numbers) if text else []
    if label is not None:
        candidates = _label_numbers(label, numbers)
        if candidates:
            return [n for n in candidates if n in printed] or candidates
        if printed:
            return printed
        log.warning("number is not a card number: %s field=number value=%r", context, label)
        return []
    if printed:
        return printed
    if len({_faceless(n) for n in numbers}) == 1:
        return list(numbers)
    if fallback_all:
        log.warning(
            "printing row without a card number is attached to all numbers: %s field=number "
            "value=%r",
            context,
            text.strip(),
        )
        return list(numbers)
    raise ParseError(f"printing row without a card number on a multi-number page in {context}")


def parse_printings(soup: BeautifulSoup, url: str, numbers: Sequence[str]) -> tuple[Printing, ...]:
    """Return the printings of every card number: 収録 rows joined with block-icon rows.

    Block-icon rows that match no 収録 row become printings with ``rarity=None`` and
    ``section="ブロックアイコン"``.
    """
    heading = _find_section(soup, SECTION_PRINTINGS, None)
    rows = _printing_rows(heading, url) if heading is not None else []
    block_heading = _find_section(soup, None, "収録/掲載")
    blocks = _block_rows(block_heading, url) if block_heading is not None else []
    used: set[tuple[int, str]] = set()
    printings: list[Printing] = []
    for row in rows:
        href = urljoin(url, row.href) if row.href else None
        for number in _targets(row.label, numbers, url, text=row.text, fallback_all=True):
            joined = _join(blocks, row.name, number, used)
            printings.append(
                Printing(
                    number,
                    row.name,
                    href,
                    row.rarity,
                    row.detail,
                    row.note,
                    joined.code if joined else None,
                    joined.icon if joined else None,
                    joined.date if joined else None,
                    SECTION_PRINTINGS,
                )
            )
    if rows and not any(p.section == SECTION_PRINTINGS for p in printings):
        raise ParseError(f"{len(rows)} 収録 rows but none resolves to a card number in {url}")
    for index, block in enumerate(blocks):
        try:
            targets = [
                n for label in block.numbers or (None,) for n in _targets(label, numbers, url)
            ]
        except ParseError as error:
            log.warning("block-icon row skipped: %s field=blockicon value=%r", error, block.name)
            continue
        for number in targets:
            if (index, number) in used:
                continue
            printings.append(
                Printing(
                    number,
                    block.name,
                    None,
                    None,
                    None,
                    None,
                    block.code,
                    block.icon,
                    block.date,
                    SECTION_BLOCK_ICON,
                )
            )
    return tuple(printings)


def _product_key(name: str) -> str:
    return unicodedata.normalize("NFKC", name).strip()


def _join(
    blocks: list[_BlockRow], name: str, number: str, used: set[tuple[int, str]]
) -> _BlockRow | None:
    """First unused block-icon row of the same product that lists ``number`` (or no number)."""
    for index, block in enumerate(blocks):
        if _product_key(block.name) != _product_key(name) or (index, number) in used:
            continue
        if block.numbers and _faceless(number) not in {_faceless(n) for n in block.numbers}:
            continue
        used.add((index, number))
        return block
    return None


def _caption_lines(caption: Tag) -> list[str]:
    lines = [""]
    for node in caption.children:
        if isinstance(node, Tag) and node.name == "br":
            lines.append("")
        else:
            lines[-1] += node.get_text() if isinstance(node, Tag) else str(node)
    return [line.strip() for line in lines]


def parse_images(soup: BeautifulSoup, url: str, numbers: Sequence[str]) -> tuple[CardImage, ...]:
    """Return the gallery images (one per ``<li>`` of each ``ul.ppy-imglist``).

    URLs are read from ``a[href]`` and ``img[src]`` and made absolute; file names are
    never built. The first caption line is the card number, the rest is the caption.
    """
    images: list[CardImage] = []
    for gallery in soup.select("ul.ppy-imglist"):
        if gallery.find_parent("li") is not None:
            continue
        for item in gallery.find_all("li", recursive=False):
            link = item.find("a")
            thumb = item.find("img")
            caption = item.find("span", class_="ppy-extcaption")
            href = _attr(link, "href") if isinstance(link, Tag) else None
            if href is None:
                raise ParseError(f"gallery image without a link in {url}")
            if not isinstance(caption, Tag):
                if href.endswith(_PLACEHOLDER):  # an announced number with no scan yet
                    alt = _attr(thumb, "alt") if isinstance(thumb, Tag) else None
                    log.warning(
                        "gallery placeholder skipped: %s field=image value=%r", url, alt or href
                    )
                    continue
                raise ParseError(f"gallery image {href!r} without a caption in {url}")
            lines = _caption_lines(caption)
            if not lines[0]:
                raise ParseError(f"gallery image {href!r} without a card number in {url}")
            small = _attr(thumb, "src") if isinstance(thumb, Tag) else None
            rest = lines[1:]
            while rest and not rest[-1]:
                rest.pop()
            for number in _targets(lines[0], numbers, url):
                images.append(
                    CardImage(
                        number,
                        urljoin(url, href),
                        urljoin(url, small) if small else None,
                        tuple(rest),
                    )
                )
    return tuple(images)
