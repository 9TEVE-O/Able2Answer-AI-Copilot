"""Turn a session snapshot into the observations relevant to a question.

Selecting evidence is itself a decision worth isolating. Handing the model the
whole snapshot for every question buries the two facts that matter under two
hundred that do not, and a model given irrelevant material will reach for it.

Selection is keyword-driven and deterministic: it can be read, tested, and
argued with. What it must never do is *fabricate* — it only ever selects from
what the snapshot actually contains.
"""
from __future__ import annotations

from abel.evidence.provenance import Observation
from abel.live.models import SessionSnapshot

# Question terms that make a family of observations relevant.
_TOPICS: dict[str, tuple[str, ...]] = {
    "audio": (
        "sample", "rate", "khz", "hz", "buffer", "latency", "quality",
        "bit", "depth", "interface", "soundcard", "driver",
    ),
    "cpu": ("cpu", "load", "performance", "slow", "glitch", "crackle", "dropout", "freeze"),
    "devices": ("device", "plugin", "effect", "instrument", "chain", "rack"),
    "tracks": ("track", "tracks", "channel", "mix", "arrangement"),
    "tempo": ("tempo", "bpm", "speed", "signature", "time", "grid"),
    "selection": ("selected", "this track", "current track", "highlighted"),
}


def _topics_for(question: str) -> set[str]:
    """Which observation families this question is asking about."""
    text = question.lower()
    matched = {topic for topic, terms in _TOPICS.items() if any(t in text for t in terms)}
    # A question that matches nothing still deserves the orienting facts about
    # the session, rather than an empty bundle.
    return matched or {"audio", "tracks", "tempo"}


def observe(snapshot: SessionSnapshot, question: str) -> list[Observation]:
    """Select the observations from ``snapshot`` that bear on ``question``."""
    topics = _topics_for(question)
    at = snapshot.captured_at
    out: list[Observation] = []

    def add(key: str, label: str, value: object, unit: str | None = None,
            lom_path: str | None = None) -> None:
        out.append(
            Observation(key=key, label=label, value=value, unit=unit,
                        lom_path=lom_path, captured_at=at)
        )

    if "audio" in topics:
        add("audio.sample_rate_hz", "Sample rate", snapshot.audio.sample_rate_hz, "Hz",
            "live_app.get_document().get_data('sample_rate')")
        add("audio.buffer_size_samples", "Buffer size", snapshot.audio.buffer_size_samples,
            "samples")
        if snapshot.audio.output_latency_ms is not None:
            add("audio.output_latency_ms", "Output buffer latency",
                snapshot.audio.output_latency_ms, "ms")
        if snapshot.audio.output_device:
            add("audio.output_device", "Output device", snapshot.audio.output_device)

    if "tempo" in topics:
        add("set.tempo_bpm", "Tempo", snapshot.live_set.tempo_bpm, "BPM",
            "live_set.tempo")
        if snapshot.live_set.signature_numerator and snapshot.live_set.signature_denominator:
            add("set.signature", "Time signature",
                f"{snapshot.live_set.signature_numerator}/"
                f"{snapshot.live_set.signature_denominator}")

    if "tracks" in topics or "cpu" in topics:
        add("set.track_count", "Tracks (audio + MIDI)", snapshot.track_count, None,
            "live_set.tracks")
        frozen = sum(1 for t in snapshot.tracks if t.is_frozen)
        if frozen:
            add("set.frozen_track_count", "Frozen tracks", frozen)

    if "devices" in topics or "cpu" in topics:
        add("set.active_device_count", "Active devices", snapshot.active_device_count)
        heaviest = sorted(
            (t for t in snapshot.tracks if t.active_device_count > 0),
            key=lambda t: (-t.active_device_count, t.index),
        )[:3]
        for track in heaviest:
            add(
                f"track.{track.index}.active_device_count",
                f"Active devices on '{track.name}'",
                track.active_device_count,
                lom_path=f"live_set.tracks[{track.index}].devices",
            )

    if "selection" in topics or "devices" in topics:
        selected = snapshot.selected_track
        if selected is not None:
            add("selection.track_name", "Selected track", selected.name,
                lom_path="live_set.view.selected_track")
            add("selection.track_type", "Selected track type", selected.type.value)
            if selected.devices:
                add(
                    "selection.devices",
                    f"Device chain on '{selected.name}'",
                    ", ".join(d.class_name for d in selected.devices),
                )

    return out
