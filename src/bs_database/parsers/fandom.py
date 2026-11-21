"""Pure parsers for fandom wiki wikitext: family, keyword and rarity names (ADR 0009, #104).

Input is untrusted wikitext; only the opening sentence is read, e.g.
``'''Machine Beast''' (''機獣; kijuu'')``. Pages that do not match return ``None`` and are listed
by the caller, never guessed.
"""

import re
import unicodedata
from dataclasses import dataclass

# ``en`` never spans another bold marker (``'''NZ''', short for '''Neo Zeon''' (…)`` gives
# ``Neo Zeon``), and an italic opening right after the bold (``'''X '''''(…)''``) is allowed.
_BOLD_PAREN = re.compile(
    r"'''(?P<en>(?:(?!''')[^\n])+?)'''[^\S\n]*(?:'')?[^\S\n]*[(（](?P<body>(?:[^()（）\n]|[(（][^()（）\n]*[)）])*)[)）]"
)
# ``{{Nihongo|'''English'''|日本語|Romaji}}``: the template name is not checked, only the shape.
_TEMPLATE = re.compile(
    r"\{\{[^|{}\n]+\|[^\S\n]*(?P<en>'''[^|{}\n]*?''')[^\S\n]*\|"
    r"(?P<jp>[^|}\n]*)(?:\|(?P<romaji>[^|}\n]*))?[^}\n]*\}\}"
)
_BOLD = re.compile(r"'''((?:(?!''')[^\n])+?)'''")
_HTML_RUBY = re.compile(r"<ruby>(.*?)<rt>.*?</rt>(?:<rp>.*?</rp>)*</ruby>", re.IGNORECASE)
_INNER_PAREN = re.compile(r"[(（][^)）]*[)）]?")
_DISAMBIGUATOR = re.compile(r"\s*\([^)]*\)\s*$")
_QUOTES = re.compile(r"'{2,}")
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
    body = _QUOTES.sub("", _RUBY.sub(r"\1", _HTML_RUBY.sub(r"\1", body)))
    parts = _SEPARATOR.split(body, maxsplit=2)
    first, rest = parts[0], (parts[1] if len(parts) > 1 else "")
    jp = " ".join(_INNER_PAREN.sub("", first).split())
    if not jp or not _has_japanese(jp):
        return None
    romaji = " ".join(rest.split()) or None
    return jp, romaji


def _template_en(arg: str, title: str) -> str:
    """English name from the bold part(s) of a template argument.

    Several bold parts (``'''TP''' (Trans-Phase) '''Armor'''``) are joined when the page title
    says the same, otherwise the title without its disambiguator is used.
    """
    bolds = [" ".join(b.split()) for b in _BOLD.findall(arg)]
    if len(bolds) <= 1:
        return bolds[0] if bolds else ""
    joined = " ".join(bolds)
    plain = _DISAMBIGUATOR.sub("", title)
    return joined if jp_key(joined) == jp_key(plain) else plain


def parse_name(title: str, wikitext: str) -> FandomName | None:
    """The name in the opening sentence of a family or keyword page."""
    paren = _BOLD_PAREN.search(wikitext)
    template = _TEMPLATE.search(wikitext)
    if template is not None and (paren is None or template.start() < paren.start()):
        split = _split_paren(f"{template['jp']};{template['romaji'] or ''}")
        en = _template_en(template["en"], title)
    elif paren is not None:
        split = _split_paren(paren["body"])
        en = " ".join(paren["en"].split())
    else:
        return None
    if split is None or not en:
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
