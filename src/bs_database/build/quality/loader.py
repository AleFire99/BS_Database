"""Severity of every loader warning kind (#122).

The loaders count data they repaired or skipped (``BuildWarnings``). Each kind is mapped here to
a severity and a one-line meaning; a test checks that every kind used in ``build/*.py`` is
mapped. A kind that is missing is reported as a warning, so new kinds are never silent.
"""

from bs_database.build.diagnostics import BuildWarnings
from bs_database.build.quality.model import Finding, Severity

E, W, I = Severity.ERROR, Severity.WARNING, Severity.INFO  # noqa: E741

# kind -> (severity, meaning)
LOADER_KINDS: dict[str, tuple[Severity, str]] = {
    "color_unmapped": (E, "A colour without a glossary code was skipped"),
    "symbol_unmapped": (E, "A symbol without a glossary code was skipped"),
    "family_unmapped": (W, "A family without a glossary code was skipped"),
    "keyword_unmapped": (W, "A keyword without a glossary code was skipped"),
    "product_without_type": (W, "A product without any type was set to other"),
    "product_name_conflict": (W, "A product with several names, the most frequent was kept"),
    "product_type_conflict": (W, "A product with several types, the most frequent was kept"),
    "printing_rarity_conflict": (W, "A printing with two rarities, the first was kept"),
    "effect_level_missing": (W, "An effect level that is not a level of the card was skipped"),
    "level_duplicate": (W, "A level listed twice on a card, the first was kept"),
    "keyword_duplicate": (W, "A keyword twice in one effect, the first was kept"),
    "effect_position_invalid": (W, "An effect with an invalid or repeated position was skipped"),
    "printing_number_unknown": (W, "A printing of a number without a card entry was skipped"),
    "image_without_printing": (W, "An image of a number without printings was skipped"),
    "source_page_without_raw_html": (
        W,
        "The raw HTML was not cached, the page hash is of the normalized document",
    ),
    "block_icon_conflict": (I, "A card whose printings show different block icons (#131)"),
    "image_fallback_first_of_number": (I, "An image given to the first printing of its number"),
    "image_fallback_first_of_product": (I, "An image given to the first printing of its product"),
    "printing_duplicate_merged": (I, "Duplicate printing rows merged into one"),
    "product_name_folded": (I, "A name-only product row joined a product by its code"),
    "symbol_merged": (I, "The same symbol twice on a card, merged"),
}


def loader_findings(warnings: BuildWarnings) -> list[Finding]:
    """One finding per loader warning kind that occurred, sorted by kind."""
    findings: list[Finding] = []
    for kind, count in warnings.counts().items():
        severity, title = LOADER_KINDS.get(kind, (W, f"Unmapped loader warning {kind}"))
        findings.append(Finding(kind, severity, "loader", title, count, warnings.examples(kind)))
    return findings
