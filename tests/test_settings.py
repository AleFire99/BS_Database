from pathlib import Path

import pytest
from pydantic import ValidationError

from bs_database.settings import Settings


@pytest.fixture(autouse=True)
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for key in list(os.environ):
        if key.startswith("BSDB_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)


def test_defaults() -> None:
    s = Settings()
    assert s.batspi_url == "https://batspi.com/"
    assert s.fandom_base_url == "https://battle-spirits.fandom.com"
    assert s.fandom_set_url == "https://battle-spirits.fandom.com/wiki/"
    assert s.data_dir == Path("data")
    assert s.db_path == Path("data/battle_spirits.db")
    assert s.json_dir == Path("data/json")
    for p in (s.json_dir, s.images_dir, s.db_path, s.family_mapping_path, s.extracted_urls_path):
        assert not p.is_absolute()
    assert s.request_delay == 0.0
    assert s.log_level == "INFO"


def test_data_dir_derives_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSDB_DATA_DIR", "/x")
    s = Settings()
    for p in (s.json_dir, s.images_dir, s.db_path, s.family_mapping_path, s.extracted_urls_path):
        assert p.is_relative_to("/x")


def test_explicit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSDB_DATA_DIR", "/x")
    monkeypatch.setenv("BSDB_JSON_DIR", "/elsewhere")
    s = Settings()
    assert s.json_dir == Path("/elsewhere")
    assert s.images_dir == Path("/x/images")


def test_dotenv_and_env_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("BSDB_LOG_LEVEL=DEBUG\nBSDB_REQUEST_DELAY=1.5\n")
    s = Settings()
    assert s.log_level == "DEBUG"
    assert s.request_delay == 1.5
    monkeypatch.setenv("BSDB_LOG_LEVEL", "WARNING")
    assert Settings().log_level == "WARNING"


def test_invalid_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSDB_REQUEST_DELAY", "abc")
    with pytest.raises(ValidationError):
        Settings()
