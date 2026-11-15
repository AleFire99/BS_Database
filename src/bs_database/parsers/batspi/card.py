"""Parser for batspi.com card pages. Implemented in #70 and #71.

#70 reads identity (numbers, names) and gameplay values (type, cost, reduction,
colours, families, levels, symbols). Text and printings are added by #71.
"""

import dataclasses
import logging
import re

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from bs_database.parsers.card_models import (
    SCHEMA_VERSION,
    CardEntry,
    CardPage,
    Gameplay,
    Level,
    Overclock,
    Reduction,
    SymbolCount,
    ValueDifference,
)
from bs_database.parsers.errors import ParseError

log = logging.getLogger(__name__)

CARD_TYPES = ("スピリット", "ネクサス", "マジック", "ブレイヴ", "アルティメット")
COLORS = "赤紫緑白黄青"
SYMBOL_GLYPHS = COLORS + "神極"
REDUCTION_GLYPHS = SYMBOL_GLYPHS + "全"

TYPE_LINE_RE = re.compile(rf"^({'|'.join(CARD_TYPES)})\s*(?:\(制限カード<(\d+)>\))?\s*$")
COST_LINE_RE = re.compile(r"^(\d+)\(([^()]*)\)/([^/]+)(?:/(.+))?$")
LEVEL_LINE_RE = re.compile(r"^<\d+>Lv\d")
_LEVEL_TOKEN_RE = re.compile(r"^<(\d+)>Lv(\d+)$")
_FUSION_TOKEN_RE = re.compile(r"^<\d+>合体\+(\d+)$")
_OVERCLOCK_TOKEN_RE = re.compile(r"^OC<(\d+)\+>\+(\d+)$")
_PART_RE = re.compile(rf"([{REDUCTION_GLYPHS}])(\d*)")
_SYMBOL_RE = re.compile(rf"([{SYMBOL_GLYPHS}])(\d*)")
SYMBOL_PREFIX = "シンボル："


def parse_type_line(line: str) -> tuple[str, int | None]:
    """Return ``(card_type, deck_limit)`` from the first line of a card block."""
    match = TYPE_LINE_RE.match(line)
    if match is None:
        raise ParseError(f"unknown type line: {line!r}")
    limit = match.group(2)
    return match.group(1), int(limit) if limit is not None else None


def _parts(text: str, pattern: re.Pattern[str], what: str) -> tuple[SymbolCount, ...]:
    """Split ``赤2神1`` into counted glyphs, adding up repeated glyphs in order."""
    counts: dict[str, int] = {}
    pos = 0
    while pos < len(text):
        match = pattern.match(text, pos)
        if match is None:
            raise ParseError(f"unknown {what} syntax: {text!r}")
        counts[match.group(1)] = counts.get(match.group(1), 0) + int(match.group(2) or 1)
        pos = match.end()
    return tuple(SymbolCount(symbol, count) for symbol, count in counts.items())


def parse_cost_line(line: str) -> tuple[int, Reduction, tuple[str, ...], tuple[str, ...]]:
    """Return ``(cost, reduction, colors, families)`` from ``N(reduction)/colours[/families]``."""
    match = COST_LINE_RE.match(line)
    if match is None:
        raise ParseError(f"unknown cost line: {line!r}")
    cost = int(match.group(1))
    inner = match.group(2)
    if inner == "":
        reduction = Reduction(plain=None, parts=())
    elif inner.isdigit():
        reduction = Reduction(plain=int(inner), parts=())
    else:
        reduction = Reduction(plain=None, parts=_parts(inner, _PART_RE, "reduction"))
    colors = tuple(match.group(3))
    for color in colors:
        if color not in COLORS:
            raise ParseError(f"unknown colour {color!r} in cost line: {line!r}")
    family_text = match.group(4)
    families = tuple(family_text.split("・")) if family_text else ()
    return cost, reduction, colors, families


