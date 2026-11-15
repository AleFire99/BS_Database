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
        DBM["db<br/>(models, build_db)"]
    end

    CJ[("data/json/card_json/BSxx/*.json")]
    FM[("data/family_mapping.txt")]
    DB[("battle_spirits.db<br/>(untracked build output)")]

    CLI --> SET
    CLI --> LOG
    CLI --> NORM
    CLI --> DBM
    CLI --> PIPE
    PIPE --> HTTP
    PIPE --> CACHE
    PIPE --> STATE
    PIPE --> PSTORE
    PIPE --> REPORT
    PIPE --> BPARSE
    HTTP --> POL

    CJ --> NORM
    FM --> NORM
    NORM --> CJ
    CJ --> DBM --> DB
```

The `ingest` and `parsers` packages hold the target layout of the scraper rewrite ([#10](https://github.com/AleFire99/BS_Database/issues/10)). They are complete: `bsdb scrape` runs the whole pipeline (HTTP client, cache, parsers, state store, parsed JSON, run report), documented in [scraper.md](scraper.md). The parsed JSON is not loaded into the database yet; the loader is [#12](https://github.com/AleFire99/BS_Database/issues/12). The legacy scrapers and `bsdb images` were removed in [#66](https://github.com/AleFire99/BS_Database/issues/66); they are at tag `v0.1.0` or commit `f90747b`.

### Card page parser

`bs_database.parsers.batspi.card.parse_card_page(html, url)` ([#70](https://github.com/AleFire99/BS_Database/issues/70), [#71](https://github.com/AleFire99/BS_Database/issues/71)) is a pure function: cached HTML in, a `CardPage` out, with no network, translation or file I/O. It reads identity (card numbers, `name_ja`, `name_en`) and gameplay values (type, cost, reduction, colours, families, levels, symbols, plus `fusion_bp_bonus` for Brave and `overclock` for Ultimate) of every card block in the card region of the page. Erratum and trial-spec blocks, Q&A and the related listing are skipped. The DTOs are frozen slotted dataclasses in `bs_database.parsers.card_models`, JSON-ready through `dataclasses.asdict`, and carry `SCHEMA_VERSION` (`1.1.0`). #71 added, per card number, the effect blocks, side conditions, credits and flavour text (`CardEntry.text`), and, per page, the printings and gallery images (`CardPage.printings`, `CardPage.images`). Unknown cost, level, symbol or header syntax raises `ParseError` instead of being guessed.

- **Number source.** The number in the print heading comes first, because it is the only per-block source (the `span.cardno` order differs on promo pages and the spans lack the `(A)`/`(B)` face on flip pages). The page's own `span.cardno` values are a set cross-check, and a mismatch is logged as a warning. Pages without a heading number take the span at the same position. This clarifies the "cardno span is authoritative" rule of [ADR 0007](../adr/0007-source-of-truth.md) for #12; the ADR itself is unchanged.
- **Literal values.** Colours, symbols, types and families keep the Japanese glyphs of the source; mapping to codes is the loader's job (#12).
- **Per-number differences (#63).** Gameplay fields that differ between numbers with the same name are logged at INFO and listed in `CardPage.differences`, so #12 can decide the card-versus-number grouping.
- **Effects (`card_text`).** The text after the level line is split into `Effect` blocks in printed order. `form` is `header` (a `Lv…`, `メイン`/`フラッシュ`, `【…】`/`《…》` or `『…』` header line plus its body), `keyword_line` (a one-line `【…】` block such as `【ミラージュ：…】` or `《神託》〔…〕`, where `header` equals `text`) or `plain` (text before the first header). Level scope, label, keywords and timing are raw facts; `effect_kind` is derived by the loader (#12). Keywords come from the header only, split at the first `：`, and the parameter is kept as printed (including a trailing reminder in parentheses). Fusion (`合体条件`), summon (`【召喚条件：…】`) and overclock (`OC条件`) lines are exposed as side conditions and are not effects. A line that starts like a level header but does not match the header grammar raises `ParseError`.
- **Credits and flavour.** `イラスト：` and `コンセプト：` lines become `Credit(name, note)`, where `note` is a trailing parenthesised group (the product in which that credit applies). Matching credits to printings is left to the loader. The flavour text keeps its source line breaks; `flavor_note` is the text after the `フレーバーテキスト：` label. An unknown trailer line raises `ParseError`.
- **Printings (`card_sections`).** Rows of the `収録` section (one-number paragraph, per-number list, or the nested promo list) become `Printing` rows with the product link (made absolute with `urljoin`), `detail_ja`, raw `rarity` and `note_ja`. A face-less label (`BS52-TX01`) gives one row per face. The block-icon section is joined by product name and number for `product_code`, `block_icon` and `release_date` (each block row is consumed once per number); block-icon rows with no `収録` row become printings with `rarity=None` and `section="ブロックアイコン"`. Rarity, product and variant mapping is the loader's job.
- **Images.** Each `ul.ppy-imglist` item becomes a `CardImage` with the large and small URLs read from the page (never built from a name) and the caption lines; the first caption line is the card number. Assigning images to printings is left to #12/#13.
- **#63 text differences.** `CardPage.differences` also compares `effects`, the side conditions and `flavor`. Credits and `flavor_note` are printing-level and excluded.
- **Fields without a schema column.** `deck_limit` (`制限カード<N>`), `overclock`, `OC条件`, `コンセプト`, `Printing.detail_ja` and `note_ja`, `flavor_note` and the effect `form`/`label` structure are parsed but have no column in the [target schema](../data-model/target-schema.md); #12 decides where they go.
- **Coverage gate.** `pyproject.toml` runs coverage with branches and fails below 97% over `ingest/` and `parsers/` only; the legacy modules (`db.py`, `cli.py`, `normalize.py`) are not gated. CI already runs `uv run pytest --cov`.

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
    participant J as card JSON files
    participant I as ingest.pipeline
    participant P as data/parsed
    participant N as normalize
    participant D as db.build_db
    participant DB as SQLite

    Dev->>C: bsdb scrape
    C->>I: run_pipeline (index, sets, cards)
    I->>P: parsed JSON per card page, state in ingest.db
    C-->>Dev: run report, exit code 0, 1 or 3
    Dev->>C: bsdb normalize
    C->>N: normalize_tree(json_dir, family mapping)
    N->>J: rewrite JSON in place
    Dev->>C: bsdb build [--db PATH]
    C->>D: build_db(json_dir, db_path)
    D->>J: read each JSON
    D->>DB: insert card, type, colors, families, core requirements
```

