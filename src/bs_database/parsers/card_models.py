"""Card page DTOs produced by the batspi card parser (#70, extended by #71).

Frozen, slotted dataclasses made of tuples only, so ``dataclasses.asdict`` gives
JSON-ready data. Values keep the literal Japanese glyphs of the source; mapping to
codes is the loader's job (#12).
"""

from dataclasses import dataclass

SCHEMA_VERSION = "2.1.0"


@dataclass(frozen=True, slots=True)
class SymbolCount:
    """A colour/symbol glyph with a count, e.g. ``赤`` x 2.

    ``variant`` is a prefix printed before the glyph (``EX`` in ``EX赤``) and ``color`` the
    colour in brackets after a god symbol (``青`` in ``神(青)``); both as printed, None if absent.
    """

    symbol: str
    count: int
    variant: str | None = None
    color: str | None = None


@dataclass(frozen=True, slots=True)
class Reduction:
    """Cost reduction: a plain number, coloured parts, or both absent (``()``)."""

    plain: int | None
    parts: tuple[SymbolCount, ...]


@dataclass(frozen=True, slots=True)
class Level:
    """One level row: level number, cores needed, battle points (None if absent).

    ``cores`` is None when the page prints a condition instead of a count (``<C2>Lv2``,
    kept in ``count_condition``). ``note`` is a remark printed with the level (``真界放``) or a
    battle point that is not a number (``X0000``).
    """

    level: int
    cores: int | None
    battle_points: int | None
    count_condition: str | None = None
    note: str | None = None


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
    card_class: str | None = None
    type_mark: str | None = None


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
class RoleCredit:
    """A credit other than illustrator and concept: the printed role, the name and its note."""

    role: str
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
    other_credits: tuple[RoleCredit, ...] = ()


@dataclass(frozen=True, slots=True)
class Printing:
    """One 収録 row (or block-icon-only row) of a card number."""

    number: str
    product_name_jp: str
    product_href: str | None
    rarity: str | None
    detail_jp: str | None
    note_jp: str | None
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
    name_jp: str
    name_en: str | None
    gameplay: Gameplay
    text: CardText | None = None


@dataclass(frozen=True, slots=True)
class ValueDifference:
    """A gameplay field that differs between numbers of the same card (#63).

    ``values`` holds ``(number, rendered value)`` pairs.
    """

    name_jp: str
    field: str
    values: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class CardPage:
    """Everything parsed from one batspi card page."""

    schema_version: str
    url: str
    title_jp: str
    entries: tuple[CardEntry, ...]
    differences: tuple[ValueDifference, ...]
    printings: tuple[Printing, ...] = ()
    images: tuple[CardImage, ...] = ()
