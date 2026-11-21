"""Normalized goldens: html -> parse -> parsed store -> normalize_tree (#93)."""

import json
from pathlib import Path

import pytest
from golden_support import (
    NORMALIZED_GOLDENS,
    REGEN_COMMAND,
    card_fixture_names,
    golden_path,
    normalized_documents,
)


@pytest.fixture(scope="module")
def documents(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return normalized_documents(tmp_path_factory.mktemp("goldens"))


@pytest.mark.parametrize("name", card_fixture_names())
def test_matches_golden(documents: dict[str, str], name: str) -> None:
    path = golden_path(name)
    assert path.is_file(), f"missing golden {path.name}; regenerate with {REGEN_COMMAND}"
    assert documents[name] == path.read_text(encoding="utf-8"), (
        f"{path.name} differs; regenerate with {REGEN_COMMAND}"
    )


def test_no_stale_goldens() -> None:
    expected = {golden_path(n).name for n in card_fixture_names()}
    assert {p.name for p in NORMALIZED_GOLDENS.glob("*.json")} == expected


def test_second_run_is_byte_equal(documents: dict[str, str], tmp_path: Path) -> None:
    assert normalized_documents(tmp_path) == documents


def golden_entries(stem: str) -> list[dict[str, object]]:
    document = json.loads((NORMALIZED_GOLDENS / f"{stem}.json").read_text(encoding="utf-8"))
    entries: list[dict[str, object]] = document["page"]["entries"]
    return entries


def test_new_card_fields_are_carried_as_literals() -> None:
    """#108, ADR 0010: class, mark, symbol variant and other credits stay as printed."""
    (contract, *_) = golden_entries("card_spirit_contract")
    gameplay = contract["gameplay"]
    assert isinstance(gameplay, dict)
    assert (gameplay["card_type_code"], gameplay["card_class_jp"]) == ("spirit", "契約")
    (marked, *_) = golden_entries("card_spirit_mark_light_limit")
    assert marked["gameplay"]["type_mark_jp"] == "光"  # type: ignore[index]
    symbols = [s for e in golden_entries("card_magic_symbol_ex") for s in e["gameplay"]["symbols"]]  # type: ignore[index]
    assert [(s["symbol_code"], s["variant_jp"], s["color_jp"]) for s in symbols] == [
        ("white", "EX", None)
    ]
    credits = [
        c["role"]
        for e in golden_entries("card_spirit_credit_producer")
        for c in e["text"]["other_credits"]  # type: ignore[index]
    ]
    assert credits == ["プロデュース"]
