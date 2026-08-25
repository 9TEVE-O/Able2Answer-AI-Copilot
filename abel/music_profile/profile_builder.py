"""Aggregate tracks from multiple sources into a TasteProfile."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from statistics import mean
from typing import Any

_ELECTRONIC = {
    "techno", "house", "deep house", "tech house", "minimal", "drum and bass",
    "dnb", "jungle", "dubstep", "ambient", "electronica", "electronic",
    "idm", "industrial", "rave", "trance", "progressive trance", "psytrance",
    "hardcore", "hardstyle", "electro", "synth-pop", "synthpop", "downtempo",
    "trip-hop", "breaks", "uk garage", "grime", "bass music", "edm",
}
_ACOUSTIC = {
    "country", "folk", "bluegrass", "acoustic", "singer-songwriter", "americana",
    "blues", "roots", "gospel", "soul", "r&b", "jazz", "classical", "world",
}
_HIPHOP = {"hip hop", "hip-hop", "rap", "trap", "lo-fi hip hop", "lo-fi", "boom bap"}
_ROCK = {"rock", "alternative", "indie", "metal", "punk", "pop rock", "grunge"}


@dataclass
class TasteProfile:
    genres: list[str] = field(default_factory=list)
    bpm_range: dict[str, int] = field(default_factory=dict)
    energy: str = "unknown"
    valence: str = "unknown"
    top_artists: list[str] = field(default_factory=list)
    production_style: str = ""
    sources_used: list[str] = field(default_factory=list)
    track_count_analysed: int = 0
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "genres": self.genres,
            "bpm_range": self.bpm_range,
            "energy": self.energy,
            "valence": self.valence,
            "top_artists": self.top_artists,
            "production_style": self.production_style,
            "sources_used": self.sources_used,
            "track_count_analysed": self.track_count_analysed,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TasteProfile":
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in valid})


def build_profile(source_tracks: list[list[dict[str, Any]]]) -> TasteProfile:
    """Aggregate track lists from multiple sources into a TasteProfile."""
    all_tracks = [t for source in source_tracks for t in source]
    if not all_tracks:
        return TasteProfile(last_updated=str(date.today()))

    sources_used = sorted({t.get("source", "") for t in all_tracks if t.get("source")})

    # Genre frequency weighted by play count
    genre_counter: Counter = Counter()
    for t in all_tracks:
        weight = max(t.get("play_count", 1), 1)
        for g in t.get("genres", []):
            if g:
                genre_counter[g.lower().strip()] += weight
    top_genres = [g for g, _ in genre_counter.most_common(10)]

    # BPM stats (filter implausible values)
    bpms = [t["bpm"] for t in all_tracks if t.get("bpm") and 50 < t["bpm"] < 300]
    bpm_range: dict[str, int] = {}
    if bpms:
        bpm_range = {"min": min(bpms), "max": max(bpms), "avg": int(mean(bpms))}

    # Energy / valence from Spotify audio features
    energies = [t["energy"] for t in all_tracks if t.get("energy") is not None]
    valences = [t["valence"] for t in all_tracks if t.get("valence") is not None]
    avg_energy = mean(energies) if energies else None
    avg_valence = mean(valences) if valences else None

    energy_label = "unknown"
    if avg_energy is not None:
        energy_label = "high" if avg_energy > 0.7 else ("medium" if avg_energy > 0.4 else "low")

    valence_label = "unknown"
    if avg_valence is not None:
        valence_label = "bright" if avg_valence > 0.6 else ("mixed" if avg_valence > 0.35 else "dark")

    # Top artists weighted by play count
    artist_counter: Counter = Counter()
    for t in all_tracks:
        if t.get("artist"):
            artist_counter[t["artist"]] += max(t.get("play_count", 1), 1)
    top_artists = [a for a, _ in artist_counter.most_common(10)]

    return TasteProfile(
        genres=top_genres,
        bpm_range=bpm_range,
        energy=energy_label,
        valence=valence_label,
        top_artists=top_artists,
        production_style=_classify_style(top_genres),
        sources_used=sources_used,
        track_count_analysed=len(all_tracks),
        last_updated=str(date.today()),
    )


def _classify_style(genres: list[str]) -> str:
    if not genres:
        return ""
    top5 = set(genres[:5])
    scores = {
        "electronic": len(top5 & _ELECTRONIC),
        "hip-hop/urban": len(top5 & _HIPHOP),
        "acoustic/roots": len(top5 & _ACOUSTIC),
        "rock/alternative": len(top5 & _ROCK),
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else (genres[0] if genres else "")
