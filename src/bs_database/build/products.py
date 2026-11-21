"""Products and printings with the dedup and fallback rules of the build (#120).

The rules, measured on the full local data (see docs/architecture/build.md):

- A product is keyed by its code. A row without a code whose name is used with exactly one code
  elsewhere takes that code; otherwise the normalized name is the key.
- A product takes its most frequent name (tie: sorted first), its most frequent non-null type and
  its earliest non-null release date. A product without any type falls back to ``other``.
- A printing is keyed by ``(number, product, variant)``; the first row in ``(url, page)`` order
  wins, nulls are filled from later rows and a conflicting non-null value is kept as first.
"""

import sqlite3
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from bs_database.build.diagnostics import BuildError, BuildWarnings
from bs_database.build.lookups import STATUS_PENDING, Lookups
from bs_database.build.reader import Document, Json

FALLBACK_TYPE = "other"
ILLUSTRATOR_JOIN = " / "

ProductKey = tuple[int, str]  # (0, code) for a coded product, (1, name) for a name-only one


@dataclass(slots=True)
class Product:
    """A merged product; ``id`` is assigned after sorting."""

    key: ProductKey
    rows: list[Json] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    id: int = 0


@dataclass(slots=True)
class Printing:
    """A merged printing; ``texts`` are the texts used to match illustrator notes and captions."""

    number: str
    product: ProductKey
    variant: str
    rarity: str | None
    names: set[str] = field(default_factory=set)
    texts: list[str] = field(default_factory=list)
    id: int = 0

    @property
    def sort_key(self) -> tuple[str, ProductKey, str]:
        """Order of printing ids: number, then product, then variant."""
        return (self.number, self.product, self.variant)


@dataclass(frozen=True, slots=True)
class PrintingIndex:
    """Result of the products and printings step, used by the image and provenance steps."""

    products: list[Product]
    printings: list[Printing]
    by_number: dict[str, list[Printing]]  # first-seen order in (url, page) order


def _name_to_codes(documents: Iterable[Document]) -> dict[str, set[str]]:
    codes: dict[str, set[str]] = {}
    for doc in documents:
        for row in doc.printings:
            if row["product_code"]:
                codes.setdefault(row["product_name_jp"], set()).add(row["product_code"])
    return codes


def _most_common(values: Iterable[str]) -> str | None:
    """The most frequent value; ties go to the sorted first; ``None`` for no values."""
    counts = Counter(values)
    if not counts:
        return None
    return min(counts, key=lambda v: (-counts[v], v))


def _product_key(row: Json, codes: dict[str, set[str]]) -> tuple[ProductKey, bool]:
    """The product key of a row and whether the name was folded into a code."""
    if row["product_code"]:
        return (0, row["product_code"]), False
    known = codes.get(row["product_name_jp"], set())
    if len(known) == 1:
        return (0, next(iter(known))), True
    return (1, row["product_name_jp"]), False


def pick_illustrator(illustrators: list[Json], texts: list[str]) -> str | None:
    """The illustrator text of one printing (Q5 of the plan of #120).

    No names: NULL. One name: that name. Several: the one whose note matches the printing's
    product or variant text, else the only one without a note, else all names joined.
    """
    credits = [c for c in illustrators if c["name"]]
    if not credits:
        return None
    if len(credits) == 1:
        return str(credits[0]["name"])
    matched = [
        c
        for c in credits
        if c["note"] and any(t and (c["note"] in t or t in c["note"]) for t in texts)
    ]
    if len(matched) == 1:
        return str(matched[0]["name"])
    plain = [c for c in credits if not c["note"]]
    if len(plain) == 1:
        return str(plain[0]["name"])
    return ILLUSTRATOR_JOIN.join(dict.fromkeys(str(c["name"]) for c in credits))


