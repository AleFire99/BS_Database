import logging
from collections.abc import Iterator

import pytest
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
