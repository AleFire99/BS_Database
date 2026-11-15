"""CI check (#95): strict normalize over every card fixture, offline, with the real glossary."""

import json
import shutil
from pathlib import Path

import pytest
from golden_support import GLOSSARY_DIR, card_fixture_names, write_parsed_fixture
from typer.testing import CliRunner

from bs_database.cli import app


def test_strict_normalize_over_all_fixtures_without_a_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    shutil.copytree(GLOSSARY_DIR, data / "glossary")
    names = card_fixture_names()
    for name in names:
        write_parsed_fixture(data / "parsed", name)
    monkeypatch.setenv("BSDB_DATA_DIR", str(data))
    monkeypatch.setenv("BSDB_DEEPL_API_KEY", "")  # offline; the no_network fixture backs this up
    result = CliRunner().invoke(app, ["normalize", "--strict"])
    assert result.exit_code == 0, result.output
    report = json.loads((data / "normalized" / "_report.json").read_text(encoding="utf-8"))
    assert report["engine"] == "null"
    assert report["pages"] == {"written": len(names), "failed": []}
    assert report["unmapped"] == {"closed": [], "warnings": []}
