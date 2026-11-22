"""Reader and card grouping of the build (#120, ADR 0004 amendment)."""

import json
import shutil
from pathlib import Path

import pytest
from golden_support import NORMALIZED_GOLDENS

from bs_database.build import BuildError
from bs_database.build.grouping import CardGroup, group_entries, grouping_key
from bs_database.build.reader import Document, read_documents


@pytest.fixture(scope="module")
def documents() -> list[Document]:
    return read_documents(NORMALIZED_GOLDENS)


def _numbers(groups: list[CardGroup], name: str) -> list[tuple[str, ...]]:
    return [g.numbers for g in groups if g.first.entry["name_jp"] == name]


def test_reads_all_goldens_sorted_by_url(documents: list[Document]) -> None:
    assert len(documents) == 32
    assert [d.url for d in documents] == sorted(d.url for d in documents)


def test_reports_and_other_majors(tmp_path: Path) -> None:
    src = NORMALIZED_GOLDENS / "card_magic.json"
    shutil.copy(src, tmp_path / "a.json")
    (tmp_path / "_report.json").write_text("{not even json", encoding="utf-8")
    assert len(read_documents(tmp_path)) == 1
    data = json.loads(src.read_text(encoding="utf-8"))
    data["schema_version"] = "2.0.0"
    (tmp_path / "b.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BuildError, match="major"):
        read_documents(tmp_path)


def test_broken_document_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    with pytest.raises(BuildError, match="not a normalized document"):
        read_documents(tmp_path)


def test_number_in_two_documents_is_an_error(tmp_path: Path) -> None:
    src = NORMALIZED_GOLDENS / "card_magic.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    (tmp_path / "a.json").write_text(json.dumps(data), encoding="utf-8")
    data["url"] = data["url"] + "&copy"
    (tmp_path / "b.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BuildError, match="in two documents"):
        read_documents(tmp_path)


def test_same_url_is_an_error(tmp_path: Path) -> None:
    src = NORMALIZED_GOLDENS / "card_magic.json"
    shutil.copy(src, tmp_path / "a.json")
    shutil.copy(src, tmp_path / "b.json")
    with pytest.raises(BuildError, match="url in two documents"):
        read_documents(tmp_path)


def test_fixture_cards_of_the_adr(documents: list[Document]) -> None:
    groups = group_entries(documents)
    assert _numbers(groups, "ゴラドン") == [("BS01-001",), ("BSC22-001",)]
    assert _numbers(groups, "ダブルドロー") == [("BS01-117",), ("BSC22-117",)]
    madou = _numbers(groups, "焔竜翼人マ・ドー")
    assert sorted(madou) == [("EX001", "P001"), ("P20-19",)]


def test_one_group_per_distinct_key(documents: list[Document]) -> None:
    groups = group_entries(documents)
    entries = [e for d in documents for e in d.entries]
    assert sum(len(g.members) for g in groups) == len(entries)
    assert len(groups) == len({grouping_key(e) for e in entries})
    assert [g.first.number for g in groups] == sorted(g.first.number for g in groups)


def test_order_of_documents_does_not_matter(documents: list[Document]) -> None:
    forward = [(g.key, g.numbers) for g in group_entries(documents)]
    backward = [(g.key, g.numbers) for g in group_entries(documents[::-1])]
    assert forward == backward


def test_credits_english_and_images_are_not_in_the_key(documents: list[Document]) -> None:
    entry = json.loads(json.dumps(documents[0].entries[0]))
    base = grouping_key(entry)
    entry["name_en"] = "changed"
    entry["text"]["illustrators"] = [{"name": "someone", "note": None}]
    entry["text"]["flavor_en"] = "x"
    assert grouping_key(entry) == base
    entry["text"]["flavor_jp"] = "different flavor"
    assert grouping_key(entry) != base


def test_merged_names_must_match(
    documents: list[Document], monkeypatch: pytest.MonkeyPatch
) -> None:
    import bs_database.build.grouping as grouping

    monkeypatch.setattr(grouping, "grouping_key", lambda entry: "same")
    with pytest.raises(BuildError, match="different names"):
        grouping.group_entries(documents)
