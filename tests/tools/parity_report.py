"""Parity report between the v0.1.0 legacy database and a new ``bsdb build`` database (#124).

Usage: ``uv run python tests/tools/parity_report.py <legacy.db> <new.db> [--out FILE]
[--glossary DIR] [--examples N]``

Both databases are opened read-only. The report is deterministic Markdown: table counts,
the overlap of printed numbers (the 96 legacy-only numbers classified by cause, the
new-only numbers grouped by prefix) and a field comparison on the shared numbers (name,
cost, card type, colours, families, core levels). Every difference category carries a
count, a few examples, a label and a one-line explanation.

Labels: ``new data`` (the new build has more or better data), ``normalization`` (same
fact, different spelling or mapping), ``legacy bug`` (the legacy value is wrong) and
``unexplained`` (to investigate).
"""

import argparse
import difflib
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_EXAMPLES = 5
DEFAULT_GLOSSARY = Path(__file__).resolve().parents[2] / "data" / "glossary"

NEW_DATA = "new data"
NORMALIZATION = "normalization"
LEGACY_BUG = "legacy bug"
UNEXPLAINED = "unexplained"

# legacy table -> new equivalent(s) (summed)
TABLE_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cards", ("cards",)),
    ("card_types", ("card_types",)),
    ("colors", ("colors",)),
    ("card_colors", ("card_colors",)),
    ("families", ("families",)),
    ("card_families", ("card_families",)),
    ("core_requirements", ("card_levels",)),
)

TABLE_NOTES = {
    "cards": (
        NEW_DATA,
        "The new build covers many more printed numbers; one card row per ADR 0004 group, "
        "so several numbers can share a card.",
    ),
    "card_types": (NORMALIZATION, "Same five types."),
    "colors": (NEW_DATA, "The new build adds White (colourless)."),
    "card_colors": (NEW_DATA, "More cards, and White rows."),
    "families": (
        NORMALIZATION,
        "The new build has one row per Japanese family; legacy kept many English "
        "machine-translation variants and unsplit compounds.",
    ),
    "card_families": (NEW_DATA, "More cards."),
    "core_requirements": (NEW_DATA, "More cards, plus the levels legacy lacked."),
}
NEW_ONLY_TOP = 25

_FLIP = re.compile(r"^(?P<base>.+)\((?P<face>[A-Z])\)$")


@dataclass
class Category:
    """One difference category: a count, a few examples, a label and an explanation."""

    key: str
    label: str
    explanation: str
    count: int = 0
    examples: list[str] = field(default_factory=list)

    def add(self, example: str, limit: int) -> None:
        self.count += 1
        if len(self.examples) < limit:
            self.examples.append(example)


def connect_ro(path: Path) -> sqlite3.Connection:
    """Open ``path`` read-only (``mode=ro``)."""
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    return conn


def norm_number(number: str) -> str:
    """Matching key of a printed number: whitespace removed, upper case."""
    return "".join(number.split()).upper()


