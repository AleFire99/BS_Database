import os

from config.settings import BASE_SET_URL, JSON_FOLDER_PATH
from scripts.json_set_scraper import scrape_battle_spirits

for i in range(47, 61):
    set_number = f"BS{i:02d}"  # Format as two-digit string
    SET_URL = BASE_SET_URL + set_number
    JSON_FILE = os.path.join(JSON_FOLDER_PATH, f"{set_number}.json")
    
    print(f"Scraping {SET_URL} and saving to {JSON_FILE}")
    
    if __name__ == "__main__":
        data = scrape_battle_spirits(SET_URL, JSON_FILE)
        print(f"Scraped {len(data)} entries and saved to {JSON_FILE}")
