"""Effect blocks, side conditions, credits and flavour of a batspi card block (#71).

Pure functions over the lines of a card ``<pre>`` (after the type, cost and level
lines). Facts are kept as printed; deriving effect kinds is the loader's job (#12).
"""

import logging
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from bs_database.parsers.card_models import CardText, Credit, Effect, Keyword, RoleCredit
from bs_database.parsers.errors import ParseError

log = logging.getLogger(__name__)

_BRACKET = r"【[^】]*】|《[^》]*》"
_HEADER_RE = re.compile(
    rf"^(?P<pre>(?:{_BRACKET})*)(?P<lv>Lv\d+(?:[・･]Lv\d+)*)?\s*[：:]?\s*"
    rf"(?P<label>(?:メイン|フラッシュ))?[：:]?(?P<post>(?:{_BRACKET})*)"
    r"(?P<param>〔[^〕]*〕)?(?P<timing>『[^』]*』)?"
    rf"(?P<post2>(?:{_BRACKET})*)(?P<param2>〔[^〕]*〕)?$"
)
_PARAM_SEP_RE = re.compile("[：:]")
_BRACKET_RE = re.compile(rf"({_BRACKET})")
_LEVEL_SCOPE_RE = re.compile(r"Lv(\d+)")
_LEVEL_LIKE_RE = re.compile(r"^Lv\d+(?:[・･：『【《]|$)")
_SYMBOL_PREFIX = "シンボル："
_FLAVOR_PREFIX = "フレーバーテキスト："
_ILLUSTRATOR = "イラスト"
_CONCEPT = "コンセプト"
_OTHER_ROLES = ("プロデュース", "ペイント", "書", "写真", "コラボレート")
_CREDIT_RE = re.compile(rf"^(?P<role>{'|'.join((_ILLUSTRATOR, _CONCEPT, *_OTHER_ROLES))})[：:]")
_TRAILER_RE = re.compile(rf"^(?:{_SYMBOL_PREFIX}|{_FLAVOR_PREFIX}|(?:{_CREDIT_RE.pattern[1:]}))")
_PAIRS = {")": "(", "）": "（"}
_SIDE_RE = re.compile(r"^(?:(?:右|左)?合体条件：|OC条件：|【召喚条件：.*】$)")


@dataclass(slots=True)
class _Block:
    """An effect block being collected."""

    form: str
    levels: tuple[int, ...]
    label: str | None
    keywords: tuple[Keyword, ...]
    timing: str | None
    header: str | None
    lines: list[str] = field(default_factory=list)

    def to_effect(self, position: int) -> Effect:
        return Effect(
            position,
            self.form,
            self.levels,
            self.label,
            self.keywords,
            self.timing,
            self.header,
            "\n".join(self.lines),
        )


def _keywords(text: str) -> tuple[Keyword, ...]:
    keywords: list[Keyword] = []
    for token in _BRACKET_RE.findall(text):
        # Name and parameter split on a full-width or ASCII colon; a 《…》 keyword nested
        # in 【…】 keeps no inner brackets (【《バースト封印》：…】, #109).
        parts = _PARAM_SEP_RE.split(token[1:-1], maxsplit=1)
        name, parameter = parts[0], (parts[1] if len(parts) > 1 else None)
        if token[0] == "【" and name.startswith("《") and name.endswith("》"):
            name = name[1:-1]
        keywords.append(Keyword(token[0], name, parameter or None))
    return tuple(keywords)


def parse_body(
    lines: Sequence[str], levels: Collection[int] = (), context: str = ""
) -> tuple[tuple[Effect, ...], tuple[str, ...], str | None, str | None]:
    """Return ``(effects, fusion_conditions, summon_condition, overclock_condition)``.

    ``lines`` are the effect lines of one card block, before the trailer. ``levels``
    are the level numbers of the card, used to warn about effects scoped elsewhere;
    ``context`` (card number and URL) goes into log and error messages.
    """
    effects: list[Effect] = []
    fusion: list[str] = []
    summon: str | None = None
    overclock: str | None = None
    pending: _Block | None = None

    def close() -> None:
        nonlocal pending
        if pending is not None:
            effects.append(pending.to_effect(len(effects) + 1))
            pending = None

    for raw in lines:
        line = raw.rstrip()
        if not line:
            continue
        if _SIDE_RE.match(line):
            close()
            if "合体条件：" in line:
                fusion.append(line)
            elif line.startswith("OC条件："):
                overclock = line
            else:
                summon = line
            continue
        match = _HEADER_RE.match(line)
        if match is None and _LEVEL_LIKE_RE.match(line):
            raise ParseError(f"malformed effect header {line!r} in {context}")
        if match is not None and any(
            match.group(g) for g in ("pre", "lv", "label", "post", "timing")
        ):
            close()
            scope = tuple(int(n) for n in _LEVEL_SCOPE_RE.findall(match.group("lv") or ""))
            if any(n not in levels for n in scope):
                log.warning(
                    "effect scope not in card levels: %s field=levels scope=%s levels=%s",
                    context,
                    scope,
                    sorted(levels),
                )
            standalone = not (match.group("lv") or match.group("label") or match.group("timing"))
            pending = _Block(
                "keyword_line" if standalone else "header",
                scope,
                match.group("label"),
                _keywords(match.group("pre") + match.group("post") + match.group("post2")),
                match.group("timing"),
                line,
            )
            if standalone:
                pending.lines.append(line)
                close()
        else:
            if pending is None:
                pending = _Block("plain", (), None, (), None, None)
            pending.lines.append(line)
    close()
    return tuple(effects), tuple(fusion), summon, overclock


