"""Main GUI window — player editor (primary) with table browser (secondary)."""

from pathlib import Path

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
        self._name_resolver = None
        self._tab_signal_connected = False

        self.setWindowTitle("FIFA 19 Save Editor")
        self.resize(1400, 900)

        self._setup_ui()

    def _setup_ui(self):
        # --- Menu ---
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        open_action = QAction("Open Save...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("Save As...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

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
        self._rebuild_tabs()
        self.setCentralWidget(self._tabs)

        # --- Status bar ---
        if self._sav.db:
            players_table = self._sav.db.get_table("CZUM")
            self._status_label = QLabel(
                f"Loaded {len(self._sav.db.tables)} tables, "
                f"{len(players_table.records) if players_table else 0:,} players"
            )
        else:
            self._status_label = QLabel("No save file loaded")
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

    def _on_open(self):
        """Open a new save file via file dialog."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open FIFA 19 Save File", "",
            "Save Files (Squads*.sav Squads*);;All Files (*)",
        )
        if not path:
            return

        try:
            # Prompt to apply any pending changes before switching
            if self._player_editor:
                changes = self._player_editor.get_modified()
                if changes:
                    reply = QMessageBox.question(
                        self, "Unsaved Changes",
                        f"{sum(len(c) for _, c in changes)} attribute change(s) not applied. "
                        "Discard them?",
                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    )
                    if reply == QMessageBox.Cancel:
                        return
                    elif reply == QMessageBox.Yes:
                        self._player_editor.apply_changes()

            # Load the new save file
            new_sav = SavFile()
            new_sav.load(Path(path), self._meta_db)
            self._sav = new_sav
            self._rebuild_tabs()
            self.statusBar().showMessage(
                f"Loaded: {path} — "
                f"{len(self._sav.db.tables)} tables, "
                f"{len(self._sav.db.get_table('CZUM').records) if self._sav.db.get_table('CZUM') else 0:,} players",
                5000,
            )
            self._status_label.setText(
                f"Loaded {len(self._sav.db.tables)} tables, "
                f"{len(self._sav.db.get_table('CZUM').records) if self._sav.db.get_table('CZUM') else 0:,} players"
            )
            self.setWindowTitle(f"FIFA 19 Save Editor — {Path(path).name}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to open save file:\n{e}")

    def _rebuild_tabs(self):
        """Destroy and recreate all tabs for the current sav data."""
        # Disconnect tab change signal while rebuilding
        if self._tab_signal_connected:
            self._tabs.currentChanged.disconnect(self._on_tab_changed)
            self._tab_signal_connected = False

        # Remove all existing tabs
        while self._tabs.count():
            widget = self._tabs.widget(0)
            self._tabs.removeTab(0)
            if widget:
                widget.deleteLater()

        self._player_editor = None
        self._player_stats_tab = None

        # If no DB loaded, show placeholder
        if not self._sav.db:
            self._tabs.addTab(QLabel("No save file loaded. Use File → Open Save... to open a .sav file."), "⚽ Player Editor")
            self._tabs.addTab(QLabel("No save file loaded."), "📊 Table Browser")
            return

        self._name_resolver = NameResolver(self._sav.db)

        # Tab 1: Player Editor
        players_table = self._sav.db.get_table("CZUM")
        if players_table and players_table.records:
            self._player_editor = PlayerEditor(players_table, self._name_resolver)
            self._tabs.addTab(self._player_editor, "⚽ Player Editor")
            self._tabs.currentChanged.connect(self._on_tab_changed)
            self._tab_signal_connected = True
        else:
            self._tabs.addTab(QLabel("Players table not found"), "⚽ Player Editor")

        # Tab 2: Table Browser
        self._table_browser = TableBrowser(self._sav)
        self._tabs.addTab(self._table_browser, "📊 Table Browser")

        # Tab 3: Player Stats Table
        if players_table and players_table.records:
            self._player_stats_tab = PlayerStatsTable(players_table, self._name_resolver)
            self._tabs.addTab(self._player_stats_tab, "📋 Player Stats")

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

    def _on_save_as(self):
        """Save the modified DB back to a .sav file."""
        if not self._sav or not self._sav.db:
            QMessageBox.warning(self, "No Data", "No save file loaded.")
            return

        # Apply any pending changes in the player editor first
        if self._player_editor:
            changes = self._player_editor.get_modified()
            if changes:
                reply = QMessageBox.question(
                    self, "Apply Changes",
                    f"{sum(len(c) for _, c in changes)} attribute change(s) pending. "
                    "Apply them before saving?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    self._player_editor.apply_changes()

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Save File As",
            "Squads_modified.sav",
            "Save Files (Squads*.sav);;All Files (*)",
        )
        if not path:
            return

        try:
            self._sav.save(Path(path))
            self._status_label.setText(f"Saved to {Path(path).name}")
            self.statusBar().showMessage(f"Saved to {path}", 5000)
            self.setWindowTitle(f"FIFA 19 Save Editor — {Path(path).name}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{e}")

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
