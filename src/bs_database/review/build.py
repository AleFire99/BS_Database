"""Turn the corpus, the legacy votes and the current glossary rows into review proposals (#96).

Pure: no I/O. The proposals are what the owner reviews; the CSV rows are the same proposals
in the glossary schema, ready to copy into ``data/glossary`` once the owner agrees.

Proposed English name of a family, in priority order:

1. the glossary row's own ``en`` (``glossary``);
2. the fandom wiki name, when a fandom file is given and the Japanese names match (``fandom``,
   ADR 0009);
3. a strong legacy link whose legacy name has a ``family_legacy_en`` alias: the preferred
   name (``alias``);
4. a strong legacy link: the legacy name (``legacy``);
5. the machine translation of the normalize run (``machine``);
6. blank.

A weak legacy link never proposes a name; it is shown with its candidates instead. A fandom
name that differs from the proposal is shown among the candidates too.
Keywords take the glossary row, else the fandom name when one matches; otherwise the owner
writes the English name. A code is proposed from the fandom romaji (slugified), falling back to
the slug of the English name; a code that two rows want is left blank.
"""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from bs_database.glossary import ProductPrefix, prefix_type_code
from bs_database.parsers.fandom import FandomName, jp_key
from bs_database.review.corpus import Corpus, ProductStat, product_prefix
from bs_database.review.fandom import FandomData
from bs_database.review.legacy import LinkResult

Row = Mapping[str, str]

FAMILY_COLUMNS = ("jp", "code", "en", "notes", "aliases_en", "no_split")
KEYWORD_COLUMNS = ("jp", "code", "en", "notes")
LEGACY_COLUMNS = ("legacy_en", "preferred_en", "jp", "notes")
TIMING_COLUMNS = ("jp", "code", "en", "notes")
CLASS_COLUMNS = ("jp", "code", "en", "notes")
IN_TEXT_ONLY = "in-text only"

SOURCE_GLOSSARY = "glossary"
SOURCE_ALIAS = "alias"
SOURCE_LEGACY = "legacy"
SOURCE_MACHINE = "machine"
SOURCE_FANDOM = "fandom"
SOURCES = (SOURCE_GLOSSARY, SOURCE_FANDOM, SOURCE_ALIAS, SOURCE_LEGACY, SOURCE_MACHINE)
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
    fandom_en: str = ""
    fandom_title: str = ""


@dataclass(frozen=True, slots=True)
class KeywordRow:
    """A keyword of the corpus; ``known`` is False when the glossary has no row for it."""

    jp: str
    cards: int
    code: str
    en: str
    known: bool
    fandom_title: str = ""
    code_conflict: str = ""


@dataclass(frozen=True, slots=True)
class TimingRow:
    """A timing (or a card class) of the corpus; ``known`` is False without a glossary row.

    ``in_timing_jp`` is False for a span seen only inside effect text (``timing_jp`` never
    holds it); card classes leave it True.
    """

    jp: str
    cards: int
    code: str
    en: str
    known: bool
    in_timing_jp: bool = True


@dataclass(frozen=True, slots=True)
class RarityRow:
    """A fandom rarity with the batspi rarity strings it matches (by letter or Japanese name).

    A row with an empty ``fandom_jp`` is a batspi rarity that no fandom rarity matches.
    """

    fandom_jp: str
    letter: str
    en: str
    batspi: tuple[str, ...]
    printings: int


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
class UntypedRow:
    """A product name whose printings no type rule resolves."""

    name: str
    printings: int
    products: int


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
    rarities: tuple[RarityRow, ...] = ()
    with_fandom: bool = False
    untyped: tuple[UntypedRow, ...] = ()
    timings: tuple[TimingRow, ...] = ()
    timing_csv: tuple[tuple[str, ...], ...] = ()
    classes: tuple[TimingRow, ...] = ()
    class_csv: tuple[tuple[str, ...], ...] = ()

    @property
    def family_sources(self) -> tuple[tuple[str, int], ...]:
        """Families per proposal source (``""`` is no proposal), in priority order."""
        counts = [(s, sum(1 for f in self.families if f.source == s)) for s in SOURCES]
        return (*counts, ("", sum(1 for f in self.families if not f.source)))


