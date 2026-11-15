"""``normalize_page`` and the parsed-to-normalized tree runner (#93, ADR 0008).

``normalize_page`` is pure: no I/O and no settings. ``normalize_tree`` reads
``<parsed_dir>/<source>/<sha>.json`` and writes ``<normalized_dir>/<source>/<sha>.json``
with the same stem, atomically and byte-identically across runs. ``parsed_dir`` is never
written.
"""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from bs_database.glossary import Glossary
from bs_database.ingest.atomic import atomic_write
from bs_database.ingest.parsed_store import read_card_page
from bs_database.normalize import rules
from bs_database.normalize.records import (
    NORMALIZED_SCHEMA_VERSION,
    SOURCE_BATSPI,
    STATUS_PENDING,
    STATUS_REVIEWED,
    CardTextRecord,
    EffectRecord,
    EntryRecord,
    GameplayRecord,
    NormalizedPage,
    PrintingRecord,
    ReductionRecord,
    UnmappedCollector,
    UnmappedTerm,
)
from bs_database.parsers.card_models import (
    CardEntry,
    CardPage,
    CardText,
    Effect,
    Gameplay,
    Printing,
)

log = logging.getLogger(__name__)


def _gameplay(g: Gameplay, number: str, glossary: Glossary, u: UnmappedCollector) -> GameplayRecord:
    return GameplayRecord(
        card_type_jp=g.card_type,
        card_type_code=rules.closed_code(glossary, "card_types", g.card_type, number, u),
        deck_limit=g.deck_limit,
        cost=g.cost,
        reduction=ReductionRecord(
            g.reduction.plain, rules.map_symbols(glossary, g.reduction.parts, number, u)
        ),
        colors=rules.map_colors(glossary, g.colors, number, u),
        symbols=rules.map_symbols(glossary, g.symbols, number, u),
        families=rules.map_families(glossary, g.families, number, u),
        levels=g.levels,
        fusion_bp_bonus=g.fusion_bp_bonus,
        overclock=g.overclock,
    )


def _effect(e: Effect, number: str, glossary: Glossary, u: UnmappedCollector) -> EffectRecord:
    return EffectRecord(
        position=e.position,
        form=e.form,
        levels=e.levels,
        label=e.label,
        keywords=rules.map_keywords(glossary, e.keywords, number, u),
        timing_jp=e.timing,
        header_jp=e.header,
        text_jp=e.text,
        text_en=None,
        en_source=None,
        en_status=STATUS_PENDING,
    )


def _text(t: CardText, number: str, glossary: Glossary, u: UnmappedCollector) -> CardTextRecord:
    return CardTextRecord(
        effects=tuple(_effect(e, number, glossary, u) for e in t.effects),
        fusion_conditions_jp=t.fusion_conditions,
        summon_condition_jp=t.summon_condition,
        overclock_condition_jp=t.overclock_condition,
        illustrators=t.illustrators,
        concepts=t.concepts,
        flavor_jp=t.flavor,
        flavor_note_jp=t.flavor_note,
        flavor_en=None,
        en_source=None,
        en_status=STATUS_PENDING,
    )


def _entry(e: CardEntry, glossary: Glossary, u: UnmappedCollector) -> EntryRecord:
    has_name = e.name_en is not None
    return EntryRecord(
        number=e.number,
        name_jp=e.name_jp,
        name_en=e.name_en,
        en_source=SOURCE_BATSPI if has_name else None,
        en_status=STATUS_REVIEWED if has_name else STATUS_PENDING,
        gameplay=_gameplay(e.gameplay, e.number, glossary, u),
        text=None if e.text is None else _text(e.text, e.number, glossary, u),
    )


def _printing(p: Printing, glossary: Glossary, u: UnmappedCollector) -> PrintingRecord:
    variant_jp, variant = rules.variant_code(glossary, p.note_jp)
    return PrintingRecord(
        number=p.number,
        product_name_jp=p.product_name_jp,
        product_name_en=None,
        product_en_source=None,
        product_en_status=STATUS_PENDING,
        product_href=p.product_href,
        product_code=p.product_code,
        product_type_code=rules.product_type_code(glossary, p.product_name_jp),
        rarity_jp=p.rarity,
        rarity_code=rules.rarity_code(glossary, p.rarity, p.number, u),
        variant_jp=variant_jp,
        variant_code=variant,
        detail_jp=p.detail_jp,
        note_jp=p.note_jp,
        block_icon=p.block_icon,
        release_date=p.release_date,
        section=p.section,
    )


def normalize_page(page: CardPage, glossary: Glossary) -> NormalizedPage:
    """Map every Japanese glyph of ``page`` to a code. Pure and deterministic."""
    u = UnmappedCollector()
    entries = tuple(_entry(e, glossary, u) for e in page.entries)
    printings = tuple(_printing(p, glossary, u) for p in page.printings)
    return NormalizedPage(
        url=page.url,
        title_jp=page.title_jp,
        entries=entries,
        differences=page.differences,
        printings=printings,
        images=page.images,
        unmapped=u.terms(),
        uncurated=u.uncurated_terms(),
    )


@dataclass(frozen=True, slots=True)
class TreeResult:
    """Outcome of one :func:`normalize_tree` run."""

    written: int
    failed: tuple[Path, ...]
    unmapped: tuple[UnmappedTerm, ...]

    @property
    def closed(self) -> int:
        """Number of closed unmapped terms (errors)."""
        return sum(1 for t in self.unmapped if t.closed)


def normalize_tree(parsed_dir: Path, normalized_dir: Path, glossary: Glossary) -> TreeResult:
    """Normalize every ``<parsed_dir>/<source>/*.json`` into ``normalized_dir``.

    A page with a closed unmapped term, or a parsed file that cannot be read, is not written
    and counted as failed; the run continues. Normalized files whose parsed source was
    deleted are not pruned.
    """
    written = 0
    failed: list[Path] = []
    unmapped: list[UnmappedTerm] = []
    for path in sorted(parsed_dir.glob("*/*.json")):
        try:
            page, provenance = read_card_page(path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.error("cannot read %s: %s", path, exc)
            failed.append(path)
            continue
        result = normalize_page(page, glossary)
        unmapped.extend(result.unmapped)
        if any(t.closed for t in result.unmapped):
            log.error("%s: closed unmapped terms, page not written", path)
            failed.append(path)
            continue
        document = {
            "schema_version": NORMALIZED_SCHEMA_VERSION,
            "parsed_schema_version": page.schema_version,
            "url": page.url,
            "provenance": provenance,
            "page": asdict(result),
        }
        target = normalized_dir / path.parent.name / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        atomic_write(target, text.encode("utf-8"))
        written += 1
    return TreeResult(written, tuple(failed), tuple(unmapped))
