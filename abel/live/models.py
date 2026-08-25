"""Typed model of the Live Set that is *currently open* in Ableton Live.

This complements `abel.als_parser`, which reads a saved `.als` file from disk.
The two answer different questions, and the difference matters to a producer:

    als_parser  →  what is in the project I saved
    live/models →  what Live is doing right now

A snapshot is built only from values the Live Bridge actually read out of the
Live Object Model. Nothing here is inferred. A property the bridge could not
read is ``None`` and must be reported as unknown — never defaulted to a
plausible number, because an invented sample rate is exactly the kind of
confident falsehood Abel exists to avoid.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class TrackType(str, Enum):
    """The kind of track, as distinguished by the Live Object Model."""

    AUDIO = "audio"
    MIDI = "midi"
    RETURN = "return"
    MAIN = "main"


@dataclass(frozen=True)
class Device:
    """A single device in a track's device chain."""

    name: str                      # user-visible name; the producer may have renamed it
    class_name: str                # Live's internal class ("Operator", "Eq8"), rename-stable
    is_active: bool = True         # False when present but bypassed, so it costs little CPU


@dataclass(frozen=True)
class Track:
    """One track in the Live Set."""

    index: int
    name: str
    type: TrackType
    devices: tuple[Device, ...] = ()
    is_frozen: bool = False
    is_muted: bool = False
    is_soloed: bool = False

    @property
    def active_device_count(self) -> int:
        """Devices actually processing audio on this track.

        A frozen track's devices are not processed in real time, so counting
        them would overstate the session's live CPU cost.
        """
        if self.is_frozen:
            return 0
        return sum(1 for device in self.devices if device.is_active)


@dataclass(frozen=True)
class AudioConfig:
    """The audio environment the Live Set is running in."""

    sample_rate_hz: int | None = None
    buffer_size_samples: int | None = None
    input_device: str | None = None
    output_device: str | None = None

    @property
    def output_latency_ms(self) -> float | None:
        """Approximate output buffer latency, when both values are known."""
        if self.sample_rate_hz is None or self.buffer_size_samples is None:
            return None
        return round(self.buffer_size_samples / self.sample_rate_hz * 1000, 2)


@dataclass(frozen=True)
class LiveSet:
    """Set-level properties that belong to no single track."""

    name: str | None = None
    tempo_bpm: float | None = None
    signature_numerator: int | None = None
    signature_denominator: int | None = None
    is_playing: bool | None = None


@dataclass(frozen=True)
class SessionSnapshot:
    """A complete, point-in-time observation of the producer's open Live Set.

    A snapshot is evidence, not state: it records what was true in Live at
    ``captured_at`` and is never mutated to track later changes. Observing
    again produces a new snapshot.
    """

    captured_at: datetime
    bridge_version: str
    live_set: LiveSet
    audio: AudioConfig
    live_version: str | None = None
    tracks: tuple[Track, ...] = ()
    selected_track_index: int | None = None

    @property
    def track_count(self) -> int:
        """Tracks the producer arranges on, excluding returns and the main track."""
        return sum(1 for t in self.tracks if t.type in (TrackType.AUDIO, TrackType.MIDI))

    @property
    def active_device_count(self) -> int:
        """Devices processing audio across the whole set."""
        return sum(track.active_device_count for track in self.tracks)

    @property
    def selected_track(self) -> Track | None:
        """The track the producer has selected, if the bridge reported one."""
        if self.selected_track_index is None:
            return None
        for track in self.tracks:
            if track.index == self.selected_track_index:
                return track
        return None

    def age(self, *, now: datetime | None = None) -> timedelta:
        """How long ago this observation was taken."""
        captured = self.captured_at
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
        return (now or datetime.now(timezone.utc)) - captured

    def to_dict(self) -> dict:
        """Plain-data form, for the API layer and for test fixtures."""
        return {
            "captured_at": self.captured_at.isoformat(),
            "bridge_version": self.bridge_version,
            "live_version": self.live_version,
            "live_set": {
                "name": self.live_set.name,
                "tempo_bpm": self.live_set.tempo_bpm,
                "signature_numerator": self.live_set.signature_numerator,
                "signature_denominator": self.live_set.signature_denominator,
                "is_playing": self.live_set.is_playing,
            },
            "audio": {
                "sample_rate_hz": self.audio.sample_rate_hz,
                "buffer_size_samples": self.audio.buffer_size_samples,
                "input_device": self.audio.input_device,
                "output_device": self.audio.output_device,
                "output_latency_ms": self.audio.output_latency_ms,
            },
            "tracks": [
                {
                    "index": t.index,
                    "name": t.name,
                    "type": t.type.value,
                    "is_frozen": t.is_frozen,
                    "is_muted": t.is_muted,
                    "is_soloed": t.is_soloed,
                    "active_device_count": t.active_device_count,
                    "devices": [
                        {"name": d.name, "class_name": d.class_name, "is_active": d.is_active}
                        for d in t.devices
                    ],
                }
                for t in self.tracks
            ],
            "selected_track_index": self.selected_track_index,
            "track_count": self.track_count,
            "active_device_count": self.active_device_count,
        }
