"""Glossary loader and validator (#92, ADR 0008).

The glossaries live in ``data/glossary/*.csv``: one file per kind plus the legacy
English family aliases. Every ``jp`` value is exactly what the batspi parser emits,
so callers can ``lookup(kind, value)`` without cleanup. Matching is exact.

``load_glossary`` validates every file and raises one :class:`GlossaryError` that
lists all violations as ``<file>:<line>: <rule>``.
"""

import csv
import io
from dataclasses import dataclass
from pathlib import Path

KINDS = (
    "colors",
    "symbols",
    "card_types",
    "rarities",
    "variants",
    "product_types",
    "keywords",
    "families",
)
CLOSED = frozenset({"colors", "symbols", "card_types", "rarities", "variants", "product_types"})
LEGACY_FILE = "family_legacy_en"

_BASE_COLUMNS = ("jp", "code", "en", "notes")
_COLUMNS: dict[str, tuple[str, ...]] = {
    "rarities": (*_BASE_COLUMNS, "sort_order"),
    "families": (*_BASE_COLUMNS, "aliases_en", "no_split"),
    LEGACY_FILE: ("legacy_en", "preferred_en", "jp", "notes"),
}
_EMPTY_JP_OK = frozenset({"variants", "product_types"})
_ALIAS_SEPARATOR = "|"
_NO_SPLIT_MARK = "・"


class GlossaryError(ValueError):
    """Raised once by :func:`load_glossary`, listing every violation found."""

    def __init__(self, violations: list[str]) -> None:
        super().__init__("\n".join(violations))
        self.violations = tuple(violations)


@dataclass(frozen=True, slots=True)
class Entry:
    """A glossary row: the parsed Japanese value, its code and English name."""

    jp: str
    code: str
    en: str
    notes: str


@dataclass(frozen=True, slots=True)
class SymbolEntry(Entry):
    """A symbol; ``color_code`` is the code of the same-glyph colour, if any."""

    color_code: str | None


@dataclass(frozen=True, slots=True)
class RarityEntry(Entry):
    """A rarity with its display order."""

    sort_order: int


@dataclass(frozen=True, slots=True)
class FamilyEntry(Entry):
    """A family; ``aliases_en`` merges declared aliases and matching legacy rows."""

    aliases_en: tuple[str, ...]
    no_split: bool


@dataclass(frozen=True, slots=True)
class LegacyFamilyAlias:
    """A legacy English family pair; ``jp`` is ``None`` until #96 fills it."""

    legacy_en: str
    preferred_en: str
    jp: str | None
    notes: str


@dataclass(frozen=True, slots=True)
class Glossary:
    """All glossaries, indexed by kind and exact ``jp`` value."""

    entries: dict[str, tuple[Entry, ...]]
    legacy_family_aliases: tuple[LegacyFamilyAlias, ...]

    def lookup(self, kind: str, jp: str) -> Entry | None:
        """Return the entry of ``kind`` whose ``jp`` equals ``jp``, else ``None``."""
        for entry in self.entries.get(kind, ()):
            if entry.jp == jp:
                return entry
        return None

    def unresolved_legacy(self) -> tuple[LegacyFamilyAlias, ...]:
        """Legacy pairs whose ``jp`` is still empty (to be filled in #96)."""
        return tuple(a for a in self.legacy_family_aliases if a.jp is None)


Row = tuple[int, dict[str, str]]


def _read_rows(path: Path, columns: tuple[str, ...], errors: list[str]) -> list[Row] | None:
    """Read one CSV, checking existence, encoding, header, cell count and whitespace."""
    name = path.name
    if not path.is_file():
        errors.append(f"{name}:0: missing file")
        return None
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{name}:0: not valid UTF-8")
        return None
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, None)
    if header is None or tuple(header) != columns:
        errors.append(f"{name}:1: header must be {','.join(columns)}")
        return None
    rows: list[Row] = []
    for cells in reader:
        line = reader.line_num
        if not cells:
            continue
        if len(cells) != len(columns):
            errors.append(f"{name}:{line}: expected {len(columns)} columns, got {len(cells)}")
            continue
        if any(c != c.strip() for c in cells):
            errors.append(f"{name}:{line}: leading or trailing whitespace")
        rows.append((line, dict(zip(columns, cells, strict=True))))
    return rows


