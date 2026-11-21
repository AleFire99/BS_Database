"""Command-line interface for bs-database."""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from bs_database import __version__
from bs_database.build import BuildError, BuildResult, build_from_directories
from bs_database.glossary import GlossaryError, load_glossary
from bs_database.ingest.cache import CachedFetcher, RawCache
from bs_database.ingest.fandom import FandomApi
from bs_database.ingest.http import HttpClient
from bs_database.ingest.pipeline import RunOptions, run_pipeline
from bs_database.ingest.policy import StopRun
from bs_database.ingest.report import render
from bs_database.ingest.state import StateStore
from bs_database.log import configure_logging
from bs_database.normalize.pipeline import normalize_tree
from bs_database.normalize.report import REPORT_MD, build_report, write_report
from bs_database.review.fandom import FANDOM_JSON, NameSource, fetch_names, write_names
from bs_database.review.render import REVIEW_MD, source_summary, write_review
from bs_database.review.run import run_review
from bs_database.review.source import ReviewError
from bs_database.settings import Settings
from bs_database.translate import make_translator

app = typer.Typer(no_args_is_help=True, help="bsdb: Battle Spirits card database tooling.")


glossary_app = typer.Typer(no_args_is_help=True, help="Glossary curation tools.")
app.add_typer(glossary_app, name="glossary")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"bsdb {__version__}")
        raise typer.Exit()


def _level_callback(value: str | None) -> str | None:
    if value is not None and not isinstance(logging.getLevelName(value.upper()), int):
        raise typer.BadParameter(f"unknown log level: {value}")
    return value


@app.callback()
def main(
    ctx: typer.Context,
    log_level: Annotated[
        str | None,
        typer.Option(
            "--log-level",
            callback=_level_callback,
            help="Root log level; overrides BSDB_LOG_LEVEL.",
        ),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """bsdb: Battle Spirits card database tooling."""
    settings = Settings()
    ctx.obj = settings
    configure_logging(log_level or settings.log_level)


def _settings(ctx: typer.Context) -> Settings:
    settings: Settings = ctx.obj
    return settings


@app.command()
def normalize(
    ctx: typer.Context,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Exit 1 on any unmapped term (no glossary row)."),
    ] = False,
    max_chars: Annotated[
        int | None,
        typer.Option(
            "--max-chars",
            min=0,
            help="Send at most this many characters to the translation engine (0 = cache only).",
        ),
    ] = None,
) -> None:
    """Normalize data/parsed into data/normalized: glossary codes and English names.

    Card names, product names and families are machine-translated offline when the quickmt
    model is in BSDB_MT_MODEL_DIR and the mt group is installed; otherwise nothing is translated.
    Writes _report.json and _report.md next to the pages.
    """
    settings = _settings(ctx)
    if not settings.parsed_dir.is_dir():
        typer.echo(f"error: parsed directory not found: {settings.parsed_dir}", err=True)
        raise typer.Exit(1)
    try:
        glossary = load_glossary(settings.glossary_dir)
    except GlossaryError as exc:
        typer.echo(f"error: invalid glossary in {settings.glossary_dir}:\n{exc}", err=True)
        raise typer.Exit(1) from exc
    translator = make_translator(settings, max_chars=max_chars)
    result = normalize_tree(settings.parsed_dir, settings.normalized_dir, glossary, translator)
    report = build_report(result, translator.name, settings.parsed_dir)
    write_report(settings.normalized_dir, report)
    statuses = [r.status for r in result.translations.values()]
    typer.echo(
        f"Normalized {result.written} pages, {len(result.unmapped)} unmapped terms "
        f"({result.closed} closed), {len(report['uncurated'])} uncurated terms"
    )
    typer.echo(
        f"Translation ({translator.name}): {statuses.count('machine')} machine, "
        f"{statuses.count('pending')} pending, {statuses.count('failed')} failed"
    )
    typer.echo(f"Report: {settings.normalized_dir / REPORT_MD}")
    if result.failed:
        typer.echo(f"{len(result.failed)} pages failed", err=True)
        raise typer.Exit(1)
    if strict and any(not t.closed for t in result.unmapped):
        warnings = len(report["unmapped"]["warnings"])
        typer.echo(f"strict: {warnings} unmapped terms without a glossary row", err=True)
        raise typer.Exit(1)


@glossary_app.command("review")
def glossary_review(
    ctx: typer.Context,
    legacy_db: Annotated[
        Path,
        typer.Option("--legacy-db", help="The v0.1.0 battle_spirits.db snapshot (read-only)."),
    ],
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output directory (default: <data dir>/review)."),
    ] = None,
    fandom: Annotated[
        Path | None,
        typer.Option("--fandom", help="fandom_names.json from `bsdb glossary fandom` (optional)."),
    ] = None,
) -> None:
    """Propose glossary rows from data/normalized and the legacy snapshot, for the owner.

    Writes review.md (families, keywords, no_split candidates, product-code prefixes, untyped
    products, slug conflicts, legacy pairs) and ready-to-copy families.csv, keywords.csv and
    family_legacy_en.csv. Nothing under data/glossary is changed. Copy families.csv and
    family_legacy_en.csv together, and re-sort families.csv and keywords.csv by code after
    filling codes by hand (the loader requires it).
    """
    settings = _settings(ctx)
    try:
        load_glossary(settings.glossary_dir)
    except GlossaryError as exc:
        typer.echo(f"error: invalid glossary in {settings.glossary_dir}:\n{exc}", err=True)
        raise typer.Exit(1) from exc
    try:
        review = run_review(settings.normalized_dir, settings.glossary_dir, legacy_db, fandom)
    except ReviewError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    target = out or settings.data_dir / "review"
    write_review(target, review)
    typer.echo(
        f"Review: {len(review.families)} families, {len(review.keywords)} keywords, "
        f"{len(review.no_split)} no_split candidates, {len(review.prefixes)} prefixes, "
        f"{len(review.conflicts)} slug conflicts"
    )
    if review.with_fandom:
        typer.echo(f"Family names by source: {source_summary(review)}")
    typer.echo(f"Written to {target / REVIEW_MD} and the CSV files next to it")


