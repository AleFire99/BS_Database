import os
import json
import re

# Root folder where your JSON files are (including subfolders)
root_folder = r"C:\Users\AleFire\Desktop\Projects\BS_Database\data\json\card_json"
family_mapping_file = r"C:\Users\AleFire\Desktop\Projects\BS_Database\data\family_mapping.txt"

# Load family name mappings
def load_family_mappings(file_path):
    mapping = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if '=' in line:
                old, new = map(str.strip, line.strip().split('='))
                mapping[old.lower()] = new
    return mapping

family_mapping = load_family_mappings(family_mapping_file)

# Normalize and remap family names
def normalize_family(family_field):
    if isinstance(family_field, str):
        return transform_family_names(split_family(family_field))

    elif isinstance(family_field, list):
        cleaned = []
        for item in family_field:
            if isinstance(item, str):
                cleaned.extend(transform_family_names(split_family(item)))
        return cleaned

    return family_field  # Leave unchanged if it's some other unexpected type

def split_family(s):
    parts = re.split(r",|\s+and\s+|:", s)  # Added ':' as separator
    split_parts = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        part_lower = part.lower()

        # Special case: Starts with 'Next Generation' and contains ' of '
        if part_lower.startswith("next generation") and " of " in part_lower:
            sub_parts = re.split(r"\s+of\s+", part, flags=re.IGNORECASE)
            split_parts.append("Next Generation")
            if len(sub_parts) > 1:
                split_parts.append(sub_parts[1].strip())

        # Special case: Starts with 'New X'
        elif part_lower.startswith("new "):
            new_parts = part.split(None, 1)
            if len(new_parts) == 2:
                split_parts.extend(new_parts)
            else:
                split_parts.append(part)

        # Special case: Starts with 'Different X'
        elif part_lower.startswith("different "):
            diff_parts = part.split(None, 1)
            if len(diff_parts) == 2:
                split_parts.extend(diff_parts)
            else:
                split_parts.append(part)

        else:
            split_parts.append(part)

    return split_parts


def transform_family_names(family_list):
    normalized = []
    for fam in family_list:
        fam_lower = fam.lower()

        # Normalize snake-related names first
        if "snake" in fam_lower:
            new_fam = "Dark Snake"
        # Apply mapping
        elif fam_lower in family_mapping:
            new_fam = family_mapping[fam_lower]
        else:
            new_fam = fam

        # Remove leading "The"
        new_fam = new_fam.strip()
        if new_fam.lower().startswith("the "):
            new_fam = new_fam[4:].strip()

        if new_fam.lower().startswith("and "):
            new_fam = new_fam[4:].strip()

        if new_fam.lower().startswith("a "):
            new_fam = new_fam[2:].strip()

        # Capitalize each word
        new_fam = new_fam.title()

        # Singularize last word if plural and longer than 1 character
        words = new_fam.split()
        if words:
            last = words[-1]
            if last.lower().endswith("s") and len(last) > 1:
                words[-1] = last[:-1]
            new_fam = " ".join(words)

        normalized.append(new_fam)

    return list(set(normalized))  # remove duplicates



# Type normalization
def normalize_type(card_type):
    normalized = re.split(r"\s*\(", card_type)[0].strip()
    return normalized.capitalize()

# Update all JSONs
for dirpath, _, filenames in os.walk(root_folder):
    for filename in filenames:
        if filename.endswith(".json"):
            file_path = os.path.join(dirpath, filename)

            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Skipping {file_path} (invalid JSON): {e}")
                    continue

            if "family" in data:
                data["family"] = normalize_family(data["family"])

            if "type" in data and isinstance(data["type"], str):
                data["type"] = normalize_type(data["type"])

            if "image" in data:
                data["image"] = data["image"].replace("\\", "/")

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

print("All JSON files updated with full normalization.")
