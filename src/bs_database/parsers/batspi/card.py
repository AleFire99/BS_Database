"""Parser for batspi.com card pages. Implemented in #70 and #71.

#70 reads identity (numbers, names) and gameplay values (type, cost, reduction,
colours, families, levels, symbols). #71 adds effects, side conditions, credits and
flavour (``card_text``), then printings and images (``card_sections``).
"""

import dataclasses
import logging
import re

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from bs_database.parsers.batspi.card_sections import parse_images, parse_printings
from bs_database.parsers.batspi.card_text import parse_card_text
from bs_database.parsers.card_models import (
    SCHEMA_VERSION,
    CardEntry,
    CardPage,
    CardText,
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

CARD_CLASSES = ("契約", "トークン")
_LIMIT_MARK = "制限カード"
TYPE_LINE_RE = re.compile(
    rf"^(?:({'|'.join(CARD_CLASSES)}))?({'|'.join(CARD_TYPES)})\s*"
    rf"(?:\((?!{_LIMIT_MARK})([^()<>]+)\))?\s*(?:\({_LIMIT_MARK}<(\d+)>\))?\s*$"
)
COST_LINE_RE = re.compile(r"^(\d+)\(([^()]*)\)/([^/]*)(?:/(.*))?$")
NO_COLOR_TOKEN = "(なし)"  # the colour slot of a colourless card, e.g. ``15(0)/(なし)``
_LEVEL_HEAD = r"<(?P<cores>[^<>]+)>\s*(?:(?P<cond>条件[:：]\S+)\s*)?Lv(?P<level>\d+)"
LEVEL_LINE_RE = re.compile(rf"^{_LEVEL_HEAD}")
_LEVEL_TOKEN_RE = re.compile(
    rf"{_LEVEL_HEAD}(?:/(?P<note>[^\s<]+))?(?:\s+(?P<points>\d+|X\d+)(?=\s|$))?"
)
_FUSION_TOKEN_RE = re.compile(r"<\d+>\s*合体\s*\+(\d+)")
_OVERCLOCK_TOKEN_RE = re.compile(r"OC<(\d+)\+>\s*\+(\d+)")
_PART_RE = re.compile(rf"(?P<glyph>[{REDUCTION_GLYPHS}])(?P<count>\d*)")
_SYMBOL_RE = re.compile(
    rf"(?P<variant>EX)?(?P<glyph>[{SYMBOL_GLYPHS}])(?:\((?P<color>[{COLORS}])\))?(?P<count>\d*)"
)
SYMBOL_PREFIX = "シンボル："


def parse_type_line(line: str) -> tuple[str, int | None, str | None, str | None]:
    """Return ``(card_type, deck_limit, card_class, type_mark)`` from a card block's first line.

    ``契約スピリット`` gives the class ``契約``; ``スピリット(光)`` and ``スピリット(禁止カード)``
    give the mark as printed. The card type stays one of the five base types.
    """
    match = TYPE_LINE_RE.match(line)
    if match is None:
        raise ParseError(f"unknown type line: {line!r}")
    limit = match.group(4)
    return match.group(2), int(limit) if limit is not None else None, match.group(1), match.group(3)


def _parts(text: str, pattern: re.Pattern[str], what: str) -> tuple[SymbolCount, ...]:
    """Split ``赤2神1`` into counted glyphs, adding up repeated glyphs in order."""
    counts: dict[tuple[str, str | None, str | None], int] = {}
    pos = 0
    while pos < len(text):
        match = pattern.match(text, pos)
        if match is None:
            raise ParseError(f"unknown {what} syntax: {text!r}")
        found = match.groupdict()
        key = (found["glyph"], found.get("variant"), found.get("color"))
        counts[key] = counts.get(key, 0) + int(found["count"] or 1)
        pos = match.end()
    return tuple(
        SymbolCount(g, count, variant, color) for (g, variant, color), count in counts.items()
    )


def parse_cost_line(line: str) -> tuple[int, Reduction, tuple[str, ...], tuple[str, ...]]:
    """Return ``(cost, reduction, colors, families)`` from ``N(reduction)/colours[/families]``.

    Tolerates what the pages print: trailing blanks, a trailing ``/`` (``4(2)/白/``), and
    ``(なし)`` or nothing for a colourless card.
    """
    match = COST_LINE_RE.match(line.strip())
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
    color_text = match.group(3).strip()
    colors = () if color_text in ("", NO_COLOR_TOKEN) else tuple(color_text)
    for color in colors:
        if color not in COLORS:
            raise ParseError(f"unknown colour {color!r} in cost line: {line!r}")
    family_text = (match.group(4) or "").strip().rstrip("/").strip()
    families = tuple(family_text.split("・")) if family_text else ()
    return cost, reduction, colors, families


def parse_level_line(
    line: str,
) -> tuple[tuple[Level, ...], int | None, Overclock | None]:
    """Return ``(levels, fusion_bp_bonus, overclock)`` from a level line.

    Tolerates a blank after ``<n>``, a core slot that is not a number (``<C2>Lv2``, kept in
    ``count_condition``), a remark after the level (``Lv2/真界放``) and a battle point
    printed as text (``X0000``, kept in ``note``).
    """
    levels: list[Level] = []
    fusion: int | None = None
    overclock: Overclock | None = None
    pos = 0
    while pos < len(line):
        if line[pos].isspace():
            pos += 1
        elif match := _LEVEL_TOKEN_RE.match(line, pos):
            cores_text = match.group("cores")
            cores = int(cores_text) if cores_text.isdigit() else None
            condition = match.group("cond") or (None if cores is not None else cores_text)
            points_text = match.group("points")
            points = int(points_text) if points_text and points_text.isdigit() else None
            notes = [n for n in (match.group("note"), points_text if points is None else None) if n]
            levels.append(
                Level(int(match.group("level")), cores, points, condition, "/".join(notes) or None)
            )
            pos = match.end()
        elif match := _FUSION_TOKEN_RE.match(line, pos):
            fusion = int(match.group(1))
            pos = match.end()
        elif match := _OVERCLOCK_TOKEN_RE.match(line, pos):
            overclock = Overclock(int(match.group(1)), int(match.group(2)))
            pos = match.end()
        else:
            raise ParseError(f"unknown level token {line[pos:].split()[0]!r} in: {line!r}")
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
    """Split ``名前/English <number>`` into ``(name_jp, name_en, number)``."""
    number: str | None = None
    match = _TRAILING_NUMBER_RE.search(text)
    if match:
        number = match.group(1).strip()
        text = text[: match.start()]
    name_jp, name_en = text.strip(), None
    english = re.search(r"/(?=[A-Za-z0-9])", text)
    if english:
        name_jp, name_en = text[: english.start()].strip(), text[english.end() :].strip()
    return name_jp, name_en or None, number


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


def _pre_lines(pre: Tag) -> list[str]:
    return [line.rstrip("\r") for line in pre.get_text().split("\n")]


def _parse_gameplay(lines: list[str], url: str) -> Gameplay:
    if len(lines) < 2:
        raise ParseError(f"card block without a cost line in {url}")
    card_type, deck_limit, card_class, type_mark = parse_type_line(lines[0])
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
        card_class=card_class,
        type_mark=type_mark,
    )


