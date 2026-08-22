"""
PUBG DataTable Repaker
======================
Patches obfuscated RowStruct hashes in PUBG DataTable .uasset files
and repacks them into a .pak file loadable by FModel.

Usage:
    python repak.py

Reads all .uasset files from the input/ folder, patches them,
and packs everything into a single .pak in the output/ folder.

When the RowStruct hash changes after a PUBG update, edit config.json.
"""

import json
import os
import shutil
import struct
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(SCRIPT_DIR, "input")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERROR: config.json not found at {CONFIG_PATH}")
        sys.exit(1)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse config.json: {e}")
        sys.exit(1)

    required_keys = ["rowstruct_hash", "repak_exe", "pak_version", "output_pak_name"]
    for key in required_keys:
        if key not in config:
            print(f"ERROR: Missing key '{key}' in config.json")
            sys.exit(1)

    return config


def normalize_hash(raw_hash):
    raw_hash = raw_hash.strip()
    if raw_hash.startswith("_"):
        return "*" + raw_hash[1:]
    if not raw_hash.startswith("*"):
        return "*" + raw_hash
    return raw_hash


def find_fstring(data, text_bytes):
    str_with_null = text_bytes + b"\x00"
    length = len(str_with_null)
    target = struct.pack("<i", length) + str_with_null

    idx = data.find(target)
    if idx == -1:
        return None, None
    return idx, 4 + length


def find_package_path(data):
    search = b"/Game/"
    idx = data.find(search)
    if idx == -1:
        return None, None, None

    length_prefix_offset = idx - 4
    if length_prefix_offset < 0:
        return None, None, None

    length = struct.unpack("<i", data[length_prefix_offset:length_prefix_offset + 4])[0]
    if length <= 0 or length > 500:
        return None, None, None

    path_bytes = data[idx:idx + length - 1]
    try:
        path_str = path_bytes.decode("ascii")
    except UnicodeDecodeError:
        return None, None, None

    return length_prefix_offset, path_str, 4 + length


def game_path_to_pak_path(game_path):
    cleaned = game_path
    while "//" in cleaned:
        cleaned = cleaned.replace("//", "/")
    cleaned = cleaned.strip("/")

    if cleaned.startswith("Game/"):
        cleaned = "TslGame/Content/" + cleaned[5:]

    parts = cleaned.rsplit("/", 1)
    return parts[0] if len(parts) == 2 else cleaned


def patch_uasset(data, hash_string):
    hash_bytes = hash_string.encode("ascii")
    rowstruct_bytes = b"RowStruct"

    hash_offset, hash_fstring_size = find_fstring(data, hash_bytes)

    if hash_offset is None:
        rs_offset, _ = find_fstring(data, rowstruct_bytes)
        if rs_offset is not None:
            print("    Already patched (RowStruct found). Skipping patch step.")
            path_offset, game_path, _ = find_package_path(data)
            if path_offset is None:
                print("    ERROR: Could not find /Game/ package path.")
                return None, None
            return data, game_path

        print(f"    ERROR: Hash '{hash_string}' not found in file.")
        return None, None

    print(f"    Found hash at offset {hex(hash_offset)}")

    path_offset, game_path, _ = find_package_path(data)
    if path_offset is None:
        print("    ERROR: Could not find /Game/ package path.")
        return None, None

    print(f"    Found package path: {game_path}")

    old_hash_fstring_size = hash_fstring_size
    new_hash_fstring_size = 4 + len(rowstruct_bytes) + 1
    byte_diff = old_hash_fstring_size - new_hash_fstring_size

    if byte_diff < 0:
        print("    ERROR: Replacement RowStruct is longer than hash.")
        return None, None

    print(f"    Byte difference: {byte_diff} bytes (hash={old_hash_fstring_size}, RowStruct={new_hash_fstring_size})")

    new_hash_fstring = struct.pack("<i", len(rowstruct_bytes) + 1) + rowstruct_bytes + b"\x00"

    old_path_length = struct.unpack("<i", data[path_offset:path_offset + 4])[0]
    new_path_length = old_path_length + byte_diff
    old_path_str = data[path_offset + 4:path_offset + 4 + old_path_length][:-1]

    game_prefix = b"/Game/"
    prefix_idx = old_path_str.find(game_prefix)
    if prefix_idx == -1:
        print("    ERROR: /Game/ not found in path string.")
        return None, None

    # Compensate byte difference by adding extra '/' slashes to preserve exact file offsets
    insert_point = prefix_idx + len(game_prefix)
    padded_path = (
        old_path_str[:insert_point]
        + b"/" * byte_diff
        + old_path_str[insert_point:]
    )
    new_path_fstring = struct.pack("<i", new_path_length) + padded_path + b"\x00"

    patched = bytearray(data)

    # Patch in reverse offset order to maintain positional integrity
    if hash_offset < path_offset:
        patched[path_offset:path_offset + 4 + old_path_length] = new_path_fstring
        patched[hash_offset:hash_offset + old_hash_fstring_size] = new_hash_fstring
    else:
        patched[hash_offset:hash_offset + old_hash_fstring_size] = new_hash_fstring
        patched[path_offset:path_offset + 4 + old_path_length] = new_path_fstring

    if len(patched) != len(data):
        print(f"    ERROR: File size mismatch! Original={len(data)}, Patched={len(patched)}")
        return None, None

    print("    Patch successful! File size preserved.")
    return bytes(patched), game_path.replace("//", "/")


