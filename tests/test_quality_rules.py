"""Every quality rule has a failing case, and the clean data set triggers none (#122)."""

import sqlite3
from collections.abc import Callable

import pytest
from quality_support import clean_db

from bs_database.build.quality import RULES, Severity, run_rules

Mutation = Callable[[sqlite3.Connection], None]


def _sql(*statements: str) -> Mutation:
    def mutate(conn: sqlite3.Connection) -> None:
        for statement in statements:
            conn.execute(statement)

    return mutate


# rule id -> a mutation of the clean data set that makes exactly that rule fire
FAILING: dict[str, Mutation] = {
    "Q001": _sql("INSERT INTO card_numbers (number, card_id) VALUES ('X-1', 99)"),
}


def test_clean_data_set_has_no_findings() -> None:
    assert run_rules(clean_db()) == []


def test_every_rule_has_a_failing_case() -> None:
    assert sorted(FAILING) == sorted(r.id for r in RULES)


def test_rule_ids_are_unique_and_follow_the_severity_ranges() -> None:
    ids = [r.id for r in RULES]
    assert len(ids) == len(set(ids))
    ranges = {
        Severity.ERROR: range(1, 30),
        Severity.WARNING: range(30, 50),
        Severity.INFO: range(50, 100),
    }
    for r in RULES:
        assert r.id.startswith("Q") and int(r.id[1:]) in ranges[r.severity], r.id


@pytest.mark.parametrize("rule_id", sorted(FAILING))
def test_rule_fires_on_its_failing_case(rule_id: str) -> None:
    conn = clean_db()
    FAILING[rule_id](conn)
    findings = run_rules(conn)
    assert rule_id in {f.id for f in findings}
    assert all(f.count >= 1 and f.examples for f in findings)


def test_examples_are_capped_and_the_count_is_complete() -> None:
    conn = clean_db()
    for i in range(5):
        conn.execute(f"INSERT INTO card_numbers (number, card_id) VALUES ('X-{i}', 99)")
    (finding,) = run_rules(conn)
    assert finding.count == 5
    assert len(finding.examples) == 3
