"""Card page DTOs produced by the batspi card parser (#70, extended by #71).

Frozen, slotted dataclasses made of tuples only, so ``dataclasses.asdict`` gives
JSON-ready data. Values keep the literal Japanese glyphs of the source; mapping to
codes is the loader's job (#12).
"""

from dataclasses import dataclass

SCHEMA_VERSION = "1.1.0"


@dataclass(frozen=True, slots=True)
class SymbolCount:
    """A colour/symbol glyph with a count, e.g. ``赤`` x 2."""

    symbol: str
    count: int


@dataclass(frozen=True, slots=True)
class Reduction:
    """Cost reduction: a plain number, coloured parts, or both absent (``()``)."""

    plain: int | None
    parts: tuple[SymbolCount, ...]


@dataclass(frozen=True, slots=True)
class Level:
    """One level row: level number, cores needed, battle points (None if absent)."""

    level: int
    cores: int
    battle_points: int | None


@dataclass(frozen=True, slots=True)
class Overclock:
    """Ultimate overclock: from ``count_min`` cores the card gets ``bp_bonus`` BP."""

    count_min: int
    bp_bonus: int


@dataclass(frozen=True, slots=True)
class Gameplay:
    """Gameplay values read from the type, cost, level and symbol lines."""

    card_type: str
    deck_limit: int | None
    cost: int
    reduction: Reduction
    colors: tuple[str, ...]
    symbols: tuple[SymbolCount, ...]
    families: tuple[str, ...]
    levels: tuple[Level, ...]
    fusion_bp_bonus: int | None
    overclock: Overclock | None


@dataclass(frozen=True, slots=True)
class Keyword:
    """A ``【…】``/``《…》`` token of an effect header, split at the first ``：``."""

    bracket: str
    name: str
    parameter: str | None


@dataclass(frozen=True, slots=True)
class Effect:
    """One effect block as printed; the loader derives the effect kind (#12).

    ``form`` is ``header`` (header line plus body), ``keyword_line`` (a one-line
    ``【…】`` block, ``header == text``) or ``plain`` (text without a header).
    ``timing`` keeps the ``『…』`` brackets.
    """

    position: int
    form: str
    levels: tuple[int, ...]
    label: str | None
    keywords: tuple[Keyword, ...]
    timing: str | None
    header: str | None
    text: str


@dataclass(frozen=True, slots=True)
class Credit:
    """An illustrator or concept credit with its optional parenthesised note."""

    name: str
    note: str | None


@dataclass(frozen=True, slots=True)
class CardText:
    """Effects, side conditions, credits and flavour text of one card number."""

    effects: tuple[Effect, ...]
    fusion_conditions: tuple[str, ...]
    summon_condition: str | None
    overclock_condition: str | None
    illustrators: tuple[Credit, ...]
    concepts: tuple[Credit, ...]
    flavor: str | None
    flavor_note: str | None


@dataclass(frozen=True, slots=True)
class Printing:
    """One 収録 row (or block-icon-only row) of a card number."""

    number: str
    product_name_ja: str
    product_href: str | None
    rarity: str | None
    detail_ja: str | None
    note_ja: str | None
    product_code: str | None
    block_icon: str | None
    release_date: str | None
    section: str


@dataclass(frozen=True, slots=True)
class CardImage:
    """One gallery image of a card number, URLs as read from the page (absolute)."""

    number: str
    large_url: str
    small_url: str | None
    caption: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CardEntry:
    """One card number on the page with its names and gameplay values."""

    number: str
    name_ja: str
    name_en: str | None
    gameplay: Gameplay
    text: CardText | None = None


@dataclass(frozen=True, slots=True)
class ValueDifference:
    """A gameplay field that differs between numbers of the same card (#63).

    ``values`` holds ``(number, rendered value)`` pairs.
    """

    name_ja: str
    field: str
    values: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class CardPage:
    """Everything parsed from one batspi card page."""

    schema_version: str
    url: str
    title_ja: str
    entries: tuple[CardEntry, ...]
    differences: tuple[ValueDifference, ...]
    printings: tuple[Printing, ...] = ()
    images: tuple[CardImage, ...] = ()
