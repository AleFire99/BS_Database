PRAGMA foreign_keys = ON;
PRAGMA user_version = 200;

-- Versioning (ADR 0003): exactly one row.
CREATE TABLE schema_meta (
    id INTEGER NOT NULL,
    schema_version TEXT NOT NULL,
    data_version TEXT NOT NULL,
    built_at TEXT NOT NULL,
    source_snapshot TEXT,
    generator TEXT NOT NULL,
    CONSTRAINT pk_schema_meta_id PRIMARY KEY (id),
    CONSTRAINT ck_schema_meta_id CHECK (id = 1)
);

-- Lookups
CREATE TABLE translation_statuses (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    CONSTRAINT pk_translation_statuses_id PRIMARY KEY (id),
    CONSTRAINT uq_translation_statuses_code UNIQUE (code)
);

CREATE TABLE translation_sources (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    CONSTRAINT pk_translation_sources_id PRIMARY KEY (id),
    CONSTRAINT uq_translation_sources_code UNIQUE (code)
);

CREATE TABLE card_types (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    CONSTRAINT pk_card_types_id PRIMARY KEY (id),
    CONSTRAINT uq_card_types_code UNIQUE (code)
);

CREATE TABLE colors (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    CONSTRAINT pk_colors_id PRIMARY KEY (id),
    CONSTRAINT uq_colors_code UNIQUE (code)
);

CREATE TABLE symbols (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    color_id INTEGER,
    CONSTRAINT pk_symbols_id PRIMARY KEY (id),
    CONSTRAINT uq_symbols_code UNIQUE (code),
    CONSTRAINT fk_symbols_color_id FOREIGN KEY (color_id) REFERENCES colors (id)
);
CREATE INDEX ix_symbols_color_id ON symbols (color_id);

CREATE TABLE product_types (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    CONSTRAINT pk_product_types_id PRIMARY KEY (id),
    CONSTRAINT uq_product_types_code UNIQUE (code)
);

CREATE TABLE rarities (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    CONSTRAINT pk_rarities_id PRIMARY KEY (id),
    CONSTRAINT uq_rarities_code UNIQUE (code)
);

CREATE TABLE variants (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    CONSTRAINT pk_variants_id PRIMARY KEY (id),
    CONSTRAINT uq_variants_code UNIQUE (code)
);

CREATE TABLE effect_kinds (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    CONSTRAINT pk_effect_kinds_id PRIMARY KEY (id),
    CONSTRAINT uq_effect_kinds_code UNIQUE (code)
);

CREATE TABLE keywords (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    CONSTRAINT pk_keywords_id PRIMARY KEY (id),
    CONSTRAINT uq_keywords_code UNIQUE (code)
);

CREATE TABLE image_sizes (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    CONSTRAINT pk_image_sizes_id PRIMARY KEY (id),
    CONSTRAINT uq_image_sizes_code UNIQUE (code)
);

CREATE TABLE sources (
    id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    CONSTRAINT pk_sources_id PRIMARY KEY (id),
    CONSTRAINT uq_sources_code UNIQUE (code)
);

