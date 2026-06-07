"""Table — parses a single DB table: header, field descriptors, and records."""

import struct
from typing import List, Optional, Dict, Any
from .db_reader import DbReader
from .field_descriptor import FieldDescriptor
from .meta_parser import MetaDatabase, MetaTable
from .types import EFieldTypes


class Table:
    """A single database table with its field descriptors and records."""

    def __init__(self, short_name: str = ""):
        self.short_name: str = short_name
        self.long_name: str = ""
        self.fields: List[FieldDescriptor] = []
        self._fields_by_short: Dict[str, FieldDescriptor] = {}
        self._fields_by_name: Dict[str, FieldDescriptor] = {}

        # Header fields
        self.unknown00: int = 0
        self.record_size: int = 0       # bytes per record (byte-aligned size)
        self.n_bit_records: int = 0
        self.compressed_string_length: int = 0
        self.n_records: int = 0         # total slots
        self.n_valid_records: int = 0   # used slots
        self.unknown14: int = 0
        self.n_fields: int = 0
        self.unknown1c: int = 0
        self.crc_table_header: int = 0

        # Records data position/bookkeeping
        self._records_byte_start: int = 0

        # Parsed records (only valid ones)
        self.records: List[Dict[str, Any]] = []

    def load(self, reader: DbReader, meta_db: Optional[MetaDatabase] = None):
        """Load table from binary reader at current position."""
        # -- Read table header (36 bytes) --
        self.unknown00 = struct.unpack("<I", reader.read_bytes(4))[0]
        self.record_size = struct.unpack("<I", reader.read_bytes(4))[0]
        self.n_bit_records = struct.unpack("<I", reader.read_bytes(4))[0]
        self.compressed_string_length = struct.unpack("<I", reader.read_bytes(4))[0]
        self.n_records = struct.unpack("<H", reader.read_bytes(2))[0]
        self.n_valid_records = struct.unpack("<H", reader.read_bytes(2))[0]
        self.unknown14 = struct.unpack("<i", reader.read_bytes(4))[0]
        self.n_fields = reader.read_bytes(1)[0]
        reader.read_bytes(3)  # 3 padding bytes
        self.unknown1c = struct.unpack("<I", reader.read_bytes(4))[0]
        self.crc_table_header = struct.unpack("<I", reader.read_bytes(4))[0]

        # -- Read field descriptors --
        self.fields = []
        for _ in range(self.n_fields):
            fd = FieldDescriptor()
            fd.load(reader)
            self.fields.append(fd)
            self._fields_by_short[fd.short_name_str] = fd

        # -- Apply XML metadata --
        if meta_db:
            mt = meta_db.get_table(self.short_name)
            if mt:
                self.long_name = mt.name
                for fd in self.fields:
                    mf = mt.fields.get(fd.short_name_str)
                    if mf:
                        fd.apply_xml_metadata(mf.name, mf.range_low, mf.range_high)
                        self._fields_by_name[mf.name] = fd

        # Sort fields by bit_offset (critical for correct reading order)
        self.fields.sort(key=lambda f: f.bit_offset)

        # -- Record where record data begins --
        self._records_byte_start = reader.position

        # -- Read records --
        # Valid records come first (indices 0..nValidRecords-1);
        # deleted/empty slots follow (indices nValidRecords..nRecords-1).
        self.records = []
        for rec_idx in range(self.n_valid_records):
            record = self._read_record(reader, rec_idx)
            if record is not None:
                self.records.append(record)

        # Advance reader position past all record slots (including deleted)
        records_end = self._records_byte_start + self.n_records * self.record_size
        reader.position = records_end

        # Skip compressed string data if present
        if self.compressed_string_length > 0:
            reader.position += self.compressed_string_length

    def _read_record(self, reader: DbReader, rec_idx: int) -> Optional[Dict[str, Any]]:
        """Read a single record. Returns None for deleted records."""
        record_start_byte = self._records_byte_start + rec_idx * self.record_size
        record = {}

        for fd in self.fields:
            # Seek to the field's bit position within the record
            abs_bit = record_start_byte * 8 + fd.bit_offset
            reader.seek_to_bit(abs_bit)

            if fd.field_type == EFieldTypes.Integer:
                value = reader.read_integer(fd.depth, fd.range_low)
            elif fd.field_type == EFieldTypes.Float:
                value = reader.read_float()
            elif fd.field_type == EFieldTypes.String:
                str_len = fd.depth // 8  # depth is in bits, convert to bytes
                value = reader.read_string(str_len)
            elif fd.field_type in (
                EFieldTypes.ShortCompressedString,
                EFieldTypes.LongCompressedString,
            ):
                # Compressed strings: read 4-byte offset pointer
                value = reader.read_integer(32, 0)
            else:
                value = None

            record[fd.field_name or fd.short_name_str] = value

        # Detect deleted records: if all integer fields are 0 or at boundaries
        # Actually, FIFA DB uses a special marker. For now, treat records
        # where the key field equals its range_low (minimum) as potentially deleted.
        # Most tables use teamid/playerid with range_low >= 0, so 0 or -1 markers.
        # We'll include all records; filtering can be done by the caller.
        return record

    def get_field(self, short_name: str) -> Optional[FieldDescriptor]:
        """Look up a field descriptor by short name."""
        return self._fields_by_short.get(short_name)

    def get_field_by_name(self, name: str) -> Optional[FieldDescriptor]:
        """Look up a field descriptor by full name."""
        return self._fields_by_name.get(name)

    def __repr__(self):
        n_fields = len(self.fields)
        n_recs = len(self.records)
        return (
            f"Table('{self.long_name or self.short_name}', "
            f"{n_fields} fields, {n_recs} records, "
            f"recordSize={self.record_size}B)"
        )
