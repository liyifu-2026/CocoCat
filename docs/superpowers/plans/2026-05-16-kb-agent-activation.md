# KB Agent Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate the KB system by creating a dedicated kb-agent (Resident agent), a KBService layer, agent tools, cron maintenance, and a frontend chat panel.

**Architecture:** KBService encapsulates existing ingest/*.py capabilities into a pure-function service layer. kb-agent is a Resident agent (peer of Coco) with 9 KB tools, bound to the /knowledge page. All other agents get read-only search_kb + read_wiki tools. CronTaskRunner triggers periodic lint/dedup/overview.

**Tech Stack:** Python (FastAPI, asyncio), React (TypeScript, TanStack Query), SQLite

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `cococat/kb/service.py` | Create | KBService — unified KB operations |
| `cococat/core/agent.py` | Modify | AgentRole RESIDENT/WORKER, role checks |
| `cococat/core/tools/__init__.py` | Modify | Add kb_tools + call_worker tool |
| `cococat/core/tools/kb_tools.py` | Create | KB tool implementations |
| `cococat/core/bootstrap.py` | Modify | Load resident agents, role mapping, kb-tools wiring |
| `cococat/core/agent_pool.py` | Modify | get_residents(), get_free_workers() |
| `cococat/worker.py` | Modify | CronTaskRunner integration |
| `cococat/kb/__init__.py` | Modify | get_overview_context(), update load_kb_overview |
| `cococat/routes/chat.py` | Modify | Add /api/kb-chat endpoint |
| `cococat/routes/knowledge.py` | Modify | Accept target_agent param, WS events |
| `cococat/prompt.py` | Modify | KB overview integration, resident prompts |
| `skills/public/knowledge-ingestion.md` | Create | kb-agent ingestion skill |
| `config/residents/kb-agent.yaml` | Create | kb-agent configuration |
| `config/residents/coco.yaml` | Create | Coco configuration (extract from seed) |
| `web-ui/src/pages/KnowledgeDetail.tsx` | Modify | Add kb-agent chat panel |
| `web-ui/src/pages/Knowledge.tsx` | Modify | Add upload button |
| `web-ui/src/components/KbChatPanel.tsx` | Create | Chat panel component |
| `tests/cococat/test_kb_service.py` | Create | KBService unit tests |
| `tests/cococat/test_cron_runner.py` | Create | CronTaskRunner tests |
| `tests/cococat/test_agent_roles.py` | Create | Agent role permission tests |

---

### Task 1: KBService — Unified Service Layer

**Files:**
- Create: `cococat/kb/service.py`
- Create: `tests/cococat/test_kb_service.py`

- [ ] **Step 1: Write the failing test for KBService.search**

```python
# tests/cococat/test_kb_service.py
import os
import tempfile
import pytest
from cococat.kb.service import KBService

@pytest.fixture
def temp_kb():
    """Create a temporary KB directory with test pages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        kb_dir = os.path.join(tmpdir, "test-kb")
        wiki_dir = os.path.join(kb_dir, "wiki", "entities")
        os.makedirs(wiki_dir)
        with open(os.path.join(wiki_dir, "python.md"), "w") as f:
            f.write("---\ntitle: Python\ntype: entity\n---\n\nPython is a programming language.")
        with open(os.path.join(wiki_dir, "rust.md"), "w") as f:
            f.write("---\ntitle: Rust\ntype: entity\n---\n\nRust is a systems language.")
        concepts_dir = os.path.join(kb_dir, "wiki", "concepts")
        os.makedirs(concepts_dir)
        with open(os.path.join(concepts_dir, "async.md"), "w") as f:
            f.write("---\ntitle: Async\ntype: concept\n---\n\nAsync programming with coroutines.")
        os.makedirs(os.path.join(kb_dir, "raw", "sources"))
        with open(os.path.join(kb_dir, "index.md"), "w") as f:
            f.write("# Index\n\n## Entities\n- python\n- rust\n\n## Concepts\n- async")
        with open(os.path.join(kb_dir, "purpose.md"), "w") as f:
            f.write("Test knowledge base for unit tests.")
        yield kb_dir


def test_search_finds_matching_pages(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    results = service.search("test-kb", "programming")
    assert len(results) >= 2
    names = [r["name"] for r in results]
    assert "python" in names
    assert "rust" in names


def test_search_case_insensitive(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    results = service.search("test-kb", "PYTHON")
    assert len(results) >= 1
    assert results[0]["name"] == "python"


def test_search_no_match(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    results = service.search("test-kb", "zzzzzz_nonexistent")
    assert results == []


def test_read_page(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    page = service.read("test-kb", "entities", "python")
    assert page is not None
    assert page["name"] == "python"
    assert "programming language" in page["content"]


def test_read_nonexistent_page(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    page = service.read("test-kb", "entities", "nonexistent")
    assert page is None


def test_list_pages(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    pages = service.list_pages("test-kb")
    assert "entities" in pages
    assert "concepts" in pages
    assert "python" in pages["entities"]
    assert "async" in pages["concepts"]


def test_write_page(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    service.write_page("test-kb", "entities", "golang", "Go is a compiled language.", {
        "title": "Go", "type": "entity",
    })
    page = service.read("test-kb", "entities", "golang")
    assert page is not None
    assert "compiled language" in page["content"]


def test_write_page_updates_index(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    service.write_page("test-kb", "concepts", "testing", "Testing is important.", {
        "title": "Testing", "type": "concept",
    })
    index_path = os.path.join(temp_kb, "index.md")
    with open(index_path) as f:
        content = f.read()
    assert "testing" in content.lower()


def test_get_overview_context(temp_kb):
    service = KBService(knowledge_dir=os.path.dirname(temp_kb))
    ctx = service.get_overview_context(["test-kb"])
    assert "test-kb" in ctx
    assert "Test knowledge base" in ctx
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cococat/test_kb_service.py -v`
Expected: FAIL with "No module named 'cococat.kb.service'" or similar

- [ ] **Step 3: Write KBService implementation**

```python
# cococat/kb/service.py
"""KBService — unified knowledge base operations.

Pure function service layer wrapping ingest/*.py capabilities.
Does NOT depend on LLM, HTTP, or agent infrastructure.
LLM is passed as a parameter where needed.
"""

from __future__ import annotations

import logging
import os
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

        # Build file content with frontmatter
        from cococat.ingest.merge import write_frontmatter
        fm = frontmatter or {}
        fm.setdefault("title", slug)
        fm.setdefault("type", page_type.rstrip("s"))  # "entities" → "entity"
        file_content = write_frontmatter(fm, content)

        file_path = os.path.join(wiki_dir, f"{slug}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)

        self._update_index(kb_path, page_type, slug)
        self._append_log(kb_path, f"Wrote {page_type}/{slug}")

    def cascade_delete(self, kb_name: str, source_filename: str, llm: Any = None) -> list[str]:
        """Delete a source file and clean up all wiki pages referencing it."""
        from cococat.ingest.cascade import cascade_delete_source
        return cascade_delete_source(source_filename, self._kb_path(kb_name), llm)  # type: ignore[return-value]

    # ── Maintenance ─────────────────────────────────────

    def run_dedup(self, kb_name: str, llm: Any) -> dict:
        """Run 3-stage dedup pipeline. Returns {merged, removed, log}."""
        from cococat.ingest.dedup import DedupPipeline
        pipeline = DedupPipeline(llm, self._kb_path(kb_name))
        return pipeline.run()  # type: ignore[return-value]

    def run_lint(self, kb_name: str) -> dict:
        """Run health check. Returns {orphans, broken_links, missing_frontmatter}."""
        from cococat.ingest.overview import lint_kb
        return lint_kb(self._kb_path(kb_name))  # type: ignore[return-value]

    async def gen_overview(self, kb_name: str, llm: Any = None) -> str:
        """Generate/update overview.md. Returns the generated markdown."""
        from cococat.ingest.overview import update_overview
        return await update_overview(self._kb_path(kb_name), llm)

    # ── Context ─────────────────────────────────────────

    def get_overview_context(self, kb_names: list[str]) -> str:
        """Build KB overview markdown for system prompt injection.
        Uses overview.md if available, falls back to purpose.md + index.md preview.
        """
        from cococat.kb import load_kb_overview
        return load_kb_overview(kb_names, self._knowledge_dir)

    # ── Internal ────────────────────────────────────────

    def _update_index(self, kb_path: str, page_type: str, slug: str) -> None:
        """Ensure slug appears in index.md under the correct category."""
        index_path = os.path.join(kb_path, "index.md")
        category = page_type.capitalize()  # "entities" → "Entities"

        existing = ""
        if os.path.exists(index_path):
            with open(index_path, encoding="utf-8") as f:
                existing = f.read()

        if f"- {slug}" in existing:
            return  # already indexed

        if existing:
            content = existing.rstrip() + f"\n- {slug}\n"
        else:
            content = f"# Index\n\n## {category}\n- {slug}\n"

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
    if _service is None:
        _service = KBService(knowledge_dir)
    return _service
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cococat/test_kb_service.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add cococat/kb/service.py tests/cococat/test_kb_service.py
git commit -m "feat: add KBService unified service layer"
```

---

### Task 2: AgentRole — RESIDENT/WORKER Redesign

**Files:**
- Modify: `cococat/core/agent.py:26-28,79-83`
- Modify: `cococat/core/agent_pool.py:42-47`

- [ ] **Step 1: Update AgentRole enum and role checks**

```python
# cococat/core/agent.py — replace lines 26-28
class AgentRole(Enum):
    RESIDENT = "resident"   # Permanent, page-bound, peer-level
    WORKER = "worker"       # Ephemeral pool, created/destroyed per task
```

Replace line 81:
```python
# cococat/core/agent.py — replace Agent.bind_to_scene role check
    def bind_to_scene(self, scene) -> None:
        """Bind this agent to a scene. Accepts SceneConfig object or scene_id string."""
        if self.role == AgentRole.RESIDENT:
            raise ValueError("Resident agents cannot bind to a scene (they are page-bound).")
        # ... rest unchanged
```

- [ ] **Step 2: Update AgentPool for new roles**

```python
# cococat/core/agent_pool.py — replace get_free_sub_agents and add new methods
    def get_free_workers(self) -> list[Agent]:
        """Return all idle worker agents."""
        return [
            a for a in self._agents.values()
            if a.role == AgentRole.WORKER and a.state == AgentState.IDLE
        ]

    def get_residents(self) -> list[Agent]:
        """Return all resident agents."""
        return [
            a for a in self._agents.values()
            if a.role == AgentRole.RESIDENT
        ]

    def get_resident(self, agent_id: str) -> Agent | None:
        """Get a resident agent by ID."""
        agent = self._agents.get(agent_id)
        if agent and agent.role == AgentRole.RESIDENT:
            return agent
        return None
```

- [ ] **Step 3: Run existing tests to catch regressions**

Run: `pytest tests/cococat/ -v -k "not integration" --ignore=tests/cococat/test_kb_service.py`
Expected: verify no failures from AgentRole change

- [ ] **Step 4: Commit**

```bash
git add cococat/core/agent.py cococat/core/agent_pool.py
git commit -m "refactor: AgentRole RESIDENT/WORKER to replace MAIN/SUB"
```

---

### Task 3: KB Agent Tools

**Files:**
- Create: `cococat/core/tools/kb_tools.py`
- Modify: `cococat/core/tools/__init__.py`

- [ ] **Step 1: Create kb_tools.py**

```python
# cococat/core/tools/kb_tools.py
"""KB tool implementations — thin wrappers around KBService."""

from __future__ import annotations

from typing import Any


def _search_kb(params: dict, ctx: dict) -> str:
    """Search a knowledge base."""
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    query = params.get("query", "")
    if not kb_name or not query:
        return "Error: kb_name and query are required"
    service = get_kb_service()
    results = service.search(kb_name, query)
    if not results:
        return f"No results found for '{query}' in KB '{kb_name}'."
    lines = [f"Search results for '{query}' in KB '{kb_name}':"]
    for i, r in enumerate(results, 1):
        lines.append(f"\n{i}. **{r['name']}** ({r['type']})")
        lines.append(f"   {r['snippet'][:200]}")
    return "\n".join(lines)


def _read_wiki(params: dict, ctx: dict) -> str:
    """Read a wiki page."""
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    page_type = params.get("type", "entities")
    slug = params.get("slug", "")
    if not kb_name or not slug:
        return "Error: kb_name, type, and slug are required"
    service = get_kb_service()
    page = service.read(kb_name, page_type, slug)
    if page is None:
        return f"Page '{slug}' not found in KB '{kb_name}' ({page_type})."
    return f"# {page['name']} ({page['type']})\n\n{page['content']}"


def _write_wiki(params: dict, ctx: dict) -> str:
    """Write a wiki page (kb-agent only)."""
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    page_type = params.get("type", "entities")
    slug = params.get("slug", "")
    content = params.get("content", "")
    title = params.get("title", slug)
    if not kb_name or not slug or not content:
        return "Error: kb_name, type, slug, and content are required"
    service = get_kb_service()
    service.write_page(kb_name, page_type, slug, content, {"title": title})
    return f"Page '{slug}' written to KB '{kb_name}' ({page_type})."


def _run_dedup(params: dict, ctx: dict) -> str:
    """Run dedup pipeline (kb-agent only)."""
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    if not kb_name:
        return "Error: kb_name is required"
    llm = ctx.get("_llm")
    if not llm:
        return "Error: LLM not available for dedup"
    service = get_kb_service()
    result = service.run_dedup(kb_name, llm)
    return f"Dedup complete for KB '{kb_name}': {result}"


def _run_lint(params: dict, ctx: dict) -> str:
    """Run health check (kb-agent only)."""
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    if not kb_name:
        return "Error: kb_name is required"
    service = get_kb_service()
    result = service.run_lint(kb_name)
    lines = [f"Lint results for KB '{kb_name}':"]
    for key, val in result.items():
        if isinstance(val, list) and val:
            lines.append(f"- {key}: {len(val)} issues")
            for item in val[:5]:
                lines.append(f"  • {item}")
    if not any(isinstance(v, list) and v for v in result.values()):
        lines.append("No issues found.")
    return "\n".join(lines)


def _gen_overview(params: dict, ctx: dict) -> str:
    """Generate overview (kb-agent only)."""
    import asyncio
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    if not kb_name:
        return "Error: kb_name is required"
    llm = ctx.get("_llm")
    service = get_kb_service()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, service.gen_overview(kb_name, llm))
                overview = future.result(timeout=60)
        else:
            overview = asyncio.run(service.gen_overview(kb_name, llm))
    except RuntimeError:
        overview = asyncio.run(service.gen_overview(kb_name, llm))
    return f"Overview generated for KB '{kb_name}':\n\n{overview[:2000]}"


def _cascade_del(params: dict, ctx: dict) -> str:
    """Cascade delete a source file (kb-agent only)."""
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    source_filename = params.get("source_filename", "")
    if not kb_name or not source_filename:
        return "Error: kb_name and source_filename are required"
    service = get_kb_service()
    modified = service.cascade_delete(kb_name, source_filename)
    return f"Cascade delete complete for '{source_filename}' in KB '{kb_name}'. Modified {len(modified)} page(s)."


def _get_graph(params: dict, ctx: dict) -> str:
    """Get knowledge graph data (kb-agent only)."""
    from cococat.kb.service import get_kb_service
    import json
    kb_name = params.get("kb_name", "")
    if not kb_name:
        return "Error: kb_name is required"
    service = get_kb_service()
    data = service.get_graph(kb_name)
    insights = data.get("insights", {})
    lines = [f"Knowledge graph for KB '{kb_name}':"]
    if insights.get("connections"):
        lines.append(f"\nSurprising connections: {json.dumps(insights['connections'], indent=2)}")
    if insights.get("gaps"):
        lines.append(f"\nKnowledge gaps: {json.dumps(insights['gaps'], indent=2)}")
    if insights.get("bridges"):
        lines.append(f"\nBridge nodes: {json.dumps(insights['bridges'], indent=2)}")
    return "\n".join(lines)


def _call_worker(params: dict, ctx: dict) -> str:
    """Call a worker agent for heavy execution (all resident agents)."""
    task = params.get("task", "")
    if not task:
        return "Error: task is required"
    sub_executor = ctx.get("sub_agent_executor")
    if not sub_executor:
        return "Error: No worker executor available"
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, sub_executor(task, ctx.get("agent_id", "unknown")))
                result = future.result(timeout=120)
        else:
            result = asyncio.run(sub_executor(task, ctx.get("agent_id", "unknown")))
    except RuntimeError:
        result = asyncio.run(sub_executor(task, ctx.get("agent_id", "unknown")))
    return result or "Worker completed, no output."
```

- [ ] **Step 2: Add kb tools to __init__.py**

Add to `cococat/core/tools/__init__.py` after existing imports:
```python
# Add at top after existing imports (around line 19):
from cococat.core.tools.kb_tools import (
    _search_kb, _read_wiki, _write_wiki, _run_dedup,
    _run_lint, _gen_overview, _cascade_del, _get_graph, _call_worker,
)
```

Add new function after `_make_sub_agent_tool` (before line 152):
```python
def _make_kb_tools() -> list[dict]:
    """KB tools for agents."""
    return [
        _make("search_kb", "Search a knowledge base wiki", {"kb_name": "string", "query": "string"},
              lambda p, ctx: _search_kb(p, ctx)),
        _make("read_wiki", "Read a wiki page", {"kb_name": "string", "type": "string", "slug": "string"},
              lambda p, ctx: _read_wiki(p, ctx)),
    ]


def _make_kb_admin_tools() -> list[dict]:
    """KB admin tools (write + maintenance) for kb-agent only."""
    return [
        _make("write_wiki", "Write a wiki page", {"kb_name": "string", "type": "string", "slug": "string", "content": "string", "title": "string"},
              lambda p, ctx: _write_wiki(p, ctx)),
        _make("run_dedup", "Run KB dedup pipeline", {"kb_name": "string"},
              lambda p, ctx: _run_dedup(p, ctx)),
        _make("run_lint", "Run KB health check", {"kb_name": "string"},
              lambda p, ctx: _run_lint(p, ctx)),
        _make("gen_overview", "Generate KB overview", {"kb_name": "string"},
              lambda p, ctx: _gen_overview(p, ctx)),
        _make("cascade_del", "Cascade delete source file from KB", {"kb_name": "string", "source_filename": "string"},
              lambda p, ctx: _cascade_del(p, ctx)),
        _make("get_graph", "Get KB knowledge graph", {"kb_name": "string"},
              lambda p, ctx: _get_graph(p, ctx)),
    ]


def _make_call_worker_tool(sub_agent_executor=None) -> list[dict]:
    """call_worker tool for resident agents to invoke worker pool."""
    return [
        _make("call_worker", "Call a worker agent for execution", {"task": "string"},
              (lambda p, ctx: f"[call_worker] {p.get('task', '')} — stub")
              if sub_agent_executor is None else
              (lambda p, ctx: _call_worker(p, {**(ctx or {}), "sub_agent_executor": sub_agent_executor}))),
    ]
```

Update `create_core_tools` to include kb_tools + call_worker:
```python
# In create_core_tools, add after _make_meta_tools() call (line 171):
def create_core_tools(
    sub_agent_executor: Callable[[str, str], Awaitable[str]] | None = None,
    dag_store=None,
    tavily_api_key: str | None = None,
    sandbox_run: Callable[[str], Awaitable[str]] | None = None,
) -> list[dict]:
    """Create the full tool set for worker agents (includes read-only KB tools)."""
    if tavily_api_key is None:
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
    return (
        _make_file_tools() +
        _make_execution_tools(sandbox_run) +
        _make_web_tools(tavily_api_key) +
        _make_dag_tools(dag_store, sub_agent_executor) +
        _make_sub_agent_tool(sub_agent_executor) +
        _make_memory_tools() +
        _make_meta_tools() +
        _make_kb_tools()  # read-only KB access
    )
```

Add new function `create_resident_tools`:
```python
# Add after create_main_ai_tools (after line 187):
def create_resident_tools(
    sub_agent_executor: Callable[[str, str], Awaitable[str]] | None = None,
    dag_store=None,
    is_kb_agent: bool = False,
) -> list[dict]:
    """Create tools for a resident agent.

    Coco: DAG + memory + meta + call_worker + kb_read
    kb-agent: KB tools (read+write+admin) + call_worker + meta
    """
    tools = (
        _make_dag_tools(dag_store, sub_agent_executor) +
        _make_memory_tools() +
        _make_meta_tools() +
        _make_call_worker_tool(sub_agent_executor) +
        _make_kb_tools()  # read-only KB for all residents
    )
    if is_kb_agent:
        tools += _make_kb_admin_tools()
    return tools
```

- [ ] **Step 3: Run tests for tool structure**

Run: `python -c "from cococat.core.tools import create_resident_tools, create_core_tools; r = create_resident_tools(is_kb_agent=True); c = create_core_tools(); print(f'Resident(kb): {len(r)} tools'); print(f'Worker: {len(c)} tools')"`
Expected: Resident(kb): ~18 tools, Worker: ~28 tools

- [ ] **Step 4: Commit**

```bash
git add cococat/core/tools/kb_tools.py cococat/core/tools/__init__.py
git commit -m "feat: add KB agent tools and resident tool sets"
```

---

### Task 4: Bootstrap — Load Resident Agents

**Files:**
- Modify: `cococat/core/bootstrap.py:91-123`

- [ ] **Step 1: Update bootstrap to handle RESIDENT role and KB tools**

Replace the role mapping and agent loading in bootstrap.py (lines 91-123):
```python
    # ── Load agents ──
    # Load resident agents from config first, then DB agents
    _load_residents(ctx, factory, sub_executor, dag_store)
    
    rows = db.list_running_agents()
    for r in rows:
        role_str = r["role"]
        try:
            role = AgentRole(role_str)
        except ValueError:
            # Legacy role mapping
            role_map = {
                "main": AgentRole.RESIDENT,
                "sub": AgentRole.WORKER,
                "worker": AgentRole.WORKER,
                "leader": AgentRole.RESIDENT,
                "employee": AgentRole.WORKER,
            }
            role = role_map.get(role_str)
            if not role:
                logger.warning("Skipping agent %s with unknown role '%s'", r["name"], role_str)
                continue

        # Skip resident agents — they are loaded via _load_residents
        if role == AgentRole.RESIDENT:
            continue

        model = r["model"]
        provider = factory.create_sync(model)
        if not provider:
            logger.warning("No provider for agent %s (model=%s), using stub", r["name"], model)

            class StubLLM:
                async def chat(self, messages, tools=None, **kwargs):
                    return type('obj', (object,), {'content': f"[No provider for model '{model}']", 'tool_calls': None})()

            provider = StubLLM()

        worker_tools = create_core_tools(
            sub_agent_executor=sub_executor.dispatch,
            dag_store=dag_store,
        )

        agent = Agent(
            id=r["id"],
            name=r["name"],
            role=role,
            llm=provider,
            tools=worker_tools,
            agent_dir=f"agents/{r['id']}",
        )
        pool.add_agent(agent)
        logger.info("Worker loaded: %s (%s) → %s", r["name"], r["id"], model)
```

Add `_load_residents` function before `load_agents`:
```python
def _load_residents(ctx, factory, sub_executor, dag_store) -> None:
    """Load resident agents from config/residents/*.yaml and seed DB."""
    import yaml
    import glob as glob_mod
    from cococat.core.tools import create_resident_tools

    pool = ctx.pool
    db = ctx.db

    config_dir = "config/residents"
    if not os.path.isdir(config_dir):
        os.makedirs(config_dir, exist_ok=True)
        _seed_default_residents(config_dir)

    for config_path in sorted(glob_mod.glob(os.path.join(config_dir, "*.yaml"))):
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        except Exception:
            logger.exception("Failed to load resident config: %s", config_path)
            continue

        agent_id = cfg.get("id", "")
        name = cfg.get("name", agent_id)
        model = cfg.get("model", "deepseek-chat")
        is_kb = (agent_id == "kb-agent")

        provider = factory.create_sync(model)
        if not provider:
            logger.warning("No provider for resident %s, using stub", agent_id)
            class StubLLM:
                async def chat(self, messages, tools=None, **kwargs):
                    return type('obj', (object,), {'content': f"[No provider for {model}]", 'tool_calls': None})()
            provider = StubLLM()

        tools = create_resident_tools(
            sub_agent_executor=sub_executor.dispatch,
            dag_store=dag_store,
            is_kb_agent=is_kb,
        )

        agent = Agent(
            id=agent_id,
            name=name,
            role=AgentRole.RESIDENT,
            llm=provider,
            tools=tools,
            agent_dir=f"agents/{agent_id}",
        )
        pool.add_agent(agent)

        # Ensure DB has the agent record
        existing = db._conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not existing:
            db._conn.execute(
                "INSERT INTO agents (id, name, role, model, status) VALUES (?, ?, ?, ?, 'running')",
                (agent_id, name, "resident", model),
            )
            db._conn.commit()

        # Register cron jobs if configured
        cron_jobs = cfg.get("cron", [])
        if cron_jobs:
            from cococat.worker import CronTaskRunner
            runner = ctx.__dict__.setdefault("_cron_runner", CronTaskRunner())
            for job in cron_jobs:
                runner.register(agent_id, job["name"], job["schedule"])

        logger.info("Resident loaded: %s (%s) → %s", name, agent_id, model)


def _seed_default_residents(config_dir: str) -> None:
    """Create default resident configs if they don't exist."""
    import yaml

    coco_path = os.path.join(config_dir, "coco.yaml")
    if not os.path.exists(coco_path):
        with open(coco_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "id": "coco",
                "name": "Coco",
                "role": "resident",
                "page": "/chat",
                "model": "deepseek-chat",
                "skills": [],
                "cron": [],
            }, f, allow_unicode=True)

    kb_path = os.path.join(config_dir, "kb-agent.yaml")
    if not os.path.exists(kb_path):
        with open(kb_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "id": "kb-agent",
                "name": "知识库管理员",
                "role": "resident",
                "page": "/knowledge",
                "model": "deepseek-chat",
                "skills": ["knowledge-ingestion"],
                "cron": [
                    {"name": "lint", "schedule": "@daily"},
                    {"name": "dedup", "schedule": "@weekly"},
                    {"name": "overview", "schedule": "@weekly"},
                ],
            }, f, allow_unicode=True)
```

Also update the `seed_main_agent` in database.py to use "resident" role:
```python
# cococat/db/database.py — update seed_main_agent
def seed_main_agent(self) -> bool:
    existing = self._conn.execute(
        "SELECT id FROM agents WHERE id = 'main'"
    ).fetchone()
    if existing:
        return False
    self._conn.execute(
        "INSERT INTO agents (id, name, role, model, status) "
        "VALUES ('main', 'Coco', 'resident', 'deepseek-chat', 'running')"
    )
    self._conn.commit()
    return True
```

- [ ] **Step 2: Run bootstrap import test**

Run: `python -c "from cococat.db import Database; from cococat.core.agent import AgentRole; print(AgentRole.RESIDENT.value)"`
Expected: Prints "resident"

- [ ] **Step 3: Commit**

```bash
git add cococat/core/bootstrap.py cococat/db/database.py config/residents/
git commit -m "feat: load resident agents from config with cron registration"
```

---

### Task 5: CronTaskRunner

**Files:**
- Modify: `cococat/worker.py`

- [ ] **Step 1: Create CronTaskRunner test**

```python
# tests/cococat/test_cron_runner.py
import time
import pytest
from cococat.worker import CronJob, CronTaskRunner


def test_cron_job_daily_due():
    job = CronJob("test", "lint", "@daily")
    # First call always returns True (never run before)
    assert job.is_due() is True
    # Second call immediately returns False
    assert job.is_due() is False


def test_cron_job_interval():
    job = CronJob("test", "lint", "@daily")
    assert job.is_due() is True
    # simulate time passage
    job._last_run = time.time() - 90000  # 25 hours ago
    assert job.is_due() is True


def test_cron_runner_register_and_tick():
    runner = CronTaskRunner()
    called = []

    async def handler(job_name):
        called.append(job_name)

    runner.register("kb-agent", "lint", "@daily")
    runner.set_handler(handler)
    runner.tick()
    assert "lint" in called


def test_cron_runner_respects_interval():
    runner = CronTaskRunner()
    called = []

    async def handler(job_name):
        called.append(job_name)

    runner.register("kb-agent", "lint", "@daily")
    runner.set_handler(handler)
    runner.tick()
    assert len(called) == 1
    runner.tick()
    assert len(called) == 1  # not due yet
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cococat/test_cron_runner.py -v`
Expected: FAIL — CronJob/CronTaskRunner not defined

- [ ] **Step 3: Add CronTaskRunner to worker.py**

Add to `cococat/worker.py` before the TaskWorker class:
```python
"""Add after existing imports, before TaskWorker class:"""

import time
import re
from typing import Callable, Awaitable


class CronJob:
    """A single cron job with last-run tracking."""

    def __init__(self, agent_id: str, name: str, schedule: str):
        self.agent_id = agent_id
        self.name = name
        self.schedule = schedule
        self._last_run: float = 0
        self._interval = self._parse_schedule(schedule)

    @staticmethod
    def _parse_schedule(schedule: str) -> float:
        """Parse schedule string to seconds. Supports @daily, @weekly, @hourly, or raw seconds."""
        mapping = {
            "@hourly": 3600,
            "@daily": 86400,
            "@weekly": 604800,
        }
        if schedule in mapping:
            return mapping[schedule]
        try:
            return float(schedule)
        except ValueError:
            return 86400  # default daily

    def is_due(self) -> bool:
        """Check if this job is due to run."""
        now = time.time()
        if now - self._last_run >= self._interval:
            return True
        return False

    def mark_run(self) -> None:
        self._last_run = time.time()


class CronTaskRunner:
    """Checks registered cron jobs and fires handlers when due."""

    def __init__(self):
        self._jobs: list[CronJob] = []
        self._handler: Callable[[str, str], Awaitable[None]] | None = None

    def register(self, agent_id: str, name: str, schedule: str) -> None:
        self._jobs.append(CronJob(agent_id, name, schedule))

    def set_handler(self, handler: Callable[[str, str], Awaitable[None]]) -> None:
        self._handler = handler

    def tick(self) -> list[CronJob]:
        """Check all jobs, return list of due jobs."""
        due = [j for j in self._jobs if j.is_due()]
        for job in due:
            job.mark_run()
        return due

    def get_jobs(self) -> list[CronJob]:
        return list(self._jobs)
```

Update TaskWorker._loop to fire cron:
```python
    async def _loop(self) -> None:
        while self._running:
            try:
                await self._process_kb()
                await self._process_dag()
                await self._process_cron()
            except Exception:
                logger.exception("TaskWorker error")
            await asyncio.sleep(self._poll_interval)

    async def _process_cron(self) -> None:
        """Fire due cron jobs."""
        cron_runner: CronTaskRunner | None = getattr(self, '_cron_runner', None)
        if not cron_runner:
            return
        due = cron_runner.tick()
        handler = getattr(cron_runner, '_handler', None)
        if not handler:
            return
        for job in due:
            try:
                await handler(job.agent_id, job.name)
            except Exception:
                logger.exception("Cron job %s/%s failed", job.agent_id, job.name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cococat/test_cron_runner.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add cococat/worker.py tests/cococat/test_cron_runner.py
git commit -m "feat: add CronTaskRunner for resident agent scheduled jobs"
```

---

### Task 6: KB Chat Route

**Files:**
- Modify: `cococat/routes/chat.py`

- [ ] **Step 1: Add /api/kb-chat endpoint**

Add to `cococat/routes/chat.py` after existing routes:
```python
class KbChatRequest(BaseModel):
    content: str
    kb_name: str
    user_id: str = "local"
    session_id: str | None = None


@router.post("/kb-chat")
async def kb_chat(body: KbChatRequest, ctx: AppContext = Depends(get_ctx)):
    """Send a message to kb-agent."""
    msg_uuid = new_uuid()
    ctx.db.save_message(
        msg_uuid=msg_uuid, agent_id="kb-agent", user_id=body.user_id,
        role="user", content=f"[KB:{body.kb_name}] {body.content}",
        scene_id="knowledge", channel_type="web",
    )

    pool = ctx.pool
    agent = pool.get_resident("kb-agent")
    if not agent:
        reply_uuid = new_uuid()
        error_msg = "kb-agent is not available"
        ctx.db.save_message(
            msg_uuid=reply_uuid, agent_id="kb-agent", user_id=body.user_id,
            role="assistant", content=error_msg, scene_id="knowledge",
        )
        return {"reply": error_msg, "msg_uuid": reply_uuid}

    ws = ctx.ws_manager

    async def on_text(delta: str):
        await ws.broadcast("text_delta", {
            "content": delta,
            "agent_id": "kb-agent",
            "session_id": body.session_id,
        })

    async def on_reasoning(content: str):
        await ws.broadcast("stream_reasoning", {
            "content": content,
            "agent_id": "kb-agent",
            "session_id": body.session_id,
        })

    async def on_tool(name: str, status: str, data: dict = None):
        payload = {
            "name": name,
            "status": status,
            "agent_id": "kb-agent",
            "session_id": body.session_id,
        }
        if data:
            payload.update(data)
        await ws.broadcast("stream_tool", payload)

    try:
        message = f"[KB: {body.kb_name}] {body.content}"
        reply = await agent.run(
            message=message,
            on_text=on_text,
            on_reasoning=on_reasoning,
            on_tool=on_tool,
        )
    except Exception as e:
        reply = f"Error: {e}"

    reply_uuid = new_uuid()
    ctx.db.save_message(
        msg_uuid=reply_uuid, agent_id="kb-agent", user_id=body.user_id,
        role="assistant", content=reply, scene_id="knowledge",
    )
    return {"reply": reply, "msg_uuid": reply_uuid}
```

- [ ] **Step 2: Run import check**

Run: `python -c "from cococat.routes.chat import kb_chat; print('Route loaded')"`
Expected: "Route loaded"

- [ ] **Step 3: Commit**

```bash
git add cococat/routes/chat.py
git commit -m "feat: add /api/kb-chat endpoint for kb-agent"
```

---

### Task 7: knowledge-ingestion Skill

**Files:**
- Create: `skills/public/knowledge-ingestion.md`

- [ ] **Step 1: Write the skill file**

```markdown
# Knowledge Ingestion Skill

You are a knowledge base maintainer. When a user gives you source material, follow this process.

## 1. Material Analysis

- Identify the type: document, code, conversation log, image description
- Extract key entities (named things, components, people, tools)
- Extract key concepts (ideas, patterns, techniques, architectures)
- Determine overlap with existing wiki: use `search_kb` to check

## 2. Injection Strategy

- New entity → create `wiki/entities/{slug}.md` using `write_wiki`
- New concept → create `wiki/concepts/{slug}.md` using `write_wiki`
- Existing page needs updating → merge new info using `write_wiki` (it overwrites)
- Use `[[slug]]` wikilinks to cross-reference related pages
- Each page must have YAML frontmatter: type, title, created, summary, sources, tags

## 3. Frontmatter Convention

```yaml
---
type: entity          # or concept
title: Display Name
created: 2026-05-16
summary: One-line description
sources:
  - source-filename.pdf
tags:
  - category
  - keyword
related:
  - other-slug
---
```

## 4. Quality Control

- Run `search_kb` to verify no duplicate exists before writing
- After writing, verify the page reads correctly with `read_wiki`
- Ensure all `[[wikilinks]]` point to existing pages or create the target pages
- Update relevant pages that should link back to the new page

## 5. Batch Processing

If the user uploads a file, you may use `call_worker` to run the ingest pipeline:
```
call_worker(task="Run ingest pipeline for FILE in KB KBNAME")
```
The worker will execute the two-phase LLM ingestion and write wiki pages.

For complex materials, process them yourself step by step using the tools above.
```

- [ ] **Step 2: Verify file exists**

Run: `ls -la skills/public/knowledge-ingestion.md`

- [ ] **Step 3: Commit**

```bash
git add skills/public/knowledge-ingestion.md
git commit -m "feat: add knowledge-ingestion skill for kb-agent"
```

---

### Task 8: Frontend — KB Chat Panel

**Files:**
- Create: `web-ui/src/components/KbChatPanel.tsx`
- Modify: `web-ui/src/pages/KnowledgeDetail.tsx`

- [ ] **Step 1: Create KbChatPanel component**

```tsx
// web-ui/src/components/KbChatPanel.tsx
import { useState, useRef, useEffect } from "react"
import { Send, Loader2, Bot } from "lucide-react"

interface Message {
  role: "user" | "assistant"
  content: string
}

export default function KbChatPanel({ kbName }: { kbName: string }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight)
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput("")
    setMessages(prev => [...prev, { role: "user", content: text }])
    setLoading(true)

    try {
      const res = await fetch("/api/kb-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text, kb_name: kbName }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: "assistant", content: data.reply || "No response" }])
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "Error: failed to reach kb-agent" }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full border-l border-border bg-card/30">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2 shrink-0">
        <Bot className="size-4 text-primary" />
        <span className="text-xs font-medium">kb-agent</span>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
        {messages.length === 0 && (
          <p className="text-muted-foreground text-center pt-8">
            我是知识库管理员，可以帮你搜索、整理、维护 KB。
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : ""}>
            <div className={`inline-block rounded-lg px-3 py-2 max-w-[85%] ${
              m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
            }`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="size-3 animate-spin" />
            kb-agent 思考中...
          </div>
        )}
      </div>
      <div className="p-2 border-t border-border shrink-0">
        <div className="flex gap-1">
          <input
            className="flex-1 bg-background border border-border rounded-md px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="问 kb-agent..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && send()}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="p-1.5 rounded-md hover:bg-accent disabled:opacity-30"
          >
            <Send className="size-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Integrate chat panel into KnowledgeDetail**

In `KnowledgeDetail.tsx`:
- Add import: `import KbChatPanel from "@/components/KbChatPanel"`
- Modify the return JSX to add chat panel on the right side

Replace the return block (starting at line 97):
```tsx
  return (
    <div className="flex h-full">
      <nav className="w-56 border-r border-border overflow-y-auto p-3 space-y-3 shrink-0">
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{kb}</h3>
        {wiki && (
          <>
            <Section title="Entities" items={wiki.entities ?? []} selected={selectedPage} onSelect={(n) => setSelectedPage({ type: "entities", name: n })} />
            <Section title="Concepts" items={wiki.concepts ?? []} selected={selectedPage} onSelect={(n) => setSelectedPage({ type: "concepts", name: n })} />
          </>
        )}
      </nav>
      <main className="flex-1 overflow-auto p-6">
        {pageData ? (
          <div className="max-w-3xl">
            <h1 className="text-xl font-bold mb-4">{(pageData as any)?.name ?? selectedPage?.name}</h1>
            <div className="markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {processedContent}
              </ReactMarkdown>
            </div>
            {backlinks.length > 0 && (
              <div className="mt-8 pt-6 border-t border-border">
                <h2 className="text-sm font-medium text-muted-foreground flex items-center gap-1.5 mb-3">
                  <Link2 className="size-3.5" />
                  Backlinks ({backlinks.length})
                </h2>
                <div className="flex flex-wrap gap-1.5">
                  {backlinks.map(bl => (
                    <button
                      key={bl.name}
                      onClick={() => setSelectedPage(bl)}
                      className="text-xs px-2.5 py-1 rounded-md bg-muted hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {bl.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <FileText className="size-8 mb-2 opacity-40" />
            <p className="text-sm">选择一个页面查看</p>
          </div>
        )}
      </main>
      <div className="w-72 shrink-0">
        <KbChatPanel kbName={kb!} />
      </div>
    </div>
  )
```

- [ ] **Step 3: Verify build**

Run: `cd web-ui && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/components/KbChatPanel.tsx web-ui/src/pages/KnowledgeDetail.tsx
git commit -m "feat: add kb-agent chat panel to knowledge detail page"
```

---

### Task 9: Frontend — Upload Button on Knowledge Page

**Files:**
- Modify: `web-ui/src/pages/Knowledge.tsx`

- [ ] **Step 1: Add upload button to Knowledge page**

Replace KnowledgePage component:
```tsx
// web-ui/src/pages/Knowledge.tsx
import { useState, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { BookOpen, Loader2, Upload, X } from "lucide-react"

export default function KnowledgePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [uploadKb, setUploadKb] = useState<string | null>(null)
  const [uploadStatus, setUploadStatus] = useState("")
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data, isLoading } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetch("/api/knowledge").then(r => r.json()),
  })

  const uploadMutation = useMutation({
    mutationFn: async ({ kbName, file }: { kbName: string; file: File }) => {
      const formData = new FormData()
      formData.append("file", file)
      setUploadStatus("Uploading...")
      const res = await fetch(`/api/knowledge/${kbName}/upload`, {
        method: "POST",
        body: formData,
      })
      const data = await res.json()
      setUploadStatus(`Queued: ${data.task_uuid?.slice(0, 8) || "ok"}`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] })
    },
  })

  const kbs = (data as { kbs?: { id: string; purpose?: string }[] })?.kbs ?? []

  if (isLoading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="size-6 animate-spin" /></div>
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BookOpen className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-bold">知识库</h1>
        </div>
      </div>
      {kbs.length === 0 && (
        <p className="text-sm text-muted-foreground">暂无知识库</p>
      )}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
        {kbs.map(kb => (
          <div key={kb.id} className="relative group">
            <button
              onClick={() => navigate(`/knowledge/${kb.id}`)}
              className="w-full rounded-xl border border-border/60 bg-card p-5 text-left hover:shadow-sm transition-shadow duration-200 space-y-2"
            >
              <h3 className="font-medium">{kb.id}</h3>
              {kb.purpose && <p className="text-xs text-muted-foreground line-clamp-3">{kb.purpose}</p>}
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                setUploadKb(kb.id)
                fileInputRef.current?.click()
              }}
              className="absolute top-3 right-3 p-1.5 rounded-md bg-muted hover:bg-accent opacity-0 group-hover:opacity-100 transition-opacity"
              title="Upload file"
            >
              <Upload className="size-3.5" />
            </button>
          </div>
        ))}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file && uploadKb) {
            uploadMutation.mutate({ kbName: uploadKb, file })
          }
          e.target.value = ""
          setUploadKb(null)
        }}
      />

      {uploadStatus && (
        <div className="fixed bottom-4 right-4 bg-card border border-border rounded-lg px-4 py-2 text-sm shadow-lg flex items-center gap-2">
          <span>{uploadStatus}</span>
          <button onClick={() => setUploadStatus("")}><X className="size-3" /></button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd web-ui && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/pages/Knowledge.tsx
git commit -m "feat: add file upload button to knowledge page"
```

---

### Task 10: Agent Role Permission Tests

**Files:**
- Create: `tests/cococat/test_agent_roles.py`

- [ ] **Step 1: Write the test**

```python
# tests/cococat/test_agent_roles.py
"""Test agent role permissions: RESIDENT vs WORKER, resident tools vs worker tools."""

from cococat.core.agent import Agent, AgentRole
from cococat.core.tools import create_resident_tools, create_core_tools


class StubLLM:
    async def chat(self, messages, tools=None, **kwargs):
        return type('obj', (object,), {'content': 'ok', 'tool_calls': None})()


def test_resident_role_cannot_bind_scene():
    agent = Agent(id="test", name="Test", role=AgentRole.RESIDENT, llm=StubLLM())
    try:
        agent.bind_to_scene("test-scene")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "cannot bind" in str(e).lower()


def test_worker_role_can_bind_scene():
    agent = Agent(id="test", name="Test", role=AgentRole.WORKER, llm=StubLLM())
    # Should not raise
    agent.bind_to_scene("test-scene")
    assert agent.bound_scene == "test-scene"


def test_kb_agent_has_admin_tools():
    tools = create_resident_tools(is_kb_agent=True)
    names = [t["name"] for t in tools]
    assert "write_wiki" in names
    assert "search_kb" in names
    assert "read_wiki" in names
    assert "run_dedup" in names
    assert "run_lint" in names
    assert "gen_overview" in names
    assert "cascade_del" in names
    assert "get_graph" in names
    assert "call_worker" in names


def test_coco_resident_has_read_only_kb():
    tools = create_resident_tools(is_kb_agent=False)
    names = [t["name"] for t in tools]
    assert "search_kb" in names
    assert "read_wiki" in names
    assert "write_wiki" not in names
    assert "run_dedup" not in names
    assert "call_worker" in names


def test_worker_has_read_only_kb():
    tools = create_core_tools()
    names = [t["name"] for t in tools]
    assert "search_kb" in names
    assert "read_wiki" in names
    assert "write_wiki" not in names
    assert "run_dedup" not in names
    assert "bash" in names  # workers have execution tools
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/cococat/test_agent_roles.py -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/cococat/test_agent_roles.py
git commit -m "test: agent role permission tests"
```

---

### Task 11: Integration — Wire Everything Together

**Files:**
- Modify: `cococat/prompt.py`

- [ ] **Step 1: Update prompt.py to use KBService for overview**

Update `cococat/prompt.py` imports and `build_system_prompt`:
```python
# Update import at top of prompt.py (line 9):
from cococat.kb.service import get_kb_service

# Update the kb_overview section in build_system_prompt (line 151-154):
    if scene_kbs:
        service = get_kb_service()
        kb_overview = service.get_overview_context(scene_kbs)
        if kb_overview:
            parts.append(kb_overview)
```

- [ ] **Step 2: Update knowledge route to accept target_agent param**

In `cococat/routes/knowledge.py`, update `upload_file`:
```python
# Change line 30 from: target_agent="main"
# To:
    target_agent = "kb-agent"  # Always route KB tasks to kb-agent
    ctx.db.create_task(
        task_uuid=task_uuid, target_agent=target_agent, source="kb",
        method="process_kb_source",
        params=f'{{"kb_name": "{kb_name}", "filename": "{file.filename}"}}',
    )
```

- [ ] **Step 3: Verify full import chain**

Run: `python -c "
from cococat.kb.service import get_kb_service
from cococat.core.agent import Agent, AgentRole
from cococat.core.tools import create_resident_tools, create_core_tools
from cococat.worker import CronTaskRunner, CronJob
from cococat.core.bootstrap import _load_residents
print('All imports OK')
"`

- [ ] **Step 4: Run all tests**

Run: `pytest tests/cococat/ -v --ignore=tests/cococat/test_kb_integration.py -x`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add cococat/prompt.py cococat/routes/knowledge.py
git commit -m "feat: wire kb-agent into prompt, routes, and task dispatch"
```

---

### Task 12: List KBs Agent Route (Optional — expose KB list to agents)

**Files:**
- Modify: `cococat/core/tools/kb_tools.py`

- [ ] **Step 1: Add list_kbs to kb_tools**

Add to `cococat/core/tools/kb_tools.py`:
```python
def _list_kbs(params: dict, ctx: dict) -> str:
    """List all available knowledge bases."""
    import os
    kb_dir = "knowledge"
    if not os.path.isdir(kb_dir):
        return "No knowledge bases found."
    kbs = [n for n in os.listdir(kb_dir)
           if os.path.isdir(os.path.join(kb_dir, n)) and not n.startswith(".")]
    if not kbs:
        return "No knowledge bases found."
    return "Available knowledge bases:\n" + "\n".join(f"- {kb}" for kb in kbs)
```

Add to `_make_kb_tools()`:
```python
        _make("list_kbs", "List available knowledge bases", {},
              lambda p, ctx: _list_kbs(p, ctx)),
```

- [ ] **Step 2: Run test and commit**

```bash
pytest tests/cococat/test_agent_roles.py -v
git add cococat/core/tools/kb_tools.py cococat/core/tools/__init__.py
git commit -m "feat: add list_kbs tool for agents"
```
