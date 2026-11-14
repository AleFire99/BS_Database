# Target schema

This is the design document for the new normalized schema. It is extended by [#30](https://github.com/AleFire99/BS_Database/issues/30) (gameplay attributes), [#31](https://github.com/AleFire99/BS_Database/issues/31) (effects, i18n, provenance, images) and [#32](https://github.com/AleFire99/BS_Database/issues/32). It is **not** the build source: the DDL and SQLAlchemy models are owned by [#12](https://github.com/AleFire99/BS_Database/issues/12). Naming follows [ADR 0003](../adr/0003-naming-and-schema-versioning.md). Items marked "pending #9" depend on the source analysis ([#9](https://github.com/AleFire99/BS_Database/issues/9)).

## Identity

Card versus printing identity, as decided in [ADR 0004](../adr/0004-card-printing-identity.md): a **card** is the gameplay identity, a **card number** (`BS72-069`) belongs to exactly one card, and a **printing** is one number in one product and variant.

```mermaid
erDiagram
    cards ||--|{ card_numbers : "has"
    card_numbers ||--|{ printings : "printed as"
    products ||--o{ printings : "contains"
    product_types ||--o{ products : "classifies"
    rarities |o--o{ printings : "rates"
    variants ||--o{ printings : "finishes"

    cards {
        integer id PK
        text name_ja
        text name_en
        text block_icon
    }
    card_numbers {
        integer id PK
        text number UK
        integer card_id FK
    }
    printings {
        integer id PK
        integer card_number_id FK
        integer product_id FK
        integer variant_id FK
        integer rarity_id FK
        text illustrator
    }
    products {
        integer id PK
        text code UK
        text name_ja
        text name_en
        integer product_type_id FK
        text release_date
        text series
    }
    product_types {
        integer id PK
        text code UK
        text name
    }
    rarities {
        integer id PK
        text code UK
        text name
        integer sort_order
    }
    variants {
        integer id PK
        text code UK
        text name
    }
```

### cards

The gameplay identity: one row per distinct card. Gameplay columns (type, cost) and the related tables (colors, symbols, families, levels) are described in [Gameplay attributes](#gameplay-attributes); effects, text and translation columns are in [Effects and keywords](#effects-and-keywords) and [Multilingual text](#multilingual-text).

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | Surrogate key. |
| `name_ja` | TEXT | NOT NULL | Japanese card name (batspi page title). |
| `name_en` | TEXT | | English name; NULL until translated. Source and status in `en_source_id` and `en_status_id` below; see [Multilingual text](#multilingual-text). |
| `flavor_text_ja` | TEXT | | Flavor text as printed (`フレーバーテキスト：` in the `<pre>`). NULL when the card has none (the Magic fixture has none). On the card, not the printing; whether it varies per printing is pending #9. |
| `flavor_text_en` | TEXT | | English flavor text; NULL until translated. |
| `en_source_id` | INTEGER | FOREIGN KEY to `translation_sources.id` | Where the English texts of this row come from; NULL while there is no English text. |
| `en_status_id` | INTEGER | NOT NULL, FOREIGN KEY to `translation_statuses.id` | Translation status of this row; defaults to `pending`. |
| `block_icon` | TEXT | | Block icon (`12`, `A`, ...). Placed on the card by default; per card or per number is pending #9. |

Whether numbers with the same name but different numbers are one card is pending #9. The planned rule: link them only if text and stats are identical.

### card_numbers

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `number` | TEXT | NOT NULL, UNIQUE | Printed number, e.g. `BS72-069`. Promo number format pending #9. |
| `card_id` | INTEGER | NOT NULL, FOREIGN KEY to `cards.id` | A number belongs to exactly one card; a card can have several numbers. |

### printings

One physical printing of a number in a product.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `card_number_id` | INTEGER | NOT NULL, FOREIGN KEY to `card_numbers.id` | |
| `product_id` | INTEGER | NOT NULL, FOREIGN KEY to `products.id` | |
| `variant_id` | INTEGER | NOT NULL, FOREIGN KEY to `variants.id` | Defaults to the `normal` variant; NOT NULL because SQLite treats NULLs as distinct in UNIQUE. |
| `rarity_id` | INTEGER | FOREIGN KEY to `rarities.id` | Nullable: distribution entries on batspi show no rarity (pending #9). |
| `illustrator` | TEXT | | Plain text for now; normalised later if needed. |

Table constraint: `UNIQUE (card_number_id, product_id, variant_id)`. Images are not a column of `printings`: they are rows of [printing_images](#printing_images).

### products

Anything a card is released in. A booster set is a product; there is no separate `sets` table.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | UNIQUE | e.g. `BS72`; NULL for distributions without a code (SQLite allows several NULLs). |
| `name_ja` | TEXT | NOT NULL | e.g. `第1章：廻帰再醒`. |
| `name_en` | TEXT | | |
| `product_type_id` | INTEGER | NOT NULL, FOREIGN KEY to `product_types.id` | |
| `release_date` | TEXT | | ISO-8601 date; NULL when the source gives none. |
| `series` | TEXT | | Chapter or saga grouping (`契約編：環`), a plain column, no table. |
| `en_source_id` | INTEGER | FOREIGN KEY to `translation_sources.id` | Source of `name_en`; NULL while untranslated. |
| `en_status_id` | INTEGER | NOT NULL, FOREIGN KEY to `translation_statuses.id` | Translation status of `name_en`; defaults to `pending`. |

### product_types

Lookup, following the lookup convention of ADR 0003: `code` plus one English `name`, no Japanese name column.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | Planned: `booster`, `starter`, `promo`, `magazine`, `collab`, `other`. Final list pending #9. |
| `name` | TEXT | NOT NULL | English display name. |

### rarities

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | `C` and `R` seen in batspi `<C>`, `<R>`; other codes and the full scale are pending #9. |
| `name` | TEXT | NOT NULL | English display name, e.g. `Common`, `Rare`. |
| `sort_order` | INTEGER | NOT NULL | Display order from common to rare. |

### variants

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | Planned: `normal`, `secret`, `full_art`, `promo_art`, parallel. The full list is pending #9. |
| `name` | TEXT | NOT NULL | English display name, e.g. `Full art`. The source text `フルアート版` is mapped to `full_art` by the loader. |

## Gameplay attributes

Added by [#30](https://github.com/AleFire99/BS_Database/issues/30). Gameplay attributes are identical across printings of a card (a reprint keeps its number and text; only rarity and art change, see ADR 0004), so they hang off `cards`, never off `card_numbers` or `printings`. Effects, keywords and alternate costs such as `【ミラージュ：コスト2(1)】` belong to [#31](https://github.com/AleFire99/BS_Database/issues/31) and are modelled in [Effects and keywords](#effects-and-keywords), not here.

Lookup tables (`card_types`, `colors`, `symbols`, `rarities`, `variants`, `product_types`) carry a stable `code` and one English `name`. They have **no Japanese name column**: the Japanese source text is translated to a `code` by the loader ([#12](https://github.com/AleFire99/BS_Database/issues/12)), see [JP source to code](#jp-source-to-code). Data entities (`cards`, `families`, `products`) keep `name_ja` so a bad machine translation can be redone.

```mermaid
erDiagram
    card_types ||--o{ cards : "classifies"
    cards ||--o{ card_colors : "has"
    colors ||--o{ card_colors : "used in"
    cards ||--o{ card_symbols : "has"
    cards ||--o{ card_reductions : "has"
    symbols ||--o{ card_symbols : "used in"
    symbols ||--o{ card_reductions : "used in"
    colors |o--o{ symbols : "colours"
    cards ||--o{ card_levels : "has"
    cards ||--o{ card_families : "has"
    families ||--o{ card_families : "used in"
    families ||--o{ family_aliases : "known as"
    cards ||--o| brave_details : "extends"
    cards ||--o| ultimate_details : "extends"

    cards {
        integer id PK
        integer card_type_id FK
        integer cost
        text name_ja
        text name_en
    }
    card_types {
        integer id PK
        text code UK
        text name
    }
    colors {
        integer id PK
        text code UK
        text name
    }
    card_colors {
        integer card_id PK
        integer color_id PK
    }
    symbols {
        integer id PK
        text code UK
        text name
        integer color_id FK
    }
    card_symbols {
        integer card_id PK
        integer symbol_id PK
        integer count
    }
    card_reductions {
        integer card_id PK
        integer symbol_id PK
        integer count
    }
    card_levels {
        integer id PK
        integer card_id FK
        integer level
        integer cores
        integer battle_points
    }
    families {
        integer id PK
        text code UK
        text name_ja UK
        text name_en
    }
    family_aliases {
        integer id PK
        integer family_id FK
        text alias
        text lang
        text source
    }
    card_families {
        integer card_id PK
        integer family_id PK
    }
    brave_details {
        integer card_id PK, FK
        text fusion_condition_ja
        text fusion_condition_en
        integer fusion_bp_bonus
    }
    ultimate_details {
        integer card_id PK, FK
        text summon_condition_ja
        text summon_condition_en
    }
```

### cards (gameplay columns)

Columns added by #30 to the identity table above (`name_ja`, `name_en` and `block_icon` are already described there).

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `card_type_id` | INTEGER | NOT NULL, FOREIGN KEY to `card_types.id` | Type from `<pre>` line 1. |
| `cost` | INTEGER | NOT NULL, CHECK `cost` >= 0 | Number before the parentheses on the cost line (`4` in `4(赤2神1)`). Legacy range 0 to 12. |

### card_types

Lookup.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | `spirit`, `nexus`, `magic`, `brave`, `ultimate`. A new type needs no schema change. |
| `name` | TEXT | NOT NULL | English display name, e.g. `Spirit`. |

### colors

Lookup. Colours are the six game colours; the god symbol is not a colour.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | `red`, `purple`, `green`, `white`, `yellow`, `blue`. White is included (it is missing from the legacy `colors` table). |
| `name` | TEXT | NOT NULL | English display name. |

### card_colors

Pure junction table. One row per colour of a card; a six-colour card has six rows and there is no "multicolour" pseudo-colour. The colour comes from segment 2 of the cost line in the Japanese text (`赤`, or several colours), never from translated text.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `card_id` | INTEGER | FOREIGN KEY to `cards.id` | Part of the composite PRIMARY KEY. |
| `color_id` | INTEGER | FOREIGN KEY to `colors.id` | Part of the composite PRIMARY KEY. |

How several colours are separated in segment 2 is pending #9 (only single-colour fixtures exist).

### symbols

Lookup. Symbols are distinct from colours: a symbol is an icon printed on a card or used to reduce a cost, and the god symbol 神 is a symbol without a colour (same idea as BSS_app `Symbols(ColorID)`).

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | `red`, `purple`, `green`, `white`, `yellow`, `blue`, `god`. |
| `name` | TEXT | NOT NULL | English display name. |
| `color_id` | INTEGER | FOREIGN KEY to `colors.id` | NULL for `god`. |

### card_symbols

Pure junction table. Symbols printed on the card, from the `シンボル：` line. Magic cards have no such line and therefore no rows.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `card_id` | INTEGER | FOREIGN KEY to `cards.id` | Part of the composite PRIMARY KEY. |
| `symbol_id` | INTEGER | FOREIGN KEY to `symbols.id` | Part of the composite PRIMARY KEY. |
| `count` | INTEGER | NOT NULL, CHECK `count` >= 1 | Double symbols use a count. The format of multi-symbol lines is pending #9. |

### card_reductions

Pure junction table. Cost reduction symbols, from the parentheses in the cost line. It is keyed by **symbol**, not by colour as in BSS_app `CardReductions(ColorID)`, because reductions can include the god symbol 神 (see [ADR 0003](../adr/0003-naming-and-schema-versioning.md)).

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `card_id` | INTEGER | FOREIGN KEY to `cards.id` | Part of the composite PRIMARY KEY. |
| `symbol_id` | INTEGER | FOREIGN KEY to `symbols.id` | Part of the composite PRIMARY KEY. |
| `count` | INTEGER | NOT NULL, CHECK `count` >= 1 | Number of symbols that can be used. |

`4(赤2神1)` gives two rows (red 2, god 1). A plain number such as `(2)` means N symbols of the card's own colour; the loader resolves it. The rule for multicolour cards is pending #9. A `(0)` reduction gives no row.

### card_levels

Per-level rows. Hangs off the card, not the printing.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | Referenced by [card_effect_levels](#card_effect_levels). |
| `card_id` | INTEGER | NOT NULL, FOREIGN KEY to `cards.id` | |
| `level` | INTEGER | NOT NULL, CHECK `level` >= 1 | Flagged in review as a column name (ADR 0003); legal unquoted in SQLite. |
| `cores` | INTEGER | NOT NULL, CHECK `cores` >= 0 | Cores needed on the card to reach this level (the `<n>` in `<3>Lv2`). |
| `battle_points` | INTEGER | CHECK `battle_points` >= 0 | NULL when the level has no BP (Nexus). |

Table constraint: `UNIQUE (card_id, level)`. Magic has no level line and therefore no rows. Legacy data shows Spirit levels 1 to 4, Brave exactly one row at level 1 and Ultimate levels 3 to 6 (see [field-inventory.md](field-inventory.md)); the Brave and Ultimate line formats are pending #9.

### families

Family (系統) tags. The Japanese text is the identity; the English name is the preferred display name.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | UNIQUE | Stable slug of the preferred English name; NULL until assigned (SQLite allows several NULLs). |
| `name_ja` | TEXT | NOT NULL, UNIQUE | e.g. `眷属`, `武迅`. |
| `name_en` | TEXT | | Preferred English name, e.g. `Reptile Beast` for `爬獣`. |
| `en_source_id` | INTEGER | FOREIGN KEY to `translation_sources.id` | Source of `name_en`; NULL while untranslated. |
| `en_status_id` | INTEGER | NOT NULL, FOREIGN KEY to `translation_statuses.id` | Translation status of `name_en`; defaults to `pending`. |

### family_aliases

Other names for a family, so a machine translation can be mapped back to the preferred name.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `family_id` | INTEGER | NOT NULL, FOREIGN KEY to `families.id` | |
| `alias` | TEXT | NOT NULL | |
| `lang` | TEXT | NOT NULL, CHECK `lang` IN (`ja`, `en`) | |
| `source` | TEXT | NOT NULL | `machine_translation`, `fandom` or `manual`. |

Table constraint: `UNIQUE (family_id, alias, lang)`. Seeded from the 40 `MT = preferred EN` pairs in `data/family_mapping.txt` (for example `Rebirth = Reptile Beast`: the alias `Rebirth` points to the family whose preferred name is `Reptile Beast`) and from the machine-translated names in the legacy `families` table.

### card_families

Pure junction table. Order of the families on the card is not significant.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `card_id` | INTEGER | FOREIGN KEY to `cards.id` | Part of the composite PRIMARY KEY. |
| `family_id` | INTEGER | FOREIGN KEY to `families.id` | Part of the composite PRIMARY KEY. |

Families are segment 3 of the cost line, separated by `・`. Magic and Nexus cards often have none, but the fixtures show a family on each (`武迅`, `皇獣`).

### brave_details

1:1 side table for Brave cards only. Text first (Gate A); all fields are **pending #9** because no Brave fixture exists.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `card_id` | INTEGER | PRIMARY KEY, FOREIGN KEY to `cards.id` | The card must have type `brave`. |
| `fusion_condition_ja` | TEXT | | Fusion condition as printed. Pending #9. |
| `fusion_condition_en` | TEXT | | Translation. Pending #9. |
| `fusion_bp_bonus` | INTEGER | | NULL when absent. Pending #9. |
| `en_source_id` | INTEGER | FOREIGN KEY to `translation_sources.id` | Source of `fusion_condition_en`. Pending #9. |
| `en_status_id` | INTEGER | NOT NULL, FOREIGN KEY to `translation_statuses.id` | Translation status; defaults to `pending`. Pending #9. |

### ultimate_details

1:1 side table for Ultimate cards only. Text first, **pending #9**. The Ultimate level rows stay in `card_levels` (they start at 3).

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `card_id` | INTEGER | PRIMARY KEY, FOREIGN KEY to `cards.id` | The card must have type `ultimate`. |
| `summon_condition_ja` | TEXT | | Summon condition as printed. Pending #9. |
| `summon_condition_en` | TEXT | | Translation. Pending #9. |
| `en_source_id` | INTEGER | FOREIGN KEY to `translation_sources.id` | Source of `summon_condition_en`. Pending #9. |
| `en_status_id` | INTEGER | NOT NULL, FOREIGN KEY to `translation_statuses.id` | Translation status; defaults to `pending`. Pending #9. |

Side tables instead of nullable columns on `cards`: `cards` stays free of type-specific NULL columns, and a new type with its own attributes (for example a 創界神ネクサス) adds a side table without touching `cards`. The cost is one extra join for those types.

### Worked examples

The `<pre>` lines come from the fixtures in `tests/fixtures/html/`. Ids are illustrative.

#### Spirit (`card_spirit.html`)

```text
スピリット
4(赤2神1)/赤/眷属・武迅
<1>Lv1 3000 <3>Lv2 7000
...
シンボル：赤
```

| Line | Target rows |
| --- | --- |
| `スピリット` | `cards.card_type_id` -> `card_types.code = spirit` |
| `4(赤2神1)` | `cards.cost = 4`; `card_reductions`: (red, 2) and (god, 1) |
| `/赤/` | `card_colors`: red |
| `眷属・武迅` | `families` `眷属` and `武迅`; two `card_families` rows |
| `<1>Lv1 3000` | `card_levels`: level 1, cores 1, battle_points 3000 |
| `<3>Lv2 7000` | `card_levels`: level 2, cores 3, battle_points 7000 |
| `シンボル：赤` | `card_symbols`: (red, 1) |

#### Nexus (`card_nexus.html`)

```text
ネクサス
3(2)/赤/皇獣
<0>Lv1 <1>Lv2
...
シンボル：赤
```

| Line | Target rows |
| --- | --- |
| `ネクサス` | `card_types.code = nexus` |
| `3(2)` | `cards.cost = 3`; `card_reductions`: (red, 2), the plain `2` resolved to the card's own colour (single colour here; assumed, pending #9) |
| `/赤/` | `card_colors`: red |
| `皇獣` | `families` `皇獣`; one `card_families` row |
| `<0>Lv1` | `card_levels`: level 1, cores 0, battle_points NULL |
| `<1>Lv2` | `card_levels`: level 2, cores 1, battle_points NULL |
| `シンボル：赤` | `card_symbols`: (red, 1) |

#### Magic (`card_magic.html`)

```text
マジック
4(2)/赤/武迅
【ミラージュ：コスト2(1)(このカードは手札からセットできる)】
...
```

| Line | Target rows |
| --- | --- |
| `マジック` | `card_types.code = magic` |
| `4(2)` | `cards.cost = 4`; `card_reductions`: (red, 2) (assumed: plain `2` = own colour, pending #9) |
| `/赤/` | `card_colors`: red |
| `武迅` | `families` `武迅`; one `card_families` row |
| (no level line) | no `card_levels` rows |
| (no `シンボル：` line) | no `card_symbols` rows |
| `【ミラージュ：コスト2(1)…】` | not a cost: an alternate cost, kept as text in [Effects and keywords](#effects-and-keywords) |

### JP source to code

The loader (#12) maps Japanese source text to lookup codes. The mapping is code, not data: it is not stored in the database.

| Lookup | JP source | Code | Seen in |
| --- | --- | --- | --- |
| `colors` / `symbols` | 赤 | `red` | fixtures |
| `colors` / `symbols` | 紫 | `purple` | glossary, to verify #9 |
| `colors` / `symbols` | 緑 | `green` | glossary, to verify #9 |
| `colors` / `symbols` | 白 | `white` | glossary, to verify #9 |
| `colors` / `symbols` | 黄 | `yellow` | glossary, to verify #9 |
| `colors` / `symbols` | 青 | `blue` | glossary, to verify #9 |
| `symbols` | 神 | `god` | fixture (reduction) |
| `card_types` | スピリット | `spirit` | fixtures |
| `card_types` | ネクサス | `nexus` | fixtures |
| `card_types` | マジック | `magic` | fixtures |
| `card_types` | ブレイヴ | `brave` | not in fixtures, pending #9 |
| `card_types` | アルティメット | `ultimate` | not in fixtures, pending #9 |
| `rarities` | `<C>` | `C` | batspi `収録` list |
| `rarities` | `<R>` | `R` | batspi `収録` list |
| `variants` | `SECRETあり` | `secret` | BS72-007 |
| `variants` | `フルアート版` | `full_art` | BS72-069 |

Other rarities and variants, and the exact spelling of colours and Brave/Ultimate type names on the page, are pending #9. The colour and symbol glyphs 紫, 緑, 白, 黄, 青 are not in the three fixtures and are taken from the game's standard colour names and the glossary. Mark them to verify in #9.

### Legacy mapping

| Legacy (current-schema.md) | Target | Note |
| --- | --- | --- |
| `core_requirements` | `card_levels` | Renamed. |
| `core_requirements.battlePoints` | `card_levels.battle_points` | snake_case; NULL for Nexus. |
| `core_requirements.cores` (cores needed) | `card_levels.cores` | Unchanged name. |
| `cards.symbol` (free text, e.g. `Red and blue`) | `card_colors` rows | One row per colour, taken from the Japanese text. |
| `colors` | `colors` | Adds White, drops the lowercase/capitalised variants. |
| `families` (machine-translated EN) | `families` + `family_aliases` | JP name becomes the identity; the legacy EN names become aliases. |
| `card_families` | `card_families` | Same shape. |
| reductions (JSON only) | `card_reductions` | Now stored, including 神. |
| `cards.type_id` -> `card_types.name` | `cards.card_type_id` -> `card_types.code` | |

## Effects and keywords

Added by [#31](https://github.com/AleFire99/BS_Database/issues/31), decided in [ADR 0005](../adr/0005-text-first-effects-and-translations.md). Effects are **text-first** (Gate A of epic #8): each effect block of the `<pre>` is stored as printed, with its timing kept as text. Conditions, costs and actions are not parsed in v1. A structured model in the style of BSS_app (`Steps`, `Conditions`, `EffectSteps`) is a future, additive extension that would reference `card_effects` rows; it is not built now.

Effects hang off `cards`, like the gameplay attributes, because a reprint keeps its text. `cards`, `card_levels` and `printings` are shown with key columns only.

```mermaid
erDiagram
    cards ||--o{ card_effects : "has"
    effect_kinds ||--o{ card_effects : "classifies"
    card_effects ||--o{ card_effect_levels : "applies at"
    card_levels ||--o{ card_effect_levels : "activates"
    cards ||--o{ card_levels : "has"
    card_effects ||--o{ card_effect_keywords : "uses"
    keywords ||--o{ card_effect_keywords : "used in"

    cards {
        integer id PK
        text name_ja
    }
    card_levels {
        integer id PK
        integer card_id FK
        integer level
    }
    card_effects {
        integer id PK
        integer card_id FK
        integer position
        integer effect_kind_id FK
        text timing_ja
        text timing_en
        text text_ja
        text text_en
        integer en_source_id FK
        integer en_status_id FK
    }
    effect_kinds {
        integer id PK
        text code UK
        text name
    }
    card_effect_levels {
        integer card_effect_id PK, FK
        integer card_level_id PK, FK
    }
    keywords {
        integer id PK
        text code UK
        text name
    }
    card_effect_keywords {
        integer card_effect_id PK, FK
        integer keyword_id PK, FK
        text parameter_ja
    }
```

### card_effects

One row per effect block in the `<pre>`, in printed order.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `card_id` | INTEGER | NOT NULL, FOREIGN KEY to `cards.id` | |
| `position` | INTEGER | NOT NULL, CHECK `position` >= 1 | Order of the block on the card. |
| `effect_kind_id` | INTEGER | NOT NULL, FOREIGN KEY to `effect_kinds.id` | Kind of block. |
| `timing_ja` | TEXT | | The timing as printed, brackets included (`『自分のアタックステップ』`). NULL when the block has none. Kept as text, not parsed. |
| `timing_en` | TEXT | | English timing; NULL until translated. |
| `text_ja` | TEXT | NOT NULL | The effect text as printed: the lines of the block after its header, joined with line breaks. For a `keyword_block` it is the whole `【…】` line. |
| `text_en` | TEXT | | English text; NULL until translated. |
| `en_source_id` | INTEGER | FOREIGN KEY to `translation_sources.id` | Source of `timing_en` and `text_en`; NULL while untranslated. |
| `en_status_id` | INTEGER | NOT NULL, FOREIGN KEY to `translation_statuses.id` | Defaults to `pending`. |

Table constraint: `UNIQUE (card_id, position)`. How blocks are segmented in older eras, and in Brave and Ultimate cards, is pending #9: only the three fixtures were checked.

### effect_kinds

Lookup (`code` plus English `name`, no Japanese name column).

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | Planned: `level` (a `LvN` header with a timing), `constant` (a `LvN` header with no timing), `main` (`メイン：`), `flash` (`フラッシュ：`), `set_active` (`【セット中】`), `keyword_block` (a `【…】` line), `other`. `flash` is seen only in related-card blocks (pending #9); Brave and Ultimate blocks are pending #9. |
| `name` | TEXT | NOT NULL | English display name. |

The kind is derived by the loader from the block header. Whether `level` and `constant` should be one kind is a judgment call; the split follows the two shapes in the fixtures.

### card_effect_levels

Pure junction table. Which levels a block applies to. `Lv1・Lv2` gives two rows. A block with no rows applies to every level or is not level-scoped (Magic). The foreign key to `card_levels` keeps the levels consistent with the card (as BSS_app `EffectLevels`).

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `card_effect_id` | INTEGER | FOREIGN KEY to `card_effects.id` | Part of the composite PRIMARY KEY. |
| `card_level_id` | INTEGER | FOREIGN KEY to `card_levels.id` | Part of the composite PRIMARY KEY. The level must belong to the same card as the effect; checked by the build (a plain foreign key cannot enforce it). |

### keywords

Lookup of keyword abilities written as `【…】`.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | Only `mirage` (`ミラージュ`) is seen in the fixtures. The list is built from the source analysis ([#9](https://github.com/AleFire99/BS_Database/issues/9), [#11](https://github.com/AleFire99/BS_Database/issues/11)) and can grow without a schema change. |
| `name` | TEXT | NOT NULL | English display name, e.g. `Mirage`. |

### card_effect_keywords

Pure junction table with one extra column. Which keywords a block declares.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `card_effect_id` | INTEGER | FOREIGN KEY to `card_effects.id` | Part of the composite PRIMARY KEY. |
| `keyword_id` | INTEGER | FOREIGN KEY to `keywords.id` | Part of the composite PRIMARY KEY. |
| `parameter_ja` | TEXT | | The parameter as printed, e.g. `コスト2(1)` for Mirage. NULL for a keyword with none. |

The extra column makes this more than a pure junction, but the composite key stays because a keyword appears once per block. Text-first: the alternate cost `コスト2(1)` is **not** split into numbers in v1. The reminder text `(このカードは手札からセットできる)` stays in `card_effects.text_ja`.

### Worked examples (effects)

The blocks come from the `<pre>` of the fixtures in `tests/fixtures/html/`. Ids are illustrative and continue the ids used in [ADR 0004](../adr/0004-card-printing-identity.md): Nexus BS72-069 is card 1, Magic BS72-075 is card 2, Spirit BS72-007 is card 3. Level ids follow [card_levels](#card_levels). Long texts are shortened with `…`; the stored `text_ja` is the full block text. `en_status_id` is `pending` and `en_source_id` NULL in every row, as nothing is translated yet. Effect kinds are shown by code.

#### Spirit BS72-007

`card_levels` (card 3): id 1 = Lv1, id 2 = Lv2.

`card_effects` (card 3):

| id | position | effect_kind | timing_ja | text_ja (start) |
| --- | --- | --- | --- | --- |
| 1 | 1 | `level` | `『自分のアタックステップ開始時』` | 自分の「契約神ルー」すべてのブレイヴ1つにつき、… |
| 2 | 2 | `level` | `『自分のアタックステップ』` | 系統：「武迅」を持つ自分のスピリットがアタックしたとき、… |

`card_effect_levels`:

| card_effect_id | card_level_id | Source header |
| --- | --- | --- |
| 1 | 1 (Lv1) | `Lv1・Lv2` |
| 1 | 2 (Lv2) | `Lv1・Lv2` |
| 2 | 2 (Lv2) | `Lv2` |

`card_effect_keywords`: none. Flavor text goes to `cards.flavor_text_ja` (`ルーの下に集った武芸者たちは、…`).

#### Nexus BS72-069

`card_levels` (card 1): id 3 = Lv1, id 4 = Lv2.

`card_effects` (card 1):

| id | position | effect_kind | timing_ja | text_ja (start) |
| --- | --- | --- | --- | --- |
| 3 | 1 | `level` | `『このネクサスの配置時』` | 自分のネクサスが「ゼウス」だけのとき、…(3 lines) |
| 4 | 2 | `constant` | NULL | 系統：「眷属」/「締皇」を持つ自分の赤のスピリットすべては、… |

`card_effect_levels`:

| card_effect_id | card_level_id | Source header |
| --- | --- | --- |
| 3 | 3 (Lv1) | `Lv1・Lv2` |
| 3 | 4 (Lv2) | `Lv1・Lv2` |
| 4 | 4 (Lv2) | `Lv2`, no timing |

`card_effect_keywords`: none. Flavor text goes to `cards.flavor_text_ja` (`噴火すると、周囲に雷火を落とすオリン随一の山。…`, including the closing `―『創世書記』神世界図125―`).

#### Magic BS72-075

The Magic fixture has no level line, so no `card_effect_levels` rows and no flavor text.

`card_effects` (card 2):

| id | position | effect_kind | timing_ja | text_ja (start) |
| --- | --- | --- | --- | --- |
| 5 | 1 | `keyword_block` | NULL | `【ミラージュ：コスト2(1)(このカードは手札からセットできる)】` |
| 6 | 2 | `set_active` | `『自分のアタックステップ開始時』` | 相手の手元にあるカードの色3色につき、…(2 lines) |
| 7 | 3 | `main` | NULL | 自分はデッキから2枚ドローする。…(4 lines) |

`card_effect_keywords`:

| card_effect_id | keyword | parameter_ja |
| --- | --- | --- |
| 5 | `mirage` | `コスト2(1)` |

The `メイン：` label is not part of `text_ja`: it becomes the kind `main`. Whether `【セット中】` is a block kind or a keyword of its own is pending #9 (the fixture shows it as a header with a timing, so it is a kind here). The `フラッシュ：` label is seen only in related-card blocks, not in a card's own `<pre>` (pending #9).

## Multilingual text

Pattern decided in [ADR 0005](../adr/0005-text-first-effects-and-translations.md), option 1. Every translatable text has a Japanese source column `X_ja` (NOT NULL where the source always has it) and an English column `X_en` (NULL until translated). Each row with English text carries two foreign keys that describe it.

```mermaid
erDiagram
    translation_sources ||--o{ cards : "sourced"
    translation_statuses ||--o{ cards : "states"
    translation_sources ||--o{ card_effects : "sourced"
    translation_statuses ||--o{ card_effects : "states"
    translation_sources ||--o{ families : "sourced"
    translation_statuses ||--o{ families : "states"

    cards {
        integer id PK
        text name_ja
        text name_en
        text flavor_text_ja
        text flavor_text_en
        integer en_source_id FK
        integer en_status_id FK
    }
    card_effects {
        integer id PK
        text text_ja
        text text_en
        integer en_source_id FK
        integer en_status_id FK
    }
    families {
        integer id PK
        text name_ja
        text name_en
        integer en_source_id FK
        integer en_status_id FK
    }
    translation_sources {
        integer id PK
        text code UK
        text name
    }
    translation_statuses {
        integer id PK
        text code UK
        text name
    }
```

`products`, `brave_details` and `ultimate_details` carry the same two columns (see their tables). The diagram shows three of the tables only.

### translation_sources

Lookup: where an English text came from.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | `official`, `fandom`, `manual`, `machine`. |
| `name` | TEXT | NOT NULL | English display name. |

### translation_statuses

Lookup: how far a translation has come.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | `pending` (not translated yet), `machine` (machine translated, not reviewed), `reviewed` (checked by a person or taken from an official or wiki source), `failed` (the translation did not work). |
| `name` | TEXT | NOT NULL | English display name. |

### Rules

- The Japanese text is the source of truth and is never overwritten by a translation.
- A failed translation is `X_en` NULL with the status `failed`. An error string is **never** stored as text; this fixes the legacy `Error: …` and `Aaaaaa` names.
- `en_source_id` and `en_status_id` describe the row, not a single column: on `cards`, one pair covers `name_en` and `flavor_text_en`. If a row needs different sources for two texts, the model must change (accepted for v1, see ADR 0005).
- `en_source_id` is NULL while there is no English text. `en_status_id` is NOT NULL with the default `pending`. Names on lookups are English only, as in [ADR 0003](../adr/0003-naming-and-schema-versioning.md).
- A third language would add `_xx` columns; it is out of scope.
- Full-text search (FTS5) over `cards.name_*` and `card_effects.text_*` is a build option for [#12](https://github.com/AleFire99/BS_Database/issues/12), not designed here.

## Provenance

Which source pages a row was built from, so a build can be reproduced and an error traced back to its page. The raw HTML cache that fills these tables is defined in [#9](https://github.com/AleFire99/BS_Database/issues/9) and [#10](https://github.com/AleFire99/BS_Database/issues/10). `schema_meta.source_snapshot` ([ADR 0003](../adr/0003-naming-and-schema-versioning.md)) identifies the cache snapshot as a whole; these tables identify single pages.

```mermaid
erDiagram
    sources ||--o{ source_pages : "serves"
    cards ||--o{ card_source_pages : "built from"
    source_pages ||--o{ card_source_pages : "feeds"
    products ||--o{ product_source_pages : "built from"
    source_pages ||--o{ product_source_pages : "feeds"

    sources {
        integer id PK
        text code UK
        text name
        text base_url
    }
    source_pages {
        integer id PK
        integer source_id FK
        text url UK
        text fetched_at
        text content_sha256
        text parser_version
    }
    card_source_pages {
        integer card_id PK, FK
        integer source_page_id PK, FK
    }
    product_source_pages {
        integer product_id PK, FK
        integer source_page_id PK, FK
    }
    cards {
        integer id PK
    }
    products {
        integer id PK
    }
```

### sources

Lookup of the sites the data comes from.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | `batspi` (batspi.com, Japanese card pages) and `fandom` (battle-spirits.fandom.com, English wiki). |
| `name` | TEXT | NOT NULL | English display name. |
| `base_url` | TEXT | NOT NULL | Site root, used to resolve relative links such as `/card/BS7/small/BS72-007.jpg`. |

### source_pages

One row per fetched page.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `source_id` | INTEGER | NOT NULL, FOREIGN KEY to `sources.id` | |
| `url` | TEXT | NOT NULL, UNIQUE | Page address. |
| `fetched_at` | TEXT | NOT NULL | ISO-8601 UTC timestamp of the fetch. |
| `content_sha256` | TEXT | NOT NULL | Hash of the raw HTML in the cache. |
| `parser_version` | TEXT | NOT NULL | Version of the parser that read the page. |

### card_source_pages

Pure junction table. The pages a card was built from.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `card_id` | INTEGER | FOREIGN KEY to `cards.id` | Part of the composite PRIMARY KEY. |
| `source_page_id` | INTEGER | FOREIGN KEY to `source_pages.id` | Part of the composite PRIMARY KEY. |

### product_source_pages

Pure junction table. The pages a product was built from (for example a set list page).

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `product_id` | INTEGER | FOREIGN KEY to `products.id` | Part of the composite PRIMARY KEY. |
| `source_page_id` | INTEGER | FOREIGN KEY to `source_pages.id` | Part of the composite PRIMARY KEY. |

The build always has at least one source page per card; whether that is enforced in the schema or by a build check is left to [#12](https://github.com/AleFire99/BS_Database/issues/12).

## Images

Images belong to the printing, not to the card: BS72-007 has two images for its normal and its secret printing (see [ADR 0004](../adr/0004-card-printing-identity.md)). `printing_images` replaces the legacy `cards.image` path string and the earlier `printings.image` column.

```mermaid
erDiagram
    printings ||--o{ printing_images : "shown by"

    printings {
        integer id PK
        integer card_number_id FK
        integer product_id FK
        integer variant_id FK
    }
    printing_images {
        integer id PK
        integer printing_id FK
        text size
        text path
        text source_url
        text sha256
        integer width
        integer height
        text mime_type
    }
```

### printing_images

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | |
| `printing_id` | INTEGER | NOT NULL, FOREIGN KEY to `printings.id` | |
| `size` | TEXT | NOT NULL, CHECK `size` IN (`small`, `large`) | `small` is the `<img>` under `/card/BS7/small/`, `large` is the linked file under `/card/BS7/` (both seen in the fixtures). Whether more sizes exist is pending #9. |
| `path` | TEXT | NOT NULL | Path relative to the release artefact. The layout is decided in [#13](https://github.com/AleFire99/BS_Database/issues/13). |
| `source_url` | TEXT | NOT NULL | Where the file was downloaded from. |
| `sha256` | TEXT | | Hash of the file; NULL until downloaded. |
| `width` | INTEGER | CHECK `width` > 0 | Pixels; NULL until downloaded (not read from the page). Pending #9. |
| `height` | INTEGER | CHECK `height` > 0 | Pixels; NULL until downloaded. Pending #9. |
| `mime_type` | TEXT | | e.g. `image/jpeg`; NULL until downloaded. |

Table constraint: `UNIQUE (printing_id, size)`. Storage, download and versioning of the files are decided in [#13](https://github.com/AleFire99/BS_Database/issues/13). A row says where an image is and where it came from; it does not require the file to be in the artefact.

### Worked example (BS72-007)

The page links `BS72-007.jpg` and `BS72-007-2.jpg`, each as a small `<img>` and a larger link. Printing ids are those of [ADR 0004](../adr/0004-card-printing-identity.md) (5 = normal, 6 = secret). Which image is the secret art is pending #9 (see ADR 0004), so the mapping below is an assumption: the plain file to the normal printing and the `-2` file to the secret printing.

| id | printing_id | size | source_url (relative) |
| --- | --- | --- | --- |
| 1 | 5 (normal) | `small` | `/card/BS7/small/BS72-007.jpg` |
| 2 | 5 (normal) | `large` | `/card/BS7/BS72-007.jpg` |
| 3 | 6 (secret) | `small` | `/card/BS7/small/BS72-007-2.jpg` |
| 4 | 6 (secret) | `large` | `/card/BS7/BS72-007-2.jpg` |

`path`, `sha256`, `width`, `height` and `mime_type` are filled by the image download of #13 and are not in the fixtures.

### Out of scope for v1

Q&A (ADR 0003), the batspi effect-category tags (カード効果 and 発揮タイミング tags outside the `<pre>`, a possible future source) and structured effects.
