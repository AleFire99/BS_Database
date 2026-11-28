import glob
import json
from pathlib import Path

import pytest

from bs_database.glossary import FamilyEntry, Glossary, load_glossary
from bs_database.parsers.batspi.card import parse_card_page
from bs_database.parsers.card_models import CardPage

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY_DIR = ROOT / "data" / "glossary"
FIXTURES = sorted(glob.glob(str(ROOT / "tests" / "fixtures" / "html" / "card_*.html")))


@pytest.fixture(scope="module")
def glossary() -> Glossary:
    return load_glossary(GLOSSARY_DIR)


@pytest.fixture(scope="module")
def pages() -> list[CardPage]:
    return [
        parse_card_page(Path(f).read_text(encoding="utf-8"), "https://batspi.com/fixture")
        for f in FIXTURES
    ]


def test_seed_loads_and_is_stable() -> None:
    assert load_glossary(GLOSSARY_DIR) == load_glossary(GLOSSARY_DIR)


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
    missing = sorted({w for w in wanted if glossary.lookup(*w) is None})
    assert missing == []


LEGACY_PAIRS = [
    ("Rebirth", "Reptile Beast"),
    ("Sky Fang", "Flying Fang"),
    ("Flood", "Drifting Spirit"),
    ("Earth Dragon", "Terra Dragon"),
    ("Kidra", "Machine Dragon"),
    ("The Imperial Beast", "Emperor Beast"),
    ("War", "Mounted Warrior"),
    ("Pterosaur", "Winged Dragon"),
    ("Dragon Man", "Dragon"),
    ("Old Dragon", "Ancient Dragon"),
    ("Ghost", "Darkling"),
    ("No Wonder", "Zombie"),
    ("Cursed Demon", "Ogre Wizard"),
    ("Demon", "Evil Deity"),
    ("Night Tribe", "Nightling"),
    ("Sword Beast", "Blade Beast"),
    ("Tree Demon", "Plant Spirit"),
    ("Monster", "Parasite"),
    ("Claw Bird", "Winged Beast"),
    ("Yusei", "Imp"),
    ("Shell Man", "Shellman"),
    ("Motion", "Machine"),
    ("Sky Fish", "Flying Fish"),
    ("Light Insect", "Glow insect"),
    ("Armed", "Armed Machine"),
    ("Beast", "Machine Beast"),
    ("Man", "Android"),
    ("Human", "Android"),
    ("Melted Fish", "Lava Fish"),
    ("Imperial Beast", "Emperor Beast"),
    ("Old Dragons", "Ancient Dragon"),
    ("Demon Shadow", "Evil shadow"),
    ("Shellworm", "Shell Insect"),
    ("Axial Beast", "Armored Beast"),
    ("Raku Tribe", "Fairy"),
    ("Small Toy", "Toy Beast"),
    ("Four Way", "Magician"),
    ("New", "Incarnate"),
    ("Divine Beast", "Imaginary Beast"),
    ("Divine General", "Deified General"),
    ("Different", "Fusion Beast"),
]


def test_legacy_pair_count() -> None:
    assert len(LEGACY_PAIRS) == 41


@pytest.mark.parametrize(("legacy", "preferred"), LEGACY_PAIRS)
def test_legacy_pairs(glossary: Glossary, legacy: str, preferred: str) -> None:
    rows = [a for a in glossary.legacy_family_aliases if a.legacy_en == legacy]
    assert [(a.legacy_en, a.preferred_en) for a in rows] == [(legacy, preferred)]


def test_legacy_order_and_rebirth(glossary: Glossary) -> None:
    pairs = [(a.legacy_en, a.preferred_en) for a in glossary.legacy_family_aliases]
    assert pairs == LEGACY_PAIRS
    family = glossary.lookup("families", "爬獣")
    assert isinstance(family, FamilyEntry)
    assert "Rebirth" in family.aliases_en
    assert family.en == "Reptile Beast"


def test_unresolved_legacy(glossary: Glossary) -> None:
    assert len(glossary.unresolved_legacy()) == 40


def test_timings_and_classes_counts_and_shape(glossary: Glossary) -> None:
    timings = glossary.entries["timings"]
    assert len(timings) == 117
    assert sum(1 for t in timings if t.notes.startswith("in-text only")) == 22
    for t in timings:
        assert t.jp[0] == "『" and t.jp[-1] == "』", t.jp
        assert t.en[0] == "『" and t.en[-1] == "』", t.en
        assert t.en == t.en.strip()
        assert "  " not in t.en
    assert [(c.jp, c.code, c.en) for c in glossary.entries["card_classes"]] == [
        ("契約", "contract", "Contract"),
        ("トークン", "token", "Token"),
    ]
    contract = glossary.lookup("card_classes", "契約")
    assert contract is not None and contract.en == "Contract"
    summoned = glossary.lookup("timings", "『このスピリットの召喚時』")
    assert summoned is not None and summoned.en == "『When this Spirit is summoned』"


def test_every_normalized_timing_and_class_is_mapped(glossary: Glossary) -> None:
    """Needs the real ``data/normalized`` (git-ignored); skipped in CI."""
    pages = sorted((ROOT / "data" / "normalized").glob("*/*.json"))
    if not pages:
        pytest.skip("data/normalized is absent")
    seen: set[tuple[str, str]] = set()
    for path in pages:
        for entry in json.loads(path.read_text(encoding="utf-8"))["page"]["entries"]:
            if cls := entry["gameplay"].get("card_class_jp"):
                seen.add(("card_classes", cls))
            for effect in entry["text"]["effects"]:
                if effect["timing_jp"]:
                    seen.add(("timings", effect["timing_jp"]))
    assert seen
    assert sorted(k for k in seen if glossary.lookup(*k) is None) == []