def parse_level_line(
    line: str,
) -> tuple[tuple[Level, ...], int | None, Overclock | None]:
    """Return ``(levels, fusion_bp_bonus, overclock)`` from a level line."""
    tokens = line.split()
    levels: list[Level] = []
    fusion: int | None = None
    overclock: Overclock | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if match := _LEVEL_TOKEN_RE.match(token):
            points: int | None = None
            if index < len(tokens) and tokens[index].isdigit():
                points = int(tokens[index])
                index += 1
            levels.append(Level(int(match.group(2)), int(match.group(1)), points))
        elif match := _FUSION_TOKEN_RE.match(token):
            fusion = int(match.group(1))
        elif match := _OVERCLOCK_TOKEN_RE.match(token):
            overclock = Overclock(int(match.group(1)), int(match.group(2)))
        else:
            raise ParseError(f"unknown level token {token!r} in: {line!r}")
    return tuple(levels), fusion, overclock


def parse_symbol_line(line: str) -> tuple[SymbolCount, ...]:
    """Return the symbols of a ``シンボル：…`` line (``なし`` gives an empty tuple)."""
    if not line.startswith(SYMBOL_PREFIX):
        raise ParseError(f"not a symbol line: {line!r}")
    text = "".join(line[len(SYMBOL_PREFIX) :].split())
    if text == "なし":
        return ()
    return _parts(text, _SYMBOL_RE, "symbol")


_TITLE_SUFFIX = " - バトルスピリッツ wiki"
_TRAILING_NUMBER_RE = re.compile(r"\s*<([^<>]+)>\s*$")
_FACE_RE = re.compile(r"\([A-Z]\)$")
_KNOWN_COLLAPSED_LABELS = ("(エラッタ前)", "体験会でのスペック")


def _h3_text(h3: Tag) -> str:
    """Text of a print heading without ruby readings and the anchor dagger."""
    parts: list[str] = []
    for node in h3.descendants:
        if isinstance(node, NavigableString) and not any(
            isinstance(parent, Tag)
            and (parent.name in ("rt", "rp") or "anchor_super" in (parent.get("class") or []))
            for parent in node.parents
            if parent is not h3
        ):
            parts.append(str(node))
    return "".join(parts).strip()


def _split_heading(text: str) -> tuple[str, str | None, str | None]:
    """Split ``名前/English <number>`` into ``(name_ja, name_en, number)``."""
    number: str | None = None
    match = _TRAILING_NUMBER_RE.search(text)
    if match:
        number = match.group(1).strip()
        text = text[: match.start()]
    name_ja, name_en = text.strip(), None
    english = re.search(r"/(?=[A-Za-z0-9])", text)
    if english:
        name_ja, name_en = text[: english.start()].strip(), text[english.end() :].strip()
    return name_ja, name_en or None, number


def _is_print_heading(h3: Tag) -> bool:
    return h3.find("a", class_="anchor_super") is not None


def _is_gallery_heading(h3: Tag) -> bool:
    return h3.get_text().strip().startswith("カード画像")


def _card_blocks(soup: BeautifulSoup) -> list[tuple[Tag | None, Tag]]:
    """Return ``(print heading, pre)`` pairs of the card region, in page order."""
    blocks: list[tuple[Tag | None, Tag]] = []
    heading: Tag | None = None
    elements = soup.find_all(["h3", "h4", "pre"])
    # A page without any print heading (trimmed) has its card blocks from the start.
    started = not any(
        el.name == "h3" and _is_print_heading(el) and not _is_gallery_heading(el) for el in elements
    )
    for el in elements:
        if el.name == "h3":
            if _is_gallery_heading(el) and started:
                break
            if _is_print_heading(el) and not _is_gallery_heading(el):
                heading, started = el, True
        elif el.name == "h4":
            if started:
                break
        elif started:
            first = el.get_text().split("\n")[0].strip("\r")
            collapsed = el.find_parent(class_="plugin-openclose-contents")
            if collapsed is not None:
                label_tag = collapsed.find_previous_sibling(class_="plugin-openclose-link")
                label = label_tag.get_text().strip() if label_tag else ""
                if TYPE_LINE_RE.match(first) and not any(
                    known in label for known in _KNOWN_COLLAPSED_LABELS
                ):
                    log.warning("unknown collapsed card block %r is skipped", label)
                continue
            if TYPE_LINE_RE.match(first):
                blocks.append((heading, el))
                heading = None
    return blocks


