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
MAX_DIFF_EXAMPLES = 5
BANDS = ((60, "<=60"), (150, "61-150"), (10**9, ">150"))
PAIRS = {'"': '"', "“": "”", "「": "」", "‘": "’"}
# style -> (token for index i, regex with one group capturing the index, residue regex)
STYLES: dict[str, tuple[Callable[[int], str], str, str]] = {
    "brk": (lambda i: f"⟦K{i}⟧", r"⟦\s*K\s*(\d+)\s*⟧", r"[⟦⟧]"),
    "xml": (lambda i: f"<k{i}/>", r"<\s*k\s*(\d+)\s*/\s*>", r"<\s*/?\s*k|/\s*>"),
    "tok": (lambda i: f"K{i}K", r"K(\d+)K", r"K\d+|\d+K"),
    "sq": (lambda i: f"[{i}]", r"\[\s*(\d+)\s*\]", r"\[\s*\d*|\d+\s*\]"),
}
STYLE_NAMES = ("raw", *STYLES)
MODES = ("whole", "line")
# (style, mode) combinations that are run; line mode only for the two best styles + baseline
COMBOS = [
    (st, m) for st in STYLE_NAMES for m in MODES if m == "whole" or st in ("raw", "brk", "xml")
]
GROUPS = ("all", "longest", "stratified")


@dataclass(frozen=True)
class Sample:
    """One sampled source text and where it came from."""

    kind: str  # text | flavor | summon
    card_type: str
    text: str
    group: str = "stratified"  # longest | stratified | flavor | summon


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
    garbled: bool
    order_changed: bool


