"""The registry of quality rules (#122). Ids: Q0xx errors, Q03x warnings, Q05x info.

Every query returns one row per violation, the first column being a short example, and has a
stable ``ORDER BY`` so the report is deterministic.
"""

from bs_database.build.quality.model import Rule, Severity

E, W, I = Severity.ERROR, Severity.WARNING, Severity.INFO  # noqa: E741

RULES: tuple[Rule, ...] = (
    Rule("Q001", E, "A foreign key points to a missing row", "PRAGMA foreign_key_check"),
)


def rule(rule_id: str) -> Rule:
    """The rule with ``rule_id`` (``KeyError`` when unknown)."""
    for r in RULES:
        if r.id == rule_id:
            return r
    raise KeyError(rule_id)
