"""Turn the corpus, the legacy votes and the current glossary rows into review proposals (#96).

Pure: no I/O. The proposals are what the owner reviews; the CSV rows are the same proposals
in the glossary schema, ready to copy into ``data/glossary`` once the owner agrees.

Proposed English name of a family, in priority order:

1. the glossary row's own ``en`` (``glossary``);
2. a strong legacy link whose legacy name has a ``family_legacy_en`` alias: the preferred
   name (``alias``);
3. a strong legacy link: the legacy name (``legacy``);
4. the machine translation of the normalize run (``machine``);
5. blank.

A weak legacy link never proposes a name; it is shown with its candidates instead.
Keywords get no proposal: the owner writes their English names.
"""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from bs_database.glossary import ProductPrefix, prefix_type_code
from bs_database.review.corpus import Corpus, ProductStat, product_prefix
from bs_database.review.legacy import LinkResult

Row = Mapping[str, str]

FAMILY_COLUMNS = ("jp", "code", "en", "notes", "aliases_en", "no_split")
KEYWORD_COLUMNS = ("jp", "code", "en", "notes")
LEGACY_COLUMNS = ("legacy_en", "preferred_en", "jp", "notes")

SOURCE_GLOSSARY = "glossary"
SOURCE_ALIAS = "alias"
SOURCE_LEGACY = "legacy"
SOURCE_MACHINE = "machine"
NO_SPLIT_MIN_CARDS = 2
SAMPLE_PRODUCTS = 3


