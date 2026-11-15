"""Parser for batspi.com card pages. Implemented in #70 and #71.

#70 reads identity (numbers, names) and gameplay values (type, cost, reduction,
colours, families, levels, symbols). Text and printings are added by #71.
"""

import re

from bs_database.parsers.card_models import Level, Overclock, Reduction, SymbolCount
from bs_database.parsers.errors import ParseError

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


def _parts(text: str, glyphs: str, what: str) -> tuple[SymbolCount, ...]:
    """Split ``赤2神1`` into counted glyphs, adding up repeated glyphs in order."""
    counts: dict[str, int] = {}
    pos = 0
    pattern = _PART_RE if glyphs == REDUCTION_GLYPHS else _SYMBOL_RE
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
        reduction = Reduction(plain=None, parts=_parts(inner, REDUCTION_GLYPHS, "reduction"))
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
    return _parts(text, SYMBOL_GLYPHS, "symbol")
