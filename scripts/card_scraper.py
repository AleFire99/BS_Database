import os
import requests
import json
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import re

IMAGE_PATH = "data/images"

# Function to translate Japanese text to English
def translate(text):
    return GoogleTranslator(source='ja', target='en').translate(text)

# Function to extract card name and ID
def extract_card_name_and_id(soup):
    # Extract card number from the <span class="cardno"> element
    card_id_tag = soup.find("span", class_="cardno")
    if card_id_tag:
        card_id = card_id_tag.get_text(strip=True)
        # Extract the card name from the "h3" element as before
        name_tag = soup.find("h3", id="content_1_0")
        if name_tag:
            name_text = name_tag.get_text(strip=True)
            return name_text, card_id  # Return the name and the card ID (from <span>)
    return None, None

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

        # Extract reduction (inside parentheses), set None if 0
        reduction_value = int(parts[0].split("(")[1].strip(")"))
        reduction = None if reduction_value == 0 else reduction_value

        # Extract symbol (third value) and translate it
        symbol = translate(parts[1])

        # Extract family (fourth value) and translate it
        family = translate(parts[2]) if len(parts) > 2 else None

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
def save_card_data_to_json(card_data, set_name, card_id, json_folder_path):
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
def scrape_card_data(URL, json_folder_path):
    # Scrape the webpage
    response = requests.get(URL)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract card name and ID
    name, card_id = extract_card_name_and_id(soup)
    if not name or not card_id:
        print("Error: Could not extract card name and ID.")
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
    save_card_data_to_json(card_data, set_name, card_id, json_folder_path)
