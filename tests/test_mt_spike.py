"""Unit tests for the MT spike tool (no model needed)."""

import importlib.util
import re
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


def test_restore_tolerates_quotes_and_spaces() -> None:
    chk = spike.restore("During “⟦K0⟧” , hit ⟦ K1 ⟧.", "brk", ["【A】", "「B」"])
    assert chk.survived
    assert chk.restored == "During 【A】 , hit 「B」."  # noqa: RUF001


def test_failure_classes() -> None:
    spans = ["a", "b"]
    assert spike.restore("⟦K0⟧", "brk", spans).lost
    assert spike.restore("⟦K0⟧ ⟦K0⟧ ⟦K1⟧", "brk", spans).duplicated
    assert spike.restore("⟦K0⟧ ⟦K1⟧ ⟦K7⟧", "brk", spans).foreign
    chk = spike.restore("⟦K1⟧ ⟦K0⟧", "brk", spans)
    assert chk.survived and chk.order_changed


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


def test_run_style_with_fake_translator() -> None:
    samples = [spike.Sample("text", "spirit", SRC), spike.Sample("text", "spirit", "なし")]
    res = spike.run_style("brk", samples, Echo(), PAT, 256, None)
    assert (res.with_spans, res.survived, res.failed) == (1, 1, 0)
    assert not re.search("x", "")
