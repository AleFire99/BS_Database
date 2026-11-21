"""Cards, numbers, gameplay, credits and details of the build (#120)."""

from pathlib import Path

import pytest
from build_support import as_document, build, golden_documents, golden_json, query

from bs_database.build import BuildError
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


def test_unmapped_codes_are_skipped_with_warnings(tmp_path: Path) -> None:
    data = _spirit()
    gameplay = data["page"]["entries"][0]["gameplay"]
    gameplay["families"][0]["code"] = None
    gameplay["colors"][0]["code"] = None
    gameplay["symbols"][0]["symbol_code"] = None
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert result.warnings["family_unmapped"] == 1
    assert result.warnings["color_unmapped"] == 1
    assert result.warnings["symbol_unmapped"] == 1
    assert query(out, "SELECT count(*) FROM card_families")[0][0] == len(gameplay["families"]) - 1
    assert query(out, "SELECT count(*) FROM card_colors")[0][0] == 0


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


def test_english_pair_follows_the_text_that_exists(tmp_path: Path) -> None:
    data = _spirit()
    entry = data["page"]["entries"][0]
    entry["name_en"] = "Hellhound"
    entry["en_source"], entry["en_status"] = "machine", "machine"
    out = tmp_path / "x.db"
    build(out, [as_document(data)])
    assert query(
        out,
        "SELECT c.name_en, s.code, t.code FROM cards c JOIN translation_sources s"
        " ON s.id = c.en_source_id JOIN translation_statuses t ON t.id = c.en_status_id",
    ) == [("Hellhound", "machine", "machine")]
    entry["name_en"], entry["en_source"], entry["en_status"] = None, None, "failed"
    build(out, [as_document(data)])
    assert query(
        out,
        "SELECT c.name_en, c.en_source_id, t.code FROM cards c JOIN translation_statuses t"
        " ON t.id = c.en_status_id",
    ) == [(None, None, "failed")]


def test_unmapped_card_type_is_an_error(tmp_path: Path) -> None:
    data = _spirit()
    data["page"]["entries"][0]["gameplay"]["card_type_code"] = None
    with pytest.raises(BuildError, match="card type"):
        build(tmp_path / "x.db", [as_document(data)])