def split_trailer(lines: Sequence[str]) -> tuple[Sequence[str], Sequence[str]]:
    """Split card lines into the effect body and the trailer (symbols, credits, flavour)."""
    for index, line in enumerate(lines):
        if _TRAILER_RE.match(line):
            return lines[:index], lines[index:]
    return lines, ()


def split_note(text: str) -> tuple[str, str | None]:
    """Split ``name(note)`` into ``(name, note)``; the note is a trailing balanced group."""
    text = text.strip()
    if not text or text[-1] not in _PAIRS:
        return text, None
    close, opener = text[-1], _PAIRS[text[-1]]
    depth = 0
    for index in range(len(text) - 1, -1, -1):
        if text[index] == close:
            depth += 1
        elif text[index] == opener:
            depth -= 1
            if depth == 0:
                return text[:index].strip(), text[index + 1 : -1].strip()
    return text, None


def _credit(text: str, kind: str, context: str) -> Credit:
    name, note = split_note(text)
    if not name:
        raise ParseError(f"empty {kind} name in {context}")
    return Credit(name, note)


def parse_trailer(
    lines: Sequence[str], context: str = ""
) -> tuple[tuple[Credit, ...], tuple[Credit, ...], str | None, str | None, tuple[RoleCredit, ...]]:
    """Return ``(illustrators, concepts, flavor, flavor_note, other_credits)`` from the trailer.

    The ``シンボル：`` line is read elsewhere (#70) and skipped. Credit labels take a full-width
    or ASCII colon. An ``イラスト：`` with nothing after it gives no credit, with a warning. The
    flavour runs to the end of the block with its source line breaks; any other non-blank line
    is an error.
    """
    illustrators: list[Credit] = []
    concepts: list[Credit] = []
    others: list[RoleCredit] = []
    flavor: str | None = None
    note: str | None = None
    for index, raw in enumerate(lines):
        line = raw.rstrip()
        if not line or line.startswith(_SYMBOL_PREFIX):
            continue
        credit = _CREDIT_RE.match(line)
        if credit is not None:
            role, text = credit.group("role"), line[credit.end() :]
            if role == _ILLUSTRATOR and not text.strip():
                log.warning("empty illustrator ignored: %s field=illustrators", context)
            elif role == _ILLUSTRATOR:
                illustrators.append(_credit(text, "illustrator", context))
            elif role == _CONCEPT:
                concepts.append(_credit(text, "concept", context))
            else:
                found = _credit(text, role, context)
                others.append(RoleCredit(role, found.name, found.note))
        elif line.startswith(_FLAVOR_PREFIX):
            head = line[len(_FLAVOR_PREFIX) :].strip()
            outer, inner = split_note(head)
            note = inner if inner is not None and not outer else (head or None)
            rest = [x.rstrip() for x in lines[index + 1 :]]
            flavor = "\n".join(rest).strip("\n") or None
            break
        else:
            raise ParseError(f"unexpected trailer line {line!r} in {context}")
    return tuple(illustrators), tuple(concepts), flavor, note, tuple(others)


def parse_card_text(lines: Sequence[str], levels: Collection[int], context: str) -> CardText:
    """Parse the lines after the level line (or cost line for Magic) into a CardText."""
    body, trailer = split_trailer(lines)
    effects, fusion, summon, overclock = parse_body(body, levels, context)
    illustrators, concepts, flavor, note, others = parse_trailer(trailer, context)
    return CardText(
        effects, fusion, summon, overclock, illustrators, concepts, flavor, note, others
    )
