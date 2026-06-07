"""SavFile — handles FIFA 19 .sav container files (FBCHUNKS wrapper + DB data)."""

from pathlib import Path
from typing import Optional
from .db_file import DbFile
from .meta_parser import MetaDatabase


class SavFile:
    """FIFA 19 squad/career save file."""

    DB_MAGIC = b"DB\x00\x08"

    def __init__(self):
        self.fbchunks_header: bytes = b""
        self.db: Optional[DbFile] = None
        self.filepath: Optional[Path] = None

    def load(self, filepath: Path, meta_db: Optional[MetaDatabase] = None):
        """Load a .sav file."""
        self.filepath = Path(filepath)

        with open(filepath, "rb") as f:
            data = f.read()

        # Find the embedded DB signature
        db_pos = data.find(self.DB_MAGIC)
        if db_pos == -1:
            raise ValueError(
                f"Not a valid FIFA save file: DB signature not found in {filepath}"
            )

        # Preserve the FBCHUNKS header for later save
        self.fbchunks_header = data[:db_pos]

        # Load the DB portion
        self.db = DbFile()
        self.db.load(data[db_pos:], meta_db)

    def save(self, filepath: Optional[Path] = None) -> Path:
        """Save the DB back to a .sav file (preserving FBCHUNKS header)."""
        if self.db is None:
            raise ValueError("No DB loaded — nothing to save.")

        output_path = Path(filepath) if filepath else self.filepath
        if output_path is None:
            raise ValueError("No output path specified.")

        # Serialize DB
        db_data = self.db.save()

        # Write: FBCHUNKS header + DB data
        with open(output_path, "wb") as f:
            f.write(self.fbchunks_header)
            f.write(db_data)

        return output_path

    def summary(self) -> str:
        """Return a human-readable summary."""
        lines = [
            f"SAV File: {self.filepath}",
            f"  FBCHUNKS header: {len(self.fbchunks_header)} bytes",
            "",
        ]
        if self.db:
            lines.append(self.db.summary())
        return "\n".join(lines)
