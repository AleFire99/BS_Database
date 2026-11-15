"""Normalized record shapes (#93, ADR 0008).

Frozen, slotted dataclasses made of tuples only, so ``dataclasses.asdict`` gives JSON-ready
data. Japanese values are kept next to the codes they map to (``*_jp`` / ``*_code``); a
``None`` English text means "not translated" (ADR 0008, row-pair rule).
"""

from dataclasses import dataclass

from bs_database.glossary import CLOSED
from bs_database.parsers.card_models import CardImage, Credit, Level, Overclock, ValueDifference

NORMALIZED_SCHEMA_VERSION = "1.0.0"

SOURCE_BATSPI = "batspi"
SOURCE_MANUAL = "manual"
STATUS_REVIEWED = "reviewed"
STATUS_PENDING = "pending"


@dataclass(frozen=True, slots=True)
class UnmappedTerm:
    """A Japanese value with no glossary entry of ``kind``, seen on card ``number``."""

    kind: str
    jp: str
    number: str

    @property
    def closed(self) -> bool:
        """True for a closed kind (an error); families and keywords are warnings."""
        return self.kind in CLOSED


class UnmappedCollector:
    """Gathers unmapped terms of one page; :meth:`terms` is deduplicated and sorted."""

    def __init__(self) -> None:
        self._terms: set[UnmappedTerm] = set()

    def add(self, kind: str, jp: str, number: str) -> None:
        """Record that ``jp`` has no ``kind`` glossary entry on card ``number``."""
        self._terms.add(UnmappedTerm(kind, jp, number))

    def terms(self) -> tuple[UnmappedTerm, ...]:
        """All recorded terms in a stable order."""
        return tuple(sorted(self._terms, key=lambda t: (t.kind, t.jp, t.number)))


@dataclass(frozen=True, slots=True)
class CodedTerm:
    """A Japanese value and its glossary code (``None`` when unmapped)."""

    jp: str
    code: str | None


@dataclass(frozen=True, slots=True)
class SymbolCountRecord:
    """A symbol glyph with its code and count."""

    symbol_jp: str
    symbol_code: str | None
    count: int


@dataclass(frozen=True, slots=True)
class ReductionRecord:
    """Cost reduction: a plain number, coloured parts, or both absent."""

    plain: int | None
    parts: tuple[SymbolCountRecord, ...]


@dataclass(frozen=True, slots=True)
class FamilyRecord:
    """A family with its code and English name when the glossary has them."""

    jp: str
    code: str | None
    en: str | None
    en_source: str | None
    en_status: str


@dataclass(frozen=True, slots=True)
class GameplayRecord:
    """Gameplay values with every glyph mapped to a code."""

    card_type_jp: str
    card_type_code: str | None
    deck_limit: int | None
    cost: int
    reduction: ReductionRecord
    colors: tuple[CodedTerm, ...]
    symbols: tuple[SymbolCountRecord, ...]
    families: tuple[FamilyRecord, ...]
    levels: tuple[Level, ...]
    fusion_bp_bonus: int | None
    overclock: Overclock | None


@dataclass(frozen=True, slots=True)
class KeywordRecord:
    """A keyword token with its glossary code (``None`` when unmapped)."""

    bracket: str
    name_jp: str
    code: str | None
    parameter_jp: str | None


@dataclass(frozen=True, slots=True)
class EffectRecord:
    """One effect block; ``text_en`` stays ``None`` until a later translation step."""

    position: int
    form: str
    levels: tuple[int, ...]
    label: str | None
    keywords: tuple[KeywordRecord, ...]
    timing_jp: str | None
    header_jp: str | None
    text_jp: str
    text_en: str | None
    en_source: str | None
    en_status: str


@dataclass(frozen=True, slots=True)
class CardTextRecord:
    """Effects, side conditions, credits and flavour text of one card number."""

    effects: tuple[EffectRecord, ...]
    fusion_conditions_jp: tuple[str, ...]
    summon_condition_jp: str | None
    overclock_condition_jp: str | None
    illustrators: tuple[Credit, ...]
    concepts: tuple[Credit, ...]
    flavor_jp: str | None
    flavor_note_jp: str | None
    flavor_en: str | None
    en_source: str | None
    en_status: str


@dataclass(frozen=True, slots=True)
class EntryRecord:
    """One card number with its names, gameplay and text."""

    number: str
    name_jp: str
    name_en: str | None
    en_source: str | None
    en_status: str
    gameplay: GameplayRecord
    text: CardTextRecord | None


@dataclass(frozen=True, slots=True)
class PrintingRecord:
    """One printing of a card number with product, rarity and variant codes."""

    number: str
    product_name_jp: str
    product_name_en: str | None
    product_en_source: str | None
    product_en_status: str
    product_href: str | None
    product_code: str | None
    product_type_code: str | None
    rarity_jp: str | None
    rarity_code: str | None
    variant_jp: str | None
    variant_code: str
    detail_jp: str | None
    note_jp: str | None
    block_icon: str | None
    release_date: str | None
    section: str


@dataclass(frozen=True, slots=True)
class NormalizedPage:
    """Everything normalized from one parsed card page."""

    url: str
    title_jp: str
    entries: tuple[EntryRecord, ...]
    differences: tuple[ValueDifference, ...]
    printings: tuple[PrintingRecord, ...]
    images: tuple[CardImage, ...]
    unmapped: tuple[UnmappedTerm, ...]
