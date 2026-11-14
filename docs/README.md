# Documentation index

This folder documents the **current, legacy** state of BS_Database (a Battle Spirits card scraper and SQLite builder) and the decisions that shape its restructuring. It is the baseline for the roadmap epics listed in the [top-level README](../README.md).

## Contents

| Document | Description |
| --- | --- |
| [architecture/overview.md](architecture/overview.md) | Current pipeline, components, known issues and tech debt |
| [data-model/current-schema.md](data-model/current-schema.md) | Current SQLite schema, SQLAlchemy models, row counts, gaps |
| [domain/glossary.md](domain/glossary.md) | Battle Spirits domain glossary (EN/JP) |
| [adr/README.md](adr/README.md) | Architecture Decision Records index |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | How to contribute (workflow, commits, tooling) |
| [../CLAUDE.md](../CLAUDE.md) | Guidance for Claude Code in this repository |

## Docs conventions

- **Diagrams use mermaid**, always: `flowchart`, `sequenceDiagram`, `erDiagram`, `classDiagram`, `stateDiagram-v2`. No binary images for diagrams.
- **One ADR per decision**, stored in [adr/](adr/README.md) and based on [adr/0000-template.md](adr/0000-template.md). Superseded ADRs are kept and marked, never deleted.
- **Docs are updated in the same PR as the code** they describe.
- Relative links only, one H1 per file, fenced code blocks always carry a language.