-- Data entities
CREATE TABLE cards (
    id INTEGER NOT NULL,
    card_type_id INTEGER NOT NULL,
    cost INTEGER NOT NULL,
    name_jp TEXT NOT NULL,
    name_en TEXT,
    flavor_text_jp TEXT,
    flavor_text_en TEXT,
    -- en_source_id / en_status_id describe name_en only; the flavor text has its own pair
    en_source_id INTEGER,
    en_status_id INTEGER NOT NULL DEFAULT 1,
    flavor_en_source_id INTEGER,
    flavor_en_status_id INTEGER NOT NULL DEFAULT 1,
    block_icon TEXT,
    card_class_jp TEXT,
    card_class_en TEXT,
    type_mark_jp TEXT,
    deck_limit INTEGER,
    reduction_plain INTEGER,
    overclock_count_min INTEGER,
    overclock_bp_bonus INTEGER,
    overclock_condition_jp TEXT,
    flavor_note_jp TEXT,
    CONSTRAINT pk_cards_id PRIMARY KEY (id),
    CONSTRAINT fk_cards_card_type_id FOREIGN KEY (card_type_id) REFERENCES card_types (id),
    CONSTRAINT fk_cards_en_source_id FOREIGN KEY (en_source_id) REFERENCES translation_sources (id),
    CONSTRAINT fk_cards_en_status_id FOREIGN KEY (en_status_id) REFERENCES translation_statuses (id),
    CONSTRAINT fk_cards_flavor_en_source_id FOREIGN KEY (flavor_en_source_id) REFERENCES translation_sources (id),
    CONSTRAINT fk_cards_flavor_en_status_id FOREIGN KEY (flavor_en_status_id) REFERENCES translation_statuses (id),
    CONSTRAINT ck_cards_cost CHECK (cost >= 0),
    CONSTRAINT ck_cards_deck_limit CHECK (deck_limit >= 1),
    CONSTRAINT ck_cards_reduction_plain CHECK (reduction_plain >= 0),
    CONSTRAINT ck_cards_overclock_count_min CHECK (overclock_count_min >= 1),
    CONSTRAINT ck_cards_overclock_bp_bonus CHECK (overclock_bp_bonus >= 0),
    CONSTRAINT ck_cards_overclock_pair CHECK ((overclock_count_min IS NULL) = (overclock_bp_bonus IS NULL))
);
CREATE INDEX ix_cards_card_type_id ON cards (card_type_id);

CREATE TABLE card_numbers (
    id INTEGER NOT NULL,
    number TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    CONSTRAINT pk_card_numbers_id PRIMARY KEY (id),
    CONSTRAINT uq_card_numbers_number UNIQUE (number),
    CONSTRAINT fk_card_numbers_card_id FOREIGN KEY (card_id) REFERENCES cards (id)
);
CREATE INDEX ix_card_numbers_card_id ON card_numbers (card_id);

CREATE TABLE products (
    id INTEGER NOT NULL,
    code TEXT,
    name_jp TEXT NOT NULL,
    name_en TEXT,
    product_type_id INTEGER NOT NULL,
    release_date TEXT,
    series TEXT,
    en_source_id INTEGER,
    en_status_id INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT pk_products_id PRIMARY KEY (id),
    CONSTRAINT uq_products_code UNIQUE (code),
    CONSTRAINT fk_products_product_type_id FOREIGN KEY (product_type_id) REFERENCES product_types (id),
    CONSTRAINT fk_products_en_source_id FOREIGN KEY (en_source_id) REFERENCES translation_sources (id),
    CONSTRAINT fk_products_en_status_id FOREIGN KEY (en_status_id) REFERENCES translation_statuses (id)
);
CREATE INDEX ix_products_product_type_id ON products (product_type_id);

CREATE TABLE printings (
    id INTEGER NOT NULL,
    card_number_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    variant_id INTEGER NOT NULL DEFAULT 1,
    rarity_id INTEGER,
    illustrator TEXT,
    detail_jp TEXT,
    note_jp TEXT,
    CONSTRAINT pk_printings_id PRIMARY KEY (id),
    CONSTRAINT uq_printings_card_number_id_product_id_variant_id UNIQUE (card_number_id, product_id, variant_id),
    CONSTRAINT fk_printings_card_number_id FOREIGN KEY (card_number_id) REFERENCES card_numbers (id),
    CONSTRAINT fk_printings_product_id FOREIGN KEY (product_id) REFERENCES products (id),
    CONSTRAINT fk_printings_variant_id FOREIGN KEY (variant_id) REFERENCES variants (id),
    CONSTRAINT fk_printings_rarity_id FOREIGN KEY (rarity_id) REFERENCES rarities (id)
);
CREATE INDEX ix_printings_product_id ON printings (product_id);
CREATE INDEX ix_printings_variant_id ON printings (variant_id);
CREATE INDEX ix_printings_rarity_id ON printings (rarity_id);

