import logging
from pathlib import Path

import pytest
from fakes import FakeEngine

from bs_database.translate.cache import TranslationCache
from bs_database.translate.cached import CachedTranslator


def make(
    tmp_path: Path, max_chars: int | None = None, fail: frozenset[str] = frozenset()
) -> tuple[CachedTranslator, FakeEngine, TranslationCache]:
    engine = FakeEngine(fail)
    cache = TranslationCache(tmp_path / "t.sqlite")
    return CachedTranslator(engine, cache, max_chars=max_chars), engine, cache


def texts_of(results: list) -> list[str | None]:  # type: ignore[type-arg]
    return [r.text for r in results]


def test_cache_hit_makes_no_engine_call(tmp_path: Path) -> None:
    ct, engine, _ = make(tmp_path)
    assert texts_of(ct.translate(["あ"])) == ["<あ>"]
    assert len(engine.calls) == 1
    again = ct.translate(["あ"])
    assert len(engine.calls) == 1
    assert again[0].status == "machine" and again[0].engine == "fake"


def test_duplicates_sent_once_and_order_kept(tmp_path: Path) -> None:
    ct, engine, _ = make(tmp_path)
    ct.translate(["b"])
    out = ct.translate(["a", "b", "a", "c"])
    assert texts_of(out) == ["<a>", "<b>", "<a>", "<c>"]
    assert engine.calls[1] == ["a", "c"]


def test_blank_is_pending_without_call(tmp_path: Path) -> None:
    ct, engine, _ = make(tmp_path)
    out = ct.translate(["", "  "])
    assert [r.status for r in out] == ["pending", "pending"]
    assert engine.calls == []


def test_failed_not_cached(tmp_path: Path) -> None:
    ct, engine, cache = make(tmp_path, fail=frozenset({"x"}))
    out = ct.translate(["x", "y"])
    assert [r.status for r in out] == ["failed", "machine"]
    assert out[0].text is None
    assert cache.get_many("fake", "jp", "en", ["x", "y"]) == {"y": "<y>"}


def test_budget_boundary_and_skip(tmp_path: Path) -> None:
    ct, engine, _ = make(tmp_path, max_chars=5)
    out = ct.translate(["abc", "defg", "hi", "j"])
    # abc fits (3), defg would reach 7 -> pending, hi lands exactly on 5, j is over
    assert [r.status for r in out] == ["machine", "pending", "machine", "pending"]
    assert ct.chars_sent == 5
    assert engine.calls == [["abc", "hi"]]


def test_budget_zero_hits_free(tmp_path: Path) -> None:
    ct, engine, _ = make(tmp_path)
    ct.translate(["abc"])
    limited = CachedTranslator(engine, TranslationCache(tmp_path / "t.sqlite"), max_chars=0)
    out = limited.translate(["abc", "d"])
    assert [r.status for r in out] == ["machine", "pending"]
    assert limited.chars_sent == 0


def test_budget_is_cumulative(tmp_path: Path) -> None:
    ct, _, _ = make(tmp_path, max_chars=4)
    assert ct.translate(["abc"])[0].status == "machine"
    assert ct.translate(["de"])[0].status == "pending"


def test_chunks_are_committed_separately(tmp_path: Path) -> None:
    ct, engine, _ = make(tmp_path)
    ct.translate([f"t{i}" for i in range(120)])
    assert [len(c) for c in engine.calls] == [50, 50, 20]


def test_unsupported_pair(tmp_path: Path) -> None:
    ct, _, _ = make(tmp_path)
    with pytest.raises(ValueError):
        ct.translate(["a"], src="jp", tgt="jp")


def test_info_line_has_no_texts(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    ct, _, _ = make(tmp_path, max_chars=1)
    with caplog.at_level(logging.INFO):
        ct.translate(["秘密", "z"])
    assert "engine=fake hits=0 sent=1 chars=1 pending=1 failed=0" in caplog.text
    assert "秘密" not in caplog.text


def test_failed_second_chunk_keeps_first_chunk(tmp_path: Path) -> None:
    texts = [f"t{i}" for i in range(100)]
    ct, _, cache = make(tmp_path, fail=frozenset(texts[50:]))
    out = ct.translate(texts)
    assert [r.status for r in out] == ["machine"] * 50 + ["failed"] * 50
    assert set(cache.get_many("fake", "jp", "en", texts)) == set(texts[:50])


def test_engine_raising_keeps_earlier_chunks(tmp_path: Path) -> None:
    class Boom(FakeEngine):
        def translate(self, texts, *, src="jp", tgt="en"):  # type: ignore[no-untyped-def]
            if self.calls:
                raise RuntimeError("engine died")
            return super().translate(texts, src=src, tgt=tgt)

    cache = TranslationCache(tmp_path / "t.sqlite")
    ct = CachedTranslator(Boom(), cache)
    texts = [f"t{i}" for i in range(80)]
    with pytest.raises(RuntimeError):
        ct.translate(texts)
    assert set(cache.get_many("fake", "jp", "en", texts)) == set(texts[:50])
