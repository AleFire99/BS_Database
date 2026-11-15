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
    assert s.data_dir == Path("data")
    assert s.db_path == Path("data/battle_spirits.db")
    assert s.cache_dir == Path("data/cache/html")
    assert s.state_db_path == Path("data/state/ingest.db")
    assert s.parsed_dir == Path("data/parsed")
    assert s.glossary_dir == Path("data/glossary")
    for p in (s.images_dir, s.db_path, s.family_mapping_path, s.cache_dir):
        assert not p.is_absolute()
    assert s.request_delay == 3.0
    assert s.max_requests == 1000
    assert s.connect_timeout == 10.0
    assert s.read_timeout == 30.0
    assert s.user_agent.startswith("bs-database/")
    assert s.log_level == "INFO"


def test_data_dir_derives_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSDB_DATA_DIR", "/x")
    s = Settings()
    for p in (s.images_dir, s.db_path, s.family_mapping_path, s.cache_dir):
        assert p.is_relative_to("/x")
    assert s.state_db_path.is_relative_to("/x")
    assert s.parsed_dir.is_relative_to("/x")
    assert s.glossary_dir == Path("/x/glossary")


def test_explicit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSDB_DATA_DIR", "/x")
    monkeypatch.setenv("BSDB_IMAGES_DIR", "/elsewhere")
    s = Settings()
    assert s.images_dir == Path("/elsewhere")
    assert s.db_path == Path("/x/battle_spirits.db")


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


def test_delay_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSDB_REQUEST_DELAY", "0.5")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("BSDB_REQUEST_DELAY", "1.0")
    assert Settings().request_delay == 1.0


def test_invalid_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSDB_MAX_REQUESTS", "0")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.delenv("BSDB_MAX_REQUESTS")
    monkeypatch.setenv("BSDB_READ_TIMEOUT", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_glossary_dir_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSDB_GLOSSARY_DIR", "/g")
    assert Settings().glossary_dir == Path("/g")
