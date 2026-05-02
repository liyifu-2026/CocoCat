"""Heartbeat service: periodically check schedule and execute pending tasks."""
import os
import json
import time
import threading


def get_schedule_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "schedule.json")


def load_schedule():
    path = get_schedule_path()
    if not os.path.exists(path):
        return {"tasks": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_schedule(schedule: dict):
    path = get_schedule_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)


def get_pending_tasks(agent_id: str) -> list[dict]:
    schedule = load_schedule()
    return [t for t in schedule.get("tasks", [])
            if t.get("assigned_to") == agent_id and t.get("status") == "pending"]


def update_task_status(task_id: int, status: str, result: str = ""):
    schedule = load_schedule()
    for t in schedule.get("tasks", []):
        if t.get("id") == task_id:
            t["status"] = status
            if result:
                t["result"] = result
            break
    save_schedule(schedule)


def start_heartbeat(agent_id: str, agent_name: str, interval: int = 300):
    thread = threading.Thread(target=_heartbeat_loop, args=(agent_id, agent_name, interval), daemon=True)
    thread.start()
    return thread


def _heartbeat_loop(agent_id: str, agent_name: str, interval: int):
    while True:
        time.sleep(interval)
        try:
            tasks = get_pending_tasks(agent_id)
            if not tasks:
                continue
            print(f"[Heartbeat] {agent_name} found {len(tasks)} pending task(s)")
            for task in tasks:
                _execute_task(agent_id, agent_name, task)
        except Exception as e:
            print(f"[Heartbeat] Error: {e}")


def _execute_task(agent_id: str, agent_name: str, task: dict):
    from agent_loop import AgentLoop
    from tools import create_default_registry
    from context import load_agent_memory

    task_id = task.get("id")
    prompt = task.get("task", "")
    if not prompt:
        update_task_status(task_id, "failed", "No task description")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    agent_runtime_path = os.path.join(script_dir, "agent_runtime.py")
    tools = create_default_registry(agent_runtime_path=agent_runtime_path, agent_id=agent_id)
    agent_memory = load_agent_memory(agent_id)
    loop = AgentLoop(agent_id=agent_id, agent_name=agent_name, tools=tools)

    try:
        result = loop.run(prompt)
        content = result.get("content", "")
        update_task_status(task_id, "completed", content[:500])
        print(f"[Heartbeat] Task {task_id} completed")
    except Exception as e:
        update_task_status(task_id, "failed", str(e)[:500])
        print(f"[Heartbeat] Task {task_id} failed: {e}")
