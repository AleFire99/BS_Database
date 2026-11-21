"""Group card number entries into cards (ADR 0004 amendment, #63, #120).

Several numbers share one card only when gameplay, text and flavor are identical. The key is a
hash of the canonical JSON of the fields listed in the ADR; English names, credits and images
are printing data and stay out of it.
"""

import hashlib
import json
from dataclasses import dataclass

from bs_database.build.diagnostics import BuildError
from bs_database.build.reader import Document, Json


@dataclass(frozen=True, slots=True)
class NumberEntry:
    """One card number entry and the document it comes from."""

    number: str
    document: Document
    entry: Json


@dataclass(frozen=True, slots=True)
class CardGroup:
    """The number entries that make up one card, sorted by number (the first one rules)."""

    key: str
    members: tuple[NumberEntry, ...]

    @property
    def first(self) -> NumberEntry:
        """The member with the smallest number: it supplies the non-key data (English, credits)."""
        return self.members[0]

    @property
    def numbers(self) -> tuple[str, ...]:
        """The numbers of the card, sorted."""
        return tuple(m.number for m in self.members)


def grouping_key(entry: Json) -> str:
    """SHA-256 of the canonical JSON of the identity fields of ``entry`` (ADR 0004 amendment)."""
    gameplay = dict(entry["gameplay"])
    gameplay["families"] = [f["jp"] for f in gameplay["families"]]
    text = entry["text"] or {}
    effects = [
        {k: e[k] for k in ("position", "levels", "header_jp", "text_jp")}
        for e in text.get("effects", [])
    ]
    identity = {
        "name_jp": entry["name_jp"],
        "gameplay": gameplay,
        "effects": effects,
        "conditions": [
            text.get("fusion_conditions_jp"),
            text.get("summon_condition_jp"),
            text.get("overclock_condition_jp"),
        ],
        "flavor": [text.get("flavor_jp"), text.get("flavor_note_jp")],
    }
    canonical = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def group_entries(documents: list[Document]) -> list[CardGroup]:
    """Cards in the order of their first number; independent of the order of ``documents``."""
    by_key: dict[str, list[NumberEntry]] = {}
    for doc in documents:
        for entry in doc.entries:
            by_key.setdefault(grouping_key(entry), []).append(
                NumberEntry(entry["number"], doc, entry)
            )
    groups = []
    for key, members in by_key.items():
        ordered = tuple(sorted(members, key=lambda m: m.number))
        if len({m.entry["name_jp"] for m in ordered}) != 1:  # ADR 0004: a key bug must not merge
            raise BuildError(f"merged entries with different names: {[m.number for m in ordered]}")
        groups.append(CardGroup(key, ordered))
    return sorted(groups, key=lambda g: g.first.number)
