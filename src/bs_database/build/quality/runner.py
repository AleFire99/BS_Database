"""Run the quality rules on an open connection (#122)."""

import sqlite3
from collections.abc import Sequence

from bs_database.build.quality.model import MAX_EXAMPLES, Finding, Rule
from bs_database.build.quality.rules import RULES


def _example(row: Sequence[object]) -> str:
    return " ".join(str(v) for v in row)


def run_rules(conn: sqlite3.Connection, rules: Sequence[Rule] = RULES) -> list[Finding]:
    """One finding per rule that has violations, in the order of ``rules``."""
    findings: list[Finding] = []
    for rule in rules:
        rows = conn.execute(rule.sql).fetchall()
        if rows:
            examples = tuple(_example(r) for r in rows[:MAX_EXAMPLES])
            findings.append(
                Finding(rule.id, rule.severity, "rule", rule.title, len(rows), examples)
            )
    return findings