def _by_key(names: Sequence[FandomName]) -> dict[str, FandomName]:
    """Fandom names by matching key; the first (sorted) page wins when keys collide."""
    out: dict[str, FandomName] = {}
    for name in names:
        out.setdefault(jp_key(name.jp), name)
    return out


def _fandom_code(name: FandomName | None) -> str:
    """Code slug from the fandom romaji, else from the fandom English name, else blank."""
    if name is None:
        return ""
    return slugify(name.romaji or "") or slugify(name.en)


def _proposal(
    jp: str,
    existing_en: str,
    link: LinkResult,
    aliases: Mapping[str, str],
    corpus: Corpus,
    fandom: FandomName | None = None,
) -> tuple[str, str]:
    """``(en, source)`` for a family, in the priority order of the module docstring."""
    if existing_en:
        return existing_en, SOURCE_GLOSSARY
    if fandom is not None and fandom.en:
        return fandom.en, SOURCE_FANDOM
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
    corpus: Corpus,
    link: LinkResult,
    glossary_rows: Sequence[Row],
    aliases: Mapping[str, str],
    fandom: Mapping[str, FandomName] | None = None,
) -> tuple[list[FamilyRow], list[SlugConflict], list[tuple[str, ...]]]:
    fandom = fandom or {}
    existing = {r["jp"]: r for r in glossary_rows}
    jps = sorted(set(existing) | set(corpus.family_cards))
    matched = {jp: fandom.get(jp_key(jp)) for jp in jps}
    proposed: dict[str, tuple[str, str]] = {}
    for jp in jps:
        row = existing.get(jp, {})
        proposed[jp] = _proposal(jp, row.get("en", ""), link, aliases, corpus, matched[jp])
    slugs = {jp: _fandom_code(matched[jp]) or slugify(proposed[jp][0]) for jp in jps}
    taken = {r["code"] for r in glossary_rows if r["code"]}
    wanted: dict[str, list[str]] = defaultdict(list)
    for jp in jps:
        if existing.get(jp, {}).get("code"):
            continue
        if slugs[jp]:
            wanted[slugs[jp]].append(jp)
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
            code = slugs[jp]
        vote = link.links.get(jp)
        best, votes = vote.best if vote else ("", 0)
        name = matched[jp]
        notes = row.get("notes", "")
        if source == SOURCE_FANDOM and name is not None and not notes:
            notes = f"fandom: {name.title}"
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
                name.en if name is not None else "",
                name.title if name is not None else "",
            )
        )
        csv_rows.append((jp, code, en, notes, row.get("aliases_en", ""), row.get("no_split", "")))
    csv_rows.sort(key=lambda r: (r[1], r[0]))
    rows.sort(key=lambda r: (-r.cards, r.jp))
    return rows, conflicts, csv_rows


def _keyword_rows(
    corpus: Corpus,
    glossary_rows: Sequence[Row],
    fandom: Mapping[str, FandomName] | None = None,
) -> tuple[list[KeywordRow], list[tuple[str, ...]]]:
    fandom = fandom or {}
    existing = {r["jp"]: r for r in glossary_rows}
    jps = sorted(set(existing) | set(corpus.keyword_cards))
    matched = {jp: fandom.get(jp_key(jp)) for jp in jps}
    proposed = {jp: _fandom_code(matched[jp]) for jp in jps}
    taken = {r["code"] for r in glossary_rows if r["code"]}
    wanted: dict[str, list[str]] = defaultdict(list)
    for jp in jps:
        if not existing.get(jp, {}).get("code") and proposed[jp]:
            wanted[proposed[jp]].append(jp)
    clashing = {slug for slug, owners in wanted.items() if len(owners) > 1 or slug in taken}
    rows: list[KeywordRow] = []
    csv_rows: list[tuple[str, ...]] = []
    for jp in jps:
        row = existing.get(jp, {})
        name = matched[jp]
        code = row.get("code", "")
        clash = ""
        if not code and proposed[jp]:
            if proposed[jp] in clashing:
                clash = proposed[jp]
            else:
                code = proposed[jp]
        en = row.get("en", "") or (name.en if name is not None else "")
        notes = row.get("notes", "")
        from_fandom = name is not None and (not row.get("en") or not row.get("code"))
        if from_fandom and name is not None and not notes:
            notes = f"fandom: {name.title}"
        rows.append(
            KeywordRow(
                jp,
                corpus.keyword_cards.get(jp, 0),
                code,
                en,
                jp in existing,
                name.title if name is not None else "",
                clash,
            )
        )
        csv_rows.append((jp, code, en, notes))
    csv_rows.sort(key=lambda r: (r[1], r[0]))
    rows.sort(key=lambda r: (-r.cards, r.jp))
    return rows, csv_rows


