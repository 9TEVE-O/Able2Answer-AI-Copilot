"""Parse Ableton Live Set (.als) files to extract session metadata."""
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def parse_als(path: str | Path) -> dict[str, Any]:
    """Parse an Ableton .als file and return session metadata."""
    path = Path(path)
    if not path.exists():
        return {"error": f"File not found: {path}"}
    if path.suffix.lower() != ".als":
        return {"error": f"Not an .als file: {path}"}

    try:
        with gzip.open(path, "rb") as f:
            xml_data = f.read()
    except gzip.BadGzipFile:
        return {"error": "Not a valid .als file (not gzip-compressed)"}
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        return {"error": f"Failed to parse .als XML: {e}"}

    live_set = root.find("LiveSet")
    if live_set is None:
        return {"error": "Invalid .als file: missing LiveSet element"}

    tracks = _extract_tracks(live_set)
    audio_clip_data = _extract_audio_clip_sample_rates(live_set)

    return {
        "file": str(path),
        "ableton_version": root.get(
            "Creator",
            f"{root.get('MajorVersion', '?')}.{root.get('MinorVersion', '?')}",
        ),
        "tempo_bpm": _extract_tempo(live_set),
        "time_signature": _extract_time_signature(live_set),
        "tracks": tracks,
        "track_count": len(tracks),
        "audio_track_count": sum(1 for t in tracks if t["type"] == "AudioTrack"),
        "midi_track_count": sum(1 for t in tracks if t["type"] == "MidiTrack"),
        "return_track_count": sum(1 for t in tracks if t["type"] == "ReturnTrack"),
        "total_clip_count": sum(t["clip_count"] for t in tracks),
        "audio_clip_native_sample_rates": audio_clip_data["sample_rates"],
        "sample_rate_mismatch_detected": audio_clip_data["has_mismatch"],
        "devices": _extract_devices(live_set),
    }


def get_session_quality_report(path: str | Path) -> dict[str, Any]:
    """Parse an .als file and return quality-focused analysis with Ableton-specific advice."""
    session = parse_als(path)
    if "error" in session:
        return session

    issues: list[str] = []
    recommendations: list[str] = []

    rates = session["audio_clip_native_sample_rates"]
    if session["sample_rate_mismatch_detected"]:
        issues.append(
            f"Audio clips have mixed native sample rates: {rates}. "
            "Live resamples mismatched clips in real time, increasing CPU load."
        )
        recommendations.append(
            "Consolidate or re-export clips to a consistent sample rate. "
            "In Live: select the clip → Cmd+J / Ctrl+J to consolidate, "
            "or re-record at the project sample rate."
        )

    track_count = session["track_count"]
    if track_count > 32:
        issues.append(
            f"Session has {track_count} tracks. Large track counts raise CPU and RAM demand."
        )
        recommendations.append(
            "Freeze CPU-heavy tracks (right-click a track → Freeze Track) or bounce "
            "finished sections to audio to free processing resources."
        )

    if not issues:
        recommendations.append("No audio quality issues detected. Session looks clean.")

    return {
        **session,
        "quality_issues": issues,
        "recommendations": recommendations,
        "issue_count": len(issues),
    }


def _extract_tempo(live_set: ET.Element) -> float | None:
    for xpath in (
        "MasterTrack/DeviceChain/Mixer/Tempo/Manual",
        ".//Tempo/Manual",
    ):
        elem = live_set.find(xpath)
        if elem is not None:
            try:
                return float(elem.get("Value", ""))
            except (ValueError, TypeError):
                pass
    return None


def _extract_time_signature(live_set: ET.Element) -> str | None:
    pairs = [
        (
            "MasterTrack/DeviceChain/Mixer/TimeSignature/Numerator/Manual",
            "MasterTrack/DeviceChain/Mixer/TimeSignature/Denominator/Manual",
        ),
        (".//TimeSignature/Numerator/Manual", ".//TimeSignature/Denominator/Manual"),
    ]
    for num_path, den_path in pairs:
        num = live_set.find(num_path)
        den = live_set.find(den_path)
        if num is not None and den is not None:
            return f"{num.get('Value', '?')}/{den.get('Value', '?')}"
    return None


def _extract_tracks(live_set: ET.Element) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    tracks_elem = live_set.find("Tracks")
    if tracks_elem is None:
        return tracks

    for elem in tracks_elem:
        if elem.tag not in ("AudioTrack", "MidiTrack", "ReturnTrack"):
            continue
        name_elem = elem.find("Name/EffectiveName")
        name = name_elem.get("Value", "Unnamed") if name_elem is not None else "Unnamed"
        audio_clips = len(elem.findall(".//AudioClip"))
        midi_clips = len(elem.findall(".//MidiClip"))
        tracks.append({
            "type": elem.tag,
            "name": name,
            "clip_count": audio_clips + midi_clips,
            "audio_clips": audio_clips,
            "midi_clips": midi_clips,
        })

    return tracks


def _extract_audio_clip_sample_rates(live_set: ET.Element) -> dict[str, Any]:
    rates: list[int] = []
    for clip in live_set.findall(".//AudioClip"):
        sr_elem = clip.find("SampleRef/DefaultSampleRate")
        if sr_elem is not None:
            try:
                rates.append(int(float(sr_elem.get("Value", ""))))
            except (ValueError, TypeError):
                pass
    unique = sorted(set(rates))
    return {"sample_rates": unique, "has_mismatch": len(unique) > 1}


def _extract_devices(live_set: ET.Element) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []

    for plugin in live_set.findall(".//PluginDevice"):
        name = None
        for xpath in (
            ".//VstPluginInfo/PlugName",
            ".//AuPluginInfo/Name",
            ".//Vst3PluginInfo/Name",
        ):
            elem = plugin.find(xpath)
            if elem is not None:
                name = elem.get("Value")
                break
        label = f"Plugin: {name}" if name else "Plugin: Unknown"
        if label not in seen:
            seen.add(label)
            results.append(label)

    native = (
        "Simpler", "Sampler", "Operator", "Analog", "Collision",
        "Electric", "Tension", "Drift", "Meld", "Wavetable",
        "DrumGroupDevice", "InstrumentGroupDevice",
    )
    for tag in native:
        if live_set.findall(f".//{tag}"):
            label = f"Ableton: {tag}"
            if label not in seen:
                seen.add(label)
                results.append(label)

    return sorted(results)
