"""Abel music taste profile — connects listening history to personalise advice."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from abel.config import AbelConfig


def get_or_build_profile(config: "AbelConfig") -> dict | None:
    """Load the saved taste profile from disk. Returns None if not yet built."""
    from abel.music_profile.profile_store import load_profile
    return load_profile(config.db_path.parent / "taste_profile.json")


def build_taste_summary(profile: dict) -> str:
    """Return a single paragraph describing the user's musical taste for system prompt injection."""
    genres = profile.get("genres", [])
    bpm = profile.get("bpm_range", {})
    energy = profile.get("energy", "unknown")
    valence = profile.get("valence", "unknown")
    artists = profile.get("top_artists", [])
    style = profile.get("production_style", "")
    track_count = profile.get("track_count_analysed", 0)

    parts: list[str] = []
    if genres:
        parts.append(f"primarily listens to {', '.join(genres[:4])}")
    if bpm.get("avg"):
        parts.append(f"({bpm.get('min', '?')}–{bpm.get('max', '?')} BPM, avg {bpm.get('avg', '?')})")
    if energy != "unknown":
        parts.append(f"{energy} energy")
    if valence != "unknown":
        parts.append(f"{valence} mood")

    summary = "User " + ", ".join(parts) + "." if parts else "User music profile available."
    if artists:
        summary += f" Top artists: {', '.join(artists[:5])}."
    if style:
        summary += f" Tailor all production advice toward {style} music contexts."
    if track_count:
        summary += f" (Profile built from {track_count} tracks.)"
    return summary
