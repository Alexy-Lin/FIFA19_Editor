"""Player search and attribute editor widget.

Search workflow:
  1. Type a player ID → exact match, jump straight to editing
  2. Type a name → fuzzy match against available name data (limited — only ~300 named players)
  3. Browse recent/default results
"""

from typing import Optional, List, Tuple, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QScrollArea,
    QFormLayout, QSpinBox, QDoubleSpinBox,
    QGroupBox, QMessageBox, QFrame, QGridLayout,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from core.table import Table
from core.field_descriptor import FieldDescriptor
from core.name_resolver import NameResolver


# Attribute categories for the form layout (sofifa-style grouping)
ATTRIBUTE_CATEGORIES = [
    ("Identity", [
        ("playerid", "Player ID"),
        ("firstnameid", "First Name ID"),
        ("lastnameid", "Last Name ID"),
        ("commonnameid", "Common Name ID"),
        ("playerjerseynameid", "Jersey Name ID"),
    ]),
    ("Rating", [
        ("overallrating", "Overall Rating"),
        ("potential", "Potential"),
        ("modifier", "Form Modifier"),
        ("internationalrep", "International Rep"),
    ]),
    ("Position / Work Rate", [
        ("preferredposition1", "Main Position"),
        ("preferredposition2", "Alt Position 1"),
        ("preferredposition3", "Alt Position 2"),
        ("preferredposition4", "Alt Position 3"),
        ("preferredfoot", "Preferred Foot"),
        ("skillmoves", "Skill Moves"),
        ("weakfootabilitytypecode", "Weak Foot"),
        ("attackingworkrate", "Att. Work Rate"),
        ("defensiveworkrate", "Def. Work Rate"),
    ]),
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
    ("Biometrics", [
        ("height", "Height (cm)"),
        ("weight", "Weight (kg)"),
        ("birthdate", "Birthdate"),
        ("nationality", "Nationality ID"),
        ("bodytypecode", "Body Type"),
    ]),
]


POSITION_NAMES = {
    0: "GK", 1: "SW", 2: "RWB", 3: "RB", 4: "CB", 5: "LB",
    6: "LWB", 7: "CDM", 8: "RM", 9: "CM", 10: "LM",
    11: "CAM", 12: "RF", 13: "CF", 14: "LF", 15: "RW",
    16: "ST", 17: "LW",
}

WEAK_FOOT = {1: "★", 2: "★★", 3: "★★★", 4: "★★★★", 5: "★★★★★"}
SKILL_MOVES = {0: "☆", 1: "★", 2: "★★", 3: "★★★", 4: "★★★★", 5: "★★★★★"}
WORK_RATE = {0: "Low", 1: "Medium", 2: "High"}
FOOT = {1: "Right", 2: "Left"}


