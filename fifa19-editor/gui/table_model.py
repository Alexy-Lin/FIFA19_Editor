"""QAbstractTableModel for displaying and editing DB table records."""

from typing import List, Dict, Any, Set, Tuple, Optional
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QColor, QBrush

from core.table import Table
from core.field_descriptor import FieldDescriptor


# Highlight colors for modified cells
MODIFIED_BG = QColor(255, 255, 200)  # pale yellow
VALIDATED_BG = QColor(200, 255, 200)  # pale green (new/validated)


class FifaTableModel(QAbstractTableModel):
    """Model wrapping a Table's records for display in QTableView.

    Provides:
    - All field columns sorted by bit_offset
    - Cell editing with type validation
    - Modified cell tracking (yellow highlight)
    - Efficient row-based data access
    """

    data_changed = Signal(int, int)  # row, col — emitted after successful edit

    def __init__(self, parent=None):
        super().__init__(parent)
        self._table: Optional[Table] = None
        self._records: List[Dict[str, Any]] = []
        self._headers: List[str] = []
        self._field_by_name: Dict[str, FieldDescriptor] = {}
        self._modified: Set[Tuple[int, int]] = set()  # (row, col)

    @property
    def table(self) -> Optional[Table]:
        return self._table

    def load_table(self, table: Table, records: Optional[List[Dict]] = None):
        """Load a new table into the model."""
        self.beginResetModel()
        self._table = table
        self._records = records if records is not None else table.records
        self._headers = [fd.field_name or fd.short_name_str for fd in table.fields]
        self._field_by_name = {}
        for fd in table.fields:
            key = fd.field_name or fd.short_name_str
            self._field_by_name[key] = fd
        self._modified.clear()
        self.endResetModel()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._records)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row >= len(self._records) or col >= len(self._headers):
            return None

        key = self._headers[col]
        record = self._records[row]
        val = record.get(key)

        if role == Qt.DisplayRole or role == Qt.EditRole:
            if isinstance(val, float):
                return round(val, 6)
            return val

        if role == Qt.BackgroundRole:
            if (row, col) in self._modified:
                return MODIFIED_BG

        if role == Qt.ToolTipRole:
            fd = self._field_by_name.get(key)
            if fd:
                range_info = f"[{fd.range_low}, {fd.range_high}]"
                return f"{key} ({fd.short_name_str})\ntype={fd.field_type.name} depth={fd.depth} range={range_info}"

        return None

    def setData(self, index, value, role=Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        row, col = index.row(), index.column()
        if row >= len(self._records) or col >= len(self._headers):
            return False

        key = self._headers[col]
        fd = self._field_by_name.get(key)
        old_val = self._records[row].get(key)

        # Parse and validate
        if fd:
            try:
                new_val = self._parse_value(value, fd)
            except (ValueError, TypeError):
                return False  # invalid input, reject edit
        else:
            new_val = value

        if new_val == old_val:
            return False  # no change

        self._records[row][key] = new_val
        self._modified.add((row, col))
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.BackgroundRole])
        self.data_changed.emit(row, col)
        return True

    def flags(self, index) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def _parse_value(self, value, fd: FieldDescriptor):
        """Parse user input according to field type and constraints."""
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return fd.range_low

        if fd.field_type.name == "Integer":
            v = int(value)
            if v < fd.range_low:
                v = fd.range_low
            if v > fd.range_high:
                v = fd.range_high
            return v
        elif fd.field_type.name == "Float":
            v = float(value)
            max_val = 1.0  # most game floats are -1..1
            if v < -max_val:
                v = -max_val
            if v > max_val:
                v = max_val
            return v
        else:
            return str(value)

    def get_modified_records(self) -> List[Tuple[int, Dict]]:
        """Get list of (row_index, modified_dict) for changed rows."""
        rows: Dict[int, Dict] = {}
        for row, col in self._modified:
            if row not in rows:
                rows[row] = {}
            key = self._headers[col]
            rows[row][key] = self._records[row].get(key)
        return sorted(rows.items())

    def clear_modified(self):
        """Clear all modification tracking."""
        self._modified.clear()
        if self._records:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._records) - 1, len(self._headers) - 1),
                [Qt.BackgroundRole],
            )

    def record_at(self, row: int) -> Optional[Dict[str, Any]]:
        """Get the raw record dict at a given row."""
        if 0 <= row < len(self._records):
            return self._records[row]
        return None
