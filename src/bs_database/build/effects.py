"""Effects, their keywords and their levels (#120).

The effect kind is derived from the normalized block (rule table in docs/architecture/build.md).
"""

import sqlite3

from bs_database.build.cards import CardIds
from bs_database.build.diagnostics import BuildWarnings
from bs_database.build.grouping import CardGroup
from bs_database.build.lookups import STATUS_PENDING, Lookups
from bs_database.build.reader import Json

LABEL_KINDS = {"メイン": "main", "フラッシュ": "flash"}
SET_ACTIVE_PREFIX = "【セット中】"


def effect_kind(effect: Json) -> str:
    """The ``effect_kinds`` code of one effect block."""
    if effect["form"] == "keyword_line":
        return "keyword_block"
    if effect["label"] in LABEL_KINDS:
        return LABEL_KINDS[effect["label"]]
    if (effect["header_jp"] or "").startswith(SET_ACTIVE_PREFIX):
        return "set_active"
    if effect["form"] == "header" and effect["levels"]:
        return "level" if effect["timing_jp"] else "constant"
    return "other"


def load_effects(
    conn: sqlite3.Connection,
    lookups: Lookups,
    warnings: BuildWarnings,
    groups: list[CardGroup],
    cards: CardIds,
) -> None:
    """Insert ``card_effects``, ``card_effect_keywords`` and ``card_effect_levels``."""
    effects: list[tuple[object, ...]] = []
    keywords: list[tuple[int, int, str | None]] = []
    levels: list[tuple[int, int]] = []
    for group in groups:
        text = group.first.entry["text"]
        if text is None:
            continue
        card_id = cards.by_group[group.key]
        positions: set[int] = set()
        for effect in text["effects"]:
            where = f"{group.first.number} #{effect['position']}"
            if effect["position"] < 1 or effect["position"] in positions:
                warnings.add("effect_position_invalid", where)
                continue
            positions.add(effect["position"])
            effect_id = len(effects) + 1
            effects.append(
                (
                    effect_id,
                    card_id,
                    effect["position"],
                    lookups.effect_kinds[effect_kind(effect)],
                    effect["timing_jp"],
                    None,
                    effect["text_jp"],
                    effect["text_en"],
                    lookups.source_id(effect["en_source"]),
                    lookups.status_id(effect["en_status"] or STATUS_PENDING),
                )
            )
            seen: set[int] = set()
            for keyword in effect["keywords"]:
                if keyword["code"] is None:
                    warnings.add("keyword_unmapped", f"{where} {keyword['name_jp']}")
                    continue
                keyword_id = lookups.keywords[keyword["code"]]
                if keyword_id in seen:
                    warnings.add("keyword_duplicate", f"{where} {keyword['name_jp']}")
                    continue
                seen.add(keyword_id)
                keywords.append((effect_id, keyword_id, keyword["parameter_jp"]))
            for level in sorted(set(effect["levels"])):
                level_id = cards.level_ids.get((card_id, level))
                if level_id is None:
                    warnings.add("effect_level_missing", f"{where} Lv{level}")
                    continue
                levels.append((effect_id, level_id))
    conn.executemany(
        "INSERT INTO card_effects (id, card_id, position, effect_kind_id, timing_jp, timing_en,"
        " text_jp, text_en, en_source_id, en_status_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        effects,
    )
    conn.executemany(
        "INSERT INTO card_effect_keywords (card_effect_id, keyword_id, parameter_jp)"
        " VALUES (?, ?, ?)",
        keywords,
    )
    conn.executemany(
        "INSERT INTO card_effect_levels (card_effect_id, card_level_id) VALUES (?, ?)", levels
    )
