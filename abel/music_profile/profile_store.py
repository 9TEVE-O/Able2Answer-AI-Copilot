"""Persist and load TasteProfile as JSON at ~/.abel/taste_profile.json."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any


def save_profile(profile_dict: dict[str, Any], path: Path) -> None:
    """Write profile JSON with owner-only read/write permissions (0o600)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(profile_dict, f, indent=2)
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    tmp.replace(path)


def load_profile(path: Path) -> dict[str, Any] | None:
    """Load profile JSON. Returns None if file doesn't exist or is malformed."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
