"""Unit tests for the MT spike tool (no model needed)."""

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path

from bs_database.translate.types import Lang, TranslationResult

_path = Path(__file__).parent / "tools" / "mt_spike.py"
_spec = importlib.util.spec_from_file_location("mt_spike", _path)
assert _spec is not None and _spec.loader is not None
spike = importlib.util.module_from_spec(_spec)
sys.modules["mt_spike"] = spike
_spec.loader.exec_module(spike)

PAT = spike.span_pattern(["赤", "青"])
SRC = "【一騎打】の間、「ティガ」を持つ赤赤のスピリットを破壊する。"


class Echo:
    """Fake translator: returns the (masked) text unchanged."""

    name = "echo"

    def translate(
        self, texts: Sequence[str], *, src: Lang = "jp", tgt: Lang = "en"
    ) -> list[TranslationResult]:
        return [TranslationResult(t, "machine", self.name) for t in texts]


def test_round_trip_every_style() -> None:
    for style in spike.STYLES:
        masked, spans = spike.mask(SRC, style, PAT)
        assert spans == ["【一騎打】", "「ティガ」", "赤赤"]
        chk = spike.restore(masked, style, spans)
        assert chk.survived and chk.restored == SRC


def test_adjacent_tokens_every_style() -> None:
    for style, (make, _rx, _res) in spike.STYLES.items():
        chk = spike.restore(make(0) + make(1) + make(2), style, ["a", "b", "c"])
        assert chk.survived and chk.restored == "abc", style


def test_restore_tolerates_symmetric_quotes_and_spaces() -> None:
    chk = spike.restore("During “⟦K0⟧” , hit ⟦ K1 ⟧.", "brk", ["【A】", "「B」"])
    assert chk.survived
    assert chk.restored == "During 【A】 , hit 「B」."  # noqa: RUF001
    assert spike.restore('say "⟦K0⟧" now', "brk", ["X"]).restored == "say X now"


def test_lone_apostrophe_is_kept() -> None:
    chk = spike.restore("It's ⟦K0⟧'s", "brk", ["X"])
    assert chk.survived and chk.restored == "It's X's"
    assert spike.restore("'⟦K0⟧'", "brk", ["X"]).restored == "'X'"


def test_failure_classes() -> None:
    spans = ["a", "b"]
    assert spike.restore("⟦K0⟧", "brk", spans).lost
    assert spike.restore("⟦K0⟧ ⟦K0⟧ ⟦K1⟧", "brk", spans).duplicated
    assert spike.restore("⟦K0⟧ ⟦K1⟧ ⟦K7⟧", "brk", spans).foreign
    chk = spike.restore("⟦K1⟧ ⟦K0⟧", "brk", spans)
    assert chk.survived and chk.order_changed


def test_garbled_residue_fails_survival() -> None:
    for style, out in [
        ("brk", "⟦K0⟧ ⟦"),
        ("xml", "<k0/> <k"),
        ("tok", "K0K K5"),
        ("sq", "[0] [3"),
    ]:
        chk = spike.restore(out, style, ["a"])
        assert chk.garbled and not chk.survived, style


def test_span_edge_cases() -> None:
    nested = "【あ「い」う】え"
    assert spike.mask(nested, "brk", PAT) == ("⟦K0⟧え", ["【あ「い」う】"])
    assert spike.mask("「閉じない", "brk", PAT) == ("「閉じない", [])
    assert spike.mask("赤のスピリット", "brk", PAT) == ("赤のスピリット", [])


def test_truncated_both_branches() -> None:
    assert spike.truncated("短い", "x", 256, lambda s: 255)
    assert not spike.truncated("短い", "x", 256, lambda s: 100)
    long_src = "あ" * 201
    assert spike.truncated(long_src, "It goes on", 256, None)
    assert not spike.truncated(long_src, "It ends.", 256, None)
    assert not spike.truncated("あ" * 10, "no stop", 256, None)


def test_repetition_and_coverage() -> None:
    assert spike.repetition("あいうえお", "draw a card. draw a card. draw a card. draw a card.")
    assert not spike.repetition("あいうえお", "draw a card. then discard one.")
    assert not spike.repetition("ドロー" * 20, "draw a card. draw a card. draw a card.")
    assert spike.low_coverage("一。二。三。四。五。", "Only one.")
    assert not spike.low_coverage("一。二。", "One. Two.")
    assert not spike.low_coverage("一\n二", "One\nTwo")


class Lines:
    """Fake translator keeping only the first line of what it is given (drops the rest)."""

    name = "lines"

    def translate(
        self, texts: Sequence[str], *, src: Lang = "jp", tgt: Lang = "en"
    ) -> list[TranslationResult]:
        return [TranslationResult(t.split("\n")[0], "machine", self.name) for t in texts]


def test_sampler_is_deterministic() -> None:
    found = {
        "text": {
            f"テキスト{i}" * (1 + i % 40): ("spirit" if i % 2 else "magic") for i in range(300)
        },
        "flavor": {f"f{i}": "spirit" for i in range(80)},
        "summon": {f"s{i}": "spirit" for i in range(5)},
    }
    a = spike.draw_sample(found, 147)
    b = spike.draw_sample(found, 147)
    assert a == b
    assert a != spike.draw_sample(found, 1)
    kinds = [s.kind for s in a]
    assert kinds.count("flavor") == 50 and kinds.count("summon") == 5
    assert kinds.count("text") >= 200
    longest = sorted(found["text"], key=lambda t: (-len(t), t))[:20]
    assert set(longest) <= {s.text for s in a}


def test_run_combo_with_fake_translator() -> None:
    samples = [spike.Sample("text", "spirit", SRC), spike.Sample("text", "spirit", "なし")]
    res = spike.run_combo("brk", "whole", samples, Echo(), PAT, 256, None)
    t = res.tallies["all"]
    assert (t.with_spans, t.survived, t.failed) == (1, 1, 0)


def test_line_mode_beats_whole_when_translator_drops_lines() -> None:
    text = "【A】一。\n「B」二。"
    samples = [spike.Sample("text", "spirit", text, "longest")]
    whole = spike.run_combo("brk", "whole", samples, Lines(), PAT, 256, None)
    line = spike.run_combo("brk", "line", samples, Lines(), PAT, 256, None)
    assert whole.tallies["all"].lost == 1 and whole.tallies["longest"].lost == 1
    assert line.tallies["all"].survived == 1
    diff = spike.whole_vs_line(whole, line, samples)
    assert len(diff) == 1 and diff[0]["whole"].startswith("BAD")
