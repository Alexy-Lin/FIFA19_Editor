"""FIFA 19 Save Editor — CLI tool to read and display/export squad file contents.

Usage:
    python main.py <path_to_sav_file>                  # Display summary only
    python main.py <path_to_sav_file> --export <xlsx>  # Export all tables to Excel
    python main.py <path_to_sav_file> --export-players <xlsx>  # Export only players table
    python main.py <path_to_sav_file> --player <id>    # Display a player's stats

Example:
    python main.py ../Squads20260423210221 --export ../squad.xlsx
    python main.py ../Squads20260423210221 --player 20801
"""

import sys
import time
from pathlib import Path

# Allow running from the project directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.sav_file import SavFile
from core.meta_parser import MetaDatabase
from core.exporter import export_to_excel
from core.name_resolver import NameResolver


META_XML_PATH = Path(__file__).resolve().parent.parent / "fifa_ng_db-meta.xml"


# Sofifa-style attribute groupings for player display
SOFIFA_GROUPS = [
    ("Attacking", [
        ("crossing", "Crossing"),
        ("finishing", "Finishing"),
        ("headingaccuracy", "Heading Accuracy"),
        ("shortpassing", "Short Passing"),
        ("volleys", "Volleys"),
    ]),
    ("Skill", [
        ("dribbling", "Dribbling"),
        ("curve", "Curve"),
        ("freekickaccuracy", "FK Accuracy"),
        ("longpassing", "Long Passing"),
        ("ballcontrol", "Ball Control"),
    ]),
    ("Movement", [
        ("acceleration", "Acceleration"),
        ("sprintspeed", "Sprint Speed"),
        ("agility", "Agility"),
        ("reactions", "Reactions"),
        ("balance", "Balance"),
    ]),
    ("Power", [
        ("shotpower", "Shot Power"),
        ("jumping", "Jumping"),
        ("stamina", "Stamina"),
        ("strength", "Strength"),
        ("longshots", "Long Shots"),
    ]),
    ("Mentality", [
        ("aggression", "Aggression"),
        ("interceptions", "Interceptions"),
        ("positioning", "Attack Position"),
        ("vision", "Vision"),
        ("penalties", "Penalties"),
        ("composure", "Composure"),
    ]),
    ("Defending", [
        ("marking", "Marking"),
        ("standingtackle", "Standing Tackle"),
        ("slidingtackle", "Sliding Tackle"),
    ]),
    ("Goalkeeping", [
        ("gkdiving", "GK Diving"),
        ("gkhandling", "GK Handling"),
        ("gkkicking", "GK Kicking"),
        ("gkpositioning", "GK Positioning"),
        ("gkreflexes", "GK Reflexes"),
    ]),
]

POSITION_NAMES = {
    0: "GK", 1: "SW", 2: "RWB", 3: "RB", 4: "CB", 5: "LB",
    6: "LWB", 7: "CDM", 8: "RM", 9: "CM", 10: "LM",
    11: "CAM", 12: "RF", 13: "CF", 14: "LF", 15: "RW",
    16: "ST", 17: "LW",
}


def print_summary(sav: SavFile):
    """Print file overview and sample data."""
    print(f"\n{sav.summary()}")

    key_tables = [("players", "CZUM"), ("teams", "lyxL"), ("teamplayerlinks", "RrqT")]
    for long_name, short_name in key_tables:
        table = sav.db.get_table(short_name) if sav.db else None
        if table and table.records:
            print(f"\n{'='*60}")
            print(f"Table: {table.long_name} ({short_name})")
            print(f"  Fields: {len(table.fields)}, Records: {len(table.records)}")
            print(f"  Sample records (first 5):")
            for i, record in enumerate(table.records[:5]):
                key_fields = [
                    k for k in record if record[k] not in (0, "", None)
                ][:8]
                parts = [f"{k}={record[k]}" for k in key_fields]
                print(f"    [{i}] " + ", ".join(parts))