def _build_fandom_api(settings: Settings) -> NameSource:
    """The one place the real fandom client is built (tests replace it with a fake)."""
    return FandomApi(settings)


@glossary_app.command("fandom")
def glossary_fandom(
    ctx: typer.Context,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output directory (default: <data dir>/review)."),
    ] = None,
) -> None:
    """Fetch family, keyword and rarity names from the fandom wiki api (ADR 0009).

    Reads only api.php (about 20 requests, cached under the cache dir, 0 when cached) and writes
    fandom_names.json for ``bsdb glossary review --fandom``. A 403 or challenge page stops the
    run with exit 3. Nothing under data/glossary is changed.
    """
    settings = _settings(ctx)
    api = _build_fandom_api(settings)
    try:
        data = fetch_names(api)
    except StopRun as exc:
        typer.echo(f"stopped: {exc}", err=True)
        raise typer.Exit(3) from exc
    target = (out or settings.data_dir / "review") / FANDOM_JSON
    write_names(target, data)
    typer.echo(
        f"Fandom: {len(data.families)} families ({len(data.unmatched_families)} unmatched), "
        f"{len(data.keywords)} keywords ({len(data.unmatched_keywords)} unmatched), "
        f"{len(data.rarities)} rarities, {data.requests_made} requests"
    )
    typer.echo(f"Written to {target}")


def _render_build(result: BuildResult) -> str:
    """The build summary: rows per table, image association levels and warnings."""
    lines = [
        f"Built {result.path}: {sum(result.table_counts.values())} rows in "
        f"{len(result.table_counts)} tables"
    ]
    lines += [f"  {name}: {count}" for name, count in result.table_counts.items()]
    if result.image_levels:
        levels = ", ".join(f"{k} {v}" for k, v in result.image_levels.items())
        lines.append(f"Image association levels: {levels}")
    if result.warnings:
        lines.append(f"Warnings ({sum(result.warnings.values())}):")
        lines += [f"  {kind}: {count}" for kind, count in result.warnings.items()]
    else:
        lines.append("Warnings: none")
    return "\n".join(lines)


