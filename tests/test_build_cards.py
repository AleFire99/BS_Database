"""Cards, numbers, gameplay, credits and details of the build (#120)."""

from pathlib import Path

import pytest
from build_support import as_document, build, golden_documents, golden_json, query

from bs_database.build import BuildError, BuildQualityError
from bs_database.build.reader import Json


@pytest.fixture(scope="module")
def golden_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("golden") / "g.db"
    build(out, golden_documents())
    return out


def test_adr_0004_fixture_cards(golden_db: Path) -> None:
    def cards(name: str) -> list[tuple[int, str]]:
        return query(
            golden_db,
            "SELECT c.id, group_concat(n.number) FROM cards c"
            " JOIN card_numbers n ON n.card_id = c.id"
            " WHERE c.name_jp = ? GROUP BY c.id ORDER BY c.id",
            name,
        )

    assert [n for _, n in cards("ゴラドン")] == ["BS01-001", "BSC22-001"]
    assert [n for _, n in cards("ダブルドロー")] == ["BS01-117", "BSC22-117"]
    assert sorted(n for _, n in cards("焔竜翼人マ・ドー")) == ["EX001,P001", "P20-19"]
    assert (
        query(golden_db, "SELECT count(*) FROM card_numbers")[0][0]
        > query(golden_db, "SELECT count(*) FROM cards")[0][0]
    )


def test_gameplay_rows_of_a_spirit(golden_db: Path) -> None:
    card = query(golden_db, "SELECT id FROM card_numbers WHERE number = 'BS72-007'")[0][0]
    cid = query(golden_db, "SELECT card_id FROM card_numbers WHERE id = ?", card)[0][0]
    assert query(
        golden_db,
        "SELECT t.code, c.cost, c.block_icon FROM cards c"
        " JOIN card_types t ON t.id = c.card_type_id"
        " WHERE c.id = ?",
        cid,
    ) == [("spirit", 4, "12")]
    assert query(
        golden_db,
        "SELECT s.code, r.count FROM card_reductions r JOIN symbols s ON s.id = r.symbol_id"
        " WHERE r.card_id = ? ORDER BY s.code",
        cid,
    ) == [("god", 1), ("red", 2)]
    assert query(
        golden_db,
        "SELECT level, cores, battle_points FROM card_levels WHERE card_id = ? ORDER BY level",
        cid,
    ) == [(1, 1, 3000), (2, 3, 7000)]
    assert query(
        golden_db,
        "SELECT f.code FROM card_families x JOIN families f ON f.id = x.family_id"
        " WHERE x.card_id = ? ORDER BY f.code",
        cid,
    ) == [("bujin",), ("kenzoku",)]
    assert query(
        golden_db,
        "SELECT c.code FROM card_colors x JOIN colors c ON c.id = x.color_id WHERE x.card_id = ?",
        cid,
    ) == [("red",)]


def test_credits_concepts_then_other_credits(golden_db: Path) -> None:
    rows = query(
        golden_db,
        "SELECT cr.position, cr.role_jp, cr.name FROM card_credits cr JOIN card_numbers n"
        " ON n.card_id = cr.card_id WHERE n.number = 'BS10-062'",
    )
    assert rows == [(1, "コンセプト", "石垣純哉")]
    assert query(
        golden_db,
        "SELECT cr.role_jp, cr.name FROM card_credits cr JOIN card_numbers n"
        " ON n.card_id = cr.card_id WHERE n.number = 'CB23-X05'",
    ) == [("ペイント", "株式会社スタジオヴィガ")]


def test_brave_and_ultimate_details(golden_db: Path) -> None:
    brave = query(
        golden_db,
        "SELECT d.fusion_condition_jp, d.fusion_bp_bonus FROM brave_details d JOIN card_numbers n"
        " ON n.card_id = d.card_id WHERE n.number = 'BS38-RV022'",
    )
    assert brave == [("右合体条件：コスト5以上\n左合体条件：コスト3以上", 3000)]
    summon = query(
        golden_db,
        "SELECT d.summon_condition_jp FROM ultimate_details d JOIN card_numbers n"
        " ON n.card_id = d.card_id WHERE n.number = 'SD19-X01'",
    )
    assert summon == [("【召喚条件：自分の赤スピリット1体以上】",)]
    types = dict(
        query(
            golden_db,
            "SELECT t.code, count(*) FROM cards c JOIN card_types t ON t.id = c.card_type_id"
            " GROUP BY t.code",
        )
    )
    assert query(golden_db, "SELECT count(*) FROM brave_details")[0][0] == types["brave"]
    assert query(golden_db, "SELECT count(*) FROM ultimate_details")[0][0] == types["ultimate"]


