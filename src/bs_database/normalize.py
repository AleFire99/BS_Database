"""Normalization of scraped card JSON (family names, type, image path).

Ported from the legacy ``json_editor.py``; the logic (including its quirks) is kept
identical. The family mapping is passed explicitly and nothing runs at import time.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_family_mappings(path: str | Path) -> dict[str, str]:
    """Load ``old = new`` lines into a dict keyed by the lowercased old name."""
    mapping: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                old, new = map(str.strip, line.strip().split("="))
                mapping[old.lower()] = new
    return mapping


def split_family(s: str) -> list[str]:
    """Split a raw family string into individual family names."""
    parts = re.split(r",|\s+and\s+|:", s)
    split_parts: list[str] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        part_lower = part.lower()

        if part_lower.startswith("next generation") and " of " in part_lower:
            sub_parts = re.split(r"\s+of\s+", part, flags=re.IGNORECASE)
            split_parts.append("Next Generation")
            if len(sub_parts) > 1:
                split_parts.append(sub_parts[1].strip())
        elif part_lower.startswith(("new ", "different ")):
            words = part.split(None, 1)
            if len(words) == 2:
                split_parts.extend(words)
            else:
                split_parts.append(part)
        else:
            split_parts.append(part)

    return split_parts


def transform_family_names(names: list[str], mapping: dict[str, str]) -> list[str]:
    """Remap, strip articles, title-case and singularize; result order is unspecified."""
    normalized: list[str] = []
    for fam in names:
        fam_lower = fam.lower()

        if "snake" in fam_lower:
            new_fam = "Dark Snake"
        elif fam_lower in mapping:
            new_fam = mapping[fam_lower]
        else:
            new_fam = fam

        new_fam = new_fam.strip()
        if new_fam.lower().startswith("the "):
            new_fam = new_fam[4:].strip()
        if new_fam.lower().startswith("and "):
            new_fam = new_fam[4:].strip()
        if new_fam.lower().startswith("a "):
            new_fam = new_fam[2:].strip()

        new_fam = new_fam.title()

        words = new_fam.split()
        if words:
            last = words[-1]
            if last.lower().endswith("s") and len(last) > 1:
                words[-1] = last[:-1]
            new_fam = " ".join(words)

        normalized.append(new_fam)

    return list(set(normalized))


def normalize_family(field: Any, mapping: dict[str, str]) -> Any:
    """Normalize a family field given as a string or list; other types pass through."""
    if isinstance(field, str):
        return transform_family_names(split_family(field), mapping)
    if isinstance(field, list):
        cleaned: list[str] = []
        for item in field:
            if isinstance(item, str):
                cleaned.extend(transform_family_names(split_family(item), mapping))
        return cleaned
    return field


def normalize_type(card_type: str) -> str:
    """Drop a parenthesised suffix and capitalize: ``"spirit (x)"`` -> ``"Spirit"``."""
    return re.split(r"\s*\(", card_type)[0].strip().capitalize()


def normalize_card(data: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Normalize one card dict in place and return it."""
    if "family" in data:
        data["family"] = normalize_family(data["family"], mapping)
    if "type" in data and isinstance(data["type"], str):
        data["type"] = normalize_type(data["type"])
    if "image" in data:
        data["image"] = data["image"].replace("\\", "/")
    return data


def normalize_tree(root: str | Path, mapping_path: str | Path) -> int:
    """Normalize every ``*.json`` under ``root`` in place; return files written.

    Invalid JSON files are skipped with a warning.
    """
    mapping = load_family_mappings(mapping_path)
    written = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            if not filename.endswith(".json"):
                continue
            file_path = os.path.join(dirpath, filename)
            with open(file_path, encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.warning("Skipping %s (invalid JSON): %s", file_path, e)
                    continue
            normalize_card(data, mapping)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            written += 1
    logger.info("Normalized %d JSON files under %s", written, root)
    return written
