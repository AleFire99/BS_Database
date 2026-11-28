"""Spike (#153): which placeholder style keeps protected spans alive through the MT model.

Draws a fixed-seed stratified sample of Japanese effect texts from ``data/normalized``,
masks the protected spans (``【…】``, ``「…」``, ``『…』``, ``系統：``, runs of symbol
glyphs) with each placeholder style, translates with the offline quickmt model, restores,
and writes ``results.json`` and ``report.md``. A prototype only: not the #156 module.

Usage: ``uv run python tests/tools/mt_spike.py --normalized data/normalized
--out data/review/mt_spike --seed 147 [--model data/models/quickmt-ja-en]``
"""

import argparse
import csv
import json
import random
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs_database.translate.quickmt import QuickMTTranslator
from bs_database.translate.types import Translator

SHORT_MAX = 100
MAX_EXAMPLES = 8
BANDS = ((60, "<=60"), (150, "61-150"), (10**9, ">150"))
OPEN_QUOTES = "\"'“‘「«"
CLOSE_QUOTES = "\"'”’」»"
# style -> (token for index i, regex with one group capturing the index)
STYLES: dict[str, tuple[Callable[[int], str], str]] = {
    "brk": (lambda i: f"⟦K{i}⟧", r"⟦\s*K\s*(\d+)\s*⟧"),
    "xml": (lambda i: f"<k{i}/>", r"<\s*k\s*(\d+)\s*/\s*>"),
    "tok": (lambda i: f"K{i}K", r"(?<![A-Za-z])K(\d+)K(?![A-Za-z])"),
    "sq": (lambda i: f"[{i}]", r"\[\s*(\d+)\s*\]"),
}
STYLE_NAMES = ("raw", *STYLES)


@dataclass(frozen=True)
class Sample:
    """One sampled source text and where it came from."""

    kind: str  # text | flavor | summon
    card_type: str
    text: str


def span_pattern(glyphs: Sequence[str] = ()) -> re.Pattern[str]:
    """Regex of protected spans; symbol glyphs only count as a run of two or more."""
    parts = [r"【[^】]*】", r"「[^」]*」", r"『[^』]*』", r"系統："]
    if glyphs:
        cls = "".join(re.escape(g) for g in glyphs)
        parts.append(f"[{cls}]{{2,}}")
    return re.compile("|".join(parts))


def load_glyphs(symbols_csv: Path) -> list[str]:
    """Single-character ``jp`` entries of the symbols glossary (empty when missing)."""
    if not symbols_csv.is_file():
        return []
    with symbols_csv.open(encoding="utf-8", newline="") as fh:
        return [r["jp"] for r in csv.DictReader(fh) if len(r["jp"]) == 1]


def mask(text: str, style: str, pat: re.Pattern[str]) -> tuple[str, list[str]]:
    """Replace each protected span by the style's token; return (masked, spans)."""
    spans: list[str] = []
    make = STYLES[style][0]

    def sub(m: re.Match[str]) -> str:
        spans.append(m.group(0))
        return make(len(spans) - 1)

    return pat.sub(sub, text), spans


@dataclass
class Check:
    """Outcome of restoring one translated text."""

    restored: str
    survived: bool
    lost: bool
    duplicated: bool
    foreign: bool
    order_changed: bool


def restore(out: str, style: str, spans: Sequence[str]) -> Check:
    """Put the spans back, tolerating quotes and spaces around the tokens."""
    rx = re.compile(
        rf"(?:[{re.escape(OPEN_QUOTES)}]\s*)?(?:{STYLES[style][1]})(?:\s*[{re.escape(CLOSE_QUOTES)}])?"
    )
    found = [int(m.group(1)) for m in rx.finditer(out)]
    counts = Counter(found)
    valid = range(len(spans))
    lost = any(counts[i] == 0 for i in valid)
    duplicated = any(counts[i] > 1 for i in valid)
    foreign = any(i not in valid for i in counts)
    order = [i for n, i in enumerate(found) if i in valid and i not in found[:n]]
    restored = rx.sub(lambda m: spans[int(m.group(1))] if int(m.group(1)) < len(spans) else "", out)
    return Check(
        restored,
        not lost and not duplicated and not foreign,
        lost,
        duplicated,
        foreign,
        order != sorted(order),
    )


