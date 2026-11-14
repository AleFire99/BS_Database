# 0002. Storage technology: SQLite

- Status: Proposed
- Date: 2026-11-14

## Context

BS_Database builds a complete, normalized database of the Japanese Battle Spirits TCG and distributes it as a versioned release artefact ([#14](https://github.com/AleFire99/BS_Database/issues/14)). The prototype and the current `bs_database` package already write SQLite through SQLAlchemy, but that was never a recorded decision. The roadmap had left SQLite vs MongoDB open for E3 ([#8](https://github.com/AleFire99/BS_Database/issues/8)).

Facts that shape the choice:

- The data is strongly relational. Cards, printings, sets, colors, symbols, families, levels and effects are linked through many junctions, and lookup values are shared across thousands of rows (see [current-schema.md](../data-model/current-schema.md)).
- The volume is small: about 6.4k cards in the legacy build, growing incrementally with each new set.
- The sister project [BSS_app](https://github.com/AleFire99/BSS_app) uses a SQLite schema consumed by a Telegram bot and a mobile app.
- The database is built offline in batch by one process and read by many consumers.
- Effects will be stored text-first in v1 (Gate A decision on #8), so no schemaless document model is needed for effect structures.

## Decision drivers

- Referential integrity: foreign keys, unique and check constraints enforced by the engine.
- A single file with no server, so the database can be downloaded and opened anywhere.
- Parity with BSS_app, so the two projects share tooling and consumer patterns.
- Python tooling under uv: stdlib `sqlite3` and SQLAlchemy, with no extra service in CI.
- Ad-hoc SQL querying and full-text search over card names and effect text.
- Simple schema versioning inside the artefact.

## Options considered

1. **SQLite.** Relational with enforced foreign keys (`PRAGMA foreign_keys = ON`). One portable file, readable on desktop, server, Android and iOS. Full-text search through FTS5. Versioning through `PRAGMA user_version`. Same engine as BSS_app and the current package. Cons: one writer at a time (irrelevant for a batch build), and limited `ALTER TABLE` (mitigated by rebuilding the file for each release).
2. **MongoDB.** A flexible document model that would suit bespoke, nested effect structures. Cons: needs a server, so there is no single-file artefact. Relational lookups (colors, families, sets) end up denormalized and duplicated or emulated with `$lookup`. Integrity is only partly enforceable through schema validation. It diverges from BSS_app.
3. **DuckDB.** A single file with excellent analytics and Parquet export. Cons: built for OLAP rather than as an embedded app store, foreign-key enforcement is limited, mobile and bot support is weaker, and it diverges from BSS_app.
4. **PostgreSQL.** The strongest integrity and features. Cons: needs a server, and a dump is not a database people can open directly. Overkill for this data size. It could serve as a later mirror without becoming the primary store.

## Decision

Use **SQLite** (option 1) as the storage technology for the built database and the release artefact. It is the only option that combines enforced relational integrity with single-file, serverless distribution, and it matches BSS_app and the existing code.

## Consequences

- Every connection must enable `PRAGMA foreign_keys = ON`. The loader and any consumers must do this, because SQLite does not enforce foreign keys by default.
- Each release rebuilds the database from scratch from normalized sources instead of migrating it in place, which sidesteps SQLite's limited `ALTER TABLE`.
- The schema version is stored in the file. The mechanism is defined by the naming and versioning ADR ([#27](https://github.com/AleFire99/BS_Database/issues/27)) and implemented in DB build ([#12](https://github.com/AleFire99/BS_Database/issues/12)).
- Text search uses FTS5 virtual tables where needed (to be designed in #8 and #12).
- Releases ship the `.db` file and may add CSV or JSON exports for non-SQL consumers ([#14](https://github.com/AleFire99/BS_Database/issues/14)).
- If structured effects become necessary later, they are modelled relationally (as in BSS_app `Effects`/`EffectSteps`) or as JSON columns. They are not a reason to change engine.

## Links

- Issue: [#26](https://github.com/AleFire99/BS_Database/issues/26) (epic [#8](https://github.com/AleFire99/BS_Database/issues/8))
- Resolves the follow-up noted in [0001](0001-record-architecture-decisions.md) (the storage choice was to be recorded in E3).
