"""The build report: format, determinism, escaping (#122)."""

import json
from pathlib import Path
from typing import Any

from bs_database.build.quality import (
    REPORT_SCHEMA_VERSION,
    Finding,
    Severity,
    build_quality_report,
    failing,
    render_json,
    render_markdown,
    report_paths,
    write_report,
)

FINDINGS = [
    Finding("Q050", Severity.INFO, "rule", "Info", 5, ("a",)),
    Finding("Q030", Severity.WARNING, "rule", "Warn", 2, ("b | c", "d\ne")),
    Finding("Q006", Severity.ERROR, "rule", "Err", 1, ("p",)),
    Finding("level_duplicate", Severity.WARNING, "loader", "Dup", 3, ()),
]


def _report(strict: bool = False) -> dict[str, Any]:
    return build_quality_report(Path("x/db.db"), FINDINGS, {"b": 2, "a": 1}, strict=strict)


def test_report_structure_and_order() -> None:
    report = _report()
    assert report["schema_version"] == REPORT_SCHEMA_VERSION == "1.0.0"
    assert [f["id"] for f in report["findings"]] == ["Q006", "Q030", "level_duplicate", "Q050"]
    assert report["summary"]["warning"] == {"findings": 2, "occurrences": 5}
    assert list(report["tables"]) == ["a", "b"]
    assert report["database"] == "db.db"


def test_failing_follows_strict_and_info_never_fails() -> None:
    assert [f.id for f in failing(FINDINGS, strict=False)] == ["Q006"]
    assert [f.id for f in failing(FINDINGS, strict=True)] == ["Q006", "Q030", "level_duplicate"]
    info = [Finding("Q050", Severity.INFO, "rule", "Info", 5, ())]
    assert failing(info, strict=True) == []
    assert build_quality_report(Path("d.db"), info, {}, strict=True)["status"] == "ok"
    assert _report()["status"] == "failed"


def test_markdown_escapes_table_cells() -> None:
    md = render_markdown(_report())
    assert "b \\| c; d e" in md
    assert md.endswith("\n")
    assert render_markdown(build_quality_report(Path("d.db"), [], {}, strict=False)).count(
        "No findings."
    )


def test_paths_use_the_database_stem(tmp_path: Path) -> None:
    json_path, md_path = report_paths(tmp_path / "battle_spirits.db")
    assert json_path.name == "battle_spirits.build_report.json"
    assert md_path.name == "battle_spirits.build_report.md"


def test_write_report_is_valid_and_deterministic(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "x.db"
    json_path, md_path = write_report(out, _report())
    first = (json_path.read_bytes(), md_path.read_bytes())
    assert json.loads(first[0])["status"] == "failed"
    write_report(out, _report())
    assert (json_path.read_bytes(), md_path.read_bytes()) == first
    assert render_json(_report()).encode() == first[0]
    assert not list(out.parent.glob("*.tmp"))
