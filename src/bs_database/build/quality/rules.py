"""The registry of quality rules (#122). Ids: Q0xx errors, Q03x warnings, Q05x info.

Every query returns one row per violation, the first column being a short example, and has a
stable ``ORDER BY`` so the report is deterministic.
"""

from bs_database.build.quality.model import Rule, Severity

E, W, I = Severity.ERROR, Severity.WARNING, Severity.INFO  # noqa: E741

# A card has English text when its name or its flavor text has some; the other tables have one
# text column each. ``en_text`` is NULL or blank when there is none (ADR 0005).
_ENGLISH = """
WITH t(kind, id, en, source_id, status_id) AS (
    SELECT 'card', id, coalesce(nullif(trim(name_en), ''), nullif(trim(flavor_text_en), '')),
           en_source_id, en_status_id FROM cards
    UNION ALL SELECT 'effect', id, nullif(trim(text_en), ''), en_source_id, en_status_id
              FROM card_effects
    UNION ALL SELECT 'product', id, nullif(trim(name_en), ''), en_source_id, en_status_id
              FROM products
    UNION ALL SELECT 'family', id, nullif(trim(name_en), ''), en_source_id, en_status_id
              FROM families
    UNION ALL SELECT 'brave', card_id, nullif(trim(fusion_condition_en), ''), en_source_id,
                     en_status_id FROM brave_details
    UNION ALL SELECT 'ultimate', card_id, nullif(trim(summon_condition_en), ''), en_source_id,
                     en_status_id FROM ultimate_details
)
SELECT t.kind || ' ' || t.id FROM t JOIN translation_statuses s ON s.id = t.status_id
WHERE {where} ORDER BY t.kind, t.id
"""

