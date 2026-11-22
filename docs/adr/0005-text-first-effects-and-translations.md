# 0005. Text-first effects and translation storage

- Status: Accepted
- Date: 2026-11-14

## Context

The data model epic ([#8](https://github.com/AleFire99/BS_Database/issues/8)) has to store card effects and English translations. Two decisions are involved and neither has an ADR yet.

**Effects.** At Gate A of epic #8 (2026-11-14) the owner chose a **text-first** model for effects: store the effect text as printed, split into effect blocks, and do not parse it into conditions and actions in v1. The sister project BSS_app models effects as structure (`Steps`, `Conditions`, `EffectSteps`). That path stays open as a future, additive extension.

Evidence from the fixtures (see [field-inventory.md](../data-model/field-inventory.md), rows `effect_blocks`, `keyword_blocks`, `main_effect`, `flash_effect`, `set_effects`, `flavor_text`):

- **Level-scoped blocks with a timing.** [card_spirit.html](../../tests/fixtures/html/card_spirit.html) (BS72-007) has `Lv1・Lv2『自分のアタックステップ開始時』` and `Lv2『自分のアタックステップ』`, each followed by the effect text. One block can apply to several levels.
- **A block with a level and no timing.** [card_nexus.html](../../tests/fixtures/html/card_nexus.html) (BS72-069) has `Lv2` followed by a constant effect, next to `Lv1・Lv2『このネクサスの配置時』`.
- **Magic and keyword blocks.** [card_magic.html](../../tests/fixtures/html/card_magic.html) (BS72-075) has `【ミラージュ：コスト2(1)(このカードは手札からセットできる)】`, `【セット中】『自分のアタックステップ開始時』` and `メイン：`. `フラッシュ：` is seen only in related-card blocks of that page.
- **Flavor text.** `フレーバーテキスト：` is on the Spirit and the Nexus fixtures, absent on the Magic one.
- **Effect categories.** The batspi page also shows effect-category tags outside the `<pre>`. They are a possible future source and are not modelled.

**Translations.** The legacy pipeline machine-translates names and effects and stores the result in the same column as the source. Failed translations end up as data: the legacy database holds error strings (`Error: …`) and junk (`Aaaaaa`) as names (see [current-schema.md](../data-model/current-schema.md)). The target model needs a storage pattern for Japanese source text, English text, and where each English text came from.

Naming, lookups and keys follow [ADR 0003](0003-naming-and-schema-versioning.md) and [ADR 0004](0004-card-printing-identity.md).

## Decision drivers

- Keep the Japanese source text and make every English text redoable, so a bad translation never destroys data.
- Record where an English text came from and whether it was reviewed.
- Simple SQL and real foreign keys, as the database is built in batch and read by apps and bots.
- Consistent with the ADR 0003 conventions: snake_case, surrogate `id`, lookups with `code` and English `name`.
- Effects stay printed text in v1; the structure must not be blocked for later.
- Only Japanese and English are needed now, but the pattern should not make a third language impossible.

## Options considered

1. **Per-column `_jp` / `_en` with per-row translation metadata.** Each translatable text has an `X_jp` and an `X_en` column. Each row with English text carries `en_source_id` and `en_status_id` pointing to two small lookups.
   - Pros: plain SQL with no extra joins; foreign keys keep the metadata valid; readable queries; matches the `name_jp` / `name_en` columns already in [ADR 0003](0003-naming-and-schema-versioning.md) and [ADR 0004](0004-card-printing-identity.md).
   - Cons: a third language needs new columns (a schema change); the source and status are per row, not per column, so one row cannot say that its name is official and its flavor text is machine translated.
2. **A generic `translations(entity, row_id, field, lang, text, source)` table.**
   - Pros: any number of languages and fields without schema changes; metadata per field.
   - Cons: this is an entity-attribute-value design: `entity` and `row_id` cannot be foreign keys, so integrity is not enforced; every read needs a join with a filter on entity, field and language; there is no `NOT NULL` for the source text.
3. **One `texts` table referenced by a foreign key from each text column.**
   - Pros: uniform storage; foreign keys work; room for per-text metadata and more languages.
   - Cons: every text column becomes a join; the schema is hard to read and to query by hand; the Japanese source loses its place next to the entity.

## Decision

Use **option 1** (owner choice). Details are in [target-schema.md](../data-model/target-schema.md#multilingual-text).

- **Columns.** Every translatable text has `X_jp` (the source; NOT NULL where the source always has it) and `X_en` (NULL until translated). This applies to `cards` (name, flavor text), `card_effects` (timing, text), `families`, `products` and the Brave and Ultimate side tables.
- **Row metadata.** A row with English text carries `en_source_id` (to the lookup `translation_sources`: `official`, `fandom`, `manual`, `machine`) and `en_status_id` (to the lookup `translation_statuses`: `pending`, `machine`, `reviewed`, `failed`). Both lookups follow ADR 0003 (`code` plus English `name`).
- **Failures.** A failed translation is stored as `X_en` NULL with the status `failed`. An error string is **never** stored as text.
- **Effects are text-first.** `card_effects` holds one row per effect block of the `<pre>`, in printed order. The timing (`『自分のアタックステップ』`) is kept as text. `card_effect_levels` links a block to the `card_levels` it applies to, and `card_effect_keywords` links a block to a `keywords` lookup row with an optional parameter text (`コスト2(1)` for Mirage). Alternate costs and conditions are **not** structured in v1.
- **Structured effects stay a future option.** A later version can add tables in the BSS_app style (`Steps`, `Conditions`, `EffectSteps`) that reference `card_effects` rows. This is additive: the text rows stay the source of truth and nothing is migrated.
- **Provenance.** Source pages are recorded in `sources`, `source_pages` and the junctions `card_source_pages` and `product_source_pages`. Images move from the `printings.image` column to `printing_images` (see [ADR 0004](0004-card-printing-identity.md)).
- **Search.** Full-text search (FTS5) over `cards.name_*` and `card_effects.text_*` is a build option for [#12](https://github.com/AleFire99/BS_Database/issues/12), not designed here.
- **Out of scope for v1.** Q&A (see ADR 0003), batspi effect-category tags, structured effects.

## Consequences

- Reading a card in either language needs no extra join. Translation quality can be filtered with `en_status_id`.
- A bad machine translation can be redone from the stored Japanese text, and failures are visible as a status, not as strange names.
- The source and status are one pair per row. If one row ever needs different sources for two texts, the model needs a change (for example per-field columns). This is accepted for v1.
- Adding a language is a schema change (new `_xx` columns and metadata). Accepted: only Japanese and English are in scope.
- Effect text cannot be queried by structure (for example "all cards that draw 2"); users search the text. The structured path is open.
- Open items for [#9](https://github.com/AleFire99/BS_Database/issues/9): how effect blocks are segmented across eras, Brave and Ultimate block layouts, the keyword list, whether flavor text differs per printing, and the image sizes. DDL is written in [#12](https://github.com/AleFire99/BS_Database/issues/12), image storage in [#13](https://github.com/AleFire99/BS_Database/issues/13), translation workflow in [#11](https://github.com/AleFire99/BS_Database/issues/11).

## Links

- Issue: [#31](https://github.com/AleFire99/BS_Database/issues/31) (epic [#8](https://github.com/AleFire99/BS_Database/issues/8))
- Builds on [0003](0003-naming-and-schema-versioning.md) and [0004](0004-card-printing-identity.md).
- Model: [target-schema.md](../data-model/target-schema.md)
