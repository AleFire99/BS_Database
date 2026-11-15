"""The card DTOs are frozen, versioned and JSON-serialisable."""

import dataclasses
import json

import pytest

from bs_database.parsers.card_models import (
    SCHEMA_VERSION,
    CardEntry,
    CardPage,
    Gameplay,
    Level,
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
    assert SCHEMA_VERSION == "1.0.0"


def test_frozen() -> None:
    page = sample()
    with pytest.raises(dataclasses.FrozenInstanceError):
        page.url = "x"  # type: ignore[misc]


def test_json_round_trip() -> None:
    data = json.loads(json.dumps(dataclasses.asdict(sample()), ensure_ascii=False))
    assert data["schema_version"] == "1.0.0"
    assert data["entries"][0]["gameplay"]["levels"] == [
        {"level": 1, "cores": 1, "battle_points": 3000}
    ]
