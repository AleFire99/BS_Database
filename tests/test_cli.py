import json
import logging
import os
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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


FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "goldens" / "db.json"


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, restore_logging: None) -> Path:
    data = tmp_path / "data"
    shutil.copytree(FIXTURES / "card_json", data / "json" / "card_json")
    shutil.copy(FIXTURES / "family_mapping.txt", data / "family_mapping.txt")
    monkeypatch.setenv("BSDB_DATA_DIR", str(data))
    return data


def test_commands_listed_with_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ("scrape", "normalize", "build", "images"):
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


def test_normalize_then_build_matches_golden(data_dir: Path) -> None:
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0, result.output
    _assert_matches_golden(data_dir / "battle_spirits.db")


def test_build_db_option(data_dir: Path, tmp_path: Path) -> None:
    runner.invoke(app, ["normalize"])
    target = tmp_path / "custom.db"
    result = runner.invoke(app, ["build", "--db", str(target)])
    assert result.exit_code == 0, result.output
    _assert_matches_golden(target)
    assert not (data_dir / "battle_spirits.db").exists()


@pytest.fixture
def scrape_calls(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    calls: dict[str, list[Any]] = {"sets": [], "links": [], "cards": []}

    def fake_set_urls(url: str, output_path: Path) -> None:
        calls["sets"].append((url, output_path))
        Path(output_path).write_text("index.php?BS01\n", encoding="utf-8")

    def fake_links(url: str, batspi_url: str) -> list[tuple[str, str]]:
        calls["links"].append((url, batspi_url))
        return [("BS01-001", "http://x/1"), ("BS02-001", "http://x/2")]

    def fake_card(card_id: str, url: str, json_dir: str, image_root: str) -> None:
        calls["cards"].append((card_id, url, json_dir, image_root))

    monkeypatch.setattr("bs_database.cli.extract_set_urls", fake_set_urls)
    monkeypatch.setattr("bs_database.cli.extract_links", fake_links)
    monkeypatch.setattr("bs_database.cli.scrape_card_data", fake_card)
    return calls


def test_scrape_reads_urls_and_prefixes_batspi(
    data_dir: Path, scrape_calls: dict[str, list[Any]]
) -> None:
    (data_dir / "extracted_urls.txt").write_text("a.php\n\n  b.php  \n", encoding="utf-8")
    result = runner.invoke(app, ["scrape"])
    assert result.exit_code == 0, result.output
    base = "https://batspi.com/"
    assert scrape_calls["links"] == [(base + "a.php", base), (base + "b.php", base)]
    assert scrape_calls["sets"] == []
    assert len(scrape_calls["cards"]) == 4
    _, _, json_dir, image_root = scrape_calls["cards"][0]
    assert json_dir == str(data_dir / "json")
    assert image_root == str(data_dir / "images")


def test_scrape_set_filter(data_dir: Path, scrape_calls: dict[str, list[Any]]) -> None:
    (data_dir / "extracted_urls.txt").write_text("a.php\n", encoding="utf-8")
    result = runner.invoke(app, ["scrape", "--set", "BS02"])
    assert result.exit_code == 0, result.output
    assert [c[0] for c in scrape_calls["cards"]] == ["BS02-001"]


def test_scrape_refresh_urls_first(data_dir: Path, scrape_calls: dict[str, list[Any]]) -> None:
    result = runner.invoke(app, ["scrape", "--refresh-urls"])
    assert result.exit_code == 0, result.output
    assert scrape_calls["sets"] == [
        ("https://batspi.com/index.php?カードリスト", data_dir / "extracted_urls.txt")
    ]
    assert scrape_calls["links"][0][0] == "https://batspi.com/index.php?BS01"


def test_scrape_missing_url_file(data_dir: Path, scrape_calls: dict[str, list[Any]]) -> None:
    result = runner.invoke(app, ["scrape"])
    assert result.exit_code == 1
    assert "not found" in result.output
    assert scrape_calls["cards"] == []


def test_scrape_default_dirs_keep_legacy_image_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, restore_logging: None
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BSDB_DATA_DIR", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "extracted_urls.txt").write_text("a.php\n", encoding="utf-8")
    seen: list[str] = []
    monkeypatch.setattr(
        "bs_database.cli.extract_links", lambda url, base: [("BS01-001", "http://x/1")]
    )
    monkeypatch.setattr(
        "bs_database.cli.scrape_card_data",
        lambda card_id, link, json_dir, image_root: seen.append(
            os.path.join(image_root, "BS01", f"{card_id}.jpg")
        ),
    )
    assert runner.invoke(app, ["scrape"]).exit_code == 0
    assert seen == ["data/images/BS01/BS01-001.jpg"]


def test_images_range_and_settings(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "bs_database.cli.download_set_images", lambda *a, **k: calls.append((*a, k))
    )
    result = runner.invoke(app, ["images", "--sets", "47-48"])
    assert result.exit_code == 0, result.output
    assert calls == [
        (
            range(47, 49),
            "https://battle-spirits.fandom.com/wiki/",
            "https://battle-spirits.fandom.com",
            str(data_dir / "images"),
            {},
        )
    ]


def test_images_default_range(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    got: list[range] = []
    monkeypatch.setattr("bs_database.cli.download_set_images", lambda nums, *a: got.append(nums))
    assert runner.invoke(app, ["images"]).exit_code == 0
    assert got == [range(19, 72)]


@pytest.mark.parametrize("value", ["abc", "19", "1-2-3", "9-3"])
def test_images_malformed_range(data_dir: Path, value: str) -> None:
    result = runner.invoke(app, ["images", "--sets", value])
    assert result.exit_code == 2
