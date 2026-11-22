"""Quality findings in the build: failing, strict, the report and the old database (#122)."""

import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from build_support import build, golden_documents
from golden_support import GLOSSARY_DIR, NORMALIZED_GOLDENS, real_glossary
from typer.testing import CliRunner

import bs_database.build.builder as builder
import bs_database.build.quality.loader as loader
from bs_database.build import BuildQualityError, build_database
from bs_database.build.quality import Rule, Severity
from bs_database.cli import app

runner = CliRunner()

ERR = Rule("Q900", Severity.ERROR, "Test error", "SELECT 'bad' FROM schema_meta")
WARN = Rule("Q930", Severity.WARNING, "Test warning", "SELECT 'meh' FROM schema_meta")
INFO = Rule("Q950", Severity.INFO, "Test info", "SELECT 'fyi' FROM schema_meta")


def _fk_break(conn: sqlite3.Connection, *_: object) -> None:
    conn.execute("PRAGMA defer_foreign_keys = ON")
    conn.execute("INSERT INTO card_numbers (number, card_id) VALUES ('A-1', 99)")


def test_fixture_build_has_no_errors_and_writes_the_report(tmp_path: Path) -> None:
    result = build(tmp_path / "x.db", golden_documents())
    assert not [f for f in result.findings if f.severity is Severity.ERROR]
    assert result.report_json == tmp_path / "x.build_report.json"
    assert result.report_md == tmp_path / "x.build_report.md"
    report = json.loads(result.report_json.read_text("utf-8"))
    assert report["status"] == "ok"
    assert report["schema_version"] == "1.0.0"


def test_two_builds_give_identical_reports(tmp_path: Path) -> None:
    for name in ("a", "b"):
        build(tmp_path / name / "x.db", golden_documents())
    for suffix in ("json", "md"):
        a = (tmp_path / "a" / f"x.build_report.{suffix}").read_bytes()
        assert a == (tmp_path / "b" / f"x.build_report.{suffix}").read_bytes()


def test_error_fails_keeps_the_old_database_and_writes_the_report(tmp_path: Path) -> None:
    out = tmp_path / "x.db"
    build_database(out, real_glossary())
    before = out.read_bytes()
    with pytest.raises(BuildQualityError) as info:
        build_database(out, real_glossary(), rules=[ERR])
    assert out.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))
    report = json.loads((tmp_path / "x.build_report.json").read_text("utf-8"))
    assert report["status"] == "failed"
    assert [f["id"] for f in report["findings"]] == ["Q900"]
    assert [f.id for f in info.value.failed] == ["Q900"]
    assert "Q900" in (tmp_path / "x.build_report.md").read_text("utf-8")


def test_error_without_an_old_database_leaves_only_the_report(tmp_path: Path) -> None:
    with pytest.raises(BuildQualityError):
        build_database(tmp_path / "x.db", real_glossary(), rules=[ERR])
    assert not (tmp_path / "x.db").exists()
    assert (tmp_path / "x.build_report.json").is_file()


def test_foreign_key_violation_is_rule_q001(tmp_path: Path) -> None:
    with pytest.raises(BuildQualityError) as info:
        build_database(tmp_path / "x.db", real_glossary(), load=_fk_break)
    assert [f.id for f in info.value.failed] == ["Q001"]


def test_warning_passes_but_fails_under_strict(tmp_path: Path) -> None:
    result = build_database(tmp_path / "x.db", real_glossary(), rules=[WARN])
    assert [f.id for f in result.findings] == ["Q930"]
    with pytest.raises(BuildQualityError, match="Q930"):
        build_database(tmp_path / "y.db", real_glossary(), rules=[WARN], strict=True)
    assert not (tmp_path / "y.db").exists()
    assert json.loads((tmp_path / "y.build_report.json").read_text("utf-8"))["strict"] is True


def test_info_never_fails_not_even_strict(tmp_path: Path) -> None:
    result = build_database(tmp_path / "x.db", real_glossary(), rules=[INFO], strict=True)
    assert [f.id for f in result.findings] == ["Q950"]
    assert result.path.exists()


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    monkeypatch.setenv("BSDB_DATA_DIR", str(data))
    return data


def _data(data_dir: Path) -> None:
    shutil.copytree(NORMALIZED_GOLDENS, data_dir / "normalized" / "batspi")
    shutil.copytree(GLOSSARY_DIR, data_dir / "glossary")


def test_cli_warnings_exit_zero_and_strict_exits_one(data_dir: Path) -> None:
    _data(data_dir)
    assert runner.invoke(app, ["build"]).exit_code == 0
    db = data_dir / "battle_spirits.db"
    before = db.read_bytes()
    result = runner.invoke(app, ["build", "--strict"])
    assert result.exit_code == 1
    assert "build_report" in result.output
    assert db.read_bytes() == before


def test_cli_error_exits_one_and_keeps_the_old_database(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _data(data_dir)
    db = data_dir / "battle_spirits.db"
    db.write_bytes(b"old content")
    monkeypatch.setattr(builder, "RULES", (ERR,))
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 1
    assert "Q900" in result.output
    assert db.read_bytes() == b"old content"
    assert (data_dir / "battle_spirits.build_report.json").is_file()
    assert (data_dir / "battle_spirits.build_report.md").is_file()


def test_cli_info_never_fails_even_strict(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _data(data_dir)
    monkeypatch.setattr(builder, "RULES", (INFO,))
    monkeypatch.setattr(
        loader, "LOADER_KINDS", {k: (Severity.INFO, t) for k, (_, t) in loader.LOADER_KINDS.items()}
    )
    result = runner.invoke(app, ["build", "--strict"])
    assert result.exit_code == 0, result.output
    assert "[info] Q950" in result.output
