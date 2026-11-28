"""Run the review end to end: read the inputs, build the proposals (#96)."""

from pathlib import Path

from bs_database.review.build import Review, build_review
from bs_database.review.corpus import collect_corpus
from bs_database.review.fandom import load_names
from bs_database.review.legacy import link_families
from bs_database.review.source import iter_pages, load_legacy_families, read_csv_rows


def _optional_rows(path: Path) -> list[dict[str, str]]:
    """The rows of a glossary CSV, ``[]`` while the file does not exist yet."""
    return read_csv_rows(path) if path.is_file() else []


def run_review(
    normalized_dir: Path,
    glossary_dir: Path,
    legacy_db: Path,
    fandom_path: Path | None = None,
) -> Review:
    """Build the :class:`Review` from normalized pages, the glossary CSVs and the snapshot.

    ``fandom_path`` is the optional ``fandom_names.json`` of ``bsdb glossary fandom``.
    Raises :class:`~bs_database.review.source.ReviewError` for any unreadable input.
    """
    corpus = collect_corpus(iter_pages(normalized_dir))
    link = link_families(corpus.card_families, load_legacy_families(legacy_db))
    return build_review(
        corpus,
        link,
        read_csv_rows(glossary_dir / "families.csv"),
        read_csv_rows(glossary_dir / "keywords.csv"),
        read_csv_rows(glossary_dir / "family_legacy_en.csv"),
        read_csv_rows(glossary_dir / "product_code_prefixes.csv"),
        load_names(fandom_path) if fandom_path is not None else None,
        _optional_rows(glossary_dir / "timings.csv"),
        _optional_rows(glossary_dir / "card_classes.csv"),
    )
