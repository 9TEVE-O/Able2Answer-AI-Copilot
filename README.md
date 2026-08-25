# Able2Answer AI Copilot

Able2Answer AI Copilot is a production assistant for [Ableton Live](https://www.ableton.com/). It answers audio-quality
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

Every optional dependency is imported lazily, so Able2Answer AI Copilot starts and runs without any of them installed.

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

So that Able2Answer AI Copilot's advice fits the music you actually make:

```bash
pip install -e ".[music-profile]"

export SPOTIFY_CLIENT_ID=...        # from developer.spotify.com
export SPOTIFY_CLIENT_SECRET=...
export ABEL_MUSIC_DIRS="$HOME/Music:/Volumes/Samples"

abel --setup-profile     # connect sources and build the profile
abel --update-profile    # re-sync later
```

It aggregates genres (weighted by play count), a BPM range, energy and mood, and your top artists,
then classifies a production style. That summary is injected into Able2Answer AI Copilot's system prompt.

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
├── live/                    # the Live Set currently open: typed snapshot + bridge boundary
├── evidence/                # observation vs. knowledge, and the guard between them
└── music_profile/           # Spotify / iTunes / local file taste profiling
ableton/live-bridge/         # Max for Live device that reads the open Live Set
tests/                       # 167 tests
```

---

## Reading the session that is open right now

`.als` parsing answers *what is in the project I saved*. That is not the same
question as *what is Live doing right now*, and a producer mid-session is
usually asking the second one.

The `abel/live/` package covers the second. A small **Max for Live bridge**
reads the open Live Set through the Live Object Model and posts a structured
snapshot to Able2Answer AI Copilot, which parses it into a typed `SessionSnapshot`.

The rules that layer follows are worth stating plainly, because they are the
product:

- **Read only.** The bridge calls no setter. It cannot change your session.
- **Never guess a reading.** A property Live does not report stays `None` and
  is shown as "not reported by Live". An assumed sample rate presented as an
  observation is the exact failure this project exists to avoid.
- **Never answer from a stale session.** An observation older than 30 seconds
  is withheld, because you have probably changed something since.
- **Observation and knowledge stay separate.** `abel/evidence/` keeps what was
  *measured in your session* permanently distinguishable from what Able2Answer AI Copilot *knows
  about audio in general* — right through to the UI, which labels them apart.
- **Quantities get checked.** Before an answer reaches you, every number in it
  is checked against the evidence the model was given. Unsupported figures are
  flagged rather than shown as fact.

The bridge itself is deliberately tiny — no analysis, no thresholds, no advice.
All of that lives in Python, where it is tested.

## Development

```bash
pip install -e ".[all]"
pytest -q
```

## Status

Alpha, and honest about it:

- The audio-quality tools, `.als` parsing, offline knowledge base, taste-profile aggregation, and the Live Bridge boundary are covered by 167 tests.
- **Spotify OAuth has not been tested against the live API** — it has no automated coverage and rests on review rather than execution. Treat it as unproven until you have run `--setup-profile` [...]
- **The Max for Live bridge has not been run inside Ableton Live.** The Python side of that boundary is tested against the exact payload shape it documents, so the contract is covered — but the[...]

## License

MIT — see [LICENSE](LICENSE).