def restore(out: str, style: str, spans: Sequence[str]) -> Check:
    """Put the spans back; strip only symmetric quote pairs around a token."""
    tok, residue = STYLES[style][1], STYLES[style][2]
    pair = re.compile(rf"([\"“「‘])\s*({tok})\s*([\"”」’])")
    out = pair.sub(lambda m: m.group(2) if PAIRS[m.group(1)] == m.group(4) else m.group(0), out)
    rx = re.compile(tok)
    found = [int(m.group(1)) for m in rx.finditer(out)]
    counts = Counter(found)
    valid = range(len(spans))
    lost = any(counts[i] == 0 for i in valid)
    duplicated = any(counts[i] > 1 for i in valid)
    foreign = any(i not in valid for i in counts)
    garbled = re.search(residue, rx.sub("", out)) is not None
    order = [i for n, i in enumerate(found) if i in valid and i not in found[:n]]
    restored = rx.sub(lambda m: spans[int(m.group(1))] if int(m.group(1)) < len(spans) else "", out)
    return Check(
        restored,
        not (lost or duplicated or foreign or garbled),
        lost,
        duplicated,
        foreign,
        garbled,
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
    longest_set = set(longest)
    out = [
        Sample("text", texts[t], t, "longest" if t in longest_set else "stratified") for t in chosen
    ]
    flavors = sorted(found["flavor"])
    out += [
        Sample("flavor", found["flavor"][t], t, "flavor")
        for t in rng.sample(flavors, min(n_flavor, len(flavors)))
    ]
    out += [Sample("summon", found["summon"][t], t, "summon") for t in sorted(found["summon"])]
    return out


Counter_ = Callable[[str], int]
STOPS = (".", "!", "?", '"', "”", ")", "]")


def truncated(src: str, out: str, limit: int, count: Counter_ | None) -> bool:
    """Heuristic: token count at the decoding limit, or a long text with no final stop."""
    if count is not None and count(out) >= limit - 1:
        return True
    return len(src) > 200 and not out.rstrip().endswith(STOPS)


def source_repeats(src: str, size: int = 8) -> bool:
    """True when the source itself repeats a ``size``-char run three or more times."""
    grams = Counter(src[i : i + size] for i in range(max(0, len(src) - size + 1)))
    return any(c >= 3 for c in grams.values())


def repetition(src: str, out: str) -> bool:
    """A word 3-gram that occurs 3+ times in the output while the source does not repeat."""
    words = re.findall(r"[a-z0-9']+", out.lower())
    grams = Counter(zip(words, words[1:], words[2:], strict=False))
    return any(c >= 3 for c in grams.values()) and not source_repeats(src)


def low_coverage(src: str, out: str, ratio: float = 0.6) -> bool:
    """Output has fewer sentences than ``ratio`` of the source lines/sentences."""
    n_src = len([x for x in re.split(r"[。\n]", src) if x.strip()])
    n_out = len([x for x in re.split(r"(?<=[.!?])\s+|\n", out) if x.strip()])
    return n_src >= 2 and n_out < ratio * n_src


@dataclass
class Tally:
    """Counters of one result over one group of samples."""

    n: int = 0
    with_spans: int = 0
    survived: int = 0
    lost: int = 0
    duplicated: int = 0
    foreign: int = 0
    garbled: int = 0
    order_changed: int = 0
    truncated: int = 0
    repetition: int = 0
    coverage: int = 0
    failed: int = 0


@dataclass
class Unit:
    """One translated string: a whole sample, or one line of it in line mode."""

    sample: int
    src: str
    masked: str
    spans: list[str]


@dataclass
class ComboResult:
    style: str
    mode: str
    tallies: dict[str, Tally] = field(default_factory=dict)
    s_short: float = 0.0
    s_long: float = 0.0
    trunc512: int | None = None
    examples: list[dict[str, str]] = field(default_factory=list)
    per_sample: list[dict[str, Any]] = field(default_factory=list)


def build_units(texts: Sequence[str], style: str, mode: str, pat: re.Pattern[str]) -> list[Unit]:
    """Split (line mode) and mask the texts; empty lines are not translated."""
    units: list[Unit] = []
    for i, text in enumerate(texts):
        parts = [text] if mode == "whole" else [x for x in text.split("\n") if x.strip()]
        for part in parts:
            masked, spans = mask(part, style, pat) if style != "raw" else (part, [])
            units.append(Unit(i, part, masked, spans))
    return units


def translate_units(
    units: Sequence[Unit],
    texts: Sequence[str],
    translator: Translator,
    clock: Callable[[], float] = time.perf_counter,
) -> tuple[list[list[str | None]], dict[bool, float]]:
    """Translate units in one batch per sample length class; return outputs and s/text."""
    outs: list[str | None] = [None] * len(units)
    secs: dict[bool, float] = {True: 0.0, False: 0.0}
    for short in (True, False):
        idx = [k for k, u in enumerate(units) if (len(texts[u.sample]) <= SHORT_MAX) == short]
        n_samples = len({units[k].sample for k in idx})
        if not idx:
            continue
        t0 = clock()
        got = translator.translate([units[k].masked for k in idx])
        secs[short] = (clock() - t0) / n_samples
        for k, r in zip(idx, got, strict=True):
            outs[k] = r.text
    per: list[list[str | None]] = [[] for _ in texts]
    for u, o in zip(units, outs, strict=True):
        per[u.sample].append(o)
    return per, secs


def score(
    style: str,
    mode: str,
    samples: Sequence[Sample],
    units: Sequence[Unit],
    per: list[list[str | None]],
    limit: int,
    count: Counter_ | None,
) -> ComboResult:
    """Score the translated units per sample and tally them by group."""
    res = ComboResult(style, mode, {g: Tally() for g in GROUPS})
    by_sample: dict[int, list[Unit]] = {}
    for u in units:
        by_sample.setdefault(u.sample, []).append(u)
    for i, s in enumerate(samples):
        outs = per[i]
        ts = [res.tallies["all"], res.tallies.get(s.group, Tally())]
        for t in ts:
            t.n += 1
        us = by_sample.get(i, [])
        if not us or any(o is None for o in outs):
            for t in ts:
                t.failed += 1
            res.per_sample.append({"bad": True, "out": None})
            continue
        checks = [
            restore(o or "", style, u.spans) if style != "raw" else None
            for u, o in zip(us, outs, strict=True)
        ]
        joined = "\n".join(
            c.restored if c else (o or "") for c, o in zip(checks, outs, strict=True)
        )
        raw_joined = "\n".join(o or "" for o in outs)
        spanned = any(u.spans for u in us)
        flags = {
            "truncated": any(
                truncated(u.src, o or "", limit, count) for u, o in zip(us, outs, strict=True)
            ),
            "repetition": repetition(s.text, joined),
            "coverage": low_coverage(s.text, joined),
        }
        real = [c for c in checks if c is not None]
        survived = all(c.survived for c in real)
        for t in ts:
            for name, v in flags.items():
                setattr(t, name, getattr(t, name) + v)
            if spanned and style != "raw":
                t.with_spans += 1
                t.survived += survived
                t.lost += any(c.lost for c in real)
                t.duplicated += any(c.duplicated for c in real)
                t.foreign += any(c.foreign for c in real)
                t.garbled += any(c.garbled for c in real)
                t.order_changed += any(c.order_changed for c in real)
            elif spanned:
                t.with_spans += 1
        bad = (spanned and style != "raw" and not survived) or any(flags.values())
        res.per_sample.append({"bad": bad, "out": raw_joined})
        if spanned and style != "raw" and not survived and len(res.examples) < MAX_EXAMPLES:
            res.examples.append(
                {
                    "source": "\n".join(u.masked for u in us),
                    "output": raw_joined,
                    "spans": " | ".join(sp for u in us for sp in u.spans),
                }
            )
    return res


def run_combo(
    style: str,
    mode: str,
    samples: Sequence[Sample],
    translator: Translator,
    pat: re.Pattern[str],
    limit: int,
    count: Counter_ | None,
    clock: Callable[[], float] = time.perf_counter,
) -> ComboResult:
    """Translate every sample under one style and mode and score it."""
    texts = [s.text for s in samples]
    units = build_units(texts, style, mode, pat)
    per, secs = translate_units(units, texts, translator, clock)
    res = score(style, mode, samples, units, per, limit, count)
    res.s_short, res.s_long = secs[True], secs[False]
    return res


def whole_vs_line(
    whole: ComboResult, line: ComboResult, samples: Sequence[Sample]
) -> list[dict[str, str]]:
    """Up to MAX_DIFF_EXAMPLES samples whose good/bad outcome differs between the modes."""
    out: list[dict[str, str]] = []
    for s, w, ln in zip(samples, whole.per_sample, line.per_sample, strict=True):
        if w["bad"] != ln["bad"] and len(out) < MAX_DIFF_EXAMPLES:
            out.append(
                {
                    "source": s.text,
                    "whole": f"{'BAD' if w['bad'] else 'ok'}: {w['out']}",
                    "line": f"{'BAD' if ln['bad'] else 'ok'}: {ln['out']}",
                }
            )
    return out


def compare_lengths(
    samples: Sequence[Sample],
    pat: re.Pattern[str],
    make: Callable[[int], Translator],
    counts: Callable[[int], Counter_ | None],
    n: int = 20,
) -> dict[str, Any]:
    """Re-run the n longest texts with limits 256 and 512; differing outputs = truncated."""
    longest = sorted((s.text for s in samples), key=lambda t: (-len(t), t))[:n]
    rows: list[dict[str, Any]] = [{"src_chars": len(t)} for t in longest]
    differ: dict[str, int] = {}
    for style, mode in COMBOS:
        if style not in ("raw", "brk", "xml"):
            continue
        units = build_units(longest, style, mode, pat)
        outs = {}
        for limit in (256, 512):
            per, _ = translate_units(units, longest, make(limit))
            outs[limit] = ["\n".join(o or "" for o in p) for p in per]
        differ[f"{style}/{mode}"] = sum(a != b for a, b in zip(outs[256], outs[512], strict=True))
        if (style, mode) == ("raw", "whole"):
            for limit in (256, 512):
                count = counts(limit)
                for row, src, out in zip(rows, longest, outs[limit], strict=True):
                    row[f"out_chars_{limit}"] = len(out)
                    row[f"tokens_{limit}"] = count(out) if count else None
                    row[f"truncated_{limit}"] = truncated(src, out, limit, count)
    return {"rows": rows, "differ": differ, "n": len(longest)}


def pct(a: int, b: int) -> str:
    return f"{a} ({100 * a / b:.0f}%)" if b else f"{a} (n/a)"


def _table(results: list[ComboResult], group: str, cmp: dict[str, Any] | None) -> list[str]:
    head = (
        "| style | mode | n | w/ spans | survived | lost | dup | foreign | garbled | order "
        "| repetition | coverage | truncated |"
    )
    cols = 13
    if cmp is not None:
        head += " trunc-512 (of 20) | s/text short | s/text long |"
        cols += 3
    else:
        head += " failed |"
        cols += 1
    lines = [head, "|" + " --- |" * cols]
    for r in results:
        t, w = r.tallies[group], r.tallies[group].with_spans
        row = (
            f"| {r.style} | {r.mode} | {t.n} | {w} | {pct(t.survived, w)} | {pct(t.lost, w)} "
            f"| {pct(t.duplicated, w)} | {pct(t.foreign, w)} | {pct(t.garbled, w)} "
            f"| {pct(t.order_changed, w)} | {pct(t.repetition, t.n)} | {pct(t.coverage, t.n)} "
            f"| {pct(t.truncated, t.n)} |"
        )
        if cmp is not None:
            d = cmp["differ"].get(f"{r.style}/{r.mode}")
            row += f" {'-' if d is None else d} | {r.s_short:.3f} | {r.s_long:.3f} |"
        else:
            row += f" {t.failed} |"
        lines.append(row)
    return lines


def write_report(
    out: Path,
    meta: dict[str, Any],
    results: list[ComboResult],
    cmp: dict[str, Any],
    diffs: dict[str, list[dict[str, str]]],
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": meta,
        "results": [r.__dict__ for r in results],
        "compare_256_512": cmp,
        "diffs": diffs,
    }
    payload["results"] = [{**r.__dict__, "per_sample": None} for r in results]
    (out / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=lambda o: o.__dict__),
        encoding="utf-8",
    )
    lines = [
        "# MT placeholder spike (#153)",
        "",
        f"Sample: {meta['n_samples']} texts (seed {meta['seed']}), kinds {meta['kinds']}, "
        f"cold model load {meta['cold_load_s']:.1f} s.",
        "",
        "Notes:",
        "- The 20 longest texts are forced into the sample, so the *all* table over-weights long "
        "texts; *longest* and *stratified* are reported separately below.",
        "- Rates are over texts with spans (survival columns) or over all texts in the group "
        "(repetition, coverage, truncated). Garbled = marker residue left after restoring. "
        "Repetition and coverage are heuristics (3-gram x3; output sentences < 60% of source).",
        "- Timing is per batch: each length class (short <= 100 chars, long) is translated as one "
        "batch and divided by its text count; line mode divides by samples, not lines.",
        "- trunc-512: of the 20 longest texts, how many outputs differ between decoding limits "
        "256 and 512 (differ = truncated at 256).",
        "",
        "## All samples",
        "",
        *_table(results, "all", cmp),
        "",
        "## 20 longest (forced)",
        "",
        *_table(results, "longest", None),
        "",
        "## Stratified texts",
        "",
        *_table(results, "stratified", None),
    ]
    for key, exs in diffs.items():
        if exs:
            lines += ["", f"## Whole vs line differs: {key}", ""]
            for ex in exs:
                lines += [
                    f"- source: `{ex['source']}`",
                    f"  - whole: `{ex['whole']}`",
                    f"  - line: `{ex['line']}`",
                ]
    for r in results:
        if not r.examples:
            continue
        lines += ["", f"## Failures: {r.style}/{r.mode}", ""]
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
    for row in cmp["rows"]:
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
    for style, mode in COMBOS:
        print(f"style {style} {mode} ...", flush=True)
        results.append(run_combo(style, mode, samples, tr, pat, 256, count))
    translators: dict[int, QuickMTTranslator] = {256: tr}

    def make(limit: int) -> QuickMTTranslator:
        return translators.setdefault(
            limit, QuickMTTranslator(args.model, max_decoding_length=limit)
        )

    def counts(limit: int) -> Counter_ | None:
        return token_counter(make(limit))

    cmp = compare_lengths(samples, pat, make, counts)
    for r in results:
        r.trunc512 = cmp["differ"].get(f"{r.style}/{r.mode}")
    by = {(r.style, r.mode): r for r in results}
    diffs = {
        st: whole_vs_line(by[st, "whole"], by[st, "line"], samples) for st in ("raw", "brk", "xml")
    }
    meta = {
        "seed": args.seed,
        "n_samples": len(samples),
        "cold_load_s": cold,
        "kinds": dict(Counter(s.kind for s in samples)),
    }
    write_report(args.out, meta, results, cmp, diffs)
    print(f"wrote {args.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
