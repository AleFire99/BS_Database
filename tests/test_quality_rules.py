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
    "Q014": _sql("UPDATE cards SET cost = 51"),
    "Q015": _sql("UPDATE card_levels SET level = 11 WHERE id = 2"),
    "Q016": _sql("UPDATE card_levels SET cores = 31 WHERE id = 2"),
    "Q017": _sql("UPDATE card_levels SET battle_points = 1000000 WHERE id = 2"),
    "Q018": _sql("UPDATE card_symbols SET count = 10"),
    "Q019": _sql("UPDATE products SET release_date = '2026-13-01'"),
    "Q020": _sql("UPDATE families SET en_status_id = 1"),
    "Q021": _sql("UPDATE families SET name_en = NULL, en_source_id = NULL"),
    "Q022": _sql("UPDATE families SET en_source_id = NULL"),
    "Q023": _sql(
        "UPDATE products SET code = NULL",
        "INSERT INTO products (id, name_jp, product_type_id) VALUES (2, 'ブースター', 1)",
    ),
    "Q030": _sql("UPDATE cards SET name_en = NULL"),
    "Q031": _sql("UPDATE products SET name_en = NULL"),
    "Q032": _sql("UPDATE families SET name_en = NULL"),
    "Q033": _sql("INSERT INTO families (id, name_jp) VALUES (2, '孤児')"),
    "Q034": _sql("INSERT INTO keywords (id, code, name) VALUES (2, 'orphan', 'Orphan')"),
    "Q036": _sql("UPDATE card_levels SET battle_points = NULL WHERE id = 2"),
    "Q037": _sql("UPDATE card_levels SET cores = 0 WHERE id = 2"),
    "Q038": _sql(
        "INSERT INTO source_pages (id, source_id, url, fetched_at, content_sha256, parser_version)"
        " VALUES (2, 1, 'https://example.test/orphan', '2026-01-01T00:00:00Z', 'b', '2.1.0')"
    ),
    "Q039": _sql("UPDATE card_levels SET level = 4 WHERE id = 2"),
    "Q040": _sql("UPDATE printings SET note_jp = '新規イラスト「」' WHERE id = 1"),
    "Q050": _sql("UPDATE card_effects SET text_en = NULL WHERE id = 1"),
    "Q051": _sql("UPDATE card_effects SET text_jp = 'Lv1-2『召喚時』効果' WHERE id = 2"),
    "Q052": _sql("UPDATE card_colors SET color_id = 2"),
    "Q053": _sql(
        "INSERT INTO card_numbers (id, number, card_id) VALUES (2, 'BS01-002', 1)",
        "INSERT INTO printings (id, card_number_id, product_id) VALUES (2, 2, 1)",
    ),
    "Q054": _sql("DELETE FROM printing_images"),
    "Q055": _sql(
        "DELETE FROM card_effect_levels",
        "DELETE FROM card_effect_keywords",
        "DELETE FROM card_effects",
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


@pytest.mark.parametrize(
    "mutation",
    [
        _sql("UPDATE card_reductions SET count = 10"),
        _sql(
            "UPDATE card_symbols SET count = 5",
            "INSERT INTO card_symbols (card_id, symbol_id, count) VALUES (1, 2, 5)",
        ),
        _sql("UPDATE products SET release_date = '26-1-1'"),
        _sql("UPDATE source_pages SET fetched_at = 'yesterday'"),
        _sql("UPDATE schema_meta SET built_at = 'now'"),
    ],
)
def test_range_and_date_variants_fire_too(mutation: Mutation) -> None:
    conn = clean_db()
    conn.execute(
        "INSERT INTO schema_meta (id, schema_version, data_version, built_at, generator)"
        " VALUES (1, '0.1.0', 'dev', '2026-01-01T00:00:00Z', 'test')"
    )
    mutation(conn)
    assert {f.id for f in run_rules(conn)} & {"Q014", "Q016", "Q017", "Q018", "Q019"}


def test_the_range_boundaries_pass() -> None:
    conn = clean_db()
    conn.execute("UPDATE cards SET cost = 50")
    conn.execute(
        "UPDATE card_levels SET level = 10, cores = 30, battle_points = 999999 WHERE id = 2"
    )
    conn.execute("UPDATE card_symbols SET count = 9")
    conn.execute("UPDATE card_reductions SET count = 9")
    conn.execute("UPDATE card_levels SET cores = NULL, battle_points = NULL WHERE id = 1")
    assert [f for f in run_rules(conn) if f.id in {"Q014", "Q015", "Q016", "Q017", "Q018"}] == []


def test_flavor_provenance_is_checked_apart_from_the_name() -> None:
    conn = clean_db()
    conn.execute("UPDATE cards SET flavor_en_status_id = 3")  # machine, no flavor text
    (finding,) = [f for f in run_rules(conn) if f.id == "Q021"]
    assert finding.examples == ("card flavor 1",)
    conn = clean_db()
    conn.execute("UPDATE cards SET flavor_text_en = 'A hound.', flavor_en_source_id = 3")
    assert {f.id for f in run_rules(conn)} & {"Q020", "Q021", "Q022"} == {"Q020"}
