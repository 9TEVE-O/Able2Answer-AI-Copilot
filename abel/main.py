"""Abel CLI — ask the Ableton Live audio quality copilot a question."""
import sys


def main() -> None:
    from abel.config import load_config

    config = load_config()
    args = sys.argv[1:]

    if "--setup-profile" in args:
        _run_setup_profile(config)
        return

    if "--update-profile" in args:
        print("Updating Abel music profile...")
        _run_setup_profile(config)
        return

    if not args or "--help" in args or "-h" in args:
        print(f"Abel: Offline AI Copilot for Ableton Live  [mode: {config.mode}]\n")
        print("Usage: abel <question>\n")
        print("Commands:")
        print("  --help, -h         Show this message")
        print("  --setup-profile    Connect music sources and build taste profile")
        print("  --update-profile   Re-sync all sources and refresh profile\n")
        print("Environment variables:")
        print("  ABEL_MODE=online|offline            (default: online)")
        print("  ABEL_LOCAL_MODEL=<model>            (default: llama3.1, offline only)")
        print("  ABEL_DATA_DIR=<path>                (default: ~/.abel)")
        print("  SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET")
        print("  ITUNES_LIBRARY_PATH                 (auto-detected on macOS)")
        print("  ABEL_MUSIC_DIRS=<path1:path2>       (colon-separated music dirs)\n")
        print("Examples:")
        print('  abel "What sample rate should I use for music production?"')
        print('  abel "Analyse my session at ~/Music/Ableton/MySong.als"')
        print('  ABEL_MODE=offline abel "How does sidechain compression work?"')
        print("\n(`python -m abel.main ...` works too if the package is not installed.)")
        sys.exit(0)

    from abel.audio_quality_agent import ask_abel_streaming

    question = " ".join(args)
    label = "offline" if config.mode == "offline" else "online"
    print(f"\nAbel ({label}): ", end="", flush=True)
    ask_abel_streaming(question, config)


def _run_setup_profile(config) -> None:
    """Build the music taste profile from all configured sources."""
    from abel.music_profile.profile_builder import build_profile
    from abel.music_profile.profile_store import save_profile

    print("\nAbel Music Profile Setup")
    print("=" * 30)
    all_tracks = []

    if config.spotify_client_id and config.spotify_client_secret:
        print("\nSpotify: connecting (browser will open for auth)...")
        try:
            from abel.music_profile.spotify_client import fetch_spotify_tracks
            tracks = fetch_spotify_tracks(
                config.spotify_client_id,
                config.spotify_client_secret,
                config.db_path.parent / "spotify_token.json",
            )
            all_tracks.append(tracks)
            print(f"  OK  {len(tracks)} tracks")
        except Exception as e:
            print(f"  FAIL  {e}")
    else:
        print("\nSpotify: skipped  (set SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET)")

    if config.itunes_library_path:
        print(f"\niTunes: reading {config.itunes_library_path} ...")
        try:
            from abel.music_profile.itunes_parser import parse_itunes_library
            tracks = parse_itunes_library(config.itunes_library_path)
            all_tracks.append(tracks)
            print(f"  OK  {len(tracks)} tracks")
        except Exception as e:
            print(f"  FAIL  {e}")
    else:
        print("\niTunes: skipped  (no library XML found; set ITUNES_LIBRARY_PATH to override)")

    if config.music_dirs:
        dirs = list(config.music_dirs)
        suffix = "y" if len(dirs) == 1 else "ies"
        print(f"\nLocal files: scanning {len(dirs)} director{suffix} ...")
        try:
            from abel.music_profile.local_scanner import scan_directories
            tracks = scan_directories(dirs)
            all_tracks.append(tracks)
            print(f"  OK  {len(tracks)} tracks")
        except Exception as e:
            print(f"  FAIL  {e}")
    else:
        print("\nLocal files: skipped  (set ABEL_MUSIC_DIRS=<path1:path2>)")

    if not any(all_tracks):
        print("\nNo sources produced data. Configure at least one source and re-run --setup-profile.")
        return

    profile = build_profile(all_tracks)
    profile_path = config.db_path.parent / "taste_profile.json"
    save_profile(profile.to_dict(), profile_path)

    print(f"\nProfile saved  →  {profile_path}")
    print(f"  Genres : {', '.join(profile.genres[:5]) or 'none'}")
    print(f"  BPM    : {profile.bpm_range or 'n/a'}")
    print(f"  Style  : {profile.production_style or 'n/a'}")
    print(f"  Energy : {profile.energy}")
    print(f"  Tracks : {profile.track_count_analysed}")


if __name__ == "__main__":
    main()
