# BS_Database

A Battle Spirits (JP) card database builder: scrape card data and images from public sources, normalize and translate it, and load it into a SQLite database.

## Status

Legacy prototype being restructured; see the roadmap below. The current state is documented in [docs/](docs/README.md), starting with the [architecture overview](docs/architecture/overview.md).

## Roadmap

| Epic | Theme | Issue |
| --- | --- | --- |
| E1 | Governance bootstrap | [#1](https://github.com/AleFire99/BS_Database/issues/1) |
| E2 | Restructure | [#7](https://github.com/AleFire99/BS_Database/issues/7) |
| E3 | Data model | [#8](https://github.com/AleFire99/BS_Database/issues/8) |
| E4 | Source analysis | [#9](https://github.com/AleFire99/BS_Database/issues/9) |
| E5 | Scraper rewrite | [#10](https://github.com/AleFire99/BS_Database/issues/10) |
| E6 | Normalization and translation | [#11](https://github.com/AleFire99/BS_Database/issues/11) |
| E7 | DB build and validation | [#12](https://github.com/AleFire99/BS_Database/issues/12) |
| E8 | Images | [#13](https://github.com/AleFire99/BS_Database/issues/13) |
| E9 | Distribution | [#14](https://github.com/AleFire99/BS_Database/issues/14) |

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
| `bsdb scrape [--refresh-urls] [--set BSxx ...]` | Scrape batspi.com card pages into card JSON (and image paths) |
| `bsdb normalize` | Normalize family names and types in the card JSON, in place |
| `bsdb build [--db PATH]` | Build the SQLite database from the card JSON (appends to an existing DB, skipping duplicates) |
| `bsdb images [--sets 19-71]` | Download card images from the fandom wiki (inclusive set range) |

A typical run is `scrape`, `normalize`, `build`, with `images` independent of the others.

## Documentation

- [Contributing](CONTRIBUTING.md)
- [Docs index](docs/README.md)
- [Configuration](docs/configuration.md)

## Related projects

- [BSS_app](https://github.com/AleFire99/BSS_app): Battle Spirits Saga companion app.

## License

TBD
