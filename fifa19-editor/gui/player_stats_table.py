"""Compact table of all players with core ability values — includes name editing.

Displays every player as a row with columns:
  ID | Name | Nation | Common | OVR | POT | POS | (all sofifa ability values)

💡 Double-click **Name** or **Nation** cell to edit — changes auto-save to CSV.
"""

from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
import csv

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableView, QFrame, QHeaderView, QAbstractItemView, QComboBox,
    QCheckBox,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QModelIndex, Signal
from PySide6.QtGui import QColor, QBrush

from core.table import Table
from core.name_resolver import NameResolver
from core.nationality_lookup import get_nationality_name, save_nationality_name


# ── Column definitions: (field_key, display_header) ──────────────────────
# "_name" is a synthetic key for the resolved player name (not a raw field).
STATS_COLUMNS = [
    ("playerid",            "ID"),
    ("_name",              "Name"),
    ("_nation",            "Nation"),
    ("_common",            "Common"),
    ("overallrating",       "OVR"),
    ("potential",           "POT"),
    ("preferredposition1",  "POS"),
    # ── Attacking ──
    ("crossing",            "Crossing"),
    ("finishing",           "Finishing"),
    ("headingaccuracy",     "Heading Acc"),
    ("shortpassing",        "Short Pass"),
    ("volleys",             "Volleys"),
    # ── Skill ──
    ("dribbling",           "Dribbling"),
    ("curve",               "Curve"),
    ("freekickaccuracy",    "FK Acc"),
    ("longpassing",         "Long Pass"),
    ("ballcontrol",         "Ball Control"),
    # ── Movement ──
    ("acceleration",        "Acceleration"),
    ("sprintspeed",         "Sprint Speed"),
    ("agility",             "Agility"),
    ("reactions",           "Reactions"),
    ("balance",             "Balance"),
    # ── Power ──
    ("shotpower",           "Shot Power"),
    ("jumping",             "Jumping"),
    ("stamina",             "Stamina"),
    ("strength",            "Strength"),
    ("longshots",           "Long Shots"),
    # ── Mentality ──
    ("aggression",          "Aggression"),
    ("interceptions",       "Interceptions"),
    ("positioning",         "Att. Position"),
    ("vision",              "Vision"),
    ("penalties",           "Penalties"),
    ("composure",           "Composure"),
    # ── Defending ──
    ("marking",             "Marking"),
    ("standingtackle",      "Standing Tackle"),
    ("slidingtackle",       "Sliding Tackle"),
    # ── Goalkeeping ──
    ("gkdiving",            "GK Diving"),
    ("gkhandling",          "GK Handling"),
    ("gkkicking",           "GK Kicking"),
    ("gkpositioning",       "GK Positioning"),
    ("gkreflexes",          "GK Reflexes"),
]

POSITION_NAMES = {
    0: "GK", 1: "SW", 2: "RWB", 3: "RB", 4: "CB", 5: "LB",
    6: "LWB", 7: "CDM", 8: "RM", 9: "CM", 10: "LM",
    11: "CAM", 12: "RF", 13: "CF", 14: "LF", 15: "RW",
    16: "ST", 17: "LW",
}


