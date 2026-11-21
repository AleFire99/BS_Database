"""Review with fandom names (#104): ranking, disagreement, romaji codes, rarity table."""

from pathlib import Path
from typing import Any

import pytest
from test_cli_glossary_review import data_dir as data_dir  # noqa: F401  (fixture)
from test_review_build import (
    card,
    fam_row,
    family,
    legacy_row,
    page,
    strong_cards,
)
from test_review_legacy import make_legacy

from bs_database.parsers.fandom import FandomName, FandomRarity
from bs_database.review.build import Review, build_review
from bs_database.review.corpus import collect_corpus
from bs_database.review.fandom import (
    FandomData,
    load_names,
    write_names,
)
from bs_database.review.legacy import link_families
from bs_database.review.render import render_markdown
from bs_database.review.source import ReviewError


def name(jp: str, en: str, romaji: str | None, title: str | None = None) -> FandomName:
    return FandomName(jp=jp, en=en, romaji=romaji, title=title or en)


def make(
    pages: list[Any],
    legacy: dict[str, tuple[str, ...]],
    fandom: FandomData | None,
    families: list[Any] | None = None,
    keywords: list[Any] | None = None,
    aliases: list[Any] | None = None,
) -> Review:
    corpus = collect_corpus(pages)
    link = link_families(corpus.card_families, legacy)
    return build_review(corpus, link, families or [], keywords or [], aliases or [], [], fandom)


def test_fandom_ranks_between_glossary_and_alias() -> None:
    entries, legacy = strong_cards("甲", "Rebirth")
    more, more_legacy = strong_cards("乙", "Dragon")
    entries += more + [card("c-1", [family("丙")])]
    data = FandomData(
        families=[name("甲", "Reptile Beast", "kijuu"), name("乙", "Fandom Dragon", None)]
    )
    review = make(
        [page(entries)],
        legacy | more_legacy,
        data,
        families=[fam_row("丙", "", "Mine")],
        aliases=[legacy_row("Rebirth", "Alias Name")],
    )
    by = {f.jp: f for f in review.families}
    assert (by["甲"].en, by["甲"].source) == ("Reptile Beast", "fandom")
    assert (by["乙"].en, by["乙"].source) == ("Fandom Dragon", "fandom")
    assert (by["丙"].en, by["丙"].source) == ("Mine", "glossary")  # glossary beats fandom
    sources = dict(review.family_sources)
    assert sources["fandom"] == 2
    assert sources["glossary"] == 1


def test_without_fandom_nothing_changes() -> None:
    entries, legacy = strong_cards("甲", "Dragon")
    review = make([page(entries)], legacy, None)
    (row,) = review.families
    assert (row.en, row.source) == ("Dragon", "legacy")
    assert not review.with_fandom
    markdown = render_markdown(review)
    assert "## Rarities" not in markdown
    assert "Family names by source" not in markdown


def test_matching_ignores_width_and_whitespace() -> None:
    entries = [card("n-1", [family("ｱｸｾﾙ ")])]
    review = make([page(entries)], {}, FandomData(families=[name("アクセル", "Accel", "akuseru")]))
    (row,) = review.families
    assert (row.en, row.source, row.code) == ("Accel", "fandom", "akuseru")


def test_disagreement_shows_both_candidates() -> None:
    entries, legacy = strong_cards("甲", "Old Name")
    review = make([page(entries)], legacy, FandomData(families=[name("甲", "New Name", "kou")]))
    (row,) = review.families
    assert row.en == "New Name"
    markdown = render_markdown(review)
    assert "Old Name x2" in markdown  # the legacy candidate stays visible
    # when the proposal is the glossary's, the fandom name is listed as a candidate
    review = make(
        [page(entries)],
        legacy,
        FandomData(families=[name("甲", "New Name", "kou")]),
        families=[fam_row("甲", "", "Kept")],
    )
    assert "fandom: New Name" in render_markdown(review)
    agree = make([page(entries)], legacy, FandomData(families=[name("甲", "old name", "kou")]))
    assert "fandom:" not in render_markdown(agree).split("## Families")[1].split("## Keywords")[0]


@pytest.mark.parametrize(
    ("romaji", "en", "code"),
    [
        ("kijuu", "Machine Beast", "kijuu"),
        ("Āmā-tai", "Armor", "ama_tai"),
        ("shin-en", "Abyssen", "shin_en"),
        (None, "Machine Beast", "machine_beast"),  # fallback: the English slug
    ],
)
def test_code_from_fandom_romaji(romaji: str | None, en: str, code: str) -> None:
    review = make(
        [page([card("n-1", [family("甲")])])], {}, FandomData(families=[name("甲", en, romaji)])
    )
    (row,) = review.families
    assert row.code == code
    assert review.family_csv[0][:4] == ("甲", code, en, f"fandom: {en}")


def test_existing_code_kept_and_conflicts_flagged() -> None:
    entries = [card("n-1", [family("甲"), family("乙")])]
    data = FandomData(families=[name("甲", "A", "same"), name("乙", "B", "same")])
    review = make([page(entries)], {}, data)
    assert {c.slug for c in review.conflicts} == {"same"}
    assert all(f.code == "" for f in review.families)
    kept = make([page(entries)], {}, data, families=[fam_row("甲", "mine")])
    assert {f.jp: f.code for f in kept.families}["甲"] == "mine"