def _spirit() -> Json:
    return golden_json("card_spirit")


def test_duplicate_symbols_are_merged(tmp_path: Path) -> None:
    data = _spirit()
    god = {"symbol_jp": "神", "symbol_code": "god", "count": 1, "variant_jp": None}
    data["page"]["entries"][0]["gameplay"]["symbols"] = [
        {**god, "color_jp": "青"},
        {**god, "color_jp": "白"},
    ]
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert query(
        out,
        "SELECT s.code, x.count, x.color_jp FROM card_symbols x JOIN symbols s"
        " ON s.id = x.symbol_id",
    ) == [("god", 2, "青・白")]
    assert result.warnings["symbol_merged"] == 1


def test_unmapped_family_is_skipped_with_a_warning(tmp_path: Path) -> None:
    data = _spirit()
    gameplay = data["page"]["entries"][0]["gameplay"]
    gameplay["families"][0]["code"] = None
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert result.warnings["family_unmapped"] == 1
    assert query(out, "SELECT count(*) FROM card_families")[0][0] == len(gameplay["families"]) - 1


@pytest.mark.parametrize(
    ("field", "kind"),
    [("colors", "color_unmapped"), ("symbols", "symbol_unmapped")],
)
def test_unmapped_closed_lookup_value_fails_the_build(
    tmp_path: Path, field: str, kind: str
) -> None:
    data = _spirit()
    entry = data["page"]["entries"][0]["gameplay"][field][0]
    entry["symbol_code" if field == "symbols" else "code"] = None
    out = tmp_path / "x.db"
    with pytest.raises(BuildQualityError, match=kind):
        build(out, [as_document(data)])
    assert not out.exists()


def test_duplicate_level_keeps_the_first(tmp_path: Path) -> None:
    data = _spirit()
    levels = data["page"]["entries"][0]["gameplay"]["levels"]
    levels.append({**levels[0], "battle_points": 1})
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert result.warnings["level_duplicate"] == 1
    assert query(out, "SELECT battle_points FROM card_levels WHERE level = 1") == [(3000,)]


def test_block_icon_conflict_takes_the_first_and_counts(tmp_path: Path) -> None:
    data = _spirit()
    first = data["page"]["printings"][0]
    first["block_icon"] = None
    second = {**first, "block_icon": "A", "product_name_jp": "other"}
    third = {**first, "block_icon": "B", "product_name_jp": "another"}
    data["page"]["printings"] += [second, third]
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert query(out, "SELECT block_icon FROM cards") == [("A",)]
    assert result.warnings["block_icon_conflict"] == 1


_PAIRS = (
    "SELECT c.name_en, s.code, t.code, c.flavor_text_en, fs.code, ft.code FROM cards c"
    " LEFT JOIN translation_sources s ON s.id = c.en_source_id"
    " JOIN translation_statuses t ON t.id = c.en_status_id"
    " LEFT JOIN translation_sources fs ON fs.id = c.flavor_en_source_id"
    " JOIN translation_statuses ft ON ft.id = c.flavor_en_status_id"
)


def test_name_and_flavor_keep_their_own_provenance(tmp_path: Path) -> None:
    data = _spirit()
    entry = data["page"]["entries"][0]
    entry["name_en"], entry["en_source"], entry["en_status"] = "Hellhound", "batspi", "reviewed"
    entry["text"].update(flavor_en="A hound.", en_source="machine", en_status="machine")
    out = tmp_path / "x.db"
    build(out, [as_document(data)])
    assert query(out, _PAIRS) == [
        ("Hellhound", "batspi", "reviewed", "A hound.", "machine", "machine")
    ]


