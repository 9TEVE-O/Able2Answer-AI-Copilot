"""Tests for Abel .als file parser."""
import gzip
import io
from pathlib import Path

import pytest

from abel.als_parser import get_session_quality_report, parse_als

_ALS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="11" MinorVersion="11.3.2" SchemaChangeCount="3" Creator="Ableton Live 11.3.2" Revision="">
  <LiveSet>
    <Tracks>
      <AudioTrack Id="1">
        <Name><EffectiveName Value="Kick" /></Name>
        <Clips>
          <AudioClip Id="1">
            <SampleRef><DefaultSampleRate Value="44100" /></SampleRef>
          </AudioClip>
        </Clips>
      </AudioTrack>
      <AudioTrack Id="2">
        <Name><EffectiveName Value="Snare" /></Name>
        <Clips>
          <AudioClip Id="2">
            <SampleRef><DefaultSampleRate Value="48000" /></SampleRef>
          </AudioClip>
        </Clips>
      </AudioTrack>
      <MidiTrack Id="3">
        <Name><EffectiveName Value="Bass Synth" /></Name>
        <Clips><MidiClip Id="3" /></Clips>
      </MidiTrack>
      <ReturnTrack Id="4">
        <Name><EffectiveName Value="Reverb" /></Name>
      </ReturnTrack>
    </Tracks>
    <MasterTrack>
      <DeviceChain>
        <Mixer>
          <Tempo><Manual Value="128.0" /></Tempo>
          <TimeSignature>
            <Numerator><Manual Value="4" /></Numerator>
            <Denominator><Manual Value="4" /></Denominator>
          </TimeSignature>
        </Mixer>
      </DeviceChain>
    </MasterTrack>
  </LiveSet>
</Ableton>"""


def _make_als_file(tmp_path: Path, xml: str = _ALS_XML) -> Path:
    als_path = tmp_path / "test_session.als"
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(xml.encode("utf-8"))
    als_path.write_bytes(buf.getvalue())
    return als_path


class TestParseAls:
    def test_parses_valid_file(self, tmp_path):
        result = parse_als(_make_als_file(tmp_path))
        assert "error" not in result
        assert result["ableton_version"] == "Ableton Live 11.3.2"

    def test_extracts_tempo(self, tmp_path):
        result = parse_als(_make_als_file(tmp_path))
        assert result["tempo_bpm"] == 128.0

    def test_extracts_time_signature(self, tmp_path):
        result = parse_als(_make_als_file(tmp_path))
        assert result["time_signature"] == "4/4"

    def test_counts_tracks_by_type(self, tmp_path):
        result = parse_als(_make_als_file(tmp_path))
        assert result["audio_track_count"] == 2
        assert result["midi_track_count"] == 1
        assert result["return_track_count"] == 1
        assert result["track_count"] == 4

    def test_extracts_track_names(self, tmp_path):
        result = parse_als(_make_als_file(tmp_path))
        names = [t["name"] for t in result["tracks"]]
        assert "Kick" in names
        assert "Bass Synth" in names

    def test_counts_clips(self, tmp_path):
        result = parse_als(_make_als_file(tmp_path))
        assert result["total_clip_count"] == 3

    def test_detects_sample_rate_mismatch(self, tmp_path):
        result = parse_als(_make_als_file(tmp_path))
        assert result["sample_rate_mismatch_detected"] is True
        assert 44100 in result["audio_clip_native_sample_rates"]
        assert 48000 in result["audio_clip_native_sample_rates"]

    def test_no_mismatch_when_rates_consistent(self, tmp_path):
        xml = _ALS_XML.replace(
            '<DefaultSampleRate Value="48000" />',
            '<DefaultSampleRate Value="44100" />',
        )
        result = parse_als(_make_als_file(tmp_path, xml))
        assert result["sample_rate_mismatch_detected"] is False

    def test_file_not_found(self, tmp_path):
        result = parse_als(tmp_path / "missing.als")
        assert "error" in result

    def test_wrong_extension(self, tmp_path):
        f = tmp_path / "song.wav"
        f.write_bytes(b"")
        result = parse_als(f)
        assert "error" in result

    def test_not_gzip(self, tmp_path):
        f = tmp_path / "fake.als"
        f.write_bytes(b"not gzip data")
        result = parse_als(f)
        assert "error" in result


class TestSessionQualityReport:
    def test_detects_sample_rate_mismatch_issue(self, tmp_path):
        report = get_session_quality_report(_make_als_file(tmp_path))
        assert report["issue_count"] >= 1
        assert any("sample rate" in i.lower() for i in report["quality_issues"])

    def test_no_issues_for_clean_session(self, tmp_path):
        xml = _ALS_XML.replace(
            '<DefaultSampleRate Value="48000" />',
            '<DefaultSampleRate Value="44100" />',
        )
        report = get_session_quality_report(_make_als_file(tmp_path, xml))
        assert report["issue_count"] == 0
        assert len(report["recommendations"]) > 0

    def test_passes_through_parse_error(self, tmp_path):
        report = get_session_quality_report(tmp_path / "missing.als")
        assert "error" in report
