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
| `BSDB_CACHE_DIR` | `<data_dir>/cache/html` | Raw HTML cache (`<source>/<sha256(url)>.html` plus `.json` sidecar) |
| `BSDB_BATSPI_URL` | `https://batspi.com/` | batspi.com base URL |
| `BSDB_USER_AGENT` | `bs-database/<version> (+https://github.com/AleFire99/BS_Database)` | `User-Agent` sent on every request |
| `BSDB_REQUEST_DELAY` | `3.0` | Minimum delay between HTTP requests, in seconds (must be >= 1.0, policy floor) |
| `BSDB_MAX_REQUESTS` | `1000` | Request budget per run, retries and robots.txt included (must be >= 1) |
| `BSDB_CONNECT_TIMEOUT` | `10.0` | HTTP connect timeout, in seconds (must be > 0) |
| `BSDB_READ_TIMEOUT` | `30.0` | HTTP read timeout, in seconds (must be > 0) |
| `BSDB_LOG_LEVEL` | `INFO` | Root log level |

`bsdb --log-level LEVEL` overrides `BSDB_LOG_LEVEL` for a single run.

Paths derived from `data_dir` are only derived when not set explicitly.

## `.env` example

```dotenv
BSDB_DATA_DIR=/srv/bsdb
BSDB_REQUEST_DELAY=1.5
BSDB_LOG_LEVEL=DEBUG
```

`.env` is git-ignored.
