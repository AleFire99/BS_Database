"""Quality rules and findings (#122).

A rule is a read-only SQL query that returns one row per offending record (first column: a short
human-readable example). The runner counts the rows and keeps the first few as examples.
"""

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    """How a finding is treated: errors fail the build, warnings fail it under ``--strict``."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"  # reported, never fails


SEVERITIES = (Severity.ERROR, Severity.WARNING, Severity.INFO)

MAX_EXAMPLES = 3


@dataclass(frozen=True, slots=True)
class Rule:
    """One check on the finished database: ``sql`` returns a row per violation, ordered."""

    id: str
    severity: Severity
    title: str
    sql: str


@dataclass(frozen=True, slots=True)
class Finding:
    """A rule (or a loader warning kind) that fired: how often, with a few examples."""

    id: str
    severity: Severity
    origin: str  # "rule" or "loader"
    title: str
    count: int
    examples: tuple[str, ...]