CREATE TABLE printing_images (
    id INTEGER NOT NULL,
    printing_id INTEGER NOT NULL,
    image_size_id INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 1,
    path TEXT,
    source_url TEXT NOT NULL,
    sha256 TEXT,
    width INTEGER,
    height INTEGER,
    mime_type TEXT,
    CONSTRAINT pk_printing_images_id PRIMARY KEY (id),
    CONSTRAINT uq_printing_images_printing_id_image_size_id_position UNIQUE (printing_id, image_size_id, position),
    CONSTRAINT fk_printing_images_printing_id FOREIGN KEY (printing_id) REFERENCES printings (id),
    CONSTRAINT fk_printing_images_image_size_id FOREIGN KEY (image_size_id) REFERENCES image_sizes (id),
    CONSTRAINT ck_printing_images_position CHECK (position >= 1),
    CONSTRAINT ck_printing_images_width CHECK (width > 0),
    CONSTRAINT ck_printing_images_height CHECK (height > 0)
);
CREATE INDEX ix_printing_images_image_size_id ON printing_images (image_size_id);

-- Gameplay attributes
CREATE TABLE card_colors (
    card_id INTEGER NOT NULL,
    color_id INTEGER NOT NULL,
    CONSTRAINT pk_card_colors_card_id_color_id PRIMARY KEY (card_id, color_id),
    CONSTRAINT fk_card_colors_card_id FOREIGN KEY (card_id) REFERENCES cards (id),
    CONSTRAINT fk_card_colors_color_id FOREIGN KEY (color_id) REFERENCES colors (id)
);
CREATE INDEX ix_card_colors_color_id ON card_colors (color_id);

CREATE TABLE card_symbols (
    card_id INTEGER NOT NULL,
    symbol_id INTEGER NOT NULL,
    count INTEGER NOT NULL,
    variant_jp TEXT,
    color_jp TEXT,
    CONSTRAINT pk_card_symbols_card_id_symbol_id PRIMARY KEY (card_id, symbol_id),
    CONSTRAINT fk_card_symbols_card_id FOREIGN KEY (card_id) REFERENCES cards (id),
    CONSTRAINT fk_card_symbols_symbol_id FOREIGN KEY (symbol_id) REFERENCES symbols (id),
    CONSTRAINT ck_card_symbols_count CHECK (count >= 1)
);
CREATE INDEX ix_card_symbols_symbol_id ON card_symbols (symbol_id);

CREATE TABLE card_reductions (
    card_id INTEGER NOT NULL,
    symbol_id INTEGER NOT NULL,
    count INTEGER NOT NULL,
    CONSTRAINT pk_card_reductions_card_id_symbol_id PRIMARY KEY (card_id, symbol_id),
    CONSTRAINT fk_card_reductions_card_id FOREIGN KEY (card_id) REFERENCES cards (id),
    CONSTRAINT fk_card_reductions_symbol_id FOREIGN KEY (symbol_id) REFERENCES symbols (id),
    CONSTRAINT ck_card_reductions_count CHECK (count >= 1)
);
CREATE INDEX ix_card_reductions_symbol_id ON card_reductions (symbol_id);

CREATE TABLE card_levels (
    id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    level INTEGER NOT NULL,
    cores INTEGER,
    battle_points INTEGER,
    count_condition_jp TEXT,
    note_jp TEXT,
    CONSTRAINT pk_card_levels_id PRIMARY KEY (id),
    CONSTRAINT uq_card_levels_card_id_level UNIQUE (card_id, level),
    CONSTRAINT fk_card_levels_card_id FOREIGN KEY (card_id) REFERENCES cards (id),
    CONSTRAINT ck_card_levels_level CHECK (level >= 1),
    CONSTRAINT ck_card_levels_cores CHECK (cores >= 0),
    CONSTRAINT ck_card_levels_battle_points CHECK (battle_points >= 0)
);

CREATE TABLE card_credits (
    id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    role_jp TEXT NOT NULL,
    name TEXT NOT NULL,
    note TEXT,
    CONSTRAINT pk_card_credits_id PRIMARY KEY (id),
    CONSTRAINT uq_card_credits_card_id_position UNIQUE (card_id, position),
    CONSTRAINT fk_card_credits_card_id FOREIGN KEY (card_id) REFERENCES cards (id) ON DELETE CASCADE
);