def _parse_text(lines: list[str], gameplay: Gameplay, number: str, url: str) -> CardText:
    """Parse the lines after the type, cost and level lines of a card block."""
    start = 3 if len(lines) > 2 and LEVEL_LINE_RE.match(lines[2]) else 2
    levels = {level.level for level in gameplay.levels}
    return parse_card_text(lines[start:], levels, f"{number} in {url}")


def _title(soup: BeautifulSoup) -> str:
    if soup.title is None:
        return ""
    text = soup.title.get_text().strip()
    return text.removesuffix(_TITLE_SUFFIX).strip()


_TEXT_DIFF_FIELDS = (
    "effects",
    "fusion_conditions",
    "summon_condition",
    "overclock_condition",
    "flavor",
)


def _differences(entries: list[CardEntry]) -> tuple[ValueDifference, ...]:
    """Gameplay and text fields that differ between numbers of the same name (#63).

    Credits (illustrators, concepts) and the flavour note are printing-level and
    excluded: they differ per print by nature.
    """
    groups: dict[str, list[CardEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.name_jp, []).append(entry)
    found: list[ValueDifference] = []
    for name_jp, group in groups.items():
        if len(group) < 2:
            continue
        sources: list[tuple[str, list[tuple[str, object]]]] = []
        for field in dataclasses.fields(Gameplay):
            sources.append(
                (field.name, [(e.number, getattr(e.gameplay, field.name)) for e in group])
            )
        for name in _TEXT_DIFF_FIELDS:
            sources.append((name, [(e.number, getattr(e.text, name, None)) for e in group]))
        for name, pairs in sources:
            if all(value == pairs[0][1] for _, value in pairs[1:]):
                continue
            values = tuple((number, repr(value)) for number, value in pairs)
            found.append(ValueDifference(name_jp, name, values))
            log.info("per-number values differ: %s field=%s values=%s", name_jp, name, values)
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
        name_jp, name_en, h3_number = (
            _split_heading(_h3_text(heading)) if heading is not None else ("", None, None)
        )
        numbers: list[str]
        if h3_number is not None:
            numbers = [h3_number]
            if own and _FACE_RE.sub("", h3_number) not in own:
                log.warning(
                    "source conflict: field=number h3=%r cardno=%r in %s", h3_number, own, url
                )
        elif len(own) == len(blocks):
            numbers = [own[index]]
        elif len(blocks) == 1 and own:
            # one block printed once for several numbers: each gets its own entry
            numbers = list(own)
            log.warning("one card block shared by the numbers %s in %s", own, url)
        else:
            raise ParseError(
                f"{len(blocks)} card blocks without h3 numbers but {len(own)} card numbers in {url}"
            )
        if name_jp:
            titles = title.split("／")
            if title and name_jp not in (title, *titles):
                log.warning(
                    "source conflict: field=name_jp number=%s h3=%r title=%r in %s",
                    numbers[0],
                    name_jp,
                    title,
                    url,
                )
        else:
            name_jp = title
        if not name_jp:
            raise ParseError(f"no card name for {numbers[0]} in {url}")
        lines = _pre_lines(pre)
        gameplay = _parse_gameplay(lines, url)
        for number in numbers:
            text = _parse_text(lines, gameplay, number, url)
            entries.append(CardEntry(number, name_jp, name_en, gameplay, text))
    printings = parse_printings(soup, url, [e.number for e in entries])
    images = parse_images(soup, url, [e.number for e in entries])
    return CardPage(
        SCHEMA_VERSION,
        url,
        title,
        tuple(entries),
        _differences(entries),
        printings=printings,
        images=images,
    )
