"""Build the SQLite database from the normalized data (#120, ADR 0011)."""

from bs_database.build.builder import (
    BuildQualityError,
    BuildResult,
    build_database,
    build_from_directories,
)
from bs_database.build.diagnostics import BuildError, BuildWarnings

__all__ = [
    "BuildError",
    "BuildQualityError",
    "BuildResult",
    "BuildWarnings",
    "build_database",
    "build_from_directories",
]
