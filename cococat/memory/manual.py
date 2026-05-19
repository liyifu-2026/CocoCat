"""Manual memory operations — remember / recall / forget / experiences."""

from __future__ import annotations

import os
from typing import Any


class ManualMemory:
    """Manual memory operations: remember, recall, forget, experiences.

    Dependencies are explicit in __init__ — no hidden superclass state.
    """

    def __init__(self, memory_dir: str = "memory", db: Any = None):
        self._memory_dir = memory_dir
        self._db = db

    def remember(self, text: str, category: str | None = None, exp_path: str = "") -> str:
        """Add a fact or experience.

        category=None → append to memory.md (pin).
        Otherwise → write to {exp_path or memory_dir/experiences}/{category}/{slug}.md.
        """
        if category:
            return self._record_experience(category, text, exp_path)
        return self._pin(text)

    def recall(self, query: str) -> str:
        """Search memory.md + FTS5 + experiences/ for query. Returns formatted results."""
        q = query.lower()
        results = []

        # 1. Search memory.md
        mem_path = os.path.join(self._memory_dir, "memory.md")
        if os.path.exists(mem_path):
            with open(mem_path, encoding="utf-8") as f:
                for line in f:
                    if q in line.lower():
                        results.append(("memory", line.strip()))

        # 2. Search FTS5
        if self._db:
            try:
                rows = self._db.execute(
                    "SELECT fact FROM facts_fts WHERE facts_fts MATCH ?", (query,)
                )
                for row in rows:
                    results.append(("fts5", row[0].strip()))
            except Exception:
                pass

        # 3. Search experiences/ (under memory_dir)
        exp_path = os.path.join(self._memory_dir, "experiences")
        if os.path.isdir(exp_path):
            for root, _, files in os.walk(exp_path):
                for fname in files:
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(root, fname)
                    with open(fpath, encoding="utf-8") as f:
                        content = f.read()
                    if q in content.lower():
                        results.append(
                            (os.path.relpath(root, exp_path), content.strip()[:200])
                        )

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

    def _record_experience(self, category: str, entry: str, exp_path: str = "") -> str:
        root = exp_path or os.path.join(self._memory_dir, "experiences")
        cat_dir = os.path.join(root, category)
        os.makedirs(cat_dir, exist_ok=True)
        slug = entry.lower().strip()[:60].replace(" ", "-").replace("/", "-")
        fpath = os.path.join(cat_dir, f"{slug}.md")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(entry if entry.endswith("\n") else entry + "\n")
        return f"Recorded experience in '{category}': {entry[:80]}"

    def read_experiences(self, category: str, exp_path: str = "") -> str:
        root = exp_path or os.path.join(self._memory_dir, "experiences")
        cat_dir = os.path.join(root, category)
        if not os.path.isdir(cat_dir):
            return f"No experiences found for category '{category}'"
        entries = []
        for fname in sorted(os.listdir(cat_dir)):
            if not fname.endswith(".md"):
                continue
            with open(os.path.join(cat_dir, fname), encoding="utf-8") as f:
                entries.append(f"{fname[:-3]}:\n{f.read().strip()}")
        if not entries:
            return f"No experiences found for category '{category}'"
        return "\n\n".join(entries)
