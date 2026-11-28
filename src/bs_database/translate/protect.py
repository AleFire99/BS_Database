"""Term protection around machine translation (#156, ADR 0012): mask, validate, restore.

Pure functions, no engine. A line is masked by replacing each protected span (``【…】``,
``《…》``, ``〔…〕``, ``『…』``, ``「…」``, ``系統：``, a run of symbol glyphs) with a token
``<k0/>`` numbered per line. The engine translates the masked line; ``validate`` checks the
tokens came back intact and ``restore`` puts the canonical English back, asking a
``TermResolver`` (``GlossaryResolver`` for the glossaries).

The English keeps the source brackets (``【Duel】``). A span the resolver does not know keeps
its Japanese; that is not a failure (the translator counts them).
"""

import importlib
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from bs_database.glossary import FamilyEntry, Glossary


class SpanKind(StrEnum):
    """The protected classes of ADR 0012 decision 3."""

    KEYWORD = "keyword"  # 【…】
    GUILLEMET = "guillemet"  # 《…》
    QUALIFIER = "qualifier"  # 〔…〕
    TIMING = "timing"  # 『…』
    NAME = "name"  # 「…」
    FAMILY_LABEL = "family_label"  # 系統：
    SYMBOLS = "symbols"  # a run of two or more symbol glyphs


@dataclass(frozen=True)
class Span:
    """A protected span: ``text`` as written, ``inner`` the text inside its brackets."""

    kind: SpanKind
    text: str
    inner: str


_BRACKETS: dict[str, tuple[SpanKind, str]] = {
    "【": (SpanKind.KEYWORD, "】"),
    "《": (SpanKind.GUILLEMET, "》"),
    "〔": (SpanKind.QUALIFIER, "〕"),
    "『": (SpanKind.TIMING, "』"),
    "「": (SpanKind.NAME, "」"),
}
FAMILY_LABEL = "系統："

_TOKEN = r"<\s*k\s*(\d+)\s*/\s*>"
_TOKEN_RE = re.compile(_TOKEN)
_RESIDUE_RE = re.compile(r"<\s*/?\s*k|/\s*>")
_QUOTED_RE = re.compile(rf"([\"“「‘])\s*({_TOKEN})\s*([\"”」’])")
_QUOTE_PAIRS = {'"': '"', "“": "”", "「": "」", "‘": "’"}


def token(index: int) -> str:
    """The placeholder for span ``index`` of a line."""
    return f"<k{index}/>"


def span_pattern(glyphs: Iterable[str]) -> re.Pattern[str]:
    """Regex of protected spans; a symbol glyph only counts as part of a run of two or more."""
    parts = [f"{re.escape(o)}[^{re.escape(c)}]*{re.escape(c)}" for o, (_, c) in _BRACKETS.items()]
    parts.append(re.escape(FAMILY_LABEL))
    cls = "".join(re.escape(g) for g in dict.fromkeys(glyphs))
    if cls:
        parts.append(f"[{cls}]{{2,}}")
    return re.compile("|".join(parts))


def _span(text: str) -> Span:
    if text == FAMILY_LABEL:
        return Span(SpanKind.FAMILY_LABEL, text, "")
    bracket = _BRACKETS.get(text[0])
    if bracket is None:
        return Span(SpanKind.SYMBOLS, text, text)
    return Span(bracket[0], text, text[1:-1])


def protect(line: str, pattern: re.Pattern[str]) -> tuple[str, list[Span]]:
    """Replace each protected span of ``line`` by its token; return (masked, spans)."""
    spans: list[Span] = []

    def sub(m: re.Match[str]) -> str:
        spans.append(_span(m.group(0)))
        return token(len(spans) - 1)

    return pattern.sub(sub, line), spans


def _unquote(m: re.Match[str]) -> str:
    return m.group(2) if _QUOTE_PAIRS[m.group(1)] == m.group(4) else m.group(0)


