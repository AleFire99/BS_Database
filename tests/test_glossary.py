from pathlib import Path

import pytest

from bs_database.glossary import (
    FamilyEntry,
    GlossaryError,
    RarityEntry,
    SymbolEntry,
    load_glossary,
)

H = "jp,code,en,notes"
MINIMAL: dict[str, str] = {
    "colors": f"{H}\n青,blue,Blue,\n赤,red,Red,\n",
    "symbols": f"{H}\n神,god,God,\n赤,red,Red,\n",
    "card_types": f"{H}\nスピリット,spirit,Spirit,\n",
    "rarities": f"{H},sort_order\nC,C,Common,,1\nR,R,Rare,,2\n",
    "variants": f"{H}\n,normal,Normal,\nSECRETあり,secret,Secret,\n",
    "product_types": f"{H}\n,booster,Booster,\n,starter,Starter,\n",
    "keywords": f"{H}\n激突,clash,,\nミラージュ,mirage,Mirage,\n",
    "families": f"{H},aliases_en,no_split\nA・B,,,,,1\n爬獣,,Reptile Beast,,Rep,\n",
    "family_legacy_en": (
        "legacy_en,preferred_en,jp,notes\nRebirth,Reptile Beast,爬獣,\nSky,Fang,,\n"
    ),
    "product_code_prefixes": "prefix,code,notes\nBS,booster,\nBSC,starter,\n",
    "product_name_keywords": "keyword,code,notes\nパック,booster,\nブースターパック,starter,\n",
}


def make(tmp_path: Path, **overrides: str | bytes) -> Path:
    files: dict[str, str | bytes] = {**MINIMAL, **overrides}
    for kind, content in files.items():
        path = tmp_path / f"{kind}.csv"
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="")
    return tmp_path


def errors_of(tmp_path: Path, **overrides: str | bytes) -> list[str]:
    with pytest.raises(GlossaryError) as info:
        load_glossary(make(tmp_path, **overrides))
    return list(info.value.violations)


def test_minimal_set_loads(tmp_path: Path) -> None:
    g = load_glossary(make(tmp_path))
    red = g.lookup("symbols", "赤")
    assert isinstance(red, SymbolEntry)
    assert red.color_code == "red"
    god = g.lookup("symbols", "神")
    assert isinstance(god, SymbolEntry)
    assert god.color_code is None
    rarity = g.lookup("rarities", "R")
    assert isinstance(rarity, RarityEntry)
    assert rarity.sort_order == 2
    family = g.lookup("families", "爬獣")
    assert isinstance(family, FamilyEntry)
    assert family.aliases_en == ("Rep", "Rebirth")
    assert g.lookup("families", "A・B") == FamilyEntry("A・B", "", "", "", (), True)
    assert g.lookup("colors", "missing") is None
    assert g.lookup("nope", "赤") is None
    assert [a.legacy_en for a in g.unresolved_legacy()] == ["Sky"]


def test_rule1_missing_file(tmp_path: Path) -> None:
    make(tmp_path)
    (tmp_path / "colors.csv").unlink()
    with pytest.raises(GlossaryError, match=r"colors.csv:0: missing file"):
        load_glossary(tmp_path)


@pytest.mark.parametrize("header", ["jp,code,en", "jp,code,en,notes,extra", "code,jp,en,notes"])
def test_rule1_bad_columns(tmp_path: Path, header: str) -> None:
    assert any("colors.csv:1: header" in e for e in errors_of(tmp_path, colors=header + "\n"))


def test_rule1_wrong_cell_count(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, colors=f"{H}\n赤,red\n")
    assert "colors.csv:2: expected 4 columns, got 2" in errs


def test_rule2_not_utf8(tmp_path: Path) -> None:
    assert "colors.csv:0: not valid UTF-8" in errors_of(tmp_path, colors=b"\xff\xfe\x00")


def test_rule3_duplicate_jp(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, colors=f"{H}\n赤,a,A,\n赤,b,B,\n")
    assert "colors.csv:3: duplicate jp '赤'" in errs


def test_rule4_duplicate_code(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, colors=f"{H}\n赤,a,A,\n青,a,B,\n")
    assert "colors.csv:3: duplicate code 'a'" in errs


