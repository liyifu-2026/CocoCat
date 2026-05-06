"""Heartbeat service: consume bus events, check schedule, execute pending tasks."""
import os
import json
import sys
import time
import threading

_heartbeat_running = False
_heartbeat_lock = threading.Lock()


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


def start_heartbeat(agent_id: str, agent_name: str, interval: int = 300, scene: str = "default", bus=None):
    thread = threading.Thread(
        target=_heartbeat_loop, args=(agent_id, agent_name, interval, scene, bus), daemon=True
    )
    thread.start()
    return thread


def _heartbeat_loop(agent_id: str, agent_name: str, interval: int, scene: str = "default", bus=None):
    global _heartbeat_running
    if _heartbeat_running:
        return
    _heartbeat_running = True
    try:
        from agent_runner import AgentRunner
        runner = AgentRunner(agent_id, agent_name, scene, bus=bus)

        while True:
            # Wait for bus events (with interval timeout for schedule checks)
            if bus is not None:
                msg = bus.wait_for_inbound(timeout=interval)
                if msg is not None:
                    from message import InboundMessage
                    if isinstance(msg, InboundMessage) and msg.agent_id == agent_id:
                        prompt = msg.content
                        _execute_task(agent_id, agent_name, {"id": f"{msg.channel}_{msg.source}", "task": prompt}, scene=scene, runner=runner)
                        continue
            else:
                time.sleep(interval)

            # Status report
            try:
                from agent_status import report as _sreport
                _sreport(agent_id, "alive", f"heartbeat {agent_name}")
            except Exception:
                pass

            # Fallback: drain any bus messages that arrived during processing
            if bus is not None:
                for msg in bus.drain_inbound():
                    if msg.agent_id == agent_id:
                        prompt = msg.content
                        _execute_task(agent_id, agent_name, {"id": f"{msg.channel}_{msg.source}", "task": prompt}, scene=scene, runner=runner)

            # Schedule check
            try:
                tasks = get_pending_tasks(agent_id)
                if tasks:
                    print(f"[Heartbeat] {agent_name} found {len(tasks)} pending task(s)", file=sys.stderr)
                    for task in tasks:
                        _execute_task(agent_id, agent_name, task, scene=scene, runner=runner)
            except Exception as e:
                print(f"[Heartbeat] Error: {e}", file=sys.stderr)

            try:
                from auto_compact import run_auto_compact
                run_auto_compact(agent_id)
            except Exception:
                pass
    finally:
        _heartbeat_running = False


def _execute_task(agent_id: str, agent_name: str, task: dict, scene: str = "default", runner=None):
    from agent_runner import AgentRunner

    task_id = task.get("id")
    prompt = task.get("task", "")
    if not prompt:
        update_task_status(task_id, "failed", "No task description")
        return

    if runner is None:
        runner = AgentRunner(agent_id, agent_name, scene, bus=bus)

    try:
        result = runner.run(prompt)
        content = result.get("content", "")
        update_task_status(task_id, "completed", content[:500])
        print(f"[Heartbeat] Task {task_id} completed", file=sys.stderr)
    except Exception as e:
        update_task_status(task_id, "failed", str(e)[:500])
        print(f"[Heartbeat] Task {task_id} failed: {e}", file=sys.stderr)
