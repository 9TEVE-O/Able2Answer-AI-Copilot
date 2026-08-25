"""Parse an iTunes/Music Library XML to extract track metadata."""
from __future__ import annotations

import plistlib
from pathlib import Path
from typing import Any

_CANDIDATE_PATHS = [
    Path.home() / "Music" / "iTunes" / "iTunes Music Library.xml",
    Path.home() / "Music" / "iTunes" / "iTunes Library.xml",
    Path.home() / "Music" / "Music" / "Music Library.xml",
]


def find_library_path(override: Path | None = None) -> Path | None:
    """Return the first existing iTunes/Music library XML path."""
    if override and override.exists():
        return override
    for p in _CANDIDATE_PATHS:
        if p.exists():
            return p
    return None


def parse_itunes_library(path: Path) -> list[dict[str, Any]]:
    """Parse an iTunes Music Library XML and return a list of track dicts."""
    with open(path, "rb") as f:
        plist = plistlib.load(f)

    raw_tracks = plist.get("Tracks", {})
    tracks: list[dict[str, Any]] = []

    for track_data in raw_tracks.values():
        if track_data.get("Track Type") == "URL":
            continue  # skip streams

        genre = str(track_data.get("Genre", "") or "")
        bpm = int(track_data.get("BPM", 0) or 0)
        play_count = int(track_data.get("Play Count", 0) or 0)
        artist = str(track_data.get("Artist", "") or "")
        name = str(track_data.get("Name", "") or "")

        if not (genre or artist):
            continue

        tracks.append({
            "title": name,
            "artist": artist,
            "genres": [genre] if genre else [],
            "bpm": bpm,
            "play_count": play_count,
            "source": "itunes",
        })

    return tracks
