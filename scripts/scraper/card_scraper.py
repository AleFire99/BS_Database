import os
import requests
import json
from typing import Optional
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import re

IMAGE_PATH = "data/images"

# Function to translate Japanese text to English
def translate(text):
    try:
        return GoogleTranslator(source='ja', target='en').translate(text)
    except Exception as e:
        return f"Error: {str(e)}"

def extract_card_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract the card name from the HTML soup.

    Parameters:
    soup (BeautifulSoup): Parsed HTML content of the card page.

    Returns:
    Optional[str]: The extracted card name, or None if not found.
    """
    title_tag = soup.find("h1", class_="title")
    if title_tag:
        link_tag = title_tag.find("a")
        if link_tag:
            return link_tag.get_text(strip=True)
    return None

# Function to extract spirit type info and core requirements
def extract_spirit_info_and_core_requirements(lines):
    # Extracting spirit type info: "0(0)/赤/爬獣"
    spirit_info = lines[1] if len(lines) > 1 else None
    cost, reduction, symbol, family, spirit_type = None, None, None, None, None
    if spirit_info:
        parts = spirit_info.split("/")  # Split into parts

        # Extract spirit type (first value) and translate it
        spirit_type = translate(lines[0].strip())  # This is the dynamic part for "Spirit"

        # Extract cost (second part)
        cost = int(parts[0].split("(")[0])

        # Extract symbol (third value) and translate it
        symbol = translate(parts[1])

        # Extract reduction (inside parentheses)
        reduction_raw = parts[0].split("(")[1].strip(")")

        # Case 1: reduction is 0
        if reduction_raw == "0":
            reduction = None

        # Case 2: simple number like "3"
        elif re.match(r"^\d+$", reduction_raw):
            count = int(reduction_raw)
            reduction = [symbol] * count if count > 0 else None

        # Case 3: mixed reduction like "2 紫, 1 神"
        else:
            reduction = []
            parts_split = [s.strip() for s in reduction_raw.split(",")]
            for part in parts_split:
                match = re.match(r"(\d+)\s*(.+)", part)
                if match:
                    count, color_jp = int(match[1]), match[2]
                    color_en = translate(color_jp)
                    reduction.extend([color_en] * count)


        # Extract family (fourth value) and translate it
        # Extract family (fourth value) and translate it as a list
        family = (
            [fam.strip() for fam in translate(parts[2]).split("/")]
            if len(parts) > 2 else None
        )


    # Extract levels and structure them properly
    levels_text = " ".join([line for line in lines if "Lv" in line])
    core_requirements = []  # List for core requirements

    # Regex pattern to extract multiple level structures: <core>LvX BP
    matches = re.findall(r"<(\d+)>Lv(\d+)\s+(\d+)", levels_text)

    for match in matches:
        cores = int(match[0])  # Number inside <>, e.g., "3"
        level_num = int(match[1])  # Level number after "Lv", e.g., "1"
        battlePoints = int(match[2])  # Battle Points

        core_requirements.append({
            "level": level_num,
            "battlePoints": battlePoints,
            "cores": cores
        })

    return cost, reduction, symbol, family, spirit_type, core_requirements

# Function to save the card data into a JSON file
def save_card_data_to_json(card_data, card_id, json_folder_path):

    set_name = card_id.split("-")[0]
    # Construct the full folder path
    json_folder_path = os.path.join(json_folder_path, "card_json", set_name)

    # Create the directory if it doesn't exist
    if not os.path.exists(json_folder_path):
        os.makedirs(json_folder_path)

    # Save the JSON file in the appropriate folder with the card ID as the filename
    json_file_path = os.path.join(json_folder_path, f"{card_id}.json")
    with open(json_file_path, "w", encoding="utf-8") as json_file:
        json.dump(card_data, json_file, ensure_ascii=False, indent=4)

    print(f"Card data successfully saved to {json_file_path}!")

# Function to scrape and process card data
def scrape_card_data(card_id, URL, json_folder_path):
    # Construct the URL dynamically with the card_id

    # Scrape the webpage
    response = requests.get(URL)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract card name
    name = extract_card_name(soup)
    if not name:
        print("Error: Could not extract card name.")
        return

    # Extract the set name from the card ID (e.g., "BS01" from "BS01-001")
    set_name = card_id.split("-")[0]  # Take the part before the hyphen

    # Extract the main card details
    pre_tag = soup.find("pre")

    if pre_tag:
        lines = pre_tag.text.strip().split("\n")
        cost, reduction, symbol, family, spirit_type, core_requirements = extract_spirit_info_and_core_requirements(lines)
    else:
        cost, reduction, symbol, family, spirit_type, core_requirements = None, None, None, None, None, None

    # Construct the image path with set-name and card ID (e.g., "BS01/BS01-027")
    image_path = os.path.join(IMAGE_PATH, set_name, f"{card_id}.jpg")

    # Store extracted data in a dictionary
    card_data = {
        "name": translate(name) if name else None,
        "card_id": card_id,
        "type": spirit_type,  # Dynamically set based on extracted info
        "cost": cost,
        "reduction": reduction,
        "symbol": symbol,  # Now translated
        "family": family,
        "core_requirements": core_requirements,
        "image": image_path  # Added image path key
    }

    # Save the card data into a JSON file
    save_card_data_to_json(card_data, card_id, json_folder_path)

def main():
    card_id = "BS01-027"  # Replace with any valid card ID
    base_url = "https://batspi.com/card"  # Replace with the actual base URL
    json_folder_path = "data/json"  # Folder to store the JSON output

    scrape_card_data(card_id, base_url, json_folder_path)

if __name__ == "__main__":
    main()
