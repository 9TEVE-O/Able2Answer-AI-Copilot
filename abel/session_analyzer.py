"""Pure-function tools for analyzing Ableton Live session audio quality settings."""
from typing import Any

from abel.knowledge_base import BIT_DEPTHS, SAMPLE_RATES, USE_CASE_RECOMMENDATIONS

# Model-supplied tool arguments arrive in whatever shape the LLM chose to emit:
# "24" and 24 are both natural readings of the same schema, and "32-bit float",
# "32f" and 32 all name one Ableton format. Normalize at the tool boundary so a
# lookup miss means the value is genuinely unsupported, never merely misspelled.


def _normalize_bit_depth(bit_depth: Any) -> Any:
    """Coerce a bit depth to its BIT_DEPTHS key (16, 24, '32f', '64f')."""
    if isinstance(bit_depth, bool):  # bool is an int subclass — reject explicitly
        return bit_depth
    if isinstance(bit_depth, float) and bit_depth.is_integer():
        bit_depth = int(bit_depth)
    if isinstance(bit_depth, str):
        text = bit_depth.strip().lower()
        digits = "".join(c for c in text if c.isdigit())
        if not digits:
            return bit_depth
        bit_depth = int(digits)
    if isinstance(bit_depth, int):
        # Live represents 32- and 64-bit depths as float formats.
        if bit_depth in (32, 64):
            return f"{bit_depth}f"
        return bit_depth
    return bit_depth


def _normalize_sample_rate(sample_rate: Any) -> Any:
    """Coerce a sample rate to Hz (e.g. '44.1 kHz', '48k', 48000.0 -> 48000)."""
    if isinstance(sample_rate, bool):
        return sample_rate
    if isinstance(sample_rate, float) and sample_rate.is_integer():
        return int(sample_rate)
    if isinstance(sample_rate, str):
        text = sample_rate.strip().lower().replace(",", "").replace(" ", "")
        is_khz = "khz" in text or (text.endswith("k") and "hz" not in text)
        number = text.replace("khz", "").replace("hz", "").rstrip("k")
        try:
            value = float(number)
        except ValueError:
            return sample_rate
        if is_khz or value < 1000:  # bare "44.1" means kHz, not Hz
            value *= 1000
        return int(round(value))
    return sample_rate


def _normalize_use_case(use_case: Any) -> Any:
    """Coerce a use case to its USE_CASE_RECOMMENDATIONS key."""
    if not isinstance(use_case, str):
        return use_case
    return use_case.strip().lower().replace("-", "_").replace(" ", "_")


def get_sample_rate_info(sample_rate: int) -> dict[str, Any]:
    sample_rate = _normalize_sample_rate(sample_rate)
    info = SAMPLE_RATES.get(sample_rate)
    if info is None:
        return {
            "error": f"Unknown sample rate: {sample_rate} Hz",
            "valid_sample_rates": sorted(SAMPLE_RATES.keys()),
        }
    return {"sample_rate": sample_rate, **info}


def get_bit_depth_info(bit_depth: int | str) -> dict[str, Any]:
    bit_depth = _normalize_bit_depth(bit_depth)
    info = BIT_DEPTHS.get(bit_depth)
    if info is None:
        return {
            "error": f"Unknown bit depth: {bit_depth}",
            "valid_bit_depths": list(BIT_DEPTHS.keys()),
        }
    return {"bit_depth": bit_depth, **info}


def calculate_file_size(
    duration_seconds: float,
    sample_rate: int,
    bit_depth: int | str,
    channels: int = 2,
) -> dict[str, Any]:
    sample_rate = _normalize_sample_rate(sample_rate)
    bit_depth = _normalize_bit_depth(bit_depth)
    depth_info = BIT_DEPTHS.get(bit_depth)
    if depth_info is None:
        return {
            "error": f"Unknown bit depth: {bit_depth}",
            "valid_bit_depths": list(BIT_DEPTHS.keys()),
        }
    if sample_rate not in SAMPLE_RATES:
        return {
            "error": f"Unknown sample rate: {sample_rate}",
            "valid_sample_rates": sorted(SAMPLE_RATES.keys()),
        }

    bits = depth_info["bits_per_sample"]
    bytes_per_second = (sample_rate * channels * bits) / 8
    total_bytes = bytes_per_second * duration_seconds
    return {
        "bytes": total_bytes,
        "kilobytes": total_bytes / 1024,
        "megabytes": total_bytes / (1024 ** 2),
        "gigabytes": total_bytes / (1024 ** 3),
        "mb_per_minute": (bytes_per_second * 60) / (1024 ** 2),
        "duration_seconds": duration_seconds,
        "sample_rate": sample_rate,
        "bit_depth": bit_depth,
        "channels": channels,
    }


def analyze_session_settings(
    sample_rate: int,
    bit_depth: int | str,
    track_count: int = 1,
    session_length_minutes: float = 4.0,
) -> dict[str, Any]:
    sample_rate = _normalize_sample_rate(sample_rate)
    bit_depth = _normalize_bit_depth(bit_depth)
    sr_info = SAMPLE_RATES.get(sample_rate)
    bd_info = BIT_DEPTHS.get(bit_depth)

    if sr_info is None:
        return {
            "error": f"Unknown sample rate: {sample_rate}",
            "valid_sample_rates": sorted(SAMPLE_RATES.keys()),
        }
    if bd_info is None:
        return {
            "error": f"Unknown bit depth: {bit_depth}",
            "valid_bit_depths": list(BIT_DEPTHS.keys()),
        }

    file_size = calculate_file_size(
        duration_seconds=session_length_minutes * 60,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
    )
    total_storage_gb_per_hour = (file_size["mb_per_minute"] * 60) / 1024 * track_count

    relative_cpu = sr_info["relative_cpu"]
    if relative_cpu < 1.5:
        cpu_load = "low"
    elif relative_cpu < 2.5:
        cpu_load = "medium"
    else:
        cpu_load = "high"

    return {
        "sample_rate": sample_rate,
        "bit_depth": bit_depth,
        "sample_rate_name": sr_info["name"],
        "bit_depth_name": bd_info["name"],
        "nyquist_frequency": sr_info["nyquist_frequency"],
        "dynamic_range_db": bd_info["dynamic_range_db"],
        "is_ableton_default": sr_info["ableton_default"] and bd_info["ableton_default"],
        "relative_cpu_load": sr_info["relative_cpu"],
        "cpu_load_description": cpu_load,
        "estimated_storage_gb_per_hour_per_track": round(total_storage_gb_per_hour, 3),
        "track_count": track_count,
        "session_length_minutes": session_length_minutes,
        "ableton_notes": {
            "sample_rate": sr_info["ableton_notes"],
            "bit_depth": bd_info["ableton_notes"],
        },
    }


def get_use_case_recommendation(use_case: str) -> dict[str, Any]:
    use_case = _normalize_use_case(use_case)
    rec = USE_CASE_RECOMMENDATIONS.get(use_case)
    if rec is None:
        return {
            "error": f"Unknown use case: {use_case}",
            "valid_use_cases": list(USE_CASE_RECOMMENDATIONS.keys()),
        }
    return {"use_case": use_case, **rec}
