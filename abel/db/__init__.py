"""Abel local knowledge database — SQLite-backed Ableton Live knowledge base."""
from pathlib import Path

from abel.db.schema import create_tables, get_connection, is_seeded
from abel.db.seed import seed_database


def get_knowledge_db(db_path: Path):
    """Return an open, seeded SQLite connection. Creates and seeds on first run."""
    conn = get_connection(db_path)
    create_tables(conn)
    if not is_seeded(conn):
        seed_database(conn)
    return conn
