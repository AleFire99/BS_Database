"""Recognise batspi.com card number schemes (#69)."""

import re

from bs_database.parsers.models import ParsedNumber

_FAM = r"(?:\d{2}R)?(?:BSCO|BSC|BSH|BS|SD|CB|LM|PB|PX|RPX|RP|CP|EXG|EX|P|X|SJ|KA|KF|GX)"
_KIND = r"(?:10thX|RVXX|EXG|TCP|CP|RV|XX|AX|CX|TX|SP|DD|X|U|G|D|H|)"
_TAIL = r"(?P<variant>[A-Z])?(?P<face>\([AB]\))?$"
_A = re.compile(rf"^(?P<fam>{_FAM})(?P<sn>\d*)-(?P<kind>{_KIND})(?P<seq>\d+){_TAIL}")
_B = re.compile(rf"^(?P<fam>P|PX|X|EX)(?P<seq>\d+){_TAIL}")


def parse_number(raw: str) -> ParsedNumber | None:
    """Split a card number into its parts, or return None if no scheme matches."""
    m = _A.match(raw)
    if m:
        fam, sn = m["fam"], m["sn"]
        series = fam + sn if sn else None
        return ParsedNumber(fam, series, m["kind"], m["seq"], m["variant"], m["face"])
    m = _B.match(raw)
    if m:
        return ParsedNumber(m["fam"], None, "", m["seq"], m["variant"], m["face"])
    return None