def _closed_rows(
    cards: Mapping[str, int],
    intext: Mapping[str, int],
    glossary_rows: Sequence[Row],
) -> tuple[list[TimingRow], list[tuple[str, ...]]]:
    """Rows of a closed kind seeded from the corpus: ``cards`` (the field) and ``intext``.

    The English is the glossary row's own, never proposed; the code is its own, else the slug
    of the English (blank while the English is). A span only in ``intext`` is flagged and its
    seed notes say ``in-text only``.
    """
    existing = {r["jp"]: r for r in glossary_rows}
    jps = sorted(set(existing) | set(cards) | set(intext))
    rows: list[TimingRow] = []
    csv_rows: list[tuple[str, ...]] = []
    for jp in jps:
        row = existing.get(jp, {})
        en = row.get("en", "")
        code = row.get("code", "") or slugify(en)
        in_field = jp in cards or jp not in intext
        notes = row.get("notes", "")
        if not in_field and not notes:
            notes = IN_TEXT_ONLY
        rows.append(
            TimingRow(jp, cards.get(jp, intext.get(jp, 0)), code, en, jp in existing, in_field)
        )
        csv_rows.append((jp, code, en, notes))
    rows.sort(key=lambda r: (-r.cards, r.jp))
    csv_rows.sort(key=lambda r: (r[1], r[0]))
    return rows, csv_rows


def _rarity_rows(corpus: Corpus, data: FandomData) -> list[RarityRow]:
    """Fandom rarities matched to batspi ones by letter or Japanese name, then the leftovers."""
    batspi = {jp_key(jp): jp for jp in corpus.rarity_printings}
    used: set[str] = set()
    rows: list[RarityRow] = []
    for r in data.rarities:
        keys = {jp_key(r.jp)} | ({jp_key(r.letter)} if r.letter else set())
        hits = tuple(sorted(batspi[k] for k in keys if k in batspi))
        used.update(hits)
        rows.append(
            RarityRow(
                r.jp,
                r.letter or "",
                r.en,
                hits,
                sum(corpus.rarity_printings[h] for h in hits),
            )
        )
    rows += [
        RarityRow("", "", "", (jp,), n)
        for jp, n in sorted(corpus.rarity_printings.items())
        if jp not in used
    ]
    return rows


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


def _untyped_rows(corpus: Corpus) -> list[UntypedRow]:
    rows = [UntypedRow(name or "(empty)", n, p) for name, (n, p) in corpus.untyped.items()]
    return sorted(rows, key=lambda r: (-r.printings, r.name))


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
    fandom: FandomData | None = None,
    timing_rows: Sequence[Row] = (),
    class_rows: Sequence[Row] = (),
) -> Review:
    """Build every review table and CSV from already-read inputs."""
    aliases = {r["legacy_en"].casefold(): r["preferred_en"] for r in legacy_rows}
    fam_names = _by_key(fandom.families) if fandom else None
    kw_names = _by_key(fandom.keywords) if fandom else None
    families, conflicts, family_csv = _family_rows(corpus, link, family_rows, aliases, fam_names)
    keywords, keyword_csv = _keyword_rows(corpus, keyword_rows, kw_names)
    known = {r["jp"] for r in family_rows}
    legacy, legacy_csv = _legacy_rows(link, legacy_rows)
    timings, timing_csv = _closed_rows(corpus.timing_cards, corpus.intext_timing_cards, timing_rows)
    classes, class_csv = _closed_rows(corpus.class_cards, {}, class_rows)
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
        tuple(_rarity_rows(corpus, fandom)) if fandom else (),
        fandom is not None,
        tuple(_untyped_rows(corpus)),
        tuple(timings),
        tuple(timing_csv),
        tuple(classes),
        tuple(class_csv),
    )
