"""The card DTOs are frozen, versioned and JSON-serialisable."""

import dataclasses
import json

import pytest

from bs_database.parsers.card_models import (
    SCHEMA_VERSION,
    CardEntry,
    CardImage,
    CardPage,
    CardText,
    Credit,
    Effect,
    Gameplay,
    Keyword,
    Level,
    Printing,
    Reduction,
    SymbolCount,
)


def sample() -> CardPage:
    gameplay = Gameplay(
        card_type="スピリット",
        deck_limit=None,
        cost=4,
        reduction=Reduction(plain=None, parts=(SymbolCount("赤", 2),)),
        colors=("赤",),
        symbols=(SymbolCount("赤", 1),),
        families=("眷属",),
        levels=(Level(1, 1, 3000),),
        fusion_bp_bonus=None,
        overclock=None,
    )
    entry = CardEntry("BS72-007", "名前", None, gameplay)
    return CardPage(SCHEMA_VERSION, "https://example.invalid/", "名前", (entry,), ())


def test_schema_version() -> None:
    assert SCHEMA_VERSION == "1.1.0"


def test_frozen() -> None:
    page = sample()
    with pytest.raises(dataclasses.FrozenInstanceError):
        page.url = "x"  # type: ignore[misc]


def test_json_round_trip() -> None:
    data = json.loads(json.dumps(dataclasses.asdict(sample()), ensure_ascii=False))
    assert data["schema_version"] == "1.1.0"
    assert data["entries"][0]["gameplay"]["levels"] == [
        {"level": 1, "cores": 1, "battle_points": 3000}
    ]


def test_text_printings_and_images_round_trip() -> None:
    page = sample()
    effect = Effect(1, "header", (1, 2), None, (Keyword("【", "合体時", None),), "『x』", "h", "t")
    text = CardText((effect,), ("合体条件：x",), None, None, (Credit("a", None),), (), "f", None)
    printing = Printing("BS72-007", "p", None, "R", None, None, "BS72", "12", "2025-05-17", "収録")
    image = CardImage("BS72-007", "https://x/l.jpg", "https://x/s.jpg", ("p",))
    entry = dataclasses.replace(page.entries[0], text=text)
    full = dataclasses.replace(page, entries=(entry,), printings=(printing,), images=(image,))
    data = json.loads(json.dumps(dataclasses.asdict(full), ensure_ascii=False))
    assert data["entries"][0]["text"]["effects"][0]["keywords"][0]["name"] == "合体時"
    assert data["printings"][0]["release_date"] == "2025-05-17"
    assert data["images"][0]["caption"] == ["p"]


def test_new_fields_default() -> None:
    page = sample()
    assert page.entries[0].text is None
    assert page.printings == ()
    assert page.images == ()
