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
    "Q002": _sql(
        "INSERT INTO cards (id, card_type_id, cost, name_jp) VALUES (2, 2, 1, 'マジック')"
    ),
    "Q003": _sql("INSERT INTO card_numbers (number, card_id) VALUES ('BS01-002', 1)"),
    "Q004": _sql("UPDATE cards SET name_jp = ' '"),
    "Q005": _sql("UPDATE card_effects SET text_jp = '' WHERE id = 1"),
    "Q006": _sql("UPDATE products SET name_jp = ''"),
    "Q007": _sql("DELETE FROM card_effect_levels", "DELETE FROM card_levels"),
    "Q008": _sql("INSERT INTO brave_details (card_id) VALUES (1)"),
    "Q009": _sql("DELETE FROM card_colors"),
    "Q010": _sql("DELETE FROM card_source_pages"),
    "Q011": _sql(
        "INSERT INTO cards (id, card_type_id, cost, name_jp) VALUES (2, 1, 1, 'もう一枚')",
        "INSERT INTO card_levels (id, card_id, level) VALUES (3, 2, 1)",
        "INSERT INTO card_effect_levels (card_effect_id, card_level_id) VALUES (2, 3)",
    ),
    "Q012": _sql("UPDATE card_effects SET position = 5 WHERE id = 2"),
    "Q013": _sql("DELETE FROM card_effect_levels"),
    "Q020": _sql("UPDATE families SET en_status_id = 1"),
    "Q021": _sql("UPDATE families SET name_en = NULL, en_source_id = NULL"),
    "Q022": _sql("UPDATE families SET en_source_id = NULL"),
    "Q023": _sql(
        "UPDATE products SET code = NULL",
        "INSERT INTO products (id, name_jp, product_type_id) VALUES (2, 'ブースター', 1)",
    ),
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
    (finding,) = [f for f in run_rules(conn) if f.id == "Q001"]
    assert finding.count == 5
    assert len(finding.examples) == 3
