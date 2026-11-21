"""Mapping rules on a hand-built glossary (#93)."""

import pytest

from bs_database.glossary import (
    Entry,
    FamilyEntry,
    Glossary,
    ProductKeyword,
    ProductPrefix,
    RarityEntry,
)
from bs_database.normalize import rules
from bs_database.normalize.records import CodedTerm, UnmappedCollector, UnmappedTerm
from bs_database.parsers.card_models import Keyword, SymbolCount


def make_glossary() -> Glossary:
    return Glossary(
        {
            "colors": (Entry("赤", "red", "Red", ""),),
            "symbols": (Entry("神", "god", "God", ""),),
            "card_types": (Entry("スピリット", "spirit", "Spirit", ""),),
            "rarities": (RarityEntry("C", "C", "Common", "", 1),),
            "variants": (Entry("", "normal", "Normal", ""), Entry("SECRETあり", "secret", "S", "")),
            "product_types": (
                Entry("", "booster", "Booster", ""),
                Entry("コラボ", "collab", "Collab", ""),
                Entry("プロモーションカード", "promo", "Promo", ""),
            ),
            "keywords": (Entry("神託", "shintaku", "", ""), Entry("激突", "", "", "")),
            "families": (
                FamilyEntry("爬獣", "reptile_beast", "Reptile Beast", "", (), False),
                FamilyEntry("武迅", "", "", "", (), False),
                FamilyEntry("A・B", "a_b", "", "", (), True),
                FamilyEntry("A・B・C", "a_b_c", "", "", (), True),
            ),
        },
        (),
        (
            ProductPrefix("BS", "booster", ""),
            ProductPrefix("BSC", "starter", ""),
            ProductPrefix("SD", "starter", ""),
        ),
        (
            ProductKeyword("パック", "booster", ""),
            ProductKeyword("ブースターパック", "starter", ""),
            ProductKeyword("MAX", "promo", ""),
        ),
    )


G = make_glossary()


def test_closed_code_hit_and_miss() -> None:
    u = UnmappedCollector()
    assert rules.closed_code(G, "card_types", "スピリット", "N1", u) == "spirit"
    assert rules.closed_code(G, "card_types", "謎", "N1", u) is None
    assert u.terms() == (UnmappedTerm("card_types", "謎", "N1"),)


def test_map_colors() -> None:
    u = UnmappedCollector()
    assert rules.map_colors(G, ("赤", "?"), "N", u) == (
        CodedTerm("赤", "red"),
        CodedTerm("?", None),
    )
    assert [t.closed for t in u.terms()] == [True]


def test_map_symbols() -> None:
    u = UnmappedCollector()
    got = rules.map_symbols(G, (SymbolCount("神", 2), SymbolCount("?", 1)), "N", u)
    assert [(s.symbol_code, s.count) for s in got] == [("god", 2), (None, 1)]
    assert u.terms() == (UnmappedTerm("symbols", "?", "N"),)


def test_rarity_none_stays_none() -> None:
    u = UnmappedCollector()
    assert rules.rarity_code(G, None, "N", u) is None
    assert rules.rarity_code(G, "C", "N", u) == "C"
    assert u.terms() == ()


def test_unknown_rarity_is_a_closed_miss() -> None:
    u = UnmappedCollector()
    assert rules.rarity_code(G, "ZZ", "N", u) is None
    assert u.terms()[0].closed


def test_variant_miss_is_normal() -> None:
    assert rules.variant_code(G, None) == (None, "normal")
    assert rules.variant_code(G, "バシン 特別") == (None, "normal")
    assert rules.variant_code(G, "SECRETあり") == ("SECRETあり", "secret")


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("プロモーションカード", "promo"),
        ("ワンピースコラボ 第1弾", "collab"),
        ("第一弾", None),
    ],
)
def test_product_type_marker(name: str, code: str | None) -> None:
    assert rules.product_type_code(G, name) == code