def _check_common(kind: str, rows: list[Row], errors: list[str]) -> None:
    """Rules 3 to 8 shared by the eight kinds."""
    name = f"{kind}.csv"
    seen_jp: set[str] = set()
    seen_code: set[str] = set()
    for line, row in rows:
        jp, code = row["jp"], row["code"]
        if jp:
            if jp in seen_jp:
                errors.append(f"{name}:{line}: duplicate jp {jp!r}")
            seen_jp.add(jp)
        elif kind not in _EMPTY_JP_OK:
            errors.append(f"{name}:{line}: empty jp")
        if code:
            if code in seen_code:
                errors.append(f"{name}:{line}: duplicate code {code!r}")
            seen_code.add(code)
        elif kind != "families":
            errors.append(f"{name}:{line}: empty code")
        if kind in CLOSED and not row["en"]:
            errors.append(f"{name}:{line}: empty en")
    key = (lambda r: (r[1]["code"], r[1]["jp"])) if kind == "families" else (lambda r: r[1]["code"])
    keys = [key(r) for r in rows]
    for (line, _), prev, cur in zip(rows[1:], keys, keys[1:], strict=False):
        if cur < prev:
            errors.append(f"{name}:{line}: rows not sorted by code")


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def load_glossary(directory: Path) -> Glossary:
    """Load and validate every glossary under ``directory``."""
    errors: list[str] = []
    raw: dict[str, list[Row]] = {}
    for kind in (*KINDS, LEGACY_FILE):
        rows = _read_rows(directory / f"{kind}.csv", _COLUMNS.get(kind, _BASE_COLUMNS), errors)
        if rows is not None:
            raw[kind] = rows
    for kind in KINDS:
        if kind in raw:
            _check_common(kind, raw[kind], errors)

    sort_orders: set[int] = set()
    for line, row in raw.get("rarities", []):
        order = _parse_int(row["sort_order"])
        if order is None or order in sort_orders:
            errors.append(f"rarities.csv:{line}: sort_order must be a unique integer")
        else:
            sort_orders.add(order)

    family_jps = {r["jp"] for _, r in raw.get("families", [])}
    for line, row in raw.get("families", []):
        flag = row["no_split"]
        if flag not in ("", "0", "1"):
            errors.append(f"families.csv:{line}: no_split must be empty, 0 or 1")
        elif flag == "1" and _NO_SPLIT_MARK not in row["jp"]:
            errors.append(f"families.csv:{line}: no_split=1 needs {_NO_SPLIT_MARK} in jp")

    legacy_seen: set[str] = set()
    for line, row in raw.get(LEGACY_FILE, []):
        key = row["legacy_en"].casefold()
        if key in legacy_seen:
            errors.append(f"{LEGACY_FILE}.csv:{line}: duplicate legacy_en {row['legacy_en']!r}")
        legacy_seen.add(key)
        if not row["preferred_en"]:
            errors.append(f"{LEGACY_FILE}.csv:{line}: empty preferred_en")
        if row["jp"] and "families" in raw and row["jp"] not in family_jps:
            errors.append(f"{LEGACY_FILE}.csv:{line}: jp {row['jp']!r} not in families.csv")

    if errors:
        raise GlossaryError(errors)
    return _build(raw)


def _build(raw: dict[str, list[Row]]) -> Glossary:
    """Turn validated rows into dataclasses."""
    legacy = tuple(
        LegacyFamilyAlias(r["legacy_en"], r["preferred_en"], r["jp"] or None, r["notes"])
        for _, r in raw[LEGACY_FILE]
    )
    color_codes = {r["jp"]: r["code"] for _, r in raw["colors"]}
    entries: dict[str, tuple[Entry, ...]] = {}
    for kind in KINDS:
        built: list[Entry] = []
        for _, r in raw[kind]:
            base = (r["jp"], r["code"], r["en"], r["notes"])
            if kind == "symbols":
                built.append(SymbolEntry(*base, color_codes.get(r["jp"])))
            elif kind == "rarities":
                built.append(RarityEntry(*base, int(r["sort_order"])))
            elif kind == "families":
                declared = [a for a in r["aliases_en"].split(_ALIAS_SEPARATOR) if a]
                declared += [a.legacy_en for a in legacy if a.jp == r["jp"]]
                aliases = tuple(dict.fromkeys(declared))
                built.append(FamilyEntry(*base, aliases, r["no_split"] == "1"))
            else:
                built.append(Entry(*base))
        entries[kind] = tuple(built)
    return Glossary(entries, legacy)
