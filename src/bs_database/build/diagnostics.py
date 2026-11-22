"""Warnings and errors of one build (#120).

A warning is data that the build repaired or skipped; it never stops the build. Each kind is
counted and keeps a few examples so the CLI can print what happened.
"""

from collections import Counter

_MAX_EXAMPLES = 3


class BuildError(Exception):
    """The build cannot produce a consistent database (bad input, broken invariant)."""


class BuildWarnings:
    """Counts of repaired or skipped data, by kind, with a few examples each."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._examples: dict[str, list[str]] = {}

    def add(self, kind: str, example: str = "") -> None:
        """Count one occurrence of ``kind``; ``example`` is kept for the first few."""
        self._counts[kind] += 1
        shown = self._examples.setdefault(kind, [])
        if example and len(shown) < _MAX_EXAMPLES and example not in shown:
            shown.append(example)

    def counts(self) -> dict[str, int]:
        """Occurrences per kind, sorted by kind."""
        return dict(sorted(self._counts.items()))

    def examples(self, kind: str) -> tuple[str, ...]:
        """The first examples recorded for ``kind``."""
        return tuple(self._examples.get(kind, ()))

    @property
    def total(self) -> int:
        """Occurrences of every kind together."""
        return sum(self._counts.values())
