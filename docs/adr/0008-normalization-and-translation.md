# 0008. Normalization and translation design

- Status: Proposed
- Date: 2026-11-15

## Context

The scraper ([#10](https://github.com/AleFire99/BS_Database/issues/10)) produces Japanese-only parsed pages in `data/parsed/`. The normalization epic ([#11](https://github.com/AleFire99/BS_Database/issues/11)) turns them into records shaped like the target schema, with codes for lookups and an English value for every translatable text.

Facts that shape the choice:

- The legacy `normalize.py` works on English machine-translated JSON and rewrites files in place. Its heuristics only patch bad English (see the audit below).
- [ADR 0005](0005-text-first-effects-and-translations.md) stores each English text next to its Japanese source, with `en_source_id` and `en_status_id` per row.
- [ADR 0007](0007-source-of-truth.md) makes batspi the only source. Its `<h3>` sometimes prints an English name, transcribed by the wiki.
- The Japanese source separates families with `・`, so no splitting heuristics are needed.
- The `ja` to `jp` rename was decided at Gate A on #11 ([#91](https://github.com/AleFire99/BS_Database/issues/91)): `jp` is used everywhere, see the amendment in [ADR 0003](0003-naming-and-schema-versioning.md).

## Decision drivers

- Deterministic and idempotent output that CI can check.
- Curated data lives in reviewable text files, not in code.
- No network and no secret needed in CI.
- Machine translation is cached, so reruns are free and stable.
- A clear boundary with the DB loader.

## Options considered

1. **Keep the legacy module and extend it.** Cheap at first. Cons: it rewrites files in place, depends on English input, and its heuristics are tied to machine-translation artefacts.
2. **Normalize inside the DB loader (#12).** One stage fewer. Cons: the loader would need glossaries and a translator, and it could not be tested without a database.
3. **A separate non-destructive stage with CSV glossaries and a pluggable translator.** More files. Pros: pure per page, testable, reviewable data.

## Decision

Use **option 3**.

### Stage and boundary

- The stage is non-destructive. It reads `data/parsed/` and writes `data/normalized/`.
- It is pure per page, idempotent and deterministic. Running it twice changes nothing.
- **#11 / #12 boundary:** normalize maps every Japanese glyph to a code and emits records shaped like the schema. The #12 loader only inserts rows.

### Glossaries

- One file per kind: `data/glossary/<kind>.csv` for `colors`, `symbols`, `card_types`, `rarities`, `variants`, `product_types`, `keywords` and `families`.
- Columns: `jp,code,en,notes`.
- `families.csv` adds `aliases_en` and a `no_split` flag, for compound names that contain `・` and must not be split.
- Each file is UTF-8, sorted by `code`, and has a single owner-curated source of truth.

### Translator

- A `Translator` protocol. The first engine is DeepL (key `BSDB_DEEPL_API_KEY`, local only).
- The DeepL engine maps the internal language code `jp` to the API code `JA`. The internal codes (`jp`, `en`) are a closed list, not ISO 639-1.
- CI uses `NullTranslator`, which never calls the network.
- **Cache:** SQLite, keyed by (engine, src, tgt, sha256 of the text).

### Lookup order

For names and families: glossary, then the batspi `<h3>` name, then the cache, then the engine.

### Machine-translation scope in v0.5.0

- Card names, product names and families only.
- Effect, flavor and Brave/Ultimate condition `_en` stay NULL with status `pending`.

### Canonical English family names

Legacy English names first (`family_mapping`, v0.1.0 snapshot), with machine translation as the fallback. The owner reviews them in [#96](https://github.com/AleFire99/BS_Database/issues/96).

### Translation source codes

- Add the code `batspi` for English names printed on the batspi `<h3>`, with status `reviewed`.
- This closes coverage-matrix gap #3 and corrects the use of `official` in [ADR 0007](0007-source-of-truth.md).

### Row-pair rule

This clarifies [ADR 0005](0005-text-first-effects-and-translations.md).

- `en_source_id` and `en_status_id` describe the row's **non-NULL** English texts.
- A NULL `X_en` always means "not translated".
- Example: a card can have `name_en` machine-translated (status `machine`) while `flavor_text_en` stays NULL.

### Error policy

| Unmapped term | Default | With `--strict` |
| --- | --- | --- |
| Closed lookup (color, symbol, card type, rarity, variant, product type) | Error | Error |
| Family or keyword | Warning | Error |

Every unmapped term is listed in the report.

### Legacy audit

One verdict per legacy rule. This table is the binding cleanup list for [#92](https://github.com/AleFire99/BS_Database/issues/92) and [#93](https://github.com/AleFire99/BS_Database/issues/93).

| Legacy piece | Verdict |
| --- | --- |
| `normalize.py` as a flat module with `normalize_tree` (rewrites files in place) | **Delete.** Replace with the `bs_database/normalize/` package (`records.py`, `rules.py`, `pipeline.py`). The output is non-destructive. |
| `split_family` (`,` / ` and ` / `:`, plus the "Next Generation" / "New" / "Different" heuristics) | **Delete.** The heuristics only patched English machine translation. The Japanese source separates families with `・`. Compound names that must not be split are marked in the glossary. |
| `transform_family_names` ("snake" to Dark Snake, strip the/and/a, `.title()`, drop a trailing "s", `list(set)`) | **Delete.** The glossary replaces it, and the output order becomes stable. |
| `load_family_mappings` and `data/family_mapping.txt` | **Migrate, then delete.** The 41 pairs become `aliases_en` in `families.csv`. |
| `normalize_type` (strip `(...)`, capitalize) | **Delete.** The `card_types.csv` JP to code mapping replaces it. |
| Image backslash fix | **Delete.** The new parser already emits clean URLs. Images belong to [#13](https://github.com/AleFire99/BS_Database/issues/13). |
| `settings.json_dir`, `settings.family_mapping_path`; `cli normalize` wired to `json/card_json` | **Rewrite.** Use `parsed_dir`, `normalized_dir`, `glossary_dir` and `cache_dir`. |
| `tests/test_normalize.py`, `tests/goldens/normalized/`, normalize half of the `tests/test_cli.py` golden chain | **Delete or replace** with new tests. Keep the inputs that `db.py` still needs until #12. |
| pyproject coverage exclusion for `normalize.py`; description mentioning "translation" | **Remove the exclusion.** Update the description. |
| `_COLOR_MAP` in `db.py` (symbol to colour, `white` missing) | **Move to `colors.csv` and `symbols.csv`** in #11. The rest of `db.py` is rewritten in #12 under the same keep/rewrite/delete rule. |

## Consequences

- Positive:
  - Reviewable curated data, offline CI, stable re-runs.
  - The loader stays simple.
- Negative and follow-up work:
  - Glossaries need owner curation ([#96](https://github.com/AleFire99/BS_Database/issues/96)).
  - Effect text stays untranslated in v0.5.0.
  - The parsed schema is 2.0.0 after the `_jp` rename, so older parsed JSON must be re-parsed from the HTML cache.
- Work is split into [#92](https://github.com/AleFire99/BS_Database/issues/92) (glossaries), [#93](https://github.com/AleFire99/BS_Database/issues/93) (normalize package), [#94](https://github.com/AleFire99/BS_Database/issues/94) (translator), [#95](https://github.com/AleFire99/BS_Database/issues/95) (wiring and strict mode) and #96 (full scrape and audit).

## Amendments

Recorded during [#92](https://github.com/AleFire99/BS_Database/issues/92) to [#95](https://github.com/AleFire99/BS_Database/issues/95). The status stays Proposed.

| Id | Amendment |
| --- | --- |
| D1 | A ninth file, `family_legacy_en.csv` (`legacy_en,preferred_en,jp,notes`), holds the 41 legacy English family pairs. `jp` is empty until #96. |
| D4 | `rarities.csv` has an extra `sort_order` column (a unique integer). |
| D5 | An unmapped variant note means `normal`, not an error. |
| D6 | `product_types.csv` `jp` is an optional title marker, not an identity. |
| D7 | Recorded in [#95](https://github.com/AleFire99/BS_Database/issues/95). A glossary row whose `code` is empty is **uncurated**, not unmapped: `unmapped` means no row, so `--strict` can pass while families are still being curated (the target schema allows `families.code` NULL until assigned). `NormalizedPage` gains `uncurated` and `NORMALIZED_SCHEMA_VERSION` becomes 1.1.0. Product names are machine-translated together with card names and families. The report and strict mode are described in [normalization](../architecture/normalization.md). |

## Links

- Issues: [#11](https://github.com/AleFire99/BS_Database/issues/11), [#91](https://github.com/AleFire99/BS_Database/issues/91), [#92](https://github.com/AleFire99/BS_Database/issues/92), [#93](https://github.com/AleFire99/BS_Database/issues/93), [#94](https://github.com/AleFire99/BS_Database/issues/94), [#95](https://github.com/AleFire99/BS_Database/issues/95), [#96](https://github.com/AleFire99/BS_Database/issues/96)
- Builds on [0003](0003-naming-and-schema-versioning.md), [0005](0005-text-first-effects-and-translations.md) and [0007](0007-source-of-truth.md).
