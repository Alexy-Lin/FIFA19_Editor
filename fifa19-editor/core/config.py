"""Application configuration — persists user preferences (e.g. last opened file).

Config file location: <project_root>/fifa19-editor/config.json
"""

import json
from pathlib import Path


_CONFIG_FILE = Path(__file__).resolve().parent / "config.json"


def load() -> dict:
    """Load config from disk.  Returns a dict (empty if missing / corrupt)."""
    path = _CONFIG_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def save(cfg: dict) -> None:
    """Write config dict to disk atomically."""
    path = _CONFIG_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
