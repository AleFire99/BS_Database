"""Build the SQLite database from the normalized data (#120, ADR 0011)."""

from bs_database.build.builder import BuildResult, build_database
from bs_database.build.diagnostics import BuildError, BuildWarnings

__all__ = ["BuildError", "BuildResult", "BuildWarnings", "build_database"]
