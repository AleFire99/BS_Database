"""Render a :class:`Review` as Markdown tables and glossary-schema CSV files (#96).

Output is deterministic: no timestamps, fixed sort orders, ``\\n`` line endings.
"""

import csv
import io
from collections.abc import Sequence
from pathlib import Path

from bs_database.ingest.atomic import atomic_write
from bs_database.review.build import (
    CLASS_COLUMNS,
    FAMILY_COLUMNS,
    KEYWORD_COLUMNS,
    LEGACY_COLUMNS,
    TIMING_COLUMNS,
    FamilyRow,
    KeywordRow,
    Review,
    TimingRow,
)

REVIEW_MD = "review.md"
FAMILIES_CSV = "families.csv"
KEYWORDS_CSV = "keywords.csv"
LEGACY_CSV = "family_legacy_en.csv"
TIMINGS_CSV = "timings.csv"
CLASSES_CSV = "card_classes.csv"
NO_LEGACY_SAMPLE = 20


def cell(text: object) -> str:
    """Make ``text`` safe inside a Markdown table cell."""
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _table(header: Sequence[str], rows: Sequence[Sequence[object]], right: int = 0) -> list[str]:
    """A Markdown table; the ``right`` columns after the first are right-aligned numbers."""
    align = ["---"] + ["---:" if 1 <= i <= right else "---" for i in range(1, len(header))]
    lines = [f"| {' | '.join(header)} |", f"| {' | '.join(align)} |"]
    lines += [f"| {' | '.join(cell(c) for c in row)} |" for row in rows]
    return lines


def _section(title: str, count: int, table: list[str], note: str = "") -> list[str]:
    lines = [f"## {title} ({count})", ""]
    if note:
        lines += [note, ""]
    return [*lines, *(table if count else ["None."]), ""]


def _votes(strong: bool, best: int, total: int) -> str:
    if total == 0:
        return ""
    return f"{best}/{total} {'strong' if strong else 'weak'}"


def _candidates(f: FamilyRow) -> str:
    parts = [f"{name} x{n}" for name, n in f.candidates]
    if f.fandom_en and f.fandom_en.casefold() != f.en.casefold():
        parts.append(f"fandom: {f.fandom_en}")
    return ", ".join(parts)


def _keyword_status(k: KeywordRow) -> str:
    if k.code_conflict:
        return f"code conflict: {k.code_conflict}"
    if k.known:
        return "known"
    if k.fandom_title:
        return f"new: from fandom ({k.fandom_title})"
    return "new: needs code and EN"


def _closed_status(r: TimingRow) -> str:
    if not r.known:
        return "new: needs EN" if r.in_timing_jp else "new: not in timing_jp, needs EN"
    if not r.in_timing_jp:
        return "known: not in timing_jp"
    return "known"


def source_summary(review: Review) -> str:
    """``fandom 12, glossary 3, ..., none 4``: families per proposal source."""
    return ", ".join(f"{source or 'none'} {n}" for source, n in review.family_sources)


