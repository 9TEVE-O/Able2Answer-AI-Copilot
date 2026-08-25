"""Ableton Live audio quality knowledge base - local data, no external calls."""
from typing import Any, Dict

SAMPLE_RATES: Dict[int, Dict[str, Any]] = {
    44100: {
        "name": "44.1 kHz",
        "description": "CD-quality standard. Most music distribution targets this rate.",
        "ableton_default": True,
        "use_cases": ["Music production for streaming/CD", "Final mixdown for most release formats"],
        "nyquist_frequency": 22050,
        "relative_cpu": 1.0,
        "relative_storage": 1.0,
        "ableton_notes": (
            "Ableton Live's default. Ideal for most music production workflows. "
            "All Live instruments and effects are optimized at this rate."
        ),
    },
    48000: {
        "name": "48 kHz",
        "description": "Video/broadcast standard. Used in film, TV, and game audio.",
        "ableton_default": False,
        "use_cases": ["Video scoring", "Film/TV production", "Broadcast audio", "Game audio"],
        "nyquist_frequency": 24000,
        "relative_cpu": 1.09,
        "relative_storage": 1.09,
        "ableton_notes": (
            "Use when exporting audio for video. Avoids sample-rate conversion artifacts "
            "when syncing with video editing software like Premiere Pro or Final Cut Pro."
        ),
    },
    88200: {
        "name": "88.2 kHz",
        "description": "Double 44.1 kHz. Hi-res for audio that will be downsampled to 44.1 kHz.",
        "ableton_default": False,
        "use_cases": ["High-fidelity recording", "Mastering source files"],
        "nyquist_frequency": 44100,
        "relative_cpu": 2.0,
        "relative_storage": 2.0,
        "ableton_notes": (
            "Doubles CPU load. Useful when recording hardware and planning to downsample to 44.1 kHz "
            "for release. Niche — most producers use 44.1 or 96 kHz instead."
        ),
    },
    96000: {
        "name": "96 kHz",
        "description": "Hi-res audio standard. Captures ultrasonic content above human hearing.",
        "ableton_default": False,
        "use_cases": ["Professional recording", "Mastering", "Sound design for film"],
        "nyquist_frequency": 48000,
        "relative_cpu": 2.18,
        "relative_storage": 2.18,
        "ableton_notes": (
            "Roughly doubles CPU load vs 44.1 kHz. Set in Live Preferences → Audio. "
            "Beneficial when recording acoustic instruments or applying heavy processing."
        ),
    },
    192000: {
        "name": "192 kHz",
        "description": "Ultra hi-res. Rarely needed; very high CPU and storage cost.",
        "ableton_default": False,
        "use_cases": ["Academic/archival recording", "Specialist mastering"],
        "nyquist_frequency": 96000,
        "relative_cpu": 4.35,
        "relative_storage": 4.35,
        "ableton_notes": (
            "Quadruples CPU load vs 44.1 kHz. Not recommended for typical production. "
            "Most converters and plugins do not benefit above 96 kHz."
        ),
    },
}

BIT_DEPTHS: Dict[Any, Dict[str, Any]] = {
    16: {
        "name": "16-bit",
        "bits_per_sample": 16,
        "dynamic_range_db": 96,
        "ableton_default": False,
        "is_float": False,
        "use_cases": ["CD distribution", "Legacy formats"],
        "ableton_notes": (
            "96 dB dynamic range. Sufficient for final delivery to CD/streaming. "
            "Live internally processes at 32-bit float, so 16-bit export applies dithering."
        ),
    },
    24: {
        "name": "24-bit",
        "bits_per_sample": 24,
        "dynamic_range_db": 144,
        "ableton_default": True,
        "is_float": False,
        "use_cases": ["Professional recording", "Mixdown", "Session work"],
        "ableton_notes": (
            "Ableton Live's default export bit depth. 144 dB dynamic range — "
            "more than enough headroom for any production. Recommended for all session work."
        ),
    },
    "32f": {
        "name": "32-bit float",
        "bits_per_sample": 32,
        "dynamic_range_db": 1528,
        "ableton_default": False,
        "is_float": True,
        "use_cases": ["Stem exports", "Audio passed between DAWs", "Archival bounces"],
        "ableton_notes": (
            "Matches Live's internal processing format. No clipping possible — "
            "values above 0 dBFS are preserved. Ideal for stems you'll re-import into Live."
        ),
    },
    "64f": {
        "name": "64-bit float",
        "bits_per_sample": 64,
        "dynamic_range_db": 36080,
        "ableton_default": False,
        "is_float": True,
        "use_cases": ["Scientific audio", "Ultra-high-precision archival"],
        "ableton_notes": (
            "Doubles file size vs 32-bit float with no audible benefit in any production context. "
            "Not recommended unless interoperating with scientific/academic audio tools."
        ),
    },
}

