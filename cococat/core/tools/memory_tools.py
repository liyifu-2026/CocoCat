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


def _resolve_pinned_path(ctx: ToolContext) -> str:
    """Resolve the pinned.md path from agent directory."""
    agent_dir = ctx.agent_dir or ctx.memory.agent_dir or "agents/unknown"
    return os.path.join(agent_dir, "pinned.md")


def _pin(fact: str, ctx: ToolContext) -> str:
    if not fact:
        return "Error: 'fact' is required"
    path = _resolve_pinned_path(ctx)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(fact if fact.endswith("\n") else fact + "\n")
    return f"Pinned: {fact}"


def _unpin(keyword: str, ctx: ToolContext) -> str:
    if not keyword:
        return "Error: 'keyword' is required"
    path = _resolve_pinned_path(ctx)
    if not os.path.exists(path):
        return f"No facts matching '{keyword}' found"
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    kept = [l for l in lines if keyword.lower() not in l.lower()]
    if len(kept) == len(lines):
        return f"No facts matching '{keyword}' found"
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(kept)
    return f"Unpinned facts matching '{keyword}'"


def _list_pins(ctx: ToolContext) -> str:
    path = _resolve_pinned_path(ctx)
    if not os.path.exists(path):
        return "No pinned facts"
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return "No pinned facts"
    return content


def _recall(query: str, ctx: ToolContext) -> str:
    if not query:
        return "Error: 'query' is required"
    return _get_store(ctx).recall(query)


def _remember(note: str, ctx: ToolContext) -> str:
    if not note:
        return "Error: 'note' is required"
    return _get_store(ctx).remember(note)


def _forget(keyword: str, ctx: ToolContext) -> str:
    if not keyword:
        return "Error: 'keyword' is required"
    return _get_store(ctx).forget(keyword)



def make_memory_tools() -> list:
    from cococat.core.tools.types import Tool, _ensure_tool_context
    return [
        Tool(name="recall", description="Search memory by keyword (FTS5)",
             parameters={"query": "string"},
             execute=lambda p, ctx: _recall(p.get("query", ""), _ensure_tool_context(ctx))),
        Tool(name="remember", description="Add a note to the current whiteboard",
             parameters={"note": "string"},
             execute=lambda p, ctx: _remember(p.get("note", ""), _ensure_tool_context(ctx))),
        Tool(name="forget", description="Remove matching notes from whiteboard",
             parameters={"keyword": "string"},
             execute=lambda p, ctx: _forget(p.get("keyword", ""), _ensure_tool_context(ctx))),
        Tool(name="pin", description="Pin a fact to persistent context",
             parameters={"fact": "string"},
             execute=lambda p, ctx: _pin(p.get("fact", ""), _ensure_tool_context(ctx))),
        Tool(name="unpin", description="Unpin a fact",
             parameters={"keyword": "string"},
             execute=lambda p, ctx: _unpin(p.get("keyword", ""), _ensure_tool_context(ctx))),
        Tool(name="list_pins", description="List all pinned facts",
             parameters={},
             execute=lambda p, ctx: _list_pins(_ensure_tool_context(ctx))),
    ]
