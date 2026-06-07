"""Nationality ID ↔ name lookup, backed by CSV for persistence.

FIFA stores nationality as an integer ID (field `enmm` / `nationality`).
The nations table (`Crbb`) exists in the main game DB but not in squad save
files, so mappings use a static CSV + a built-in fallback dict.

Editing the Nation column in the Player Stats table auto-saves to the CSV.
"""

import csv
from pathlib import Path
from typing import Dict

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "nationality_names.csv"

# ── Built-in fallback (verified against editedplayernames in save file) ───
_HARDCODED: Dict[int, str] = {
    3: "Armenia",
    7: "Belgium",
    8: "Bosnia & Herz.",
    9: "Bulgaria",
    10: "Croatia",
    12: "Czech Republic",
    13: "Denmark",
    14: "England",
    17: "Finland",
    18: "France",
    20: "Georgia",
    21: "Germany",
    25: "Ireland",
    27: "Italy",
    34: "Netherlands",
    35: "Northern Ireland",
    36: "Norway",
    38: "Portugal",
    39: "Romania",
    40: "Russia",
    42: "Scotland",
    45: "Spain",
    46: "Sweden",
    49: "Ukraine",
    50: "Wales",
    51: "Serbia",
    52: "Argentina",
    54: "Brazil",
    55: "Chile",
    56: "Colombia",
    57: "Ecuador",
    60: "Uruguay",
    83: "Mexico",
    95: "United States",
    103: "Cameroon",
    108: "Ivory Coast",
    117: "Ghana",
    129: "Morocco",
    133: "Nigeria",
    163: "Japan",
    167: "South Korea",
}


def _load_csv() -> Dict[int, str]:
    """Load nationality names from CSV (overrides built-in defaults)."""
    mapping: Dict[int, str] = {}
    if CSV_PATH.exists():
        try:
            with CSV_PATH.open("r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    pid_str = (row.get("nationid") or "").strip()
                    name = (row.get("display_name") or "").strip()
                    if pid_str.isdigit() and name:
                        mapping[int(pid_str)] = name
        except Exception:
            pass
    return mapping


# ── Runtime mapping: CSV overrides hardcoded defaults ────────────────────
_mapping: Dict[int, str] = {**_HARDCODED, **_load_csv()}


def get_nationality_name(nation_id: int) -> str:
    """Return the country name for a FIFA nationality ID, or raw ID as fallback."""
    return _mapping.get(nation_id, str(nation_id))


def save_nationality_name(nation_id: int, name: str) -> None:
    """Persist a nation ID → name mapping to CSV and update runtime mapping."""
    _mapping[nation_id] = name

    # Read existing CSV and update/add this entry
    rows: list[dict] = []
    found = False
    if CSV_PATH.exists():
        try:
            with CSV_PATH.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row.get("nationid") or "").strip() == str(nation_id):
                        row["display_name"] = name
                        found = True
                    rows.append(row)
        except Exception:
            rows = []
            found = False

    if not found:
        rows.append({"nationid": str(nation_id), "display_name": name})

    try:
        CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["nationid", "display_name"])
            writer.writeheader()
            writer.writerows(rows)
    except Exception:
        pass
