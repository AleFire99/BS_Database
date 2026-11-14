"""Command-line interface for bs-database."""

import logging
from pathlib import Path
from typing import Annotated

import typer

from bs_database import __version__
from bs_database.db import build_db
from bs_database.log import configure_logging
from bs_database.normalize import normalize_tree
from bs_database.scrapers.batspi_card import scrape_card_data
from bs_database.scrapers.batspi_links import extract_links
from bs_database.scrapers.batspi_sets import extract_set_urls
from bs_database.settings import Settings

logger = logging.getLogger(__name__)

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
def scrape(
    ctx: typer.Context,
    refresh_urls: Annotated[
        bool, typer.Option("--refresh-urls", help="Re-extract the set URL list first.")
    ] = False,
    sets: Annotated[
        list[str] | None,
        typer.Option("--set", help="Only scrape cards of this set (e.g. BS01); repeatable."),
    ] = None,
) -> None:
    """Scrape card pages from batspi.com into card JSON files."""
    settings = _settings(ctx)
    urls_path = settings.extracted_urls_path
    if refresh_urls:
        extract_set_urls(settings.batspi_url + "index.php?カードリスト", urls_path)
    if not urls_path.is_file():
        typer.echo(f"Error: {urls_path} not found (run with --refresh-urls)", err=True)
        raise typer.Exit(1)
    prefixes = tuple(s.upper() for s in sets or [])
    for line in urls_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        url = settings.batspi_url + line
        logger.info("Processing URL: %s", url)
        links = extract_links(url, settings.batspi_url)
        if not links:
            logger.info("No links found for %s", url)
        for card_id, link in links:
            if prefixes and not card_id.startswith(prefixes):
                continue
            scrape_card_data(
                card_id, link, str(settings.json_dir), image_root=str(settings.images_dir)
            )
