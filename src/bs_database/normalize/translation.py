"""Pure helpers that connect normalized pages to a translator (#95, ADR 0008).

No I/O: :func:`collect_requests` lists what needs machine translation and
:func:`apply_translations` returns a new page with the results filled in.

Lookup order: a family English name from the glossary (``manual/reviewed``) and a card name
printed by batspi (``batspi/reviewed``) are kept; every other card name, product name and
family goes to the translator. Effect, flavor and condition texts are never translated here.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace

from bs_database.normalize.records import (
    EntryRecord,
    FamilyRecord,
    NormalizedPage,
    PrintingRecord,
)
from bs_database.translate.types import TranslationResult


@dataclass(frozen=True, slots=True)
class TranslationRequests:
    """Japanese texts to translate, per category, each sorted and without duplicates."""

    families: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    products: tuple[str, ...] = ()

    def ordered(self) -> list[str]:
        """Families, then names, then products, so short family names fit any budget first."""
        return [*self.families, *self.names, *self.products]


def _needed(texts: list[str]) -> tuple[str, ...]:
    return tuple(sorted({t for t in texts if t.strip()}))


def collect_requests(page: NormalizedPage) -> TranslationRequests:
    """The texts of ``page`` that have no English name yet."""
    families = [f.jp for e in page.entries for f in e.gameplay.families if f.en is None]
    names = [e.name_jp for e in page.entries if e.name_en is None]
    products = [p.product_name_jp for p in page.printings if p.product_name_en is None]
    return TranslationRequests(_needed(families), _needed(names), _needed(products))


def collect_texts(page: NormalizedPage) -> TranslationRequests:
    """Every family, card name and product name of ``page``, with or without English."""
    families = [f.jp for e in page.entries for f in e.gameplay.families]
    names = [e.name_jp for e in page.entries]
    products = [p.product_name_jp for p in page.printings]
    return TranslationRequests(_needed(families), _needed(names), _needed(products))


def _fields(result: TranslationResult) -> tuple[str | None, str | None, str]:
    """``(en, en_source, en_status)`` for a result."""
    if result.status == "machine" and result.text is not None:
        return result.text, "machine", "machine"
    return None, None, result.status


def _family(f: FamilyRecord, results: Mapping[str, TranslationResult]) -> FamilyRecord:
    result = results.get(f.jp)
    if f.en is not None or result is None:
        return f
    en, source, status = _fields(result)
    return replace(f, en=en, en_source=source, en_status=status)


def _entry(e: EntryRecord, results: Mapping[str, TranslationResult]) -> EntryRecord:
    families = tuple(_family(f, results) for f in e.gameplay.families)
    gameplay = replace(e.gameplay, families=families)
    result = results.get(e.name_jp)
    if e.name_en is not None or result is None:
        return replace(e, gameplay=gameplay)
    en, source, status = _fields(result)
    return replace(e, gameplay=gameplay, name_en=en, en_source=source, en_status=status)


def _printing(p: PrintingRecord, results: Mapping[str, TranslationResult]) -> PrintingRecord:
    result = results.get(p.product_name_jp)
    if p.product_name_en is not None or result is None:
        return p
    en, source, status = _fields(result)
    return replace(p, product_name_en=en, product_en_source=source, product_en_status=status)


def apply_translations(
    page: NormalizedPage, results: Mapping[str, TranslationResult]
) -> NormalizedPage:
    """A new page with ``results`` (keyed by Japanese text) applied.

    ``machine`` gives ``en=text`` with source and status ``machine``; ``failed`` and
    ``pending`` give ``en=None``, no source and that status. Fields that already have an
    English name, and texts absent from ``results``, are left as they are.
    """
    return replace(
        page,
        entries=tuple(_entry(e, results) for e in page.entries),
        printings=tuple(_printing(p, results) for p in page.printings),
    )