def validate(translated: str, spans: Sequence[Span]) -> str | None:
    """The translated line with canonical tokens, or ``None`` when it is not valid.

    Valid: the multiset of tokens equals the one sent (order is free) and no marker residue
    is left. Quotes the model put around a token are removed, but only symmetric pairs, so a
    real ``'`` stays.
    """
    text = _QUOTED_RE.sub(_unquote, translated)
    found = Counter(int(m.group(1)) for m in _TOKEN_RE.finditer(text))
    if found != Counter(range(len(spans))):
        return None
    if _RESIDUE_RE.search(_TOKEN_RE.sub("", text)):
        return None
    text = _TOKEN_RE.sub(lambda m: token(int(m.group(1))), text).strip()
    return text or None


class TermResolver(Protocol):
    """Gives the canonical English of a protected span."""

    def resolve(self, kind: SpanKind, jp: str) -> str | None:
        """English for ``jp`` (the text inside the brackets; the glyph run for ``SYMBOLS``).

        ``None`` means unknown: the span keeps its Japanese.
        """
        ...


def identity(text: str) -> str:
    """The default romaniser: leaves the Japanese as it is."""
    return text


def kakasi_romaniser() -> Callable[[str], str]:
    """Hepburn romaniser backed by ``pykakasi`` (optional ``mt`` group, imported here).

    Raises ``ImportError`` when ``pykakasi`` is not installed.
    """
    kks = importlib.import_module("pykakasi").kakasi()

    def romanise(jp: str) -> str:
        words = (item["hepburn"] for item in kks.convert(jp))
        return " ".join(w[:1].upper() + w[1:] for w in words if w)

    return romanise


class GlossaryResolver:
    """Resolves spans from the glossaries, the card name map and the timing map.

    Bracketed terms: ``keywords``, ``card_types``, then ``timings``. ``「…」``: a family
    ``en``, then ``card_names``, then ``romanise(jp)`` (never unknown). ``系統：`` is
    ``Family:``. A glyph run is the symbols' ``en`` joined by spaces, unknown if any glyph
    is not a symbol.
    """

    def __init__(
        self,
        glossary: Glossary,
        *,
        card_names: Mapping[str, str] | None = None,
        timings: Mapping[str, str] | None = None,
        romanise: Callable[[str], str] = identity,
    ) -> None:
        self._glossary = glossary
        self._card_names = card_names or {}
        self._timings = timings or {}
        self._romanise = romanise

    def resolve(self, kind: SpanKind, jp: str) -> str | None:
        if kind is SpanKind.FAMILY_LABEL:
            return "Family:"
        if kind is SpanKind.NAME:
            return self._name(jp)
        if kind is SpanKind.SYMBOLS:
            entries = [self._glossary.lookup("symbols", g) for g in jp]
            if any(e is None for e in entries):
                return None
            return " ".join(e.en for e in entries if e is not None)
        for glossary_kind in ("keywords", "card_types"):
            entry = self._glossary.lookup(glossary_kind, jp)
            if entry is not None and entry.en:
                return entry.en
        return self._timings.get(jp)

    def _name(self, jp: str) -> str:
        family = self._glossary.lookup("families", jp)
        if isinstance(family, FamilyEntry) and family.en:
            return family.en
        return self._card_names.get(jp) or self._romanise(jp)


def _render(span: Span, resolver: TermResolver) -> str:
    en = resolver.resolve(span.kind, span.inner)
    if en is None:
        return span.text
    if span.kind in (SpanKind.FAMILY_LABEL, SpanKind.SYMBOLS):
        return en
    return f"{span.text[0]}{en}{span.text[-1]}"


def restore(validated: str, spans: Sequence[Span], resolver: TermResolver) -> str:
    """Replace each token of a validated line by the rendering of its span."""
    return _TOKEN_RE.sub(lambda m: _render(spans[int(m.group(1))], resolver), validated)
