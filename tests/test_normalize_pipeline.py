"""normalize_page and the tree runner (#93)."""

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from fakes import FakeEngine
from golden_support import (
    card_fixture_names,
    parse_fixture,
    real_glossary,
    uncurated_glossary,
    write_parsed_fixture,
)

from bs_database.normalize.pipeline import normalize_page, normalize_tree
from bs_database.translate import NullTranslator
from bs_database.translate.cache import TranslationCache
from bs_database.translate.cached import CachedTranslator
from bs_database.translate.types import Lang, TranslationResult


def _cache(tmp_path: Path) -> TranslationCache:
    return TranslationCache(tmp_path / "translations.sqlite")


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize("name", card_fixture_names())
def test_fixtures_have_no_closed_unmapped_terms(name: str) -> None:
    result = normalize_page(parse_fixture(name), real_glossary())
    assert [t for t in result.unmapped if t.closed] == []


def test_normalize_page_is_deterministic() -> None:
    page = parse_fixture("card_flip.html")
    assert normalize_page(page, real_glossary()) == normalize_page(page, real_glossary())


def test_codes_and_name_fields() -> None:
    result = normalize_page(parse_fixture("card_spirit_bs01.html"), real_glossary())
    first = result.entries[0]
    assert first.name_en == "Goradon"
    assert (first.en_source, first.en_status) == ("batspi", "reviewed")
    assert first.gameplay.card_type_code == "spirit"
    assert [c.code for c in first.gameplay.colors] == ["red"]
    assert [f.code for f in first.gameplay.families] == ["reptile_beast"]
    assert first.gameplay.families[0].en_source == "manual"
    assert {p.rarity_code for p in result.printings} == {"C"}


def test_pending_when_no_batspi_name() -> None:
    result = normalize_page(parse_fixture("card_spirit.html"), real_glossary())
    entry = result.entries[0]
    assert (entry.name_en, entry.en_source, entry.en_status) == (None, None, "pending")
    assert result.printings[0].variant_code == "secret"
    assert result.printings[0].product_name_en is None


def test_uncurated_families_are_listed_apart_and_sorted() -> None:
    result = normalize_page(parse_fixture("card_flip.html"), uncurated_glossary())
    assert result.unmapped == ()
    assert result.uncurated
    assert all(t.kind in ("families", "keywords") for t in result.uncurated)
    assert list(result.uncurated) == sorted(
        set(result.uncurated), key=lambda t: (t.kind, t.jp, t.number)
    )


def test_product_type_marker_and_no_marker() -> None:
    result = normalize_page(parse_fixture("card_promo.html"), real_glossary())
    by_name = {p.product_name_jp: p.product_type_code for p in result.printings}
    assert by_name["プロモーションカード"] == "promo"
    assert by_name["バトスピショップバトル"] is None


def test_tree_writes_same_stem_and_is_idempotent(tmp_path: Path) -> None:
    parsed, out = tmp_path / "parsed", tmp_path / "normalized"
    sources = [write_parsed_fixture(parsed, n) for n in ("card_spirit.html", "card_flip.html")]
    first = normalize_tree(parsed, out, real_glossary(), NullTranslator())
    assert (first.written, first.failed) == (2, ())
    for src in sources:
        target = out / "batspi" / src.name
        document = json.loads(target.read_text(encoding="utf-8"))
        assert document["schema_version"] == "1.1.0"
        assert document["parsed_schema_version"] == "2.1.0"
        assert document["provenance"]["source"] == "batspi"
    snapshot = _hash_tree(out)
    normalize_tree(parsed, out, real_glossary(), NullTranslator())
    assert _hash_tree(out) == snapshot


