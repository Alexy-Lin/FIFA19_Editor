"""Nationality ID ↔ name lookup, backed by CSV for persistence.

FIFA stores nationality as an integer ID (field `enmm` / `nationality`).
The nations table (`Crbb`) exists in the RDBM template DB (218 entries) but
not in squad save files, so mappings use a static CSV extracted from the
template DB + a user-override CSV.

Editing the Nation column in the Player Stats table auto-saves to the
user-override CSV.
"""

import csv
from pathlib import Path
from typing import Dict

# Primary data: 218 nations extracted from RDBM template DB
_NATIONS_CSV = Path(__file__).resolve().parent.parent / "data" / "nations.csv"

# User override CSV (auto-saved when editing Nation in Player Stats)
_OVERRIDE_CSV = Path(__file__).resolve().parent.parent / "data" / "nationality_names.csv"


def _load_base() -> Dict[int, str]:
    """Load nation names from nations.csv (extracted from template DB)."""
    mapping: Dict[int, str] = {}
    if _NATIONS_CSV.exists():
        try:
            with _NATIONS_CSV.open("r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    nid = (row.get("nationid") or "").strip()
                    name = (row.get("nationname") or "").strip()
                    if nid.isdigit() and name:
                        mapping[int(nid)] = name
        except Exception:
            pass
    return mapping


def _load_overrides() -> Dict[int, str]:
    """Load user-edited nationality names from override CSV."""
    mapping: Dict[int, str] = {}
    if _OVERRIDE_CSV.exists():
        try:
            with _OVERRIDE_CSV.open("r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    nid = (row.get("nationid") or "").strip()
                    name = (row.get("display_name") or "").strip()
                    if nid.isdigit() and name:
                        mapping[int(nid)] = name
        except Exception:
            pass
    return mapping


# Runtime mapping: base + user overrides
_mapping: Dict[int, str] = {**_load_base(), **_load_overrides()}


def get_nationality_name(nation_id: int) -> str:
    """Return the country name for a FIFA nationality ID, or raw ID as fallback."""
    return _mapping.get(nation_id, str(nation_id))


def get_nation_dict() -> Dict[int, str]:
    """Return the full nation mapping dict."""
    return dict(_mapping)


def save_nationality_name(nation_id: int, name: str) -> None:
    """Persist a nation ID -> name mapping to override CSV and update runtime."""
    _mapping[nation_id] = name

    rows: list[dict] = []
    found = False
    if _OVERRIDE_CSV.exists():
        try:
            with _OVERRIDE_CSV.open("r", encoding="utf-8") as f:
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
        _OVERRIDE_CSV.parent.mkdir(parents=True, exist_ok=True)
        with _OVERRIDE_CSV.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["nationid", "display_name"])
            writer.writeheader()
            writer.writerows(rows)
    except Exception:
        pass
