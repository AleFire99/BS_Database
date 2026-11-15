"""Shared helpers for tests that run the parsed and normalized stages on the HTML fixtures."""

import json
from datetime import UTC, datetime
from pathlib import Path

from bs_database.glossary import Glossary, load_glossary
from bs_database.ingest.cache import CachedPage
from bs_database.ingest.parsed_store import parsed_path, write_card_json
from bs_database.normalize.pipeline import normalize_tree
from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.card_models import CardPage
from bs_database.translate import NullTranslator

ROOT = Path(__file__).parent.parent
GLOSSARY_DIR = ROOT / "data" / "glossary"
HTML_DIR = Path(__file__).parent / "fixtures" / "html"
FETCHED = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


def card_fixture_names() -> list[str]:
    """Names of the batspi card fixtures, sorted."""
    manifest = json.loads((HTML_DIR / "fixtures.json").read_text(encoding="utf-8"))
    return sorted(n for n, e in manifest.items() if e["source"] == "batspi" and e["kind"] == "card")


def fixture_url(name: str) -> str:
    manifest = json.loads((HTML_DIR / "fixtures.json").read_text(encoding="utf-8"))
    return str(manifest[name]["url"])


def parse_fixture(name: str) -> CardPage:
    """Parse one card fixture into a :class:`CardPage`."""
    html = (HTML_DIR / name).read_text(encoding="utf-8")
    return parse_card_page(html, fixture_url(name))


def real_glossary() -> Glossary:
    """The glossary shipped in ``data/glossary``."""
    return load_glossary(GLOSSARY_DIR)


def write_parsed_fixture(parsed_dir: Path, name: str) -> Path:
    """Write one card fixture to ``parsed_dir`` with a fixed fetch time; returns the path."""
    page = parse_fixture(name)
    content = (HTML_DIR / name).read_bytes()
    cached = CachedPage(page.url, "batspi", content, 200, FETCHED, True)
    return write_card_json(parsed_dir, page, cached)


NORMALIZED_GOLDENS = Path(__file__).parent / "goldens" / "normalized"
REGEN_COMMAND = "uv run python tests/tools/regen_normalized_goldens.py"


def normalized_documents(work_dir: Path) -> dict[str, str]:
    """Run html, parse, parsed store and ``normalize_tree`` for every card fixture.

    Returns ``{fixture name: normalized JSON text}``. ``work_dir`` must be empty and writable.
    """

    parsed, normalized = work_dir / "parsed", work_dir / "normalized"
    names = card_fixture_names()
    for name in names:
        write_parsed_fixture(parsed, name)
    normalize_tree(parsed, normalized, real_glossary(), NullTranslator())
    return {
        name: parsed_path(normalized, "batspi", fixture_url(name)).read_text(encoding="utf-8")
        for name in names
    }


def golden_path(name: str) -> Path:
    """Golden file of a fixture, e.g. ``card_spirit.html`` -> ``card_spirit.json``."""
    return NORMALIZED_GOLDENS / f"{Path(name).stem}.json"
