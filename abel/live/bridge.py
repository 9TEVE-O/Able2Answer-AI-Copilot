"""The boundary between Live's loosely-typed bridge payload and Abel's typed core.

Everything arriving from the Live Bridge is untrusted in the ordinary
engineering sense: Max/JS is dynamically typed, the Live Object Model reports
booleans as 0/1 and numbers as floats, and a property the bridge cannot read
arrives missing rather than wrong. This module is the single place that turns
any of that into a `SessionSnapshot` — or refuses to.

The distinction it keeps is between a payload that is *unusable* and one that is
merely *incomplete*. An unusable payload raises. An incomplete one is accepted
with the missing readings as ``None``, so Abel can say what it does not know.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from abel.live.models import AudioConfig, Device, LiveSet, SessionSnapshot, Track, TrackType


class BridgePayloadError(ValueError):
    """The bridge sent something that cannot be read as a session snapshot."""


def _coerce_int(value: Any, *, allow_zero: bool = False) -> int | None:
    """Read an integer from Live, which may deliver it as a float or a string."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or (number == 0 and not allow_zero):
        return None
    return int(round(number))


def _coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    """Read a boolean from Live, which reports flags as 0/1 rather than true/false."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return default


def _parse_track_type(raw: Any, *, index: int) -> TrackType:
    if isinstance(raw, str):
        try:
            return TrackType(raw.strip().lower())
        except ValueError:
            pass
    raise BridgePayloadError(f"track {index}: unrecognised track type {raw!r}")


def _parse_device(raw: Any, *, track_index: int) -> Device:
    if not isinstance(raw, dict):
        raise BridgePayloadError(f"track {track_index}: device entry is not an object")
    name = raw.get("name")
    class_name = raw.get("class_name") or raw.get("type")
    if not isinstance(name, str) or not isinstance(class_name, str):
        raise BridgePayloadError(
            f"track {track_index}: device is missing name or class_name"
        )
    return Device(
        name=name,
        class_name=class_name,
        # Live reports a bypassed device as is_active 0; absent means active.
        is_active=_coerce_bool(raw.get("is_active"), default=True),
    )


def _parse_track(raw: Any, *, position: int) -> Track:
    if not isinstance(raw, dict):
        raise BridgePayloadError(f"track {position}: entry is not an object")
    name = raw.get("name")
    if not isinstance(name, str):
        raise BridgePayloadError(f"track {position}: missing name")
    devices = raw.get("devices") or []
    if not isinstance(devices, list):
        raise BridgePayloadError(f"track {position}: devices is not a list")
    index = _coerce_int(raw.get("index"), allow_zero=True)
    return Track(
        index=position if index is None else index,
        name=name,
        type=_parse_track_type(raw.get("type"), index=position),
        devices=tuple(_parse_device(d, track_index=position) for d in devices),
        is_frozen=_coerce_bool(raw.get("is_frozen")),
        is_muted=_coerce_bool(raw.get("is_muted")),
        is_soloed=_coerce_bool(raw.get("is_soloed")),
    )


def _parse_timestamp(raw: Any) -> datetime:
    """Use the bridge's capture time when it sent a usable one, else time of receipt."""
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def parse_snapshot(payload: Any) -> SessionSnapshot:
    """Turn one raw Live Bridge payload into a validated `SessionSnapshot`.

    Raises `BridgePayloadError` when the payload is structurally unusable.
    """
    if not isinstance(payload, dict):
        raise BridgePayloadError("payload is not an object")

    bridge_version = payload.get("bridge_version")
    if not isinstance(bridge_version, str) or not bridge_version.strip():
        raise BridgePayloadError("payload is missing bridge_version")

    raw_set = payload.get("set") or payload.get("live_set") or {}
    if not isinstance(raw_set, dict):
        raise BridgePayloadError("'set' is not an object")

    raw_audio = payload.get("audio") or {}
    if not isinstance(raw_audio, dict):
        raise BridgePayloadError("'audio' is not an object")

    raw_tracks = payload.get("tracks") or []
    if not isinstance(raw_tracks, list):
        raise BridgePayloadError("'tracks' is not a list")

    tracks = tuple(
        _parse_track(raw, position=position) for position, raw in enumerate(raw_tracks)
    )

    # A selection naming a track the bridge did not send is not a selection we
    # can describe, so it is dropped rather than reported as an index alone.
    selected = _coerce_int(payload.get("selected_track_index"), allow_zero=True)
    if selected is not None and all(track.index != selected for track in tracks):
        selected = None

    return SessionSnapshot(
        captured_at=_parse_timestamp(payload.get("captured_at")),
        bridge_version=bridge_version,
        live_version=payload.get("live_version"),
        live_set=LiveSet(
            name=raw_set.get("name"),
            tempo_bpm=_coerce_float(raw_set.get("tempo", raw_set.get("tempo_bpm"))),
            signature_numerator=_coerce_int(raw_set.get("signature_numerator")),
            signature_denominator=_coerce_int(raw_set.get("signature_denominator")),
            is_playing=(
                None
                if raw_set.get("is_playing") is None
                else _coerce_bool(raw_set.get("is_playing"))
            ),
        ),
        audio=AudioConfig(
            sample_rate_hz=_coerce_int(
                raw_audio.get("sample_rate", raw_audio.get("sample_rate_hz"))
            ),
            buffer_size_samples=_coerce_int(
                raw_audio.get("buffer_size", raw_audio.get("buffer_size_samples"))
            ),
            input_device=raw_audio.get("input_device"),
            output_device=raw_audio.get("output_device"),
        ),
        tracks=tracks,
        selected_track_index=selected,
    )
