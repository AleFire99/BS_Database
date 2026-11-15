"""The normalize report: content, determinism and renderers (#95)."""

import json
from pathlib import Path
from typing import Any

from fakes import FakeEngine
from golden_support import card_fixture_names, real_glossary, write_parsed_fixture

from bs_database.normalize.pipeline import TreeResult, normalize_tree
from bs_database.normalize.report import (
    REPORT_JSON,
    REPORT_MD,
    build_report,
    render_json,
    render_markdown,
    write_report,
)
from bs_database.translate import NullTranslator
from bs_database.translate.cache import TranslationCache
from bs_database.translate.cached import CachedTranslator


def _fixture_run(
    tmp_path: Path, *, engine: FakeEngine | None = None
) -> tuple[TreeResult, dict[str, Any]]:
    parsed = tmp_path / "parsed"
    for name in card_fixture_names():
        write_parsed_fixture(parsed, name)
    translator = (
        CachedTranslator(engine, TranslationCache(tmp_path / "t.sqlite"))
        if engine is not None
        else NullTranslator()
    )
    result = normalize_tree(parsed, tmp_path / "normalized", real_glossary(), translator)
    return result, build_report(result, translator.name, parsed)


def test_fixture_report_has_uncurated_families_and_nothing_unmapped(tmp_path: Path) -> None:
    result, report = _fixture_run(tmp_path)
    assert report["engine"] == "null"
    assert report["pages"] == {"written": result.written, "failed": []}
    assert report["unmapped"] == {"closed": [], "warnings": []}
    uncurated = report["uncurated"]
    assert len(uncurated) == 15
    assert {t["kind"] for t in uncurated} == {"families"}
    assert uncurated == sorted(uncurated, key=lambda t: (t["kind"], t["jp"]))
    for term in uncurated:
        assert term["pages"] >= 1
        assert term["samples"] == sorted(term["samples"])
        assert len(term["samples"]) <= 5


def test_translation_counts_with_null_and_fake_engine(tmp_path: Path) -> None:
    _, offline = _fixture_run(tmp_path / "a")
    for c in offline["translation"].values():
        assert c["machine"] == 0
        assert c["failed"] == 0
        assert c["pending"] == c["distinct"] - c["from_glossary_or_batspi"]
    _, online = _fixture_run(tmp_path / "b", engine=FakeEngine())
    assert online["engine"] == "fake"
    for c in online["translation"].values():
        assert c["pending"] == 0
        assert c["machine"] == c["distinct"] - c["from_glossary_or_batspi"]
    assert online["translation"]["names"]["machine"] > 0


def test_unmapped_and_failed_pages_are_reported(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed"
    bad = write_parsed_fixture(parsed, "card_magic.html")
    document = json.loads(bad.read_text(encoding="utf-8"))
    document["page"]["entries"][0]["gameplay"]["card_type"] = "謎のタイプ"
    bad.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    result = normalize_tree(parsed, tmp_path / "out", real_glossary(), NullTranslator())
    report = build_report(result, "null", parsed)
    assert report["pages"]["failed"] == [f"batspi/{bad.name}"]
    (term,) = report["unmapped"]["closed"]
    assert (term["kind"], term["jp"], term["pages"]) == ("card_types", "謎のタイプ", 1)
    assert report["unmapped"]["warnings"] == []


def test_report_files_are_deterministic_and_outside_the_page_glob(tmp_path: Path) -> None:
    _, first = _fixture_run(tmp_path / "a")
    _, second = _fixture_run(tmp_path / "b")
    assert render_json(first) == render_json(second)
    assert render_markdown(first) == render_markdown(second)
    out = tmp_path / "a" / "normalized"
    write_report(out, first)
    assert (out / REPORT_JSON).read_text(encoding="utf-8") == render_json(first)
    assert (out / REPORT_MD).read_text(encoding="utf-8") == render_markdown(first)
    assert not list(out.glob("*/_report*"))
    assert json.loads(render_json(first)) == first


def test_markdown_lists_sections_and_empty_state(tmp_path: Path) -> None:
    _, report = _fixture_run(tmp_path)
    text = render_markdown(report)
    assert text.startswith("# Normalize report\n")
    assert "## Unmapped, closed (errors) (0)\n\nNone." in text
    assert "## Uncurated (glossary row without a code) (15)" in text
    assert "| names | " in text
    assert "## Failed pages" not in text


def test_markdown_lists_failed_pages() -> None:
    report = {
        "schema_version": "1.0.0",
        "engine": "null",
        "pages": {"written": 0, "failed": ["batspi/x.json"]},
        "unmapped": {"closed": [], "warnings": []},
        "uncurated": [],
        "translation": {
            c: {
                "distinct": 0,
                "from_glossary_or_batspi": 0,
                "machine": 0,
                "pending": 0,
                "failed": 0,
            }
            for c in ("families", "names", "products")
        },
    }
    assert "- `batspi/x.json`" in render_markdown(report)


def test_second_run_report_is_byte_equal_and_makes_no_engine_calls(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed"
    for name in card_fixture_names():
        write_parsed_fixture(parsed, name)
    engine = FakeEngine()
    cache = TranslationCache(tmp_path / "t.sqlite")
    texts = []
    for run in ("one", "two"):
        translator = CachedTranslator(engine, cache)
        result = normalize_tree(parsed, tmp_path / run, real_glossary(), translator)
        report = build_report(result, translator.name, parsed)
        write_report(tmp_path / run, report)
        texts.append((tmp_path / run / REPORT_JSON).read_text(encoding="utf-8"))
        if run == "one":
            assert engine.calls
            engine.calls.clear()
    assert engine.calls == []
    assert texts[0] == texts[1]
