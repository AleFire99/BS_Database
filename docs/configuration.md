# Configuration

Settings are defined in `src/bs_database/settings.py` (`Settings`, built on pydantic-settings). Every variable uses the `BSDB_` prefix.

**Precedence:** environment variables > `.env` file (in the current working directory) > defaults.

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `BSDB_DATA_DIR` | `data` | Base directory for all data files |
| `BSDB_JSON_DIR` | `<data_dir>/json` | Scraped card JSON files |
| `BSDB_IMAGES_DIR` | `<data_dir>/images` | Downloaded card images |
| `BSDB_DB_PATH` | `<data_dir>/battle_spirits.db` | SQLite database output |
| `BSDB_FAMILY_MAPPING_PATH` | `<data_dir>/family_mapping.txt` | Family-name normalization map |
| `BSDB_EXTRACTED_URLS_PATH` | `<data_dir>/extracted_urls.txt` | Extracted card URLs |
| `BSDB_FANDOM_BASE_URL` | `https://battle-spirits.fandom.com` | Fandom wiki base URL |
| `BSDB_FANDOM_SET_URL` | `https://battle-spirits.fandom.com/wiki/` | Fandom set page URL prefix |
| `BSDB_BATSPI_URL` | `https://batspi.com/` | batspi.com base URL |
| `BSDB_REQUEST_DELAY` | `0.0` | Delay between HTTP requests, in seconds (must be >= 0) |
| `BSDB_LOG_LEVEL` | `INFO` | Root log level |

Paths derived from `data_dir` are only derived when not set explicitly.

## `.env` example

```dotenv
BSDB_DATA_DIR=/srv/bsdb
BSDB_REQUEST_DELAY=1.5
BSDB_LOG_LEVEL=DEBUG
```

`.env` is git-ignored.
