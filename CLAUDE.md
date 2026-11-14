# CLAUDE.md

Guidance for Claude Code in this repository.

## Workflow (mandatory)

This repo opts into the owner's global workflow (`.github/workflow.yml`), so **load the `wf-workflow` skill first** before planning, coding, committing or touching GitHub. In short:

- Work only from an issue.
- Stop at human gates 🛑 A–D.
- The chat is the Opus orchestrator and delegates to the `wf-*` haiku/sonnet subagents.
- Branches: `feature/<epic#>-…` and `task/<sub#>-…`. Never commit to `main` or `dev`.
- Use Conventional Commits with a `Refs #n` footer.
- Python is **uv only**.

Full human-readable version: [CONTRIBUTING.md](CONTRIBUTING.md). Board: GitHub Project #3 "BS Database".

## Project goal

A complete, normalized database of the **Japanese Battle Spirits** TCG (sets, cards, families, cores, effects, images), distributed as a versioned release artefact. The sister project [BSS_app](https://github.com/AleFire99/BSS_app) does the same for Battle Spirits Saga, with a SQLite schema, a Telegram bot and a mobile app, and is the reference for conventions.

Current state: a **legacy prototype** that is being restructured. See the roadmap epics #7–#14 and [docs/architecture/overview.md](docs/architecture/overview.md) for known issues.

## Commands

```bash
uv sync                                  # install env from uv.lock
uv run ruff check && uv run ruff format --check
uv run mypy
uv run pytest
uv run pre-commit run --all-files
.github/scripts/check-mermaid.sh         # render-check all mermaid blocks (needs Chrome)
```

## Layout (legacy, until E2 #7)

| Path | Role |
| --- | --- |
| `main.py` | Entry point; currently only loads card JSON into `battle_spirits.db` |
| `scripts/scraper/` | `json_set_scraper.py` (fandom set tables), `card_scraper.py` (batspi.com card pages + JP→EN machine translation), `image_scraper.py` |
| `scripts/extract_card_links.py`, `scripts/set_link_extractor.py` | batspi.com link discovery |
| `scripts/db/db_manager.py` | SQLAlchemy models and JSON → SQLite loader |
| `json_editor.py`, `data/family_mapping.txt` | Family-name normalization |
| `config/settings.py` | URLs and **hardcoded Windows paths** (to be replaced in E2) |
| `battle_spirits.db` | Legacy build output, still tracked (to be untracked in E2) |
| `docs/` | Architecture, data model (ER), domain glossary, ADRs |

The legacy paths are excluded from ruff and mypy until E2. Do not refactor legacy code outside an approved task.

## Data sources

- batspi.com (JP card pages: primary card data)
- battle-spirits.fandom.com (EN wiki: set lists and images)

Scrape politely: cache raw HTML and rate-limit requests. The policy is defined in E4 #9.

## Docs

Keep the [docs/](docs/README.md) index current. All diagrams are mermaid (erDiagram, classDiagram, sequenceDiagram, stateDiagram-v2, flowchart) and are validated in CI. Every decision gets an ADR in `docs/adr/` with `Status: Proposed`, and only the owner accepts it.