def test_tree_leaves_parsed_unchanged(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed"
    write_parsed_fixture(parsed, "card_spirit.html")
    before = _hash_tree(parsed)
    normalize_tree(parsed, tmp_path / "normalized", real_glossary(), NullTranslator())
    assert _hash_tree(parsed) == before


def test_closed_unmapped_term_fails_the_page_but_not_the_run(tmp_path: Path) -> None:
    parsed, out = tmp_path / "parsed", tmp_path / "normalized"
    good = write_parsed_fixture(parsed, "card_spirit.html")
    bad = write_parsed_fixture(parsed, "card_magic.html")
    document = json.loads(bad.read_text(encoding="utf-8"))
    document["page"]["entries"][0]["gameplay"]["card_type"] = "謎のタイプ"
    bad.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    result = normalize_tree(parsed, out, real_glossary(), NullTranslator())
    assert (result.written, result.failed) == (1, (bad,))
    assert result.closed == 1
    assert (out / "batspi" / good.name).is_file()
    assert not (out / "batspi" / bad.name).exists()


def _break_schema(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    document["schema_version"] = "1.0.0"
    path.write_text(json.dumps(document), encoding="utf-8")


def _break_page_schema(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    document["page"]["schema_version"] = "1.0.0"
    path.write_text(json.dumps(document), encoding="utf-8")


def _break_json(path: Path) -> None:
    path.write_text("{not json", encoding="utf-8")


def _drop_key(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    del document["page"]["entries"]
    path.write_text(json.dumps(document), encoding="utf-8")


def _make_directory(path: Path) -> None:
    path.unlink()
    path.mkdir()


@pytest.mark.parametrize(
    "breaker", [_break_schema, _break_page_schema, _break_json, _drop_key, _make_directory]
)
def test_unreadable_parsed_file_is_counted_failed(
    tmp_path: Path, breaker: Callable[[Path], None]
) -> None:
    parsed = tmp_path / "parsed"
    path = write_parsed_fixture(parsed, "card_spirit.html")
    breaker(path)
    result = normalize_tree(parsed, tmp_path / "normalized", real_glossary(), NullTranslator())
    assert (result.written, result.failed) == (0, (path,))


def test_empty_tree(tmp_path: Path) -> None:
    result = normalize_tree(tmp_path / "none", tmp_path / "out", real_glossary(), NullTranslator())
    assert (result.written, result.failed, result.unmapped) == (0, (), ())


def _written(out: Path) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(out.rglob("*.json"))}


def test_tree_translates_names_families_and_products(tmp_path: Path) -> None:
    parsed, out = tmp_path / "parsed", tmp_path / "normalized"
    write_parsed_fixture(parsed, "card_flip.html")
    engine = FakeEngine()
    result = normalize_tree(
        parsed, out, real_glossary(), CachedTranslator(engine, _cache(tmp_path))
    )
    (document,) = (json.loads(t) for t in _written(out).values())
    page = document["page"]
    first = page["entries"][0]
    assert (first["name_en"], first["en_status"]) == (f"<{first['name_jp']}>", "machine")
    assert page["printings"][0]["product_en_source"] == "machine"
    assert len(engine.calls) == 1
    assert engine.calls[0] == result.requests.ordered()
    assert {r.status for r in result.translations.values()} == {"machine"}


def test_failed_page_sends_nothing_to_the_engine(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed"
    bad = write_parsed_fixture(parsed, "card_magic.html")
    document = json.loads(bad.read_text(encoding="utf-8"))
    document["page"]["entries"][0]["gameplay"]["card_type"] = "謎のタイプ"
    bad.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    engine = FakeEngine()
    result = normalize_tree(
        parsed, tmp_path / "out", real_glossary(), CachedTranslator(engine, _cache(tmp_path))
    )
    assert result.failed == (bad,)
    assert engine.calls == []


def test_null_translator_output_has_pending_status_and_no_text(tmp_path: Path) -> None:
    parsed, out = tmp_path / "parsed", tmp_path / "normalized"
    write_parsed_fixture(parsed, "card_spirit.html")
    normalize_tree(parsed, out, real_glossary(), NullTranslator())
    (document,) = (json.loads(t) for t in _written(out).values())
    entry = document["page"]["entries"][0]
    assert (entry["name_en"], entry["en_source"], entry["en_status"]) == (None, None, "pending")


def test_max_chars_zero_leaves_texts_pending(tmp_path: Path) -> None:
    parsed, out = tmp_path / "parsed", tmp_path / "normalized"
    write_parsed_fixture(parsed, "card_flip.html")
    engine = FakeEngine()
    translator = CachedTranslator(engine, _cache(tmp_path), max_chars=0)
    result = normalize_tree(parsed, out, real_glossary(), translator)
    assert engine.calls == []
    assert {r.status for r in result.translations.values()} == {"pending"}


def test_second_run_makes_no_engine_calls(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed"
    for name in card_fixture_names():
        write_parsed_fixture(parsed, name)
    engine = FakeEngine()
    cache = _cache(tmp_path)
    normalize_tree(parsed, tmp_path / "one", real_glossary(), CachedTranslator(engine, cache))
    assert engine.calls
    engine.calls.clear()
    normalize_tree(parsed, tmp_path / "two", real_glossary(), CachedTranslator(engine, cache))
    assert engine.calls == []
    assert _written(tmp_path / "one") == _written(tmp_path / "two")


class _RewritingTranslator:
    """Rewrites a parsed file during ``translate`` (between the two passes)."""

    name = "rewriter"

    def __init__(self, action: Callable[[], None]) -> None:
        self.action = action

    def translate(
        self, texts: Sequence[str], *, src: Lang = "jp", tgt: Lang = "en"
    ) -> list[TranslationResult]:
        self.action()
        return [TranslationResult(None, "pending", self.name) for _ in texts]


def test_page_that_gains_a_closed_term_between_passes_is_failed(tmp_path: Path) -> None:
    parsed, out = tmp_path / "parsed", tmp_path / "normalized"
    path = write_parsed_fixture(parsed, "card_magic.html")

    def corrupt() -> None:
        document = json.loads(path.read_text(encoding="utf-8"))
        document["page"]["entries"][0]["gameplay"]["card_type"] = "謎のタイプ"
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    result = normalize_tree(parsed, out, real_glossary(), _RewritingTranslator(corrupt))
    assert (result.written, result.failed) == (0, (path,))
    assert not (out / "batspi" / path.name).exists()


def test_page_that_becomes_unreadable_between_passes_is_failed(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed"
    path = write_parsed_fixture(parsed, "card_magic.html")

    def break_file() -> None:
        path.write_text("{bad", encoding="utf-8")

    translator = _RewritingTranslator(break_file)
    result = normalize_tree(parsed, tmp_path / "normalized", real_glossary(), translator)
    assert (result.written, result.failed) == (0, (path,))


def test_same_text_as_family_and_name_is_translated_once_for_both(tmp_path: Path) -> None:
    parsed, out = tmp_path / "parsed", tmp_path / "normalized"
    path = write_parsed_fixture(parsed, "card_flip.html")
    document = json.loads(path.read_text(encoding="utf-8"))
    entry = document["page"]["entries"][0]
    family = entry["gameplay"]["families"][0]
    entry["name_jp"] = family
    entry["name_en"] = None
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    engine = FakeEngine()
    normalize_tree(parsed, out, uncurated_glossary(), CachedTranslator(engine, _cache(tmp_path)))
    assert engine.calls[0].count(family) == 1
    page = json.loads(next(out.rglob("*.json")).read_text(encoding="utf-8"))["page"]
    first = page["entries"][0]
    assert first["name_en"] == f"<{family}>"
    fams = {f["jp"]: f["en"] for f in first["gameplay"]["families"]}
    assert fams[family] == f"<{family}>"


def test_engine_receives_families_then_names_then_products_sorted(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed"
    for name in card_fixture_names():
        write_parsed_fixture(parsed, name)
    engine = FakeEngine()
    result = normalize_tree(
        parsed, tmp_path / "out", uncurated_glossary(), CachedTranslator(engine, _cache(tmp_path))
    )
    sent = [t for call in engine.calls for t in call]  # chunks of 50, in order
    r = result.requests
    assert r.families and r.names and r.products
    assert sent == [*r.families, *r.names, *r.products]
    for part in (r.families, r.names, r.products):
        assert list(part) == sorted(part)
