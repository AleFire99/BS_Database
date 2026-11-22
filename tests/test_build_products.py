"""Products and printings of the build: dedup, folding and fallbacks (#120)."""

from pathlib import Path

import pytest
from build_support import as_document, build, golden_documents, golden_json, query

from bs_database.build import BuildError
from bs_database.build.products import pick_illustrator
from bs_database.build.reader import Json


def _credit(name: str, note: str | None = None) -> Json:
    return {"name": name, "note": note}


def test_illustrator_rules() -> None:
    assert pick_illustrator([], []) is None
    assert pick_illustrator([_credit("")], []) is None
    assert pick_illustrator([_credit("A", "somewhere")], ["x"]) == "A"
    both = [_credit("A"), _credit("B", "第3章")]
    assert pick_illustrator(both, ["契約編 第3章"]) == "B"  # the note matches the product text
    assert pick_illustrator(both, ["第1章"]) == "A"  # no match: the only note-less one
    two_plain = [_credit("A"), _credit("B"), _credit("A")]
    assert pick_illustrator(two_plain, []) == "A / B"
    ambiguous = [_credit("A", "第3章"), _credit("B", "第3章")]
    assert pick_illustrator(ambiguous, ["第3章"]) == "A / B"


def _doc() -> Json:
    return golden_json("card_spirit")


def _row(data: Json, **changes: object) -> Json:
    template = golden_json("card_spirit")["page"]["printings"][0]
    return {**template, "variant_code": "normal", **changes}


def test_product_merge_most_frequent_name_type_and_earliest_date(tmp_path: Path) -> None:
    data = _doc()
    base = _row(
        data,
        product_code="ZZ1",
        product_name_jp="b",
        product_type_code="starter",
        release_date="2025-02-02",
    )
    data["page"]["printings"] = [
        base,
        _row(
            data,
            product_code="ZZ1",
            product_name_jp="a",
            product_type_code="booster",
            release_date="2025-01-01",
            variant_code="secret",
        ),
        _row(
            data,
            product_code="ZZ1",
            product_name_jp="a",
            product_type_code="booster",
            release_date=None,
            variant_code="parallel",
        ),
        _row(
            data,
            product_code="ZZ1",
            product_name_jp="b",
            product_type_code="starter",
            release_date="2025-03-03",
            variant_code="full_art",
        ),
    ]
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    # names a, b both twice: the tie goes to the sorted first; the same for the type
    assert query(out, "SELECT code, name_jp, release_date FROM products") == [
        ("ZZ1", "a", "2025-01-01")
    ]
    assert query(
        out, "SELECT t.code FROM products p JOIN product_types t ON t.id = p.product_type_id"
    ) == [("booster",)]
    assert result.warnings["product_name_conflict"] == 1
    assert result.warnings["product_type_conflict"] == 1


def test_name_only_row_folds_into_the_code_of_its_name(tmp_path: Path) -> None:
    data = _doc()
    data["page"]["printings"] = [
        _row(data, product_code="ZZ1", product_name_jp="Set"),
        _row(data, product_code=None, product_name_jp="Set", variant_code="secret"),
        _row(data, product_code=None, product_name_jp="Lonely", variant_code="parallel"),
    ]
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert query(out, "SELECT code, name_jp FROM products ORDER BY id") == [
        ("ZZ1", "Set"),
        (None, "Lonely"),
    ]
    assert result.warnings["product_name_folded"] == 1
    assert query(out, "SELECT count(*) FROM printings")[0][0] == 3


def test_name_with_two_codes_is_not_folded(tmp_path: Path) -> None:
    data = _doc()
    data["page"]["printings"] = [
        _row(data, product_code="ZZ1", product_name_jp="Set"),
        _row(data, product_code="ZZ2", product_name_jp="Set", variant_code="secret"),
        _row(data, product_code=None, product_name_jp="Set", variant_code="parallel"),
    ]
    out = tmp_path / "x.db"
    build(out, [as_document(data)])
    assert query(out, "SELECT count(*) FROM products")[0][0] == 3


def test_product_without_type_falls_back_to_other(tmp_path: Path) -> None:
    data = _doc()
    data["page"]["printings"] = [
        _row(data, product_code=None, product_name_jp="Mystery", product_type_code=None)
    ]
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert query(
        out, "SELECT t.code FROM products p JOIN product_types t ON t.id = p.product_type_id"
    ) == [("other",)]
    assert result.warnings["product_without_type"] == 1


def test_duplicate_printings_merge_first_wins_and_nulls_fill(tmp_path: Path) -> None:
    data = _doc()
    first = _row(data, rarity_code=None, rarity_jp=None)
    data["page"]["printings"] = [
        first,
        _row(data, rarity_code="R"),
        _row(data, rarity_code="C"),
    ]
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert query(out, "SELECT r.code FROM printings p JOIN rarities r ON r.id = p.rarity_id") == [
        ("R",)
    ]
    assert result.warnings["printing_duplicate_merged"] == 2
    assert result.warnings["printing_rarity_conflict"] == 1


def test_printing_of_an_unknown_number_is_skipped(tmp_path: Path) -> None:
    data = _doc()
    data["page"]["printings"].append(_row(data, number="NOPE-1"))
    out = tmp_path / "x.db"
    result = build(out, [as_document(data)])
    assert result.warnings["printing_number_unknown"] == 1
    assert query(out, "SELECT count(*) FROM printings")[0][0] == 1


def test_unknown_variant_and_rarity_are_errors(tmp_path: Path) -> None:
    data = _doc()
    data["page"]["printings"] = [_row(data, variant_code="nope")]
    with pytest.raises(BuildError, match="variant"):
        build(tmp_path / "x.db", [as_document(data)])
    data["page"]["printings"] = [_row(data, rarity_code="nope")]
    with pytest.raises(BuildError, match="rarity"):
        build(tmp_path / "x.db", [as_document(data)])


def test_golden_printings(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    build(out, golden_documents())
    assert query(
        out,
        "SELECT p.code, p.name_jp, p.release_date, pr.code, v.code, r.code, x.illustrator"
        " FROM printings x JOIN card_numbers n ON n.id = x.card_number_id"
        " JOIN products p ON p.id = x.product_id JOIN product_types pr ON pr.id = p.product_type_id"
        " JOIN variants v ON v.id = x.variant_id LEFT JOIN rarities r ON r.id = x.rarity_id"
        " WHERE n.number = 'BS72-007'",
    ) == [
        ("BS72", "契約編：環 第1章：廻帰再醒", "2025-05-17", "booster", "secret", "R", "伊藤正市")
    ]


def test_printing_detail_and_note_merge_distinct_values_in_order(tmp_path: Path) -> None:
    data = _doc()
    data["page"]["printings"] = [
        _row(data, detail_jp="a", note_jp=None),
        _row(data, detail_jp="b", note_jp="n1"),
        _row(data, detail_jp="a", note_jp="n2"),
        _row(data, detail_jp="", note_jp="n1"),
        _row(data, variant_code="secret", detail_jp=None, note_jp=None),
    ]
    out = tmp_path / "x.db"
    build(out, [as_document(data)])
    assert query(
        out,
        "SELECT v.code, p.detail_jp, p.note_jp FROM printings p"
        " JOIN variants v ON v.id = p.variant_id ORDER BY v.code",
    ) == [("normal", "a\nb", "n1\nn2"), ("secret", None, None)]
