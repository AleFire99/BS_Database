import requests
from typing import List, Tuple
import re
from bs4 import BeautifulSoup
from config.settings import BATSPI_URL

def extract_links(url: str) -> List[Tuple[str, str]]:
    """
    Extract card IDs and links from the provided URL of a card list page.

    Args:
        url (str): The URL of the card list page.

    Returns:
        List[Tuple[str, str]]: A list of (card_id, full_url) tuples.
    """
    # Fetch the HTML content of the page
    response = requests.get(url)
    response.encoding = "utf-8"  # Ensure proper encoding

    # Parse the HTML content with BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")

    card_links: List[Tuple[str, str]] = []

    # Get all <p> tags that contain card entries
    for p in soup.find_all("p"):
        text = p.get_text()
        matches = re.findall(r"(BS\d{2}-\d{3})", text)  # Find card IDs
        a_tags = p.find_all("a", href=True)

        for match, a in zip(matches, a_tags):
            card_id: str = match
            relative_link: str = a["href"]
            full_link: str = BATSPI_URL + relative_link
            card_links.append((card_id, full_link))

    return card_links
