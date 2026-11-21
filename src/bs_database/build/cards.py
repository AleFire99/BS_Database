"""Cards, numbers, gameplay attributes, credits and the brave/ultimate details (#120)."""

import sqlite3
from dataclasses import dataclass, field

from bs_database.build.diagnostics import BuildError, BuildWarnings
from bs_database.build.grouping import CardGroup
from bs_database.build.lookups import STATUS_PENDING, Lookups
from bs_database.build.reader import Json

CONCEPT_ROLE = "コンセプト"
JOIN = "・"
STATUS_FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CardIds:
    """Ids assigned to cards, numbers and levels; later steps link their rows through them."""

    by_group: dict[str, int]  # grouping key -> cards.id
    by_number: dict[str, int]  # card number -> cards.id
    number_ids: dict[str, int]  # card number -> card_numbers.id
    level_ids: dict[tuple[int, int], int]  # (cards.id, level) -> card_levels.id


def _block_icon(
    group: CardGroup, printings: dict[str, list[Json]], warnings: BuildWarnings
) -> str | None:
    """Icon of the first printing that has one (numbers sorted, page order); conflicts counted."""
    icons = [
        p["block_icon"]
        for number in group.numbers
        for p in printings.get(number, ())
        if p["block_icon"]
    ]
    if len(set(icons)) > 1:
        warnings.add("block_icon_conflict", group.first.number)
    return icons[0] if icons else None


def _english(entry: Json, text: Json | None) -> tuple[str | None, str | None, str | None, str]:
    """``(name_en, flavor_en, source code, status code)``: one pair covers both (ADR 0005)."""
    pairs = [(entry["name_en"], entry["en_source"], entry["en_status"])]
    if text is not None:
        pairs.append((text["flavor_en"], text["en_source"], text["en_status"]))
    chosen = next(((s, st) for value, s, st in pairs if value), None)
    if chosen is None:
        failed = any(st == STATUS_FAILED for _, _, st in pairs)
        chosen = (None, STATUS_FAILED if failed else STATUS_PENDING)
    return entry["name_en"], text["flavor_en"] if text else None, chosen[0], chosen[1]


@dataclass(slots=True)
class _Symbol:
    count: int = 0
    variants: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)


def _merge_symbols(
    records: list[Json], ids: dict[str, int], warnings: BuildWarnings, number: str
) -> dict[int, tuple[int, str | None, str | None]]:
    """One row per symbol: counts summed, variants and colours joined with ``・`` in page order."""
    merged: dict[int, _Symbol] = {}
    for rec in records:
        code = rec["symbol_code"]
        if code is None:
            warnings.add("symbol_unmapped", f"{number} {rec['symbol_jp']}")
            continue
        symbol_id = ids[code]
        if symbol_id in merged:
            warnings.add("symbol_merged", f"{number} {rec['symbol_jp']}")
        slot = merged.setdefault(symbol_id, _Symbol())
        slot.count += rec["count"]
        for values, value in ((slot.variants, rec["variant_jp"]), (slot.colors, rec["color_jp"])):
            if value and value not in values:
                values.append(value)
    return {
        sid: (s.count, JOIN.join(s.variants) or None, JOIN.join(s.colors) or None)
        for sid, s in merged.items()
    }


def load_cards(
    conn: sqlite3.Connection,
    lookups: Lookups,
    warnings: BuildWarnings,
    groups: list[CardGroup],
    printings: dict[str, list[Json]],
) -> CardIds:
    """Insert cards, card numbers and the per-card tables; return the ids."""
    card_rows: list[tuple[object, ...]] = []
    by_group: dict[str, int] = {}
    by_number: dict[str, int] = {}
    for card_id, group in enumerate(groups, start=1):
        entry = group.first.entry
        text = entry["text"]
        gameplay = entry["gameplay"]
        type_code = gameplay["card_type_code"]
        if type_code is None:
            raise BuildError(
                f"{group.first.number}: card type {gameplay['card_type_jp']!r} unmapped"
            )
        name_en, flavor_en, source, status = _english(entry, text)
        card_rows.append(
            (
                card_id,
                lookups.card_types[type_code],
                gameplay["cost"],
                entry["name_jp"],
                name_en,
                text["flavor_jp"] if text else None,
                flavor_en,
                lookups.source_id(source),
                lookups.status_id(status),
                _block_icon(group, printings, warnings),
                gameplay["card_class_jp"],
                gameplay["type_mark_jp"],
            )
        )
        by_group[group.key] = card_id
        for number in group.numbers:
            by_number[number] = card_id
    conn.executemany(
        "INSERT INTO cards (id, card_type_id, cost, name_jp, name_en, flavor_text_jp,"
        " flavor_text_en, en_source_id, en_status_id, block_icon, card_class_jp, type_mark_jp)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        card_rows,
    )
    number_ids = {n: i for i, n in enumerate(sorted(by_number), start=1)}
    conn.executemany(
        "INSERT INTO card_numbers (id, number, card_id) VALUES (?, ?, ?)",
        [(i, n, by_number[n]) for n, i in number_ids.items()],
    )
    level_ids = _load_gameplay(conn, lookups, warnings, groups, by_group)
    _load_credits(conn, groups, by_group)
    _load_details(conn, lookups, groups, by_group)
    return CardIds(by_group, by_number, number_ids, level_ids)


