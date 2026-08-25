"""Abel runtime configuration — read from environment variables."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AbelConfig:
    mode: str                      # "online" | "offline"
    local_model: str               # ollama model name for offline mode
    api_key: str | None
    db_path: Path
    spotify_client_id: str | None
    spotify_client_secret: str | None
    itunes_library_path: Path | None
    music_dirs: tuple[Path, ...]   # tuple keeps the frozen dataclass hashable


def load_config() -> AbelConfig:
    mode = os.getenv("ABEL_MODE", "online").lower()
    if mode not in ("online", "offline"):
        mode = "online"
    data_dir = Path(os.getenv("ABEL_DATA_DIR", str(Path.home() / ".abel")))

    # iTunes auto-detection
    itunes_override = os.getenv("ITUNES_LIBRARY_PATH")
    itunes_path: Path | None = None
    if itunes_override:
        itunes_path = Path(itunes_override)
    else:
        for candidate in (
            Path.home() / "Music" / "iTunes" / "iTunes Music Library.xml",
            Path.home() / "Music" / "iTunes" / "iTunes Library.xml",
            Path.home() / "Music" / "Music" / "Music Library.xml",
        ):
            if candidate.exists():
                itunes_path = candidate
                break

    # Music dirs from colon-separated env var
    music_dirs_raw = os.getenv("ABEL_MUSIC_DIRS", "")
    music_dirs = tuple(Path(p) for p in music_dirs_raw.split(":") if p.strip())

    return AbelConfig(
        mode=mode,
        local_model=os.getenv("ABEL_LOCAL_MODEL", "llama3.1"),
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        db_path=data_dir / "knowledge.db",
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        itunes_library_path=itunes_path,
        music_dirs=music_dirs,
    )
