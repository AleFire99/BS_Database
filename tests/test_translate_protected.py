import logging
import random
from pathlib import Path

import pytest
from fakes import ScriptedEngine

from bs_database.glossary import Entry, Glossary
from bs_database.translate.protect import GlossaryResolver
from bs_database.translate.protected import PROTECTION_VERSION, ProtectedTranslator

GLYPHS = ["赤", "青"]


def _resolver() -> GlossaryResolver:
    g = Glossary(
        entries={
            "keywords": (Entry("ダブルシンボル", "ds", "Double Symbol", ""),),
            "symbols": (Entry("赤", "red", "Red", ""), Entry("青", "blue", "Blue", "")),
        },
        legacy_family_aliases=(),
    )
    return GlossaryResolver(g, card_names={"ミカド": "Mikado"})


def _make(engine: ScriptedEngine, *, retry: bool = True) -> ProtectedTranslator:
    return ProtectedTranslator(engine, _resolver(), GLYPHS, retry=retry)


def test_name_and_pair_check() -> None:
    t = _make(ScriptedEngine())
    assert t.name == f"scripted+prot{PROTECTION_VERSION}" == "scripted+prot1"
    with pytest.raises(ValueError, match="unsupported"):
        t.translate(["a"], src="jp", tgt="jp")


def test_multi_line_field_is_one_engine_call_and_rejoined() -> None:
    e = ScriptedEngine({"<k0/>を持つ": "Has <k0/>", "二行目": "Second line"})
    out = _make(e).translate(["【ダブルシンボル】を持つ\n二行目", "二行目"])
    assert e.calls == [["<k0/>を持つ", "二行目", "二行目"]]
    assert [(r.text, r.status, r.engine) for r in out] == [
        ("Has 【Double Symbol】\nSecond line", "machine", "scripted+prot1"),
        ("Second line", "machine", "scripted+prot1"),
    ]


def test_blank_texts_are_pending_and_never_sent() -> None:
    e = ScriptedEngine()
    out = _make(e).translate(["", "  \n ", "あ"])
    assert [r.status for r in out] == ["pending", "pending", "machine"]
    assert e.calls == [["あ"]]
    assert _make(e).translate([""])[0].status == "pending"
    assert e.calls == [["あ"]]  # nothing sent for an all-blank call


def test_blank_inner_line_is_kept() -> None:
    e = ScriptedEngine({"あ": "A", "い": "B"})
    assert _make(e).translate(["あ\n\nい"])[0].text == "A\n\nB"


def test_bad_line_fails_the_whole_field() -> None:
    e = ScriptedEngine({"<k0/>あ": "lost the token", "い": "fine"})
    out = _make(e).translate(["【ダブルシンボル】あ\nい", "い"])
    assert (out[0].text, out[0].status) == (None, "failed")
    assert out[1].text == "fine"
    assert len(e.calls) == 1  # single sentence: nothing to retry, no second call


def test_retry_splits_on_the_sentence_stop() -> None:
    e = ScriptedEngine(
        {
            "<k0/>を得る。<k1/>が出る。": "garbled <k0",
            "<k0/>を得る。": "Gain <k0/>.",
            "<k0/>が出る。": "<k0/> appears.",
        }
    )
    out = _make(e).translate(["【ダブルシンボル】を得る。「ミカド」が出る。"])
    assert e.calls[1] == ["<k0/>を得る。", "<k0/>が出る。"]
    assert out[0].text == "Gain 【Double Symbol】. 「Mikado」 appears."
    assert out[0].status == "machine"


def test_retry_that_still_fails_fails_the_field() -> None:
    e = ScriptedEngine({"<k0/>あ。い。": "x", "<k0/>あ。": "x", "い。": "ok."})
    out = _make(e).translate(["【ダブルシンボル】あ。い。"])
    assert out[0].status == "failed"
    assert len(e.calls) == 2


def test_retry_can_be_off() -> None:
    e = ScriptedEngine({"あ。い。": None})
    assert _make(e, retry=False).translate(["あ。い。"])[0].status == "failed"
    assert len(e.calls) == 1


def test_engine_failure_is_failed_and_retried_by_sentence() -> None:
    e = ScriptedEngine({"あ。い。": None, "あ。": "A.", "い。": "B."})
    assert _make(e).translate(["あ。い。"])[0].text == "A. B."
    assert _make(ScriptedEngine({"あ": None})).translate(["あ"])[0].status == "failed"


