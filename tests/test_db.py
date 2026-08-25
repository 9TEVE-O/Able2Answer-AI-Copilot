"""Tests for Abel's local knowledge database."""
import pytest

from abel.db.schema import create_tables, get_connection, is_seeded
from abel.db.seed import seed_database
from abel.db.search import build_rag_context, search_concepts, search_devices, search_techniques


@pytest.fixture
def db(tmp_path):
    conn = get_connection(tmp_path / "test.db")
    create_tables(conn)
    seed_database(conn)
    return conn


class TestSchema:
    def test_tables_created(self, tmp_path):
        conn = get_connection(tmp_path / "schema.db")
        create_tables(conn)
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"devices", "concepts", "techniques"}.issubset(tables)

    def test_not_seeded_before_seed(self, tmp_path):
        conn = get_connection(tmp_path / "empty.db")
        create_tables(conn)
        assert is_seeded(conn) is False


class TestSeed:
    def test_devices_populated(self, db):
        assert db.execute("SELECT COUNT(*) FROM devices").fetchone()[0] >= 10

    def test_concepts_populated(self, db):
        assert db.execute("SELECT COUNT(*) FROM concepts").fetchone()[0] >= 10

    def test_techniques_populated(self, db):
        assert db.execute("SELECT COUNT(*) FROM techniques").fetchone()[0] >= 5

    def test_is_seeded_true_after_seed(self, db):
        assert is_seeded(db) is True

    def test_operator_present(self, db):
        row = db.execute("SELECT * FROM devices WHERE name = 'Operator'").fetchone()
        assert row is not None
        assert row["category"] == "instrument"

    def test_sample_rate_concept_present(self, db):
        row = db.execute("SELECT * FROM concepts WHERE term = 'Sample Rate'").fetchone()
        assert row is not None
        assert "44100" in row["definition"]

    def test_sidechain_technique_present(self, db):
        row = db.execute("SELECT * FROM techniques WHERE name LIKE '%Sidechain%'").fetchone()
        assert row is not None


class TestSearch:
    def test_search_devices_finds_operator(self, db):
        results = search_devices(db, "Operator FM")
        assert any(r["name"] == "Operator" for r in results)

    def test_search_devices_finds_simpler(self, db):
        results = search_devices(db, "sample simpler")
        assert any(r["name"] == "Simpler" for r in results)

    def test_search_concepts_finds_sidechain(self, db):
        results = search_concepts(db, "sidechain compression")
        assert len(results) > 0

    def test_search_techniques_finds_sidechain(self, db):
        results = search_techniques(db, "sidechain pumping")
        assert len(results) > 0

    def test_build_rag_context_nonempty(self, db):
        ctx = build_rag_context(db, "How do I use sidechain compression on bass?")
        assert isinstance(ctx, str)
        assert len(ctx) > 50

    def test_build_rag_context_returns_string_for_any_input(self, db):
        ctx = build_rag_context(db, "xyz1234 nonsense qqq")
        assert isinstance(ctx, str)
