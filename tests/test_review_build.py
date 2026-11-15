"""Review proposals, CSV output and rendering (#96), offline and on tiny inputs."""

import csv
import io
from pathlib import Path
from typing import Any

import pytest
from test_review_legacy import entry, write_page

from bs_database.glossary import load_glossary
from bs_database.review.build import Review, build_review, slugify
from bs_database.review.corpus import NO_PRODUCT_CODE, collect_corpus, product_prefix
from bs_database.review.legacy import link_families
from bs_database.review.render import (
    FAMILIES_CSV,
    KEYWORDS_CSV,
    LEGACY_CSV,
    REVIEW_MD,
    cell,
    render_markdown,
    write_review,
)
from bs_database.review.source import ReviewError, iter_pages, read_csv_rows


def family(jp: str, en: str | None = None, source: str | None = None) -> dict[str, Any]:
    return {"jp": jp, "en": en, "en_source": source}


def card(number: str, families: list[dict[str, Any]], keywords: tuple[str, ...] = ()) -> Any:
    return {
        "number": number,
        "gameplay": {"families": families},
        "text": {"effects": [{"keywords": [{"name_jp": k} for k in keywords]}]},
    }


def printing(number: str, code: str | None, name: str, type_code: str | None = None) -> Any:
    return {
        "number": number,
        "product_code": code,
        "product_name_jp": name,
        "product_type_code": type_code,
    }


def page(entries: list[Any], printings: list[Any] | None = None) -> dict[str, Any]:
    return {"entries": entries, "printings": printings or []}


def fam_row(
    jp: str, code: str = "", en: str = "", extra: tuple[str, str, str] = ("", "", "")
) -> Any:
    return {
        "jp": jp,
        "code": code,
        "en": en,
        "notes": extra[0],
        "aliases_en": extra[1],
        "no_split": extra[2],
    }


def legacy_row(legacy_en: str, preferred: str, jp: str = "") -> Any:
    return {"legacy_en": legacy_en, "preferred_en": preferred, "jp": jp, "notes": ""}


def make_review(
    pages: list[dict[str, Any]],
    legacy: dict[str, tuple[str, ...]],
    families: list[Any] | None = None,
    keywords: list[Any] | None = None,
    aliases: list[Any] | None = None,
    prefixes: list[Any] | None = None,
) -> Review:
    corpus = collect_corpus(pages)
    link = link_families(corpus.card_families, legacy)
    return build_review(corpus, link, families or [], keywords or [], aliases or [], prefixes or [])


def strong_cards(
    jp: str, legacy_name: str, count: int = 2
) -> tuple[list[Any], dict[str, tuple[str, ...]]]:
    numbers = [f"{jp}-{i}" for i in range(count)]
    return [card(n, [family(jp)]) for n in numbers], {n: (legacy_name,) for n in numbers}


def test_slugify() -> None:
    assert slugify("Reptile Beast") == "reptile_beast"
    assert slugify("  Café-Au  Lait!") == "cafe_au_lait"
    assert slugify("神") == ""


def test_priority_alias_then_legacy_then_machine_then_blank() -> None:
    entries: list[Any] = []
    legacy: dict[str, tuple[str, ...]] = {}
    for jp, name in (("甲", "Rebirth"), ("乙", "Dragon")):
        e, lg = strong_cards(jp, name)
        entries += e
        legacy |= lg
    entries += [card("m-1", [family("丙", "Machine Name", "machine")]), card("b-1", [family("丁")])]
    review = make_review([page(entries)], legacy, aliases=[legacy_row("Rebirth", "Reptile Beast")])
    by = {f.jp: f for f in review.families}
    assert (by["甲"].en, by["甲"].source, by["甲"].code) == (
        "Reptile Beast",
        "alias",
        "reptile_beast",
    )
    assert (by["乙"].en, by["乙"].source) == ("Dragon", "legacy")
    assert (by["丙"].en, by["丙"].source) == ("Machine Name", "machine")
    assert (by["丁"].en, by["丁"].source, by["丁"].code) == ("", "", "")


def test_existing_glossary_en_and_code_win() -> None:
    entries, legacy = strong_cards("甲", "Other")
    review = make_review(
        [page(entries)], legacy, families=[fam_row("甲", "kept_code", "Kept", ("n", "a|b", "1"))]
    )
    (row,) = review.families
    assert (row.en, row.source, row.code) == ("Kept", "glossary", "kept_code")
    assert review.family_csv == (("甲", "kept_code", "Kept", "n", "a|b", "1"),)


def test_weak_link_is_shown_but_does_not_propose() -> None:
    entries = [card("n-1", [family("甲")]), card("n-2", [family("甲")])]
    review = make_review([page(entries)], {"n-1": ("x",), "n-2": ("y",)})
    (row,) = review.families
    assert row.en == ""
    assert not row.strong
    assert row.candidates == (("x", 1), ("y", 1))
    assert "| 甲 | 2 |  |  |  | 1/2 weak | x x1, y x1 |" in render_markdown(review)