def collect(
    documents: list[Document], numbers: set[str], warnings: BuildWarnings
) -> tuple[list[Product], list[Printing]]:
    """Merge the printing rows of all documents into products and printings (no ids yet)."""
    docs = sorted(documents, key=lambda d: d.url)
    codes = _name_to_codes(docs)
    products: dict[ProductKey, Product] = {}
    printings: dict[tuple[str, ProductKey, str], Printing] = {}
    for doc in docs:
        for row in doc.printings:
            key, folded = _product_key(row, codes)
            if folded:
                warnings.add("product_name_folded", f"{row['product_name_jp']} -> {key[1]}")
            product = products.setdefault(key, Product(key))
            product.rows.append(row)
            if doc.url not in product.urls:
                product.urls.append(doc.url)
            if row["number"] not in numbers:
                warnings.add("printing_number_unknown", f"{row['number']} ({doc.url})")
                continue
            pkey = (row["number"], key, row["variant_code"])
            texts = [row["product_name_jp"], row["variant_jp"], row["note_jp"], row["detail_jp"]]
            current = printings.get(pkey)
            if current is None:
                current = printings[pkey] = Printing(
                    row["number"], key, row["variant_code"], row["rarity_code"]
                )
            else:
                warnings.add("printing_duplicate_merged", f"{row['number']} {key[1]}")
                if current.rarity is None:
                    current.rarity = row["rarity_code"]
                elif row["rarity_code"] not in (None, current.rarity):
                    warnings.add("printing_rarity_conflict", f"{row['number']} {key[1]}")
            current.names.add(row["product_name_jp"])
            current.texts.extend(t for t in texts if t)
    return list(products.values()), list(printings.values())


def _merge_product(product: Product, warnings: BuildWarnings) -> dict[str, object]:
    rows = product.rows
    name = _most_common(r["product_name_jp"] for r in rows)
    if len({r["product_name_jp"] for r in rows}) > 1:
        warnings.add("product_name_conflict", f"{product.key[1]} -> {name}")
    type_code = _most_common(r["product_type_code"] for r in rows if r["product_type_code"])
    if len({r["product_type_code"] for r in rows if r["product_type_code"]}) > 1:
        warnings.add("product_type_conflict", f"{product.key[1]} -> {type_code}")
    if type_code is None:
        type_code = FALLBACK_TYPE
        warnings.add("product_without_type", f"{name}")
    dates = [r["release_date"] for r in rows if r["release_date"]]
    name_en = _most_common(r["product_name_en"] for r in rows if r["product_name_en"])
    en_row = next((r for r in rows if r["product_name_en"] == name_en and name_en), None)
    return {
        "code": product.key[1] if product.key[0] == 0 else None,
        "name_jp": name,
        "name_en": name_en,
        "type": type_code,
        "release_date": min(dates) if dates else None,
        "source": en_row["product_en_source"] if en_row else None,
        "status": en_row["product_en_status"] if en_row else STATUS_PENDING,
    }


def load_products_and_printings(
    conn: sqlite3.Connection,
    lookups: Lookups,
    warnings: BuildWarnings,
    documents: list[Document],
    number_ids: dict[str, int],
    illustrators: dict[str, list[Json]],
) -> PrintingIndex:
    """Insert products and printings; ``illustrators`` maps a number to its illustrator credits."""
    products, printings = collect(documents, set(number_ids), warnings)
    products.sort(key=lambda p: p.key)
    product_rows = []
    for product_id, product in enumerate(products, start=1):
        product.id = product_id
        merged = _merge_product(product, warnings)
        product_rows.append(
            (
                product_id,
                merged["code"],
                merged["name_jp"],
                merged["name_en"],
                lookups.product_types[str(merged["type"])],
                merged["release_date"],
                lookups.source_id(str(merged["source"]) if merged["source"] else None),
                lookups.status_id(str(merged["status"])),
            )
        )
    conn.executemany(
        "INSERT INTO products (id, code, name_jp, name_en, product_type_id, release_date,"
        " en_source_id, en_status_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        product_rows,
    )
    by_number: dict[str, list[Printing]] = {}
    for printing in printings:
        by_number.setdefault(printing.number, []).append(printing)
    product_ids = {p.key: p.id for p in products}
    printing_rows = []
    for printing_id, printing in enumerate(sorted(printings, key=lambda p: p.sort_key), start=1):
        printing.id = printing_id
        if printing.variant not in lookups.variants:
            raise BuildError(f"{printing.number}: variant {printing.variant!r} not in the glossary")
        if printing.rarity is not None and printing.rarity not in lookups.rarities:
            raise BuildError(f"{printing.number}: rarity {printing.rarity!r} not in the glossary")
        printing_rows.append(
            (
                printing_id,
                number_ids[printing.number],
                product_ids[printing.product],
                lookups.variants[printing.variant],
                lookups.rarities[printing.rarity] if printing.rarity else None,
                pick_illustrator(illustrators.get(printing.number, []), printing.texts),
            )
        )
    conn.executemany(
        "INSERT INTO printings (id, card_number_id, product_id, variant_id, rarity_id,"
        " illustrator) VALUES (?, ?, ?, ?, ?, ?)",
        printing_rows,
    )
    return PrintingIndex(products, printings, by_number)
