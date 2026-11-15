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
from bs_database.settings import Settings

app = typer.Typer(no_args_is_help=True, help="bsdb: Battle Spirits card database tooling.")


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
def normalize(ctx: typer.Context) -> None:
    """Normalize data/parsed into data/normalized: codes from the glossary, non-destructive."""
    settings = _settings(ctx)
    if not settings.parsed_dir.is_dir():
        typer.echo(f"error: parsed directory not found: {settings.parsed_dir}", err=True)
        raise typer.Exit(1)
    try:
        glossary = load_glossary(settings.glossary_dir)
    except GlossaryError as exc:
        typer.echo(f"error: invalid glossary in {settings.glossary_dir}:\n{exc}", err=True)
        raise typer.Exit(1) from exc
    result = normalize_tree(settings.parsed_dir, settings.normalized_dir, glossary)
    typer.echo(
        f"Normalized {result.written} pages, {len(result.unmapped)} unmapped terms "
        f"({result.closed} closed)"
    )
    if result.failed:
        typer.echo(f"{len(result.failed)} pages failed", err=True)
        raise typer.Exit(1)


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