def test_rule5_empty_code(tmp_path: Path) -> None:
    assert "keywords.csv:2: empty code" in errors_of(tmp_path, keywords=f"{H}\n激突,,x,\n")


def test_rule5_families_may_have_empty_code(tmp_path: Path) -> None:
    load_glossary(make(tmp_path))


def test_rule6_empty_jp(tmp_path: Path) -> None:
    assert "colors.csv:2: empty jp" in errors_of(tmp_path, colors=f"{H}\n,red,Red,\n")


def test_rule6_variants_and_product_types_may_have_empty_jp(tmp_path: Path) -> None:
    load_glossary(make(tmp_path))


def test_rule7_empty_en_on_closed_kind(tmp_path: Path) -> None:
    assert "colors.csv:2: empty en" in errors_of(tmp_path, colors=f"{H}\n赤,red,,\n")


def test_rule8_unsorted(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, colors=f"{H}\n赤,red,Red,\n青,blue,Blue,\n")
    assert "colors.csv:3: rows not sorted by code" in errs


def test_rule8_families_sorted_by_code_then_jp(tmp_path: Path) -> None:
    bad = f"{H},aliases_en,no_split\nB,,,,,\nA,,,,,\n"
    assert "families.csv:3: rows not sorted by code" in errors_of(tmp_path, families=bad)


@pytest.mark.parametrize("cell", [" 赤", "赤 ", "赤\t"])
def test_rule9_whitespace(tmp_path: Path, cell: str) -> None:
    errs = errors_of(tmp_path, colors=f'{H}\n"{cell}",red,Red,\n')
    assert "colors.csv:2: leading or trailing whitespace" in errs


def test_rule10_bad_no_split_value(tmp_path: Path) -> None:
    bad = f"{H},aliases_en,no_split\nA・B,,,,,2\n"
    assert "families.csv:2: no_split must be empty, 0 or 1" in errors_of(tmp_path, families=bad)


def test_rule10_no_split_without_separator(tmp_path: Path) -> None:
    bad = f"{H},aliases_en,no_split\nAB,,,,,1\n"
    assert "families.csv:2: no_split=1 needs ・ in jp" in errors_of(tmp_path, families=bad)


def test_rule11_legacy_duplicate_case_insensitive(tmp_path: Path) -> None:
    bad = "legacy_en,preferred_en,jp,notes\nSky,Fang,,\nSKY,Fang,,\n"
    errs = errors_of(tmp_path, family_legacy_en=bad)
    assert "family_legacy_en.csv:3: duplicate legacy_en 'SKY'" in errs


def test_rule11_legacy_empty_preferred(tmp_path: Path) -> None:
    bad = "legacy_en,preferred_en,jp,notes\nSky,,,\n"
    assert "family_legacy_en.csv:2: empty preferred_en" in errors_of(tmp_path, family_legacy_en=bad)


def test_rule11_legacy_unknown_jp(tmp_path: Path) -> None:
    bad = "legacy_en,preferred_en,jp,notes\nSky,Fang,竜,\n"
    errs = errors_of(tmp_path, family_legacy_en=bad)
    assert "family_legacy_en.csv:2: jp '竜' not in families.csv" in errs


@pytest.mark.parametrize("order", ["x", ""])
def test_rule12_sort_order_not_integer(tmp_path: Path, order: str) -> None:
    errs = errors_of(tmp_path, rarities=f"{H},sort_order\nC,C,Common,,{order}\n")
    assert "rarities.csv:2: sort_order must be a unique integer" in errs


def test_rule12_sort_order_duplicate(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, rarities=f"{H},sort_order\nC,C,Common,,1\nR,R,Rare,,1\n")
    assert "rarities.csv:3: sort_order must be a unique integer" in errs


def test_all_violations_reported_once(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, colors=f"{H}\n赤,red,,\n", card_types=f"{H}\n,spirit,S,\n")
    assert len(errs) == 2


def test_blank_lines_ignored(tmp_path: Path) -> None:
    load_glossary(make(tmp_path, colors=f"{H}\n青,blue,Blue,\n\n赤,red,Red,\n"))


