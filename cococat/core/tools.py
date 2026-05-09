"""Tool system — flat dict tools with registry and execution."""

import os
from typing import Any


def create_core_tools() -> list[dict]:
    """Create the 20 core tools. Each is {name, description, parameters, execute}."""
    return [
        _make("read_file", "Read a file with offset/limit", {"path": "string", "offset": "integer", "limit": "integer"},
              lambda p, ctx: _read_file(p["path"], p.get("offset", 0), p.get("limit", 2000))),
        _make("write_file", "Write content to a file", {"path": "string", "content": "string"},
              lambda p, ctx: _write_file(p["path"], p.get("content", ""))),
        _make("edit_file", "Edit a file by replacing text", {"path": "string", "old": "string", "new": "string"},
              lambda p, ctx: _edit_file(p["path"], p["old"], p["new"])),
        _make("list_dir", "List directory contents", {"path": "string"},
              lambda p, ctx: _list_dir(p["path"])),
        _make("bash", "Execute shell command", {"command": "string"},
              lambda p, ctx: f"[bash] {p['command']} — stub"),
        _make("glob", "Find files by glob pattern", {"pattern": "string"},
              lambda p, ctx: f"[glob] {p['pattern']} — stub"),
        _make("grep", "Search file contents with regex", {"pattern": "string", "path": "string"},
              lambda p, ctx: f"[grep] {p['pattern']} — stub"),
        _make("web_search", "Search the web", {"query": "string"},
              lambda p, ctx: f"[web_search] {p['query']} — stub"),
        _make("web_fetch", "Fetch URL content", {"url": "string"},
              lambda p, ctx: f"[web_fetch] {p['url']} — stub"),
        _make("browser", "Browser control", {"action": "string"},
              lambda p, ctx: f"[browser] {p['action']} — stub"),
        _make("sub_agent", "Spawn a sub-agent (async)", {"task": "string", "agent_id": "string"},
              lambda p, ctx: f"[sub_agent] {p['task']} — stub"),
        _make("check_tasks", "Check pending task status", {},
              lambda p, ctx: f"[check_tasks] — stub"),
        _make("stop_task", "Cancel a running task", {"task_id": "string"},
              lambda p, ctx: f"[stop_task] {p['task_id']} — stub"),
        _make("todo_write", "Structured task list", {"todos": "array"},
              lambda p, ctx: f"[todo_write] — stub"),
        _make("recall", "Search memory by keyword (FTS5)", {"query": "string"},
              lambda p, ctx: f"[recall] {p['query']} — stub"),
        _make("pin", "Pin a fact to persistent context", {"fact": "string"},
              lambda p, ctx: f"[pin] — stub"),
        _make("unpin", "Unpin a fact", {"keyword": "string"},
              lambda p, ctx: f"[unpin] {p['keyword']} — stub"),
        _make("record_experience", "Record a categorized experience", {"category": "string", "entry": "string"},
              lambda p, ctx: f"[record_experience] — stub"),
        _make("recall_experience", "Recall experiences by category", {"category": "string"},
              lambda p, ctx: f"[recall_experience] {p['category']} — stub"),
        _make("cron", "Schedule a recurring task", {"schedule": "string", "task": "string"},
              lambda p, ctx: f"[cron] — stub"),
        _make("current_status", "Agent runtime introspection", {},
              lambda p, ctx: f"[current_status] — stub"),
        _make("wait", "Sleep for seconds", {"seconds": "number"},
              lambda p, ctx: f"[wait] {p.get('seconds')}s — stub"),
    ]


def _make(name: str, description: str, params: dict, execute_fn) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": params,
        "execute": execute_fn,
    }


class ToolRegistry:
    """Registry for executing tools."""

    def __init__(self, tools: list[dict]):
        self._tools = {t["name"]: t for t in tools}

    async def execute(self, name: str, params: dict, context: dict | None = None) -> str:
        """Execute a tool by name. Returns string result."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        context = context or {}
        result = tool["execute"](params, context)
        if callable(getattr(result, "__await__", None)):
            result = await result
        return str(result)

    def filter(self, allowed_names: set[str]) -> list[dict]:
        """Return tools whose names are in the allowed set."""
        return [t for name, t in self._tools.items() if name in allowed_names]

    def list_tools(self) -> list[dict]:
        return list(self._tools.values())


# ── concrete tool implementations (stubs for now, real logic in Phase 2) ──

def _read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        if offset:
            lines = lines[offset:]
        if limit:
            lines = lines[:limit]
        return "".join(lines)
    except Exception as e:
        return f"Error reading {path}: {e}"


def _write_file(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


def _edit_file(path: str, old_str: str, new_str: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if old_str not in content:
            return f"Error: old string not found in {path}"
        content = content.replace(old_str, new_str, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Edited {path}"
    except Exception as e:
        return f"Error editing {path}: {e}"


def _list_dir(path: str) -> str:
    try:
        items = os.listdir(path)
        items.sort()
        return "\n".join(items)
    except Exception as e:
        return f"Error listing {path}: {e}"
