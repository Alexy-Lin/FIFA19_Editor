"""FIFA 19 Save Editor — GUI launcher.

Loads the last-opened save file from config, or falls back to the first
Squads*.sav found next to the meta XML.
"""

import sys
import time
from pathlib import Path

# Allow running from the project directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication, QMessageBox

from core.sav_file import SavFile
from core.meta_parser import MetaDatabase
from core.config import load as load_config, save as save_config
from gui.main_window import MainWindow

META_XML_PATH = Path(__file__).resolve().parent.parent / "fifa_ng_db-meta.xml"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FIFA 19 Save Editor")

    # Load meta XML
    print(f"Loading meta XML: {META_XML_PATH}")
    t0 = time.time()
    meta_db = MetaDatabase.from_file(META_XML_PATH)
    print(f"  Parsed {len(meta_db.tables)} table definitions ({time.time()-t0:.1f}s)")

    # Determine which save file to load
    cfg = load_config()
    last = cfg.get("last_save_path")
    last_valid = last and Path(last).exists()

    if last_valid:
        print(f"Auto-loading last opened: {last}")
        sav_path = Path(last)
    else:
        # Fallback: look for any Squads*.sav next to the meta XML
        print("  (no last_save_path in config)")
        sav_dir = META_XML_PATH.parent
        candidates = sorted(sav_dir.glob("Squads*.sav"))
        if candidates:
            sav_path = candidates[-1]
            print(f"  (found fallback: {sav_path.name})")
            save_config({"last_save_path": str(sav_path.resolve())})
        else:
            sav_path = None

    # Load save file if we have a path
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
    if sav_path:
        window.setWindowTitle(f"FIFA 19 Save Editor — {sav_path.name}")
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
