"""The documented state diagram must match the code (#72)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from bs_database.ingest.state import TRANSITIONS, IngestState

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "architecture" / "ingestion-state.md"
EDGE = re.compile(r"^\s*(\[\*\]|\w+)\s*-->\s*(\[\*\]|\w+)\s*(?::.*)?$")


def _first_mermaid_block() -> list[str]:
    match = re.search(r"```mermaid\s*\n(.*?)\n\s*```", DOC.read_text(), re.DOTALL)
    assert match, "no mermaid block"
    return match.group(1).splitlines()


def _parse() -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for line in _first_mermaid_block():
        m = EDGE.match(line)
        if m:
            edges.add((m.group(1), m.group(2)))
    return edges


def test_diagram_edges_match_transition_table() -> None:
    edges = _parse()
    assert ("[*]", "discovered") in edges
    assert ("loaded", "[*]") in edges
    real = {(a, b) for a, b in edges if "[*]" not in (a, b)}
    expected = {(src.value, dst.value) for src, dsts in TRANSITIONS.items() for dst in dsts}
    assert real == expected


def test_diagram_nodes_match_enum() -> None:
    nodes = {n for edge in _parse() for n in edge} - {"[*]"}
    assert nodes == {s.value for s in IngestState}


def test_state_dir_is_gitignored() -> None:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "data/state/ingest.db"],
            cwd=ROOT,
            check=False,
        )
    except FileNotFoundError:
        pytest.skip("git not available")
    assert result.returncode == 0
