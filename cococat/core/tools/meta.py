"""Meta tools — cron, wait, current_status, todo_write."""
import json
import os


def _cron(schedule: str, task: str, ctx: dict) -> str:
    if not schedule:
        return "Error: 'schedule' is required"
    if not task:
        return "Error: 'task' is required"
    import uuid
    cron_path = ctx.get("cron_path", "runs/cron")
    try:
        os.makedirs(cron_path, exist_ok=True)
        entry = {
            "id": str(uuid.uuid4())[:8],
            "schedule": schedule,
            "task": task,
            "created_at": str(__import__("datetime").datetime.now()),
            "status": "active",
        }
        fname = f"{entry['id']}.json"
        with open(os.path.join(cron_path, fname), "w") as f:
            json.dump(entry, f, indent=2)
        return f"Scheduled task '{task}' with schedule '{schedule}' (id: {entry['id']})"
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


def _current_status(ctx: dict) -> str:
    parts = []
    if ctx.get("agent_id"):
        parts.append(f"agent_id: {ctx['agent_id']}")
    if ctx.get("bound_scene"):
        parts.append(f"bound_scene: {ctx['bound_scene']}")
    if ctx.get("role"):
        parts.append(f"role: {ctx['role']}")
    parts.append("tools: 20 core tools loaded")
    return "\n".join(parts)


def _todo_write(todos, ctx: dict) -> str:
    if todos is None:
        return "Error: 'todos' is required"
    path = ctx.get("todos_path", "todos.json")
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2, ensure_ascii=False)
        return f"Saved {len(todos)} todo items to {path}"
    except Exception as e:
        return f"Error saving todos: {e}"
