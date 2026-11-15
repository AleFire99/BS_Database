"""Card page DTOs produced by the batspi card parser (#70, extended by #71).

Frozen, slotted dataclasses made of tuples only, so ``dataclasses.asdict`` gives
JSON-ready data. Values keep the literal Japanese glyphs of the source; mapping to
codes is the loader's job (#12).
"""

from dataclasses import dataclass

SCHEMA_VERSION = "1.0.0"


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
class CardEntry:
    """One card number on the page with its names and gameplay values."""

    number: str
    name_ja: str
    name_en: str | None
    gameplay: Gameplay


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
