# Documentation index

This folder documents the current state of BS_Database (the `bs_database` package: Battle Spirits card scrapers, normalizer and SQLite builder) and the decisions that shape it. It is the baseline for the roadmap epics listed in the [top-level README](../README.md).

## Contents

| Document | Description |
| --- | --- |
| [architecture/overview.md](architecture/overview.md) | Package layout, CLI flow, components, known issues and tech debt |
| [data-model/current-schema.md](data-model/current-schema.md) | **Legacy** SQLite schema, SQLAlchemy models, row counts, gaps (superseded by the target schema, kept for the #12 migration) |
| [data-model/field-inventory.md](data-model/field-inventory.md) | Card fields per type and source: what exists, what is parsed, what is stored |
| [data-model/target-schema.md](data-model/target-schema.md) | Target schema design: identity, gameplay, effects, text, provenance, images, complete ER and DDL draft |
| [data-model/legacy-mapping.md](data-model/legacy-mapping.md) | Every legacy table, column, JSON key and artefact mapped to the target schema or dropped, plus the gap list |
| [data-model/samples.md](data-model/samples.md) | Hand-modelled sample cards as SQL inserts against the DDL draft |
| [sources/batspi.md](sources/batspi.md) | batspi.com source catalogue: robots rules, URL patterns, categories, card number schemes, `<pre>` format per card type, image URLs, candidate fixtures |
| [sources/fandom.md](sources/fandom.md) | Fandom wiki dossier: Cloudflare access evidence, CC-BY-SA licence, verdict dropped for v1 |
| [sources/official.md](sources/official.md) | Official Bandai site survey: URLs, reuse note, card markup, fields mapped to the inventory |
| [sources/policy.md](sources/policy.md) | Scraping and redistribution policy: robots, rate, User-Agent, cache, errors, attribution, requirements for #10 |
| [domain/glossary.md](domain/glossary.md) | Battle Spirits domain glossary (EN/JP) |
| [configuration.md](configuration.md) | Settings and `BSDB_*` environment variables |
| [adr/README.md](adr/README.md) | Architecture Decision Records index |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | How to contribute (workflow, commits, tooling) |
| [../CLAUDE.md](../CLAUDE.md) | Guidance for Claude Code in this repository |

## Docs conventions

- **Diagrams use mermaid**, always: `flowchart`, `sequenceDiagram`, `erDiagram`, `classDiagram`, `stateDiagram-v2`. No binary images for diagrams.
- **One ADR per decision**, stored in [adr/](adr/README.md) and based on [adr/0000-template.md](adr/0000-template.md). Superseded ADRs are kept and marked, never deleted.
- **Docs are updated in the same PR as the code** they describe.
- Relative links only, one H1 per file, fenced code blocks always carry a language.
