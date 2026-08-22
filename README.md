# PUBG DataTable Repaker

A generic binary patcher and repaker for PUBG Unreal Engine 4 `DataTable` assets. Fixes obfuscated `RowStruct` property hashes to make any DataTable readable in **FModel** and **CUE4Parse**.

---

## The Problem

When PUBG updates, the developers periodically obfuscate property names across engine structs. For `UDataTable`, the internal `RowStruct` property name is replaced with a dynamically generated hash (e.g. `*94e90f7066`, `*8148d9ac28`).

Because **CUE4Parse** and **FModel** rely on the literal string `"RowStruct"` to deserialize table rows, opening an affected DataTable yields:

```json
"Properties": {
  "*8148d9ac28": {
    "ObjectName": "ScriptStruct'DBDataRow'",
    "ObjectPath": "/Script/TslGame"
  }
},
"Rows": null
```

Until CUE4Parse's internal name map is updated, the table rows cannot be read.
Once you find the new hash, it is advised to make a PR and update the [CUE4Parse/PUBGNameHashMap](https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/Resources/PUBGNameHashMap.json) to be available for everyone via the FModel.

## The Solution

**PUBG DataTable Repaker** automates the workaround:

1. **Size-Preserving In-Place Patching**: Replaces the obfuscated hash in the `.uasset` binary with the literal `RowStruct`, adjusting string length prefixes and compensating length differences by padding adjacent internal package paths (`/Game/...`). This prevents file offset corruption.
2. **Auto Path Detection**: Parses the internal package path directly from the `.uasset` headers to construct the correct Unreal Engine folder hierarchy (e.g., `TslGame/Content/...`).
3. **Automated Repacking**: Uses `repak` to pack all patched `.uasset`, `.uexp`, and `.ubulk` files into a single patch pak (`patch_DataTable_P.pak`).

---

## Features

- **Generic**: Works with any PUBG DataTable, not just a single asset.
- **Batch Processing**: Place multiple `.uasset` + `.uexp` files in `input/` to pack them all into a single `.pak`.
- **Zero Hex Editing**: No manual byte calculation or hex editing required.
- **Easy Maintenance**: When PUBG updates its hash, change one line in `config.json` and re-run.

---

## Quick Start

### Prerequisites
- Windows 10/11
- Python 3.8+ (ensure Python is added to `PATH`)
- `repak.exe` (included in the repository, or available from [trumank/repak](https://github.com/trumank/repak))

### Usage

1. **Extract** the desired DataTable assets (`.uasset` and `.uexp`) from FModel.
2. **Copy** the extracted files into the `input/` folder.
3. **Run**:
   - **Double-click** `run.bat`, or
   - Run via terminal:
     ```bash
     python repak.py
     ```
4. **Output**: Your patched `.pak` file will be created in `output/patch_DataTable_P.pak`.

### Loading in FModel

1. Open **FModel**.
2. Go to **Settings** -> **Directory**.
3. Add the `output/` folder directory path.
4. Load the archive - DataTable rows will now deserialize and display all data.

---

## Configuration (`config.json`)

```json
{
  "rowstruct_hash": "*8148d9ac28",
  "repak_exe": "repak.exe",
  "pak_version": "V9",
  "output_pak_name": "patch_DataTable_P.pak"
}
```

| Setting | Description |
|---|---|
| `rowstruct_hash` | The current obfuscated hash for `RowStruct`. Accepts `*hash`, `_hash`, or raw hash. |
| `repak_exe` | Path or command for the `repak` CLI binary. |
| `pak_version` | Unreal Engine pak format version. |
| `output_pak_name` | Name of the output `.pak` archive (keep `_P.pak` suffix for patch priority). |

---

## How to Find the New Hash After Game Updates

When PUBG releases a patch and DataTable stop showing rows:

1. **Via FModel Export**:
   - Export any DataTable to JSON.
   - Look inside `"Properties"`. The key pointing to `ScriptStruct` is the new hash (e.g., `"*8148d9ac28"`).

2. **Via C++ SDK Dump**:
   - Open `Engine_classes.h` in your SDK dump.
   - Locate `struct UDataTable : UObject`.
   - Find the property of type `UScriptStruct*` (e.g. `UScriptStruct* _8148d9ac28;`).
   - Replace the leading `_` with `*` (`*8148d9ac28`).

3. Update `"rowstruct_hash"` in `config.json` and re-run.

---

## Repository Structure

```
PUBG-DataTable-Repaker/
├── config.json          # Configuration file for current hash & pak settings
├── repak.py             # Main Python patcher & repak pipeline
├── repak.exe            # Unreal Engine pak packaging utility
├── run.bat              # One-click Windows runner
├── input/               # Drop raw .uasset / .uexp files here
├── output/              # Patched .pak output destination
├── .gitignore
├── LICENSE
└── README.md
```

---

## Acknowledgments

- [repak](https://github.com/trumank/repak) by trumank - High-performance Unreal Engine `.pak` CLI tool.
- [CUE4Parse](https://github.com/FabianFG/CUE4Parse) by FabianFG - Unreal Engine asset parsing library.
- [FModel](https://github.com/4sval/FModel) by 4sval - Unreal Engine archive explorer.

---

## License

This project is licensed under the [MIT License](LICENSE).