class PlayerStatsModel(QAbstractTableModel):
    """Flat table model: one row per player, fixed columns."""

    name_edited = Signal(int, int, str)  # source_row, playerid, new_name
    nation_edited = Signal(int, int, str)  # source_row, playerid, new_nation_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[List[Any]] = []    # row-major data
        self._headers: List[str] = []
        self._col_keys: List[str] = []      # field key for each column
        self._player_ids: List[int] = []    # playerid for each row (for CSV saving)
        self._source_rows: List[int] = []   # original row index in table.records
        self._genders: List[int] = []       # 0=male, 1=female

    def load(self, table: Table, resolver: NameResolver):
        """Build the model from the CZUM players table."""
        self.beginResetModel()
        self._headers = [h for _, h in STATS_COLUMNS]
        self._col_keys = [k for k, _ in STATS_COLUMNS]
        self._rows = []
        self._player_ids = []
        self._source_rows = []
        self._genders = []

        num_cols = len(STATS_COLUMNS)

        for src_idx, rec in enumerate(table.records):
            pid = rec.get("playerid", 0)
            if pid <= 0:
                continue

            row = [None] * num_cols

            for ci, (key, _) in enumerate(STATS_COLUMNS):
                if key == "_name":
                    row[ci] = resolver.get_name(rec)
                elif key == "_nation":
                    raw = rec.get("nationality", 0)
                    if isinstance(raw, int):
                        row[ci] = get_nationality_name(raw)
                    else:
                        row[ci] = str(raw)
                elif key == "_common":
                    cnid = rec.get("commonnameid", 0) or 0
                    if cnid > 0 and cnid in resolver._dc_names:
                        row[ci] = resolver._dc_names.get(cnid, "")
                    elif pid in resolver._csv_common_names:
                        row[ci] = resolver._csv_common_names[pid]
                    else:
                        row[ci] = ""
                elif key == "preferredposition1":
                    raw = rec.get(key)
                    if isinstance(raw, int) and raw in POSITION_NAMES:
                        row[ci] = POSITION_NAMES[raw]
                    else:
                        row[ci] = raw
                else:
                    row[ci] = rec.get(key)

            self._rows.append(row)
            self._player_ids.append(pid)
            self._source_rows.append(src_idx)
            self._genders.append(rec.get("gender", 0) or 0)

        self.endResetModel()

    # ── QAbstractTableModel interface ──

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        elif orientation == Qt.Vertical and role == Qt.DisplayRole:
            # Row numbers (1-based)
            return section + 1
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row >= len(self._rows) or col >= len(self._headers):
            return None
        val = self._rows[row][col]

        if role == Qt.DisplayRole:
            return val

        if role == Qt.EditRole and self._col_keys[col] in ("_name", "_nation"):
            return val  # return current value for editing

        if role == Qt.TextAlignmentRole:
            # Left-align text columns, center numeric
            key = self._col_keys[col]
            if key in ("_name", "_nation"):
                return int(Qt.AlignLeft | Qt.AlignVCenter)
            return int(Qt.AlignCenter)

        # Colored font for unresolved / missing cells
        if role == Qt.ForegroundRole:
            key = self._col_keys[col]
            if key == "_name" and val and "Player" in str(val):
                return QBrush(QColor("#3a7bd5"))  # blue: placeholder name
            if key == "_nation" and val and str(val).isdigit():
                return QBrush(QColor("#3a7bd5"))  # blue: raw nationality ID
            if key == "_common" and (not val or not str(val).strip()):
                return QBrush(QColor("#aaaaaa"))  # gray: no common name available

        return None

    def flags(self, index) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        # Name and Nation columns are editable
        if self._col_keys[index.column()] in ("_name", "_nation"):
            flags |= Qt.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        row, col = index.row(), index.column()
        key = self._col_keys[col]
        if key not in ("_name", "_nation"):
            return False
        if not value or not str(value).strip():
            return False
        new_val = str(value).strip()
        old_val = self._rows[row][col]
        if new_val == old_val:
            return False

        self._rows[row][col] = new_val
        pid = self._player_ids[row]
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        if key == "_name":
            self.name_edited.emit(self._source_rows[row], pid, new_val)
        else:
            self.nation_edited.emit(self._source_rows[row], pid, new_val)
        return True

    def get_gender(self, row: int) -> int:
        """Return gender for row: 0=male, 1=female."""
        if 0 <= row < len(self._genders):
            return self._genders[row]
        return 0


