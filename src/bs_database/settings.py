"""Runtime settings, read from ``BSDB_*`` environment variables and an optional ``.env`` file."""

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_DATA_DIR = Path("data")

# field name -> path relative to data_dir, used when the field is not set explicitly
_DERIVED_PATHS = {
    "json_dir": "json",
    "images_dir": "images",
    "db_path": "battle_spirits.db",
    "family_mapping_path": "family_mapping.txt",
    "extracted_urls_path": "extracted_urls.txt",
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
    extracted_urls_path: Path = Path()
    fandom_base_url: str = "https://battle-spirits.fandom.com"
    fandom_set_url: str = "https://battle-spirits.fandom.com/wiki/"
    batspi_url: str = "https://batspi.com/"
    request_delay: float = Field(default=0.0, ge=0)
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
