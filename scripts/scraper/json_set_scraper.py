import requests
from bs4 import BeautifulSoup
import json
import os

def fetch_page(url):
    """Fetches the HTML content of a given URL."""
    headers = {"User-Agent": "Mozilla/5.0"}  # Avoid being blocked
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def parse_table(html, url):
    """Parses the table from the HTML content and extracts data."""
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all("table")  # Get all tables

    if not tables:
        print(f"No tables found for URL: {url}")
        return []

    table = soup.select_one("#mw-content-text > div > table:nth-child(2) > tbody")
    if not table:
        print(f"Table not found for URL: {url}")
        return []

    rows = table.find_all("tr")
    if not rows:
        print(f"Empty table found for URL: {url}")
        return []

    headers = [th.text.strip() for th in rows[0].find_all("th")]

    set_number = url[-4:]  # Extract last two digits from URL

    data = []
    for row in rows[1:]:  # Skip header row
        cells = row.find_all("td")
        if len(cells) != len(headers):
            continue  # Skip malformed rows
        entry = {headers[i]: cells[i].text.strip() for i in range(len(cells))}

        if "Number" in entry:
            if not entry['Number'].startswith(set_number):
                entry["Card_ID"] = f"{set_number}-{entry['Number'].zfill(3)}"
            else:
                entry["Card_ID"] = entry['Number']
            del entry["Number"]

        data.append(entry)

    return data

def save_to_json(data, filename):
    """Saves the extracted data to a JSON file, creating the file if it does not exist."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)  # Ensure directory exists

    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=4)  # Create empty JSON array

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def scrape_battle_spirits(url, output_file):
    """Main function to scrape the site and save data."""
    html = fetch_page(url)
    data = parse_table(html, url)
    save_to_json(data, output_file)
    return data
