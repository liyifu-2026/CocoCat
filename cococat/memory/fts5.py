"""Memory FTS5 indexer — indexes pinned.md + compiled/ for recall with BM25 ranking."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("cococat.memory.fts5")


def index_memory(agent_dir: str, db) -> int:
    """Index all memory files for a given agent_dir into memory_fts.

    Clears old entries for this agent_dir, then re-indexes pinned.md + compiled/*.md.
    Returns count of indexed documents.
    """
    memory_dir = os.path.join(agent_dir, "memory")
    count = 0

    # Clear old entries
    try:
        db.execute("DELETE FROM memory_fts WHERE agent_dir = ?", (agent_dir,))
    except Exception:
        pass

    # Index pinned.md
    pinned_path = os.path.join(agent_dir, "pinned.md")
    if os.path.exists(pinned_path):
        try:
            with open(pinned_path, encoding="utf-8") as f:
                content = f.read(5000)
            if content.strip():
                db.execute(
                    "INSERT INTO memory_fts (source, content, agent_dir) VALUES (?, ?, ?)",
                    ("pinned", content, agent_dir),
                )
                count += 1
        except OSError:
            pass

    # Index compiled/ directory
    compiled_dir = os.path.join(memory_dir, "compiled")
    if os.path.isdir(compiled_dir):
        for fname in sorted(os.listdir(compiled_dir)):
            if fname.startswith(".") or not fname.endswith(".md"):
                continue
            fpath = os.path.join(compiled_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read(5000)
                if content.strip():
                    source = f"compiled:{fname}"
                    db.execute(
                        "INSERT INTO memory_fts (source, content, agent_dir) VALUES (?, ?, ?)",
                        (source, content, agent_dir),
                    )
                    count += 1
            except OSError:
                pass

    # Index whiteboard
    whiteboard_path = os.path.join(memory_dir, "memory.md")
    if os.path.exists(whiteboard_path):
        try:
            with open(whiteboard_path, encoding="utf-8") as f:
                content = f.read(5000)
            if content.strip():
                db.execute(
                    "INSERT INTO memory_fts (source, content, agent_dir) VALUES (?, ?, ?)",
                    ("whiteboard", content, agent_dir),
                )
                count += 1
        except OSError:
            pass

    logger.info("Indexed %d memory documents for %s", count, agent_dir)
    return count


def search_fts(query: str, agent_dir: str, db, limit: int = 10) -> list[dict]:
    """Search memory_fts with FTS5 BM25 ranking. Returns [{source, snippet, rank}, ...]."""
    try:
        rows = db.execute(
            """SELECT source, snippet(memory_fts, 1, '<b>', '</b>', '...', 40) as snippet, rank
               FROM memory_fts
               WHERE memory_fts MATCH ? AND agent_dir = ?
               ORDER BY rank
               LIMIT ?""",
            (query, agent_dir, limit),
        )
        return [{"source": r[0], "snippet": r[1], "rank": r[2]} for r in rows]
    except Exception:
        return []
