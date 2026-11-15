# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.4.0] - 2026-11-15

### Added

- **http:** Policy-compliant HTTP client with retries, robots.txt gate and request budget (#80)
- **parse:** Batspi discovery parsers for the index, set pages and promo list (#81)
- **parse:** Batspi card parser for identity and gameplay values (#82)
- **state:** SQLite ingestion state store and per-page state machine (#83)
- **cache:** Raw HTML cache with sidecar metadata and hybrid policy-gated lookup (#84)
- **parse:** Batspi card parser for effects, keywords, printings, credits and images (#85)
- **cli:** Bsdb scrape pipeline with cache, state tracking, resume and run report (#86)
- **scraper:** Polite, resumable, tested batspi ingestion pipeline (epic #10) (#87)

### Changed

- **ingest:** Target ingestion layout, move policy helpers, remove legacy scrapers (#75)

### Internal

- **commitlint:** Ignore the one legacy #83 subject that starts with an acronym
- **commitlint:** Allow subjects that start with an acronym

## [0.3.0] - 2026-11-15

### Documentation

- **adr:** Add ADR 0002 storage technology (SQLite) (#43)
- **adr:** Add ADR 0003 naming conventions and schema versioning (#44)
- **data-model:** Add card field inventory per type and source (#45)
- **adr:** Add ADR 0004 card vs printing identity (#46)
- **data-model:** Add gameplay attributes to target schema (#47)
- **data-model:** Add effects, text, provenance and image model (#48)
- **data-model:** Consolidate target model, DDL draft, mapping and samples (#49)
- Domain and data-model design (epic #8) (#50)
- **sources:** Catalogue batspi.com URLs, products, eras and card text layout (#57)
- **sources:** Catalogue fandom wiki and official Bandai site with v1 verdicts (#58)
- **sources:** Add scraping and redistribution policy with ADR 0006 (#60)
- **sources:** Add field coverage matrix, gap list and resolve pending #9 rows (#62)
- **adr:** Add ADR 0007 source of truth per field and target data flow (#64)
- **adr:** Accept ADR 0006 and ADR 0007
- **sources:** Reflect accepted ADR 0006 in the policy
- Data source analysis (epic #9) (#65)
- Adopt milestones as release targets (#76)

### Internal

- **fixtures:** Add real batspi fixtures for all card types with manifest and budget (#61)
- Update uv-build requirement from <0.13,>=0.12.0 to >=0.12.0,<0.14 (#59)

## [0.2.0] - 2026-11-14

### Added

- **packaging:** Add src/bs_database package and bsdb entry point (#25)
- **config:** Add BSDB_ settings and logging setup (#33)
- **db:** Port normalization and DB loader into the package with golden tests (#34)
- **scraper:** Port scrapers into the package with offline HTML tests (#35)
- **cli:** Add bsdb scrape, normalize, build and images commands (#36)

### Changed

- Remove legacy code, untrack the DB and document the package layout (#37)

## [0.1.0] - 2026-11-14

### Documentation

- Document squash vs merge commit into dev and manual issue closing

### Internal

- Bootstrap governance, workflow and tooling (#15)
