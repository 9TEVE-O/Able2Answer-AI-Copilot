"""Abel audio quality agent — online (Claude API) and offline (Ollama + RAG) modes."""
import json
from typing import Any

from abel.als_parser import get_session_quality_report, parse_als
from abel.config import AbelConfig, load_config
from abel.session_analyzer import (
    analyze_session_settings,
    calculate_file_size,
    get_bit_depth_info,
    get_sample_rate_info,
    get_use_case_recommendation,
)

MODEL = "claude-opus-4-7"

_BASE_SYSTEM = """You are Abel, an expert offline AI copilot for Ableton Live. \
You specialize in audio quality settings — sample rate, bit depth, file size, and session optimization.

Your knowledge is Ableton-specific:
- Reference Ableton Live menus, preferences, and keyboard shortcuts (e.g., Preferences → Audio, \
File → Export Audio/Video with Cmd+Shift+R on Mac / Ctrl+Shift+R on Windows).
- Ableton Live processes audio internally at 32-bit float regardless of the project bit depth setting.
- The Ableton Live defaults are 44.1 kHz sample rate and 24-bit depth.
- Never suggest third-party DAW workflows; keep all advice specific to Ableton Live.
- You can read and analyse actual Ableton .als project files when the user provides a file path.

When answering questions:
1. Use the provided tools to fetch accurate data before explaining.
2. If the user mentions a .als file path, use parse_als_file or get_session_quality_report first.
3. When a user taste profile is available, tailor every recommendation to their genre/BPM context.
4. Explain the WHY behind recommendations, not just the numbers.
5. Be concise and practical — producers need actionable guidance.
6. Always ground your answer in Ableton Live's specific behavior."""

