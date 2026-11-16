"""Pure mapping rules (#93, ADR 0008). Every mapping goes through ``Glossary.lookup``.

Each rule takes the glossary and an :class:`UnmappedCollector` and returns records; a miss
is reported to the collector and never raises. Whether a miss is an error or a warning is
decided by the kind (see :attr:`UnmappedTerm.closed`).
"""

from bs_database.glossary import Entry, FamilyEntry, Glossary
from bs_database.normalize.records import (
    SOURCE_MANUAL,
    STATUS_PENDING,
    STATUS_REVIEWED,
    CodedTerm,
    FamilyRecord,
    KeywordRecord,
    SymbolCountRecord,
    UnmappedCollector,
)
from bs_database.parsers.card_models import Keyword, SymbolCount

DEFAULT_VARIANT = "normal"


def closed_code(
    glossary: Glossary, kind: str, jp: str, number: str, unmapped: UnmappedCollector
) -> str | None:
    """Code of ``jp`` in the closed ``kind``, or ``None`` after reporting the miss."""
    entry = glossary.lookup(kind, jp)
    if entry is None:
        unmapped.add(kind, jp, number)
        return None
    return entry.code


def map_colors(
    glossary: Glossary, colors: tuple[str, ...], number: str, unmapped: UnmappedCollector
) -> tuple[CodedTerm, ...]:
    """Colour glyphs to :class:`CodedTerm` in source order."""
    return tuple(CodedTerm(c, closed_code(glossary, "colors", c, number, unmapped)) for c in colors)


def map_symbols(
    glossary: Glossary,
    symbols: tuple[SymbolCount, ...],
    number: str,
    unmapped: UnmappedCollector,
) -> tuple[SymbolCountRecord, ...]:
    """Symbol glyphs with counts to records carrying the symbol code."""
    return tuple(
        SymbolCountRecord(
            s.symbol, closed_code(glossary, "symbols", s.symbol, number, unmapped), s.count
        )
        for s in symbols
    )


def rarity_code(
    glossary: Glossary, rarity: str | None, number: str, unmapped: UnmappedCollector
) -> str | None:
    """Rarity code; ``None`` stays ``None``, a value missing from the glossary is reported."""
    if rarity is None:
        return None
    return closed_code(glossary, "rarities", rarity, number, unmapped)


def variant_code(glossary: Glossary, note: str | None) -> tuple[str | None, str]:
    """``(variant_jp, variant_code)`` from a printing note.

    A note that is not a known variant means ``normal`` and is never unmapped (ADR 0008, D5).
    """
    if note is not None:
        entry = glossary.lookup("variants", note)
        if entry is not None:
            return note, entry.code
    return None, DEFAULT_VARIANT


def product_type_code(
    glossary: Glossary, product_name: str, product_code: str | None = None
) -> str | None:
    """Product type: a title marker in the name wins, else the longest ``product_code`` prefix.

    A collab starter such as ``SD54`` stays ``collab`` because its title carries the marker
    (ADR 0008, D6). No marker and no matching prefix gives ``None``.
    """
    for entry in glossary.entries["product_types"]:
        if entry.jp and entry.jp in product_name:
            return entry.code
    return glossary.product_type_for_code(product_code)


def merge_family_tokens(glossary: Glossary, tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Re-join adjacent tokens whose ``・``-joined form is a ``no_split`` glossary family.

    The parser splits on ``・``. Tokens are stripped of surrounding whitespace (``衣装 `` and
    ``衣装`` are the same family) and empty ones dropped. Order is source order and duplicates
    are removed.
    """
    tokens = tuple(t for token in tokens if (t := token.strip()))
    merged: list[str] = []
    i = 0
    while i < len(tokens):
        joined = _longest_no_split(glossary, tokens, i)
        if joined is None:
            merged.append(tokens[i])
            i += 1
        else:
            text, size = joined
            merged.append(text)
            i += size
    return tuple(dict.fromkeys(merged))


def _longest_no_split(
    glossary: Glossary, tokens: tuple[str, ...], start: int
) -> tuple[str, int] | None:
    for size in range(len(tokens) - start, 1, -1):
        text = "・".join(tokens[start : start + size])
        entry = glossary.lookup("families", text)
        if isinstance(entry, FamilyEntry) and entry.no_split:
            return text, size
    return None


def _report_miss(
    unmapped: UnmappedCollector, kind: str, jp: str, number: str, entry: Entry | None
) -> None:
    """No row is unmapped; a row without a code is uncurated; otherwise nothing."""
    if entry is None:
        unmapped.add(kind, jp, number)
    elif not entry.code:
        unmapped.add_uncurated(kind, jp, number)


def map_families(
    glossary: Glossary, tokens: tuple[str, ...], number: str, unmapped: UnmappedCollector
) -> tuple[FamilyRecord, ...]:
    """Family tokens to records.

    A family with no glossary row is an unmapped warning; a row with an empty code is
    uncurated (reported apart, not a warning).

    An English name from the glossary is curated by the owner: source ``manual``, status
    ``reviewed``. Without one the name is ``None`` and pending.
    """
    records: list[FamilyRecord] = []
    for jp in merge_family_tokens(glossary, tokens):
        entry = glossary.lookup("families", jp)
        code = entry.code if entry is not None and entry.code else None
        _report_miss(unmapped, "families", jp, number, entry)
        en = entry.en if entry is not None and entry.en else None
        if en is None:
            records.append(FamilyRecord(jp, code, None, None, STATUS_PENDING))
        else:
            records.append(FamilyRecord(jp, code, en, SOURCE_MANUAL, STATUS_REVIEWED))
    return tuple(records)


def map_keywords(
    glossary: Glossary, keywords: tuple[Keyword, ...], number: str, unmapped: UnmappedCollector
) -> tuple[KeywordRecord, ...]:
    """Keyword tokens to records; no code gives ``None`` (unmapped or uncurated, see above).

    The name is stripped of surrounding whitespace.
    """
    records: list[KeywordRecord] = []
    for k in keywords:
        name = k.name.strip()
        entry = glossary.lookup("keywords", name)
        code = entry.code if entry is not None and entry.code else None
        _report_miss(unmapped, "keywords", name, number, entry)
        records.append(KeywordRecord(k.bracket, name, code, k.parameter))
    return tuple(records)
