"""``bsdb glossary review`` through CliRunner (#96), offline."""

import shutil
from pathlib import Path

import pytest
from golden_support import GLOSSARY_DIR, card_fixture_names, real_glossary, write_parsed_fixture
from test_review_legacy import make_legacy
from typer.testing import CliRunner

from bs_database.cli import app
from bs_database.normalize.pipeline import normalize_tree
from bs_database.review.render import FAMILIES_CSV, KEYWORDS_CSV, LEGACY_CSV, REVIEW_MD
from bs_database.review.source import iter_pages
from bs_database.translate import NullTranslator

runner = CliRunner()


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    shutil.copytree(GLOSSARY_DIR, data / "glossary")
    for name in card_fixture_names():
        write_parsed_fixture(data / "parsed", name)
    normalize_tree(data / "parsed", data / "normalized", real_glossary(), NullTranslator())
    monkeypatch.setenv("BSDB_DATA_DIR", str(data))
    return data


def test_review_writes_tables_and_csvs(data_dir: Path, tmp_path: Path) -> None:
    number = next(iter_pages(data_dir / "normalized"))["entries"][0]["number"]
    legacy = make_legacy(tmp_path / "legacy.db", {number: ["Rebirth"]})
    result = runner.invoke(app, ["glossary", "review", "--legacy-db", str(legacy)])
    assert result.exit_code == 0, result.output
    out = data_dir / "review"
    for name in (REVIEW_MD, FAMILIES_CSV, KEYWORDS_CSV, LEGACY_CSV):
        assert (out / name).is_file()
    assert "## Families (" in (out / REVIEW_MD).read_text(encoding="utf-8")
    assert "Review: " in result.output
    assert (data_dir / "glossary" / "families.csv").read_bytes() == (
        GLOSSARY_DIR / "families.csv"
    ).read_bytes()


def test_review_out_option(data_dir: Path, tmp_path: Path) -> None:
    legacy = make_legacy(tmp_path / "legacy.db", {})
    out = tmp_path / "elsewhere"
    result = runner.invoke(
        app, ["glossary", "review", "--legacy-db", str(legacy), "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert (out / REVIEW_MD).is_file()
    assert not (data_dir / "review").exists()


def test_review_missing_legacy_db_exits_1(data_dir: Path, tmp_path: Path) -> None:
    result = runner.invoke(app, ["glossary", "review", "--legacy-db", str(tmp_path / "none.db")])
    assert result.exit_code == 1
    assert "legacy database not found" in result.output


def test_review_rejects_other_schema_version(data_dir: Path, tmp_path: Path) -> None:
    page = next((data_dir / "normalized").glob("*/*.json"))
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            '"schema_version": "1.1.0"', '"schema_version": "0.9.0"'
        ),
        encoding="utf-8",
    )
    legacy = make_legacy(tmp_path / "legacy.db", {})
    result = runner.invoke(app, ["glossary", "review", "--legacy-db", str(legacy)])
    assert result.exit_code == 1
    assert "schema_version" in result.output


def test_review_missing_normalized_dir_exits_1(data_dir: Path, tmp_path: Path) -> None:
    shutil.rmtree(data_dir / "normalized")
    legacy = make_legacy(tmp_path / "legacy.db", {})
    result = runner.invoke(app, ["glossary", "review", "--legacy-db", str(legacy)])
    assert result.exit_code == 1
    assert "normalized directory not found" in result.output


def test_review_invalid_glossary_exits_1(data_dir: Path, tmp_path: Path) -> None:
    (data_dir / "glossary" / "colors.csv").unlink()
    legacy = make_legacy(tmp_path / "legacy.db", {})
    result = runner.invoke(app, ["glossary", "review", "--legacy-db", str(legacy)])
    assert result.exit_code == 1
    assert "invalid glossary" in result.output


def test_glossary_help_lists_review() -> None:
    result = runner.invoke(app, ["glossary", "--help"])
    assert result.exit_code == 0
    assert "review" in result.output
