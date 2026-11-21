"""Recognise batspi.com card number schemes (#69)."""

import re

from bs_database.parsers.models import ParsedNumber

_FAM = (
    r"(?:\d{2}R)?(?:BSCO|BSC|BSH|BS|SD|CBX|CB|LM|PB|PC|PX|RPX|RP|CP|EXGB|EXGM|EXGN|EXG|EX"
    r"|P|X|SJ|KA|KF|GX)"
)
# ``RV X`` (with the blank) is how the pages print the X cards of a reprint series (#108).
_KIND = r"(?:10thX|RVXX|RVTX|RV X|XXA|EXG|TCP|CP|RV|XX|XA|XV|NX|AX|CX|TX|SP|DD|X|U|G|D|H|A|T|)"
_TAIL = r"(?P<variant>[A-Z])?(?P<face>\([AB]\))?$"
_A = re.compile(rf"^(?P<fam>{_FAM})(?P<sn>\d*)-(?P<kind>{_KIND})(?P<seq>\d+){_TAIL}")
_B = re.compile(rf"^(?P<fam>P|PX|GX|X|EX)(?P<seq>\d+){_TAIL}")


_THREE_DIGITS = {"BS", "SD", "CB", "BSC", "PC", "CBX"}  # plain and RV cards: BS01-001
_TWO_OR_THREE = {  # variable width
    "PB",
    "EXG",
    "EXGB",
    "EXGM",
    "EXGN",
    "KA",
    "KF",
    "BSCO",
    "BSH",
    "SJ",
    "GX",
    "EX",
    "X",
}
_THREE_DIGIT_KINDS = {"A", "T"}  # BSC35-A001, BS73-T001: three digits though not plain


def _widths_ok(fam: str, sn: str, kind: str, seq: str) -> bool:
    """Digit counts seen on batspi.com: 2-digit series, 2-digit seq (3 for plain cards)."""
    if len(sn) not in ((0, 1, 2) if fam == "EXG" else (0, 2)):
        return False
    base = fam.removeprefix("26R")
    plain = kind in ("", "RV")
    if plain and base in _THREE_DIGITS:
        return len(seq) == 3
    if plain and base in _TWO_OR_THREE:
        return len(seq) in (2, 3)
    if kind in _THREE_DIGIT_KINDS:
        return len(seq) == 3
    return len(seq) == 2


def parse_number(raw: str) -> ParsedNumber | None:
    """Split a card number into its parts, or return None if no scheme matches."""
    m = _A.match(raw)
    if m:
        fam, sn = m["fam"], m["sn"]
        if not _widths_ok(fam, sn, m["kind"], m["seq"]):
            return None
        series = fam + sn if sn else None
        return ParsedNumber(fam, series, m["kind"], m["seq"], m["variant"], m["face"])
    m = _B.match(raw)
    if m and len(m["seq"]) == (2 if m["fam"] in ("PX", "GX") else 3):
        return ParsedNumber(m["fam"], None, "", m["seq"], m["variant"], m["face"])
    return None
