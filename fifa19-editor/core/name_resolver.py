"""Player name resolver — builds lookup tables from available name sources."""
import csv
from pathlib import Path
from typing import Dict, Optional

from .table import Table
from .db_file import DbFile


class NameResolver:
    """Resolves player names from available data sources in the save file.

    Sources (in priority order):
      1. editedplayernames:  playerid → firstname/surname (from save file, ~300 players)
      2. dcplayernames:      nameid → name string (2862 entries, shared across players)
      3. player_names.csv:   static CSV file with player ID → display name mappings
      4. commonnameid fallback:  look up in dcplayernames
      5. Fallback: "Player #{pid}"
    """

    def __init__(self, db: DbFile):
        self._edited: Dict[int, tuple[str, str, str]] = {}  # pid -> (first, last, jersey)
        self._dc_names: Dict[int, str] = {}  # nameid -> best name string
        self._csv_names: Dict[int, str] = {}  # pid -> display_name (from CSV)
        self._csv_common_names: Dict[int, str] = {}  # pid -> common_name (from common_names.csv)

        # Build editedplayernames lookup
        et = db.get_table("nQVU")
        if et:
            for r in et.records:
                pid = r.get("playerid", 0)
                first = r.get("firstname", "") or ""
                last = r.get("surname", "") or ""
                jersey = r.get("playerjerseyname", "") or ""
                if pid > 0 and (first or last):
                    self._edited[pid] = (first, last, jersey)

        # Build dcplayernames lookup (first occurrence per nameid)
        dt = db.get_table("bneD")
        if dt:
            seen_ids = set()
            for r in dt.records:
                nid = r.get("nameid", 0)
                name_str = r.get("name", "") or ""
                if nid > 0 and name_str and nid not in seen_ids:
                    self._dc_names[nid] = name_str
                    seen_ids.add(nid)

        # Build CSV name lookup from the static player_names.csv file
        csv_path = Path(__file__).resolve().parent.parent / "data" / "player_names.csv"
        if csv_path.exists():
            try:
                with csv_path.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        pid_str = (row.get("playerid") or "").strip()
                        display_name = (row.get("display_name") or "").strip()
                        if pid_str.isdigit() and display_name:
                            self._csv_names[int(pid_str)] = display_name
            except Exception:
                pass

        # Build common name lookup from common_names.csv (Icon short names)
        common_csv = Path(__file__).resolve().parent.parent / "data" / "common_names.csv"
        if common_csv.exists():
            try:
                with common_csv.open("r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        pid_str = (row.get("playerid") or "").strip()
                        name = (row.get("common_name") or "").strip()
                        if pid_str.isdigit() and name:
                            self._csv_common_names[int(pid_str)] = name
            except Exception:
                pass

    def get_name(self, record: dict) -> str:
        """Build the best possible display name for a player record."""
        pid = record.get("playerid", 0)

        # 1. CSV name lookup (user-curated, overrides in-game edited names)
        if pid in self._csv_names:
            return self._csv_names[pid]

        # 2. Edited name (from save file's editedplayernames)
        if pid in self._edited:
            first, last, jersey = self._edited[pid]
            display = f"{first} {last}".strip()
            if not display:
                display = jersey
            return display

        # 3. Try commonnameid -> dcplayernames
        cnid = record.get("commonnameid", 0)
        if cnid > 0 and cnid in self._dc_names:
            return self._dc_names.get(cnid, "")

        # 4. Try firstnameid + lastnameid -> dcplayernames
        fnid = record.get("firstnameid", 0) or 0
        lnid = record.get("lastnameid", 0) or 0
        first = self._dc_names.get(fnid, "") if fnid > 0 else ""
        last = self._dc_names.get(lnid, "") if lnid > 0 else ""
        if first and last:
            return f"{first} {last}"
        if last:
            return last
        if first:
            return first

        # 5. Fallback
        return f"Player #{pid}"

    def get_name_by_player_id(self, playerid: int) -> str:
        """Get display name for a player by ID."""
        if playerid in self._edited:
            first, last, jersey = self._edited[playerid]
            display = f"{first} {last}".strip()
            return display or jersey or f"Player #{playerid}"
        if playerid in self._csv_names:
            return self._csv_names[playerid]
        return f"Player #{playerid}"

    def search(self, query: str, players_table: Table) -> list[int]:
        """Search players by name or playerid.

        Returns matching playerids.
        """
        results = set()
        q = query.lower().strip()

        for r in players_table.records:
            pid = r.get("playerid", 0)
            if q.isdigit() and pid == int(q):
                return [pid]
            name = self.get_name(r)
            if q in name.lower():
                results.add(pid)

        return sorted(results)