class StatsSortProxy(QSortFilterProxyModel):
    """Filter proxy that searches across all columns + gender filtering."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""
        self._column_filter = -1
        self._hide_female = True
        self._nation_filter = ""  # empty = show all nations

    def set_filter_text(self, text: str):
        self._filter_text = text.lower().strip()
        self.invalidateFilter()

    def set_column_filter(self, col: int):
        self._column_filter = col
        self.invalidateFilter()

    def set_hide_female(self, hide: bool):
        self._hide_female = hide
        self.invalidateFilter()

    def set_nation_filter(self, nation: str):
        self._nation_filter = nation
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent) -> bool:
        model = self.sourceModel()
        if not model:
            return True

        # Gender filter
        if self._hide_female and hasattr(model, 'get_gender'):
            if model.get_gender(source_row) == 1:
                return False

        # Nation filter
        if self._nation_filter:
            nat_col = None
            for i, key in enumerate(model._col_keys):
                if key == "_nation":
                    nat_col = i
                    break
            if nat_col is not None:
                idx = model.index(source_row, nat_col, source_parent)
                val = model.data(idx, Qt.DisplayRole)
                if val is None or str(val) != self._nation_filter:
                    return False

        # Text search filter
        if not self._filter_text:
            return True
        cols = (
            range(model.columnCount())
            if self._column_filter < 0
            else [self._column_filter]
        )
        for ci in cols:
            idx = model.index(source_row, ci, source_parent)
            val = model.data(idx, Qt.DisplayRole)
            if val is not None and self._filter_text in str(val).lower():
                return True
        return False


class PlayerStatsTable(QWidget):
    """Table with inline-editable Name column — changes auto-save to player_names.csv."""

    def __init__(self, players_table: Table, resolver: NameResolver, parent=None):
        super().__init__(parent)
        self._resolver = resolver
        self._players_table = players_table
        self._csv_path = (
            Path(__file__).resolve().parent.parent / "data" / "player_names.csv"
        )

        self._source_model = PlayerStatsModel()
        self._source_model.load(players_table, resolver)
        self._source_model.name_edited.connect(self._on_name_edited)
        self._source_model.nation_edited.connect(self._on_nation_edited)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── Toolbar ──
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("<b>Player Stats Table</b>  —  all players with core abilities")
        title.setStyleSheet("font-size: 14px;")
        toolbar_layout.addWidget(title)

        # Editable hint
        edit_hint = QLabel("✏️ Double-click Name / Nation to edit")
        edit_hint.setStyleSheet("color: #4a90d9; font-size: 11px; padding: 2px 8px; "
                                "background: #e8f0fe; border-radius: 3px;")
        toolbar_layout.addWidget(edit_hint)

        toolbar_layout.addStretch()

        toolbar_layout.addWidget(QLabel("Search:"))
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter by any column…")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumWidth(200)
        self._search_input.textChanged.connect(self._on_search)
        toolbar_layout.addWidget(self._search_input)

        toolbar_layout.addWidget(QLabel("Column:"))
        self._column_combo = QComboBox()
        self._column_combo.addItem("All columns", -1)
        for ci, (key, header) in enumerate(STATS_COLUMNS):
            if key not in ("_name", "_nation", "_common"):
                self._column_combo.addItem(header, ci)
        self._column_combo.currentIndexChanged.connect(self._on_column_filter)
        toolbar_layout.addWidget(self._column_combo)

        # Nation filter dropdown
        toolbar_layout.addWidget(QLabel("Nation:"))
        self._nation_combo = QComboBox()
        self._nation_combo.addItem("All nations", "")
        self._nation_combo.setMinimumWidth(120)
        nations = set()
        nat_col = self._source_model._col_keys.index("_nation")
        for r in range(self._source_model.rowCount()):
            nat = self._source_model.data(self._source_model.index(r, nat_col))
            if nat:
                nations.add(str(nat))
        for n in sorted(nations, key=lambda v: (v.isdigit(), v)):
            self._nation_combo.addItem(n, n)
        self._nation_combo.currentIndexChanged.connect(self._on_nation_filter)
        toolbar_layout.addWidget(self._nation_combo)

        # Gender filter
        self._gender_cb = QCheckBox("Hide women")
        self._gender_cb.setChecked(True)
        self._gender_cb.setStyleSheet("font-size: 12px; color: #555; margin-left: 8px;")
        self._gender_cb.toggled.connect(self._on_gender_toggle)
        toolbar_layout.addWidget(self._gender_cb)

        # Record count
        self._count_label = QLabel(f"{self._source_model.rowCount():,} players")
        self._count_label.setStyleSheet("color: #666; font-size: 12px; margin-left: 8px;")
        toolbar_layout.addWidget(self._count_label)

        layout.addWidget(toolbar)

        # ── Separator ──
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # ── Table view ──
        self._table_view = QTableView()
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSortingEnabled(True)
        self._table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table_view.setEditTriggers(QAbstractItemView.DoubleClicked)  # edit Name by double-click
        self._table_view.horizontalHeader().setStretchLastSection(False)
        self._table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table_view.horizontalHeader().setDefaultSectionSize(70)
        self._table_view.verticalHeader().setDefaultSectionSize(22)
        self._table_view.verticalHeader().hide()  # hide row numbers (too much clutter)
        self._table_view.setStyleSheet(
            "QTableView { font-size: 11px; }"
            "QHeaderView::section { font-size: 10px; padding: 2px 4px; }"
        )

        # Column-specific widths
        header = self._table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # ID
        header.setSectionResizeMode(1, QHeaderView.Interactive)        # Name
        self._table_view.setColumnWidth(1, 160)                         # Name default
        for ci in range(2, len(STATS_COLUMNS)):
            header.setSectionResizeMode(ci, QHeaderView.ResizeToContents)

        # ── Proxy for sorting/filtering ──
        self._proxy = StatsSortProxy()
        self._proxy.setSourceModel(self._source_model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._table_view.setModel(self._proxy)

        layout.addWidget(self._table_view)

    def _save_name_to_csv(self, playerid: int, name: str):
        """Append or update an entry in player_names.csv."""
        if not self._csv_path:
            return
        rows = []
        found = False
        # Read existing CSV
        if self._csv_path.exists():
            try:
                with self._csv_path.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames or ["playerid", "display_name", "common_name", "source"]
                    for row in reader:
                        if row.get("playerid", "").strip() == str(playerid):
                            row["display_name"] = name
                            row["common_name"] = name
                            found = True
                        rows.append(row)
            except Exception:
                rows = []
                found = False
        if not found:
            rows.append({
                "playerid": str(playerid),
                "display_name": name,
                "common_name": name,
                "source": "user",
            })
        # Write back
        try:
            self._csv_path.parent.mkdir(parents=True, exist_ok=True)
            with self._csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["playerid", "display_name", "common_name", "source"])
                writer.writeheader()
                writer.writerows(rows)
        except Exception:
            pass  # Silently fail — next session will miss this name

    def _on_name_edited(self, source_row: int, playerid: int, new_name: str):
        """Handle a user-edited name: save to CSV and update resolver in-memory."""
        self._save_name_to_csv(playerid, new_name)
        self._resolver._csv_names[playerid] = new_name

    def _on_nation_edited(self, source_row: int, playerid: int, new_nation: str):
        """Handle a user-edited Nation: persist to nationality_names.csv."""
        for rec in self._players_table.records:
            if rec.get("playerid") == playerid:
                nid = rec.get("nationality", 0)
                if isinstance(nid, int) and nid > 0:
                    save_nationality_name(nid, new_nation)
                break

    def _on_search(self, text: str):
        self._proxy.set_filter_text(text)
        self._update_count()

    def _on_column_filter(self, idx: int):
        col = self._column_combo.itemData(idx)
        self._proxy.set_column_filter(col if col is not None else -1)
        self._proxy.invalidateFilter()

    def _on_gender_toggle(self, checked: bool):
        """Toggle female player filtering."""
        self._proxy.set_hide_female(checked)
        self._update_count()

    def _on_nation_filter(self, idx: int):
        """Filter by selected nation."""
        nation = self._nation_combo.itemData(idx)
        self._proxy.set_nation_filter(nation if nation else "")
        self._update_count()

    def _update_count(self):
        """Update the player count label."""
        total = self._source_model.rowCount()
        shown = self._proxy.rowCount()
        self._count_label.setText(f"{shown:,} / {total:,} players")
