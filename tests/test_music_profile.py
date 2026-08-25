"""Tests for Abel music taste profile feature."""
import json
import os
import plistlib
import stat
from pathlib import Path

import pytest

from abel.music_profile import build_taste_summary
from abel.music_profile.itunes_parser import parse_itunes_library
from abel.music_profile.profile_builder import TasteProfile, build_profile
from abel.music_profile.profile_store import load_profile, save_profile


def _make_itunes_xml(tmp_path: Path) -> Path:
    tracks = {
        "1": {
            "Track ID": 1,
            "Name": "Acid Rain",
            "Artist": "Aphex Twin",
            "Genre": "Electronic",
            "BPM": 130,
            "Play Count": 50,
            "Track Type": "File",
        },
        "2": {
            "Track ID": 2,
            "Name": "Blue Calx",
            "Artist": "Aphex Twin",
            "Genre": "Ambient",
            "BPM": 90,
            "Play Count": 30,
            "Track Type": "File",
        },
        "3": {
            "Track ID": 3,
            "Name": "Internet Stream",
            "Artist": "Unknown",
            "Genre": "",
            "Track Type": "URL",  # should be skipped
        },
    }
    path = tmp_path / "iTunes Music Library.xml"
    with open(path, "wb") as f:
        plistlib.dump({"Tracks": tracks}, f)
    return path


class TestITunesParser:
    def test_skips_url_tracks(self, tmp_path):
        path = _make_itunes_xml(tmp_path)
        tracks = parse_itunes_library(path)
        assert len(tracks) == 2

    def test_extracts_genre(self, tmp_path):
        path = _make_itunes_xml(tmp_path)
        tracks = parse_itunes_library(path)
        genres = {t["genres"][0] for t in tracks if t["genres"]}
        assert "Electronic" in genres

    def test_extracts_bpm(self, tmp_path):
        path = _make_itunes_xml(tmp_path)
        tracks = parse_itunes_library(path)
        assert any(t["bpm"] == 130 for t in tracks)

    def test_extracts_play_count(self, tmp_path):
        path = _make_itunes_xml(tmp_path)
        tracks = parse_itunes_library(path)
        assert any(t["play_count"] == 50 for t in tracks)

    def test_source_is_itunes(self, tmp_path):
        path = _make_itunes_xml(tmp_path)
        tracks = parse_itunes_library(path)
        assert all(t["source"] == "itunes" for t in tracks)


class TestProfileBuilder:
    @staticmethod
    def _tracks():
        return [
            {"artist": "Artist A", "genres": ["techno"], "bpm": 132, "energy": 0.85, "valence": 0.2, "source": "spotify"},
            {"artist": "Artist B", "genres": ["techno"], "bpm": 138, "energy": 0.90, "valence": 0.15, "source": "spotify"},
            {"artist": "Artist A", "genres": ["house"],  "bpm": 124, "energy": 0.75, "valence": 0.40, "source": "itunes", "play_count": 20},
        ]

    def test_top_genre_is_techno(self):
        profile = build_profile([self._tracks()])
        assert "techno" in profile.genres[:2]

    def test_bpm_avg_in_range(self):
        profile = build_profile([self._tracks()])
        assert 124 <= profile.bpm_range["avg"] <= 138

    def test_energy_high(self):
        assert build_profile([self._tracks()]).energy == "high"

    def test_valence_dark(self):
        assert build_profile([self._tracks()]).valence == "dark"

    def test_production_style_electronic(self):
        assert build_profile([self._tracks()]).production_style == "electronic"

    def test_top_artists(self):
        assert "Artist A" in build_profile([self._tracks()]).top_artists

    def test_sources_used(self):
        assert "spotify" in build_profile([self._tracks()]).sources_used

    def test_empty_returns_profile(self):
        assert isinstance(build_profile([]), TasteProfile)

    def test_round_trip_dict(self):
        profile = build_profile([self._tracks()])
        restored = TasteProfile.from_dict(profile.to_dict())
        assert restored.genres == profile.genres


class TestProfileStore:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "profile.json"
        data = {"genres": ["techno"], "bpm_range": {"avg": 130}}
        save_profile(data, path)
        assert load_profile(path) == data

    def test_file_permissions_600(self, tmp_path):
        path = tmp_path / "profile.json"
        save_profile({"genres": []}, path)
        mode = oct(stat.S_IMODE(os.stat(path).st_mode))
        assert mode == "0o600"

    def test_load_missing_returns_none(self, tmp_path):
        assert load_profile(tmp_path / "missing.json") is None

    def test_load_invalid_json_returns_none(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json")
        assert load_profile(path) is None


class TestTasteSummary:
    _profile = {
        "genres": ["techno", "deep house"],
        "bpm_range": {"min": 120, "max": 145, "avg": 130},
        "energy": "high",
        "valence": "dark",
        "top_artists": ["Aphex Twin", "Burial"],
        "production_style": "electronic",
        "track_count_analysed": 100,
    }

    def test_includes_top_genre(self):
        assert "techno" in build_taste_summary(self._profile)

    def test_includes_top_artist(self):
        assert "Aphex Twin" in build_taste_summary(self._profile)

    def test_includes_style(self):
        assert "electronic" in build_taste_summary(self._profile)

    def test_returns_string_for_empty_profile(self):
        assert isinstance(build_taste_summary({}), str)
