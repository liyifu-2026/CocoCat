"""Manual memory — remember / recall / forget."""
from __future__ import annotations

import os
from typing import Any


class ManualMemory:
    """Manual memory: remember, recall, forget.

    Dependencies are explicit in __init__ — no hidden superclass state.
    """

    def __init__(self, memory_dir: str = "memory", db: Any = None):
        self._memory_dir = memory_dir
        self._db = db

    def remember(self, text: str, category: str | None = None, exp_path: str = "") -> str:
        """Append a fact to memory.md (whiteboard)."""
        return self._pin(text)

    def recall(self, query: str) -> str:
        """Search all memory layers. Uses FTS5 when available, file grep as fallback."""
        q = query.lower()
        results = []

        # Try FTS5 first (ranked, fast)
        if self._db:
            try:
                from cococat.memory.fts5 import search_fts, index_memory
                agent_dir = os.path.dirname(self._memory_dir)
                row = self._db.execute(
                    "SELECT COUNT(*) FROM memory_fts WHERE agent_dir = ?", (agent_dir,)
                ).fetchone()
                if row and row[0] == 0:
                    index_memory(agent_dir, self._db)
                fts_results = search_fts(query, agent_dir, self._db)
                if fts_results:
                    for r in fts_results:
                        source = r['source']
                        label = source.rsplit(':', 1)[-1] if ':' in source else source
                        results.append((label, r['snippet'].replace("<b>","").replace("</b>","")))
                    return "\n---\n".join(f"[{src}] {text}" for src, text in results)
            except Exception:
                pass

        # Fallback: file grep (no DB available)
        # 1. Search memory.md
        mem_path = os.path.join(self._memory_dir, "memory.md")
        if os.path.exists(mem_path):
            with open(mem_path, encoding="utf-8") as f:
                for line in f:
                    if q in line.lower():
                        results.append(("whiteboard", line.strip()))

        # 2. Search pinned.md
        agent_dir = os.path.dirname(self._memory_dir)
        pinned_path = os.path.join(agent_dir, "pinned.md")
        if os.path.exists(pinned_path):
            with open(pinned_path, encoding="utf-8") as f:
                for line in f:
                    if q in line.lower():
                        results.append(("pinned", line.strip()))

        # 3. FTS5 unavailable — search compiled via grep
        compiled_dir = os.path.join(self._memory_dir, "compiled")
        if os.path.isdir(compiled_dir):
            for fname in sorted(os.listdir(compiled_dir), reverse=True):
                if fname.startswith(".") or not fname.endswith(".md"):
                    continue
                fpath = os.path.join(compiled_dir, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        content = f.read()
                    if q in content.lower():
                        results.append(("compiled:" + fname, content.strip()[:200]))
                except OSError:
                    pass

        if not results:
            return "No matches found"
        return "\n---\n".join(f"[{src}] {text}" for src, text in results)

    def forget(self, keyword: str) -> str:
        """Remove lines matching keyword from memory.md."""
        mem_path = os.path.join(self._memory_dir, "memory.md")
        if not os.path.exists(mem_path):
            return f"No facts matching '{keyword}' found"
        with open(mem_path, encoding="utf-8") as f:
            lines = f.readlines()
        kept = [l for l in lines if keyword.lower() not in l.lower()]
        if len(kept) == len(lines):
            return f"No facts matching '{keyword}' found"
        with open(mem_path, "w", encoding="utf-8") as f:
            f.writelines(kept)
        return f"Unpinned facts matching '{keyword}'"

    def load_for_system_prompt(self) -> str:
        """Return memory.md content for inclusion in system prompt."""
        path = os.path.join(self._memory_dir, "memory.md")
        if not os.path.exists(path):
            return ""
        try:
            with open(path, encoding="utf-8") as f:
                return f.read(3000)
        except OSError:
            return ""

    # ── Internal manual helpers ─────────────────────────────
    def _pin(self, fact: str) -> str:
        mem_path = os.path.join(self._memory_dir, "memory.md")
        os.makedirs(self._memory_dir, exist_ok=True)
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write(fact if fact.endswith("\n") else fact + "\n")
        return f"Pinned: {fact}"