def fold_name(name: str) -> str:
    """Fold a name for loose comparison: NFKC, lower case, letters and digits only."""
    text = unicodedata.normalize("NFKC", name).lower()
    return "".join(ch for ch in text if ch.isalnum())


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Row count per user table, sorted by name."""
    names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {n: int(conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]) for n in names}


# --------------------------------------------------------------------------- loading


@dataclass
class LegacyCard:
    number: str
    name: str
    cost: int | None
    card_type: str | None
    colors: frozenset[str]
    families: frozenset[str]
    levels: frozenset[tuple[int | None, int | None, int | None]]


@dataclass
class NewCard:
    number: str
    name_jp: str
    name_en: str | None
    cost: int
    card_type: str
    colors: frozenset[str]
    families: frozenset[int]
    levels: frozenset[tuple[int | None, int | None, int | None]]


@dataclass
class FamilyResolver:
    """Resolve a legacy English family name to new family ids."""

    by_en: dict[str, int]
    by_alias: dict[str, int]
    by_jp: dict[str, int]
    legacy: dict[str, tuple[str, str | None]]  # legacy_en lower -> (preferred_en, jp)

    def resolve(self, name: str) -> int | None:
        key = name.strip().lower()
        if key in self.by_en:
            return self.by_en[key]
        if key in self.by_alias:
            return self.by_alias[key]
        if key in self.legacy:
            preferred, jp = self.legacy[key]
            if jp and jp in self.by_jp:
                return self.by_jp[jp]
            return self.by_en.get(preferred.strip().lower())
        return None


def load_legacy_aliases(glossary_dir: Path | None) -> dict[str, tuple[str, str | None]]:
    """``legacy_en`` (lower) -> ``(preferred_en, jp)`` from the glossary, ``{}`` if absent."""
    if glossary_dir is None or not (glossary_dir / "family_legacy_en.csv").is_file():
        return {}
    from bs_database.glossary import load_glossary

    glossary = load_glossary(glossary_dir)
    return {
        a.legacy_en.strip().lower(): (a.preferred_en, a.jp) for a in glossary.legacy_family_aliases
    }


def build_resolver(new: sqlite3.Connection, glossary_dir: Path | None) -> FamilyResolver:
    by_en: dict[str, int] = {}
    by_jp: dict[str, int] = {}
    for fid, jp, en in new.execute("SELECT id, name_jp, name_en FROM families ORDER BY id"):
        by_jp[jp] = fid
        if en:
            by_en.setdefault(en.strip().lower(), fid)
    by_alias = {
        a.strip().lower(): fid
        for fid, a in new.execute(
            "SELECT family_id, alias FROM family_aliases WHERE lang = 'en' ORDER BY id"
        )
    }
    return FamilyResolver(by_en, by_alias, by_jp, load_legacy_aliases(glossary_dir))


def load_legacy(conn: sqlite3.Connection) -> dict[str, LegacyCard]:
    """Legacy cards keyed by normalized number."""
    types = dict(conn.execute("SELECT id, name FROM card_types").fetchall())
    colors: dict[int, set[str]] = defaultdict(set)
    for cid, name in conn.execute(
        "SELECT cc.card_id, c.name FROM card_colors cc JOIN colors c ON c.id = cc.color_id"
    ):
        colors[cid].add(name)
    fams: dict[int, set[str]] = defaultdict(set)
    for cid, name in conn.execute(
        "SELECT cf.card_id, f.name FROM card_families cf JOIN families f ON f.id = cf.family_id"
    ):
        fams[cid].add(name)
    levels: dict[int, set[tuple[int | None, int | None, int | None]]] = defaultdict(set)
    for cid, level, cores, bp in conn.execute(
        'SELECT card_id, level, cores, "battlePoints" FROM core_requirements'
    ):
        levels[cid].add((level, cores, bp))
    out: dict[str, LegacyCard] = {}
    for cid, number, name, cost, type_id in conn.execute(
        "SELECT id, card_id, name, cost, type_id FROM cards ORDER BY id"
    ):
        out[norm_number(number)] = LegacyCard(
            number=number,
            name=name or "",
            cost=cost,
            card_type=types.get(type_id),
            colors=frozenset(colors[cid]),
            families=frozenset(fams[cid]),
            levels=frozenset(levels[cid]),
        )
    return out


def load_new(conn: sqlite3.Connection) -> dict[str, NewCard]:
    """New cards keyed by normalized number (one entry per printed number)."""
    types = dict(conn.execute("SELECT id, name FROM card_types").fetchall())
    colors: dict[int, set[str]] = defaultdict(set)
    for cid, name in conn.execute(
        "SELECT cc.card_id, c.name FROM card_colors cc JOIN colors c ON c.id = cc.color_id"
    ):
        colors[cid].add(name)
    fams: dict[int, set[int]] = defaultdict(set)
    for cid, fid in conn.execute("SELECT card_id, family_id FROM card_families"):
        fams[cid].add(fid)
    levels: dict[int, set[tuple[int | None, int | None, int | None]]] = defaultdict(set)
    for cid, level, cores, bp in conn.execute(
        "SELECT card_id, level, cores, battle_points FROM card_levels"
    ):
        levels[cid].add((level, cores, bp))
    out: dict[str, NewCard] = {}
    for cid, number, name_jp, name_en, cost, type_id in conn.execute(
        "SELECT c.id, n.number, c.name_jp, c.name_en, c.cost, c.card_type_id "
        "FROM card_numbers n JOIN cards c ON c.id = n.card_id ORDER BY n.number"
    ):
        out[norm_number(number)] = NewCard(
            number=number,
            name_jp=name_jp,
            name_en=name_en,
            cost=cost,
            card_type=types[type_id],
            colors=frozenset(colors[cid]),
            families=frozenset(fams[cid]),
            levels=frozenset(levels[cid]),
        )
    return out


# --------------------------------------------------------------------------- analysis


def number_prefix(number: str) -> str:
    """Prefix of a printed number: the part before ``-`` (``BS52-007(A)`` -> ``BS52``)."""
    return number.split("-", 1)[0]


def classify_legacy_only(
    legacy_only: Iterable[str], legacy: dict[str, LegacyCard], new: dict[str, NewCard], limit: int
) -> list[Category]:
    """Classify the numbers only the legacy database has, by cause."""
    flip = Category(
        "flip",
        NORMALIZATION,
        "Flip card: the legacy DB holds one row with both faces' names joined by '/'; "
        "the new build stores two numbers `X(A)` and `X(B)`.",
    )
    suffix = Category(
        "suffix",
        NORMALIZATION,
        "The new build lists the number only with another suffix (not an A/B flip face).",
    )
    absent = Category(
        "absent",
        UNEXPLAINED,
        "No trace of the number (nor of a flip face) in the new build.",
    )
    new_keys = sorted(new)
    for key in sorted(legacy_only):
        card = legacy[key]
        faces = [k for k in new_keys if k.startswith(key + "(")]
        if any(_FLIP.match(k) and (m := _FLIP.match(k)) and m["base"] == key for k in faces):
            flip.add(f"{card.number} -> {', '.join(new[k].number for k in faces)}", limit)
        elif faces:
            suffix.add(f"{card.number} -> {', '.join(new[k].number for k in faces)}", limit)
        else:
            absent.add(f"{card.number} ({card.name[:40]})", limit)
    return [flip, suffix, absent]


def group_new_only(new_only: Iterable[str], new: dict[str, NewCard]) -> dict[str, int]:
    """Count the new-only numbers per prefix."""
    counts: dict[str, int] = defaultdict(int)
    for key in new_only:
        counts[number_prefix(new[key].number)] += 1
    return dict(sorted(counts.items()))


def compare_fields(
    shared: Sequence[str],
    legacy: dict[str, LegacyCard],
    new: dict[str, NewCard],
    resolver: FamilyResolver,
    limit: int,
) -> dict[str, list[Category]]:
    """Compare the fields of the shared numbers; returns categories per field."""
    result: dict[str, list[Category]] = {}

    # name: legacy names are English machine translations, the new name_en is a different one
    n_same = Category("same", NORMALIZATION, "Identical English name.")
    n_fold = Category(
        "folded",
        NORMALIZATION,
        "Same name apart from case, spacing, hyphens or punctuation.",
    )
    n_close = Category(
        "close",
        NEW_DATA,
        "Re-translated: the wording is close (similarity >= 0.6); the new name_en comes from "
        "the Japanese name, the legacy one from a different translation.",
    )
    n_far = Category(
        "far",
        NEW_DATA,
        "Re-translated: the wording differs a lot (similarity < 0.6); the legacy DB has no "
        "Japanese name to check against, the new one keeps name_jp.",
    )
    n_none = Category("no_en", NEW_DATA, "The new build has no English name yet (name_jp only).")
    for key in shared:
        lc, nc = legacy[key], new[key]
        ex = f"{lc.number}: {lc.name[:50]!r} vs {(nc.name_en or '')[:50]!r}"
        if nc.name_en is None:
            n_none.add(ex, limit)
        elif lc.name == nc.name_en:
            n_same.count += 1
        elif fold_name(lc.name) == fold_name(nc.name_en):
            n_fold.add(ex, limit)
        elif (
            difflib.SequenceMatcher(None, fold_name(lc.name), fold_name(nc.name_en)).ratio() >= 0.6
        ):
            n_close.add(ex, limit)
        else:
            n_far.add(ex, limit)
    result["name"] = [n_same, n_fold, n_close, n_far, n_none]

    c_same = Category("same", NORMALIZATION, "Same cost.")
    c_diff = Category("diff", UNEXPLAINED, "Different cost.")
    t_same = Category("same", NORMALIZATION, "Same card type.")
    t_diff = Category("diff", UNEXPLAINED, "Different card type.")
    col_same = Category("same", NORMALIZATION, "Same colour set.")
    col_white = Category(
        "white_added",
        NEW_DATA,
        "Legacy had no empty-colour (White) colour row; the new build records White.",
    )
    col_empty = Category(
        "legacy_empty",
        LEGACY_BUG,
        "Legacy stored no colour at all for a coloured (mostly multicolour) card.",
    )
    col_subset = Category(
        "legacy_subset",
        LEGACY_BUG,
        "Legacy kept only some of the card's colours.",
    )
    col_less = Category("less", UNEXPLAINED, "The new build lacks colours the legacy DB has.")
    col_diff = Category("diff", UNEXPLAINED, "The colour sets differ in both directions.")
    for key in shared:
        lc, nc = legacy[key], new[key]
        if lc.cost == nc.cost:
            c_same.count += 1
        else:
            c_diff.add(f"{lc.number}: {lc.cost} vs {nc.cost}", limit)
        if lc.card_type == nc.card_type:
            t_same.count += 1
        else:
            t_diff.add(f"{lc.number}: {lc.card_type} vs {nc.card_type}", limit)
        ex = f"{lc.number}: {sorted(lc.colors)} vs {sorted(nc.colors)}"
        if lc.colors == nc.colors:
            col_same.count += 1
        elif not lc.colors and nc.colors == {"White"}:
            col_white.add(ex, limit)
        elif not lc.colors:
            col_empty.add(ex, limit)
        elif lc.colors < nc.colors:
            col_subset.add(ex, limit)
        elif lc.colors > nc.colors:
            col_less.add(ex, limit)
        else:
            col_diff.add(ex, limit)
    result["cost"] = [c_same, c_diff]
    result["card type"] = [t_same, t_diff]
    result["colours"] = [col_same, col_white, col_empty, col_subset, col_less, col_diff]

    f_same = Category("same", NORMALIZATION, "Same families (legacy English names mapped).")
    f_more = Category(
        "more",
        NEW_DATA,
        "The new build has extra families on top of the mapped legacy ones.",
    )
    f_count_same = Category(
        "count_same",
        NORMALIZATION,
        "Legacy English names are machine translations missing from the glossary: compared "
        "by count only, and the counts match.",
    )
    f_merged = Category(
        "legacy_merged",
        LEGACY_BUG,
        "Legacy kept a compound family string as one name; the new build splits it into "
        "several families (inferred: fewer legacy families than new).",
    )
    f_collision = Category(
        "name_collision",
        LEGACY_BUG,
        "A legacy English name is the preferred name of a different family: the legacy "
        "translation merged distinct Japanese families under one English name (inferred: "
        "same number of families, different set).",
    )
    f_extra = Category(
        "legacy_extra",
        LEGACY_BUG,
        "Legacy has extra family names that look like split fragments (e.g. 'Year', 'Face'); "
        "the parsed page lists fewer families.",
    )
    f_diff = Category("diff", UNEXPLAINED, "The family sets differ in a way not covered above.")
    unmapped_names: set[str] = set()
    for key in shared:
        lc, nc = legacy[key], new[key]
        mapped = {name: resolver.resolve(name) for name in lc.families}
        missing = sorted(n for n, fid in mapped.items() if fid is None)
        ids = frozenset(fid for fid in mapped.values() if fid is not None)
        ex = f"{lc.number}: {sorted(lc.families)} vs {len(nc.families)} families"
        unmapped_names.update(missing)
        if not missing and ids == nc.families:
            f_same.count += 1
        elif not missing and ids < nc.families:
            f_more.add(ex, limit)
        elif len(lc.families) == len(nc.families):
            (f_count_same if missing else f_collision).add(ex, limit)
        elif len(lc.families) < len(nc.families):
            f_merged.add(ex, limit)
        elif len(lc.families) - len(nc.families) <= 2:
            f_extra.add(ex, limit)
        else:
            f_diff.add(ex, limit)
    result["families"] = [f_same, f_more, f_count_same, f_merged, f_collision, f_extra, f_diff]
    result["families"].append(
        Category(
            "unmapped_names",
            NORMALIZATION,
            "Distinct legacy family names with no glossary or alias mapping: "
            + (", ".join(sorted(unmapped_names)[:10]) or "none")
            + ("..." if len(unmapped_names) > 10 else ""),
            count=len(unmapped_names),
        )
    )

    l_same = Category("same", NORMALIZATION, "Same level rows (level, cores, BP).")
    l_new = Category(
        "new_only",
        NEW_DATA,
        "The legacy DB has no level rows, the new build has them.",
    )
    l_legacy = Category(
        "legacy_only", UNEXPLAINED, "The legacy DB has level rows, the new build has none."
    )
    l_more = Category(
        "superset",
        NEW_DATA,
        "The new build has all legacy rows plus more (extra levels).",
    )
    l_diff = Category("diff", UNEXPLAINED, "The level rows differ.")
    for key in shared:
        lc, nc = legacy[key], new[key]
        ex = f"{lc.number}: {sorted(lc.levels, key=str)} vs {sorted(nc.levels, key=str)}"
        if lc.levels == nc.levels:
            l_same.count += 1
        elif not lc.levels:
            l_new.add(ex, limit)
        elif not nc.levels:
            l_legacy.add(ex, limit)
        elif lc.levels < nc.levels:
            l_more.add(ex, limit)
        else:
            l_diff.add(ex, limit)
    result["core levels"] = [l_same, l_new, l_legacy, l_more, l_diff]
    return result


# --------------------------------------------------------------------------- rendering


def _fmt(n: int) -> str:
    return f"{n:,}"


def _categories_table(cats: Sequence[Category]) -> list[str]:
    lines = [
        "| Category | Count | Label | Explanation | Examples |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for c in cats:
        if c.count == 0 and c.key not in ("same",):
            continue
        ex = "<br>".join(f"`{e}`".replace("|", "\\|") for e in c.examples) or "-"
        lines.append(f"| {c.key} | {_fmt(c.count)} | {c.label} | {c.explanation} | {ex} |")
    return lines


def build_report(
    legacy_conn: sqlite3.Connection,
    new_conn: sqlite3.Connection,
    glossary_dir: Path | None = DEFAULT_GLOSSARY,
    limit: int = DEFAULT_EXAMPLES,
) -> str:
    """Return the parity report as deterministic Markdown."""
    legacy = load_legacy(legacy_conn)
    new = load_new(new_conn)
    resolver = build_resolver(new_conn, glossary_dir)
    lc, nc = table_counts(legacy_conn), table_counts(new_conn)
    shared = sorted(set(legacy) & set(new))
    legacy_only = sorted(set(legacy) - set(new))
    new_only = sorted(set(new) - set(legacy))

    out = [
        "## Table counts",
        "",
        "| Legacy table | Rows | New table | Rows | Label | Explanation |",
        "| --- | ---: | --- | ---: | --- | --- |",
    ]
    for lt, nts in TABLE_MAP:
        nrows = sum(nc.get(t, 0) for t in nts)
        label, why = TABLE_NOTES.get(lt, (UNEXPLAINED, ""))
        names = ", ".join(f"`{t}`" for t in nts)
        out.append(
            f"| `{lt}` | {_fmt(lc.get(lt, 0))} | {names} | {_fmt(nrows)} | {label} | {why} |"
        )
    out += ["", "## Number overlap", ""]
    out += ["| Group | Numbers |", "| --- | ---: |"]
    out += [
        f"| Legacy | {_fmt(len(legacy))} |",
        f"| New | {_fmt(len(new))} |",
        f"| In both | {_fmt(len(shared))} |",
        f"| Only in legacy | {_fmt(len(legacy_only))} |",
        f"| Only in new | {_fmt(len(new_only))} |",
        "",
        "Matched on the printed number, whitespace removed and upper case.",
        "",
        "### Legacy-only numbers by cause",
        "",
    ]
    out += _categories_table(classify_legacy_only(legacy_only, legacy, new, limit))
    prefixes = group_new_only(new_only, new)
    ranked = sorted(prefixes.items(), key=lambda kv: (-kv[1], kv[0]))
    out += ["", "### New-only numbers by prefix", ""]
    out += [
        f"Label: {NEW_DATA}. The new build scrapes every batspi product (main sets, starter "
        "decks, promos, collaborations), the legacy DB only the first part of the catalogue. "
        f"{_fmt(len(new_only))} numbers in {_fmt(len(prefixes))} prefixes; the largest "
        f"{min(NEW_ONLY_TOP, len(ranked))}:",
        "",
        "| Prefix | Numbers |",
        "| --- | ---: |",
    ]
    out += [f"| {p} | {_fmt(c)} |" for p, c in ranked[:NEW_ONLY_TOP]]
    rest = ranked[NEW_ONLY_TOP:]
    out += ["", f"Other {_fmt(len(rest))} prefixes: {_fmt(sum(c for _, c in rest))} numbers.", ""]
    out += [f"## Field comparison on the {_fmt(len(shared))} shared numbers", ""]
    for fld, cats in compare_fields(shared, legacy, new, resolver, limit).items():
        out += [f"### {fld.capitalize()}", ""]
        out += _categories_table(cats)
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parity report: v0.1.0 DB vs a new build.")
    parser.add_argument("legacy", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--out", type=Path, default=None, help="write here instead of stdout")
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument("--examples", type=int, default=DEFAULT_EXAMPLES)
    args = parser.parse_args(argv)
    for db in (args.legacy, args.new):
        if not db.is_file():
            print(f"error: no such file: {db}", file=sys.stderr)
            return 1
    legacy_conn, new_conn = connect_ro(args.legacy), connect_ro(args.new)
    try:
        text = build_report(legacy_conn, new_conn, args.glossary, args.examples)
    finally:
        legacy_conn.close()
        new_conn.close()
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
