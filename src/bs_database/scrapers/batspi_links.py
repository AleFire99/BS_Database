"""Extract card ids and links from a batspi.com set page.

Ported from the legacy ``scripts/extract_card_links.py``.
"""

import re

import requests
from bs4 import BeautifulSoup


def extract_links(url: str, batspi_url: str) -> list[tuple[str, str]]:
    """Return ``(card_id, batspi_url + href)`` for every card entry of a set page."""
    response = requests.get(url)
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")

    card_links: list[tuple[str, str]] = []
    for p in soup.find_all("p"):
        text = p.get_text()
        matches = re.findall(r"(BS\d{2}-\d{3})", text)
        a_tags = p.find_all("a", href=True)

        for match, a in zip(matches, a_tags, strict=False):
            card_links.append((match, batspi_url + str(a["href"])))

    return card_links
