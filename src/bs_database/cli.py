"""Command-line interface for bs-database."""

from typing import Annotated

import typer

from bs_database import __version__

app = typer.Typer(no_args_is_help=True, help="bsdb: Battle Spirits card database tooling.")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"bsdb {__version__}")
        raise typer.Exit()


@app.callback()
def main(
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
