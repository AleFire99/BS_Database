"""Tests of the ``bsdb`` command line."""

import json
import logging
import re
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes import FakeEngine
from golden_support import (
    GLOSSARY_DIR,
    NORMALIZED_GOLDENS,
    blank_family_curation,
    write_parsed_fixture,
)
from typer.testing import CliRunner

from bs_database import __version__
from bs_database.cli import app
from bs_database.translate.cache import TranslationCache
from bs_database.translate.cached import CachedTranslator

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


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, restore_logging: None) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("BSDB_DATA_DIR", str(data))
    # a missing model means offline; also beats a local model or .env
    monkeypatch.setenv("BSDB_MT_MODEL_DIR", str(data / "no-model"))
    return data


def test_commands_listed_with_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ("scrape", "normalize", "build"):
        assert name in result.output
        assert runner.invoke(app, [name, "--help"]).exit_code == 0


def _normalized_data(data_dir: Path) -> None:
    shutil.copytree(NORMALIZED_GOLDENS, data_dir / "normalized" / "batspi")
    shutil.copytree(GLOSSARY_DIR, data_dir / "glossary")


def _rows(db: Path, sql: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(db) as con:
        return con.execute(sql).fetchall()


def test_build_writes_the_default_database(data_dir: Path) -> None:
    _normalized_data(data_dir)
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0, result.output
    db = data_dir / "battle_spirits.db"
    assert _rows(db, "SELECT count(*) FROM cards") == [(46,)]
    assert "cards: 46" in result.output
    assert "Quality: 0 errors," in result.output
    assert "Report: " in result.output
    assert (data_dir / "battle_spirits.build_report.json").is_file()
    assert "block_icon_conflict" in result.output
    assert "Image association levels: L0 " in result.output


def test_build_out_option_and_replace(data_dir: Path, tmp_path: Path) -> None:
    _normalized_data(data_dir)
    target = tmp_path / "custom.db"
    target.write_bytes(b"old content")
    result = runner.invoke(app, ["build", "--out", str(target)])
    assert result.exit_code == 0, result.output
    assert _rows(target, "SELECT count(*) FROM cards") == [(46,)]
    assert not (data_dir / "battle_spirits.db").exists()


def test_build_built_at_is_reproducible(data_dir: Path, tmp_path: Path) -> None:
    _normalized_data(data_dir)
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    for target in (a, b):
        result = runner.invoke(
            app, ["build", "--out", str(target), "--built-at", "2026-01-01T00:00:00+00:00"]
        )
        assert result.exit_code == 0, result.output
    assert a.read_bytes() == b.read_bytes()


def test_build_rejects_a_bad_built_at(data_dir: Path) -> None:
    _normalized_data(data_dir)
    result = runner.invoke(app, ["build", "--built-at", "yesterday"])
    assert result.exit_code == 2


def test_build_without_normalized_data_fails(data_dir: Path) -> None:
    shutil.copytree(GLOSSARY_DIR, data_dir / "glossary")
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 1
    assert "bsdb normalize" in result.output
    assert not (data_dir / "battle_spirits.db").exists()


def test_build_error_keeps_the_old_database(data_dir: Path) -> None:
    _normalized_data(data_dir)
    old = data_dir / "battle_spirits.db"
    old.write_bytes(b"old content")
    bad = next((data_dir / "normalized" / "batspi").glob("card_magic.json"))
    bad.write_text("{}", encoding="utf-8")
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 1
    assert "not a normalized document" in result.output
    assert old.read_bytes() == b"old content"


def test_build_invalid_glossary_fails(data_dir: Path) -> None:
    _normalized_data(data_dir)
    (data_dir / "glossary" / "colors.csv").write_text("jp,code\n", encoding="utf-8")
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 1
    assert "invalid glossary" in result.output


def test_build_input_option_is_gone(data_dir: Path) -> None:
    assert runner.invoke(app, ["build", "--input", "x"]).exit_code == 2


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
    assert re.fullmatch(
        r"Normalized 2 pages, \d+ unmapped terms \(0 closed\), \d+ uncurated terms\n"
        r"Translation \(null\): 0 machine, \d+ pending, 0 failed\n"
        r"Report: \S+_report\.md\n",
        result.stdout,
    )
    for name in ("_report.json", "_report.md"):
        assert (glossary_data / "normalized" / name).is_file()
    assert len(list((glossary_data / "normalized" / "batspi").glob("*.json"))) == 2


def test_normalize_closed_unmapped_exits_1_without_file(glossary_data: Path) -> None:
    path = write_parsed_fixture(glossary_data / "parsed", "card_magic.html")
    document = json.loads(path.read_text(encoding="utf-8"))
    document["page"]["entries"][0]["gameplay"]["card_type"] = "謎のタイプ"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 1
    assert "1 closed" in result.stdout
    assert list((glossary_data / "normalized").rglob("batspi/*.json")) == []
    report = json.loads((glossary_data / "normalized" / "_report.json").read_text("utf-8"))
    assert [t["jp"] for t in report["unmapped"]["closed"]] == ["謎のタイプ"]


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


def _drop_family_rows(glossary_dir: Path, jp: str) -> None:
    path = glossary_dir / "families.csv"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [lines[0], *(ln for ln in lines[1:] if not ln.startswith(f"{jp},"))]
    assert len(kept) < len(lines)
    path.write_text("".join(kept), encoding="utf-8")


def test_normalize_strict_passes_on_the_real_glossary(glossary_data: Path) -> None:
    _parsed_data(glossary_data, "card_spirit.html", "card_flip.html")
    result = runner.invoke(app, ["normalize", "--strict"])
    assert result.exit_code == 0, result.output
    assert "uncurated terms" in result.stdout


def test_normalize_strict_fails_on_an_unmapped_family_but_writes_pages(glossary_data: Path) -> None:
    blank_family_curation(glossary_data / "glossary")
    _parsed_data(glossary_data, "card_flip.html")
    assert runner.invoke(app, ["normalize"]).exit_code == 0
    report = json.loads((glossary_data / "normalized" / "_report.json").read_text("utf-8"))
    jp = report["uncurated"][0]["jp"]
    _drop_family_rows(glossary_data / "glossary", jp)
    plain = runner.invoke(app, ["normalize"])
    assert plain.exit_code == 0, plain.output
    strict = runner.invoke(app, ["normalize", "--strict"])
    assert strict.exit_code == 1
    assert "strict:" in strict.output
    assert len(list((glossary_data / "normalized" / "batspi").glob("*.json"))) == 1
    report = json.loads((glossary_data / "normalized" / "_report.json").read_text("utf-8"))
    assert [t["jp"] for t in report["unmapped"]["warnings"]] == [jp]


def test_normalize_max_chars_zero_and_bad_values(glossary_data: Path) -> None:
    _parsed_data(glossary_data, "card_spirit.html")
    assert runner.invoke(app, ["normalize", "--max-chars", "0"]).exit_code == 0
    assert runner.invoke(app, ["normalize", "--max-chars", "-1"]).exit_code == 2
    assert runner.invoke(app, ["normalize", "--max-chars", "many"]).exit_code == 2


def test_normalize_with_an_engine_uses_the_engine_and_pending_does_not_fail_strict(
    glossary_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _parsed_data(glossary_data, "card_flip.html")
    monkeypatch.setattr(
        "bs_database.cli.make_translator",
        lambda settings, *, max_chars=None: CachedTranslator(
            FakeEngine(), TranslationCache(settings.translation_cache_path), max_chars=max_chars
        ),
    )
    result = runner.invoke(app, ["normalize", "--strict"])
    assert result.exit_code == 0, result.output
    assert "Translation (fake):" in result.stdout
    assert ": 0 machine" not in result.stdout
    monkeypatch.setenv("BSDB_TRANSLATION_CACHE_PATH", str(glossary_data / "fresh.sqlite"))
    limited = runner.invoke(app, ["normalize", "--strict", "--max-chars", "0"])
    assert limited.exit_code == 0, limited.output
    assert ": 0 machine" in limited.stdout
    assert " 0 pending" not in limited.stdout