def _load_gameplay(
    conn: sqlite3.Connection,
    lookups: Lookups,
    warnings: BuildWarnings,
    groups: list[CardGroup],
    by_group: dict[str, int],
) -> dict[tuple[int, int], int]:
    colors: list[tuple[int, int]] = []
    symbols: list[tuple[int, int, int, str | None, str | None]] = []
    reductions: list[tuple[int, int, int]] = []
    levels: list[tuple[object, ...]] = []
    families: list[tuple[int, int]] = []
    level_ids: dict[tuple[int, int], int] = {}
    for group in groups:
        card_id = by_group[group.key]
        number = group.first.number
        gameplay = group.first.entry["gameplay"]
        card_colors = set()
        for term in gameplay["colors"]:
            if term["code"] is None:
                warnings.add("color_unmapped", f"{number} {term['jp']}")
            else:
                card_colors.add(lookups.colors[term["code"]])
        colors.extend((card_id, c) for c in sorted(card_colors))
        for sid, (count, variant, color) in sorted(
            _merge_symbols(gameplay["symbols"], lookups.symbols, warnings, number).items()
        ):
            symbols.append((card_id, sid, count, variant, color))
        parts = [
            {
                "symbol_code": p["symbol_code"],
                "symbol_jp": p["symbol_jp"],
                "count": p["count"],
                "variant_jp": None,
                "color_jp": None,
            }
            for p in gameplay["reduction"]["parts"]
            if p["count"] >= 1
        ]
        for sid, (count, _, _) in sorted(
            _merge_symbols(parts, lookups.symbols, warnings, number).items()
        ):
            reductions.append((card_id, sid, count))
        card_levels: dict[int, Json] = {}
        for level in gameplay["levels"]:
            if level["level"] in card_levels:
                warnings.add("level_duplicate", f"{number} Lv{level['level']}")
            else:
                card_levels[level["level"]] = level
        for _, level in sorted(card_levels.items()):
            level_id = len(levels) + 1
            level_ids[(card_id, level["level"])] = level_id
            levels.append(
                (
                    level_id,
                    card_id,
                    level["level"],
                    level["cores"],
                    level["battle_points"],
                    level["count_condition"],
                    level["note"],
                )
            )
        codes = set()
        for family in gameplay["families"]:
            if family["code"] is None:
                warnings.add("family_unmapped", f"{number} {family['jp']}")
            else:
                codes.add(lookups.families[family["code"]])
        families.extend((card_id, f) for f in sorted(codes))
    conn.executemany("INSERT INTO card_colors (card_id, color_id) VALUES (?, ?)", colors)
    conn.executemany(
        "INSERT INTO card_symbols (card_id, symbol_id, count, variant_jp, color_jp)"
        " VALUES (?, ?, ?, ?, ?)",
        symbols,
    )
    conn.executemany(
        "INSERT INTO card_reductions (card_id, symbol_id, count) VALUES (?, ?, ?)", reductions
    )
    conn.executemany(
        "INSERT INTO card_levels (id, card_id, level, cores, battle_points, count_condition_jp,"
        " note_jp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        levels,
    )
    conn.executemany("INSERT INTO card_families (card_id, family_id) VALUES (?, ?)", families)
    return level_ids


def _load_credits(
    conn: sqlite3.Connection, groups: list[CardGroup], by_group: dict[str, int]
) -> None:
    """Concept credits (role ``コンセプト``) first, then the other credits, in page order."""
    rows: list[tuple[object, ...]] = []
    for group in groups:
        text = group.first.entry["text"]
        if text is None:
            continue
        credits = [(CONCEPT_ROLE, c["name"], c["note"]) for c in text["concepts"]]
        credits += [(c["role"], c["name"], c["note"]) for c in text["other_credits"]]
        card_id = by_group[group.key]
        rows.extend(
            (len(rows) + 1, card_id, position, role, name, note)
            for position, (role, name, note) in enumerate(credits, start=1)
        )
    conn.executemany(
        "INSERT INTO card_credits (id, card_id, position, role_jp, name, note)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )


def _load_details(
    conn: sqlite3.Connection, lookups: Lookups, groups: list[CardGroup], by_group: dict[str, int]
) -> None:
    brave: list[tuple[int, str | None, int | None]] = []
    ultimate: list[tuple[int, str | None]] = []
    for group in groups:
        entry = group.first.entry
        gameplay, text = entry["gameplay"], entry["text"]
        card_id = by_group[group.key]
        if gameplay["card_type_code"] == "brave":
            conditions = text["fusion_conditions_jp"] if text else []
            brave.append((card_id, "\n".join(conditions) or None, gameplay["fusion_bp_bonus"]))
        elif gameplay["card_type_code"] == "ultimate":
            ultimate.append((card_id, text["summon_condition_jp"] if text else None))
    conn.executemany(
        "INSERT INTO brave_details (card_id, fusion_condition_jp, fusion_bp_bonus)"
        " VALUES (?, ?, ?)",
        brave,
    )
    conn.executemany(
        "INSERT INTO ultimate_details (card_id, summon_condition_jp) VALUES (?, ?)", ultimate
    )