@app.command()
def build(
    ctx: typer.Context,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Database file to write (default: BSDB_DB_PATH)."),
    ] = None,
    built_at: Annotated[
        str | None,
        typer.Option(
            "--built-at",
            help="Fixed ISO 8601 build time, so two builds of the same data are byte-identical.",
        ),
    ] = None,
    data_version: Annotated[
        str,
        typer.Option("--data-version", help="Release tag of the data (schema_meta), e.g. v0.5.0."),
    ] = "dev",
) -> None:
    """Build the SQLite database from data/normalized and the glossary (replaces the file).

    Reads the normalized card pages and the glossary, writes a fresh database in one
    transaction and replaces the output atomically; on any error the old file stays.
    """
    settings = _settings(ctx)
    if built_at is not None:
        try:
            datetime.fromisoformat(built_at)
        except ValueError as exc:
            raise typer.BadParameter(f"not an ISO 8601 time: {built_at!r}") from exc
    try:
        result = build_from_directories(
            out or settings.db_path,
            settings.normalized_dir,
            settings.glossary_dir,
            cache_dir=settings.cache_dir,
            built_at=built_at,
            data_version=data_version,
        )
    except GlossaryError as exc:
        typer.echo(f"error: invalid glossary in {settings.glossary_dir}:\n{exc}", err=True)
        raise typer.Exit(1) from exc
    except BuildError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(_render_build(result))


_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
_DURATION = re.compile(r"(\d+)([smhdw])")


def parse_duration(text: str) -> timedelta:
    """``<int><unit>`` with units ``s m h d w`` (``30d``, ``12h``)."""
    match = _DURATION.fullmatch(text.strip().lower())
    if match is None:
        raise typer.BadParameter(f"expected <int><unit> with unit s, m, h, d or w, got {text!r}")
    return timedelta(seconds=int(match[1]) * _UNITS[match[2]])


def _build_http_client(settings: Settings) -> HttpClient:
    """The one place the real network client is built (tests replace it with a fake)."""
    return HttpClient(settings)


@app.command()
def scrape(
    ctx: typer.Context,
    sets: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help="Only sets whose Japanese product name contains this text (repeatable).",
        ),
    ] = None,
    refresh: Annotated[
        bool, typer.Option("--refresh", help="Fetch again every page this run visits.")
    ] = False,
    max_age: Annotated[
        str | None,
        typer.Option("--max-age", help="Fetch again cached pages older than this (30d, 12h)."),
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help="Take at most this many card pages.")
    ] = None,
    retry_failed: Annotated[
        bool,
        typer.Option(
            "--retry-failed",
            help="Give new attempts to pages that failed with a parse error (after a parser fix).",
        ),
    ] = False,
    offline: Annotated[
        bool,
        typer.Option(
            "--offline",
            help="Use the cache only: a page not in it is skipped, no request is ever made.",
        ),
    ] = False,
    reparse: Annotated[
        bool,
        typer.Option(
            "--reparse",
            help="Parse every parsed card page again from the cache (after a schema change). "
            "Combine with --offline to make no request.",
        ),
    ] = False,
) -> None:
    """Scrape card pages from batspi.com into data/parsed, resuming where the last run stopped."""
    settings = _settings(ctx)
    age = parse_duration(max_age) if max_age is not None else None
    client = _build_http_client(settings)
    fetcher = CachedFetcher(
        client, RawCache(settings.cache_dir), refresh=refresh, max_age=age, offline=offline
    )
    options = RunOptions(
        sets=tuple(sets or ()), limit=limit, retry_failed=retry_failed, reparse=reparse
    )
    with StateStore(settings.state_db_path) as store:
        report = run_pipeline(
            settings, fetcher, store, requests_made=lambda: client.requests_made, options=options
        )
    typer.echo(render(report))
    if report.exit_code:
        raise typer.Exit(report.exit_code)
