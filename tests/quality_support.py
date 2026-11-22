"""A minimal, fully valid database for the quality rule tests (#122).

``clean_db`` has one of everything and violates no rule of any severity. A test applies one
mutation and checks that exactly the rule under test starts to fire.
"""

import sqlite3

from bs_database.schema import load_schema_sql

CLEAN_SQL = """
INSERT INTO card_types (id, code, name) VALUES
    (1, 'spirit', 'Spirit'), (2, 'magic', 'Magic'), (3, 'nexus', 'Nexus'),
    (4, 'brave', 'Brave'), (5, 'ultimate', 'Ultimate');
INSERT INTO colors (id, code, name) VALUES (1, 'red', 'Red'), (2, 'blue', 'Blue');
INSERT INTO symbols (id, code, name, color_id) VALUES (1, 'red', 'Red', 1), (2, 'blue', 'Blue', 2);
INSERT INTO product_types (id, code, name) VALUES (1, 'booster', 'Booster');
INSERT INTO rarities (id, code, name, sort_order) VALUES (1, 'c', 'Common', 1);
INSERT INTO effect_kinds (id, code, name) VALUES (1, 'level', 'Level'), (2, 'other', 'Other');
INSERT INTO keywords (id, code, name) VALUES (1, 'kw', 'Keyword');

INSERT INTO families (id, code, name_jp, name_en, en_source_id, en_status_id)
    VALUES (1, 'fam', 'ファミリー', 'Family', 4, 3);

-- a spirit with two levels, effects, a family, a printing and an image
INSERT INTO cards (id, card_type_id, cost, name_jp, name_en, en_source_id, en_status_id)
    VALUES (1, 1, 3, 'スピリット', 'Spirit', 1, 3);
INSERT INTO card_numbers (id, number, card_id) VALUES (1, 'BS01-001', 1);
INSERT INTO card_colors (card_id, color_id) VALUES (1, 1);
INSERT INTO card_symbols (card_id, symbol_id, count) VALUES (1, 1, 1);
INSERT INTO card_reductions (card_id, symbol_id, count) VALUES (1, 1, 1);
INSERT INTO card_families (card_id, family_id) VALUES (1, 1);
INSERT INTO card_levels (id, card_id, level, cores, battle_points) VALUES
    (1, 1, 1, 1, 1000), (2, 1, 2, 2, 3000);
INSERT INTO card_effects (id, card_id, position, effect_kind_id, text_jp, text_en, en_source_id,
                          en_status_id) VALUES
    (1, 1, 1, 1, '効果', 'Effect', 5, 2),
    (2, 1, 2, 2, '別の効果', 'Other effect', 5, 2);
INSERT INTO card_effect_levels (card_effect_id, card_level_id) VALUES (1, 1), (1, 2);
INSERT INTO card_effect_keywords (card_effect_id, keyword_id) VALUES (1, 1);

INSERT INTO products (id, code, name_jp, name_en, product_type_id, release_date, en_source_id,
                      en_status_id)
    VALUES (1, 'BS01', 'ブースター', 'Booster', 1, '2026-01-01', 5, 2);
INSERT INTO printings (id, card_number_id, product_id, rarity_id) VALUES (1, 1, 1, 1);
INSERT INTO printing_images (id, printing_id, image_size_id, source_url)
    VALUES (1, 1, 2, 'https://example.test/1.png');

INSERT INTO source_pages (id, source_id, url, fetched_at, content_sha256, parser_version)
    VALUES (1, 1, 'https://example.test/card/1', '2026-01-01T00:00:00Z', '{sha}', '2.1.0');
INSERT INTO card_source_pages (card_id, source_page_id) VALUES (1, 1);
INSERT INTO product_source_pages (product_id, source_page_id) VALUES (1, 1);
"""


def clean_db() -> sqlite3.Connection:
    """An in-memory database built from ``schema.sql`` with the valid mini data set."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.executescript(load_schema_sql())
    conn.executescript(CLEAN_SQL.replace("{sha}", "a" * 64))
    conn.execute("PRAGMA foreign_keys = OFF")  # mutations may break references on purpose
    return conn
