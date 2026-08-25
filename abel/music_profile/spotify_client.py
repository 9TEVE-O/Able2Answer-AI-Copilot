"""Fetch listening data from Spotify Web API via spotipy."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def fetch_spotify_tracks(
    client_id: str,
    client_secret: str,
    token_path: Path,
) -> list[dict[str, Any]]:
    """
    Authenticate with Spotify (opens browser on first run) and return a list
    of track dicts with genre, bpm, energy, danceability, valence, and artist.
    """
    try:
        import spotipy
        from spotipy.cache_handler import CacheFileHandler
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        raise RuntimeError("Spotify integration requires spotipy: pip install spotipy")

    token_path.parent.mkdir(parents=True, exist_ok=True)
    cache = CacheFileHandler(cache_path=str(token_path))

    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri="http://localhost:8888/callback",
            scope="user-top-read user-library-read",
            cache_handler=cache,
            open_browser=True,
        )
    )

    # Top artists → genre map
    artist_genres: dict[str, list[str]] = {}
    top_artists = sp.current_user_top_artists(limit=50, time_range="medium_term")
    for artist in top_artists.get("items", []):
        artist_genres[artist["name"]] = artist.get("genres", [])

    # Top tracks
    top_tracks_resp = sp.current_user_top_tracks(limit=50, time_range="medium_term")
    track_items = top_tracks_resp.get("items", [])

    # Audio features in batches of 50
    track_ids = [t["id"] for t in track_items if t.get("id")]
    features_map: dict[str, dict] = {}
    for i in range(0, len(track_ids), 50):
        batch = track_ids[i : i + 50]
        feats = sp.audio_features(batch) or []
        for f in feats:
            if f:
                features_map[f["id"]] = f

    tracks: list[dict[str, Any]] = []
    for item in track_items:
        tid = item.get("id", "")
        artist_name = item["artists"][0]["name"] if item.get("artists") else ""
        genres = artist_genres.get(artist_name, [])
        feats = features_map.get(tid, {})
        tracks.append({
            "title": item.get("name", ""),
            "artist": artist_name,
            "genres": genres,
            "bpm": int(feats.get("tempo", 0)),
            "energy": feats.get("energy"),
            "danceability": feats.get("danceability"),
            "valence": feats.get("valence"),
            "source": "spotify",
        })

    return tracks
