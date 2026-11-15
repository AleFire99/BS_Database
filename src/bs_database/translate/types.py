"""Translator protocol and result type (#94, ADR 0008)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

Lang = Literal["jp", "en"]
# ADR 0005 translation status codes
Status = Literal["machine", "failed", "pending"]

LANGS: frozenset[str] = frozenset({"jp", "en"})


@dataclass(frozen=True)
class TranslationResult:
    """One translated text. ``text`` is None unless ``status`` is ``machine``."""

    text: str | None
    status: Status
    engine: str


class Translator(Protocol):
    """A translation engine.

    ``translate`` returns one result per input text, in the same order. It never raises on
    engine errors (they become ``failed`` results); an unsupported language pair is a
    programming error and raises ``ValueError``.
    """

    name: str

    def translate(
        self, texts: Sequence[str], *, src: Lang = "jp", tgt: Lang = "en"
    ) -> list[TranslationResult]: ...


def check_pair(src: str, tgt: str) -> None:
    """Raise ``ValueError`` unless ``src`` and ``tgt`` are different supported languages."""
    if src not in LANGS or tgt not in LANGS or src == tgt:
        raise ValueError(f"unsupported language pair: {src!r} -> {tgt!r}")
