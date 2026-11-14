"""Scrape a fandom wiki set page (card table) into JSON.

Ported from the legacy ``scripts/scraper/json_set_scraper.py``. The table is located with the
legacy CSS selector, so it needs the ``<tbody>`` the wiki serves.
"""

import json
import logging
import os
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def fetch_page(url: str) -> str:
    """Fetch the HTML of ``url`` (raises on HTTP errors)."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def parse_table(html: str, url: str) -> list[dict[str, str]]:
    """Extract the card rows of the set table; ``Number`` becomes ``Card_ID``."""
    soup = BeautifulSoup(html, "html.parser")
    if not soup.find_all("table"):
        logger.warning("No tables found for URL: %s", url)
        return []

    table = soup.select_one("#mw-content-text > div > table:nth-child(2) > tbody")
    if not isinstance(table, Tag):
        logger.warning("Table not found for URL: %s", url)
        return []

    rows = table.find_all("tr")
    if not rows:
        logger.warning("Empty table found for URL: %s", url)
        return []

    headers = [th.text.strip() for th in rows[0].find_all("th")]
    set_number = url[-4:]

    data: list[dict[str, str]] = []
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) != len(headers):
            continue
        entry = {headers[i]: cells[i].text.strip() for i in range(len(cells))}

        if "Number" in entry:
            if not entry["Number"].startswith(set_number):
                entry["Card_ID"] = f"{set_number}-{entry['Number'].zfill(3)}"
            else:
                entry["Card_ID"] = entry["Number"]
            del entry["Number"]

        data.append(entry)

    return data


def save_to_json(data: Any, filename: str) -> None:
    """Write ``data`` as indented UTF-8 JSON, creating the directory."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def scrape_battle_spirits(url: str, output_file: str) -> list[dict[str, str]]:
    """Fetch, parse and save one set page; return the parsed rows."""
    html = fetch_page(url)
    data = parse_table(html, url)
    save_to_json(data, output_file)
    return data
