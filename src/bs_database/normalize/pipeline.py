"""``normalize_page`` and the parsed-to-normalized tree runner (#93, ADR 0008).

``normalize_page`` is pure: no I/O and no settings. ``normalize_tree`` reads
``<parsed_dir>/<source>/<sha>.json`` and writes ``<normalized_dir>/<source>/<sha>.json``
with the same stem, atomically and byte-identically across runs. ``parsed_dir`` is never
written.

``normalize_tree`` streams the tree twice so it never holds every page in memory: pass 1
normalizes each page and keeps only the texts to translate; one batched ``translate`` call
follows; pass 2 normalizes again, applies the results and writes.
"""

import json
import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
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
from bs_database.normalize.translation import (
    TranslationRequests,
    apply_translations,
    collect_requests,
    collect_texts,
)
from bs_database.parsers.card_models import (
    CardEntry,
    CardPage,
    CardText,
    Effect,
    Gameplay,
    Printing,
)
from bs_database.translate.types import TranslationResult, Translator

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
    """Outcome of one :func:`normalize_tree` run.

    ``requests`` are the texts sent for translation and ``translations`` their results;
    ``texts`` are all distinct texts of the written pages. ``unmapped_pages`` and
    ``uncurated_pages`` map ``(kind, jp)`` to the URLs of the pages where it was seen.
    """

    written: int
    failed: tuple[Path, ...]
    unmapped: tuple[UnmappedTerm, ...]
    uncurated: tuple[UnmappedTerm, ...] = ()
    requests: TranslationRequests = field(default_factory=TranslationRequests)
    translations: Mapping[str, TranslationResult] = field(default_factory=dict)
    texts: TranslationRequests = field(default_factory=TranslationRequests)
    unmapped_pages: Mapping[tuple[str, str], frozenset[str]] = field(default_factory=dict)
    uncurated_pages: Mapping[tuple[str, str], frozenset[str]] = field(default_factory=dict)

    @property
    def closed(self) -> int:
        """Number of closed unmapped terms (errors)."""
        return sum(1 for t in self.unmapped if t.closed)


def _load(
    path: Path, glossary: Glossary
) -> tuple[CardPage, dict[str, object], NormalizedPage] | None:
    """Read and normalize one parsed file; ``None`` (logged) when it cannot be read."""
    try:
        page, provenance = read_card_page(path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.error("cannot read %s: %s", path, exc)
        return None
    return page, provenance, normalize_page(page, glossary)


def _write(
    normalized_dir: Path,
    path: Path,
    page: CardPage,
    provenance: dict[str, object],
    result: NormalizedPage,
) -> None:
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


def normalize_tree(
    parsed_dir: Path, normalized_dir: Path, glossary: Glossary, translator: Translator
) -> TreeResult:
    """Normalize every ``<parsed_dir>/<source>/*.json`` into ``normalized_dir``.

    Card names, product names and families without an English name are translated with
    ``translator`` in one batched call (pass a ``NullTranslator`` to stay offline). A page
    with a closed unmapped term, or a parsed file that cannot be read, is not written, is
    counted as failed and sends nothing to the translator; the run continues. Normalized
    files whose parsed source was deleted are not pruned.
    """
    failed: list[Path] = []
    unmapped: list[UnmappedTerm] = []
    uncurated: list[UnmappedTerm] = []
    families: set[str] = set()
    names: set[str] = set()
    products: set[str] = set()
    all_families: set[str] = set()
    all_names: set[str] = set()
    all_products: set[str] = set()
    unmapped_pages: dict[tuple[str, str], set[str]] = {}
    uncurated_pages: dict[tuple[str, str], set[str]] = {}
    good: list[Path] = []
    for path in sorted(parsed_dir.glob("*/*.json")):
        loaded = _load(path, glossary)
        if loaded is None:
            failed.append(path)
            continue
        result = loaded[2]
        unmapped.extend(result.unmapped)
        uncurated.extend(result.uncurated)
        for t in result.unmapped:
            unmapped_pages.setdefault((t.kind, t.jp), set()).add(result.url)
        for t in result.uncurated:
            uncurated_pages.setdefault((t.kind, t.jp), set()).add(result.url)
        if any(t.closed for t in result.unmapped):
            log.error("%s: closed unmapped terms, page not written", path)
            failed.append(path)
            continue
        present = collect_texts(result)
        all_families.update(present.families)
        all_names.update(present.names)
        all_products.update(present.products)
        wanted = collect_requests(result)
        families.update(wanted.families)
        names.update(wanted.names)
        products.update(wanted.products)
        good.append(path)
    requests = TranslationRequests(
        tuple(sorted(families)), tuple(sorted(names)), tuple(sorted(products))
    )
    to_send = requests.ordered()
    results = dict(zip(to_send, translator.translate(to_send), strict=True)) if to_send else {}
    written = 0
    for path in good:
        loaded = _load(path, glossary)
        if loaded is None:
            failed.append(path)
            continue
        page, provenance, result = loaded
        _write(normalized_dir, path, page, provenance, apply_translations(result, results))
        written += 1
    return TreeResult(
        written,
        tuple(failed),
        tuple(unmapped),
        tuple(uncurated),
        requests,
        results,
        TranslationRequests(
            tuple(sorted(all_families)), tuple(sorted(all_names)), tuple(sorted(all_products))
        ),
        {k: frozenset(v) for k, v in unmapped_pages.items()},
        {k: frozenset(v) for k, v in uncurated_pages.items()},
    )
