"""Main GUI window — player editor (primary) with table browser (secondary)."""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QMessageBox, QFileDialog, QTabWidget,
    QTableView, QListWidget, QLineEdit, QSplitter,
    QHeaderView, QComboBox, QFrame, QAbstractItemView,
    QPushButton,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, Signal
from PySide6.QtGui import QAction

from core.sav_file import SavFile
from core.meta_parser import MetaDatabase
from core.name_resolver import NameResolver
from core.exporter import export_to_excel
from .player_editor import PlayerEditor
from .table_model import FifaTableModel
from .player_stats_table import PlayerStatsTable


class TableFilterProxy(QSortFilterProxyModel):
    """Filter proxy that searches across all columns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""
        self._column_filter = -1

    def set_filter_text(self, text: str):
        self._filter_text = text.lower().strip()
        self.invalidateFilter()

    def set_column_filter(self, col: int):
        self._column_filter = col
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent) -> bool:
        if not self._filter_text:
            return True
        model = self.sourceModel()
        if not model:
            return True
        cols = (
            range(model.columnCount())
            if self._column_filter < 0
            else [self._column_filter]
        )
        for col in cols:
            idx = model.index(source_row, col, source_parent)
            val = model.data(idx, Qt.DisplayRole)
            if val is not None and self._filter_text in str(val).lower():
                return True
        return False


class TableBrowser(QWidget):
    """Sidebar + table view for browsing all DB tables."""

    def __init__(self, sav: SavFile, parent=None):
        super().__init__(parent)
        self._sav = sav
        self._source_model = FifaTableModel()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        # Left: table list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Tables"))
        self._table_list = QListWidget()
        self._table_list.setMinimumWidth(160)
        self._table_list.setMaximumWidth(280)
        self._table_list.currentItemChanged.connect(self._on_table_selected)
        left_layout.addWidget(self._table_list)
        splitter.addWidget(left)

        # Right: toolbar + table view
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self._table_label = QLabel("Select a table")
        self._table_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        toolbar_layout.addWidget(self._table_label)
        toolbar_layout.addStretch()

        toolbar_layout.addWidget(QLabel("Search:"))
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter rows...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumWidth(180)
        self._search_input.textChanged.connect(self._on_search)
        toolbar_layout.addWidget(self._search_input)

        toolbar_layout.addWidget(QLabel("Column:"))
        self._column_combo = QComboBox()
        self._column_combo.addItem("All columns", -1)
        self._column_combo.currentIndexChanged.connect(self._on_column_filter)
        self._column_combo.setMinimumWidth(120)
        toolbar_layout.addWidget(self._column_combo)

        right_layout.addWidget(toolbar)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        right_layout.addWidget(sep)

        # Table view
        self._table_view = QTableView()
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSortingEnabled(True)
        self._table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table_view.horizontalHeader().setStretchLastSection(True)
        self._table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table_view.verticalHeader().setDefaultSectionSize(24)
        right_layout.addWidget(self._table_view)

        splitter.addWidget(right)
        splitter.setSizes([200, 800])
        layout.addWidget(splitter)

        # Filter proxy
        self._proxy = TableFilterProxy()
        self._proxy.setSourceModel(self._source_model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._table_view.setModel(self._proxy)

        # Populate table list
        self._populate()

    def _populate(self):
        self._table_list.clear()
        for short_name, table in sorted(self._sav.db.tables.items()):
            display = table.long_name or short_name
            if table.records:
                display += f"  ({len(table.records):,})"
            self._table_list.addItem(display)
        if self._table_list.count() > 0:
            self._table_list.item(0).setSelected(True)

    def _on_table_selected(self, current, previous):
        if not current:
            return
        short_names = sorted(self._sav.db.tables.keys())
        idx = self._table_list.currentRow()
        if idx < 0 or idx >= len(short_names):
            return
        short_name = short_names[idx]
        table = self._sav.db.get_table(short_name)

        self._column_combo.blockSignals(True)
        self._column_combo.clear()
        self._column_combo.addItem("All columns", -1)
        for fd in table.fields:
            name = fd.field_name or fd.short_name_str
            self._column_combo.addItem(name, fd.bit_offset)
        self._column_combo.setCurrentIndex(0)
        self._column_combo.blockSignals(False)

        self._table_label.setText(f"{table.long_name or short_name} ({short_name})")
        self._source_model.load_table(table)
        self._table_view.resizeColumnsToContents()

    def _on_search(self, text: str):
        self._proxy.set_filter_text(text)

    def _on_column_filter(self, idx: int):
        if not self._source_model.table:
            return
        col = self._column_combo.itemData(idx)
        if col == -1:
            self._proxy.set_column_filter(-1)
        else:
            for i, fd in enumerate(self._source_model.table.fields):
                if fd.bit_offset == col:
                    self._proxy.set_column_filter(i)
                    break
        self._proxy.invalidateFilter()


class MainWindow(QMainWindow):
    """Main editor window with Player Editor and Table Browser tabs."""

    def __init__(self, sav: SavFile, meta_db: MetaDatabase):
        super().__init__()
        self._sav = sav
        self._meta_db = meta_db
        self._name_resolver = NameResolver(sav.db)

        self.setWindowTitle("FIFA 19 Save Editor")
        self.resize(1400, 900)

        self._setup_ui()

    def _setup_ui(self):
        # --- Menu ---
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        export_action = QAction("Export to Excel...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- Tabs ---
        self._tabs = QTabWidget()

        # Tab 1: Player Editor
        players_table = self._sav.db.get_table("CZUM")
        if players_table:
            self._player_editor = PlayerEditor(players_table, self._name_resolver)
            self._tabs.addTab(self._player_editor, "⚽ Player Editor")
        else:
            self._player_editor = None
            self._tabs.addTab(QLabel("Players table not found"), "⚽ Player Editor")

        # Tab 2: Table Browser
        self._table_browser = TableBrowser(self._sav)
        self._tabs.addTab(self._table_browser, "📊 Table Browser")

        # Tab 3: Player Stats Table (compact core-ability overview)
        self._player_stats_tab = None
        if players_table:
            self._player_stats_tab = PlayerStatsTable(players_table, self._name_resolver)
            self._tabs.addTab(self._player_stats_tab, "📋 Player Stats")

        # Apply button for player editor
        if self._player_editor:
            self._tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self._tabs)

        # --- Status bar ---
        self._status_label = QLabel(
            f"Loaded {len(self._sav.db.tables)} tables, "
            f"{len(self._sav.db.get_table('CZUM').records) if self._sav.db.get_table('CZUM') else 0:,} players"
        )
        self.statusBar().addWidget(self._status_label, 1)

    def _on_tab_changed(self, idx: int):
        """When switching away from Player Editor, prompt to apply changes."""
        if idx != 0 or not self._player_editor:
            return
        # Coming back to player editor — check for unapplied changes
        changes = self._player_editor.get_modified()
        if changes:
            reply = QMessageBox.question(
                self, "Apply Changes",
                f"Apply {sum(len(c) for _, c in changes)} attribute change(s)?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                count = self._player_editor.apply_changes()
                if count:
                    self._status_label.setText(f"Applied {count} changes")

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to Excel", "squad.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return
        try:
            export_to_excel(self._sav, Path(path))
            QMessageBox.information(self, "Export Complete", f"Saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def closeEvent(self, event):
        # Check for unapplied changes
        if self._player_editor:
            changes = self._player_editor.get_modified()
            if changes:
                reply = QMessageBox.question(
                    self, "Unsaved Changes",
                    f"{sum(len(c) for _, c in changes)} attribute change(s) not applied. "
                    "Apply before closing?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                )
                if reply == QMessageBox.Cancel:
                    event.ignore()
                    return
                elif reply == QMessageBox.Yes:
                    self._player_editor.apply_changes()
        event.accept()
