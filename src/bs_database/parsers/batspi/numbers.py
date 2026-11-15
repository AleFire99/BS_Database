"""Recognise batspi.com card number schemes (#69)."""

import re

from bs_database.parsers.models import ParsedNumber

_FAM = r"(?:\d{2}R)?(?:BSCO|BSC|BSH|BS|SD|CB|LM|PB|PX|RPX|RP|CP|EXG|EX|P|X|SJ|KA|KF|GX)"
_KIND = r"(?:10thX|RVXX|EXG|TCP|CP|RV|XX|AX|CX|TX|SP|DD|X|U|G|D|H|)"
_TAIL = r"(?P<variant>[A-Z])?(?P<face>\([AB]\))?$"
_A = re.compile(rf"^(?P<fam>{_FAM})(?P<sn>\d*)-(?P<kind>{_KIND})(?P<seq>\d+){_TAIL}")
_B = re.compile(rf"^(?P<fam>P|PX|X|EX)(?P<seq>\d+){_TAIL}")


_THREE_DIGITS = {"BS", "SD", "CB", "BSC"}  # plain and RV cards: BS01-001
_TWO_OR_THREE = {"PB", "EXG", "KA", "KF", "BSCO", "BSH", "SJ", "GX", "EX", "X"}  # variable width


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
    if m and len(m["seq"]) == (2 if m["fam"] == "PX" else 3):
        return ParsedNumber(m["fam"], None, "", m["seq"], m["variant"], m["face"])
    return None