CREATE TABLE families (
    id INTEGER NOT NULL,
    code TEXT,
    name_jp TEXT NOT NULL,
    name_en TEXT,
    en_source_id INTEGER,
    en_status_id INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT pk_families_id PRIMARY KEY (id),
    CONSTRAINT uq_families_code UNIQUE (code),
    CONSTRAINT uq_families_name_jp UNIQUE (name_jp),
    CONSTRAINT fk_families_en_source_id FOREIGN KEY (en_source_id) REFERENCES translation_sources (id),
    CONSTRAINT fk_families_en_status_id FOREIGN KEY (en_status_id) REFERENCES translation_statuses (id)
);

CREATE TABLE family_aliases (
    id INTEGER NOT NULL,
    family_id INTEGER NOT NULL,
    alias TEXT NOT NULL,
    lang TEXT NOT NULL,
    translation_source_id INTEGER NOT NULL,
    CONSTRAINT pk_family_aliases_id PRIMARY KEY (id),
    CONSTRAINT uq_family_aliases_family_id_alias_lang UNIQUE (family_id, alias, lang),
    CONSTRAINT fk_family_aliases_family_id FOREIGN KEY (family_id) REFERENCES families (id),
    CONSTRAINT fk_family_aliases_translation_source_id FOREIGN KEY (translation_source_id) REFERENCES translation_sources (id),
    CONSTRAINT ck_family_aliases_lang CHECK (lang IN ('jp', 'en'))
);

CREATE TABLE card_families (
    card_id INTEGER NOT NULL,
    family_id INTEGER NOT NULL,
    CONSTRAINT pk_card_families_card_id_family_id PRIMARY KEY (card_id, family_id),
    CONSTRAINT fk_card_families_card_id FOREIGN KEY (card_id) REFERENCES cards (id),
    CONSTRAINT fk_card_families_family_id FOREIGN KEY (family_id) REFERENCES families (id)
);
CREATE INDEX ix_card_families_family_id ON card_families (family_id);

CREATE TABLE brave_details (
    card_id INTEGER NOT NULL,
    fusion_condition_jp TEXT,
    fusion_condition_en TEXT,
    fusion_bp_bonus INTEGER,
    en_source_id INTEGER,
    en_status_id INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT pk_brave_details_card_id PRIMARY KEY (card_id),
    CONSTRAINT fk_brave_details_card_id FOREIGN KEY (card_id) REFERENCES cards (id),
    CONSTRAINT fk_brave_details_en_source_id FOREIGN KEY (en_source_id) REFERENCES translation_sources (id),
    CONSTRAINT fk_brave_details_en_status_id FOREIGN KEY (en_status_id) REFERENCES translation_statuses (id)
);

CREATE TABLE ultimate_details (
    card_id INTEGER NOT NULL,
    summon_condition_jp TEXT,
    summon_condition_en TEXT,
    en_source_id INTEGER,
    en_status_id INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT pk_ultimate_details_card_id PRIMARY KEY (card_id),
    CONSTRAINT fk_ultimate_details_card_id FOREIGN KEY (card_id) REFERENCES cards (id),
    CONSTRAINT fk_ultimate_details_en_source_id FOREIGN KEY (en_source_id) REFERENCES translation_sources (id),
    CONSTRAINT fk_ultimate_details_en_status_id FOREIGN KEY (en_status_id) REFERENCES translation_statuses (id)
);

-- Effects and keywords
CREATE TABLE card_effects (
    id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    effect_kind_id INTEGER NOT NULL,
    timing_jp TEXT,
    timing_en TEXT,
    text_jp TEXT NOT NULL,
    text_en TEXT,
    en_source_id INTEGER,
    en_status_id INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT pk_card_effects_id PRIMARY KEY (id),
    CONSTRAINT uq_card_effects_card_id_position UNIQUE (card_id, position),
    CONSTRAINT fk_card_effects_card_id FOREIGN KEY (card_id) REFERENCES cards (id),
    CONSTRAINT fk_card_effects_effect_kind_id FOREIGN KEY (effect_kind_id) REFERENCES effect_kinds (id),
    CONSTRAINT fk_card_effects_en_source_id FOREIGN KEY (en_source_id) REFERENCES translation_sources (id),
    CONSTRAINT fk_card_effects_en_status_id FOREIGN KEY (en_status_id) REFERENCES translation_statuses (id),
    CONSTRAINT ck_card_effects_position CHECK (position >= 1)
);
CREATE INDEX ix_card_effects_effect_kind_id ON card_effects (effect_kind_id);