def test_slug_conflicts_leave_codes_blank_and_are_flagged() -> None:
    entries: list[Any] = []
    legacy: dict[str, tuple[str, ...]] = {}
    for jp in ("甲", "乙"):
        e, lg = strong_cards(jp, "Same")
        entries += e
        legacy |= lg
    e, lg = strong_cards("丙", "Taken")
    entries += e
    legacy |= lg
    review = make_review([page(entries)], legacy, families=[fam_row("丁", "taken", "Taken")])
    by = {f.jp: f for f in review.families}
    assert by["甲"].code == by["乙"].code == by["丙"].code == ""
    assert by["甲"].conflict
    assert {(c.slug, c.jps) for c in review.conflicts} == {
        ("same", ("乙", "甲")),
        ("taken", ("丙",)),
    }
    assert "CONFLICT" in render_markdown(review)
    codes = [r[1] for r in review.family_csv]
    assert codes == sorted(codes)


def test_families_csv_includes_glossary_only_rows_sorted_by_code_then_jp() -> None:
    entries, legacy = strong_cards("甲", "Alpha")
    review = make_review([page(entries)], legacy, families=[fam_row("乙", "zeta", "Z")])
    assert [r[:3] for r in review.family_csv] == [("甲", "alpha", "Alpha"), ("乙", "zeta", "Z")]


def test_keywords_known_and_new() -> None:
    entries = [card("n-1", [], ("激突", "新語")), card("n-2", [], ("激突",))]
    review = make_review(
        [page(entries)],
        {},
        keywords=[
            {"jp": "激突", "code": "clash", "en": "", "notes": "x"},
            {"jp": "未使用", "code": "unused", "en": "U", "notes": ""},
        ],
    )
    by = {k.jp: k for k in review.keywords}
    assert (by["激突"].cards, by["激突"].known, by["激突"].code) == (2, True, "clash")
    assert not by["新語"].known
    assert by["未使用"].cards == 0
    assert review.keyword_csv[0] == ("新語", "", "", "")
    assert ("激突", "clash", "", "x") in review.keyword_csv
    assert "new: needs code and EN" in render_markdown(review)


def test_no_split_candidates_are_adjacent_pairs_that_never_appear_apart() -> None:
    entries = [
        card("n-1", [family("A"), family("B")]),
        card("n-2", [family("A"), family("B")]),
        card("n-3", [family("C"), family("D")]),
        card("n-4", [family("D")]),
        card("n-5", [family("E"), family("F")]),
        card("n-6", [family("E"), family("F")]),
    ]
    review = make_review([page(entries)], {}, families=[fam_row("E・F")])
    assert [(r.joined, r.cards) for r in review.no_split] == [("A・B", 2)]


def test_product_prefixes_group_count_and_show_mapping() -> None:
    printings = [
        printing("n-1", "BS01", "第1弾", "booster"),
        printing("n-2", "BS02", "第2弾"),
        printing("n-3", "BSC22", "スターター", None),
        printing("n-3", "BSC22", "スターター", None),
        printing("n-4", None, "不明"),
        printing("n-5", "9999", "他"),
    ]
    review = make_review(
        [page([], printings)],
        {},
        prefixes=[{"prefix": "BSC", "code": "starter", "notes": ""}],
    )
    by = {p.prefix: p for p in review.prefixes}
    assert (by["BS"].products, by["BS"].printings, by["BS"].unresolved) == (2, 2, 1)
    assert by["BS"].types == ("-", "booster")
    assert by["BS"].samples == ("BS01: 第1弾", "BS02: 第2弾")
    assert (by["BSC"].printings, by["BSC"].mapped) == (1, "starter")
    assert by["(none)"].samples == ("-: 不明",)
    assert by["(other)"].products == 1


def test_product_prefix_helper() -> None:
    assert product_prefix("BSC22") == "BSC"
    assert product_prefix(NO_PRODUCT_CODE) == "(none)"
    assert product_prefix("22X") == "22X"
    assert product_prefix("26RBS01") == "26RBS"
    assert product_prefix("2026") == "(other)"


def test_legacy_pairs_filled_kept_conflicting_and_missing() -> None:
    entries: list[Any] = []
    legacy: dict[str, tuple[str, ...]] = {}
    for jp, name in (("甲", "Rebirth"), ("乙", "Twin"), ("丙", "Twin")):
        e, lg = strong_cards(jp, name)
        entries += e
        legacy |= lg
    review = make_review(
        [page(entries)],
        legacy,
        aliases=[
            legacy_row("Rebirth", "Reptile Beast"),
            legacy_row("twin", "Twin Pair"),
            legacy_row("Gone", "Gone"),
            legacy_row("Kept", "Kept", "甲"),
        ],
    )
    assert [r.status for r in review.legacy] == [
        "filled",
        "conflict: 丙, 乙",
        "no strong link",
        "kept",
    ]
    assert review.legacy_csv[0] == ("Rebirth", "Reptile Beast", "甲", "")
    assert review.legacy_csv[1][2] == ""


