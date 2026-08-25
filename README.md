# Able2Answer — Abel, an AI Copilot for Ableton Live

Abel is a production assistant for [Ableton Live](https://www.ableton.com/). It answers audio-quality
questions, reads your actual `.als` project files, and tailors its advice to the music you really listen to.

It is built to be **useful without the internet** and **private by default**.

- **Ableton-specific.** Advice is grounded in Live's own devices, menu paths and behaviour — not generic DAW theory.
- **Reads your sessions.** Point it at a `.als` file and it reports tempo, tracks, devices, clip sample rates and quality issues.
- **Runs offline.** With `ABEL_MODE=offline` it answers entirely from a local Ollama model plus a bundled SQLite knowledge base. No API call.
- **Knows your taste.** It can build a profile from Spotify, iTunes/Apple Music and local audio files, so a techno producer gets techno-relevant answers.

---

## Install

Requires Python 3.11+.

```bash
git clone https://github.com/9TEVE-O/Able2Answer-AI-Copilot
cd Able2Answer-AI-Copilot
pip install -e .
```

Optional extras, added only if you want them:

```bash
pip install -e ".[music-profile]"   # Spotify + iTunes + local file taste profile
pip install -e ".[offline]"         # local inference via Ollama
pip install -e ".[all]"             # everything, including dev/test tools
```

Every optional dependency is imported lazily, so Abel starts and runs without any of them installed.

---

## Quickstart

```bash
export ANTHROPIC_API_KEY=sk-ant-...

abel "What sample rate should I use for music production?"
abel "Analyse my session at ~/Music/Ableton/MySong.als"
abel --help
```

### Offline mode

No API key, no network:

```bash
pip install -e ".[offline]"
ollama serve
ollama pull llama3.1

ABEL_MODE=offline abel "How does sidechain compression work in Live?"
```

Offline answers are grounded by retrieval over a local SQLite knowledge base (25 Ableton devices,
17 concepts, 7 techniques), which is created and seeded automatically on first run.

---

## Music taste profile

So that Abel's advice fits the music you actually make:

```bash
pip install -e ".[music-profile]"

export SPOTIFY_CLIENT_ID=...        # from developer.spotify.com
export SPOTIFY_CLIENT_SECRET=...
export ABEL_MUSIC_DIRS="$HOME/Music:/Volumes/Samples"

abel --setup-profile     # connect sources and build the profile
abel --update-profile    # re-sync later
```

It aggregates genres (weighted by play count), a BPM range, energy and mood, and your top artists,
then classifies a production style. That summary is injected into Abel's system prompt.

### Privacy

This is the part worth being precise about:

- Your listening data is aggregated **on your machine** and stored at `~/.abel/taste_profile.json`, written with `0o600` (owner-only) permissions.
- Raw track data — individual songs, play counts, artists — **never leaves your machine**.
- In online mode, only a short summary paragraph is sent, e.g. *"User primarily listens to techno and deep house (120–145 BPM), high energy, dark mood."*
- In offline mode, nothing leaves your machine at all.
- Your `.als` session files are parsed locally and are never uploaded.

Delete `~/.abel/taste_profile.json` at any time to remove the profile.

---

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for online mode |
| `ABEL_MODE` | `online` | `online` (Claude) or `offline` (Ollama) |
| `ABEL_LOCAL_MODEL` | `llama3.1` | Ollama model, offline mode only |
| `ABEL_DATA_DIR` | `~/.abel` | Where the knowledge DB and profile live |
| `SPOTIFY_CLIENT_ID` | — | Spotify OAuth app ID |
| `SPOTIFY_CLIENT_SECRET` | — | Spotify OAuth app secret |
| `ITUNES_LIBRARY_PATH` | auto-detected on macOS | iTunes/Music library XML |
| `ABEL_MUSIC_DIRS` | — | Colon-separated dirs to scan for audio files |

---

## Project layout

```
abel/
├── audio_quality_agent.py   # the agent loop + tool definitions (online & offline)
├── session_analyzer.py      # sample rate / bit depth / file size tools
├── knowledge_base.py        # sample rates, bit depths, use-case recommendations
├── als_parser.py            # reads gzip+XML Ableton .als project files
├── config.py                # environment-driven configuration
├── main.py                  # CLI entry point
├── db/                      # SQLite knowledge base + FTS5 search + RAG context
└── music_profile/           # Spotify / iTunes / local file taste profiling
tests/                       # 113 tests
```

## Development

```bash
pip install -e ".[all]"
pytest -q
```

## Status

Alpha, and honest about it:

- The audio-quality tools, `.als` parsing, offline knowledge base, and taste-profile aggregation are covered by 113 tests.
- **Spotify OAuth has not been tested against the live API** — it has no automated coverage and rests on review rather than execution. Treat it as unproven until you have run `--setup-profile` with real credentials.

## License

MIT — see [LICENSE](LICENSE).
