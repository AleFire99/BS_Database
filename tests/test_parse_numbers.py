"""Card number scheme recognition."""

import pytest

from bs_database.parsers.batspi.numbers import parse_number
from bs_database.parsers.models import ParsedNumber

# raw, family, series, kind, variant, face
CASES = [
    ("BS01-001", "BS", "BS01", "", None, None),
    ("BS01-X01", "BS", "BS01", "X", None, None),
    ("BS31-XX02", "BS", "BS31", "XX", None, None),
    ("BS52-CP14", "BS", "BS52", "CP", None, None),
    ("BS38-RV022", "BS", "BS38", "RV", None, None),
    ("BS72-AX03", "BS", "BS72", "AX", None, None),
    ("BS52-TX01", "BS", "BS52", "TX", None, None),
    ("BS73-TCP01(A)", "BS", "BS73", "TCP", None, "(A)"),
    ("BS73-TCP01(B)", "BS", "BS73", "TCP", None, "(B)"),
    ("SD29-001", "SD", "SD29", "", None, None),
    ("SD19-X01", "SD", "SD19", "X", None, None),
    ("SD67-CP01", "SD", "SD67", "CP", None, None),
    ("SD43-RV001", "SD", "SD43", "RV", None, None),
    ("BSC22-001", "BSC", "BSC22", "", None, None),
    ("CB34-001", "CB", "CB34", "", None, None),
    ("CB17-X06", "CB", "CB17", "X", None, None),
    ("CB34-CX01", "CB", "CB34", "CX", None, None),
    ("CB34-XX01", "CB", "CB34", "XX", None, None),
    ("LM18-01", "LM", "LM18", "", None, None),
    ("LM18-U01", "LM", "LM18", "U", None, None),
    ("P001", "P", None, "", None, None),
    ("P25-06", "P", "P25", "", None, None),
    ("P20-19", "P", "P20", "", None, None),
    ("P14-X01", "P", "P14", "X", None, None),
    ("P21-G01", "P", "P21", "G", None, None),
    ("26RBS02-CP01", "26RBS", "26RBS02", "CP", None, None),
    ("26RSD01-013", "26RSD", "26RSD01", "", None, None),
    ("BS44-10thX01", "BS", "BS44", "10thX", None, None),
    ("PB46-RVXX01", "PB", "PB46", "RVXX", None, None),
    ("P17-EXG01", "P", "P17", "EXG", None, None),
    ("BS48-SP01", "BS", "BS48", "SP", None, None),
    ("X001", "X", None, "", None, None),
    ("X003A", "X", None, "", "A", None),
    ("EX001", "EX", None, "", None, None),
    ("PX01", "PX", None, "", None, None),
    ("RP26-01", "RP", "RP26", "", None, None),
    ("RPX26-01", "RPX", "RPX26", "", None, None),
    ("CP14-X01R", "CP", "CP14", "X", "R", None),
    ("P16-09R", "P", "P16", "", "R", None),
    ("PB20-D01", "PB", "PB20", "D", None, None),
    ("PB20-DD01", "PB", "PB20", "DD", None, None),
    ("PB20-H01", "PB", "PB20", "H", None, None),
    ("KA12-01", "KA", "KA12", "", None, None),
    ("KF-01", "KF", None, "", None, None),
    ("BSCO-001", "BSCO", None, "", None, None),
    ("BSH-001", "BSH", None, "", None, None),
    ("EXG2-001", "EXG", "EXG2", "", None, None),
    # #108: schemes seen on the full scrape (one or two real numbers each)
    ("PC01-001", "PC", "PC01", "", None, None),
    ("PC02-002", "PC", "PC02", "", None, None),
    ("PC01-X01", "PC", "PC01", "X", None, None),
    ("PC01-RV001", "PC", "PC01", "RV", None, None),
    ("PC01-CP01", "PC", "PC01", "CP", None, None),
    ("PC02-CX01", "PC", "PC02", "CX", None, None),
    ("CBX01-001", "CBX", "CBX01", "", None, None),
    ("CBX01-X01", "CBX", "CBX01", "X", None, None),
    ("CBX01-CX01", "CBX", "CBX01", "CX", None, None),
    ("BSC35-A001", "BSC", "BSC35", "A", None, None),
    ("BSC35-XA01", "BSC", "BSC35", "XA", None, None),
    ("BSC35-XXA01", "BSC", "BSC35", "XXA", None, None),
    ("BSC47-RVTX01", "BSC", "BSC47", "RVTX", None, None),
    ("BSC45-XV01", "BSC", "BSC45", "XV", None, None),
    ("BS64-XV01", "BS", "BS64", "XV", None, None),
    ("BS68-NX01", "BS", "BS68", "NX", None, None),
    ("BS73-T001", "BS", "BS73", "T", None, None),
    ("SD69-T001", "SD", "SD69", "T", None, None),
    ("BS38-RV X01", "BS", "BS38", "RV X", None, None),
    ("PB17-RV X01", "PB", "PB17", "RV X", None, None),
    ("SD41-RV X01", "SD", "SD41", "RV X", None, None),
    ("BSC37-RV X01", "BSC", "BSC37", "RV X", None, None),
    ("EXGB-01", "EXGB", None, "", None, None),
    ("EXGM-01", "EXGM", None, "", None, None),
    ("EXGN-01", "EXGN", None, "", None, None),
    ("GX01", "GX", None, "", None, None),
    ("GX12-01", "GX", "GX12", "", None, None),
]


@pytest.mark.parametrize(("raw", "family", "series", "kind", "variant", "face"), CASES)
def test_known_numbers(
    raw: str, family: str, series: str | None, kind: str, variant: str | None, face: str | None
) -> None:
    parsed = parse_number(raw)
    assert parsed is not None
    assert (parsed.family, parsed.series, parsed.kind, parsed.variant, parsed.face) == (
        family,
        series,
        kind,
        variant,
        face,
    )
    assert parsed.seq.isdigit()


def test_seq_kept_as_text() -> None:
    assert parse_number("BS01-001") == ParsedNumber("BS", "BS01", "", "001", None, None)


@pytest.mark.parametrize("raw", ["", "BS01-", "ZZ01-001", "BS01-001(C)", "BS59", "XX00"])
def test_unknown_numbers(raw: str) -> None:
    assert parse_number(raw) is None


@pytest.mark.parametrize(
    "raw",
    [
        "BS1-001",
        "BS01-0",
        "BS01-01",
        "BS01-X1",
        "BS01-X001",
        "BS123-001",
        "P25-6",
        "PX1",
        "P01",
        "BSC35-A01",
        "BS73-T01",
        "BS38-RV X001",
        "PC01-01",
        "GX001",
        "GX1",
    ],
)
def test_wrong_digit_counts(raw: str) -> None:
    assert parse_number(raw) is None