def test_closed_kind_needs_a_row(tmp_path: Path) -> None:
    assert "card_types.csv: a closed kind needs at least one row" in errors_of(
        tmp_path, card_types=f"{H}\n"
    )


def test_open_kind_may_be_empty(tmp_path: Path) -> None:
    g = load_glossary(make(tmp_path, keywords=f"{H}\n"))
    assert g.entries["keywords"] == ()


def test_entries_are_read_only(tmp_path: Path) -> None:
    g = load_glossary(make(tmp_path))
    with pytest.raises(TypeError):
        g.entries["colors"] = ()  # type: ignore[index]
    assert g.lookup("colors", "赤") is not None


PH = "prefix,code,notes"


def test_prefix_longest_match_wins(tmp_path: Path) -> None:
    g = load_glossary(make(tmp_path))
    assert g.product_type_for_code("BSC01") == "starter"
    assert g.product_type_for_code("BS01") == "booster"
    assert g.product_type_for_code("XX01") is None
    assert g.product_type_for_code(None) is None
    assert g.product_type_for_code("") is None


def test_prefix_file_may_be_empty(tmp_path: Path) -> None:
    g = load_glossary(make(tmp_path, product_code_prefixes=f"{PH}\n"))
    assert g.product_prefixes == ()


def test_prefix_unknown_type(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, product_code_prefixes=f"{PH}\nBS,nope,\n")
    assert "product_code_prefixes.csv:2: unknown product type 'nope'" in errs


def test_prefix_duplicate_and_empty(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, product_code_prefixes=f"{PH}\n,booster,\nBS,booster,\nBS,booster,\n")
    assert "product_code_prefixes.csv:2: empty prefix" in errs
    assert "product_code_prefixes.csv:4: duplicate prefix 'BS'" in errs


def test_prefix_unsorted(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, product_code_prefixes=f"{PH}\nSD,booster,\nBS,booster,\n")
    assert "product_code_prefixes.csv:3: rows not sorted by prefix" in errs


def test_prefix_bad_header(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, product_code_prefixes="code,prefix,notes\n")
    assert any("product_code_prefixes.csv:1: header" in e for e in errs)


KH = "keyword,code,notes"


def test_keyword_longest_match_wins(tmp_path: Path) -> None:
    g = load_glossary(make(tmp_path))
    assert g.product_type_for_name("ABCパック") == "booster"
    assert g.product_type_for_name("ブースターパック") == "starter"
    assert g.product_type_for_name("ABC") is None
    assert g.product_type_for_name(None) is None
    assert g.product_type_for_name("") is None


def test_keyword_matches_after_nfkc(tmp_path: Path) -> None:
    g = load_glossary(make(tmp_path, product_name_keywords=f"{KH}\nMAX,booster,\n"))
    assert g.product_type_for_name("ＭＡＸ大会") == "booster"
    assert g.product_type_for_name("max") is None


def test_keyword_file_may_be_empty(tmp_path: Path) -> None:
    g = load_glossary(make(tmp_path, product_name_keywords=f"{KH}\n"))
    assert g.product_keywords == ()


def test_keyword_unknown_type(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, product_name_keywords=f"{KH}\nパック,nope,\n")
    assert "product_name_keywords.csv:2: unknown product type 'nope'" in errs


def test_keyword_duplicate_and_empty(tmp_path: Path) -> None:
    errs = errors_of(
        tmp_path, product_name_keywords=f"{KH}\n,booster,\nパック,booster,\nパック,booster,\n"
    )
    assert "product_name_keywords.csv:2: empty keyword" in errs
    assert "product_name_keywords.csv:4: duplicate keyword 'パック'" in errs


def test_keyword_unsorted(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, product_name_keywords=f"{KH}\nパック,booster,\nBOX,booster,\n")
    assert "product_name_keywords.csv:3: rows not sorted by keyword" in errs


def test_keyword_bad_header(tmp_path: Path) -> None:
    errs = errors_of(tmp_path, product_name_keywords="code,keyword,notes\n")
    assert any("product_name_keywords.csv:1: header" in e for e in errs)
