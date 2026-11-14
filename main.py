import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import BASE_SET_URL, JSON_FOLDER_PATH, BATSPI_URL
from scripts.scraper.json_set_scraper import scrape_battle_spirits
from scripts.scraper.card_scraper import scrape_card_data
from scripts.extract_card_links import extract_links
from scripts.db.db_manager import Base, load_json_cards


def extract_images():
    for i in range(47, 61):
        set_number = f"BS{i:02d}"  # Format as two-digit string
        SET_URL = BASE_SET_URL + set_number
        JSON_FILE = os.path.join(JSON_FOLDER_PATH, "set_json", f"{set_number}.json")

        print(f"Scraping {SET_URL} and saving to {JSON_FILE}")

        if __name__ == "__main__":
            data = scrape_battle_spirits(SET_URL, JSON_FILE)
            print(f"Scraped {len(data)} entries and saved to {JSON_FILE}")


def main():
    # Open the url.txt file to read the URLs
    try:
        with open("data/extracted_urls.txt", "r", encoding="utf-8") as file:
            # Read each URL from the file
            urls = file.readlines()

        # Loop through the URLs and process them
        for url in urls:
            url = BATSPI_URL + url.strip()  # Remove any leading/trailing whitespaces
            if url:  # Skip empty lines
                print(f"Processing URL: {url}")

                # Call the extract_links function from the module
                links = extract_links(url)

                # Print out the links
                if links:
                    print("Extracted Links:")
                    for BS_IDs, link in links:
                        # Call the function to scrape and save the card data
                        #print(f"Scraping and saving data for link: {link}")
                        print(f"BS_IDs: {BS_IDs}")
                        scrape_card_data(BS_IDs, link, JSON_FOLDER_PATH)
                else:
                    print(f"No links found for {url}.")
            else:
                print("Skipping empty URL line.")

    except FileNotFoundError:
        print("Error: url.txt file not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    engine = create_engine('sqlite:///battle_spirits.db')
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    root_folder = r"C:\Users\AleFire\Desktop\Projects\BS_Database\data\json\card_json"
    load_json_cards(root_folder, session)

    print("✅ Done!")
