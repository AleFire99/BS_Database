"""One pass over the normalized pages: the facts the review tables are built from (#96)."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

NO_PRODUCT_CODE = ""


@dataclass(frozen=True, slots=True)
class ProductStat:
    """One product code: how many card numbers it prints and how many have no type yet."""

    code: str
    name_jp: str
    printings: int
    unresolved: int
    types: frozenset[str]


@dataclass(frozen=True, slots=True)
class Corpus:
    """What the normalized pages say.

    ``card_families`` is the Japanese families per card number. ``family_cards`` and
    ``keyword_cards`` count distinct card numbers. ``family_machine_en`` holds the machine
    English of a family, when the normalize run produced one. ``pairs`` counts the cards
    on which two families are adjacent. ``products`` is keyed by product code
    (``NO_PRODUCT_CODE`` for printings without one). ``rarity_printings`` counts printings per
    batspi ``rarity_jp``. ``untyped`` maps a product name to ``(printings, products)`` for
    the printings no type rule resolved (``products`` counts distinct product codes).
    """

    card_families: Mapping[str, frozenset[str]]
    family_cards: Mapping[str, int]
    family_machine_en: Mapping[str, str]
    keyword_cards: Mapping[str, int]
    pairs: Mapping[tuple[str, str], int]
    products: Mapping[str, ProductStat]
    rarity_printings: Mapping[str, int] = field(default_factory=dict)
    untyped: Mapping[str, tuple[int, int]] = field(default_factory=dict)


def product_prefix(product_code: str) -> str:
    """Group key of a product code: its leading ``\\d*[A-Za-z]+`` run.

    ``BSC22`` gives ``BSC`` and ``26RBS01`` gives ``26RBS``.
    """
    if product_code == NO_PRODUCT_CODE:
        return "(none)"
    match = re.match(r"\d*[A-Za-z]+", product_code)
    return match[0] if match else "(other)"


class _Builder:
    def __init__(self) -> None:
        self.card_families: dict[str, set[str]] = {}
        self.family_cards: dict[str, set[str]] = {}
        self.machine: dict[str, str] = {}
        self.keyword_cards: dict[str, set[str]] = {}
        self.pairs: dict[tuple[str, str], set[str]] = {}
        self.product_names: dict[str, set[str]] = {}
        self.product_numbers: dict[str, set[str]] = {}
        self.product_unresolved: dict[str, set[str]] = {}
        self.product_types: dict[str, set[str]] = {}
        self.rarities: dict[str, int] = {}
        self.untyped_printings: dict[str, int] = {}
        self.untyped_codes: dict[str, set[str]] = {}

    def add_entry(self, entry: dict[str, Any]) -> None:
        number: str = entry["number"]
        families = [f["jp"] for f in entry["gameplay"]["families"]]
        self.card_families.setdefault(number, set()).update(families)
        for f in entry["gameplay"]["families"]:
            self.family_cards.setdefault(f["jp"], set()).add(number)
            if f.get("en_source") == "machine" and f.get("en"):
                self.machine.setdefault(f["jp"], f["en"])
        for left, right in zip(families, families[1:], strict=False):
            self.pairs.setdefault((left, right), set()).add(number)
        for effect in (entry.get("text") or {}).get("effects", []):
            for keyword in effect["keywords"]:
                self.keyword_cards.setdefault(keyword["name_jp"], set()).add(number)

    def add_printing(self, printing: dict[str, Any]) -> None:
        if rarity := printing.get("rarity_jp"):
            self.rarities[rarity] = self.rarities.get(rarity, 0) + 1
        code = printing["product_code"] or NO_PRODUCT_CODE
        number = printing["number"]
        self.product_names.setdefault(code, set()).add(printing["product_name_jp"])
        self.product_numbers.setdefault(code, set()).add(number)
        type_code = printing["product_type_code"]
        self.product_types.setdefault(code, set()).add(type_code or "-")
        if type_code is None:
            name = printing["product_name_jp"]
            self.untyped_printings[name] = self.untyped_printings.get(name, 0) + 1
            self.untyped_codes.setdefault(name, set()).add(code)
            self.product_unresolved.setdefault(code, set()).add(number)

    def build(self) -> Corpus:
        products = {
            code: ProductStat(
                code,
                min(self.product_names[code]),
                len(numbers),
                len(self.product_unresolved.get(code, ())),
                frozenset(self.product_types[code]),
            )
            for code, numbers in self.product_numbers.items()
        }
        return Corpus(
            {n: frozenset(f) for n, f in self.card_families.items()},
            {jp: len(n) for jp, n in self.family_cards.items()},
            dict(self.machine),
            {jp: len(n) for jp, n in self.keyword_cards.items()},
            {pair: len(n) for pair, n in self.pairs.items()},
            products,
            dict(self.rarities),
            {
                name: (count, len(self.untyped_codes[name]))
                for name, count in self.untyped_printings.items()
            },
        )


def collect_corpus(pages: Iterable[dict[str, Any]]) -> Corpus:
    """Fold normalized ``page`` objects (see ``iter_pages``) into a :class:`Corpus`."""
    builder = _Builder()
    for page in pages:
        for entry in page["entries"]:
            builder.add_entry(entry)
        for printing in page["printings"]:
            builder.add_printing(printing)
    return builder.build()
