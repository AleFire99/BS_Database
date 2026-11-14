import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from bs_database import normalize
from bs_database.normalize import (
    load_family_mappings,
    normalize_card,
    normalize_family,
    normalize_tree,
    normalize_type,
    split_family,
    transform_family_names,
)

FIXTURES = Path(__file__).parent / "fixtures"
GOLDENS = Path(__file__).parent / "goldens" / "normalized"
MAPPING = FIXTURES / "family_mapping.txt"


def test_normalize_tree_matches_legacy_goldens(tmp_path: Path) -> None:
    root = tmp_path / "card_json"
    shutil.copytree(FIXTURES / "card_json", root)
    written = normalize_tree(root, MAPPING)
    golden_files = sorted(GOLDENS.rglob("*.json"))
    assert written == len(golden_files) == 21
    for golden_path in golden_files:
        got = json.loads((root / golden_path.relative_to(GOLDENS)).read_text(encoding="utf-8"))
        want = json.loads(golden_path.read_text(encoding="utf-8"))
        got_family = got.pop("family", None)
        want_family = want.pop("family", None)
        assert got == want, golden_path.name
        if want_family is None:
            assert got_family is None
        else:
            assert set(got_family) == set(want_family), golden_path.name


def test_load_family_mappings() -> None:
    mapping = load_family_mappings(MAPPING)
    assert mapping["sky fang"] == "Flying Fang"
    assert all(k == k.lower() for k in mapping)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Dragon, Beast and Ogres", ["Dragon", "Beast", "Ogres"]),
        ("Machine:Armed", ["Machine", "Armed"]),
        ("Next Generation of Dragons", ["Next Generation", "Dragons"]),
        ("New Hero", ["New", "Hero"]),
        ("New", ["New"]),
        ("Different Beast", ["Different", "Beast"]),
        (" , ,", []),
    ],
)
def test_split_family(raw: str, expected: list[str]) -> None:
    assert split_family(raw) == expected


def test_transform_family_names() -> None:
    mapping = {"sky fang": "Flying Fang"}
    names = ["Dark Snakes", "sky fang", "The Imperial Beast", "And Fairies", "A Warrior", "S"]
    result = transform_family_names(names, mapping)
    assert set(result) == {"Dark Snake", "Flying Fang", "Imperial Beast", "Fairie", "Warrior", "S"}
    assert len(result) == len(set(result))


def test_normalize_family_types() -> None:
    assert normalize_family(5, {}) == 5
    assert normalize_family(["Dragon", 5], {}) == ["Dragon"]
    assert normalize_family("", {}) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Spirit (Attribute)", "Spirit"), ("spirit", "Spirit"), ("  BRAVE ", "Brave")],
)
def test_normalize_type(raw: str, expected: str) -> None:
    assert normalize_type(raw) == expected


def test_normalize_card_image_and_missing_keys() -> None:
    card: dict[str, Any] = {"image": "a\\b.jpg", "type": 3}
    assert normalize_card(card, {}) == {"image": "a/b.jpg", "type": 3}


def test_invalid_json_skipped_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "ok.json").write_text('{"type": "spirit (x)"}', encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="bs_database.normalize"):
        assert normalize_tree(tmp_path, MAPPING) == 1
    assert "invalid JSON" in caplog.text
    assert (tmp_path / "bad.json").read_text(encoding="utf-8") == "{not json"
    assert json.loads((tmp_path / "ok.json").read_text(encoding="utf-8")) == {"type": "Spirit"}


def test_import_touches_no_files(tmp_path: Path) -> None:
    code = "import os, bs_database.normalize; print(sorted(os.listdir('.')))"
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]"
    assert normalize.logger.name == "bs_database.normalize"
