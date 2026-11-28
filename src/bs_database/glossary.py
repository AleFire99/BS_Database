"""Glossary loader and validator (#92, ADR 0008).

The glossaries live in ``data/glossary/*.csv``: one file per kind plus the legacy
English family aliases. Every ``jp`` value is exactly what the batspi parser emits,
so callers can ``lookup(kind, value)`` without cleanup. Matching is exact.

``load_glossary`` validates every file and raises one :class:`GlossaryError` that
lists all violations as ``<file>:<line>: <rule>``.
"""

import csv
import io
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

KINDS = (
    "colors",
    "symbols",
    "card_types",
    "rarities",
    "variants",
    "product_types",
    "keywords",
    "families",
    "timings",
    "card_classes",
)
CLOSED = frozenset(
    {
        "colors",
        "symbols",
        "card_types",
        "rarities",
        "variants",
        "product_types",
        "timings",
        "card_classes",
    }
)
LEGACY_FILE = "family_legacy_en"
PREFIX_FILE = "product_code_prefixes"
KEYWORD_FILE = "product_name_keywords"

_BASE_COLUMNS = ("jp", "code", "en", "notes")
_COLUMNS: dict[str, tuple[str, ...]] = {
    "rarities": (*_BASE_COLUMNS, "sort_order"),
    "families": (*_BASE_COLUMNS, "aliases_en", "no_split"),
    LEGACY_FILE: ("legacy_en", "preferred_en", "jp", "notes"),
    PREFIX_FILE: ("prefix", "code", "notes"),
    KEYWORD_FILE: ("keyword", "code", "notes"),
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
class ProductPrefix:
    """A product-code prefix (``BSC``) and the product type code it implies."""

    prefix: str
    code: str
    notes: str


@dataclass(frozen=True, slots=True)
class ProductKeyword:
    """A product-name keyword (``ブースター``) and the product type code it implies."""

    keyword: str
    code: str
    notes: str


@dataclass(frozen=True, slots=True)
class Glossary:
    """All glossaries, indexed by kind and exact ``jp`` value."""

    entries: Mapping[str, tuple[Entry, ...]]
    legacy_family_aliases: tuple[LegacyFamilyAlias, ...]
    product_prefixes: tuple[ProductPrefix, ...] = ()
    product_keywords: tuple[ProductKeyword, ...] = ()
    _index: Mapping[tuple[str, str], Entry] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Freeze ``entries`` and build the ``(kind, jp)`` index used by :meth:`lookup`."""
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))
        index = {
            (k, e.jp): e for k, kind_entries in self.entries.items() for e in kind_entries if e.jp
        }
        object.__setattr__(self, "_index", MappingProxyType(index))

    def lookup(self, kind: str, jp: str) -> Entry | None:
        """Return the entry of ``kind`` whose ``jp`` equals ``jp``, else ``None``."""
        return self._index.get((kind, jp))

    def product_type_for_code(self, product_code: str | None) -> str | None:
        """Type code of the longest prefix of ``product_code``, else ``None``."""
        return prefix_type_code(self.product_prefixes, product_code)

    def product_type_for_name(self, product_name: str | None) -> str | None:
        """Type code of the longest product-name keyword in ``product_name``, else ``None``."""
        return keyword_type_code(self.product_keywords, product_name)

    def unresolved_legacy(self) -> tuple[LegacyFamilyAlias, ...]:
        """Legacy pairs whose ``jp`` is still empty (to be filled in #96)."""
        return tuple(a for a in self.legacy_family_aliases if a.jp is None)


def prefix_type_code(prefixes: Iterable[ProductPrefix], product_code: str | None) -> str | None:
    """The type code of the longest ``startswith`` prefix of ``product_code``, else ``None``.

    The one prefix rule: the normalizer and the review table both use it.
    """
    if not product_code:
        return None
    best: ProductPrefix | None = None
    for p in prefixes:
        if product_code.startswith(p.prefix) and (best is None or len(p.prefix) > len(best.prefix)):
            best = p
    return None if best is None else best.code


def keyword_type_code(keywords: Iterable[ProductKeyword], product_name: str | None) -> str | None:
    """The type code of the longest keyword contained in ``product_name``, else ``None``.

    Both sides are NFKC-normalised first, so full-width and half-width forms match. On a
    length tie the first row of the file wins.
    """
    if not product_name:
        return None
    name = unicodedata.normalize("NFKC", product_name)
    best: tuple[int, str] | None = None
    for k in keywords:
        word = unicodedata.normalize("NFKC", k.keyword)
        if word in name and (best is None or len(word) > best[0]):
            best = (len(word), k.code)
    return None if best is None else best[1]


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
    """Rules 3 to 8 shared by every kind."""
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


def _check_prefixes(raw: dict[str, list[Row]], errors: list[str]) -> None:
    """Prefix file rules: non-empty unique sorted prefixes with an existing type code."""
    name = f"{PREFIX_FILE}.csv"
    type_codes = {r["code"] for _, r in raw.get("product_types", [])}
    seen: set[str] = set()
    previous = ""
    for line, row in raw.get(PREFIX_FILE, []):
        prefix = row["prefix"]
        if not prefix:
            errors.append(f"{name}:{line}: empty prefix")
        elif prefix in seen:
            errors.append(f"{name}:{line}: duplicate prefix {prefix!r}")
        seen.add(prefix)
        if "product_types" in raw and row["code"] not in type_codes:
            errors.append(f"{name}:{line}: unknown product type {row['code']!r}")
        if prefix < previous:
            errors.append(f"{name}:{line}: rows not sorted by prefix")
        previous = prefix


def _check_keywords(raw: dict[str, list[Row]], errors: list[str]) -> None:
    """Keyword file rules: non-empty unique sorted keywords with an existing type code."""
    name = f"{KEYWORD_FILE}.csv"
    type_codes = {r["code"] for _, r in raw.get("product_types", [])}
    seen: set[str] = set()
    previous = ""
    for line, row in raw.get(KEYWORD_FILE, []):
        keyword = row["keyword"]
        if not keyword:
            errors.append(f"{name}:{line}: empty keyword")
        elif keyword in seen:
            errors.append(f"{name}:{line}: duplicate keyword {keyword!r}")
        seen.add(keyword)
        if "product_types" in raw and row["code"] not in type_codes:
            errors.append(f"{name}:{line}: unknown product type {row['code']!r}")
        if keyword < previous:
            errors.append(f"{name}:{line}: rows not sorted by keyword")
        previous = keyword


def load_glossary(directory: Path) -> Glossary:
    """Load and validate every glossary under ``directory``."""
    errors: list[str] = []
    raw: dict[str, list[Row]] = {}
    for kind in (*KINDS, LEGACY_FILE, PREFIX_FILE, KEYWORD_FILE):
        rows = _read_rows(directory / f"{kind}.csv", _COLUMNS.get(kind, _BASE_COLUMNS), errors)
        if rows is not None:
            raw[kind] = rows
    for kind in KINDS:
        if kind in raw:
            _check_common(kind, raw[kind], errors)
            if kind in CLOSED and not raw[kind]:
                errors.append(f"{kind}.csv: a closed kind needs at least one row")

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

    _check_prefixes(raw, errors)
    _check_keywords(raw, errors)
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
    prefixes = tuple(ProductPrefix(r["prefix"], r["code"], r["notes"]) for _, r in raw[PREFIX_FILE])
    keywords = tuple(
        ProductKeyword(r["keyword"], r["code"], r["notes"]) for _, r in raw[KEYWORD_FILE]
    )
    return Glossary(entries, legacy, prefixes, keywords)
