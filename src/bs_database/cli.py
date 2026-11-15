"""Command-line interface for bs-database."""

import logging
import re
from datetime import timedelta
from pathlib import Path
from typing import Annotated

import typer

from bs_database import __version__
from bs_database.db import build_db
from bs_database.glossary import GlossaryError, load_glossary
from bs_database.ingest.cache import CachedFetcher, RawCache
from bs_database.ingest.http import HttpClient
from bs_database.ingest.pipeline import RunOptions, run_pipeline
from bs_database.ingest.report import render
from bs_database.ingest.state import StateStore
from bs_database.log import configure_logging
from bs_database.normalize.pipeline import normalize_tree
from bs_database.normalize.report import REPORT_MD, build_report, write_report
from bs_database.review.render import REVIEW_MD, write_review
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
) -> None:
    """Propose glossary rows from data/normalized and the legacy snapshot, for the owner.

    Writes review.md (families, keywords, no_split candidates, product-code prefixes, slug
    conflicts, legacy pairs) and ready-to-copy families.csv, keywords.csv and
    family_legacy_en.csv. Nothing under data/glossary is changed.
    """
    settings = _settings(ctx)
    try:
        load_glossary(settings.glossary_dir)
    except GlossaryError as exc:
        typer.echo(f"error: invalid glossary in {settings.glossary_dir}:\n{exc}", err=True)
        raise typer.Exit(1) from exc
    try:
        review = run_review(settings.normalized_dir, settings.glossary_dir, legacy_db)
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
    typer.echo(f"Written to {target / REVIEW_MD} and the CSV files next to it")


@app.command()
def build(
    ctx: typer.Context,
    input_dir: Annotated[
        Path,
        typer.Option("--input", help="Directory with the legacy normalized card JSON files."),
    ],
    db: Annotated[Path | None, typer.Option("--db", help="Database path.")] = None,
) -> None:
    """Build the SQLite database from card JSON files (appends to an existing DB)."""
    settings = _settings(ctx)
    target = db or settings.db_path
    build_db(input_dir, target)
    typer.echo(f"Built {target}")


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
) -> None:
    """Scrape card pages from batspi.com into data/parsed, resuming where the last run stopped."""
    settings = _settings(ctx)
    age = parse_duration(max_age) if max_age is not None else None
    client = _build_http_client(settings)
    fetcher = CachedFetcher(client, RawCache(settings.cache_dir), refresh=refresh, max_age=age)
    options = RunOptions(sets=tuple(sets or ()), limit=limit)
    with StateStore(settings.state_db_path) as store:
        report = run_pipeline(
            settings, fetcher, store, requests_made=lambda: client.requests_made, options=options
        )
    typer.echo(render(report))
    if report.exit_code:
        raise typer.Exit(report.exit_code)
