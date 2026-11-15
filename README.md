# BS_Database

A Battle Spirits (JP) card database builder: scrape card data and images from public sources, normalize and translate it, and load it into a SQLite database.

## Status

The `bs_database` package and `bsdb` CLI replace the legacy scripts (E2 restructure; legacy code is at tag `v0.1.0`). See the roadmap below. The current state is documented in [docs/](docs/README.md), starting with the [architecture overview](docs/architecture/overview.md).

## Roadmap

| Epic | Theme | Issue | Milestone |
| --- | --- | --- | --- |
| E1 | Governance bootstrap | [#1](https://github.com/AleFire99/BS_Database/issues/1) | [v0.1.0](https://github.com/AleFire99/BS_Database/milestone/1) |
| E2 | Restructure | [#7](https://github.com/AleFire99/BS_Database/issues/7) | [v0.2.0](https://github.com/AleFire99/BS_Database/milestone/2) |
| E3 | Data model | [#8](https://github.com/AleFire99/BS_Database/issues/8) | [v0.3.0](https://github.com/AleFire99/BS_Database/milestone/3) |
| E4 | Source analysis | [#9](https://github.com/AleFire99/BS_Database/issues/9) | [v0.3.0](https://github.com/AleFire99/BS_Database/milestone/3) |
| E5 | Scraper rewrite | [#10](https://github.com/AleFire99/BS_Database/issues/10) | [v0.4.0](https://github.com/AleFire99/BS_Database/milestone/4) |
| E6 | Normalization and translation | [#11](https://github.com/AleFire99/BS_Database/issues/11) | [v0.5.0](https://github.com/AleFire99/BS_Database/milestone/5) |
| E7 | DB build and validation | [#12](https://github.com/AleFire99/BS_Database/issues/12) | [v0.5.0](https://github.com/AleFire99/BS_Database/milestone/5) |
| E8 | Images | [#13](https://github.com/AleFire99/BS_Database/issues/13) | [v1.0.0](https://github.com/AleFire99/BS_Database/milestone/6) |
| E9 | Distribution | [#14](https://github.com/AleFire99/BS_Database/issues/14) | [v1.0.0](https://github.com/AleFire99/BS_Database/milestone/6) |

## Quickstart

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Run the CLI:

```bash
uv run bsdb --help
```

## Usage

Paths and URLs come from `BSDB_*` settings (see [Configuration](docs/configuration.md)).

| Command | Description |
| --- | --- |
| `bsdb [--log-level L] [--version]` | Global options; `--log-level` overrides `BSDB_LOG_LEVEL` |
| `bsdb scrape [--set TEXT]... [--refresh] [--max-age 30d] [--limit N]` | Crawl batspi.com politely (cached, rate-limited, resumable) into `data/parsed/batspi/`; prints a run report. See [scraper](docs/architecture/scraper.md) |
| `bsdb normalize` | Normalize family names and types in the card JSON, in place |
| `bsdb build [--db PATH]` | Build the SQLite database from the card JSON (appends to an existing DB, skipping duplicates) |

The target run is `scrape`, `normalize`, `build`. `scrape` writes parsed JSON per card page; until the loader reads it (#12), `normalize` and `build` still work on the existing card JSON. A crawl takes several runs (request budget per run): run `bsdb scrape` again to continue.

## Documentation

- [Contributing](CONTRIBUTING.md)
- [Docs index](docs/README.md)
- [Configuration](docs/configuration.md)

## Related projects

- [BSS_app](https://github.com/AleFire99/BSS_app): Battle Spirits Saga companion app.

## License

TBD
