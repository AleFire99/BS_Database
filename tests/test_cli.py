"""Tests.

Goldens in tests/goldens/ were generated from the legacy code at 5ae5646
(legacy code removed in #23; see tag v0.1.0).
"""

import json
import logging
import re
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from golden_support import GLOSSARY_DIR, write_parsed_fixture
from typer.testing import CliRunner

from bs_database import __version__
from bs_database.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "bsdb" in result.output
    assert "Usage" in result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"bsdb {__version__}"


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output


@pytest.fixture
def restore_logging() -> Iterator[None]:
    """Restore the root logger and expose a throwaway ``ping`` command to drive the callback."""
    root = logging.getLogger()
    level, handlers = root.level, list(root.handlers)
    app.command("ping")(lambda: None)
    yield
    app.registered_commands.pop()
    for h in list(root.handlers):
        if h not in handlers:
            root.removeHandler(h)
    root.setLevel(level)


def test_log_level_option_overrides_env(
    monkeypatch: pytest.MonkeyPatch, restore_logging: None
) -> None:
    monkeypatch.setenv("BSDB_LOG_LEVEL", "ERROR")
    result = runner.invoke(app, ["--log-level", "DEBUG", "ping"])
    assert result.exit_code == 0
    assert logging.getLogger().level == logging.DEBUG


def test_env_log_level_used_by_default(
    monkeypatch: pytest.MonkeyPatch, restore_logging: None
) -> None:
    monkeypatch.setenv("BSDB_LOG_LEVEL", "WARNING")
    result = runner.invoke(app, ["ping"])
    assert result.exit_code == 0
    assert logging.getLogger().level == logging.WARNING


def test_invalid_log_level_fails(restore_logging: None) -> None:
    result = runner.invoke(app, ["--log-level", "NOPE", "ping"])
    assert result.exit_code != 0


FIXTURES = Path(__file__).parent / "fixtures"
LEGACY_JSON = FIXTURES / "legacy" / "card_json"
GOLDEN = Path(__file__).parent / "goldens" / "db.json"


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, restore_logging: None) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("BSDB_DATA_DIR", str(data))
    monkeypatch.setenv("BSDB_DEEPL_API_KEY", "")  # empty means offline; also beats a local .env
    return data


def test_commands_listed_with_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ("scrape", "normalize", "build"):
        assert name in result.output
        assert runner.invoke(app, [name, "--help"]).exit_code == 0


def _assert_matches_golden(db: Path) -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    con = sqlite3.connect(db)
    for table, count in golden["counts"].items():
        assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == count, table
    for table in ("card_types", "colors", "families"):
        names = sorted(r[0] for r in con.execute(f"SELECT name FROM {table}"))
        assert names == golden[f"{table}_names"], table
    con.close()


def test_build_matches_golden(data_dir: Path) -> None:
    result = runner.invoke(app, ["build", "--input", str(LEGACY_JSON)])
    assert result.exit_code == 0, result.output
    _assert_matches_golden(data_dir / "battle_spirits.db")


def test_build_requires_input(data_dir: Path) -> None:
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 2


def test_build_db_option(data_dir: Path, tmp_path: Path) -> None:
    target = tmp_path / "custom.db"
    result = runner.invoke(app, ["build", "--input", str(LEGACY_JSON), "--db", str(target)])
    assert result.exit_code == 0, result.output
    _assert_matches_golden(target)
    assert not (data_dir / "battle_spirits.db").exists()


def test_images_command_removed() -> None:
    assert runner.invoke(app, ["images"]).exit_code == 2


def test_no_network_guard() -> None:
    import requests

    with pytest.raises(AssertionError, match="network"):
        requests.get("https://example.invalid/")


def _parsed_data(data_dir: Path, *names: str) -> None:
    for name in names:
        write_parsed_fixture(data_dir / "parsed", name)


@pytest.fixture
def glossary_data(data_dir: Path) -> Path:
    shutil.copytree(GLOSSARY_DIR, data_dir / "glossary")
    return data_dir


def test_normalize_happy_path(glossary_data: Path) -> None:
    _parsed_data(glossary_data, "card_spirit.html", "card_flip.html")
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 0, result.output
    assert re.fullmatch(r"Normalized 2 pages, \d+ unmapped terms \(0 closed\)\n", result.stdout)
    assert len(list((glossary_data / "normalized" / "batspi").glob("*.json"))) == 2


def test_normalize_closed_unmapped_exits_1_without_file(glossary_data: Path) -> None:
    path = write_parsed_fixture(glossary_data / "parsed", "card_magic.html")
    document = json.loads(path.read_text(encoding="utf-8"))
    document["page"]["entries"][0]["gameplay"]["card_type"] = "謎のタイプ"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 1
    assert "1 closed" in result.stdout
    assert not (glossary_data / "normalized").exists()


def test_normalize_missing_glossary_is_a_clear_error(data_dir: Path) -> None:
    _parsed_data(data_dir, "card_spirit.html")
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 1
    assert "invalid glossary" in result.output
    assert "missing file" in result.output


def test_normalize_missing_parsed_dir_is_a_clear_error(glossary_data: Path) -> None:
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 1
    assert "parsed directory not found" in result.output


def test_normalize_has_no_legacy_option(glossary_data: Path) -> None:
    result = runner.invoke(app, ["normalize", "--legacy"])
    assert result.exit_code == 2