def test_keywords_take_fandom_en_and_code() -> None:
    entries = [card("n-1", [], keywords=("アクセル", "未知"))]
    data = FandomData(keywords=[name("アクセル", "Accel", "Akuseru")])
    review = make([page(entries)], {}, data)
    by = {k.jp: k for k in review.keywords}
    assert (by["アクセル"].en, by["アクセル"].code, by["アクセル"].fandom_title) == (
        "Accel",
        "akuseru",
        "Accel",
    )
    assert (by["未知"].en, by["未知"].code) == ("", "")
    assert ("アクセル", "akuseru", "Accel", "fandom: Accel") in review.keyword_csv
    markdown = render_markdown(review)
    assert "new: from fandom (Accel)" in markdown
    assert "new: needs code and EN" in markdown


def test_keyword_existing_row_wins_and_clash_is_flagged() -> None:
    entries = [card("n-1", [], keywords=("甲", "乙", "丙"))]
    data = FandomData(
        keywords=[name("甲", "A", "dup"), name("乙", "B", "dup"), name("丙", "C", "taken")]
    )
    existing = [{"jp": "丁", "code": "taken", "en": "D", "notes": ""}]
    review = make([page(entries)], {}, data, keywords=existing)
    by = {k.jp: k for k in review.keywords}
    assert by["甲"].code == "" and by["甲"].code_conflict == "dup"
    assert by["丙"].code == "" and by["丙"].code_conflict == "taken"
    assert by["甲"].en == "A"
    assert "code conflict: dup" in render_markdown(review)


def test_rarity_table_matches_batspi_by_letter_and_jp() -> None:
    def rarity_printing(number: str, rarity: str) -> dict[str, Any]:
        return {
            "number": number,
            "product_code": None,
            "product_name_jp": "x",
            "product_type_code": None,
            "rarity_jp": rarity,
        }

    printings = [
        rarity_printing(n, r) for n, r in (("a", "R"), ("b", "R"), ("c", "Xレア"), ("d", "謎"))
    ]
    pages = [page([], printings)]
    data = FandomData(
        rarities=[
            FandomRarity("レア", "Rare", "R"),
            FandomRarity("Xレア", "X-Rare", "X"),
            FandomRarity("コモン", "Common", "C"),
        ]
    )
    review = make(pages, {}, data)
    rows = {r.en: r for r in review.rarities}
    assert rows["Rare"].batspi == ("R",) and rows["Rare"].printings == 2
    assert rows["X-Rare"].batspi == ("Xレア",)
    assert rows["Common"].batspi == ()
    assert review.rarities[-1].batspi == ("謎",) and review.rarities[-1].fandom_jp == ""
    markdown = render_markdown(review)
    assert "## Rarities (4)" in markdown
    assert "| レア | R | Rare | R | 2 |" in markdown
    assert "Family names by source:" in markdown


def test_names_file_roundtrip(tmp_path: Path) -> None:
    data = FandomData(
        families=[name("甲", "A", "kou")],
        keywords=[name("乙", "B", None)],
        rarities=[FandomRarity("レア", "Rare", None)],
        unmatched_families=["X"],
        unmatched_keywords=["AFO"],
        requests_made=4,
    )
    path = tmp_path / "out" / "fandom_names.json"
    write_names(path, data)
    assert load_names(path) == data


@pytest.mark.parametrize("text", ["not json", "{}", '{"families": 1}'])
def test_names_file_errors(tmp_path: Path, text: str) -> None:
    path = tmp_path / "f.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ReviewError):
        load_names(path)
    with pytest.raises(ReviewError):
        load_names(tmp_path / "missing.json")


def test_cli_review_with_fandom(data_dir: Path, tmp_path: Path) -> None:  # noqa: F811
    from typer.testing import CliRunner

    from bs_database.cli import app
    from bs_database.review.source import iter_pages

    page_ = next(iter_pages(data_dir / "normalized"))
    number = page_["entries"][0]["number"]
    jp = page_["entries"][0]["gameplay"]["families"][0]["jp"]
    legacy = make_legacy(tmp_path / "legacy.db", {number: ["Legacy"]})
    names = tmp_path / "fandom_names.json"
    write_names(names, FandomData(families=[name(jp, "From Fandom", "furomu")]))
    runner = CliRunner()
    result = runner.invoke(
        app, ["glossary", "review", "--legacy-db", str(legacy), "--fandom", str(names)]
    )
    assert result.exit_code == 0, result.output
    assert "Family names by source:" in result.output
    text = (data_dir / "review" / "review.md").read_text(encoding="utf-8")
    assert "From Fandom" in text
    bad = runner.invoke(
        app,
        ["glossary", "review", "--legacy-db", str(legacy), "--fandom", str(tmp_path / "no.json")],
    )
    assert bad.exit_code == 1
    assert "cannot read fandom names" in bad.output
