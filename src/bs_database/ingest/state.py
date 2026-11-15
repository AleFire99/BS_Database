"""Ingestion run state and resume (#72): state machine and SQLite store."""

from __future__ import annotations

from enum import StrEnum


class IngestState(StrEnum):
    """Lifecycle stage of one page."""

    DISCOVERED = "discovered"
    FETCHED = "fetched"
    PARSED = "parsed"
    NORMALIZED = "normalized"
    TRANSLATED = "translated"
    LOADED = "loaded"
    FAILED = "failed"


class PageKind(StrEnum):
    """Kind of page tracked by the store."""

    INDEX = "index"
    SET = "set"
    CARD = "card"


S = IngestState

_CHAIN = (S.DISCOVERED, S.FETCHED, S.PARSED, S.NORMALIZED, S.TRANSLATED, S.LOADED)
_STAGES = _CHAIN[:-1]

TRANSITIONS: dict[IngestState, frozenset[IngestState]] = {
    S.DISCOVERED: frozenset({S.FETCHED, S.FAILED}),
    S.FETCHED: frozenset({S.PARSED, S.FAILED}),
    S.PARSED: frozenset({S.NORMALIZED, S.FAILED}),
    S.NORMALIZED: frozenset({S.TRANSLATED, S.FAILED}),
    S.TRANSLATED: frozenset({S.LOADED, S.FAILED}),
    S.LOADED: frozenset(),
    S.FAILED: frozenset(_STAGES),
}


class IllegalTransition(ValueError):
    """Raised when a state change is not allowed by TRANSITIONS."""


def check_transition(src: IngestState, dst: IngestState) -> None:
    """Raise IllegalTransition unless src -> dst is in the table."""
    if dst not in TRANSITIONS[src]:
        raise IllegalTransition(f"{src.value} -> {dst.value} is not allowed")
