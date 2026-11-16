"""Pure parsers for fandom wiki wikitext: family, keyword and rarity names (ADR 0009, #104).

Input is untrusted wikitext; only the opening sentence is read, e.g.
``'''Machine Beast''' (''機獣; kijuu'')``. Pages that do not match return ``None`` and are listed
by the caller, never guessed.
"""

import re
import unicodedata
from dataclasses import dataclass

_BOLD_PAREN = re.compile(r"'''(?P<en>[^\n]+?)'''[^\S\n]*\((?P<body>[^)\n]*)\)")
_RUBY = re.compile(r"\{\{\s*ruby\s*\|\s*([^|}]*?)\s*(?:\|[^}]*)?\}\}", re.IGNORECASE)
_SEPARATOR = re.compile(r"[;；,，]")
_HEADING = re.compile(r"^=+[ \t]*(?P<title>.+?)[ \t]*=+[ \t]*$", re.MULTILINE)
_SMALL_LETTER = re.compile(r"small\s+[\"“”](?P<letter>[^\"“”]+)[\"“”]")


@dataclass(frozen=True)
class FandomName:
    jp: str
    en: str
    romaji: str | None
    title: str


@dataclass(frozen=True)
class FandomRarity:
    jp: str
    en: str
    letter: str | None


def jp_key(text: str) -> str:
    """Matching key: NFKC, every whitespace character removed."""
    return "".join(unicodedata.normalize("NFKC", text).split())


def _has_japanese(text: str) -> bool:
    return any(ord(ch) > 0x7F and ch.isalpha() for ch in text)


def _split_paren(body: str) -> tuple[str, str | None] | None:
    """``(jp, romaji)`` from the text inside the parentheses, or ``None`` without Japanese."""
    body = _RUBY.sub(r"\1", body).replace("''", "")
    parts = _SEPARATOR.split(body, maxsplit=1)
    first, rest = parts[0], (parts[1] if len(parts) > 1 else "")
    jp = " ".join(first.split())
    if not jp or not _has_japanese(jp):
        return None
    romaji = " ".join(rest.split()) or None
    return jp, romaji


def parse_name(title: str, wikitext: str) -> FandomName | None:
    """The name in the opening sentence of a family or keyword page."""
    match = _BOLD_PAREN.search(wikitext)
    if match is None:
        return None
    split = _split_paren(match["body"])
    if split is None:
        return None
    en = " ".join(match["en"].split())
    if not en:
        return None
    return FandomName(jp=split[0], en=en, romaji=split[1], title=title)


def parse_rarities(wikitext: str) -> list[FandomRarity]:
    """One entry per section that opens with ``'''Plural''' (JP)``; the heading is the EN name."""
    headings = list(_HEADING.finditer(wikitext))
    out: list[FandomRarity] = []
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(wikitext)
        body = wikitext[heading.end() : end]
        match = _BOLD_PAREN.search(body)
        if match is None:
            continue
        split = _split_paren(match["body"])
        if split is None:
            continue
        letter = _SMALL_LETTER.search(body)
        out.append(
            FandomRarity(
                jp=split[0],
                en=" ".join(heading["title"].split()),
                letter=letter["letter"].strip() if letter else None,
            )
        )
    return out