def main():
    print("=" * 60)
    print("  PUBG DataTable Repaker")
    print("=" * 60)
    print()

    config = load_config()
    hash_string = normalize_hash(config["rowstruct_hash"])
    repak_exe = os.path.join(SCRIPT_DIR, config["repak_exe"])
    pak_version = config["pak_version"]
    output_pak_name = config["output_pak_name"]

    print(f"  RowStruct hash:  {hash_string}")
    print(f"  Pak version:     {pak_version}")
    print(f"  Output pak:      {output_pak_name}")
    print()

    if not os.path.exists(repak_exe):
        which_repak = shutil.which("repak")
        if which_repak:
            repak_exe = which_repak
        else:
            print(f"ERROR: repak.exe not found at {repak_exe}")
            print("Please place repak.exe in the project folder or in system PATH.")
            sys.exit(1)

    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    uasset_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".uasset")]
    if not uasset_files:
        print("No .uasset files found in the input/ folder.")
        print(f"Drop your DataTable .uasset (and .uexp) files into:\n  {INPUT_DIR}")
        sys.exit(0)

    print(f"Found {len(uasset_files)} .uasset file(s) to process:")
    for f in uasset_files:
        print(f"  - {f}")
    print()

    pak_root = os.path.join(SCRIPT_DIR, "_pak_root_tmp")
    if os.path.exists(pak_root):
        shutil.rmtree(pak_root, ignore_errors=True)

    patched_count = 0
    failed_count = 0

    try:
        for uasset_name in uasset_files:
            base_name = os.path.splitext(uasset_name)[0]
            uasset_path = os.path.join(INPUT_DIR, uasset_name)

            print(f"[{base_name}] Processing...")

            with open(uasset_path, "rb") as f:
                data = f.read()

            patched_data, game_path = patch_uasset(bytearray(data), hash_string)
            if patched_data is None:
                print(f"[{base_name}] FAILED - skipping.\n")
                failed_count += 1
                continue

            pak_internal_dir = game_path_to_pak_path(game_path)
            print(f"    Internal pak path: {pak_internal_dir}/")

            target_dir = os.path.join(pak_root, pak_internal_dir)
            os.makedirs(target_dir, exist_ok=True)

            patched_uasset_path = os.path.join(target_dir, uasset_name)
            with open(patched_uasset_path, "wb") as f:
                f.write(patched_data)

            for ext in [".uexp", ".ubulk"]:
                sidecar_name = base_name + ext
                sidecar_path = os.path.join(INPUT_DIR, sidecar_name)
                if os.path.exists(sidecar_path):
                    shutil.copy2(sidecar_path, os.path.join(target_dir, sidecar_name))
                    print(f"    Included {sidecar_name}")

            patched_count += 1
            print(f"[{base_name}] OK\n")

        if patched_count == 0:
            print("No files were successfully patched. Nothing to pack.")
            sys.exit(1)

        output_pak_path = os.path.join(OUTPUT_DIR, output_pak_name)
        if os.path.exists(output_pak_path):
            os.remove(output_pak_path)

        print("-" * 60)
        print(f"Packing {patched_count} DataTable(s) into {output_pak_name}...")
        cmd = [repak_exe, "pack", "--version", pak_version, pak_root, output_pak_path]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stdout:
            print(result.stdout.strip())

        print()
        print("=" * 60)
        print("  SUCCESS!")
        print("=" * 60)
        print()
        print(f"  Patched: {patched_count} file(s)")
        if failed_count > 0:
            print(f"  Failed:  {failed_count} file(s)")
        print(f"  Output:  {output_pak_path}")
        print()
        print("  HOW TO USE IN FMODEL:")
        print("  1. In FModel, go to Settings -> Directory")
        print(f"  2. Add this folder as a directory:\n     {OUTPUT_DIR}")
        print("  3. Load the pak - your DataTable rows will be visible!")
        print()

    except subprocess.CalledProcessError as e:
        print(f"ERROR: repak failed with exit code {e.returncode}")
        if e.stderr:
            print(e.stderr)
        sys.exit(1)
    finally:
        if os.path.exists(pak_root):
            shutil.rmtree(pak_root, ignore_errors=True)


if __name__ == "__main__":
    main()
