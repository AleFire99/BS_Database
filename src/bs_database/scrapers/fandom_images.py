"""Download card images from the fandom wiki.

Ported from the legacy ``scripts/scraper/image_scraper.py``. Kept quirks: ``extract_card_infos``
resets ``links`` per table, so only the last table is returned; the set loop builds
``<set_url><nn>`` (no ``BS`` prefix); no rate limiting.
"""

import logging
import os
from collections.abc import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def extract_card_infos(url: str, base_url: str) -> list[tuple[str, str]]:
    """Return ``(code, link)`` rows of the last card table on a set page."""
    response = requests.get(url)
    if response.status_code != 200:
        logger.error("Failed to fetch page: %s", url)
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    tables = soup.find_all("table", {"align": "center", "border": "1"})
    if not tables:
        logger.warning("No tables found on the page.")
        return []

    links: list[tuple[str, str]] = []
    for idx, table in enumerate(tables):
        logger.info("Processing table %d", idx + 1)
        rows = table.find_all("tr")[1:]
        links = []

        for row_idx, row in enumerate(rows):
            td_elements = row.find_all("td")
            if len(td_elements) < 2:
                logger.info("Skipping row %d: less than 2 <td> elements.", row_idx + 1)
                continue

            code = td_elements[0].get_text(strip=True)
            link_tag = td_elements[1].find("a")
            if isinstance(link_tag, Tag) and "href" in link_tag.attrs:
                href = str(link_tag["href"])
                full_url = href if href.startswith("http") else base_url + href
                links.append((code, full_url))
            else:
                logger.info("Row %d: No valid link in the second <td>.", row_idx + 1)
                continue

    logger.info("Extracted %d links from %s.", len(links), url)
    return links


def download_card_image(card_url: str, card_id: str, folder: str) -> None:
    """Fetch the card page, find its image and save it as ``<folder>/<card_id>.jpg``."""
    response = requests.get(card_url)
    if response.status_code != 200:
        logger.error("Failed to fetch card page: %s", card_url)
        return

    soup = BeautifulSoup(response.content, "html.parser")
    image_tag = soup.find("img", class_="mw-file-element")
    if not isinstance(image_tag, Tag):
        logger.warning("No image found for: %s", card_url)
        return

    image_url = image_tag.get("data-src") or image_tag.get("src")
    if not image_url or not isinstance(image_url, str) or image_url.startswith("data:image"):
        logger.warning("Skipping base64 or invalid image for: %s", card_url)
        return

    full_image_url = (
        image_url if image_url.startswith(("http", "https")) else urljoin(card_url, image_url)
    )

    try:
        image_data = requests.get(full_image_url).content
        image_path = os.path.join(folder, f"{card_id}.jpg")
        with open(image_path, "wb") as image_file:
            image_file.write(image_data)
        logger.info("Downloaded image: %s.jpg", card_id)
    except Exception as e:
        logger.error("Failed to download image for %s: %s", card_url, e)


def download_set_images(
    set_numbers: Iterable[int], set_url: str, base_url: str, images_dir: str
) -> None:
    """Download all card images of the given sets into ``<images_dir>/BS<nn>/``."""
    for set_number in set_numbers:
        set_page_url = f"{set_url}{set_number:02}"
        card_infos = extract_card_infos(set_page_url, base_url)

        set_name = f"BS{set_number:02}"
        image_folder = os.path.join(images_dir, set_name)
        os.makedirs(image_folder, exist_ok=True)

        for code, card_link in card_infos:
            card_id = code if code.startswith("BS") else set_name + "-" + code
            download_card_image(card_link, card_id, image_folder)

        logger.info("Completed downloading images for %s", set_name)
