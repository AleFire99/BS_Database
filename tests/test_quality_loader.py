"""Loader warning kinds are mapped to quality severities (#122)."""

import re
from pathlib import Path

import bs_database.build
from bs_database.build.diagnostics import BuildWarnings
from bs_database.build.quality import LOADER_KINDS, Severity, loader_findings

BUILD_DIR = Path(bs_database.build.__file__).parent


def _used_kinds() -> set[str]:
    kinds: set[str] = set()
    for path in BUILD_DIR.glob("*.py"):
        kinds |= set(re.findall(r'warnings\.add\(\s*"([a-z_]+)"', path.read_text("utf-8")))
    return kinds


def test_every_loader_kind_is_mapped_and_none_is_stale() -> None:
    used = _used_kinds()
    assert len(used) >= 20
    assert used == set(LOADER_KINDS)


def test_closed_lookups_are_errors_and_conflicts_are_warnings() -> None:
    assert LOADER_KINDS["color_unmapped"][0] is Severity.ERROR
    assert LOADER_KINDS["symbol_unmapped"][0] is Severity.ERROR
    assert LOADER_KINDS["product_name_conflict"][0] is Severity.WARNING
    assert LOADER_KINDS["block_icon_conflict"][0] is Severity.INFO


def test_loader_findings_carry_counts_and_examples() -> None:
    warnings = BuildWarnings()
    warnings.add("level_duplicate", "A-1 Lv1")
    warnings.add("level_duplicate", "A-2 Lv1")
    warnings.add("symbol_merged", "A-1 神")
    by_id = {f.id: f for f in loader_findings(warnings)}
    assert by_id["level_duplicate"].count == 2
    assert by_id["level_duplicate"].severity is Severity.WARNING
    assert by_id["level_duplicate"].origin == "loader"
    assert by_id["level_duplicate"].examples == ("A-1 Lv1", "A-2 Lv1")
    assert by_id["symbol_merged"].severity is Severity.INFO


def test_an_unmapped_kind_is_a_warning() -> None:
    warnings = BuildWarnings()
    warnings.add("brand_new_kind")
    (finding,) = loader_findings(warnings)
    assert finding.severity is Severity.WARNING