@pytest.mark.parametrize(
    ("name", "product_code", "code"),
    [
        ("ワンピースコラボ スターター", "SD54", "collab"),
        ("第一弾", "BSC01", "starter"),
        ("第一弾", "BS01", "booster"),
        ("第一弾", "SD01", "starter"),
        ("第一弾", "XX01", None),
        ("第一弾", None, None),
    ],
)
def test_product_type_prefix_rule(name: str, product_code: str | None, code: str | None) -> None:
    assert rules.product_type_code(G, name, product_code) == code


@pytest.mark.parametrize(
    ("name", "product_code", "code"),
    [
        ("ABCパック", None, "booster"),
        ("ABCブースターパック", None, "starter"),
        ("ABCパック", "XX01", "booster"),
        ("ABCパック", "SD01", "starter"),
        ("ABCコラボパック", None, "collab"),
        ("ＭＡＸ杯", None, "promo"),
        ("ABC", None, None),
    ],
)
def test_product_type_name_keyword_rule(
    name: str, product_code: str | None, code: str | None
) -> None:
    assert rules.product_type_code(G, name, product_code) == code


def test_merge_family_tokens_rejoins_no_split() -> None:
    assert rules.merge_family_tokens(G, ("爬獣", "A", "B", "武迅")) == ("爬獣", "A・B", "武迅")


def test_merge_prefers_longest_and_dedupes() -> None:
    assert rules.merge_family_tokens(G, ("A", "B", "C")) == ("A・B・C",)
    assert rules.merge_family_tokens(G, ("武迅", "武迅", "A")) == ("武迅", "A")


def test_families_with_glossary_name_are_manual_reviewed() -> None:
    u = UnmappedCollector()
    (rec,) = rules.map_families(G, ("爬獣",), "N", u)
    assert (rec.code, rec.en, rec.en_source, rec.en_status) == (
        "reptile_beast",
        "Reptile Beast",
        "manual",
        "reviewed",
    )
    assert u.terms() == ()


def test_family_with_empty_code_is_uncurated_not_unmapped() -> None:
    u = UnmappedCollector()
    (rec,) = rules.map_families(G, ("武迅",), "N", u)
    assert (rec.code, rec.en, rec.en_source, rec.en_status) == (None, None, None, "pending")
    assert u.terms() == ()
    assert u.uncurated_terms() == (UnmappedTerm("families", "武迅", "N"),)


def test_unknown_family_is_a_warning() -> None:
    u = UnmappedCollector()
    (rec,) = rules.map_families(G, ("未知",), "N", u)
    assert rec.code is None
    assert u.terms() == (UnmappedTerm("families", "未知", "N"),)
    assert u.uncurated_terms() == ()
    assert not u.terms()[0].closed


def test_keywords_hit_and_miss() -> None:
    u = UnmappedCollector()
    got = rules.map_keywords(
        G,
        (Keyword("【", "神託", None), Keyword("【", "激突", None), Keyword("《", "新", "1")),
        "N",
        u,
    )
    assert [k.code for k in got] == ["shintaku", None, None]
    assert got[2].parameter_jp == "1"
    assert [t.jp for t in u.terms()] == ["新"]
    assert [t.jp for t in u.uncurated_terms()] == ["激突"]


def test_family_tokens_are_stripped_and_merged() -> None:
    u = UnmappedCollector()
    got = rules.map_families(G, ("爬獣 ", "爬獣", "　", " A", "B　"), "N", u)
    assert [r.jp for r in got] == ["爬獣", "A・B"]
    assert u.terms() == ()


def test_keyword_names_are_stripped() -> None:
    u = UnmappedCollector()
    got = rules.map_keywords(
        G, (Keyword("【", " 神託　", None), Keyword("【", "新 ", None)), "N", u
    )
    assert [(k.name_jp, k.code) for k in got] == [("神託", "shintaku"), ("新", None)]
    assert [t.jp for t in u.terms()] == ["新"]