def _records(normalized: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted((normalized / "batspi").glob("*.json")):
        page = json.loads(path.read_text(encoding="utf-8"))["page"]
        out.extend(page.get("entries", []))
    return out


def collect(normalized: Path) -> dict[str, dict[str, str]]:
    """Distinct texts per kind, each mapped to a card type (first seen)."""
    found: dict[str, dict[str, str]] = {"text": {}, "flavor": {}, "summon": {}}
    for entry in _records(normalized):
        text = entry.get("text")
        if not text:
            continue
        ctype = (entry.get("gameplay") or {}).get("card_type_code") or "unknown"
        for eff in text.get("effects") or []:
            if eff.get("text_jp"):
                found["text"].setdefault(eff["text_jp"], ctype)
        if text.get("flavor_jp"):
            found["flavor"].setdefault(text["flavor_jp"], ctype)
        if text.get("summon_condition_jp"):
            found["summon"].setdefault(text["summon_condition_jp"], ctype)
    return found


def band(text: str) -> str:
    return next(label for limit, label in BANDS if len(text) <= limit)


def draw_sample(
    found: dict[str, dict[str, str]],
    seed: int,
    n_text: int = 200,
    n_flavor: int = 50,
    n_longest: int = 20,
) -> list[Sample]:
    """Fixed-seed sample: stratified texts plus the longest, flavors, all summon conditions."""
    rng = random.Random(seed)
    texts = found["text"]
    longest = sorted(texts, key=lambda t: (-len(t), t))[:n_longest]
    strata: dict[tuple[str, str], list[str]] = {}
    for t in sorted(texts):
        strata.setdefault((texts[t], band(t)), []).append(t)
    chosen: list[str] = list(longest)
    for key in sorted(strata):
        pool = [t for t in strata[key] if t not in chosen]
        take = max(1, round(n_text * len(strata[key]) / len(texts)))
        chosen += rng.sample(pool, min(take, len(pool)))
    rest = [t for t in sorted(texts) if t not in chosen]
    while len(chosen) < n_text and rest:
        chosen.append(rest.pop(rng.randrange(len(rest))))
    out = [Sample("text", texts[t], t) for t in chosen]
    flavors = sorted(found["flavor"])
    out += [
        Sample("flavor", found["flavor"][t], t)
        for t in rng.sample(flavors, min(n_flavor, len(flavors)))
    ]
    out += [Sample("summon", found["summon"][t], t) for t in sorted(found["summon"])]
    return out


Counter_ = Callable[[str], int]


def truncated(src: str, out: str, limit: int, count: Counter_ | None) -> bool:
    """Heuristic: token count at the decoding limit, or a long text with no final stop."""
    if count is not None and count(out) >= limit - 1:
        return True
    return len(src) > 200 and not out.rstrip().endswith((".", "!", "?", '"', "”", ")", "]"))


@dataclass
class StyleResult:
    style: str
    n: int = 0
    with_spans: int = 0
    survived: int = 0
    lost: int = 0
    duplicated: int = 0
    foreign: int = 0
    order_changed: int = 0
    truncated: int = 0
    failed: int = 0
    s_short: float = 0.0
    s_long: float = 0.0
    examples: list[dict[str, str]] = field(default_factory=list)


def run_style(
    style: str,
    samples: Sequence[Sample],
    translator: Translator,
    pat: re.Pattern[str],
    limit: int,
    count: Counter_ | None,
    clock: Callable[[], float] = time.perf_counter,
) -> StyleResult:
    """Translate every sample under one style (timed per length class) and score it."""
    masked = [(mask(s.text, style, pat) if style != "raw" else (s.text, [])) for s in samples]
    outs: list[str | None] = [None] * len(samples)
    res = StyleResult(style, n=len(samples))
    for is_short in (True, False):
        idx = [i for i, s in enumerate(samples) if (len(s.text) <= SHORT_MAX) == is_short]
        if not idx:
            continue
        t0 = clock()
        got = translator.translate([masked[i][0] for i in idx])
        elapsed = (clock() - t0) / len(idx)
        if is_short:
            res.s_short = elapsed
        else:
            res.s_long = elapsed
        for i, r in zip(idx, got, strict=True):
            outs[i] = r.text
    for s, (m, spans), out in zip(samples, masked, outs, strict=True):
        if out is None:
            res.failed += 1
            continue
        if truncated(s.text, out, limit, count):
            res.truncated += 1
        if style == "raw" or not spans:
            continue
        res.with_spans += 1
        chk = restore(out, style, spans)
        res.survived += chk.survived
        res.lost += chk.lost
        res.duplicated += chk.duplicated
        res.foreign += chk.foreign
        res.order_changed += chk.order_changed
        if not chk.survived and len(res.examples) < MAX_EXAMPLES:
            res.examples.append({"source": m, "output": out, "spans": " | ".join(spans)})
    return res


def compare_lengths(
    samples: Sequence[Sample],
    make: Callable[[int], Translator],
    counts: Callable[[int], Counter_ | None],
    n: int = 20,
) -> list[dict[str, Any]]:
    """Re-run the n longest raw texts with decoding limits 256 and 512."""
    longest = sorted((s.text for s in samples), key=lambda t: (-len(t), t))[:n]
    rows: list[dict[str, Any]] = [{"src_chars": len(t)} for t in longest]
    for limit in (256, 512):
        tr, count = make(limit), counts(limit)
        for row, src, r in zip(rows, longest, tr.translate(longest), strict=True):
            out = r.text or ""
            row[f"out_chars_{limit}"] = len(out)
            row[f"tokens_{limit}"] = count(out) if count else None
            row[f"truncated_{limit}"] = truncated(src, out, limit, count)
    return rows


def pct(a: int, b: int) -> str:
    return f"{a} ({100 * a / b:.1f}%)" if b else f"{a} (n/a)"


def write_report(
    out: Path, meta: dict[str, Any], results: list[StyleResult], cmp: list[dict[str, Any]]
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "styles": [r.__dict__ for r in results], "compare_256_512": cmp}
    (out / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# MT placeholder spike (#153)",
        "",
        f"Sample: {meta['n_samples']} texts (seed {meta['seed']}), "
        f"cold model load {meta['cold_load_s']:.1f} s.",
        "",
        "| style | texts w/ spans | survival | lost | duplicated | foreign "
        "| order changed | truncated | failed | s/text short | s/text long |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        w = r.with_spans
        lines.append(
            f"| {r.style} | {w} | {pct(r.survived, w)} | {pct(r.lost, w)} | {pct(r.duplicated, w)} "
            f"| {pct(r.foreign, w)} | {pct(r.order_changed, w)} | {pct(r.truncated, r.n)} "
            f"| {r.failed} | {r.s_short:.3f} | {r.s_long:.3f} |"
        )
    for r in results:
        if not r.examples:
            continue
        lines += ["", f"## Failures: {r.style}", ""]
        for ex in r.examples:
            lines += [
                f"- spans: `{ex['spans']}`",
                f"  - masked: `{ex['source']}`",
                f"  - output: `{ex['output']}`",
            ]
    lines += [
        "",
        "## 256 vs 512 decoding length (20 longest texts, raw)",
        "",
        "| src chars | out chars 256 | tokens 256 | trunc 256 "
        "| out chars 512 | tokens 512 | trunc 512 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in cmp:
        lines.append(
            f"| {row['src_chars']} | {row['out_chars_256']} | {row['tokens_256']} "
            f"| {row['truncated_256']} "
            f"| {row['out_chars_512']} | {row['tokens_512']} | {row['truncated_512']} |"
        )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def token_counter(tr: QuickMTTranslator) -> Counter_ | None:
    """Target-side SentencePiece token counter of a loaded translator (None if unavailable)."""
    models = tr._load()  # noqa: SLF001 - spike tool, reads the loaded model
    if models is None:
        return None
    return lambda s: len(models.tgt_spm.encode(s, out_type=str))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--normalized", type=Path, default=Path("data/normalized"))
    ap.add_argument("--out", type=Path, default=Path("data/review/mt_spike"))
    ap.add_argument("--model", type=Path, default=Path("data/models/quickmt-ja-en"))
    ap.add_argument("--symbols", type=Path, default=Path("data/glossary/symbols.csv"))
    ap.add_argument("--seed", type=int, default=147)
    args = ap.parse_args(argv[1:])
    if not (args.normalized / "batspi").is_dir():
        print(f"error: no normalized data in {args.normalized}", file=sys.stderr)
        return 1
    samples = draw_sample(collect(args.normalized), args.seed)
    pat = span_pattern(load_glyphs(args.symbols))

    t0 = time.perf_counter()
    tr = QuickMTTranslator(args.model, max_decoding_length=256)
    tr.translate(["テスト"])
    cold = time.perf_counter() - t0
    count = token_counter(tr)
    results = []
    for style in STYLE_NAMES:
        print(f"style {style} ...", flush=True)
        results.append(run_style(style, samples, tr, pat, 256, count))
    translators: dict[int, QuickMTTranslator] = {256: tr}

    def make(limit: int) -> QuickMTTranslator:
        return translators.setdefault(
            limit, QuickMTTranslator(args.model, max_decoding_length=limit)
        )

    def counts(limit: int) -> Counter_ | None:
        return token_counter(make(limit))

    cmp = compare_lengths(samples, make, counts)
    meta = {
        "seed": args.seed,
        "n_samples": len(samples),
        "cold_load_s": cold,
        "kinds": dict(Counter(s.kind for s in samples)),
    }
    write_report(args.out, meta, results, cmp)
    print(f"wrote {args.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