def print_player(sav: SavFile, meta_db: MetaDatabase, player_id: int):
    """Display a single player's stats grouped by sofifa-style categories."""
    players_table = sav.db.get_table("CZUM") if sav.db else None
    if not players_table:
        print("Error: Players table not found in save file.")
        return

    # Find the player record
    player_record = None
    for rec in players_table.records:
        if rec.get("playerid") == player_id:
            player_record = rec
            break

    if player_record is None:
        print(f"Error: Player ID {player_id} not found.")
        return

    resolver = NameResolver(sav.db)
    name = resolver.get_name(player_record)

    # Header
    ovr = player_record.get("overallrating", "?")
    pot = player_record.get("potential", "?")
    pos_code = player_record.get("preferredposition1", 0)
    pos_name = POSITION_NAMES.get(pos_code, str(pos_code)) if isinstance(pos_code, int) else str(pos_code)
    foot_code = player_record.get("preferredfoot", 0)
    foot = "Right" if foot_code == 1 else "Left" if foot_code == 2 else str(foot_code)
    birthdate_val = player_record.get("birthdate", 0)
    if birthdate_val and birthdate_val > 0:
        age = max(15, birthdate_val // 365)
        # Clamp to reasonable range (known limitation: date encoding not fully decoded)
        if age > 60:
            age = "?"
    else:
        age = "?"
    height = player_record.get("height", 0)
    weight = player_record.get("weight", 0)

    print()
    print("=" * 60)
    print(f"  {name}  (ID={player_id})")
    print(f"  OVR={ovr}  |  POT={pot}  |  POS={pos_name}  |  AGE={age}  |  FOOT={foot}")
    if height:
        print(f"  Height={height} cm  |  Weight={weight} kg")
    print("=" * 60)
    print()

    for group_name, fields in SOFIFA_GROUPS:
        # Collect (label, value) pairs for this group
        entries = []
        for field_name, label in fields:
            val = player_record.get(field_name)
            if val is not None:
                entries.append((label, val))
        if not entries:
            continue

        # Build formatted output for this group
        print(f"  {group_name}")
        max_label_len = max(len(label) for label, _ in entries)
        for label, val in entries:
            padded_label = label.rjust(max_label_len)
            print(f"    {padded_label}    {val}")
        print()

    print("=" * 60)
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    sav_path = Path(sys.argv[1])
    if not sav_path.exists():
        print(f"Error: File not found: {sav_path}")
        sys.exit(1)

    # Parse flags
    export_path = None
    export_players_only = False
    show_player_id = None
    remaining = sys.argv[2:]
    while remaining:
        arg = remaining.pop(0)
        if arg == "--export" and remaining:
            export_path = Path(remaining.pop(0))
        elif arg == "--export-players" and remaining:
            export_path = Path(remaining.pop(0))
            export_players_only = True
        elif arg == "--player" and remaining:
            pid_str = remaining.pop(0)
            try:
                show_player_id = int(pid_str)
            except ValueError:
                print(f"Error: Invalid player ID: {pid_str}")
                sys.exit(1)
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)

    print(f"Loading meta XML: {META_XML_PATH}")
    t0 = time.time()
    meta_db = MetaDatabase.from_file(META_XML_PATH)
    print(f"  Parsed {len(meta_db.tables)} table definitions ({time.time()-t0:.1f}s)")

    print(f"\nLoading SAV file: {sav_path}")
    t0 = time.time()
    sav = SavFile()
    sav.load(sav_path, meta_db)
    print(f"  Loaded {len(sav.db.tables)} tables ({time.time()-t0:.1f}s)")

    if export_path:
        filter_set = {"CZUM"} if export_players_only else None
        print(f"\nExporting to {export_path} ...")
        t0 = time.time()
        export_to_excel(sav, export_path, tables_filter=filter_set)
        print(f"Export finished ({time.time()-t0:.1f}s)")
    elif show_player_id is not None:
        print_player(sav, meta_db, show_player_id)
    else:
        print_summary(sav)


if __name__ == "__main__":
    main()
