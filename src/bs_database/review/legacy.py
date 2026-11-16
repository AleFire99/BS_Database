"""Link Japanese families to legacy English family names by card number (#96).

Only cards with exactly one Japanese family and exactly one legacy family vote: there the
pairing is unambiguous. A candidate is *strong* with at least :data:`MIN_VOTES` votes and a
share of at least :data:`MIN_SHARE_PERCENT` of the votes of that Japanese family; otherwise
the link is *weak* and is shown with all its candidates.

Card numbers are joined exactly first. When that fails, both sides are compared through
:func:`number_key`; a normalized key shared by several legacy numbers is ambiguous and unused.
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

_PAREN_SUFFIX = re.compile(r"\s*[(（][^()（）]*[)）]\s*$")

MIN_VOTES = 2
MIN_SHARE_PERCENT = 80


def number_key(number: str) -> str:
    """Fallback join key: NFKC (full-width to ASCII), trimmed, trailing ``(A)`` suffix removed.

    ``" BS52-TX01(A) "`` and ``"BS52-TX01"`` give the same key.
    """
    text = unicodedata.normalize("NFKC", number).strip()
    return _PAREN_SUFFIX.sub("", text).strip()


@dataclass(frozen=True, slots=True)
class FamilyLink:
    """Votes for one Japanese family; ``candidates`` is sorted by votes, then name."""

    jp: str
    candidates: tuple[tuple[str, int], ...]

    @property
    def total(self) -> int:
        """All votes cast for this family."""
        return sum(n for _, n in self.candidates)

    @property
    def best(self) -> tuple[str, int]:
        """The leading candidate; a tie is broken by name, and is weak anyway."""
        return self.candidates[0]

    @property
    def strong(self) -> bool:
        """At least ``MIN_VOTES`` votes and ``MIN_SHARE_PERCENT`` % of the family's votes."""
        _, votes = self.best
        return votes >= MIN_VOTES and votes * 100 >= self.total * MIN_SHARE_PERCENT


@dataclass(frozen=True, slots=True)
class LinkResult:
    """Outcome of :func:`link_families`.

    ``no_legacy`` are the card numbers with a Japanese family that have no legacy family,
    even through the normalized key (the legacy join is an inner join on families).
    """

    links: Mapping[str, FamilyLink]
    no_legacy: tuple[str, ...]


def link_families(
    cards: Mapping[str, frozenset[str]], legacy: Mapping[str, tuple[str, ...]]
) -> LinkResult:
    """Vote legacy English names for Japanese families through shared card numbers."""
    by_key: dict[str, tuple[str, ...] | None] = {}
    for legacy_number, legacy_names in legacy.items():
        key = number_key(legacy_number)
        by_key[key] = None if key in by_key else legacy_names
    votes: dict[str, Counter[str]] = {}
    no_legacy: list[str] = []
    for number in sorted(cards):
        jps = cards[number]
        if not jps:
            continue
        names = legacy.get(number)
        if names is None:
            names = by_key.get(number_key(number))
        if names is None:
            no_legacy.append(number)
        elif len(jps) == 1 and len(names) == 1:
            (jp,) = jps
            votes.setdefault(jp, Counter())[names[0]] += 1
    links = {
        jp: FamilyLink(jp, tuple(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))))
        for jp, counter in sorted(votes.items())
    }
    return LinkResult(links, tuple(no_legacy))
