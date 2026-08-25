"""Scan local audio directories and read ID3/MP4/FLAC tags using mutagen."""
from __future__ import annotations

from pathlib import Path
from typing import Any

_AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aiff", ".aif", ".ogg", ".wav", ".wma"}


def scan_directories(dirs: list[Path]) -> list[dict[str, Any]]:
    """Walk dirs and extract genre/BPM/artist from audio file tags."""
    try:
        import mutagen  # noqa: F401
    except ImportError:
        raise RuntimeError("Local file scanning requires mutagen: pip install mutagen")

    tracks: list[dict[str, Any]] = []
    for directory in dirs:
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.suffix.lower() not in _AUDIO_EXTENSIONS:
                continue
            track = _read_tags(path)
            if track:
                tracks.append(track)
    return tracks


def _read_tags(path: Path) -> dict[str, Any] | None:
    """Extract metadata from a single audio file. Returns None on any failure."""
    try:
        import mutagen

        audio = mutagen.File(path, easy=True)
        if audio is None:
            return None

        def _first(tag: str) -> str:
            val = audio.get(tag, [])
            return str(val[0]) if val else ""

        genre = _first("genre")
        artist = _first("artist")
        title = _first("title") or path.stem
        bpm = 0
        bpm_raw = _first("bpm")
        if bpm_raw:
            try:
                bpm = int(float(bpm_raw))
            except (ValueError, TypeError):
                pass

        if not (genre or artist):
            return None

        return {
            "title": title,
            "artist": artist,
            "genres": [genre] if genre else [],
            "bpm": bpm,
            "source": "local_files",
        }
    except Exception:
        return None