TOOLS = [
    {
        "name": "get_sample_rate_info",
        "description": "Get detailed information about a specific sample rate including Ableton-specific notes, CPU load, and use cases.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sample_rate": {"type": "integer", "description": "Sample rate in Hz (e.g. 44100, 48000, 96000)"}
            },
            "required": ["sample_rate"],
        },
    },
    {
        "name": "get_bit_depth_info",
        "description": "Get detailed information about a specific bit depth including dynamic range, Ableton behavior, and use cases.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bit_depth": {
                    "oneOf": [
                        {"type": "integer", "description": "Integer bit depth (16 or 24)"},
                        {"type": "string", "description": "Float bit depth ('32f' or '64f')"},
                    ],
                    "description": "Bit depth: 16, 24, '32f', or '64f'",
                }
            },
            "required": ["bit_depth"],
        },
    },
    {
        "name": "analyze_session_settings",
        "description": "Analyze Ableton session settings and return quality metrics, CPU load, and storage estimates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sample_rate": {"type": "integer", "description": "Sample rate in Hz"},
                "bit_depth": {
                    "oneOf": [{"type": "integer"}, {"type": "string"}],
                    "description": "Bit depth: 16, 24, '32f', or '64f'",
                },
                "track_count": {"type": "integer", "description": "Number of audio tracks (default 1)", "default": 1},
                "session_length_minutes": {"type": "number", "description": "Session length in minutes (default 4.0)", "default": 4.0},
            },
            "required": ["sample_rate", "bit_depth"],
        },
    },
    {
        "name": "calculate_file_size",
        "description": "Calculate the exact file size for an audio file given duration, sample rate, bit depth, and channel count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "duration_seconds": {"type": "number", "description": "Duration in seconds"},
                "sample_rate": {"type": "integer", "description": "Sample rate in Hz"},
                "bit_depth": {
                    "oneOf": [{"type": "integer"}, {"type": "string"}],
                    "description": "Bit depth: 16, 24, '32f', or '64f'",
                },
                "channels": {"type": "integer", "description": "Number of channels (default 2)", "default": 2},
            },
            "required": ["duration_seconds", "sample_rate", "bit_depth"],
        },
    },
    {
        "name": "get_use_case_recommendation",
        "description": "Get the recommended Ableton Live sample rate and bit depth for a specific production use case.",
        "input_schema": {
            "type": "object",
            "properties": {
                "use_case": {
                    "type": "string",
                    "description": "Use case: 'music_production', 'video_scoring', 'stems_export', 'live_performance', 'podcast', or 'archival'",
                }
            },
            "required": ["use_case"],
        },
    },
    {
        "name": "parse_als_file",
        "description": "Parse an Ableton Live Set (.als) file from disk and extract session metadata: tracks, tempo, time signature, clip counts, audio clip native sample rates, and loaded devices/plugins.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute or relative path to the .als file"}},
            "required": ["path"],
        },
    },
    {
        "name": "get_session_quality_report",
        "description": "Parse an Ableton .als file and return a quality-focused report: detects sample rate mismatches, high track counts, and issues with Ableton-specific fixes.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute or relative path to the .als file"}},
            "required": ["path"],
        },
    },
    {
        "name": "get_user_taste_profile",
        "description": "Return the user's music taste profile — genres, BPM range, energy level, valence, top artists, and production style — built from their Spotify, iTunes, and/or local music libraries.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

_TOOL_DISPATCH: dict[str, Any] = {
    "get_sample_rate_info": get_sample_rate_info,
    "get_bit_depth_info": get_bit_depth_info,
    "analyze_session_settings": analyze_session_settings,
    "calculate_file_size": calculate_file_size,
    "get_use_case_recommendation": get_use_case_recommendation,
    "parse_als_file": parse_als,
    "get_session_quality_report": get_session_quality_report,
}


def _build_system(config: AbelConfig) -> str:
    from abel.music_profile import build_taste_summary, get_or_build_profile

    system = _BASE_SYSTEM
    profile = get_or_build_profile(config)
    if profile:
        system += f"\n\n## User Music Profile\n{build_taste_summary(profile)}"
    return system


def run_tool(name: str, tool_input: dict[str, Any], config: AbelConfig) -> str:
    if name == "get_user_taste_profile":
        from abel.music_profile import get_or_build_profile
        result = get_or_build_profile(config) or {
            "error": "No taste profile found. Run: python -m abel.main --setup-profile"
        }
        return json.dumps(result, indent=2)
    fn = _TOOL_DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return json.dumps(fn(**tool_input), indent=2)


def ask_abel_streaming(question: str, config: AbelConfig | None = None) -> None:
    if config is None:
        config = load_config()
    if config.mode == "offline":
        _ask_offline(question, config)
    else:
        _ask_online(question, config)


def _ask_online(question: str, config: AbelConfig) -> None:
    """Claude API streaming with tool use loop."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.api_key)
    system = _build_system(config)
    messages: list[dict] = [{"role": "user", "content": question}]

    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=system,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    print(event.delta.text, end="", flush=True)
            response = stream.get_final_message()

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason == "end_turn" or not tool_uses:
            print()
            return

        messages.append({"role": "assistant", "content": response.content})
        tool_results = [
            {"type": "tool_result", "tool_use_id": tu.id, "content": run_tool(tu.name, tu.input, config)}
            for tu in tool_uses
        ]
        messages.append({"role": "user", "content": tool_results})


def _ask_offline(question: str, config: AbelConfig) -> None:
    """Ollama streaming with RAG context injected from local knowledge DB."""
    try:
        import ollama
    except ImportError:
        print(
            "\n[Offline mode requires Ollama]\n"
            "  pip install ollama\n"
            "  ollama serve\n"
            "  ollama pull llama3.1\n"
        )
        return

    from abel.db import get_knowledge_db
    from abel.db.search import build_rag_context

    conn = get_knowledge_db(config.db_path)
    rag = build_rag_context(conn, question)
    system = _build_system(config)
    if rag:
        system += f"\n\n## Local Knowledge Base\n{rag}"

    try:
        stream = ollama.chat(
            model=config.local_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
            stream=True,
        )
        for chunk in stream:
            print(chunk["message"]["content"], end="", flush=True)
        print()
    except Exception as e:
        print(f"\n[Abel offline error: {e}]\nIs Ollama running? Try: ollama serve")
