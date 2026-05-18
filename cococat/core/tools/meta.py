"""Meta tools — cron, wait, current_status, todo_write."""
import json
import os

from cococat.core.types import ToolContext


def _resolve(ctx) -> ToolContext:
    return ToolContext.from_dict(ctx)


def _cron(schedule: str, task: str, ctx: ToolContext) -> str:
    ctx = _resolve(ctx)
    if not schedule:
        return "Error: 'schedule' is required"
    if not task:
        return "Error: 'task' is required"
    import uuid
    entry_id = str(uuid.uuid4())[:8]
    entry = {
        "id": entry_id,
        "schedule": schedule,
        "task": task,
        "created_at": str(__import__("datetime").datetime.now()),
        "status": "active",
    }
    if ctx.db is not None:
        try:
            ctx.db.dag_runs.save(f"cron:{entry_id}", entry)
            return f"Scheduled task '{task}' with schedule '{schedule}' (id: {entry_id})"
        except Exception as e:
            return f"Error scheduling task to DB: {e}"

    cron_path = ctx.cron_path
    try:
        os.makedirs(cron_path, exist_ok=True)
        fname = f"{entry_id}.json"
        with open(os.path.join(cron_path, fname), "w") as f:
            json.dump(entry, f, indent=2)
        return f"Scheduled task '{task}' with schedule '{schedule}' (id: {entry_id})"
    except Exception as e:
        return f"Error scheduling task: {e}"


async def _wait(seconds: float) -> str:
    import asyncio
    try:
        secs = float(seconds) if seconds else 0
        if secs < 0:
            return "Error: seconds must be non-negative"
        if secs > 0:
            await asyncio.sleep(secs)
        return f"Waited {secs}s" if secs > 0 else "Waited 0s"
    except (ValueError, TypeError):
        return "Error: 'seconds' must be a number"


def _current_status(ctx: ToolContext) -> str:
    ctx = _resolve(ctx)
    parts = []
    if ctx.agent_id:
        parts.append(f"agent_id: {ctx.agent_id}")
    if ctx.bound_scene:
        parts.append(f"bound_scene: {ctx.bound_scene}")
    if ctx.role:
        parts.append(f"role: {ctx.role}")
    parts.append("tools: 20 core tools loaded")
    return "\n".join(parts)


def _todo_write(todos, ctx: ToolContext) -> str:
    ctx = _resolve(ctx)
    if todos is None:
        return "Error: 'todos' is required"

    if ctx.db is not None:
        try:
            agent_id = ctx.agent_id or "main"
            ctx.db.todos.save(todos, agent_id=agent_id)
            return f"Saved {len(todos)} todo items (DB)"
        except Exception as e:
            return f"Error saving todos to DB: {e}"

    path = ctx.todos_path
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2, ensure_ascii=False)
        return f"Saved {len(todos)} todo items to {path}"
    except Exception as e:
        return f"Error saving todos: {e}"


def make_meta_tools() -> list:
    from cococat.core.tools.types import Tool, _ensure_tool_context
    return [
        Tool(name="todo_write", description="Structured task list",
             parameters={"todos": "array"},
             execute=lambda p, ctx: _todo_write(p.get("todos"), _ensure_tool_context(ctx))),
        Tool(name="cron", description="Schedule a recurring task",
             parameters={"schedule": "string", "task": "string"},
             execute=lambda p, ctx: _cron(p.get("schedule", ""), p.get("task", ""), _ensure_tool_context(ctx))),
        Tool(name="current_status", description="Agent runtime introspection",
             parameters={},
             execute=lambda p, ctx: _current_status(_ensure_tool_context(ctx))),
        Tool(name="wait", description="Sleep for seconds",
             parameters={"seconds": "number"},
             execute=lambda p, ctx: _wait(p.get("seconds", 0))),
    ]
