# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-11-14

### Added

- **packaging:** Add src/bs_database package and bsdb entry point (#25)
- **config:** Add BSDB_ settings and logging setup (#33)
- **db:** Port normalization and DB loader into the package with golden tests (#34)
- **scraper:** Port scrapers into the package with offline HTML tests (#35)
- **cli:** Add bsdb scrape, normalize, build and images commands (#36)

### Changed

- Remove legacy code, untrack the DB and document the package layout (#37)

### Removed

- Legacy entry points `main.py`, `json_editor.py`, `scripts/`, `config/`: use `bsdb scrape | normalize | build | images`.
- `battle_spirits.db` from the tree: the snapshot is attached to the [v0.1.0 release](https://github.com/AleFire99/BS_Database/releases/tag/v0.1.0); the default build path is now `data/battle_spirits.db`.
- Unused dependencies `selenium`, `webdriver-manager`, `libretranslatepy`, `lxml`.

## [0.1.0] - 2026-11-14

### Documentation

- Document squash vs merge commit into dev and manual issue closing

### Internal

- Bootstrap governance, workflow and tooling (#15)
