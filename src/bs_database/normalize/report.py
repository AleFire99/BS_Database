"""The normalize report (#95, ADR 0008): unmapped terms and translation coverage.

``_report.json`` and ``_report.md`` sit at the root of the normalized directory, outside the
``*/*.json`` page glob. They are deterministic: no timestamps, everything sorted. Engine call
statistics (cache hits, characters sent) depend on the cache state, so they go to the log and
stdout, not here.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bs_database.glossary import CLOSED
from bs_database.ingest.atomic import atomic_write
from bs_database.normalize.pipeline import TreeResult

REPORT_SCHEMA_VERSION = "1.0.0"
REPORT_JSON = "_report.json"
REPORT_MD = "_report.md"
SAMPLE_URLS = 5
CATEGORIES = ("families", "names", "products")


def _terms(pages: Mapping[tuple[str, str], frozenset[str]], *, closed: bool | None) -> list[Any]:
    out: list[dict[str, Any]] = []
    for (kind, jp), urls in sorted(pages.items()):
        if closed is not None and (kind in CLOSED) is not closed:
            continue
        out.append(
            {"kind": kind, "jp": jp, "pages": len(urls), "samples": sorted(urls)[:SAMPLE_URLS]}
        )
    return out


def _coverage(result: TreeResult, category: str) -> dict[str, int]:
    distinct = getattr(result.texts, category)
    requested = getattr(result.requests, category)
    statuses = [result.translations[t].status for t in requested]
    return {
        "distinct": len(distinct),
        "from_glossary_or_batspi": len(distinct) - len(requested),
        "machine": statuses.count("machine"),
        "pending": statuses.count("pending"),
        "failed": statuses.count("failed"),
    }


def build_report(result: TreeResult, engine: str, parsed_dir: Path) -> dict[str, Any]:
    """The report as JSON-ready data. Failed pages are listed relative to ``parsed_dir``."""
    failed = sorted(p.relative_to(parsed_dir).as_posix() for p in result.failed)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "engine": engine,
        "pages": {"written": result.written, "failed": failed},
        "unmapped": {
            "closed": _terms(result.unmapped_pages, closed=True),
            "warnings": _terms(result.unmapped_pages, closed=False),
        },
        "uncurated": _terms(result.uncurated_pages, closed=None),
        "translation": {c: _coverage(result, c) for c in CATEGORIES},
    }


def render_json(report: Mapping[str, Any]) -> str:
    """Stable JSON text of ``report``."""
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def _cell(text: object) -> str:
    """Make ``text`` safe inside a Markdown table cell."""
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _term_lines(title: str, terms: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title} ({len(terms)})", ""]
    if not terms:
        return [*lines, "None.", ""]
    lines += ["| Kind | Japanese | Pages | Sample |", "| --- | --- | ---: | --- |"]
    for t in terms:
        sample = t["samples"][0] if t["samples"] else ""
        lines.append(f"| {_cell(t['kind'])} | {_cell(t['jp'])} | {t['pages']} | {_cell(sample)} |")
    return [*lines, ""]


def render_markdown(report: Mapping[str, Any]) -> str:
    """A human-readable version of ``report``."""
    pages = report["pages"]
    lines = [
        "# Normalize report",
        "",
        f"Engine: `{report['engine']}`. Pages written: {pages['written']}, "
        f"failed: {len(pages['failed'])}.",
        "",
    ]
    if pages["failed"]:
        lines += ["## Failed pages", "", *[f"- `{p}`" for p in pages["failed"]], ""]
    lines += _term_lines("Unmapped, closed (errors)", report["unmapped"]["closed"])
    lines += _term_lines("Unmapped, warnings (strict fails)", report["unmapped"]["warnings"])
    lines += _term_lines("Uncurated (glossary row without a code)", report["uncurated"])
    lines += [
        "## Translation",
        "",
        "| Category | Distinct | Glossary or batspi | Machine | Pending | Failed |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for category in CATEGORIES:
        c = report["translation"][category]
        lines.append(
            f"| {category} | {c['distinct']} | {c['from_glossary_or_batspi']} | "
            f"{c['machine']} | {c['pending']} | {c['failed']} |"
        )
    return "\n".join([*lines, ""])


def write_report(normalized_dir: Path, report: Mapping[str, Any]) -> None:
    """Write ``_report.json`` and ``_report.md`` atomically into ``normalized_dir``."""
    normalized_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(normalized_dir / REPORT_JSON, render_json(report).encode("utf-8"))
    atomic_write(normalized_dir / REPORT_MD, render_markdown(report).encode("utf-8"))