def slugify(text: str) -> str:
    """Lowercase ASCII words joined by ``_`` (``Reptile Beast`` gives ``reptile_beast``)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


@dataclass(frozen=True, slots=True)
class FamilyRow:
    """A family of the corpus with its proposal and legacy votes."""

    jp: str
    cards: int
    code: str
    en: str
    source: str
    best: str
    votes: int
    total: int
    strong: bool
    candidates: tuple[tuple[str, int], ...]
    conflict: bool


@dataclass(frozen=True, slots=True)
class KeywordRow:
    """A keyword of the corpus; ``known`` is False when the glossary has no row for it."""

    jp: str
    cards: int
    code: str
    en: str
    known: bool


@dataclass(frozen=True, slots=True)
class NoSplitRow:
    """Two families that always appear together, so ``joined`` may be one family."""

    joined: str
    cards: int


@dataclass(frozen=True, slots=True)
class PrefixRow:
    """A product-code prefix with its products, printings and sample product names."""

    prefix: str
    products: int
    printings: int
    unresolved: int
    types: tuple[str, ...]
    mapped: str
    samples: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LegacyRow:
    """A ``family_legacy_en`` row after the fill; ``status`` says what happened to ``jp``."""

    legacy_en: str
    preferred_en: str
    jp: str
    notes: str
    status: str


@dataclass(frozen=True, slots=True)
class SlugConflict:
    """A slug that two or more families (or an existing code) want."""

    slug: str
    jps: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Review:
    """Everything the review writes."""

    families: tuple[FamilyRow, ...]
    keywords: tuple[KeywordRow, ...]
    no_split: tuple[NoSplitRow, ...]
    prefixes: tuple[PrefixRow, ...]
    legacy: tuple[LegacyRow, ...]
    conflicts: tuple[SlugConflict, ...]
    family_csv: tuple[tuple[str, ...], ...]
    keyword_csv: tuple[tuple[str, ...], ...]
    legacy_csv: tuple[tuple[str, ...], ...]
    no_legacy: tuple[str, ...]


def _proposal(
    jp: str, existing_en: str, link: LinkResult, aliases: Mapping[str, str], corpus: Corpus
) -> tuple[str, str]:
    """``(en, source)`` for a family, in the priority order of the module docstring."""
    if existing_en:
        return existing_en, SOURCE_GLOSSARY
    candidate = link.links.get(jp)
    if candidate is not None and candidate.strong:
        legacy_name = candidate.best[0]
        preferred = aliases.get(legacy_name.casefold())
        if preferred:
            return preferred, SOURCE_ALIAS
        return legacy_name, SOURCE_LEGACY
    machine = corpus.family_machine_en.get(jp)
    if machine:
        return machine, SOURCE_MACHINE
    return "", ""


def _family_rows(
    corpus: Corpus, link: LinkResult, glossary_rows: Sequence[Row], aliases: Mapping[str, str]
) -> tuple[list[FamilyRow], list[SlugConflict], list[tuple[str, ...]]]:
    existing = {r["jp"]: r for r in glossary_rows}
    jps = sorted(set(existing) | set(corpus.family_cards))
    proposed: dict[str, tuple[str, str]] = {}
    for jp in jps:
        row = existing.get(jp, {})
        proposed[jp] = _proposal(jp, row.get("en", ""), link, aliases, corpus)
    taken = {r["code"] for r in glossary_rows if r["code"]}
    wanted: dict[str, list[str]] = defaultdict(list)
    for jp in jps:
        if existing.get(jp, {}).get("code"):
            continue
        slug = slugify(proposed[jp][0])
        if slug:
            wanted[slug].append(jp)
    conflicts = [
        SlugConflict(slug, tuple(owners))
        for slug, owners in sorted(wanted.items())
        if len(owners) > 1 or slug in taken
    ]
    conflicted = {jp for c in conflicts for jp in c.jps}
    rows: list[FamilyRow] = []
    csv_rows: list[tuple[str, ...]] = []
    for jp in jps:
        row = existing.get(jp, {})
        en, source = proposed[jp]
        code = row.get("code", "")
        if not code and jp not in conflicted:
            code = slugify(en)
        vote = link.links.get(jp)
        best, votes = vote.best if vote else ("", 0)
        rows.append(
            FamilyRow(
                jp,
                corpus.family_cards.get(jp, 0),
                code,
                en,
                source,
                best,
                votes,
                vote.total if vote else 0,
                vote.strong if vote else False,
                vote.candidates if vote else (),
                jp in conflicted,
            )
        )
        csv_rows.append(
            (
                jp,
                code,
                en,
                row.get("notes", ""),
                row.get("aliases_en", ""),
                row.get("no_split", ""),
            )
        )
    csv_rows.sort(key=lambda r: (r[1], r[0]))
    rows.sort(key=lambda r: (-r.cards, r.jp))
    return rows, conflicts, csv_rows


def _keyword_rows(
    corpus: Corpus, glossary_rows: Sequence[Row]
) -> tuple[list[KeywordRow], list[tuple[str, ...]]]:
    existing = {r["jp"]: r for r in glossary_rows}
    rows = [
        KeywordRow(
            jp,
            corpus.keyword_cards.get(jp, 0),
            existing.get(jp, {}).get("code", ""),
            existing.get(jp, {}).get("en", ""),
            jp in existing,
        )
        for jp in sorted(set(existing) | set(corpus.keyword_cards))
    ]
    csv_rows: list[tuple[str, ...]] = [
        (r.jp, r.code, r.en, existing.get(r.jp, {}).get("notes", "")) for r in rows
    ]
    csv_rows.sort(key=lambda r: (r[1], r[0]))
    rows.sort(key=lambda r: (-r.cards, r.jp))
    return rows, csv_rows


def _no_split_rows(corpus: Corpus, known: set[str]) -> list[NoSplitRow]:
    """Adjacent pairs where each family occurs only inside that pair."""
    rows = []
    for (left, right), cards in corpus.pairs.items():
        together = (
            cards >= NO_SPLIT_MIN_CARDS
            and corpus.family_cards[left] == cards
            and corpus.family_cards[right] == cards
        )
        joined = f"{left}・{right}"
        if together and joined not in known:
            rows.append(NoSplitRow(joined, cards))
    return sorted(rows, key=lambda r: (-r.cards, r.joined))


def _prefix_rows(corpus: Corpus, prefixes: Sequence[ProductPrefix]) -> list[PrefixRow]:
    groups: dict[str, list[ProductStat]] = defaultdict(list)
    for stat in corpus.products.values():
        groups[product_prefix(stat.code)].append(stat)
    rows = []
    for prefix, stats in sorted(groups.items()):
        stats.sort(key=lambda s: s.code)
        rows.append(
            PrefixRow(
                prefix,
                len(stats),
                sum(s.printings for s in stats),
                sum(s.unresolved for s in stats),
                tuple(sorted({t for s in stats for t in s.types})),
                ", ".join(
                    sorted(
                        {c for s in stats if (c := prefix_type_code(prefixes, s.code)) is not None}
                    )
                ),
                tuple(f"{s.code or '-'}: {s.name_jp}" for s in stats[:SAMPLE_PRODUCTS]),
            )
        )
    return rows


def _legacy_rows(
    link: LinkResult, legacy_rows: Sequence[Row]
) -> tuple[list[LegacyRow], list[tuple[str, ...]]]:
    claims: dict[str, set[str]] = defaultdict(set)
    for jp, vote in link.links.items():
        if vote.strong:
            claims[vote.best[0].casefold()].add(jp)
    rows: list[LegacyRow] = []
    for r in legacy_rows:
        jp = r["jp"]
        owners = claims.get(r["legacy_en"].casefold(), set())
        if jp:
            status = "kept"
        elif len(owners) == 1:
            (jp,) = owners
            status = "filled"
        elif owners:
            status = "conflict: " + ", ".join(sorted(owners))
        else:
            status = "no strong link"
        rows.append(LegacyRow(r["legacy_en"], r["preferred_en"], jp, r["notes"], status))
    return rows, [(r.legacy_en, r.preferred_en, r.jp, r.notes) for r in rows]


def build_review(
    corpus: Corpus,
    link: LinkResult,
    family_rows: Sequence[Row],
    keyword_rows: Sequence[Row],
    legacy_rows: Sequence[Row],
    prefix_rows: Sequence[Row],
) -> Review:
    """Build every review table and CSV from already-read inputs."""
    aliases = {r["legacy_en"].casefold(): r["preferred_en"] for r in legacy_rows}
    families, conflicts, family_csv = _family_rows(corpus, link, family_rows, aliases)
    keywords, keyword_csv = _keyword_rows(corpus, keyword_rows)
    known = {r["jp"] for r in family_rows}
    legacy, legacy_csv = _legacy_rows(link, legacy_rows)
    return Review(
        tuple(families),
        tuple(keywords),
        tuple(_no_split_rows(corpus, known)),
        tuple(
            _prefix_rows(
                corpus, [ProductPrefix(r["prefix"], r["code"], r["notes"]) for r in prefix_rows]
            )
        ),
        tuple(legacy),
        tuple(conflicts),
        tuple(family_csv),
        tuple(keyword_csv),
        tuple(legacy_csv),
        link.no_legacy,
    )
