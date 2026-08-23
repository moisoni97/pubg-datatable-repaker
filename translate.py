"""
PUBG JSON Name Translator
=========================
Translates obfuscated property names, enums, and asset references in
exported PUBG JSON files using PUBGNameHashMap.json.

Usage:
    python translate.py [file_or_folder_path]

If no path is provided, translates all .json files in the exported_json/ folder.
"""

import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JSON_DIR = os.path.join(SCRIPT_DIR, "exported_json")
DEFAULT_MAP_PATHS = [
    os.path.join(SCRIPT_DIR, "input", "PUBGNameHashMap.json"),
    os.path.join(SCRIPT_DIR, "PUBGNameHashMap.json"),
]

HASH_PATTERN = re.compile(r"\*[0-9a-fA-F]{10}")


def load_hash_map(custom_path=None):
    search_paths = [custom_path] if custom_path else DEFAULT_MAP_PATHS
    for p in search_paths:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {k.strip(): v.strip() for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
            except Exception as e:
                print(f"ERROR: Failed to read {p}: {e}")
                sys.exit(1)

    print("ERROR: PUBGNameHashMap.json not found.")
    print("Please place PUBGNameHashMap.json in the input/ folder.")
    sys.exit(1)


def translate_string(val_str, hash_map):
    if not val_str or not isinstance(val_str, str):
        return val_str

    if val_str in hash_map:
        return hash_map[val_str]

    if "::" in val_str:
        parts = val_str.split("::")
        translated_parts = [hash_map.get(p, p) for p in parts]
        return "::".join(translated_parts)

    def repl(match):
        h = match.group(0)
        return hash_map.get(h, h)

    return HASH_PATTERN.sub(repl, val_str)


def translate_data(data, hash_map):
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            new_key = hash_map.get(k, k)
            new_dict[new_key] = translate_data(v, hash_map)
        return new_dict
    elif isinstance(data, list):
        return [translate_data(item, hash_map) for item in data]
    elif isinstance(data, str):
        return translate_string(data, hash_map)
    return data


def process_file(file_path, hash_map):
    print(f"Translating: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        translated = translate_data(data, hash_map)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(translated, f, indent=2, ensure_ascii=False)

        print(f"  Done: {file_path}")
        return True
    except Exception as e:
        print(f"  ERROR translating {file_path}: {e}")
        return False


def main():
    os.makedirs(DEFAULT_JSON_DIR, exist_ok=True)

    input_targets = sys.argv[1:] if len(sys.argv) > 1 else [DEFAULT_JSON_DIR]

    json_files = []
    for target in input_targets:
        if not os.path.exists(target):
            print(f"WARNING: Path does not exist: {target}")
            continue

        if os.path.isfile(target):
            if target.endswith(".json") and os.path.basename(target) not in ("PUBGNameHashMap.json", "config.json"):
                json_files.append(target)
        elif os.path.isdir(target):
            for root, _, files in os.walk(target):
                for file in files:
                    if file.endswith(".json") and file not in ("PUBGNameHashMap.json", "config.json"):
                        json_files.append(os.path.join(root, file))

    if not json_files:
        print("No .json files found to translate.")
        print(f"\nDrop exported JSON files into:\n  {DEFAULT_JSON_DIR}")
        print("\nOr provide paths:\n  python translate.py <file1.json> <file2.json> ...")
        sys.exit(0)

    hash_map = load_hash_map()
    print("=" * 60)
    print("  PUBG JSON Name Translator")
    print("=" * 60)
    print(f"Loaded {len(hash_map)} name mappings from PUBGNameHashMap.json\n")

    print(f"Found {len(json_files)} JSON file(s) to process:")
    success = sum(1 for f in json_files if process_file(f, hash_map))
    print(f"\nCompleted: {success}/{len(json_files)} file(s) translated.")


if __name__ == "__main__":
    main()
