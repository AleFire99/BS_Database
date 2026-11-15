"""Parsed record models for the discovery pages (#69); card models live in ``card_models`` (#70)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedNumber:
    """A card number split into its parts."""

    family: str
    series: str | None
    kind: str
    seq: str
    variant: str | None
    face: str | None


@dataclass(frozen=True, slots=True)
class IndexProduct:
    """A product link found on the card list index."""

    name: str
    url: str
    path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IndexPage:
    """The card list index: product links and pages that do not exist yet."""

    products: tuple[IndexProduct, ...]
    missing_pages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ListEntry:
    """One card line of a set page or promo list."""

    number: str
    parsed: ParsedNumber | None
    name: str
    url: str
    rarity: str | None
    copies: int | None
    note: str | None
    section: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SetPage:
    """A parsed set page."""

    title: str
    release_date: str | None
    set_code: str | None
    entries: tuple[ListEntry, ...]

    @property
    def unknown_numbers(self) -> tuple[str, ...]:
        """Numbers that no known scheme recognises, in page order."""
        return tuple(e.number for e in self.entries if e.parsed is None)


@dataclass(frozen=True, slots=True)
class PromoList:
    """The promotion card list."""

    entries: tuple[ListEntry, ...]

    @property
    def unknown_numbers(self) -> tuple[str, ...]:
        """Numbers that no known scheme recognises, in page order."""
        return tuple(e.number for e in self.entries if e.parsed is None)
