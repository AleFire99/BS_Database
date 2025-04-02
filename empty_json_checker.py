import os
import json
from config.settings import JSON_FOLDER_PATH

def check_empty_json_files(json_folder_path):
    """Checks all JSON files in the given folder and displays paths of empty ones."""
    # Iterate over all files in the folder
    for root, dirs, files in os.walk(json_folder_path):
        for file in files:
            if file.endswith(".json"):  # Only consider JSON files
                file_path = os.path.join(root, file)
                
                # Open and check the file contents
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        
                        # Check if the data is empty or not in the expected structure
                        if not data or not isinstance(data, list) or len(data) == 0:
                            print(f"Empty or malformed JSON file: {file_path}")
                    except json.JSONDecodeError:
                        print(f"Error reading JSON file: {file_path}")

# Define the folder path where your JSON files are stored
check_empty_json_files(JSON_FOLDER_PATH)
