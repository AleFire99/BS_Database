"""Scrape a batspi.com card page into the legacy card JSON.

Ported from the legacy ``scripts/scraper/card_scraper.py``. Kept quirks: ``translate`` returns
``"Error: ..."`` on failure; a mixed reduction that does not look like ``"2 <colour>"`` yields an
empty list; the image path is the relative ``data/images/<set>/<id>.jpg``.
"""

import json
import logging
import os
import re
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag
from deep_translator import GoogleTranslator  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

IMAGE_ROOT = "data/images"


def translate(text: str) -> str:
    """Translate Japanese to English; on failure return ``"Error: <message>"``."""
    try:
        return str(GoogleTranslator(source="ja", target="en").translate(text))
    except Exception as e:
        return f"Error: {e!s}"


def extract_card_name(soup: BeautifulSoup) -> str | None:
    """Return the text of the link inside ``<h1 class="title">``, or None."""
    title_tag = soup.find("h1", class_="title")
    if isinstance(title_tag, Tag):
        link_tag = title_tag.find("a")
        if link_tag:
            return link_tag.get_text(strip=True)
    return None


def extract_spirit_info_and_core_requirements(
    lines: list[str],
) -> tuple[
    int | None,
    list[str] | None,
    str | None,
    list[str] | None,
    str | None,
    list[dict[str, int]],
]:
    """Parse the ``<pre>`` lines: type, cost/reduction/symbol/family and level table."""
    spirit_info = lines[1] if len(lines) > 1 else None
    cost: int | None = None
    reduction: list[str] | None = None
    symbol: str | None = None
    family: list[str] | None = None
    spirit_type: str | None = None
    if spirit_info:
        parts = spirit_info.split("/")

        spirit_type = translate(lines[0].strip())
        cost = int(parts[0].split("(")[0])
        symbol = translate(parts[1])
        reduction_raw = parts[0].split("(")[1].strip(")")

        if reduction_raw == "0":
            reduction = None
        elif re.match(r"^\d+$", reduction_raw):
            count = int(reduction_raw)
            reduction = [symbol] * count if count > 0 else None
        else:
            reduction = []
            for part in [s.strip() for s in reduction_raw.split(",")]:
                match = re.match(r"(\d+)\s*(.+)", part)
                if match:
                    count, color_jp = int(match[1]), match[2]
                    reduction.extend([translate(color_jp)] * count)

        family = [fam.strip() for fam in translate(parts[2]).split("/")] if len(parts) > 2 else None

    levels_text = " ".join([line for line in lines if "Lv" in line])
    core_requirements: list[dict[str, int]] = []
    for cores, level_num, battle_points in re.findall(r"<(\d+)>Lv(\d+)\s+(\d+)", levels_text):
        core_requirements.append(
            {"level": int(level_num), "battlePoints": int(battle_points), "cores": int(cores)}
        )

    return cost, reduction, symbol, family, spirit_type, core_requirements


def save_card_data_to_json(card_data: dict[str, Any], card_id: str, json_dir: str) -> None:
    """Write ``<json_dir>/card_json/<set>/<card_id>.json``."""
    set_name = card_id.split("-")[0]
    folder = os.path.join(json_dir, "card_json", set_name)
    os.makedirs(folder, exist_ok=True)

    json_file_path = os.path.join(folder, f"{card_id}.json")
    with open(json_file_path, "w", encoding="utf-8") as json_file:
        json.dump(card_data, json_file, ensure_ascii=False, indent=4)

    logger.info("Card data successfully saved to %s", json_file_path)


def scrape_card_data(card_id: str, url: str, json_dir: str, image_root: str = IMAGE_ROOT) -> None:
    """Scrape one card page and save its JSON; log an error and write nothing without a name."""
    response = requests.get(url)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    name = extract_card_name(soup)
    if not name:
        logger.error("Could not extract card name from %s", url)
        return

    set_name = card_id.split("-")[0]

    pre_tag = soup.find("pre")
    cost: int | None = None
    reduction: list[str] | None = None
    symbol: str | None = None
    family: list[str] | None = None
    spirit_type: str | None = None
    core_requirements: list[dict[str, int]] | None = None
    if isinstance(pre_tag, Tag):
        lines = pre_tag.text.strip().split("\n")
        cost, reduction, symbol, family, spirit_type, core_requirements = (
            extract_spirit_info_and_core_requirements(lines)
        )

    image_path = os.path.join(image_root, set_name, f"{card_id}.jpg")

    card_data = {
        "name": translate(name),
        "card_id": card_id,
        "type": spirit_type,
        "cost": cost,
        "reduction": reduction,
        "symbol": symbol,
        "family": family,
        "core_requirements": core_requirements,
        "image": image_path,
    }

    save_card_data_to_json(card_data, card_id, json_dir)
