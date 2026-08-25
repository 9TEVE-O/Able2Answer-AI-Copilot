"""SQLite schema for Abel's local Ableton Live knowledge base."""
import sqlite3
from pathlib import Path


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            category    TEXT NOT NULL,
            subcategory TEXT,
            description TEXT,
            key_params  TEXT,
            use_cases   TEXT,
            tips        TEXT
        );

        CREATE TABLE IF NOT EXISTS concepts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            term         TEXT NOT NULL UNIQUE,
            category     TEXT,
            definition   TEXT NOT NULL,
            ableton_path TEXT,
            shortcut     TEXT,
            related      TEXT
        );

        CREATE TABLE IF NOT EXISTS techniques (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            category    TEXT,
            description TEXT,
            steps       TEXT,
            shortcut    TEXT,
            tags        TEXT
        );

        CREATE TABLE IF NOT EXISTS music_sources (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT NOT NULL UNIQUE,
            last_sync   TEXT,
            track_count INTEGER DEFAULT 0,
            status      TEXT DEFAULT 'pending'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS devices_fts USING fts5(
            name, description, use_cases, tips,
            device_id UNINDEXED
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS concepts_fts USING fts5(
            term, definition, ableton_path,
            concept_id UNINDEXED
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS techniques_fts USING fts5(
            name, description, steps, tags,
            technique_id UNINDEXED
        );
    """)
    conn.commit()


def is_seeded(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0] > 0
