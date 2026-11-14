# 0003. Naming conventions, BSS_app alignment and schema versioning

- Status: Proposed
- Date: 2026-11-14

## Context

The data model epic ([#8](https://github.com/AleFire99/BS_Database/issues/8)) designs a new normalized schema. Several tasks ([#28](https://github.com/AleFire99/BS_Database/issues/28) to [#32](https://github.com/AleFire99/BS_Database/issues/32)) and the DB build ([#12](https://github.com/AleFire99/BS_Database/issues/12)) need one shared set of naming rules and a versioning scheme before any DDL is written.

Facts that shape the choice:

- The legacy schema (see [current-schema.md](../data-model/current-schema.md)) is already snake_case and plural, but it is inconsistent: `cards.card_id` is a TEXT print number that clashes with the `<table>_id` foreign key pattern, and `core_requirements.battlePoints` is camelCase.
- The sister project [BSS_app](https://github.com/AleFire99/BSS_app) uses PascalCase plural tables quoted with backticks, `<Singular>ID` integer primary keys (except `Cards.CardID`, a TEXT such as `BSS01-001`), free-text `Cards.Rarity`, no schema versioning and no i18n.
- Gate A decisions on #8: SQLite ([ADR 0002](0002-storage-technology.md)), snake_case plural tables with `id` primary keys, text-first effects, and surrogate integer primary keys with the printing number as a UNIQUE column on printings.
- Each release rebuilds the database from scratch (ADR 0002), so in-place migrations are not needed.

## Decision drivers

- One predictable convention that the Python and SQLAlchemy code and SQL users can guess without reading the DDL.
- Continuity with the existing legacy schema and package.
- Recognisable structure for people who know BSS_app.
- No quoting needed in hand-written SQL.
- Consumers can cheaply check which schema a file contains.

## Options considered

1. **Adopt BSS_app conventions as-is.** Maximum parity, and BSS_app tooling could be reused unchanged. Cons: PascalCase and backtick quoting are unidiomatic for Python and SQLAlchemy, they contradict the existing legacy schema and the Gate A decision, and a TEXT primary key on cards conflicts with the surrogate key decision.
2. **snake_case per this ADR.** Lower snake_case plural tables, `id` primary keys, no quoting, natural keys as UNIQUE constraints. Fits Python idiom, the legacy schema and Gate A. Cons: names differ from BSS_app, so any shared tooling needs a mapping (views can bridge this).
3. **Mixed.** snake_case for new tables, PascalCase where BSS_app has an equivalent. Cons: two styles in one file, so nobody can predict a name, and it is the worst option for maintainability.

## Decision

Use **option 2**: snake_case conventions, keeping the BSS_app entity split but not its spelling.

### Naming rules

- **Tables:** lower snake_case, plural nouns (`cards`, `printings`, `card_types`).
- **Junction tables:** `<a_singular>_<b_plural>` (`card_colors`, `card_families`), as in the legacy schema.
- **Columns:** lower snake_case, singular (`battle_points`, not `battlePoints`).
  - Booleans are named `is_…` or `has_…`.
  - Timestamps are named `…_at` and stored as ISO-8601 UTC TEXT.
  - Language variants use suffixes: `name_ja`, `name_en`.
  - Lookup rows have a stable `code` (for example `red`) plus display names.
- **Keys:**
  - The primary key is `id INTEGER PRIMARY KEY` (a rowid alias).
  - The only exception is pure junction tables (only foreign keys plus optional attributes such as a count): they use a composite primary key of their foreign key columns, as in BSS_app.
  - Foreign keys are `<referenced_singular>_id`.
  - Natural keys are UNIQUE constraints and never primary keys (for example `printings.number`, `sets.code`).
  - The legacy `cards.card_id` (TEXT print number) is retired because it clashes with the foreign key convention.
- **Constraint and index names:** `pk_`, `fk_`, `uq_`, `ck_` or `ix_` followed by `<table>_<cols>`. Implemented as a SQLAlchemy `naming_convention` in #12.
- **Quoting:** none required. Avoid reserved words as bare table names (`order`, `set`); plural names such as `sets` are safe. Columns such as `level` are legal unquoted in SQLite, but each such case is flagged in review.
- **Enum-like values:** lookup tables with foreign keys instead of CHECK lists, so a new card type or rarity needs no schema change.

### BSS_app → BS_Database

The concepts (lookups, junctions, reductions with a count, per-level rows, effects linked to levels and keywords) are kept. Names follow the rules above. Entities not yet designed have tentative names, finalised in [#29](https://github.com/AleFire99/BS_Database/issues/29), [#30](https://github.com/AleFire99/BS_Database/issues/30) and [#31](https://github.com/AleFire99/BS_Database/issues/31).

| BSS_app | BS_Database | Reason for the deviation |
| --- | --- | --- |
| `Cards` (`CardID` TEXT PK, e.g. `BSS01-001`) | `cards` plus `printings` (`id` integer PK, `number` UNIQUE on printings) | Surrogate keys (Gate A); the printing number becomes a UNIQUE natural key. Exact split finalised in #29. |
| `Cards.Rarity` (free TEXT) | `rarities` lookup, `printings.rarity_id` (tentative, #29) | Enum-like values use lookup tables. |
| `CardTypes` | `card_types` | Case and key style; `Name` becomes a stable `code` plus display names. |
| `Sets` | `sets` | Case and key style; `Name` (e.g. `BSS01`) becomes a UNIQUE `code` plus display names. |
| `Colors` | `colors` | Case and key style; `Name` becomes a stable `code` plus display names. |
| `Symbols` (`ColorID`) | `symbols` (`color_id`) | Case and key style only. |
| `Subtypes` | `families` (tentative, #29) | Battle Spirits calls them families (系統); the legacy schema already uses `families`. |
| `Keywords` | `keywords` | Case and key style only. |
| `Steps` | `steps` (tentative, #31) | Case only. Effects are text-first in v1, so this may be deferred. |
| `Conditions` | `conditions` (tentative, #31) | Case only. Effects are text-first in v1, so this may be deferred. |
| `CardColors` | `card_colors` | Case and key style only. |
| `CardSymbols` | `card_symbols` | Case and key style only. |
| `CardSubtypes` | `card_families` | Follows the rename of `Subtypes`. |
| `CardReductions` (`CardID`, `ColorID`, `Count`) | `card_reductions` (`card_id`, `color_id`, `count`) | Case only; `count` is a legal column name. Whether it hangs off the card or the printing is final in #30. |
| `Core` (`CoreID`, `CardID`, `Level`, `BP`, `Cores`) | `card_levels` (tentative, #30) | Singular table name breaks the plural rule; `BP` becomes `battle_points`, `Cores` becomes a clearer name chosen in #30. |
| `Effects` (`EffectID`, `CardID`, `ConditionID`, `Description`) | `effects` (tentative, #31) | Case and key style; `Description` becomes the text-first effect text, with the exact column set decided in #31. |
| `EffectLevels` (`EffectID`, `CoreID`) | `effect_levels` (tentative, #31) | References `card_levels` instead of `Core`. |
| `EffectKeywords` (`EffectID`, `KeywordID`, `Modifier`) | `effect_keywords` (tentative, #31) | Case and key style only. |
| `EffectSteps` | `effect_steps` (tentative, #31) | Case only. May be deferred with text-first effects. |
| `QA_cards` (`QA_cardID`…) | none | Out of scope for v1. |
| `QA_keywords` (`QA_keyID`…) | none | Out of scope for v1. |

If BSS_app tooling is ever shared, compatibility views can map the names without changing the core schema.

### Schema versioning

- `PRAGMA user_version` holds `major * 10000 + minor * 100 + patch`, so minor and patch are capped at 99. Consumers can check it with one integer read. Example: schema `1.2.0` is stored as `10200`, and `0.3.7` as `307`.
- A single-row `schema_meta` table records the details. It is a deliberate exception to the plural rule (it holds one record, not a collection), and the single row is enforced with `id INTEGER PRIMARY KEY CHECK (id = 1)`:

| Column | Type | Meaning | Example |
| --- | --- | --- | --- |
| `schema_version` | TEXT | Schema SemVer | `1.2.0` |
| `data_version` | TEXT | Release tag of the data | `v0.3.0` |
| `built_at` | TEXT | ISO-8601 UTC build time | `2026-11-14T10:00:00Z` |
| `source_snapshot` | TEXT | Identifier of the raw source snapshot used | to be defined in #9/#12 |
| `generator` | TEXT | `bs_database` package version that built the file | `0.2.0` |

- Schema SemVer rules:
  - major: a breaking rename or removal;
  - minor: an additive table or column;
  - patch: constraint or documentation change only.
- The data version (git tag of the release) is independent of the schema version. A new data release can keep the same schema version.
- No in-place migrations (ADR 0002). Breaking changes are listed in the CHANGELOG.
- Implementation is handed off to #12.

## Consequences

- #28 to #32 and #12 follow these rules; a deviation needs an amendment to this ADR.
- Names differ from BSS_app, so shared tooling needs a mapping or views.
- The legacy tables and columns (`cards.card_id`, `battlePoints`) are renamed when the package schema is rebuilt in #12.
- The tentative names in the table may change once #29 to #31 model the real entities. Those edits are allowed while this ADR is Proposed.
- Consumers get a cheap integer compatibility check and a self-describing file.
- The SQLAlchemy `naming_convention` and the `schema_meta` writer must be implemented in #12.

## Links

- Issue: [#27](https://github.com/AleFire99/BS_Database/issues/27) (epic [#8](https://github.com/AleFire99/BS_Database/issues/8))
- Builds on [0002](0002-storage-technology.md).