def test_missing_text_gives_a_pending_flavor_pair(tmp_path: Path) -> None:
    data = _spirit()
    entry = data["page"]["entries"][0]
    entry["name_en"], entry["en_source"], entry["en_status"] = "Hellhound", "batspi", "reviewed"
    entry["text"] = None
    out = tmp_path / "x.db"
    build(out, [as_document(data)])
    assert query(out, _PAIRS) == [("Hellhound", "batspi", "reviewed", None, None, "pending")]


def test_failed_flavor_leaves_the_name_pair(tmp_path: Path) -> None:
    data = _spirit()
    entry = data["page"]["entries"][0]
    entry["name_en"], entry["en_source"], entry["en_status"] = "Hellhound", "machine", "machine"
    entry["text"].update(flavor_en=None, en_source=None, en_status="failed")
    out = tmp_path / "x.db"
    build(out, [as_document(data)])
    assert query(out, _PAIRS) == [("Hellhound", "machine", "machine", None, None, "failed")]


def test_card_class_en_is_read_when_present(tmp_path: Path) -> None:
    data = _spirit()
    out = tmp_path / "x.db"
    build(out, [as_document(data)])
    assert query(out, "SELECT card_class_en FROM cards") == [(None,)]
    data["page"]["entries"][0]["gameplay"]["card_class_en"] = "Contract"
    build(out, [as_document(data)])
    assert query(out, "SELECT card_class_en FROM cards") == [("Contract",)]


def test_unmapped_card_type_is_an_error(tmp_path: Path) -> None:
    data = _spirit()
    data["page"]["entries"][0]["gameplay"]["card_type_code"] = None
    with pytest.raises(BuildError, match="card type"):
        build(tmp_path / "x.db", [as_document(data)])


def test_dropped_card_fields_are_loaded(golden_db: Path) -> None:
    def card(number: str) -> tuple[object, ...]:
        return query(
            golden_db,
            "SELECT c.deck_limit, c.reduction_plain, c.overclock_count_min,"
            " c.overclock_bp_bonus, c.overclock_condition_jp, c.flavor_note_jp"
            " FROM cards c JOIN card_numbers n ON n.card_id = c.id WHERE n.number = ?",
            number,
        )[0]

    assert card("SD10-009") == (1, 3, None, None, None, None)
    assert card("P22-14") == (None, 1, 3, 4000, "OC条件：カウント3以上", None)
    assert card("SD67-CP01") == (None, None, 5, 6000, "OC条件：カウント5以上", None)
    assert card("BS01-117")[5] == "バトルスピリッツ メモリアルカードダスセット Hero Ver."
    assert card("BS01-001") == (None, 0, None, None, None, None)  # plain 0 is kept, not NULL


def test_overclock_columns_are_both_set_or_both_null(golden_db: Path) -> None:
    assert not query(
        golden_db,
        "SELECT 1 FROM cards WHERE (overclock_count_min IS NULL) <> (overclock_bp_bonus IS NULL)",
    )


def _details(path: Path, table: str, column: str) -> set[tuple[object, ...]]:
    return set(
        query(
            path,
            f"SELECT d.{column}, s.code, t.code FROM {table} d"
            " LEFT JOIN translation_sources s ON s.id = d.en_source_id"
            " JOIN translation_statuses t ON t.id = d.en_status_id",
        )
    )


def test_condition_english_is_read_with_its_pair(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    brave = golden_json("card_brave")
    build(out, [as_document(brave)])
    assert _details(out, "brave_details", "fusion_condition_en") == {(None, None, "pending")}
    for entry in brave["page"]["entries"]:
        entry["text"].update(
            fusion_conditions_en=["Right: cost 5+", "Left: cost 3+"],
            fusion_en_source="machine",
            fusion_en_status="machine",
        )
    build(out, [as_document(brave)])
    assert _details(out, "brave_details", "fusion_condition_en") == {
        ("Right: cost 5+\nLeft: cost 3+", "machine", "machine")
    }
    ultimate = golden_json("card_ultimate")
    for entry in ultimate["page"]["entries"]:
        entry["text"].update(
            summon_condition_en="Summon: 1+ red spirit",
            summon_en_source="manual",
            summon_en_status="reviewed",
        )
    build(out, [as_document(ultimate)])
    assert _details(out, "ultimate_details", "summon_condition_en") == {
        ("Summon: 1+ red spirit", "manual", "reviewed")
    }
