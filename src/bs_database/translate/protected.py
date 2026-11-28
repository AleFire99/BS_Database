"""Term protection around a translator (#156, ADR 0012).

``ProtectedTranslator`` masks the protected spans of every line, sends all lines of all
texts to the inner engine as one batch, validates and restores them. A line that fails is
retried once by splitting it on ``。`` and translating the sentences as a second batch. If
a line still fails, the whole field is ``failed``: never a partial text.

The cache belongs *below* this layer (``ProtectedTranslator(CachedTranslator(engine))``):
it stores the engine output per masked line, so glossary or name edits apply on the next
run without re-translating, and a change of the masking rules misses the cache by itself.
"""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from bs_database.translate.protect import (
    Span,
    SpanKind,
    TermResolver,
    protect,
    restore,
    span_pattern,
    split_sentences,
    validate,
)
from bs_database.translate.types import Lang, TranslationResult, Translator, check_pair

log = logging.getLogger(__name__)

PROTECTION_VERSION = 1  # bump on any change of the masking, validation or segmentation rules

_Outcome = Literal["ok", "bad", "pending"]


@dataclass(frozen=True)
class ProtectionConfig:
    """What ``make_translator`` needs to add protection: the resolver and the symbol glyphs."""

    resolver: TermResolver
    glyphs: tuple[str, ...]


@dataclass
class _Unit:
    """One masked piece (a line or a retry sentence) and its outcome."""

    raw: str
    masked: str
    spans: list[Span]
    outcome: _Outcome = "bad"
    text: str = ""  # validated text with tokens, when ``outcome`` is ok


class _Counting:
    """A resolver that counts the spans it could not resolve."""

    def __init__(self, inner: TermResolver) -> None:
        self._inner = inner
        self.unresolved = 0

    def resolve(self, kind: SpanKind, jp: str) -> str | None:
        en = self._inner.resolve(kind, jp)
        if en is None:
            self.unresolved += 1
        return en


class ProtectedTranslator:
    """Translates jp -> en with the protected spans kept out of the engine's hands."""

    def __init__(
        self,
        engine: Translator,
        resolver: TermResolver,
        glyphs: Iterable[str],
        *,
        retry: bool = True,
    ) -> None:
        self._engine = engine
        self._resolver = resolver
        self._pattern = span_pattern(glyphs)
        self._retry = retry
        self.name = f"{engine.name}+prot{PROTECTION_VERSION}"

    def _unit(self, raw: str) -> _Unit:
        masked, spans = protect(raw, self._pattern)
        return _Unit(raw, masked, spans)

    def _run(self, units: Sequence[_Unit], src: Lang, tgt: Lang) -> None:
        """Translate the masked units in one engine call and set each outcome."""
        if not units:
            return
        results = self._engine.translate([u.masked for u in units], src=src, tgt=tgt)
        for unit, result in zip(units, results, strict=True):
            if result.status == "pending":
                unit.outcome = "pending"
                continue
            valid = None
            if result.status == "machine" and result.text is not None:
                valid = validate(result.text, unit.spans)
            if valid is None:
                unit.outcome = "bad"
            else:
                unit.outcome, unit.text = "ok", valid

    def translate(
        self, texts: Sequence[str], *, src: Lang = "jp", tgt: Lang = "en"
    ) -> list[TranslationResult]:
        check_pair(src, tgt)
        fields: dict[int, list[_Unit]] = {
            i: [self._unit(line) for line in t.split("\n")]
            for i, t in enumerate(texts)
            if t.strip()
        }
        # blank lines inside a field are kept as they are and never sent
        lines = [u for units in fields.values() for u in units if u.raw.strip()]
        self._run(lines, src, tgt)

        retries: dict[int, list[_Unit]] = {}
        if self._retry:
            for n, line in enumerate(lines):
                sentences = split_sentences(line.raw)
                if line.outcome == "bad" and len(sentences) > 1:
                    retries[n] = [self._unit(s) for s in sentences]
        self._run([u for units in retries.values() for u in units], src, tgt)

        counter = _Counting(self._resolver)
        done: dict[int, str] = {}  # id(line) -> restored text
        for n, line in enumerate(lines):
            if n in retries:
                pieces = retries[n]
                if all(p.outcome == "ok" for p in pieces):
                    line.outcome = "ok"
                    done[id(line)] = " ".join(restore(p.text, p.spans, counter) for p in pieces)
                elif any(p.outcome == "bad" for p in pieces):
                    line.outcome = "bad"
                else:
                    line.outcome = "pending"
            elif line.outcome == "ok":
                done[id(line)] = restore(line.text, line.spans, counter)

        pending = TranslationResult(None, "pending", self.name)
        failed = TranslationResult(None, "failed", self.name)
        out = [pending] * len(texts)
        for i, units in fields.items():
            real = [u for u in units if u.raw.strip()]
            if any(u.outcome == "bad" for u in real):
                out[i] = failed
            elif any(u.outcome == "pending" for u in real):
                out[i] = pending
            else:
                text = "\n".join(done.get(id(u), "") for u in units)
                out[i] = TranslationResult(text, "machine", self.name)
        log.info(
            "protect engine=%s fields=%d lines=%d retried=%d failed=%d unresolved=%d",
            self.name,
            len(fields),
            len(lines),
            len(retries),
            sum(r.status == "failed" for r in out),
            counter.unresolved,
        )
        return out


__all__ = ["PROTECTION_VERSION", "ProtectedTranslator", "ProtectionConfig"]
