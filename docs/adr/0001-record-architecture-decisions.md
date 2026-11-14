# 0001. Record architecture decisions

- Status: Accepted
- Date: 2026-11-14

## Context

The project is a legacy prototype being restructured across several epics. Decisions (storage engine, scraper design, translation strategy, distribution) will be made over time and need a durable, reviewable record so future contributors understand why things are the way they are.

## Decision drivers

- Decisions should be reviewable in pull requests.
- The record must live next to the code and be versioned with it.
- Low ceremony for a small project.

## Options considered

1. No formal record: zero cost, but rationale is lost.
2. Wiki or issues only: easy to write, but detached from the code history.
3. ADRs in `docs/adr/` using a lightweight MADR-style template: versioned with the code, reviewed in PRs.

## Decision

Use ADRs (option 3), one file per decision, numbered sequentially, based on [0000-template.md](0000-template.md) and indexed in [README.md](README.md).

## Consequences

- Each significant decision requires a short ADR in the same PR as the change.
- Superseded decisions stay in the repository with an updated status.
- The SQLite vs MongoDB choice will be recorded as a future ADR in E3.

## Links

- Issue: [#1](https://github.com/AleFire99/BS_Database/issues/1)
