"""Memory tools — thin wrappers delegating to MemoryStore."""
import os

from cococat.core.types import ToolContext
from cococat.memory.store import MemoryStore


def _get_store(ctx: ToolContext) -> MemoryStore:
    """Get or create MemoryStore from tool context."""
    if hasattr(ctx, '_memory_store'):
        return ctx._memory_store
    mem_path = ctx.memory.memory_path
    if mem_path:
        if os.path.splitext(mem_path)[1]:
            mem_path = os.path.dirname(mem_path)
    if not mem_path and ctx.memory.agent_dir:
        mem_path = os.path.join(ctx.memory.agent_dir, "memory")
    memory_dir = mem_path or "memory"
    store = MemoryStore(db=ctx.db, memory_dir=memory_dir)
    ctx._memory_store = store
    return store


def _pin(fact: str, ctx: ToolContext) -> str:
    if not fact:
        return "Error: 'fact' is required"
    return _get_store(ctx).remember(fact)


def _unpin(keyword: str, ctx: ToolContext) -> str:
    if not keyword:
        return "Error: 'keyword' is required"
    return _get_store(ctx).forget(keyword)


def _recall(query: str, ctx: ToolContext) -> str:
    if not query:
        return "Error: 'query' is required"
    return _get_store(ctx).recall(query)


def _record_experience(category: str, entry: str, ctx: ToolContext) -> str:
    if not category:
        return "Error: 'category' is required"
    if not entry:
        return "Error: 'entry' is required"
    store = _get_store(ctx)
    return store.remember(entry, category=category, exp_path=ctx.memory.exp_path)


def _recall_experience(category: str, ctx: ToolContext) -> str:
    if not category:
        return "Error: 'category' is required"
    store = _get_store(ctx)
    return store.read_experiences(category, exp_path=ctx.memory.exp_path)


def make_memory_tools() -> list:
    from cococat.core.tools.types import Tool, _ensure_tool_context
    return [
        Tool(name="recall", description="Search memory by keyword (FTS5)",
             parameters={"query": "string"},
             execute=lambda p, ctx: _recall(p.get("query", ""), _ensure_tool_context(ctx))),
        Tool(name="pin", description="Pin a fact to persistent context",
             parameters={"fact": "string"},
             execute=lambda p, ctx: _pin(p.get("fact", ""), _ensure_tool_context(ctx))),
        Tool(name="unpin", description="Unpin a fact",
             parameters={"keyword": "string"},
             execute=lambda p, ctx: _unpin(p.get("keyword", ""), _ensure_tool_context(ctx))),
        Tool(name="record_experience", description="Record a categorized experience",
             parameters={"category": "string", "entry": "string"},
             execute=lambda p, ctx: _record_experience(p.get("category", ""), p.get("entry", ""), _ensure_tool_context(ctx))),
        Tool(name="recall_experience", description="Recall experiences by category",
             parameters={"category": "string"},
             execute=lambda p, ctx: _recall_experience(p.get("category", ""), _ensure_tool_context(ctx))),
    ]
