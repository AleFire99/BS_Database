"""Command-line interface for bs-database."""

import logging
from pathlib import Path
from typing import Annotated

import typer

from bs_database import __version__
from bs_database.db import build_db
from bs_database.log import configure_logging
from bs_database.normalize import normalize_tree
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


def _card_json_dir(settings: Settings) -> Path:
    return settings.json_dir / "card_json"


@app.command()
def normalize(ctx: typer.Context) -> None:
    """Normalize family names and types in the card JSON files, in place."""
    settings = _settings(ctx)
    written = normalize_tree(_card_json_dir(settings), settings.family_mapping_path)
    typer.echo(f"Normalized {written} files")


@app.command()
def build(
    ctx: typer.Context,
    db: Annotated[Path | None, typer.Option("--db", help="Database path.")] = None,
) -> None:
    """Build the SQLite database from the card JSON files (appends to an existing DB)."""
    settings = _settings(ctx)
    target = db or settings.db_path
    build_db(_card_json_dir(settings), target)
    typer.echo(f"Built {target}")


@app.command()
def scrape() -> None:
    """Scrape card pages from batspi.com (being rewritten, see #10)."""
    typer.echo(
        "bsdb scrape is being rewritten (#10); the legacy scraper was removed because it "
        "did not follow the scraping policy.",
        err=True,
    )
    raise typer.Exit(1)
