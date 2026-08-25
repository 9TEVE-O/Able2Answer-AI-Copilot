"""Tests for the Live Bridge boundary: raw Max payload -> typed SessionSnapshot.

The payload shapes here are the ones the Max device actually emits, including
its quirks: booleans as 0/1, numbers as floats, and absent readings as null.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from abel.live.bridge import BridgePayloadError, parse_snapshot
from abel.live.models import TrackType

FIXTURE = Path(__file__).parent / "fixtures" / "bridge_payload.json"


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def snapshot(payload):
    return parse_snapshot(payload)


class TestRealisticPayload:
    """The end-to-end shape a real Live Set produces."""

    def test_reads_set_level_properties(self, snapshot):
        assert snapshot.live_set.tempo_bpm == 126.0
        assert snapshot.live_set.signature_numerator == 4
        assert snapshot.live_set.signature_denominator == 4
        assert snapshot.live_version == "Live 12.1.1"
        assert snapshot.bridge_version == "0.1.0"

    def test_reads_audio_config(self, snapshot):
        assert snapshot.audio.sample_rate_hz == 48000
        assert snapshot.audio.buffer_size_samples == 256

    def test_derives_output_latency(self, snapshot):
        # 256 samples at 48 kHz is 5.33 ms.
        assert snapshot.audio.output_latency_ms == pytest.approx(5.33)

    def test_track_count_excludes_return_tracks(self, snapshot):
        # Four tracks in the payload, but "A Reverb" is a return.
        assert len(snapshot.tracks) == 4
        assert snapshot.track_count == 3

    def test_parses_track_types(self, snapshot):
        assert snapshot.tracks[0].type is TrackType.AUDIO
        assert snapshot.tracks[1].type is TrackType.MIDI
        assert snapshot.tracks[3].type is TrackType.RETURN

    def test_selected_track_resolves_to_the_track_itself(self, snapshot):
        assert snapshot.selected_track is not None
        assert snapshot.selected_track.name == "Bass"


class TestDeviceCounting:
    """Active device counting is the basis of Abel's CPU answers, so it is exact."""

    def test_bypassed_devices_are_not_active(self, snapshot):
        kick = snapshot.tracks[0]
        assert len(kick.devices) == 2
        assert kick.active_device_count == 1     # EQ Eight is bypassed

    def test_frozen_tracks_contribute_no_active_devices(self, snapshot):
        pads = snapshot.tracks[2]
        assert pads.is_frozen
        assert len(pads.devices) == 2
        # A frozen track is not processed in real time, so its devices cost nothing.
        assert pads.active_device_count == 0

    def test_set_wide_active_device_count(self, snapshot):
        # Kick 1 + Bass 2 + Pads 0 (frozen) + return 1
        assert snapshot.active_device_count == 4


class TestLiveValueQuirks:
    """Live reports through Max in shapes Python would not choose."""

    def test_zero_and_one_are_read_as_booleans(self, payload):
        payload["tracks"][0]["is_muted"] = 1
        payload["set"]["is_playing"] = 1
        snapshot = parse_snapshot(payload)
        assert snapshot.tracks[0].is_muted is True
        assert snapshot.live_set.is_playing is True

    def test_floats_are_read_as_integers(self, payload):
        payload["audio"]["sample_rate"] = 44100.0
        assert parse_snapshot(payload).audio.sample_rate_hz == 44100

    def test_device_absent_is_active_defaults_to_active(self, payload):
        del payload["tracks"][1]["devices"][0]["is_active"]
        snapshot = parse_snapshot(payload)
        assert snapshot.tracks[1].devices[0].is_active is True

    def test_track_index_zero_is_a_real_index_not_a_missing_one(self, payload):
        payload["selected_track_index"] = 0
        snapshot = parse_snapshot(payload)
        assert snapshot.selected_track_index == 0
        assert snapshot.selected_track.name == "Kick"


class TestMissingReadings:
    """An unreadable value stays unknown; it is never defaulted to a plausible one."""

    def test_unreported_sample_rate_is_none(self, payload):
        payload["audio"]["sample_rate"] = None
        snapshot = parse_snapshot(payload)
        assert snapshot.audio.sample_rate_hz is None

    def test_unreported_sample_rate_yields_no_latency(self, payload):
        payload["audio"]["sample_rate"] = None
        assert parse_snapshot(payload).audio.output_latency_ms is None

    def test_missing_audio_block_entirely(self, payload):
        del payload["audio"]
        snapshot = parse_snapshot(payload)
        assert snapshot.audio.sample_rate_hz is None
        assert snapshot.audio.buffer_size_samples is None

    def test_a_set_with_no_tracks_is_valid_not_an_error(self, payload):
        payload["tracks"] = []
        snapshot = parse_snapshot(payload)
        assert snapshot.tracks == ()
        assert snapshot.track_count == 0

    def test_selection_naming_an_unsent_track_is_dropped(self, payload):
        payload["selected_track_index"] = 99
        snapshot = parse_snapshot(payload)
        assert snapshot.selected_track_index is None
        assert snapshot.selected_track is None


class TestUnusablePayloads:
    """Structurally broken payloads raise rather than producing a half-snapshot."""

    def test_not_an_object(self):
        with pytest.raises(BridgePayloadError):
            parse_snapshot([1, 2, 3])

    def test_missing_bridge_version(self, payload):
        del payload["bridge_version"]
        with pytest.raises(BridgePayloadError, match="bridge_version"):
            parse_snapshot(payload)

    def test_unrecognised_track_type(self, payload):
        payload["tracks"][0]["type"] = "quantum"
        with pytest.raises(BridgePayloadError, match="track type"):
            parse_snapshot(payload)

    def test_track_missing_a_name(self, payload):
        del payload["tracks"][0]["name"]
        with pytest.raises(BridgePayloadError, match="missing name"):
            parse_snapshot(payload)

    def test_device_missing_identity(self, payload):
        payload["tracks"][0]["devices"][0] = {"is_active": 1}
        with pytest.raises(BridgePayloadError, match="class_name"):
            parse_snapshot(payload)


class TestCaptureTime:
    """The bridge cannot stamp an ISO time, so Abel stamps on receipt."""

    def test_null_capture_time_becomes_receipt_time(self, snapshot):
        assert snapshot.captured_at.tzinfo is not None
        assert snapshot.age() < timedelta(seconds=5)

    def test_bridge_supplied_time_is_honoured(self, payload):
        payload["captured_at"] = "2026-08-25T04:00:00Z"
        snapshot = parse_snapshot(payload)
        assert snapshot.captured_at == datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc)

    def test_unparseable_time_falls_back_to_receipt_time(self, payload):
        payload["captured_at"] = "last tuesday"
        assert parse_snapshot(payload).age() < timedelta(seconds=5)
