"""Runtime settings, read from ``BSDB_*`` environment variables and an optional ``.env`` file."""

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bs_database import __version__

_DEFAULT_DATA_DIR = Path("data")

# field name -> path relative to data_dir, used when the field is not set explicitly
_DERIVED_PATHS = {
    "json_dir": "json",
    "images_dir": "images",
    "db_path": "battle_spirits.db",
    "family_mapping_path": "family_mapping.txt",
    "cache_dir": "cache/html",
}


class Settings(BaseSettings):
    """Project settings. Precedence: environment variables > ``.env`` > defaults."""

    model_config = SettingsConfigDict(
        env_prefix="BSDB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = _DEFAULT_DATA_DIR
    # The paths below default to locations under ``data_dir`` (see ``_derive_paths``).
    json_dir: Path = Path()
    images_dir: Path = Path()
    db_path: Path = Path()
    family_mapping_path: Path = Path()
    cache_dir: Path = Path()
    batspi_url: str = "https://batspi.com/"
    user_agent: str = f"bs-database/{__version__} (+https://github.com/AleFire99/BS_Database)"
    request_delay: float = Field(default=3.0, ge=1.0)
    max_requests: int = Field(default=1000, ge=1)
    connect_timeout: float = Field(default=10.0, gt=0)
    read_timeout: float = Field(default=30.0, gt=0)
    log_level: str = "INFO"

    @model_validator(mode="before")
    @classmethod
    def _derive_paths(cls, data: Any) -> Any:
        """Fill unset path fields relative to ``data_dir``."""
        if not isinstance(data, dict):
            return data
        data_dir = Path(data.get("data_dir") or _DEFAULT_DATA_DIR)
        for name, rel in _DERIVED_PATHS.items():
            if data.get(name) in (None, ""):
                data[name] = data_dir / rel
        return data
