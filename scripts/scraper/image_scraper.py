import os
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from config.settings import BASE_URL, BASE_SET_URL, IMAGE_FOLDER_PATH

# Function to ensure the folder exists
def create_folder(folder_name):
    """Create a folder if it doesn't exist."""
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

# Function to fetch and extract links from the card table
def extract_card_infos(url):
    """Fetch and extract links from the card table."""
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch page: {url}")
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    
    # Find all tables that match the criteria
    tables = soup.find_all("table", {"align": "center", "border": "1"})
    
    # Check if any tables were found
    if not tables:
        print("No tables found on the page.")
        return []
    
    # # If there's exactly one table, skip processing
    # if len(tables) == 1:
    #     print("Only one table found. Skipping the process.")
    #     return []
    
    # Process the tables that are selected
    for idx, table in enumerate(tables):            # Use tables[1:] to skip the first table
        print(f"Processing table {idx + 1}")  # Correct table numbering
        # Continue processing each table as needed
    
        rows = table.find_all("tr")[1:]  # Skip the header row
        links = []
    
        for idx, row in enumerate(rows):
            # Ensure the row has at least two <td> elements
            td_elements = row.find_all("td")
            if len(td_elements) < 2:
                print(f"Skipping row {idx + 1}: less than 2 <td> elements.")
                continue
            
            # Extract the code from the first column
            code = td_elements[0].get_text(strip=True)
        
            # Attempt to extract the link from the second column
            link_tag = td_elements[1].find("a")
            if link_tag and "href" in link_tag.attrs:
                href = link_tag["href"]
        
                # If the href is already a full URL, use it directly
                if href.startswith("http"):
                    full_url = href
                else:
                    full_url = BASE_URL + href  # Concatenate with BASE_URL if it's a relative URL
                
                # Store both the code and the link
                links.append((code, full_url))
            else:
                print(f"Row {idx + 1}: No valid link in the second <td>.")
                continue

    print(f"Extracted {len(links)} links from {url}.")
    return links

# Function to extract the card image and save it
def download_card_image(card_url, card_id, folder):
    """Fetch and save the card image from a given URL."""
    response = requests.get(card_url)
    if response.status_code != 200:
        print(f"Failed to fetch card page: {card_url}")
        return  # Skip if the page could not be fetched

    soup = BeautifulSoup(response.content, "html.parser")

    # Find the image tag
    image_tag = soup.find("img", class_="mw-file-element")
    if image_tag:
        # First check for data-src, then fall back to src if necessary
        image_url = image_tag.get("data-src") or image_tag.get("src")
        
        # Check if the image URL is a valid image (not a base64 data URI)
        if not image_url or image_url.startswith('data:image'):
            print(f"Skipping base64 or invalid image for: {card_url}")
            return  # Skip base64 or invalid URLs

        # Ensure the image URL is complete
        full_image_url = image_url if image_url.startswith(('http', 'https')) else urljoin(card_url, image_url)

        # Download the image
        try:
            image_data = requests.get(full_image_url).content
            image_name = f"{card_id}.jpg"  # You can change the extension if needed

            # Save the image to the folder
            image_path = os.path.join(folder, image_name)
            with open(image_path, "wb") as image_file:
                image_file.write(image_data)
            print(f"Downloaded image: {image_name}")
        except Exception as e:
            print(f"Failed to download image for {card_url}: {e}")
    else:
        print(f"No image found for: {card_url}")

# Main script
if __name__ == "__main__":

    # Loop through each set from BS01 to BS71
    for set_number in range(19, 72):  # Start at 1, end at 71 (inclusive)
        # Generate the full URL for each set page (e.g., BS01, BS02, ..., BS71)
        set_page_url = f"{BASE_SET_URL}{set_number:02}"

        # Step 1: Extract card links from the set page
        card_infos = extract_card_infos(set_page_url)

        # Step 2: Extract the set name (e.g., BS01, BS02, ..., BS71)
        set_name = f"BS{set_number:02}"

        # Step 3: Create a folder for the set images (e.g., "card_images/BS01")
        image_folder = os.path.join(IMAGE_FOLDER_PATH, set_name)
        create_folder(image_folder)

        # Step 4: Download images for each card in the set
        for card_info in card_infos:
            if card_info[0].startswith("BS"):
                card_id = card_info[0]
            else:
                card_id = set_name + "-" + card_info[0]
            card_link = card_info[1]
            download_card_image(card_link, card_id, image_folder)

        print(f"Completed downloading images for {set_name}")
