"""Extract the set-page links from the batspi.com card-list index.

Ported from the legacy ``scripts/set_link_extractor.py``.
"""

import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def extract_set_urls(url: str, output_path: str | Path = "output.txt") -> None:
    """Write the href of every link below ``<h3 id="content_1_1">`` to ``output_path``."""
    try:
        response = requests.get(url)
        response.encoding = "utf-8"

        if response.status_code != 200:
            logger.error("Failed to retrieve the page. Status code: %s", response.status_code)
            return

        soup = BeautifulSoup(response.text, "html.parser")
        h3_tag = soup.find("h3", id="content_1_1")
        if not isinstance(h3_tag, Tag):
            logger.error("Could not find the <h3 id='content_1_1'> element.")
            return

        ul_tags = h3_tag.find_all_next("ul", class_="list1 list-indent1")
        with open(output_path, "w", encoding="utf-8") as file:
            for ul_tag in ul_tags:
                for a_tag in ul_tag.find_all("a", href=True):
                    file.write(str(a_tag["href"]) + "\n")

        logger.info("URLs successfully saved to %s", output_path)
    except Exception as e:
        logger.error("An error occurred: %s", e)