class PlayerEditor(QWidget):
    """Search players → select → view and edit attributes in a clean form."""

    player_edited = Signal(int)  # emitted with playerid when changes applied

    def __init__(self, players_table: Table, name_resolver: NameResolver):
        super().__init__()
        self._table = players_table
        self._records = players_table.records
        self._name_resolver = name_resolver

        # Build field lookup by name
        self._fields: Dict[str, FieldDescriptor] = {}
        for fd in players_table.fields:
            key = fd.field_name or fd.short_name_str
            self._fields[key] = fd

        # Build search index
        self._search_index: List[Tuple[int, str, int]] = []
        for row, rec in enumerate(self._records):
            pid = rec.get("playerid", 0)
            if pid <= 0:
                continue
            self._search_index.append((row, self._name_resolver.get_name(rec), pid))

        self._current_row: Optional[int] = None
        self._spinboxes: Dict[str, QSpinBox] = {}
        self._modified: set = set()

        self._setup_ui()
        self._on_search()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Horizontal)

        # ======== LEFT: Search panel ========
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)

        left_layout.addWidget(QLabel("<b>Search Player</b>"))

        # Search row: ID input + name search
        search_row = QHBoxLayout()
        self._id_input = QLineEdit()
        self._id_input.setPlaceholderText("Player ID (e.g. 20801)")
        self._id_input.setFixedWidth(120)
        self._id_input.returnPressed.connect(self._jump_to_id)
        search_row.addWidget(self._id_input)

        go_btn = QPushButton("Go")
        go_btn.setFixedWidth(40)
        go_btn.clicked.connect(self._jump_to_id)
        search_row.addWidget(go_btn)

        search_row.addWidget(QLabel("or"))

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Name search (~300 named players available)")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._on_search)
        search_row.addWidget(self._search_input)
        left_layout.addLayout(search_row)

        # Hint text
        hint = QLabel("💡 Tip: Enter a player ID for exact match, or type a name to search")
        hint.setStyleSheet("color: #888; font-size: 11px; padding: 2px 0;")
        left_layout.addWidget(hint)

        self._result_count = QLabel("")
        self._result_count.setStyleSheet("color: #666; font-size: 11px;")
        left_layout.addWidget(self._result_count)

        self._result_list = QListWidget()
        self._result_list.setAlternatingRowColors(True)
        self._result_list.currentRowChanged.connect(self._on_result_selected)
        self._result_list.setMinimumWidth(260)
        left_layout.addWidget(self._result_list)

        splitter.addWidget(left)

        # ======== RIGHT: Attribute form ========
        right = QScrollArea()
        right.setWidgetResizable(True)
        self._form_container = QWidget()
        self._form_layout = QVBoxLayout(self._form_container)
        self._form_layout.setContentsMargins(4, 4, 4, 4)

        self._placeholder = QLabel(
            "👆 Search for a player above, then select from the list"
        )
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("color: #999; font-size: 16px; padding: 60px;")
        self._form_layout.addWidget(self._placeholder)

        right.setWidget(self._form_container)
        splitter.addWidget(right)

        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

    # ============== SEARCH ==============

    def _jump_to_id(self):
        """Jump directly to a player by ID."""
        text = self._id_input.text().strip()
        if not text.isdigit():
            # If ID field is empty, maybe it's a name
            if text:
                self._search_input.setText(text)
            return
        target = int(text)

        # Search the index
        for row, name, pid in self._search_index:
            if pid == target:
                # Select in result list
                self._search_input.clear()
                self._result_list.blockSignals(True)
                self._result_list.clear()
                pos = self._get_position_text(row)
                ovr = self._records[row].get("overallrating", "")
                item = QListWidgetItem(f"{name}  (ID={pid})  [{pos}]  OVR={ovr}")
                item.setData(Qt.UserRole, row)
                self._result_list.addItem(item)
                self._result_count.setText("1 result (ID match)")
                self._result_list.blockSignals(False)
                self._result_list.setCurrentRow(0)
                return

        # Player ID not found
        self._status_message(f"Player ID {target} not found in this save", "orange")

    def _on_search(self):
        """Filter results list based on name search text."""
        text = self._search_input.text().strip().lower()
        self._result_list.blockSignals(True)
        self._result_list.clear()

        if not text:
            # Show first 30 when no search
            results = self._search_index[:30]
            showing = f"Showing first {30} of {len(self._search_index)}"
        else:
            results = []
            for row, name, pid in self._search_index:
                if text in name.lower() or text in str(pid):
                    results.append((row, name, pid))
            showing = ""

        for row, name, pid in results:
            pos = self._get_position_text(row)
            ovr = self._records[row].get("overallrating", "")
            item_text = f"{name}  (ID={pid})  [{pos}]  OVR={ovr}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, row)
            self._result_list.addItem(item)

        count = len(results)
        self._result_count.setText(f"{count} results" if showing == "" else showing)
        self._result_list.blockSignals(False)

    def _status_message(self, msg: str, color: str = "#333"):
        self._result_count.setText(msg)
        self._result_count.setStyleSheet(f"color: {color}; font-size: 11px;")

    # ============== PLAYER FORM ==============

    def _on_result_selected(self, row_idx: int):
        if row_idx < 0:
            return
        item = self._result_list.item(row_idx)
        if not item:
            return
        source_row = item.data(Qt.UserRole)
        if source_row is None:
            return
        self._load_player(source_row)

    def _load_player(self, source_row: int):
        if source_row == self._current_row and not self._modified:
            return

        if self._modified and self._current_row is not None:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Switching player will lose unsaved changes. Continue?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.No:
                return

        self._current_row = source_row
        self._modified.clear()
        self._rebuild_form()

    def _rebuild_form(self):
        while self._form_layout.count():
            child = self._form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._spinboxes.clear()

        if self._current_row is None:
            self._form_layout.addWidget(
                QLabel("Select a player from the search results")
            )
            return

        rec = self._records[self._current_row]
        pid = rec.get("playerid", 0)
        name = self._name_resolver.get_name(rec)
        highlight_pos = name.startswith("Player") if name else True

        # --- Header ---
        header_text = f"<b>{name}</b>  (ID={pid})"
        header = QLabel(header_text)
        header.setStyleSheet(
            "font-size: 20px; padding: 10px 4px; "
            "color: #1a1a1a;"
        )
        self._form_layout.addWidget(header)

        # If name is unresolved, show a note
        if not highlight_pos:
            note = QLabel(
                "💡 Full name not available without the main game database. "
                "Search by Player ID for any player."
            )
            note.setStyleSheet("color: #999; font-size: 11px; padding: 0 4px 8px 4px;")
            note.setWordWrap(True)
            self._form_layout.addWidget(note)

        # --- Summary stats row ---
        ovr = rec.get("overallrating", "?")
        pot = rec.get("potential", "?")
        pos = self._get_position_text(self._current_row)
        age = self._approximate_age(rec.get("birthdate", 0))
        nat = rec.get("nationality", "?")

        summary_widget = QWidget()
        summary_widget.setStyleSheet(
            "background: #f0f7ff; border: 1px solid #cce5ff; "
            "border-radius: 6px; padding: 8px; margin: 4px 0;"
        )
        summary_layout = QHBoxLayout(summary_widget)
        summary_layout.setContentsMargins(12, 8, 12, 8)

        for label, value in [
            ("OVR", ovr), ("POT", pot), ("POS", pos),
            ("AGE", age), ("NAT", nat),
        ]:
            col = QVBoxLayout()
            col.setSpacing(0)
            lbl = QLabel(str(value))
            lbl.setStyleSheet(
                "font-size: 22px; font-weight: bold; text-align: center;"
            )
            lbl.setAlignment(Qt.AlignCenter)
            lbl2 = QLabel(label)
            lbl2.setStyleSheet("font-size: 10px; color: #666; text-align: center;")
            lbl2.setAlignment(Qt.AlignCenter)
            col.addWidget(lbl)
            col.addWidget(lbl2)
            summary_layout.addLayout(col)

        self._form_layout.addWidget(summary_widget)

        # --- Attribute groups ---
        for cat_name, fields in ATTRIBUTE_CATEGORIES:
            group = QGroupBox(cat_name)
            group.setStyleSheet(
                "QGroupBox { font-weight: bold; border: 1px solid #ccc; "
                "border-radius: 4px; margin-top: 8px; padding-top: 16px; "
                "padding-bottom: 4px; }"
                "QGroupBox::title { subcontrol-origin: margin; "
                "left: 10px; padding: 0 4px; }"
            )
            grid = QGridLayout(group)
            grid.setSpacing(4)

            r, c = 0, 0
            for field_name, label in fields:
                fd = self._fields.get(field_name)
                if fd is None:
                    continue
                value = rec.get(field_name, fd.range_low)

                lbl = QLabel(f"{label}:")
                lbl.setStyleSheet("font-size: 12px;")
                grid.addWidget(lbl, r, c * 2)

                widget = self._make_widget(fd, field_name, value)
                if widget:
                    grid.addWidget(widget, r, c * 2 + 1)
                    self._spinboxes[field_name] = widget

                r += 1
                if r > 13:
                    r = 0
                    c += 1

            self._form_layout.addWidget(group)

        # --- Action buttons ---
        btn_layout = QHBoxLayout()
        reset_btn = QPushButton("Reset All")
        reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(reset_btn)

        apply_btn = QPushButton("Apply Changes")
        apply_btn.setStyleSheet(
            "QPushButton { background: #4CAF50; color: white; "
            "font-weight: bold; padding: 6px 20px; border-radius: 4px; }"
            "QPushButton:hover { background: #45a049; }"
        )
        apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(apply_btn)

        self._form_layout.addLayout(btn_layout)
        self._form_layout.addStretch()

    def _make_widget(self, fd: FieldDescriptor, field_name: str, value) -> Optional[QWidget]:
        type_name = fd.field_type.name

        if type_name == "Integer":
            if field_name == "playerid":
                w = QSpinBox()
                w.setRange(0, 500000)
                w.setValue(int(value))
                w.setReadOnly(True)
                w.setStyleSheet("QSpinBox { background: #f0f0f0; }")
                w.setFixedWidth(100)
                w.setAlignment(Qt.AlignCenter)
                return w

            w = QSpinBox()
            w.setRange(fd.range_low, fd.range_high)
            w.setValue(int(value))
            w.setFixedWidth(90)
            w.setAlignment(Qt.AlignCenter)
            w.valueChanged.connect(lambda v, fn=field_name: self._on_changed(fn))

            if field_name in ("overallrating", "potential"):
                w.setStyleSheet(
                    "QSpinBox { font-weight: bold; font-size: 14px; "
                    "background: #e8f4e8; }"
                )
            return w

        elif type_name == "Float":
            w = QDoubleSpinBox()
            w.setRange(-1.0, 1.0)
            w.setSingleStep(0.01)
            w.setDecimals(6)
            w.setValue(float(value))
            w.setFixedWidth(120)
            w.valueChanged.connect(lambda v, fn=field_name: self._on_changed(fn))
            return w

        elif type_name in ("String", "ShortCompressedString", "LongCompressedString"):
            w = QLabel(str(value) if value else "-")
            w.setStyleSheet(
                "background: #f9f9f9; padding: 2px 8px; "
                "border: 1px solid #ddd; border-radius: 2px;"
            )
            return w

        return None

    def _on_changed(self, field_name: str):
        self._modified.add(field_name)

    def _on_reset(self):
        if not self._modified:
            return
        reply = QMessageBox.question(
            self, "Reset", "Reset all fields to original values?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.No:
            return
        self._modified.clear()
        self._rebuild_form()

    def _on_apply(self):
        """Write modified values back to the data model."""
        if self._current_row is None:
            return
        if not self._modified:
            self._status_message("No changes to apply", "#888")
            return

        rec = self._records[self._current_row]
        count = 0
        for field_name in self._modified:
            spin = self._spinboxes.get(field_name)
            if spin:
                val = spin.value()
                if val != rec.get(field_name):
                    rec[field_name] = val
                    count += 1

        if count:
            pid = rec.get("playerid", 0)
            self._modified.clear()
            self._status_message(f"✅ Applied {count} change(s) to Player ID={pid}", "green")
            self.player_edited.emit(pid)
        else:
            self._status_message("No changes (values unchanged)", "#888")

    def get_modified(self) -> List[Tuple[int, Dict]]:
        """Get pending changes that haven't been applied."""
        if not self._modified or self._current_row is None:
            return []
        rec = self._records[self._current_row]
        changes = {}
        for fn in self._modified:
            spin = self._spinboxes.get(fn)
            if spin and spin.value() != rec.get(fn):
                changes[fn] = spin.value()
        return [(self._current_row, changes)] if changes else []

    def apply_changes(self) -> int:
        """Force-apply any pending changes. Returns count."""
        count = 0
        for _, changes in self.get_modified():
            for k, v in changes.items():
                self._records[self._current_row][k] = v
                count += 1
        if count:
            self._modified.clear()
        return count

    # ============== HELPERS ==============

    def _get_position_text(self, source_row: int) -> str:
        pos = self._records[source_row].get("preferredposition1", 0)
        if isinstance(pos, int) and pos in POSITION_NAMES:
            return POSITION_NAMES[pos]
        return str(pos)

    def _approximate_age(self, birthdate: int) -> int:
        if not birthdate or birthdate <= 0:
            return 0
        return max(15, birthdate // 365)
