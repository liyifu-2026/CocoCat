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


def start_heartbeat(agent_id: str, agent_name: str, interval: int = 300, scene: str = "default"):
    thread = threading.Thread(target=_heartbeat_loop, args=(agent_id, agent_name, interval, scene), daemon=True)
    thread.start()
    return thread


def _heartbeat_loop(agent_id: str, agent_name: str, interval: int, scene: str = "default"):
    while True:
        time.sleep(interval)
        try:
            from mailbox import read_inbox, mark_read
            messages = read_inbox(agent_id)
            unread = [m for m in messages if m.get("status") == "unread"]
            if unread:
                print(f"[Mailbox] {agent_name} has {len(unread)} unread message(s)")
                for i, msg in enumerate(messages):
                    if msg.get("status") == "unread":
                        from_prompt = f"[Message from {msg.get('from', 'unknown')}]\n{msg.get('content', '')}"
                        _execute_task(agent_id, agent_name, {"id": i, "task": from_prompt}, scene=scene)
                        mark_read(agent_id, i)
        except Exception as e:
            print(f"[Mailbox] Error: {e}")

        # === Chat group message reading ===
        try:
            from chat_reader import get_unread_messages, mark_as_read
            unread_chat = get_unread_messages(agent_id)
            if unread_chat:
                print(f"[ChatReader] {agent_name} has {len(unread_chat)} unread chat message(s)")
                for item in unread_chat:
                    try:
                        prompt = f"[Chat: {item['group_name']}] [from {item['from']}] (priority: {item['score']})\n{item['content']}"
                        _execute_task(agent_id, agent_name, {"id": f"chat_{item['group_id']}_{item['msg_index']}", "task": prompt}, scene=scene)
                    except Exception as e:
                        print(f"[ChatReader] Failed to process: {e}")
                    mark_as_read(agent_id, item['group_id'], item['msg_index'], item['score'])
        except Exception as e:
            print(f"[ChatReader] Error: {e}")

        try:
            tasks = get_pending_tasks(agent_id)
            if not tasks:
                continue
            print(f"[Heartbeat] {agent_name} found {len(tasks)} pending task(s)")
            for task in tasks:
                _execute_task(agent_id, agent_name, task, scene=scene)
        except Exception as e:
            print(f"[Heartbeat] Error: {e}")

        try:
            from auto_compact import run_auto_compact
            run_auto_compact(agent_id)
        except Exception:
            pass


def _execute_task(agent_id: str, agent_name: str, task: dict, scene: str = "default"):
    from agent_loop import AgentLoop
    from tools import create_default_registry
    from context import load_agent_memory, load_scene_context, load_env_skills

    task_id = task.get("id")
    prompt = task.get("task", "")
    if not prompt:
        update_task_status(task_id, "failed", "No task description")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    agent_runtime_path = os.path.join(script_dir, "agent_runtime.py")
    tools = create_default_registry(agent_runtime_path=agent_runtime_path, agent_id=agent_id)
    scene_name, scene_context = load_scene_context(scene)
    scene_skills = load_env_skills(scene)
    loop = AgentLoop(agent_id=agent_id, agent_name=agent_name, tools=tools,
                     scene_name=scene_name, scene_context=scene_context, scene_skills=scene_skills)

    try:
        result = loop.run(prompt)
        content = result.get("content", "")
        update_task_status(task_id, "completed", content[:500])
        print(f"[Heartbeat] Task {task_id} completed")
    except Exception as e:
        update_task_status(task_id, "failed", str(e)[:500])
        print(f"[Heartbeat] Task {task_id} failed: {e}")
