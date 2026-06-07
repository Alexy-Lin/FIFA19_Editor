"""FIFA 19 Save Editor — GUI launcher.

Usage:
    python main_gui.py <path_to_sav_file>   # Launch GUI with a save file
    python main_gui.py                      # Launch GUI, then open via File menu
"""

import sys
import time
from pathlib import Path

# Allow running from the project directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from core.sav_file import SavFile
from core.meta_parser import MetaDatabase
from gui.main_window import MainWindow

META_XML_PATH = Path(__file__).resolve().parent.parent / "fifa_ng_db-meta.xml"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FIFA 19 Save Editor")

    # Parse args
    sav_path = None
    if len(sys.argv) > 1:
        sav_path = Path(sys.argv[1])
        if not sav_path.exists():
            print(f"Error: File not found: {sav_path}")
            sys.exit(1)
        if sav_path.suffix not in ("", ".sav"):
            print(f"Warning: {sav_path} may not be a valid save file")

    # Load meta XML
    print(f"Loading meta XML: {META_XML_PATH}")
    t0 = time.time()
    meta_db = MetaDatabase.from_file(META_XML_PATH)
    print(f"  Parsed {len(meta_db.tables)} table definitions ({time.time()-t0:.1f}s)")

    # Load save file if provided
    sav = None
    if sav_path:
        print(f"\nLoading SAV file: {sav_path}")
        t0 = time.time()
        try:
            sav = SavFile()
            sav.load(sav_path, meta_db)
            print(f"  Loaded {len(sav.db.tables)} tables ({time.time()-t0:.1f}s)")
        except Exception as e:
            QMessageBox.critical(None, "Load Error", f"Failed to load save file:\n{e}")
            sys.exit(1)
    else:
        sav = SavFile()

    window = MainWindow(sav, meta_db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
