"""Tests for Abel session analyzer and knowledge base."""
import pytest

from abel.knowledge_base import BIT_DEPTHS, SAMPLE_RATES, USE_CASE_RECOMMENDATIONS
from abel.session_analyzer import (
    analyze_session_settings,
    calculate_file_size,
    get_bit_depth_info,
    get_sample_rate_info,
    get_use_case_recommendation,
)


class TestKnowledgeBase:
    def test_sample_rates_have_required_keys(self):
        for rate, info in SAMPLE_RATES.items():
            assert "name" in info, f"{rate}: missing 'name'"
            assert "nyquist_frequency" in info, f"{rate}: missing 'nyquist_frequency'"
            assert "relative_cpu" in info, f"{rate}: missing 'relative_cpu'"
            assert "ableton_notes" in info, f"{rate}: missing 'ableton_notes'"

    def test_nyquist_is_half_sample_rate(self):
        for rate, info in SAMPLE_RATES.items():
            assert info["nyquist_frequency"] == rate // 2

    def test_bit_depths_have_dynamic_range(self):
        for depth, info in BIT_DEPTHS.items():
            assert "dynamic_range_db" in info, f"{depth}: missing 'dynamic_range_db'"


class TestSampleRateInfo:
    def test_known_rate_returns_data(self):
        result = get_sample_rate_info(44100)
        assert result["sample_rate"] == 44100
        assert "name" in result
        assert "ableton_notes" in result

    def test_unknown_rate_returns_error(self):
        result = get_sample_rate_info(12345)
        assert "error" in result
        assert "valid_sample_rates" in result


class TestBitDepthInfo:
    def test_24bit_is_ableton_default(self):
        result = get_bit_depth_info(24)
        assert result["ableton_default"] is True

    def test_16bit_lower_dynamic_range_than_24bit(self):
        r16 = get_bit_depth_info(16)
        r24 = get_bit_depth_info(24)
        assert r16["dynamic_range_db"] < r24["dynamic_range_db"]

    def test_32f_is_float(self):
        result = get_bit_depth_info("32f")
        assert result["is_float"] is True

    def test_unknown_bit_depth_returns_error(self):
        result = get_bit_depth_info(8)
        assert "error" in result
        assert "valid_bit_depths" in result


class TestFileSizeCalculation:
    def test_stereo_44100_24bit_approx_15mb_per_minute(self):
        result = calculate_file_size(60, 44100, 24, channels=2)
        assert abs(result["mb_per_minute"] - 15.09) < 0.1

    def test_higher_sample_rate_larger_file(self):
        r44 = calculate_file_size(60, 44100, 24)
        r96 = calculate_file_size(60, 96000, 24)
        assert r96["megabytes"] > r44["megabytes"]

    def test_unknown_bit_depth_returns_error(self):
        result = calculate_file_size(60, 44100, 8)
        assert "error" in result


class TestSessionAnalysis:
    def test_default_settings_parse_correctly(self):
        result = analyze_session_settings(44100, 24)
        assert result["sample_rate"] == 44100
        assert result["bit_depth"] == 24
        assert result["is_ableton_default"] is True
        assert "cpu_load_description" in result
        assert "estimated_storage_gb_per_hour_per_track" in result

    def test_unknown_settings_return_error(self):
        result = analyze_session_settings(12345, 24)
        assert "error" in result

    def test_96khz_higher_cpu_than_44100(self):
        r44 = analyze_session_settings(44100, 24)
        r96 = analyze_session_settings(96000, 24)
        assert r96["relative_cpu_load"] > r44["relative_cpu_load"]


class TestUseCaseRecommendations:
    def test_music_production_recommends_44100(self):
        result = get_use_case_recommendation("music_production")
        assert result["sample_rate"] == 44100

    def test_video_scoring_recommends_48000(self):
        result = get_use_case_recommendation("video_scoring")
        assert result["sample_rate"] == 48000

    def test_stems_export_recommends_32f(self):
        result = get_use_case_recommendation("stems_export")
        assert result["bit_depth"] == "32f"

    def test_unknown_use_case_returns_error(self):
        result = get_use_case_recommendation("djing")
        assert "error" in result
        assert "valid_use_cases" in result


class TestToolArgumentNormalization:
    """Model-supplied tool args arrive as ints or strings; both must resolve.

    Regression: get_bit_depth_info("24") used to return an error whose own
    valid_bit_depths list contained 24, which reads as self-contradictory to
    the model and invites it to retry the identical call.
    """

    @pytest.mark.parametrize("value", [16, "16", " 16 ", "16bit", "16-bit"])
    def test_sixteen_bit_variants_resolve(self, value):
        assert get_bit_depth_info(value)["bit_depth"] == 16

    @pytest.mark.parametrize("value", [24, "24", "24bit", "24-bit"])
    def test_twenty_four_bit_variants_resolve(self, value):
        assert get_bit_depth_info(value)["bit_depth"] == 24

    @pytest.mark.parametrize("value", [32, "32", "32f", "32F", "32-bit float"])
    def test_thirty_two_bit_maps_to_float_key(self, value):
        assert get_bit_depth_info(value)["bit_depth"] == "32f"

    @pytest.mark.parametrize("value", [64, "64", "64f", "64-bit float"])
    def test_sixty_four_bit_maps_to_float_key(self, value):
        assert get_bit_depth_info(value)["bit_depth"] == "64f"

    @pytest.mark.parametrize("value", [8, "gibberish", None, True])
    def test_genuinely_invalid_bit_depth_still_errors(self, value):
        assert "error" in get_bit_depth_info(value)

    @pytest.mark.parametrize(
        "value", [44100, "44100", 44100.0, "44.1kHz", "44.1 kHz", "44,100"]
    )
    def test_sample_rate_variants_resolve(self, value):
        assert get_sample_rate_info(value)["sample_rate"] == 44100

    @pytest.mark.parametrize("value", [48000, "48000", "48kHz", "48k"])
    def test_forty_eight_k_variants_resolve(self, value):
        assert get_sample_rate_info(value)["sample_rate"] == 48000

    @pytest.mark.parametrize("value", ["abc", 9999, None])
    def test_genuinely_invalid_sample_rate_still_errors(self, value):
        assert "error" in get_sample_rate_info(value)

    @pytest.mark.parametrize(
        "value",
        ["music_production", "Music Production", "MUSIC_PRODUCTION", "music-production"],
    )
    def test_use_case_variants_resolve(self, value):
        assert get_use_case_recommendation(value)["use_case"] == "music_production"

    def test_genuinely_invalid_use_case_still_errors(self):
        assert "error" in get_use_case_recommendation("polka_mastering")

    def test_normalized_input_matches_canonical_output(self):
        assert analyze_session_settings("48kHz", "24") == analyze_session_settings(48000, 24)

    def test_file_size_accepts_normalized_input(self):
        loose = calculate_file_size(60, "44.1kHz", "32-bit float")
        canonical = calculate_file_size(60, 44100, "32f")
        assert loose == canonical
        assert "error" not in loose

    def test_error_message_never_lists_the_rejected_value_as_valid(self):
        """A rejected value must not appear in the tool's own valid list."""
        for bad in [8, 12, "gibberish"]:
            result = get_bit_depth_info(bad)
            assert "error" in result
            normalized = result["error"].split(": ", 1)[1]
            assert normalized not in [str(k) for k in result["valid_bit_depths"]]
