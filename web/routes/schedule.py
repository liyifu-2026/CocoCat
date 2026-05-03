"""Schedule management routes."""
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_schedule():
    path = BASE_DIR / "agents" / "schedule.json"
    if not path.exists():
        return {"tasks": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"tasks": []}


def _save_schedule(data: dict):
    path = BASE_DIR / "agents" / "schedule.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/api/schedule")
def get_schedule():
    """Get the full schedule (all tasks)."""
    return _load_schedule()


@router.post("/api/schedule/tasks")
def create_task(body: dict):
    """Create a new scheduled task."""
    task = body.get("task", "").strip()
    assigned_to = body.get("assigned_to", "").strip()
    if not task:
        return JSONResponse({"error": "task description is required"}, status_code=400)
    if not assigned_to:
        return JSONResponse({"error": "assigned_to is required"}, status_code=400)

    schedule = _load_schedule()
    tasks = schedule.get("tasks", [])

    new_id = max([t.get("id", 0) for t in tasks], default=0) + 1
    new_task = {
        "id": new_id,
        "task": task,
        "assigned_to": assigned_to,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "result": "",
    }
    tasks.append(new_task)
    schedule["tasks"] = tasks
    _save_schedule(schedule)

    return {"status": "created", "task": new_task}


@router.patch("/api/schedule/tasks/{task_id}")
def update_task(task_id: int, body: dict):
    """Update a task (status, reassign, edit description)."""
    schedule = _load_schedule()
    for t in schedule.get("tasks", []):
        if t.get("id") == task_id:
            if "task" in body:
                t["task"] = body["task"]
            if "assigned_to" in body:
                t["assigned_to"] = body["assigned_to"]
            if "status" in body:
                t["status"] = body["status"]
            _save_schedule(schedule)
            return {"status": "updated", "task": t}

    return JSONResponse({"error": "task not found"}, status_code=404)


@router.delete("/api/schedule/tasks/{task_id}")
def delete_task(task_id: int):
    """Delete a task."""
    schedule = _load_schedule()
    tasks = [t for t in schedule.get("tasks", []) if t.get("id") != task_id]
    if len(tasks) == len(schedule.get("tasks", [])):
        return JSONResponse({"error": "task not found"}, status_code=404)
    schedule["tasks"] = tasks
    _save_schedule(schedule)
    return {"status": "deleted"}
