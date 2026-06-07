# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FIFA 19 Save File Editor** — A tool to read and edit FIFA 19 squad save files (`Squads*.sav`), which use a Frostbite-engine binary format with bit-packed integer storage.

**Phase 1 complete: read-only parsing.** The `fifa19-editor/core/` library can parse `.sav` files and extract all 46 tables with 18,500+ player records. Write functionality is not yet implemented.

## Quick Start

```powershell
# Run the CLI reader
& "C:\anaconda3\python.exe" fifa19-editor/main.py Squads20260423210221
```

## Project Structure

```
fifa19-editor/
├── main.py                     # CLI entry point
├── core/                       # Binary format library
│   ├── __init__.py
│   ├── types.py               # EFieldTypes enum, DB magic constants
│   ├── db_reader.py           # Bit-compressed reader (read_bits, seek_to_bit, read_string, read_float)
│   ├── field_descriptor.py    # FieldDescriptor (type, bit_offset, short_name, depth)
│   ├── meta_parser.py         # Parse fifa_ng_db-meta.xml → table/field metadata
│   ├── table.py               # Table — header + field descriptors + record reading
│   ├── db_file.py             # DbFile — DB header, table directory, all tables
│   └── sav_file.py            # SavFile — .sav container (FBCHUNKS header + DB)
├── tests/                     # (not yet created)
├── ../fifa_ng_db-meta.xml     # Schema metadata (534 KB, 157 table definitions)
└── ../Squads20260423210221    # Test squad file (6.0 MB, 46 tables)
```

## Key Files

| File | Size | Description |
|------|------|-------------|
| `Squads20260423210221` | 6.0 MB | FIFA 19 squad save file (binary, 146B FBCHUNKS header + 6MB DB) |
| `fifa_ng_db-meta.xml` | 534 KB | Database schema — maps 4-byte short names to field names, types, depths, ranges |
| `FIFA19存档编辑器-技术总结.md` | 14 KB | Original format analysis and implementation plan (Chinese) |

## File Format Architecture

### Level 1: Frostbite Chunks (.sav container)
- 146-byte `FBCHUNKS` header — **must be preserved byte-for-byte on save**
- Followed by embedded DB starting with `DB\x00\x08` magic

### Level 2: DB Container (24-byte header)
- Platform byte (0=PC), file length, reserved, table count (uint32), header CRC32
- Table directory: N × 8 bytes (4-byte short name + 4-byte relative offset from data section start)
- ShortNames CRC32 (4 bytes) after directory
- Table data section follows

### Level 3: Per-Table Binary Layout (verified against C# FifaLibrary14)
```
[ 0] Unknown00          int32
[ 4] RecordSize         int32    (bytes per record, byte-aligned)
[ 8] NBitRecords        uint32
[12] CompressedStrLen   uint32
[16] NRecords           uint16   (total slots including deleted)
[18] NValidRecords      uint16   (used slots, read first N)
[20] Unknown14          int32
[24] NFields            byte     (count of field descriptors)
[25] 3 padding bytes
[28] Unknown1C          int32
[32] CrcTableHeader     uint32
[36] FieldDescriptors[]  16 bytes each: type(int32) + bitOffset(int32) + shortName(4) + depth(int32)
[  ] Records[]           bit-packed per field descriptors
[  ] [CompressedStringData]  if CompressedStrLen > 0
```

### Level 4: Field Descriptor & Bit-Packed Reading
- **Field descriptor order in file**: NOT sorted by bit_offset — must sort before reading records
- **XML metadata** is matched by short_name to assign field names, range_low, range_high
- **Record reading**: for each field (sorted by bit_offset), seek to absolute bit position = `record_start_byte * 8 + bit_offset`, then read `depth` bits
- **Integer**: raw value + `range_low` (range_low is the minimum value)
- **String**: null-terminated, byte-aligned, length = depth/8 bytes
- **Float**: 4-byte IEEE 754 LE, byte-aligned
- **CompressedString**: 4-byte offset pointer into compressed string block (not yet decoded)

## Key Table Short Names (from this squad file)

| Short Name | Human Name | Records | Notes |
|-----------|------------|---------|-------|
| `CZUM` | players | 18,537 | 118 fields, 100B/record |
| `lyxL` | teams | 720 | 95 fields, 160B/record — team names are plain strings |
| `RrqT` | teamplayerlinks | 19,692 | 16 fields, 16B/record |
| `mDGw` | formations | 779 | 65 fields |
| `AGmV` | default_teamsheets | 746 | 146 fields |
| `onMQ` | leagues | 48 | 11 fields |
| `FMpz` | competition | 147 | 77 fields |

## Important Table Short Names (from meta.xml, 157 total)

Known field short names:
- `ykFq` → playerid
- `mCXg` → teamid
- `UERs` → overallrating
- `vjla` → preferredposition
- `WVIU` → birthdate

## Bit-Packed Integer Details

- Values stored as `(actual - rangeLow)` in exactly `depth` bits, MSB-first
- Reader tracks `_byte_pos` and `_bit_pos` (0-7); bit_pos=8 means "need next byte"
- `seek_to_bit(absolute_bit)` enables random access to any field position within a record
- Crosses byte boundaries seamlessly in `read_bits()`

## Implementation Status

- [x] Read DB header, table directory, field descriptors
- [x] Bit-packed integer reading (verified across 46 tables)
- [x] String reading (team names decode correctly)
- [x] Float reading
- [x] XML metadata integration (field name mapping)
- [x] Record filtering (valid vs deleted slots)
- [ ] Bit-packed integer writing (DbWriter)
- [ ] CRC32 recalculation on save
- [ ] Huffman-compressed string decoding
- [ ] Save back to .sav file
- [ ] GUI (PySide6)
- [ ] Unit tests

## External References

- **[FifaLibrary14](https://github.com/ebeninca/CreationMaster17/tree/master/FifaLibrary14)** (C#) — Primary reference. Key files: `DbReader.cs`, `DbWriter.cs`, `DbFile.cs`, `FieldDescriptor.cs`, `Table.cs`, `TableDescriptor.cs`, `Record.cs`
- **[fifa-career-save-parser](https://github.com/sammygriffiths/fifa-career-save-parser)** (JavaScript) — Read-only parser for FIFA 17-21, uses `xml/19/fifa_ng_db-meta.xml`
