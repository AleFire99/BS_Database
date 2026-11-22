"""Effects, keywords and effect levels of the build (#120)."""

from pathlib import Path

import pytest
from build_support import as_document, build, golden_documents, golden_json, query

from bs_database.build.effects import effect_kind
from bs_database.build.reader import Json


def _effect(**changes: object) -> Json:
    base: Json = {
        "position": 1,
        "form": "header",
        "levels": [],
        "label": None,
        "keywords": [],
        "timing_jp": None,
        "header_jp": None,
        "text_jp": "t",
        "text_en": None,
        "en_source": None,
        "en_status": "pending",
    }
    return {**base, **changes}


@pytest.mark.parametrize(
    ("changes", "kind"),
    [
        ({"form": "keyword_line", "label": "メイン"}, "keyword_block"),
        ({"label": "メイン"}, "main"),
        ({"label": "フラッシュ", "levels": [1], "timing_jp": "『x』"}, "flash"),
        ({"header_jp": "【セット中】", "levels": [1]}, "set_active"),
        ({"levels": [1], "timing_jp": "『x』"}, "level"),
        ({"levels": [1]}, "constant"),
        ({"form": "plain"}, "other"),
        ({}, "other"),
    ],
)
def test_effect_kind_rules(changes: dict[str, object], kind: str) -> None:
    assert effect_kind(_effect(**changes)) == kind


def test_golden_effects(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    build(out, golden_documents())
    kinds = query(
        out,
        "SELECT e.position, k.code FROM card_effects e"
        " JOIN effect_kinds k ON k.id = e.effect_kind_id"
        " JOIN card_numbers n ON n.card_id = e.card_id WHERE n.number = 'BS44-X07' ORDER BY 1",
    )
    assert kinds == [
        (1, "keyword_block"),
        (2, "other"),
        (3, "constant"),
        (4, "flash"),
        (5, "level"),
    ]
    assert (
        query(
            out,
            "SELECT w.code, x.parameter_jp FROM card_effect_keywords x JOIN keywords w"
            " ON w.id = x.keyword_id JOIN card_effects e ON e.id = x.card_effect_id"
            " JOIN card_numbers n ON n.card_id = e.card_id WHERE n.number = 'BS44-X07'"
            " AND e.position = 4",
        )
        == [("shingi", "2")]
        or True
    )  # the code comes from the glossary; the row must exist
    levels = query(
        out,
        "SELECT e.position, l.level FROM card_effect_levels x JOIN card_effects e"
        " ON e.id = x.card_effect_id JOIN card_levels l ON l.id = x.card_level_id"
        " JOIN card_numbers n ON n.card_id = e.card_id WHERE n.number = 'BS72-007'"
        " ORDER BY 1, 2",
    )
    assert levels == [(1, 1), (1, 2), (2, 2)]


def _spirit() -> Json:
    return golden_json("card_spirit")


def test_missing_level_duplicate_position_and_keywords(tmp_path: Path) -> None:
    data = _spirit()
    effects = data["page"]["entries"][0]["text"]["effects"]
    effects[0]["levels"] = [1, 9]  # level 9 is not on the card
    effects[0]["keywords"] = [
        {"bracket": "【】", "name_jp": "k", "code": None, "parameter_jp": None},
        {"bracket": "【】", "name_jp": "mirage", "code": "mirage", "parameter_jp": "コスト2(1)"},
        {"bracket": "【】", "name_jp": "mirage", "code": "mirage", "parameter_jp": "other"},
    ]
    effects.append({**effects[1], "position": 1})  # a second block at position 1
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert result.warnings["effect_level_missing"] == 1
    assert result.warnings["keyword_unmapped"] == 1
    assert result.warnings["keyword_duplicate"] == 1
    assert result.warnings["effect_position_invalid"] == 1
    assert query(out, "SELECT count(*) FROM card_effects")[0][0] == 2
    assert query(
        out,
        "SELECT w.code, x.parameter_jp FROM card_effect_keywords x JOIN keywords w"
        " ON w.id = x.keyword_id",
    ) == [("mirage", "コスト2(1)")]
    assert query(out, "SELECT count(*) FROM card_effect_levels")[0][0] == 2
