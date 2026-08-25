"""Full-text search and RAG interface for the Abel knowledge database."""
import json
import sqlite3
from typing import Any


def search_devices(
    conn: sqlite3.Connection,
    query: str,
    category: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            "SELECT device_id FROM devices_fts WHERE devices_fts MATCH ? ORDER BY rank LIMIT ?",
            (_safe_query(query), limit),
        ).fetchall()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        ph = ",".join("?" * len(ids))
        results = [
            dict(r)
            for r in conn.execute(f"SELECT * FROM devices WHERE id IN ({ph})", ids)
        ]
        if category:
            results = [r for r in results if r["category"] == category]
        return results
    except Exception:
        results = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM devices WHERE name LIKE ? OR description LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            )
        ]
        return results


def search_concepts(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            "SELECT concept_id FROM concepts_fts WHERE concepts_fts MATCH ? ORDER BY rank LIMIT ?",
            (_safe_query(query), limit),
        ).fetchall()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        ph = ",".join("?" * len(ids))
        return [dict(r) for r in conn.execute(f"SELECT * FROM concepts WHERE id IN ({ph})", ids)]
    except Exception:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM concepts WHERE term LIKE ? OR definition LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            )
        ]


def search_techniques(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            "SELECT technique_id FROM techniques_fts WHERE techniques_fts MATCH ? ORDER BY rank LIMIT ?",
            (_safe_query(query), limit),
        ).fetchall()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        ph = ",".join("?" * len(ids))
        return [dict(r) for r in conn.execute(f"SELECT * FROM techniques WHERE id IN ({ph})", ids)]
    except Exception:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM techniques WHERE name LIKE ? OR description LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            )
        ]


def build_rag_context(conn: sqlite3.Connection, question: str) -> str:
    """Return relevant knowledge formatted for injection into the offline system prompt."""
    keywords = _keywords(question)
    if not keywords:
        return ""

    query = " OR ".join(keywords[:6])  # cap at 6 terms
    devices = search_devices(conn, query, limit=3)
    concepts = search_concepts(conn, query, limit=3)
    techniques = search_techniques(conn, query, limit=2)

    parts: list[str] = []

    if devices:
        parts.append("### Relevant Devices")
        for d in devices:
            parts.append(f"**{d['name']}** ({d['category']}): {d['description']}")
            if d.get("tips"):
                tip = json.loads(d["tips"])
                if tip:
                    parts.append(f"Tip: {tip[0]}")

    if concepts:
        parts.append("### Relevant Concepts")
        for c in concepts:
            line = f"**{c['term']}**: {c['definition']}"
            if c.get("ableton_path"):
                line += f"  ·  Path: {c['ableton_path']}"
            if c.get("shortcut"):
                line += f"  ·  Shortcut: {c['shortcut']}"
            parts.append(line)

    if techniques:
        parts.append("### Relevant Techniques")
        for t in techniques:
            parts.append(f"**{t['name']}**: {t['description']}")

    return "\n".join(parts)


def _safe_query(raw: str) -> str:
    return raw.replace('"', "").replace("'", "").strip()


def _keywords(question: str) -> list[str]:
    stop = {
        "a", "an", "the", "is", "are", "was", "what", "how", "why", "do", "does",
        "i", "my", "me", "can", "should", "would", "will", "when", "where",
        "to", "in", "on", "at", "for", "of", "and", "or", "with", "use",
        "that", "this", "it", "be", "have", "has", "about",
    }
    words = question.lower().split()
    return [w.strip("?.,!:;") for w in words if len(w.strip("?.,!:;")) > 3 and w.strip("?.,!:;") not in stop]
