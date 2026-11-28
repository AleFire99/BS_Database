"""Term protection around machine translation (#156, ADR 0012): mask, validate, restore.

Pure functions, no engine. A line is masked by replacing each protected span (``【…】``,
``《…》``, ``〔…〕``, ``『…』``, ``「…」``, ``系統：``, a run of symbol glyphs) with a token
``<k0/>`` numbered per line. The engine translates the masked line; ``validate`` checks the
tokens came back intact and ``restore`` puts the canonical English back (added with the
resolver in a later step).
"""

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum


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
