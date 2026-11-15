"""Link Japanese families to legacy English family names by card number (#96).

Only cards with exactly one Japanese family and exactly one legacy family vote: there the
pairing is unambiguous. A candidate is *strong* with at least :data:`MIN_VOTES` votes and a
share of at least :data:`MIN_SHARE_PERCENT` of the votes of that Japanese family; otherwise
the link is *weak* and is shown with all its candidates.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

MIN_VOTES = 2
MIN_SHARE_PERCENT = 80


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

    ``unmatched`` are the card numbers with a Japanese family that the legacy DB lacks.
    """

    links: Mapping[str, FamilyLink]
    unmatched: tuple[str, ...]


def link_families(
    cards: Mapping[str, frozenset[str]], legacy: Mapping[str, tuple[str, ...]]
) -> LinkResult:
    """Vote legacy English names for Japanese families through shared card numbers."""
    votes: dict[str, Counter[str]] = {}
    unmatched: list[str] = []
    for number in sorted(cards):
        jps = cards[number]
        if not jps:
            continue
        names = legacy.get(number)
        if names is None:
            unmatched.append(number)
        elif len(jps) == 1 and len(names) == 1:
            (jp,) = jps
            votes.setdefault(jp, Counter())[names[0]] += 1
    links = {
        jp: FamilyLink(jp, tuple(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))))
        for jp, counter in sorted(votes.items())
    }
    return LinkResult(links, tuple(unmatched))
