import glob
from pathlib import Path

import pytest

from bs_database.glossary import KINDS, Glossary, load_glossary
from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.card_models import CardPage

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY_DIR = ROOT / "data" / "glossary"
FIXTURES = sorted(glob.glob(str(ROOT / "tests" / "fixtures" / "html" / "card_*.html")))


# Kinds seeded so far; each seeding commit extends this set.
SEEDED = {"colors", "symbols", "card_types", "rarities"}
HEADERS = {
    "rarities": "jp,code,en,notes,sort_order",
    "families": "jp,code,en,notes,aliases_en,no_split",
    "family_legacy_en": "legacy_en,preferred_en,jp,notes",
}


def load_seeded(tmp_path: Path) -> Glossary:
    """Load the real seeds; kinds not seeded yet get a header-only stub."""
    for path in GLOSSARY_DIR.glob("*.csv"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    for kind in (*KINDS, "family_legacy_en"):
        stub = tmp_path / f"{kind}.csv"
        if not stub.exists():
            stub.write_text(HEADERS.get(kind, "jp,code,en,notes") + "\n", encoding="utf-8")
    return load_glossary(tmp_path)


@pytest.fixture(scope="module")
def glossary(tmp_path_factory: pytest.TempPathFactory) -> Glossary:
    return load_seeded(tmp_path_factory.mktemp("glossary"))


@pytest.fixture(scope="module")
def pages() -> list[CardPage]:
    return [
        parse_card_page(Path(f).read_text(encoding="utf-8"), "https://batspi.com/fixture")
        for f in FIXTURES
    ]


def _sub(base: Path, name: str) -> Path:
    (base / name).mkdir()
    return base / name


def test_seed_loads_and_is_stable(tmp_path: Path) -> None:
    first = load_seeded(_sub(tmp_path, "a"))
    assert first == load_seeded(_sub(tmp_path, "b"))


def test_fixtures_found() -> None:
    assert len(FIXTURES) >= 10


def test_fixture_values_mapped(glossary: Glossary, pages: list[CardPage]) -> None:
    """Every value the parser emits for the fixtures has a glossary entry."""
    wanted: list[tuple[str, str]] = []
    for page in pages:
        for entry in page.entries:
            g = entry.gameplay
            wanted.append(("card_types", g.card_type))
            wanted += [("colors", c) for c in g.colors]
            wanted += [("symbols", s.symbol) for s in g.symbols]
            wanted += [("symbols", s.symbol) for s in g.reduction.parts]
            wanted += [("families", f) for f in g.families]
            if entry.text is not None:
                for effect in entry.text.effects:
                    wanted += [("keywords", k.name) for k in effect.keywords]
        wanted += [("rarities", p.rarity) for p in page.printings if p.rarity]
    assert wanted
    missing = sorted({w for w in wanted if w[0] in SEEDED and glossary.lookup(*w) is None})
    assert missing == []
