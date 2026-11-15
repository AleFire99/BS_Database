"""Tests for the ingestion state machine and store (#72)."""

from __future__ import annotations

import itertools

import pytest

from bs_database.ingest.state import (
    TRANSITIONS,
    IllegalTransition,
    IngestState,
    check_transition,
)

S = IngestState
CHAIN = [S.DISCOVERED, S.FETCHED, S.PARSED, S.NORMALIZED, S.TRANSLATED, S.LOADED]
ALL_PAIRS = list(itertools.product(IngestState, IngestState))


def test_forward_chain_is_legal() -> None:
    for src, dst in itertools.pairwise(CHAIN):
        check_transition(src, dst)


@pytest.mark.parametrize(("src", "dst"), ALL_PAIRS)
def test_every_pair_matches_table(src: IngestState, dst: IngestState) -> None:
    if dst in TRANSITIONS[src]:
        check_transition(src, dst)
    else:
        with pytest.raises(IllegalTransition):
            check_transition(src, dst)


def test_all_pairs_count() -> None:
    assert len(ALL_PAIRS) == 49


@pytest.mark.parametrize("src", CHAIN[:-1])
def test_non_terminal_can_fail(src: IngestState) -> None:
    check_transition(src, S.FAILED)


def test_skips_backward_and_terminal_are_illegal() -> None:
    for src, dst in [
        (S.DISCOVERED, S.PARSED),
        (S.PARSED, S.FETCHED),
        (S.LOADED, S.DISCOVERED),
        (S.LOADED, S.FAILED),
        (S.FAILED, S.LOADED),
    ]:
        with pytest.raises(IllegalTransition):
            check_transition(src, dst)