def test_engine_pending_gives_pending_without_retry() -> None:
    e = ScriptedEngine(pending=frozenset({"あ。い。"}))
    assert _make(e).translate(["あ。い。"])[0].status == "pending"
    assert len(e.calls) == 1


def test_pending_sentence_after_retry_gives_pending() -> None:
    e = ScriptedEngine({"あ。い。": None}, pending=frozenset({"い。"}))
    assert _make(e).translate(["あ。い。"])[0].status == "pending"


def test_failed_beats_pending_in_a_field() -> None:
    e = ScriptedEngine({"あ": None}, pending=frozenset({"い"}))
    assert _make(e).translate(["あ\nい"])[0].status == "failed"


def test_order_and_length_are_preserved_and_unresolved_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    e = ScriptedEngine()
    texts = ["あ", "", "【未知】い", "赤青う", "え"]
    with caplog.at_level(logging.INFO):
        out = _make(e).translate(texts)
    assert [r.text for r in out] == ["あ", None, "【未知】い", "Red Blueう", "え"]
    assert "unresolved=1" in caplog.text


def test_cache_below_protection(tmp_path: Path) -> None:
    from bs_database.translate.cache import TranslationCache
    from bs_database.translate.cached import CachedTranslator

    e = ScriptedEngine({"<k0/>を得る": "Gain <k0/>"})
    cache = TranslationCache(tmp_path / "c.sqlite")
    t = ProtectedTranslator(CachedTranslator(e, cache), _resolver(), GLYPHS)
    first = t.translate(["【ダブルシンボル】を得る"])
    assert first[0].text == "Gain 【Double Symbol】"
    assert first[0].engine == "scripted+prot1"
    assert len(e.calls) == 1
    # a glossary edit applies without an engine call
    g = Glossary(
        entries={"keywords": (Entry("ダブルシンボル", "ds", "Twin Symbol", ""),)},
        legacy_family_aliases=(),
    )
    t2 = ProtectedTranslator(CachedTranslator(e, cache), GlossaryResolver(g), GLYPHS)
    assert t2.translate(["【ダブルシンボル】を得る"])[0].text == "Gain 【Twin Symbol】"
    assert len(e.calls) == 1
    # a different masking rule (no glyph run) changes the masked text: cache miss
    t3 = ProtectedTranslator(CachedTranslator(e, cache), _resolver(), [])
    t3.translate(["【ダブルシンボル】を得る赤青"])
    assert len(e.calls) == 2


def test_round_trip_property() -> None:
    rng = random.Random(156)
    spans = {
        "【ダブルシンボル】": "【Double Symbol】",
        "「ミカド」": "「Mikado」",
        "系統：": "Family:",
        "赤青": "Red Blue",
        "【未知】": "【未知】",
    }
    fillers = ["あ", "いう", "。", "abc", " "]
    cases = []
    for _ in range(500):
        parts: list[str] = []
        for _ in range(rng.randint(1, 8)):
            piece = rng.choice([*spans, *fillers])
            if piece == "赤青" and parts[-1:] == ["赤青"]:
                piece = "あ"  # two runs side by side would merge into one
            parts.append(piece)
        cases.append(("".join(parts), "".join(spans.get(p, p) for p in parts)))
    texts = [c[0] for c in cases]
    out = _make(ScriptedEngine()).translate(texts)  # the echo engine keeps the tokens
    for (src, expected), r in zip(cases, out, strict=True):
        if src.strip():
            assert (r.status, r.text) == ("machine", expected.strip() or expected), src


def test_golden_effect_text() -> None:
    src = (
        "【アタック時】赤青を支払う：「ミカド」を手札に加える。\n"
        "系統：「悪魔契約」を持つスピリット\n"
        "【ダブルシンボル】"
    )
    engine = ScriptedEngine(
        {
            "<k0/><k1/>を支払う：<k2/>を手札に加える。": "<k0/> Pay <k1/>: add <k2/> to your hand.",
            "<k0/><k1/>を持つスピリット": "A spirit with <k1/> <k0/>",
            "<k0/>": "<k0/>",
        }
    )
    out = _make(engine).translate([src])[0]
    assert out.text == (
        "【アタック時】 Pay Red Blue: add 「Mikado」 to your hand.\n"
        "A spirit with 「悪魔契約」 Family:\n"
        "【Double Symbol】"
    )
