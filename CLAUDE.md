# CLAUDE.md

Guidance for Claude Code in this repository.

## Workflow (mandatory)

This repo opts into the owner's global workflow (`.github/workflow.yml`), so **load the `wf-workflow` skill first** before planning, coding, committing or touching GitHub. In short:

- Work only from an issue.
- Stop at human gates 🛑 A–D.
- The chat is the Opus orchestrator and delegates to the `wf-*` haiku/sonnet subagents.
- Branches: `feature/<epic#>-…` and `task/<sub#>-…`. Never commit to `main` or `dev`.
- Milestones are release targets (`vX.Y.Z`); an epic and its sub-issues share one.
- Use Conventional Commits with a `Refs #n` footer.
- Python is **uv only**.

Full human-readable version: [CONTRIBUTING.md](CONTRIBUTING.md). Board: GitHub Project #3 "BS Database".

## Project goal

A complete, normalized database of the **Japanese Battle Spirits** TCG (sets, cards, families, cores, effects, images), distributed as a versioned release artefact. The sister project [BSS_app](https://github.com/AleFire99/BSS_app) does the same for Battle Spirits Saga, with a SQLite schema, a Telegram bot and a mobile app, and is the reference for conventions.

Current state: the legacy scripts were restructured into the `bs_database` package with the `bsdb` CLI (epic #7), behaviour-preserving. Next: data model (#8), sources (#9), scraper rewrite (#10) and the rest of the roadmap #11–#14; see [docs/architecture/overview.md](docs/architecture/overview.md) for known issues.

## Commands

```bash
uv sync                                  # install env from uv.lock
uv run ruff check && uv run ruff format --check
uv run mypy
uv run pytest
uv run pre-commit run --all-files
.github/scripts/check-mermaid.sh         # render-check all mermaid blocks (needs Chrome)
```

## Layout

| Path | Role |
| --- | --- |
| `src/bs_database/cli.py` | Typer app, entry point `bsdb` (`scrape`, `normalize`, `build`, `images`) |
| `src/bs_database/settings.py`, `log.py` | `BSDB_*` settings and logging setup |
| `src/bs_database/scrapers/` | `batspi_sets`, `batspi_links`, `batspi_card` (batspi.com + JP→EN machine translation), `fandom_sets`, `fandom_images` |
| `src/bs_database/normalize.py` | Family-name and type normalization (uses `data/family_mapping.txt`) |
| `src/bs_database/db.py` | SQLAlchemy models and JSON → SQLite loader (`build_db`) |
| `tests/` | pytest suite; `tests/goldens/` and `tests/fixtures/` come from the legacy code (tag `v0.1.0`); `tests/tools/db_counts.py` prints per-table row counts |
| `battle_spirits.db` | Build output, untracked and git-ignored |
| `docs/` | Architecture, data model (ER), domain glossary, ADRs |

## Data sources

- batspi.com (JP card pages: primary card data)
- battle-spirits.fandom.com (EN wiki: set lists and images)

Scrape politely: cache raw HTML and rate-limit requests. The policy is defined in E4 #9.

## Docs

Keep the [docs/](docs/README.md) index current. All diagrams are mermaid (erDiagram, classDiagram, sequenceDiagram, stateDiagram-v2, flowchart) and are validated in CI. Every decision gets an ADR in `docs/adr/` with `Status: Proposed`, and only the owner accepts it.
