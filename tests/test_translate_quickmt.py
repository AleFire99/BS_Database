import logging
from pathlib import Path

import pytest
from fakes import FakeCT2, FakeSP

from bs_database.translate.quickmt import Models, QuickMTTranslator, default_loader


def make(
    ct2: FakeCT2 | None = None, *, batch_size: int = 32
) -> tuple[QuickMTTranslator, FakeCT2, list[tuple[Path, str, str]]]:
    fake = ct2 or FakeCT2()
    loads: list[tuple[Path, str, str]] = []

    def loader(model_dir: Path, device: str, compute_type: str) -> Models:
        loads.append((model_dir, device, compute_type))
        return Models(fake, FakeSP(), FakeSP())

    return QuickMTTranslator(Path("m"), loader=loader, batch_size=batch_size), fake, loads


def test_order_and_blanks_kept() -> None:
    engine, _, _ = make()
    out = engine.translate(["ab", "", "  ", "c"])
    assert [(r.text, r.status) for r in out] == [
        ("AB", "machine"),
        (None, "pending"),
        (None, "pending"),
        ("C", "machine"),
    ]
    assert {r.engine for r in out} == {"quickmt-ja-en"}


def test_loading_is_lazy_and_once() -> None:
    engine, _, loads = make()
    assert loads == []
    assert engine.translate(["", " "])[0].status == "pending"
    assert loads == []
    engine.translate(["a"])
    engine.translate(["b"])
    assert loads == [(Path("m"), "cpu", "int8")]


def test_chunked_by_batch_size_with_deterministic_options() -> None:
    engine, fake, _ = make(batch_size=2)
    engine.translate(["a", "b", "c", "d", "e"])
    assert [len(source) for source, _ in fake.calls] == [2, 2, 1]
    assert fake.calls[0][1] == {
        "beam_size": 5,
        "num_hypotheses": 1,
        "max_decoding_length": 256,
        "sampling_topk": 1,
    }


def test_load_failure_fails_everything_once(caplog: pytest.LogCaptureFixture) -> None:
    calls: list[int] = []

    def loader(model_dir: Path, device: str, compute_type: str) -> Models:
        calls.append(1)
        raise OSError("no model")

    engine = QuickMTTranslator(Path("m"), loader=loader)
    with caplog.at_level(logging.WARNING):
        first = engine.translate(["a", "", "b"])
        engine.translate(["c"])
    assert [r.status for r in first] == ["failed", "pending", "failed"]
    assert calls == [1]
    assert caplog.text.count("not loaded") == 1


def test_batch_exception_fails_only_that_batch() -> None:
    engine, _, _ = make(FakeCT2(fail_on=["c"]), batch_size=2)
    out = engine.translate(["a", "b", "c", "d"])
    assert [r.status for r in out] == ["machine", "machine", "failed", "failed"]
    assert [r.text for r in out[:2]] == ["A", "B"]


def test_wrong_hypothesis_count_fails_the_batch() -> None:
    engine, _, _ = make(FakeCT2(hypotheses=2))
    assert [r.status for r in engine.translate(["a", "b"])] == ["failed", "failed"]


def test_empty_output_is_failed() -> None:
    class Empty(FakeCT2):
        def translate_batch(self, source: list[list[str]], **options: object) -> list:  # type: ignore[type-arg]
            return [type("R", (), {"hypotheses": [[]]})() for _ in source]

    engine, _, _ = make(Empty())
    assert engine.translate(["a"])[0].status == "failed"


@pytest.mark.parametrize(("src", "tgt"), [("en", "jp"), ("jp", "jp"), ("jp", "fr")])
def test_bad_pair_raises(src: str, tgt: str) -> None:
    engine, _, _ = make()
    with pytest.raises(ValueError, match="unsupported"):
        engine.translate(["a"], src=src, tgt=tgt)  # type: ignore[arg-type]


def test_default_loader_without_files_raises(tmp_path: Path) -> None:
    with pytest.raises(Exception):  # noqa: B017 - ImportError without the group, else a load error
        default_loader(tmp_path / "missing", "cpu", "int8")


def test_default_loader_failure_becomes_failed(tmp_path: Path) -> None:
    engine = QuickMTTranslator(tmp_path / "missing")
    assert engine.translate(["a"])[0].status == "failed"
