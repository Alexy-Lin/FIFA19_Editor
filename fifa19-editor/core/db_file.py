"""DbFile — the DB container (header + table directory + tables)."""

import struct
from typing import Dict, Optional, BinaryIO
from pathlib import Path
from .db_reader import DbReader
from .table import Table
from .meta_parser import MetaDatabase


class DbFile:
    """FIFA DB file container — header, table directory, and all tables."""

    MAGIC = b"DB\x00\x08"

    def __init__(self):
        self.platform: int = 0  # 0=PC, 1=Xbox
        self.file_length: int = 0
        self.reserved: int = 0
        self.n_tables: int = 0
        self.crc_header: int = 0
        self.crc_short_names: int = 0

        # keyed by table short name
        self.tables: Dict[str, Table] = {}

        # Raw directory entries (short_name -> offset pairs)
        self._table_offsets: Dict[str, int] = {}

    def load(self, data: bytes, meta_db: Optional[MetaDatabase] = None):
        """Load DB from raw byte data."""
        reader = DbReader(data)

        # -- DB Header (24 bytes) --
        magic = reader.read_bytes(4)
        if magic != self.MAGIC:
            raise ValueError(
                f"Invalid DB magic: {magic!r}, expected {self.MAGIC!r}"
            )
        self.platform = reader.read_bytes(1)[0]
        reader.read_bytes(3)  # padding
        self.file_length = struct.unpack("<I", reader.read_bytes(4))[0]
        self.reserved = struct.unpack("<I", reader.read_bytes(4))[0]
        self.n_tables = struct.unpack("<I", reader.read_bytes(4))[0]
        self.crc_header = struct.unpack("<I", reader.read_bytes(4))[0]

        # -- Table Directory --
        table_names = []
        for _ in range(self.n_tables):
            name_bytes = reader.read_bytes(4)
            name = name_bytes.rstrip(b"\x00").decode("ascii", errors="replace")
            offset = struct.unpack("<I", reader.read_bytes(4))[0]
            if name:  # Only store valid entries
                table_names.append(name)
                self._table_offsets[name] = offset

        # ShortNames CRC
        self.crc_short_names = struct.unpack("<I", reader.read_bytes(4))[0]

        # Data section starts here
        data_section_start = reader.position

        # -- Load Tables --
        for name in table_names:
            table_offset = self._table_offsets.get(name, 0)
            abs_offset = data_section_start + table_offset
            reader.position = abs_offset

            table = Table(short_name=name)
            table.load(reader, meta_db)
            self.tables[name] = table

    @classmethod
    def from_file(cls, path: Path, meta_db: Optional[MetaDatabase] = None) -> "DbFile":
        """Load a raw DB file from disk (not a .sav wrapper)."""
        with open(path, "rb") as f:
            data = f.read()
        db = cls()
        db.load(data, meta_db)
        return db

    def get_table(self, short_name: str) -> Optional[Table]:
        return self.tables.get(short_name)

    def get_table_by_name(self, long_name: str) -> Optional[Table]:
        for table in self.tables.values():
            if table.long_name == long_name:
                return table
        return None

    def summary(self) -> str:
        """Return a human-readable summary of all tables."""
        lines = [
            f"DB File: {self.n_tables} tables",
            f"  Platform: {'PC' if self.platform == 0 else 'Xbox'}",
            f"  File length (header): {self.file_length:,}",
            f"  CRC Header: 0x{self.crc_header:08X}",
            f"  CRC ShortNames: 0x{self.crc_short_names:08X}",
            "",
        ]
        for name, table in self.tables.items():
            lines.append(
                f"  {name:6s}  {table.long_name:<35s}  "
                f"{len(table.fields):3d} fields  "
                f"{table.n_valid_records:5d}/{table.n_records:5d} records  "
                f"({table.record_size}B each)"
            )
        return "\n".join(lines)