USE_CASE_RECOMMENDATIONS: Dict[str, Dict[str, Any]] = {
    "music_production": {
        "sample_rate": 44100,
        "bit_depth": 24,
        "rationale": (
            "44.1 kHz/24-bit is the Ableton Live default and the industry standard for music. "
            "All streaming platforms (Spotify, Apple Music) accept 44.1 kHz, and 24-bit gives "
            "plenty of headroom during production without the CPU cost of higher rates."
        ),
    },
    "video_scoring": {
        "sample_rate": 48000,
        "bit_depth": 24,
        "rationale": (
            "48 kHz is the video/broadcast standard. Using it avoids sample-rate conversion "
            "when exporting to video editing software. 24-bit preserves full dynamic range."
        ),
    },
    "stems_export": {
        "sample_rate": 44100,
        "bit_depth": "32f",
        "rationale": (
            "32-bit float matches Live's internal processing — no clipping, no rounding loss. "
            "Stems exported at 32f can be re-imported into Live without quality degradation."
        ),
    },
    "live_performance": {
        "sample_rate": 44100,
        "bit_depth": 24,
        "rationale": (
            "44.1 kHz keeps CPU load low, critical for real-time performance stability. "
            "24-bit is sufficient and avoids the latency/CPU overhead of higher sample rates."
        ),
    },
    "podcast": {
        "sample_rate": 44100,
        "bit_depth": 16,
        "rationale": (
            "Podcasts are speech content distributed as compressed audio (MP3/AAC). "
            "44.1 kHz/16-bit produces small, compatible files with no audible quality loss."
        ),
    },
    "archival": {
        "sample_rate": 96000,
        "bit_depth": "32f",
        "rationale": (
            "96 kHz captures the full audible spectrum with headroom above. "
            "32-bit float preserves the complete dynamic range for future remastering."
        ),
    },
}

ABLETON_EXPORT_FORMATS: Dict[str, Dict[str, Any]] = {
    "wav": {
        "name": "WAV",
        "lossless": True,
        "ableton_menu": "File → Export Audio/Video (Cmd+Shift+R / Ctrl+Shift+R)",
        "supports_bit_depths": [16, 24, "32f"],
        "notes": "Universal lossless format. Best for stems, masters, and archival.",
    },
    "aiff": {
        "name": "AIFF",
        "lossless": True,
        "ableton_menu": "File → Export Audio/Video (Cmd+Shift+R / Ctrl+Shift+R)",
        "supports_bit_depths": [16, 24, "32f"],
        "notes": "Apple lossless format. Equivalent quality to WAV; preferred on macOS workflows.",
    },
    "flac": {
        "name": "FLAC",
        "lossless": True,
        "ableton_menu": "File → Export Audio/Video (Cmd+Shift+R / Ctrl+Shift+R)",
        "supports_bit_depths": [16, 24],
        "notes": "Lossless compressed. Smaller than WAV/AIFF with zero quality loss.",
    },
    "mp3": {
        "name": "MP3",
        "lossless": False,
        "ableton_menu": "File → Export Audio/Video (Cmd+Shift+R / Ctrl+Shift+R)",
        "supports_bit_depths": [],
        "notes": "Lossy. Use only for final distribution where file size matters. Not for stems.",
    },
}
