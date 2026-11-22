"""The build report (#122): quality findings as JSON and Markdown next to the database.

``<db-stem>.build_report.json`` and ``<db-stem>.build_report.md`` are deterministic: no
timestamps, findings sorted by severity then id. They are written on every build, also when the
build fails on quality errors.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bs_database.build.quality.model import SEVERITIES, Finding, Severity
from bs_database.ingest.atomic import atomic_write

REPORT_SCHEMA_VERSION = "1.0.0"
_ORDER = {s: i for i, s in enumerate(SEVERITIES)}


def sort_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Errors first, then warnings, then info; by id inside a severity."""
    return sorted(findings, key=lambda f: (_ORDER[f.severity], f.id))


def failing(findings: Sequence[Finding], *, strict: bool) -> list[Finding]:
    """The findings that fail the build: errors, and warnings when ``strict``. Info never does."""
    fatal = {Severity.ERROR, Severity.WARNING} if strict else {Severity.ERROR}
    return [f for f in sort_findings(findings) if f.severity in fatal]


def report_paths(out: Path) -> tuple[Path, Path]:
    """``<stem>.build_report.json`` and ``.md`` in the directory of the database ``out``."""
    return (
        out.with_name(f"{out.stem}.build_report.json"),
        out.with_name(f"{out.stem}.build_report.md"),
    )


def build_quality_report(
    out: Path,
    findings: Sequence[Finding],
    tables: Mapping[str, int],
    *,
    strict: bool,
) -> dict[str, Any]:
    """The report as JSON-ready data."""
    ordered = sort_findings(findings)
    summary = {
        s.value: {
            "findings": sum(1 for f in ordered if f.severity is s),
            "occurrences": sum(f.count for f in ordered if f.severity is s),
        }
        for s in SEVERITIES
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "database": out.name,
        "strict": strict,
        "status": "failed" if failing(ordered, strict=strict) else "ok",
        "summary": summary,
        "findings": [
            {
                "id": f.id,
                "severity": f.severity.value,
                "origin": f.origin,
                "title": f.title,
                "count": f.count,
                "examples": list(f.examples),
            }
            for f in ordered
        ],
        "tables": dict(sorted(tables.items())),
    }


def render_json(report: Mapping[str, Any]) -> str:
    """Stable JSON text of ``report``."""
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def _cell(text: object) -> str:
    """Make ``text`` safe inside a Markdown table cell."""
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_markdown(report: Mapping[str, Any]) -> str:
    """A human-readable version of ``report``."""
    lines = [
        f"# Build report: {_cell(report['database'])}",
        "",
        f"Status: **{report['status']}** (strict: {'yes' if report['strict'] else 'no'}).",
        "",
        "| Severity | Findings | Occurrences |",
        "| --- | ---: | ---: |",
    ]
    for severity, counts in report["summary"].items():
        lines.append(f"| {severity} | {counts['findings']} | {counts['occurrences']} |")
    lines.append("")
    if not report["findings"]:
        return "\n".join([*lines, "No findings.", ""])
    lines += [
        "## Findings",
        "",
        "| Id | Severity | Origin | What | Count | Examples |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for f in report["findings"]:
        examples = "; ".join(f["examples"])
        lines.append(
            f"| {_cell(f['id'])} | {f['severity']} | {f['origin']} | {_cell(f['title'])} | "
            f"{f['count']} | {_cell(examples)} |"
        )
    return "\n".join([*lines, ""])


def write_report(out: Path, report: Mapping[str, Any]) -> tuple[Path, Path]:
    """Write the JSON and Markdown report next to ``out`` atomically; return both paths."""
    json_path, md_path = report_paths(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(json_path, render_json(report).encode("utf-8"))
    atomic_write(md_path, render_markdown(report).encode("utf-8"))
    return json_path, md_path