## Components

| Module | Responsibility | Inputs | Outputs |
| --- | --- | --- | --- |
| `bs_database.cli` | Typer app (`bsdb`): `scrape` (pipeline, [scraper.md](scraper.md)), `normalize`, `build`, global `--log-level` and `--version` | `Settings`, command options | calls the modules below |
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
| `bs_database.normalize` | Normalize family names, type, image path in place | card JSON tree, `data/family_mapping.txt` | rewritten JSON files |
| `bs_database.db` | SQLAlchemy models, JSON loader, color derivation, `build_db` | card JSON tree | SQLite rows |
| `data/family_mapping.txt` | Manual `machine translation = canonical name` overrides | n/a | used by `normalize` |
| `tests/tools/db_counts.py` | Per-table row counts of a SQLite file as JSON | a `.db` file | JSON on stdout |
| `example_query.sql` | Sample SQL queries | n/a | n/a |
| `Notes.md` | Informal notes (card type list) | n/a | n/a |

Kept quirks (covered by golden tests): the family order from the legacy normalizer was a set, so goldens are sorted. The quirks of the removed scrapers are described in the [legacy mapping](../data-model/legacy-mapping.md).

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
| Machine translation of names and families | `GoogleTranslator` output is stored as canonical names; family names are patched with ad-hoc rules in `normalize` plus `family_mapping.txt` (e.g. "Snake" forced to "Dark Snake", naive plural stripping) | E6 |
| Translation failures stored as data | `translate()` returns `"Error: ..."` strings that would be persisted | E6 |
| Colors derived from translated symbol | Symbol-to-color map in `db.py` lacks `white`; multicolor strings (e.g. "Red purple green white yellow blue") match nothing. Designed in the target schema: `colors` with White and a `card_colors` junction filled from the Japanese colour segment ([target-schema](../data-model/target-schema.md#card_colors)); the fix is in E6/E7. | E3, E6 |
| Resolved: no caching, retries or User-Agent | The legacy scrapers were removed in #66; the new client, cache, state and pipeline (#67, #68, #72, #73) provide them. Requirements are set in the [scraping policy](../sources/policy.md#5-requirements-for-the-scraper-rewrite-10) | E5 |
| Resolved: brittle HTML selectors | The legacy selectors went with the scrapers; the new parsers read named structure and raise `ParseError` on anything unknown instead of guessing (#69-#71) | E4, E5 |
| Card effects/text not loaded | Effects, keywords, credits, flavour, printings and images are parsed into `data/parsed` since #71 and #73. The legacy `build` still loads only name, type, cost, symbol, family and core requirements, and `reduction` never reaches the DB. Designed in the target schema: `card_effects`, `card_reductions` and flavor text ([effects](../data-model/target-schema.md#effects-and-keywords), [reductions](../data-model/target-schema.md#card_reductions)); the loader is E7 (#12). | E3, E7 |
| Cards without a `<pre>` block are saved with null fields | `batspi_card` falls back to all-`None`, then `insert_card` fails on missing `type` | E5, E7 |
| Loader is not idempotent for requirements and is slow | Per-card commits and per-row `get_or_create` queries; existing cards are skipped, so changes are never updated | E7 |
| No validation of loaded data | No constraints, no checks on set coverage or duplicates | E7 |
| Images not versioned or described | Paths are stored as strings; default image set range (BS19-71) is hardcoded; `data/images` and `data/json` are not in the repository | E8 |
| No license or distribution story | No license file, no release artifacts | E9 |