RULES: tuple[Rule, ...] = (
    Rule("Q001", E, "A foreign key points to a missing row", "PRAGMA foreign_key_check"),
    Rule(
        "Q002",
        E,
        "A card has no card number",
        "SELECT 'card ' || c.id || ' ' || c.name_jp FROM cards c"
        " WHERE NOT EXISTS (SELECT 1 FROM card_numbers n WHERE n.card_id = c.id) ORDER BY c.id",
    ),
    Rule(
        "Q003",
        E,
        "A card number has no printing",
        "SELECT n.number FROM card_numbers n"
        " WHERE NOT EXISTS (SELECT 1 FROM printings p WHERE p.card_number_id = n.id)"
        " ORDER BY n.number",
    ),
    Rule(
        "Q004",
        E,
        "A card has a blank Japanese name",
        "SELECT 'card ' || id FROM cards WHERE trim(name_jp) = '' ORDER BY id",
    ),
    Rule(
        "Q005",
        E,
        "An effect has blank text",
        "SELECT c.name_jp || ' #' || e.position FROM card_effects e"
        " JOIN cards c ON c.id = e.card_id WHERE trim(e.text_jp) = '' ORDER BY e.id",
    ),
    Rule(
        "Q006",
        E,
        "A product has a blank Japanese name",
        "SELECT 'product ' || id || coalesce(' ' || code, '') FROM products"
        " WHERE trim(name_jp) = '' ORDER BY id",
    ),
    Rule(
        "Q007",
        E,
        "A card has no levels (or a magic card has some)",
        "SELECT c.name_jp || ' ' || t.code FROM cards c JOIN card_types t ON t.id = c.card_type_id"
        " WHERE (t.code = 'magic') = EXISTS (SELECT 1 FROM card_levels l WHERE l.card_id = c.id)"
        " ORDER BY c.id",
    ),
    Rule(
        "Q008",
        E,
        "A brave or ultimate card lacks its details row, or another card has one",
        "SELECT c.name_jp || ' ' || t.code FROM cards c JOIN card_types t ON t.id = c.card_type_id"
        " WHERE (t.code = 'brave') != EXISTS (SELECT 1 FROM brave_details d WHERE d.card_id = c.id)"
        " OR (t.code = 'ultimate') != EXISTS"
        " (SELECT 1 FROM ultimate_details d WHERE d.card_id = c.id) ORDER BY c.id",
    ),
    Rule(
        "Q009",
        E,
        "A card that is not magic has no colour",
        "SELECT c.name_jp FROM cards c JOIN card_types t ON t.id = c.card_type_id"
        " WHERE t.code != 'magic'"
        " AND NOT EXISTS (SELECT 1 FROM card_colors k WHERE k.card_id = c.id) ORDER BY c.id",
    ),
    Rule(
        "Q010",
        E,
        "A card or a product has no source page",
        "SELECT 'card ' || c.id || ' ' || c.name_jp FROM cards c"
        " WHERE NOT EXISTS (SELECT 1 FROM card_source_pages s WHERE s.card_id = c.id)"
        " UNION ALL SELECT 'product ' || p.id || ' ' || p.name_jp FROM products p"
        " WHERE NOT EXISTS (SELECT 1 FROM product_source_pages s WHERE s.product_id = p.id)"
        " ORDER BY 1",
    ),
    Rule(
        "Q011",
        E,
        "An effect is linked to a level of another card",
        "SELECT c.name_jp || ' #' || e.position || ' Lv' || l.level FROM card_effect_levels x"
        " JOIN card_effects e ON e.id = x.card_effect_id"
        " JOIN card_levels l ON l.id = x.card_level_id"
        " JOIN cards c ON c.id = e.card_id WHERE l.card_id != e.card_id ORDER BY e.id, l.level",
    ),
    Rule(
        "Q012",
        E,
        "The effect positions of a card do not run 1..n",
        "SELECT c.name_jp FROM card_effects e JOIN cards c ON c.id = e.card_id"
        " GROUP BY e.card_id HAVING min(e.position) != 1 OR max(e.position) != count(*)"
        " ORDER BY e.card_id",
    ),
    Rule(
        "Q013",
        E,
        "A level or constant effect is linked to no level",
        "SELECT c.name_jp || ' #' || e.position FROM card_effects e"
        " JOIN effect_kinds k ON k.id = e.effect_kind_id JOIN cards c ON c.id = e.card_id"
        " WHERE k.code IN ('level', 'constant')"
        " AND NOT EXISTS (SELECT 1 FROM card_effect_levels x WHERE x.card_effect_id = e.id)"
        " ORDER BY e.id",
    ),
    Rule(
        "Q014",
        E,
        "A cost is outside 0..50",
        "SELECT name_jp || ' cost ' || cost FROM cards WHERE cost NOT BETWEEN 0 AND 50 ORDER BY id",
    ),
    Rule(
        "Q015",
        E,
        "A level is outside 1..10",
        "SELECT c.name_jp || ' Lv' || l.level FROM card_levels l JOIN cards c ON c.id = l.card_id"
        " WHERE l.level NOT BETWEEN 1 AND 10 ORDER BY l.id",
    ),
    Rule(
        "Q016",
        E,
        "Cores are outside 0..30",
        "SELECT c.name_jp || ' Lv' || l.level || ' cores ' || l.cores FROM card_levels l"
        " JOIN cards c ON c.id = l.card_id"
        " WHERE l.cores IS NOT NULL AND l.cores NOT BETWEEN 0 AND 30 ORDER BY l.id",
    ),
    Rule(
        "Q017",
        E,
        "Battle points are outside 1..999999",
        "SELECT c.name_jp || ' Lv' || l.level || ' BP ' || l.battle_points FROM card_levels l"
        " JOIN cards c ON c.id = l.card_id WHERE l.battle_points IS NOT NULL"
        " AND l.battle_points NOT BETWEEN 1 AND 999999 ORDER BY l.id",
    ),
    Rule(
        "Q018",
        E,
        "A symbol or reduction count is outside 1..9, or a card has more than 9 symbols",
        "SELECT c.name_jp || ' symbol ' || s.count FROM card_symbols s"
        " JOIN cards c ON c.id = s.card_id WHERE s.count NOT BETWEEN 1 AND 9"
        " UNION ALL SELECT c.name_jp || ' reduction ' || r.count FROM card_reductions r"
        " JOIN cards c ON c.id = r.card_id WHERE r.count NOT BETWEEN 1 AND 9"
        " UNION ALL SELECT c.name_jp || ' symbols ' || sum(s.count) FROM card_symbols s"
        " JOIN cards c ON c.id = s.card_id GROUP BY s.card_id HAVING sum(s.count) > 9 ORDER BY 1",
    ),
    Rule(
        "Q019",
        E,
        "A date is not YYYY-MM-DD, or a timestamp is not ISO 8601 (built_at: UTC with Z)",
        "SELECT 'product ' || id || ' ' || release_date FROM products"
        " WHERE release_date IS NOT NULL"
        " AND (date(release_date) IS NULL OR date(release_date) != release_date)"
        " UNION ALL SELECT 'page ' || id || ' ' || fetched_at FROM source_pages"
        " WHERE datetime(fetched_at) IS NULL"
        " UNION ALL SELECT 'schema_meta built_at ' || built_at FROM schema_meta"
        " WHERE built_at NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T"
        "[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z' OR datetime(built_at) IS NULL ORDER BY 1",
    ),
    Rule(
        "Q020",
        E,
        "English text with a pending or failed status (ADR 0005)",
        _ENGLISH.format(where="en IS NOT NULL AND s.code IN ('pending', 'failed')"),
    ),
    Rule(
        "Q021",
        E,
        "A machine or reviewed status without English text (ADR 0005)",
        _ENGLISH.format(where="en IS NULL AND s.code IN ('machine', 'reviewed')"),
    ),
    Rule(
        "Q022",
        E,
        "English text without a source, or a source without English text (ADR 0005)",
        _ENGLISH.format(where="(en IS NOT NULL) != (source_id IS NOT NULL)"),
    ),
    Rule(
        "Q023",
        E,
        "Two products without a code share a name, which UNIQUE(code) does not catch",
        "SELECT name_jp FROM products WHERE code IS NULL"
        " GROUP BY name_jp HAVING count(*) > 1 ORDER BY name_jp",
    ),
    Rule(
        "Q030",
        W,
        "A card has no English name",
        "SELECT name_jp FROM cards WHERE nullif(trim(name_en), '') IS NULL ORDER BY id",
    ),
    Rule(
        "Q031",
        W,
        "A product has no English name",
        "SELECT name_jp FROM products"
        " WHERE nullif(trim(name_en), '') IS NULL AND trim(name_jp) != '' ORDER BY id",
    ),
    Rule(
        "Q032",
        W,
        "A family has no English name",
        "SELECT name_jp FROM families WHERE nullif(trim(name_en), '') IS NULL ORDER BY id",
    ),
    Rule(
        "Q033",
        W,
        "A family is used by no card",
        "SELECT f.name_jp FROM families f"
        " WHERE NOT EXISTS (SELECT 1 FROM card_families x WHERE x.family_id = f.id) ORDER BY f.id",
    ),
    Rule(
        "Q034",
        W,
        "A keyword is used by no effect",
        "SELECT k.name FROM keywords k"
        " WHERE NOT EXISTS (SELECT 1 FROM card_effect_keywords x WHERE x.keyword_id = k.id)"
        " ORDER BY k.id",
    ),
    Rule(
        "Q036",
        W,
        "A spirit level has no battle points",
        "SELECT c.name_jp || ' Lv' || l.level FROM card_levels l"
        " JOIN cards c ON c.id = l.card_id JOIN card_types t ON t.id = c.card_type_id"
        " WHERE t.code = 'spirit' AND l.battle_points IS NULL ORDER BY l.id",
    ),
    Rule(
        "Q037",
        W,
        "The cores of a card decrease from one level to a higher one",
        "SELECT c.name_jp || ' Lv' || a.level || ' ' || a.cores || ' > Lv' || b.level || ' '"
        " || b.cores FROM card_levels a JOIN card_levels b ON b.card_id = a.card_id"
        " AND b.level > a.level AND b.cores < a.cores JOIN cards c ON c.id = a.card_id"
        " ORDER BY a.id, b.id",
    ),
    Rule(
        "Q038",
        W,
        "A source page is linked to no card and no product",
        "SELECT p.url FROM source_pages p"
        " WHERE NOT EXISTS (SELECT 1 FROM card_source_pages x WHERE x.source_page_id = p.id)"
        " AND NOT EXISTS (SELECT 1 FROM product_source_pages x WHERE x.source_page_id = p.id)"
        " ORDER BY p.id",
    ),
    Rule(
        "Q039",
        W,
        "The levels of a card have a gap",
        "SELECT c.name_jp FROM card_levels l JOIN cards c ON c.id = l.card_id"
        " GROUP BY l.card_id HAVING max(l.level) - min(l.level) + 1 != count(*)"
        " ORDER BY l.card_id",
    ),
    Rule(
        "Q050",
        I,
        "An effect has no English text yet (ADR 0005, text first)",
        "SELECT c.name_jp || ' #' || e.position FROM card_effects e"
        " JOIN cards c ON c.id = e.card_id WHERE nullif(trim(e.text_en), '') IS NULL"
        " ORDER BY e.id",
    ),
    Rule(
        "Q051",
        I,
        "An effect of kind other starts with a level, which the normalizer does not parse (#133)",
        "SELECT c.name_jp || ' #' || e.position || ' ' || substr(e.text_jp, 1, 12)"
        " FROM card_effects e JOIN cards c ON c.id = e.card_id"
        " JOIN effect_kinds k ON k.id = e.effect_kind_id"
        " WHERE k.code = 'other' AND e.text_jp LIKE 'Lv%' ORDER BY e.id",
    ),
    Rule(
        "Q052",
        I,
        "A symbol has a colour that is not one of the card colours",
        "SELECT c.name_jp || ' ' || y.code FROM card_symbols s JOIN cards c ON c.id = s.card_id"
        " JOIN symbols y ON y.id = s.symbol_id WHERE y.color_id IS NOT NULL"
        " AND NOT EXISTS (SELECT 1 FROM card_colors k WHERE k.card_id = s.card_id"
        " AND k.color_id = y.color_id) ORDER BY s.card_id, y.id",
    ),
    Rule(
        "Q053",
        I,
        "A printing has no image",
        "SELECT n.number || ' ' || p.product_id FROM printings p"
        " JOIN card_numbers n ON n.id = p.card_number_id"
        " WHERE NOT EXISTS (SELECT 1 FROM printing_images i WHERE i.printing_id = p.id)"
        " ORDER BY p.id",
    ),
    Rule(
        "Q054",
        I,
        "A card has no image on any printing",
        "SELECT c.name_jp FROM cards c WHERE NOT EXISTS (SELECT 1 FROM card_numbers n"
        " JOIN printings p ON p.card_number_id = n.id JOIN printing_images i"
        " ON i.printing_id = p.id WHERE n.card_id = c.id) ORDER BY c.id",
    ),
    Rule(
        "Q055",
        I,
        "A spirit, brave or ultimate card has no effects",
        "SELECT c.name_jp FROM cards c JOIN card_types t ON t.id = c.card_type_id"
        " WHERE t.code IN ('spirit', 'brave', 'ultimate')"
        " AND NOT EXISTS (SELECT 1 FROM card_effects e WHERE e.card_id = c.id) ORDER BY c.id",
    ),
)


def rule(rule_id: str) -> Rule:
    """The rule with ``rule_id`` (``KeyError`` when unknown)."""
    for r in RULES:
        if r.id == rule_id:
            return r
    raise KeyError(rule_id)