def render_markdown(review: Review) -> str:
    """The review tables for the owner."""
    lines = [
        "# Glossary review",
        "",
        f"Families: {len(review.families)}. Keywords: {len(review.keywords)}. "
        f"Cards with no legacy family: {len(review.no_legacy)}.",
        "",
    ]
    if review.no_legacy:
        sample = ", ".join(review.no_legacy[:NO_LEGACY_SAMPLE])
        lines += [f"First {min(NO_LEGACY_SAMPLE, len(review.no_legacy))} (sorted): {sample}", ""]
    if review.with_fandom:
        lines += [f"Family names by source: {source_summary(review)}.", ""]
    lines += [
        "Notes: copy `families.csv` and `family_legacy_en.csv` together (the legacy `jp` values "
        "must exist in the families). After filling codes by hand, re-sort `families.csv` and "
        "`keywords.csv` by code (then jp); `bsdb normalize` reports an unsorted file.",
        "",
    ]
    family_table = _table(
        ["JP", "Cards", "Code", "Proposed EN", "Source", "Votes", "Candidates"],
        [
            [
                f.jp,
                f.cards,
                f.code or ("CONFLICT" if f.conflict else ""),
                f.en,
                f.source,
                _votes(f.strong, f.votes, f.total),
                _candidates(f),
            ]
            for f in review.families
        ],
        right=1,
    )
    lines += _section("Families", len(review.families), family_table)
    keyword_table = _table(
        ["JP", "Cards", "Code", "EN", "Status"],
        [[k.jp, k.cards, k.code, k.en, _keyword_status(k)] for k in review.keywords],
        right=1,
    )
    lines += _section(
        "Keywords",
        len(review.keywords),
        keyword_table,
        "No machine proposals: the owner writes the English names.",
    )
    timing_table = _table(
        ["JP", "Cards", "Code", "EN", "Status"],
        [[t.jp, t.cards, t.code, t.en, _closed_status(t)] for t in review.timings],
        right=1,
    )
    lines += _section(
        "Timings",
        len(review.timings),
        timing_table,
        "Every effect `timing_jp` and every timing-like `『…』` span of the effect text. "
        "No machine proposals: the owner writes the English.",
    )
    class_table = _table(
        ["JP", "Cards", "Code", "EN", "Status"],
        [[c.jp, c.cards, c.code, c.en, _closed_status(c)] for c in review.classes],
        right=1,
    )
    lines += _section("Card classes", len(review.classes), class_table)
    if review.with_fandom:
        rarity_table = _table(
            ["Fandom JP", "Letter", "EN", "batspi rarity", "Printings"],
            [
                [r.fandom_jp, r.letter, r.en, ", ".join(r.batspi), r.printings]
                for r in review.rarities
            ],
            right=0,
        )
        lines += _section(
            "Rarities",
            len(review.rarities),
            rarity_table,
            "Fandom rarities matched to batspi ones by letter or Japanese name; "
            "rows without a fandom JP are batspi rarities nothing matches.",
        )
    split_table = _table(["Joined", "Cards"], [[r.joined, r.cards] for r in review.no_split], 1)
    lines += _section(
        "no_split candidates",
        len(review.no_split),
        split_table,
        "Adjacent families that never appear apart (at least 2 cards).",
    )
    prefix_table = _table(
        ["Prefix", "Products", "Printings", "Unresolved", "Types", "Mapped", "Samples"],
        [
            [
                p.prefix,
                p.products,
                p.printings,
                p.unresolved,
                ", ".join(p.types),
                p.mapped,
                "; ".join(p.samples),
            ]
            for p in review.prefixes
        ],
        right=3,
    )
    lines += _section("Product code prefixes", len(review.prefixes), prefix_table)
    untyped_table = _table(
        ["Product name", "Printings", "Products"],
        [[r.name, r.printings, r.products] for r in review.untyped],
        right=1,
    )
    lines += _section(
        "Untyped products",
        len(review.untyped),
        untyped_table,
        "Product names whose printings no type rule resolves (marker, code prefix, name keyword).",
    )
    conflict_table = _table(
        ["Slug", "Families"], [[c.slug, ", ".join(c.jps)] for c in review.conflicts]
    )
    lines += _section(
        "Slug conflicts",
        len(review.conflicts),
        conflict_table,
        "These families keep an empty code in families.csv.",
    )
    legacy_table = _table(
        ["Legacy EN", "Preferred EN", "JP", "Status"],
        [[r.legacy_en, r.preferred_en, r.jp, r.status] for r in review.legacy],
    )
    lines += _section("Legacy family pairs", len(review.legacy), legacy_table)
    return "\n".join(lines)


def render_csv(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """A glossary CSV with ``\\n`` line endings."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def write_review(out_dir: Path, review: Review) -> list[Path]:
    """Write the Markdown and the five CSV files into ``out_dir``; returns their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        REVIEW_MD: render_markdown(review),
        FAMILIES_CSV: render_csv(FAMILY_COLUMNS, review.family_csv),
        KEYWORDS_CSV: render_csv(KEYWORD_COLUMNS, review.keyword_csv),
        LEGACY_CSV: render_csv(LEGACY_COLUMNS, review.legacy_csv),
        TIMINGS_CSV: render_csv(TIMING_COLUMNS, review.timing_csv),
        CLASSES_CSV: render_csv(CLASS_COLUMNS, review.class_csv),
    }
    paths = []
    for name, text in files.items():
        path = out_dir / name
        atomic_write(path, text.encode("utf-8"))
        paths.append(path)
    return paths
