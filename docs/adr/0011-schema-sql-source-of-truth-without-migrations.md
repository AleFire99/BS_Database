# 0011. schema.sql as the source of truth, without migrations

- Status: Proposed
- Date: 2026-11-21

## Context

The released database is a SQLite file ([ADR 0002](0002-storage-technology.md)). Epic [#12](https://github.com/AleFire99/BS_Database/issues/12) builds it from the normalized data. Today `src/bs_database/db.py` defines SQLAlchemy models that `create_all` turns into the legacy schema. Those models share nothing with the 33-table target schema in [target-schema.md](../data-model/target-schema.md).

[ADR 0003](0003-naming-and-schema-versioning.md) fixed the naming and versioning rules. It planned the constraint names as a SQLAlchemy `naming_convention`.

Every build starts from an empty file. No one edits the database by hand, and it holds no user data.

## Decision drivers

- One readable definition of the schema, so consumers do not have to install the generator to read it.
- A full rebuild from versioned source data at every release.
- No duplicated schema: a model file and a DDL file would drift apart.
- Build speed on about 15k cards and 24k printings.
- A cheap compatibility check for consumers.

## Options considered

1. **SQLAlchemy ORM models and `create_all`, with Alembic migrations.** The models stay the source.
   - Pros: typed models; migrations give in-place upgrades.
   - Cons: a second copy of the schema next to the documented DDL; slow ORM inserts; migrations serve no purpose for a file rebuilt from scratch.
2. **`schema.sql` and a plain-SQL loader on stdlib `sqlite3`, with no migrations.** The DDL is the source.
   - Pros: consumers read it directly; fast `executemany` inserts; one source.
   - Cons: no ORM convenience in the loader; schema changes are reviewed as SQL.
3. **SQLAlchemy Core with tables generated from the DDL.**
   - Pros and cons: half-way between 1 and 2; it keeps the dependency for little gain.

## Decision

Option 2.

- **`src/bs_database/schema.sql` is the single source of truth.** It is packaged with the code, and the loader (`bsdb build`, [#120](https://github.com/AleFire99/BS_Database/issues/120)) runs it on an empty file through stdlib `sqlite3`.
  - The SQLAlchemy models and the `sqlalchemy` dependency are removed when the legacy loader is replaced in #120.
  - [target-schema.md](../data-model/target-schema.md) documents the schema and points to `schema.sql` as the source.
- **No Alembic and no migrations.** Every release rebuilds the database from scratch.
  - Revisit when the database becomes long-lived or mutable: hand edits, user data, incremental updates, or a consumer that needs an in-place upgrade.
  - User data belongs in a separate, app-side database.
- **Constraint and index names are written in the DDL itself**, following the ADR 0003 pattern (`pk_`, `fk_`, `uq_`, `ck_`, `ix_` followed by `<table>_<cols>`). This replaces the SQLAlchemy `naming_convention` that ADR 0003 planned.
- **Versioning**, restating ADR 0003:
  - `PRAGMA user_version` is `major * 10000 + minor * 100 + patch`.
  - The single-row `schema_meta` holds `schema_version`, `data_version`, `built_at`, `source_snapshot` and `generator`.
  - The schema version follows SemVer: a breaking table or column change bumps major, an additive change bumps minor, a fix bumps patch.
- **Builds are content-deterministic.** Rows are inserted in a sorted order, so two builds from the same input differ only in `schema_meta.built_at`. A `--built-at` option fixes that value for byte-identical builds.
- **Foreign keys are enforced:** `PRAGMA foreign_keys=ON`, and the build checks `PRAGMA foreign_key_check` ([ADR 0002](0002-storage-technology.md)).

## Consequences

- Positive:
  - One schema file that consumers can read.
  - Fast builds, and one dependency fewer.
  - The ER doc and the DDL can be checked against each other in CI ([#119](https://github.com/AleFire99/BS_Database/issues/119)).
- Negative and follow-up work:
  - Consumers pin a schema version, because there is no in-place upgrade. Release notes ([#14](https://github.com/AleFire99/BS_Database/issues/14)) must state breaking changes.
  - The loader maps the normalized documents to tables by hand. The quality checks ([#122](https://github.com/AleFire99/BS_Database/issues/122)) catch mapping errors.

## Links

- Issue: [#118](https://github.com/AleFire99/BS_Database/issues/118); epic [#12](https://github.com/AleFire99/BS_Database/issues/12)
- Builds on [0002](0002-storage-technology.md), [0003](0003-naming-and-schema-versioning.md) and [0004](0004-card-printing-identity.md).
