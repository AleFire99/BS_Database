"""Effect blocks, side conditions, credits and flavour of a batspi card block (#71).

Pure functions over the lines of a card ``<pre>`` (after the type, cost and level
lines). Facts are kept as printed; deriving effect kinds is the loader's job (#12).
"""

import logging
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from bs_database.parsers.card_models import Effect, Keyword
from bs_database.parsers.errors import ParseError

log = logging.getLogger(__name__)

_BRACKET = r"【[^】]*】|《[^》]*》"
_HEADER_RE = re.compile(
    rf"^(?P<pre>(?:{_BRACKET})*)(?P<lv>Lv\d+(?:[・･]Lv\d+)*)?：?"
    rf"(?P<label>(?:メイン|フラッシュ))?：?(?P<post>(?:{_BRACKET})*)"
    r"(?P<param>〔[^〕]*〕)?(?P<timing>『[^』]*』)?$"
)
_BRACKET_RE = re.compile(rf"({_BRACKET})")
_LEVEL_SCOPE_RE = re.compile(r"Lv(\d+)")
_LEVEL_LIKE_RE = re.compile(r"^Lv\d+(?:[・･：『【《]|$)")
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
        name, _, parameter = token[1:-1].partition("：")
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
                _keywords(match.group("pre") + match.group("post")),
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