def _own_numbers(soup: BeautifulSoup) -> list[str]:
    """Card numbers of the page itself (not the related listing), de-duplicated in order."""
    numbers: list[str] = []
    for span in soup.select("span.cardno"):
        if span.find_parent("li") is not None:
            continue
        number = span.get_text().strip()
        if number and number not in numbers:
            numbers.append(number)
    return numbers


def _parse_gameplay(pre: Tag, url: str) -> Gameplay:
    lines = [line.rstrip("\r") for line in pre.get_text().split("\n")]
    if len(lines) < 2:
        raise ParseError(f"card block without a cost line in {url}")
    card_type, deck_limit = parse_type_line(lines[0])
    cost, reduction, colors, families = parse_cost_line(lines[1])
    levels: tuple[Level, ...] = ()
    fusion: int | None = None
    overclock: Overclock | None = None
    if len(lines) > 2 and LEVEL_LINE_RE.match(lines[2]):
        levels, fusion, overclock = parse_level_line(lines[2])
    elif card_type != "マジック":
        raise ParseError(f"{card_type} block without a level line in {url}")
    symbol_line = next((line for line in lines[2:] if line.startswith(SYMBOL_PREFIX)), None)
    symbols = parse_symbol_line(symbol_line) if symbol_line is not None else ()
    return Gameplay(
        card_type=card_type,
        deck_limit=deck_limit,
        cost=cost,
        reduction=reduction,
        colors=colors,
        symbols=symbols,
        families=families,
        levels=levels,
        fusion_bp_bonus=fusion,
        overclock=overclock,
    )


def _title(soup: BeautifulSoup) -> str:
    if soup.title is None:
        return ""
    text = soup.title.get_text().strip()
    return text.removesuffix(_TITLE_SUFFIX).strip()


def _differences(entries: list[CardEntry]) -> tuple[ValueDifference, ...]:
    """Gameplay fields that differ between numbers of the same name (#63)."""
    groups: dict[str, list[CardEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.name_ja, []).append(entry)
    found: list[ValueDifference] = []
    for name_ja, group in groups.items():
        if len(group) < 2:
            continue
        for field in dataclasses.fields(Gameplay):
            first = getattr(group[0].gameplay, field.name)
            if all(getattr(e.gameplay, field.name) == first for e in group[1:]):
                continue
            values = tuple((e.number, repr(getattr(e.gameplay, field.name))) for e in group)
            found.append(ValueDifference(name_ja, field.name, values))
            log.info("per-number values differ: %s field=%s values=%s", name_ja, field.name, values)
    return tuple(found)


def parse_card_page(html: str, url: str) -> CardPage:
    """Parse a batspi card page into identity and gameplay values (pure, no I/O)."""
    soup = BeautifulSoup(html, "html.parser")
    title = _title(soup)
    blocks = _card_blocks(soup)
    if not blocks:
        raise ParseError(f"no card <pre> found in {url}")
    own = _own_numbers(soup)
    entries: list[CardEntry] = []
    for index, (heading, pre) in enumerate(blocks):
        name_ja, name_en, h3_number = (
            _split_heading(_h3_text(heading)) if heading is not None else ("", None, None)
        )
        if h3_number is not None:
            number = h3_number
            if own and _FACE_RE.sub("", number) not in own:
                log.warning("source conflict: field=number h3=%r cardno=%r in %s", number, own, url)
        elif len(own) == len(blocks):
            number = own[index]
        else:
            raise ParseError(
                f"{len(blocks)} card blocks without h3 numbers but {len(own)} card numbers in {url}"
            )
        if name_ja:
            titles = title.split("／")
            if title and name_ja not in (title, *titles):
                log.warning(
                    "source conflict: field=name_ja number=%s h3=%r title=%r in %s",
                    number,
                    name_ja,
                    title,
                    url,
                )
        else:
            name_ja = title
        if not name_ja:
            raise ParseError(f"no card name for {number} in {url}")
        entries.append(CardEntry(number, name_ja, name_en, _parse_gameplay(pre, url)))
    return CardPage(SCHEMA_VERSION, url, title, tuple(entries), _differences(entries))