CREATE TABLE card_effect_levels (
    card_effect_id INTEGER NOT NULL,
    card_level_id INTEGER NOT NULL,
    CONSTRAINT pk_card_effect_levels_card_effect_id_card_level_id PRIMARY KEY (card_effect_id, card_level_id),
    CONSTRAINT fk_card_effect_levels_card_effect_id FOREIGN KEY (card_effect_id) REFERENCES card_effects (id),
    CONSTRAINT fk_card_effect_levels_card_level_id FOREIGN KEY (card_level_id) REFERENCES card_levels (id)
);
CREATE INDEX ix_card_effect_levels_card_level_id ON card_effect_levels (card_level_id);

CREATE TABLE card_effect_keywords (
    card_effect_id INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    parameter_jp TEXT,
    CONSTRAINT pk_card_effect_keywords_card_effect_id_keyword_id PRIMARY KEY (card_effect_id, keyword_id),
    CONSTRAINT fk_card_effect_keywords_card_effect_id FOREIGN KEY (card_effect_id) REFERENCES card_effects (id),
    CONSTRAINT fk_card_effect_keywords_keyword_id FOREIGN KEY (keyword_id) REFERENCES keywords (id)
);
CREATE INDEX ix_card_effect_keywords_keyword_id ON card_effect_keywords (keyword_id);

-- Provenance
CREATE TABLE source_pages (
    id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    CONSTRAINT pk_source_pages_id PRIMARY KEY (id),
    CONSTRAINT uq_source_pages_url UNIQUE (url),
    CONSTRAINT fk_source_pages_source_id FOREIGN KEY (source_id) REFERENCES sources (id)
);
CREATE INDEX ix_source_pages_source_id ON source_pages (source_id);

CREATE TABLE card_source_pages (
    card_id INTEGER NOT NULL,
    source_page_id INTEGER NOT NULL,
    CONSTRAINT pk_card_source_pages_card_id_source_page_id PRIMARY KEY (card_id, source_page_id),
    CONSTRAINT fk_card_source_pages_card_id FOREIGN KEY (card_id) REFERENCES cards (id),
    CONSTRAINT fk_card_source_pages_source_page_id FOREIGN KEY (source_page_id) REFERENCES source_pages (id)
);
CREATE INDEX ix_card_source_pages_source_page_id ON card_source_pages (source_page_id);

CREATE TABLE product_source_pages (
    product_id INTEGER NOT NULL,
    source_page_id INTEGER NOT NULL,
    CONSTRAINT pk_product_source_pages_product_id_source_page_id PRIMARY KEY (product_id, source_page_id),
    CONSTRAINT fk_product_source_pages_product_id FOREIGN KEY (product_id) REFERENCES products (id),
    CONSTRAINT fk_product_source_pages_source_page_id FOREIGN KEY (source_page_id) REFERENCES source_pages (id)
);
CREATE INDEX ix_product_source_pages_source_page_id ON product_source_pages (source_page_id);

-- Static lookup seeds. Glossary-derived lookups (colors, card_types, rarities,
-- product_types, families, keywords, symbols, other variants) are filled by the loader.
-- Order matters: the DEFAULT 1 of en_status_id and variant_id relies on these ids.
INSERT INTO translation_statuses (id, code, name) VALUES
    (1, 'pending', 'Pending'),
    (2, 'machine', 'Machine translated'),
    (3, 'reviewed', 'Reviewed'),
    (4, 'failed', 'Failed');

INSERT INTO translation_sources (id, code, name) VALUES
    (1, 'batspi', 'batspi.com'),
    (2, 'official', 'Official'),
    (3, 'fandom', 'Fandom wiki'),
    (4, 'manual', 'Manual'),
    (5, 'machine', 'Machine translation');

INSERT INTO variants (id, code, name) VALUES
    (1, 'normal', 'Normal');

INSERT INTO sources (id, code, name, base_url) VALUES
    (1, 'batspi', 'batspi.com', 'https://batspi.com/');

INSERT INTO image_sizes (id, code, name) VALUES
    (1, 'small', 'Small'),
    (2, 'large', 'Large');
