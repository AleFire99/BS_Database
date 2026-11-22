# Architecture overview (current state)

This document describes the `bs_database` package as restructured in E2 ([#7](https://github.com/AleFire99/BS_Database/issues/7)). The earlier script-based prototype is available at tag `v0.1.0`. Roadmap epics are listed in the [top-level README](../../README.md).

## Package layout

```mermaid
flowchart LR
    subgraph bs_database
        CLI["cli<br/>(bsdb: scrape, normalize, build)"]
        SET["settings<br/>(BSDB_* env)"]
        LOG["log"]
        subgraph ingest["ingest (#67, #68, #72, #73)"]
            POL["policy<br/>(robots, deny list, challenge)"]
            HTTP["http"]
            CACHE["cache"]
            STATE["state"]
            PIPE["pipeline"]
            PSTORE["parsed_store, atomic"]
            REPORT["report"]
        end
        subgraph parsers["parsers (#69, #70, #71)"]
            MODELS["models"]
            BPARSE["batspi: index, set_page, promo_list, numbers, card, card_text, card_sections"]
        end
        NORM["normalize"]
        GLOS["glossary<br/>(loader, validator)"]
        BUILD["build<br/>(reader, grouping, loaders)"]
        SCHEMA["schema.sql"]
    end

    PJ[("data/parsed/*/*.json")]
    NJ[("data/normalized/*/*.json")]
    GL[("data/glossary/*.csv")]
    DB[("battle_spirits.db<br/>(untracked build output)")]

    CLI --> SET
    CLI --> LOG
    CLI --> NORM
    CLI --> BUILD
    CLI --> PIPE
    PIPE --> HTTP
    PIPE --> CACHE
    PIPE --> STATE
    PIPE --> PSTORE
    PIPE --> REPORT
    PIPE --> BPARSE
    HTTP --> POL

    PSTORE --> PJ
    PJ --> NORM
    GL --> GLOS
    GLOS --> NORM
    NORM --> NJ
    NJ --> BUILD
    GL --> BUILD
    SCHEMA --> BUILD --> DB
```

The `ingest` and `parsers` packages hold the target layout of the scraper rewrite ([#10](https://github.com/AleFire99/BS_Database/issues/10)). They are complete: `bsdb scrape` runs the whole pipeline (HTTP client, cache, parsers, state store, parsed JSON, run report), documented in [scraper.md](scraper.md). The normalized JSON is loaded into the database by `bsdb build` ([build.md](build.md), [#120](https://github.com/AleFire99/BS_Database/issues/120)). The legacy scrapers and `bsdb images` were removed in [#66](https://github.com/AleFire99/BS_Database/issues/66); they are at tag `v0.1.0` or commit `f90747b`.

### Card page parser

`bs_database.parsers.batspi.card.parse_card_page(html, url)` ([#70](https://github.com/AleFire99/BS_Database/issues/70), [#71](https://github.com/AleFire99/BS_Database/issues/71)) is a pure function: cached HTML in, a `CardPage` out, with no network, translation or file I/O. It reads identity (card numbers, `name_jp`, `name_en`) and gameplay values (type, cost, reduction, colours, families, levels, symbols, plus `fusion_bp_bonus` for Brave and `overclock` for Ultimate) of every card block in the card region of the page. Erratum and trial-spec blocks, Q&A and the related listing are skipped. The DTOs are frozen slotted dataclasses in `bs_database.parsers.card_models`, JSON-ready through `dataclasses.asdict`, and carry `SCHEMA_VERSION` (`2.1.0`, [ADR 0010](../adr/0010-parsed-schema-type-marks-levels-symbols-credits.md)). #71 added, per card number, the effect blocks, side conditions, credits and flavour text (`CardEntry.text`), and, per page, the printings and gallery images (`CardPage.printings`, `CardPage.images`). Unknown cost, level, symbol or header syntax raises `ParseError` instead of being guessed.

- **Number source.** The number in the print heading comes first, because it is the only per-block source (the `span.cardno` order differs on promo pages and the spans lack the `(A)`/`(B)` face on flip pages). The page's own `span.cardno` values are a set cross-check, and a mismatch is logged as a warning. Pages without a heading number take the span at the same position. This clarifies the "cardno span is authoritative" rule of [ADR 0007](../adr/0007-source-of-truth.md) for #12; the ADR itself is unchanged.
- **Literal values.** Colours, symbols, types and families keep the Japanese glyphs of the source; mapping to codes is the loader's job (#12).
- **Per-number differences (#63).** Gameplay fields that differ between numbers with the same name are logged at INFO and listed in `CardPage.differences`, so #12 can decide the card-versus-number grouping.
- **Effects (`card_text`).** The text after the level line is split into `Effect` blocks in printed order. `form` is `header` (a `Lv…`, `メイン`/`フラッシュ`, `【…】`/`《…》` or `『…』` header line plus its body), `keyword_line` (a one-line `【…】` block such as `【ミラージュ：…】` or `《神託》〔…〕`, where `header` equals `text`) or `plain` (text before the first header). Level scope, label, keywords and timing are raw facts; `effect_kind` is derived by the loader (#12). Keywords come from the header only, split at the first `：`, and the parameter is kept as printed (including a trailing reminder in parentheses). Fusion (`合体条件`), summon (`【召喚条件：…】`) and overclock (`OC条件`) lines are exposed as side conditions and are not effects. A line that starts like a level header but does not match the header grammar raises `ParseError`.
- **Credits and flavour.** `イラスト：` and `コンセプト：` lines become `Credit(name, note)`, where `note` is a trailing parenthesised group (the product in which that credit applies). Matching credits to printings is left to the loader. The flavour text keeps its source line breaks; `flavor_note` is the text after the `フレーバーテキスト：` label. An unknown trailer line raises `ParseError`.
- **Printings (`card_sections`).** Rows of the `収録` section (one-number paragraph, per-number list, or the nested promo list) become `Printing` rows with the product link (made absolute with `urljoin`), `detail_jp`, raw `rarity` and `note_jp`. A face-less label (`BS52-TX01`) gives one row per face. The block-icon section is joined by product name and number for `product_code`, `block_icon` and `release_date` (each block row is consumed once per number); block-icon rows with no `収録` row become printings with `rarity=None` and `section="ブロックアイコン"`. Rarity, product and variant mapping is the loader's job.
- **Images.** Each `ul.ppy-imglist` item becomes a `CardImage` with the large and small URLs read from the page (never built from a name) and the caption lines; the first caption line is the card number. Assigning images to printings is left to #12/#13.
- **#63 text differences.** `CardPage.differences` also compares `effects`, the side conditions and `flavor`. Credits and `flavor_note` are printing-level and excluded.
- **Type marks, level tokens, symbol variants and extra credits (#108, ADR 0010).** The type line may start with a class (`契約`, `トークン`: `Gameplay.card_class`) and carry a bracketed mark (`禁止カード`, `光`, `闇`: `Gameplay.type_mark`); `card_type` stays one of the five base types. The level line is read by a tokenizer, not by splitting on blanks: `<C2>Lv2` has no core count (`Level.cores` is `None`, the token is `Level.count_condition`), a remark such as `/真界放` or a battle point printed as text (`X0000`) goes to `Level.note`. `シンボル：EX白` keeps `EX` in `SymbolCount.variant` and `神(青)` keeps the colour in `SymbolCount.color`. `プロデュース`, `ペイント`, `書`, `写真` and `コラボレート` credits go to `CardText.other_credits` (`RoleCredit(role, name, note)`); credit labels take a full-width or ASCII colon; an empty `イラスト：` is skipped with a warning. All values are the printed literals; what a mark means is not stated by the source and is left to the owner (ADR 0010).
- **Fields without a schema column.** `deck_limit` (`制限カード<N>`), `card_class`, `type_mark`, `Level.count_condition` and `note`, `SymbolCount.variant` and `color`, `other_credits`, `overclock`, `OC条件`, `コンセプト`, `Printing.detail_jp` and `note_jp`, `flavor_note` and the effect `form`/`label` structure are parsed but have no column in the [target schema](../data-model/target-schema.md); #12 decides where they go.
- **Coverage gate.** `pyproject.toml` runs coverage with branches and fails below 97% over `ingest/`, `parsers/`, `glossary.py`, `review/`, `normalize/`, `translate/` and `build/`; `cli.py` is not gated. CI already runs `uv run pytest --cov`.

## Target data flow

The pipeline that the roadmap epics build, following the [scraping policy](../sources/policy.md), [ADR 0006](../adr/0006-scraping-and-redistribution-policy.md) and [ADR 0007](../adr/0007-source-of-truth.md). batspi.com is the only source fetched in v1. The fandom wiki is dropped ([fandom.md](../sources/fandom.md)), and the official site is a survey only ([official.md](../sources/official.md)). Field-level coverage is in the [coverage matrix](../sources/coverage-matrix.md).

```mermaid
flowchart LR
    BAT["batspi.com<br/>(JP fan wiki)"]
    FAN["battle-spirits.fandom.com<br/>(dropped for v1)"]
    OFF["battlespirits.com<br/>(survey only)"]

    subgraph E5["Scraper (#10)"]
        GATE["Policy gate<br/>robots.txt, deny list,<br/>3 s delay, User-Agent"]
        CACHE[("Raw-HTML cache<br/>data/cache/html")]
        PARSE["Parsers<br/>precedence per ADR 0007"]
    end

    NT["Normalize and translate (#11)"]
    BUILD["SQLite build and validation (#12)"]
    REL["Release artefact (#14)<br/>data and text, no images"]

    BAT --> GATE --> CACHE --> PARSE --> NT --> BUILD --> REL
    FAN -. "not fetched" .-> GATE
    OFF -. "not fetched" .-> GATE
```

## CLI flow

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant C as bsdb (cli)
    participant I as ingest.pipeline
    participant P as data/parsed
    participant N as normalize
    participant NJ as data/normalized
    participant D as build.build_database
    participant DB as SQLite

    Dev->>C: bsdb scrape
    C->>I: run_pipeline (index, sets, cards)
    I->>P: parsed JSON per card page, state in ingest.db
    C-->>Dev: run report, exit code 0, 1 or 3
    Dev->>C: bsdb normalize
    C->>N: normalize_tree(parsed_dir, normalized_dir, glossary, translator)
    N->>P: read parsed JSON (never written)
    N-->>C: pages written, unmapped and uncurated terms, translations
    Dev->>C: bsdb build [--out PATH] [--built-at ISO]
    C->>D: build_from_directories(out, normalized_dir, glossary_dir)
    D->>NJ: read each normalized page (never written)
    D->>DB: schema.sql, lookups, cards, printings, effects, images in one transaction
    D->>DB: foreign_key_check, then atomic replace of the output
    C-->>Dev: rows per table and warning counts
```

## Components

| Module | Responsibility | Inputs | Outputs |
| --- | --- | --- | --- |
| `bs_database.cli` | Typer app (`bsdb`): `scrape` (pipeline, [scraper.md](scraper.md)), `normalize`, `build` ([build.md](build.md)), global `--log-level` and `--version` | `Settings`, command options | calls the modules below |
| `bs_database.settings` | `Settings` (pydantic-settings): `BSDB_*` env and `.env`, paths derived from `data_dir` | environment | URLs, directories, request delay |
| `bs_database.log` | `configure_logging` | level name | root logger setup |
| `bs_database.ingest.policy` | Scraping policy helpers: base URL, User-Agent, deny list, robots.txt split and check, challenge detection | URL, robots rules, page text | `StopRun` or a boolean |
| `bs_database.ingest.http` | HTTP client: policy gate, pacing, request budget, backoff, `Skipped` and `StopRun` outcomes (#67) | URL | `Fetched`, `Skipped` or a `StopRun` |
| `bs_database.ingest.cache` | Raw-HTML cache with sidecar, and `CachedFetcher` (cache first, then the client) (#68) | URL | `CachedPage` or `Skipped` |
| `bs_database.ingest.atomic` | Atomic file write (temp file, fsync, rename), shared by the cache and the parsed store | path, bytes | file |
| `bs_database.ingest.state` | Per-page state machine and SQLite store: resume, retry, permanent failures ([ingestion-state.md](ingestion-state.md), #72) | page transitions | `data/state/ingest.db` |
| `bs_database.ingest.pipeline` | `run_pipeline`: index, sets and cards through the cache, parsers and state store (#73) | `Settings`, `CachedFetcher`, `StateStore`, `RunOptions` | `RunReport` |
| `bs_database.ingest.parsed_store` | Parsed card pages as versioned JSON, named by the URL digest (#73) | `CardPage`, `CachedPage` | `data/parsed/<source>/<sha256>.json` |
| `bs_database.ingest.report` | `RunReport`, its text rendering and the exit-code mapping (#73) | run results | summary text, exit code |
| `bs_database.parsers.models` | Discovery DTOs: index products, list entries, set pages, promo list (#69) | n/a | n/a |
| `bs_database.parsers.card_models`, `.errors` | Card page DTOs with `SCHEMA_VERSION`, and `ParseError` (`NoCardList` for a set page without cards) | n/a | n/a |
| `bs_database.parsers.batspi.index`, `.set_page`, `.promo_list`, `.numbers` | batspi.com discovery parsers and card-number parser (#69) | cached HTML | parsed records |
| `bs_database.parsers.batspi.card`, `.card_text`, `.card_sections` | Card page parser: identity and gameplay values (#70); effects, credits, flavour, printings and images (#71) | cached HTML, URL | `CardPage` |
| `bs_database.glossary` | Load and validate the glossary CSVs; exact `jp` lookup, legacy English family aliases (#92); used by `normalize` | `data/glossary/*.csv` | `Glossary` |
| `bs_database.normalize` | Package (`records`, `rules`, `pipeline`, #93): `normalize_page` (pure), `normalize_tree`, `translation` and `report` (#95); see [normalization.md](normalization.md) | `data/parsed`, `Glossary` | `data/normalized/<source>/<sha256>.json` |
| `bs_database.build` | Package (`reader`, `grouping`, `lookups`, `cards`, `effects`, `products`, `images`, `builder`, #120): `build_database`, `build_from_directories`; see [build.md](build.md) | `data/normalized`, `Glossary`, raw-HTML cache (hashes), `schema.sql` | the SQLite database |
| `bs_database.schema` | `load_schema_sql()`: the packaged `schema.sql` (ADR 0011) | n/a | DDL text |
| `tests/tools/db_counts.py` | Per-table row counts of a SQLite file as JSON | a `.db` file | JSON on stdout |
| `example_query.sql` | Sample SQL queries | n/a | n/a |
| `Notes.md` | Informal notes (card type list) | n/a | n/a |

The quirks of the removed scrapers are described in the [legacy mapping](../data-model/legacy-mapping.md).

## Known issues / tech debt

The legacy data model is described in [current-schema.md](../data-model/current-schema.md); its replacement is designed in the [target schema](../data-model/target-schema.md), with a per-column [legacy mapping](../data-model/legacy-mapping.md). Rows tagged E3 below link to the part of the target schema that addresses them; the implementation stays in the later epics.

Tags refer to the epic addressing each item: E2 restructure ([#7](https://github.com/AleFire99/BS_Database/issues/7)), E3 data model ([#8](https://github.com/AleFire99/BS_Database/issues/8)), E4 source analysis ([#9](https://github.com/AleFire99/BS_Database/issues/9)), E5 scraper rewrite ([#10](https://github.com/AleFire99/BS_Database/issues/10)), E6 normalization and translation ([#11](https://github.com/AleFire99/BS_Database/issues/11)), E7 DB build and validation ([#12](https://github.com/AleFire99/BS_Database/issues/12)), E8 images ([#13](https://github.com/AleFire99/BS_Database/issues/13)), E9 distribution ([#14](https://github.com/AleFire99/BS_Database/issues/14)).

| Issue | Evidence | Epic |
| --- | --- | --- |
| Resolved: hardcoded Windows paths | Paths now come from `BSDB_*` settings; CI fails on absolute user paths | E2 |
| Resolved: inconsistent paths and DB locations | Single `Settings` with paths derived from `data_dir` | E2 |
| Resolved: no package layout, import-time side effects | `src/bs_database` package with a `bsdb` entry point | E2 |
| Resolved: dead and broken code | Legacy scripts removed in #23 (tag `v0.1.0`) | E2 |
| Resolved: dependency list | Unused `selenium`, `webdriver-manager`, `libretranslatepy`, `lxml` dropped; used packages declared | E2 |
| Resolved: database committed to git | `battle_spirits.db` untracked and ignored in #23 (release artefact is E9) | E2, E9 |
| Resolved: no tests, CI or lint | pytest with goldens, ruff, mypy strict, CI and pre-commit | E2 |
| Resolved: legacy scrapers and fandom code | Removed in #66 (commit `f90747b` has them); fandom is dropped for v1 ([fandom.md](../sources/fandom.md)); the new ingestion modules (#67-#73), the parsers (#69-#71) and `bsdb scrape` are implemented | E5 |
| Machine translation of names and families | `GoogleTranslator` output is stored as canonical names; family names were patched with ad-hoc rules in the legacy `normalize` plus `family_mapping.txt` (removed in #93). Replaced by glossaries, the [normalize package](normalization.md) (#93) and a cached translator ([ADR 0008](../adr/0008-normalization-and-translation.md)): [#92](https://github.com/AleFire99/BS_Database/issues/92) to [#95](https://github.com/AleFire99/BS_Database/issues/95) | E6 |
| Translation failures stored as data | `translate()` returns `"Error: ..."` strings that would be persisted. Fixed by the translator and its error policy in [ADR 0008](../adr/0008-normalization-and-translation.md) ([#94](https://github.com/AleFire99/BS_Database/issues/94), [#95](https://github.com/AleFire99/BS_Database/issues/95)) | E6 |
| Resolved: colors derived from translated symbol | The legacy symbol-to-color map in `db.py` lacked `white`; multicolor strings (e.g. "Red purple green white yellow blue") match nothing. Designed in the target schema: `colors` with White and a `card_colors` junction filled from the Japanese colour segment ([target-schema](../data-model/target-schema.md#card_colors)); the colour mapping moves to glossaries in [#92](https://github.com/AleFire99/BS_Database/issues/92), the loader (#120) fills `card_colors` from the glossary code. | E3, E6, E7 |
| Resolved: no caching, retries or User-Agent | The legacy scrapers were removed in #66; the new client, cache, state and pipeline (#67, #68, #72, #73) provide them. Requirements are set in the [scraping policy](../sources/policy.md#5-requirements-for-the-scraper-rewrite-10) | E5 |
| Resolved: brittle HTML selectors | The legacy selectors went with the scrapers; the new parsers read named structure and raise `ParseError` on anything unknown instead of guessing (#69-#71) | E4, E5 |
| Resolved: card effects/text not loaded | The legacy `build` loaded only name, type, cost, symbol, family and core requirements. `bsdb build` (#120) loads effects, keywords, reductions, credits, flavour, printings and images ([build.md](build.md)); the data with no column yet is listed there (follow-up #130). | E3, E7 |
| Resolved: cards without a `<pre>` block | The parser raises `ParseError` instead of saving null fields | E5 |
| Resolved: loader not idempotent and slow | `bsdb build` writes a fresh file in one transaction with `executemany` (about 5 s for the full data) and replaces the output atomically | E7 |
| Validation of loaded data | Foreign keys and the foreign key check are in the build (#120); the quality rules and `--strict` are [#122](https://github.com/AleFire99/BS_Database/issues/122) | E7 |
| Images not versioned or described | Paths are stored as strings; default image set range (BS19-71) is hardcoded; `data/images` and `data/json` are not in the repository | E8 |
| No license or distribution story | No license file, no release artifacts | E9 |
