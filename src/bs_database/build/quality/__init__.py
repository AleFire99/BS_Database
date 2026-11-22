"""Quality rules, loader-warning severities and the build report (#122)."""

from bs_database.build.quality.loader import LOADER_KINDS, loader_findings
from bs_database.build.quality.model import Finding, Rule, Severity
from bs_database.build.quality.report import (
    REPORT_SCHEMA_VERSION,
    build_quality_report,
    failing,
    render_json,
    render_markdown,
    report_paths,
    sort_findings,
    write_report,
)
from bs_database.build.quality.rules import RULES, rule
from bs_database.build.quality.runner import run_rules

__all__ = [
    "REPORT_SCHEMA_VERSION",
    "LOADER_KINDS",
    "RULES",
    "Finding",
    "Rule",
    "Severity",
    "build_quality_report",
    "failing",
    "loader_findings",
    "render_json",
    "render_markdown",
    "report_paths",
    "rule",
    "run_rules",
    "sort_findings",
    "write_report",
]