def test_markdown_escapes_and_orders_families_by_cards() -> None:
    entries = [card("n-1", [family("a|b")]), card("n-2", [family("c")]), card("n-3", [family("c")])]
    text = render_markdown(make_review([page(entries)], {}))
    assert text.index("| c | 2 |") < text.index("| a\\|b | 1 |")
    assert "## Keywords (0)" in text
    assert "None." in text
    assert cell("x|y\nz") == "x\\|y z"


def test_empty_review_renders_all_sections() -> None:
    text = render_markdown(make_review([page([])], {}))
    for title in ("Families", "Keywords", "no_split candidates", "Product code prefixes"):
        assert f"## {title} (0)" in text


def test_write_review_files_are_deterministic_and_loadable_as_csv(tmp_path: Path) -> None:
    entries, legacy = strong_cards("甲", "Alpha")
    review = make_review([page(entries)], legacy)
    paths = write_review(tmp_path / "out", review)
    assert [p.name for p in paths] == [REVIEW_MD, FAMILIES_CSV, KEYWORDS_CSV, LEGACY_CSV]
    first = [p.read_bytes() for p in paths]
    write_review(tmp_path / "out", review)
    assert [p.read_bytes() for p in paths] == first
    rows = list(csv.reader(io.StringIO((tmp_path / "out" / FAMILIES_CSV).read_text("utf-8"))))
    assert rows[0] == ["jp", "code", "en", "notes", "aliases_en", "no_split"]
    assert rows[1][:3] == ["甲", "alpha", "Alpha"]


def test_generated_families_csv_passes_the_glossary_loader(tmp_path: Path) -> None:
    real = Path(__file__).parent.parent / "data" / "glossary"
    glossary_dir = tmp_path / "g"
    glossary_dir.mkdir()
    for f in real.glob("*.csv"):
        (glossary_dir / f.name).write_bytes(f.read_bytes())
    entries, legacy = strong_cards("新種", "Brand New")
    review = make_review([page(entries)], legacy, families=read_csv_rows(real / "families.csv"))
    write_review(tmp_path / "out", review)
    (glossary_dir / "families.csv").write_bytes((tmp_path / "out" / FAMILIES_CSV).read_bytes())
    loaded = load_glossary(glossary_dir)
    found = loaded.lookup("families", "新種")
    assert found is not None
    assert found.code == "brand_new"


def test_corpus_collects_from_pages_on_disk(tmp_path: Path) -> None:
    write_page(tmp_path, "a", [entry("N-1", "甲")])
    pages = [{**p, "printings": []} for p in iter_pages(tmp_path)]
    corpus = collect_corpus(pages)
    assert corpus.card_families == {"N-1": frozenset({"甲"})}
    assert corpus.family_cards == {"甲": 1}


def test_unresolved_slug_empty_for_non_ascii_en() -> None:
    entries, legacy = strong_cards("甲", "神族")
    (row,) = make_review([page(entries)], legacy).families
    assert (row.en, row.code, row.conflict) == ("神族", "", False)


@pytest.mark.parametrize("count", [0, 1])
def test_no_families_gives_empty_tables(count: int) -> None:
    review = make_review([page([card("n-1", [])] * count)], {})
    assert review.families == ()


def test_read_csv_rows(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    assert read_csv_rows(path) == [{"a": "1", "b": "2"}]
    with pytest.raises(ReviewError, match="cannot read"):
        read_csv_rows(tmp_path / "missing.csv")


def test_prefix_mapped_uses_the_normalizer_rule_and_groups_digit_prefixes() -> None:
    printings = [
        printing("n-1", "BSC22", "スターター"),
        printing("n-2", "26RBS01", "限定"),
        printing("n-3", "BS01", "第1弾"),
    ]
    review = make_review(
        [page([], printings)],
        {},
        prefixes=[
            {"prefix": "BS", "code": "booster", "notes": ""},
            {"prefix": "BSC", "code": "starter", "notes": ""},
        ],
    )
    by = {p.prefix: p for p in review.prefixes}
    assert by["BSC"].mapped == "starter"
    assert by["BS"].mapped == "booster"
    assert by["26RBS"].mapped == ""
    assert by["26RBS"].samples == ("26RBS01: 限定",)
    assert "(other)" not in by


def test_prefix_mapped_shows_longest_prefix_of_the_group() -> None:
    review = make_review(
        [page([], [printing("n-1", "BSC22", "x")])],
        {},
        prefixes=[{"prefix": "BS", "code": "booster", "notes": ""}],
    )
    assert review.prefixes[0].prefix == "BSC"
    assert review.prefixes[0].mapped == "booster"


def test_markdown_lists_no_legacy_count_sample_and_copy_notes() -> None:
    entries = [card(f"n-{i:02d}", [family("甲")]) for i in range(25)]
    text = render_markdown(make_review([page(entries)], {}))
    assert "Cards with no legacy family: 25." in text
    assert "First 20 (sorted): n-00, n-01" in text
    assert "n-19" in text
    assert "n-20" not in text
    assert "together" in text
