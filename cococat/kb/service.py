"""KBService — unified knowledge base operations.

Pure function service layer wrapping ingest/*.py capabilities.
Does NOT depend on LLM, HTTP, or agent infrastructure.
LLM is passed as a parameter where needed.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger("cococat.kb.service")


class KBService:
    """Unified KB operations. All file I/O, no side effects beyond the KB directory."""

    def __init__(self, knowledge_dir: str = "knowledge"):
        self._knowledge_dir = knowledge_dir

    def _kb_path(self, kb_name: str) -> str:
        return os.path.join(self._knowledge_dir, kb_name)

    # ── Query ──────────────────────────────────────────

    def search(self, kb_name: str, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across wiki pages. Returns [{name, type, snippet}, ...]."""
        wiki_dir = os.path.join(self._kb_path(kb_name), "wiki")
        if not os.path.isdir(wiki_dir) or not query:
            return []

        q = query.lower()
        results = []
        for root, _, files in os.walk(wiki_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(root, fname)
                with open(path, encoding="utf-8") as f:
                    content = f.read(5000)
                if q in content.lower():
                    rel = os.path.relpath(root, wiki_dir)
                    idx = content.lower().index(q)
                    start = max(0, idx - 80)
                    end = min(len(content), idx + len(q) + 120)
                    snippet = content[start:end].strip()
                    results.append({
                        "name": fname[:-3],
                        "type": rel,
                        "snippet": snippet,
                    })
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
        return results

    def read(self, kb_name: str, page_type: str, slug: str) -> dict | None:
        """Read a single wiki page. Returns {name, type, content} or None."""
        path = os.path.join(self._kb_path(kb_name), "wiki", page_type, f"{slug}.md")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            content = f.read(10000)
        return {"name": slug, "type": page_type, "content": content}

    def list_pages(self, kb_name: str) -> dict[str, list[str]]:
        """List all wiki pages. Returns {entities: [...], concepts: [...]}."""
        kb_path = self._kb_path(kb_name)
        result = {}
        for pt in ("entities", "concepts"):
            path = os.path.join(kb_path, "wiki", pt)
            if os.path.isdir(path):
                result[pt] = sorted(
                    f[:-3] for f in os.listdir(path)
                    if f.endswith(".md") and not f.startswith(".")
                )
            else:
                result[pt] = []
        return result

    def get_graph(self, kb_name: str) -> dict:
        """Get knowledge graph D3 data + insights."""
        from cococat.ingest.graph import KnowledgeGraph
        graph = KnowledgeGraph(self._kb_path(kb_name))
        return {
            "graph": graph.to_d3(),
            "insights": graph.insights(),
        }

    # ── Write ───────────────────────────────────────────

    def write_page(self, kb_name: str, page_type: str, slug: str,
                   content: str, frontmatter: dict | None = None) -> None:
        """Create or overwrite a wiki page. Auto-updates index.md and log.md."""
        kb_path = self._kb_path(kb_name)
        wiki_dir = os.path.join(kb_path, "wiki", page_type)
        os.makedirs(wiki_dir, exist_ok=True)

        from cococat.ingest.merge import write_frontmatter
        fm = frontmatter or {}
        fm.setdefault("title", slug)
        fm.setdefault("type", page_type[:-3] + "y" if page_type.endswith("ies") else page_type[:-1])
        file_content = write_frontmatter(fm, content)

        file_path = os.path.join(wiki_dir, f"{slug}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)

        self._update_index(kb_path, page_type, slug)
        self._append_log(kb_path, f"Wrote {page_type}/{slug}")

    async def cascade_delete(self, kb_name: str, source_filename: str, llm: Any = None) -> list[str]:
        """Delete a source file and clean up all wiki pages referencing it."""
        from cococat.ingest.cascade import cascade_delete_source
        return await cascade_delete_source(source_filename, self._kb_path(kb_name), llm)

    # ── Maintenance ─────────────────────────────────────

    async def run_dedup(self, kb_name: str, llm: Any) -> dict:
        """Run 3-stage dedup pipeline. Returns {merged, removed, log}."""
        from cococat.ingest.dedup import DedupPipeline
        pipeline = DedupPipeline(llm, self._kb_path(kb_name))
        count = await pipeline.run()
        return {"merged": count, "removed": [], "log": f"Merged {count} pages"}

    def run_lint(self, kb_name: str) -> dict:
        """Run health check. Returns {orphans, broken_links, missing_fm}."""
        from cococat.ingest.overview import lint_kb
        return lint_kb(self._kb_path(kb_name))

    async def gen_overview(self, kb_name: str, llm: Any = None) -> str:
        """Generate/update overview.md. Returns the generated markdown."""
        from cococat.ingest.overview import update_overview
        return await update_overview(self._kb_path(kb_name), llm)

    # ── Context ─────────────────────────────────────────

    def get_overview_context(self, kb_names: list[str]) -> str:
        """Build KB overview markdown for system prompt injection."""
        from cococat.kb import load_kb_overview
        return load_kb_overview(kb_names, self._knowledge_dir)

    # ── Internal ────────────────────────────────────────

    def _update_index(self, kb_path: str, page_type: str, slug: str) -> None:
        """Ensure slug appears in index.md under the correct category."""
        index_path = os.path.join(kb_path, "index.md")
        category = page_type.capitalize()

        if os.path.exists(index_path):
            with open(index_path, encoding="utf-8") as f:
                existing = f.read()
        else:
            existing = ""

        if re.search(rf"^- {re.escape(slug)}$", existing, re.MULTILINE):
            return

        if not existing:
            content = f"# Index\n\n## {category}\n- {slug}\n"
        else:
            heading = f"## {category}"
            idx = existing.find(heading)
            if idx >= 0:
                # Find end of this section (next ## or EOF)
                next_heading = existing.find("\n## ", idx + len(heading))
                if next_heading >= 0:
                    before = existing[:next_heading]
                    after = existing[next_heading:]
                    content = before.rstrip() + f"\n- {slug}\n\n" + after.lstrip()
                else:
                    content = existing.rstrip() + f"\n- {slug}\n"
            else:
                content = existing.rstrip() + f"\n\n## {category}\n- {slug}\n"

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _append_log(self, kb_path: str, entry: str) -> None:
        """Append an entry to log.md."""
        from datetime import datetime
        log_path = os.path.join(kb_path, "log.md")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        line = f"- {ts} | {entry}\n"

        mode = "a" if os.path.exists(log_path) else "w"
        with open(log_path, mode, encoding="utf-8") as f:
            if mode == "w":
                f.write("# Ingest Log\n")
            f.write(line)


# Singleton convenience
_service: KBService | None = None


def get_kb_service(knowledge_dir: str = "knowledge") -> KBService:
    global _service
    if _service is None or knowledge_dir != "knowledge":
        _service = KBService(knowledge_dir)
    return _service
