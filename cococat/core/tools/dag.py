"""DAG tools — define, append, update, dispatch, check, stop."""
import os
import uuid

import yaml

from cococat.core.dag_store import DagStore
from cococat.core.types import ToolContext


def _define_dag(yaml_str: str, ctx: ToolContext) -> str:
    if not yaml_str:
        return "Error: 'yaml' is required"
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        return f"Error parsing YAML: {e}"

    store = ctx.get("dag_store")
    if store is None:
        return "Error: dag_store not configured"

    run_id = uuid.uuid4().hex[:12]
    data["run_id"] = run_id
    data.setdefault("created_by", "main")
    data.setdefault("status", "running")
    if ctx.get("session_id"):
        data["session_id"] = ctx["session_id"]
    for stage in data.get("stages", []):
        for task in stage.get("tasks", []):
            task.setdefault("status", "pending")

    store.save(run_id, data)
    return run_id


def _load_dag(run_id: str, store: DagStore) -> tuple[dict | None, str | None]:
    data = store.load(run_id)
    if data is None:
        return None, f"Error: run '{run_id}' not found"
    return data, None


def _save_dag(run_id: str, data: dict, store: DagStore) -> None:
    store.save(run_id, data)


def _append_stage(run_id: str, stage_yaml: str, ctx: ToolContext) -> str:
    if not run_id:
        return "Error: 'run_id' is required"
    if not stage_yaml:
        return "Error: 'stage_yaml' is required"

    store = ctx.get("dag_store")
    if store is None:
        return "Error: dag_store not configured"

    data, err = _load_dag(run_id, store)
    if err:
        return err

    try:
        stage = yaml.safe_load(stage_yaml)
    except yaml.YAMLError as e:
        return f"Error parsing stage_yaml: {e}"

    stage.setdefault("status", "pending")
    for task in stage.get("tasks", []):
        task.setdefault("status", "pending")

    data.setdefault("stages", []).append(stage)
    _save_dag(run_id, data, store)
    return f"Appended stage '{stage.get('id', '?')}' to run '{run_id}'"


def _update_dag(run_id: str, path: str, value: str, ctx: ToolContext) -> str:
    if not run_id:
        return "Error: 'run_id' is required"
    if not path:
        return "Error: 'path' is required"
    if not value:
        return "Error: 'value' is required"

    store = ctx.get("dag_store")
    if store is None:
        return "Error: dag_store not configured"

    data, err = _load_dag(run_id, store)
    if err:
        return err

    parts = path.split(".")
    node = data
    for i, key in enumerate(parts[:-1]):
        idx = int(key) if key.isdigit() else key
        try:
            node = node[idx]
        except (KeyError, IndexError, TypeError):
            return f"Error: path '{path}' not found at segment '{key}'"

    final_key = parts[-1]
    final_idx = int(final_key) if final_key.isdigit() else final_key
    if value.isdigit():
        parsed_value = int(value)
    elif value.lower() in ("true", "false"):
        parsed_value = value.lower() == "true"
    else:
        parsed_value = value

    try:
        node[final_idx] = parsed_value
    except (KeyError, IndexError, TypeError):
        return f"Error: path '{path}' not found at final segment '{final_key}'"

    _save_dag(run_id, data, store)
    return f"Updated '{path}' to '{value}' in run '{run_id}'"


async def _dispatch_task(run_id: str, task_id: str, prompt: str, ctx: ToolContext) -> str:
    if not run_id:
        return "Error: 'run_id' is required"
    if not task_id:
        return "Error: 'task_id' is required"
    if not prompt:
        return "Error: 'prompt' is required"

    store = ctx.get("dag_store")
    if store is None:
        return "Error: dag_store not configured"

    executor = ctx.get("sub_agent_executor")
    if not executor:
        return "Error: sub_agent_executor not configured"

    data, err = _load_dag(run_id, store)
    if err:
        return err

    task_node = None
    for stage in data.get("stages", []):
        for task in stage.get("tasks", []):
            if task.get("id") == task_id:
                task_node = task
                break
        if task_node:
            break

    if task_node is None:
        return f"Error: task '{task_id}' not found in run '{run_id}'"

    task_node["status"] = "pending"
    task_node["prompt"] = prompt
    _save_dag(run_id, data, store)

    return f"Task '{task_id}' dispatched in run '{run_id}' — will execute in background"


async def _execute_pending_dag_task(store: DagStore, executor: callable) -> int:
    """Find and execute one pending task in DAG. Returns 1 if executed, 0 if none."""
    pending = store.get_pending_task()
    if pending is None:
        return 0

    run_id = pending["run_id"]
    data = pending["data"]
    task_id = pending["task_id"]
    prompt = pending["prompt"]
    dag_session_id = pending["session_id"]

    for stage in data.get("stages", []):
        for task in stage.get("tasks", []):
            if task.get("id") == task_id:
                task["status"] = "running"
                store.save(run_id, data)
                break

    try:
        result = await executor(prompt, task_id, dag_session_id)
        for stage in data.get("stages", []):
            for task in stage.get("tasks", []):
                if task.get("id") == task_id:
                    task["status"] = "done"
                    task["result"] = str(result) if result else "(no output)"
    except Exception as e:
        for stage in data.get("stages", []):
            for task in stage.get("tasks", []):
                if task.get("id") == task_id:
                    task["status"] = "failed"
                    task["error"] = str(e)

    store.save(run_id, data)
    return 1


def _check_dag_tasks(store: DagStore) -> str:
    entries = []
    for data in store.list_all():
        run_id = data.get("run_id", "?")
        run_status = data.get("status", "?")
        entries.append(f"[{run_id}] run: {run_status}")

        for stage in data.get("stages", []):
            stage_id = stage.get("id", "?")
            stage_status = stage.get("status", "?")
            entries.append(f"  [{stage_id}] stage: {stage_status}")
            for task in stage.get("tasks", []):
                tid = task.get("id", "?")
                tstatus = task.get("status", "?")
                tresult = task.get("result") or ""
                terror = task.get("error") or ""
                line = f"    {tid}: {tstatus}"
                if tresult:
                    line += f" — result: {tresult}"
                if terror:
                    line += f" — error: {terror[:300]}"
                entries.append(line)

    if not entries:
        return "No pending tasks"
    return "\n".join(entries)


def _check_tasks(ctx: ToolContext) -> str:
    store = ctx.get("dag_store")
    if store is not None:
        return _check_dag_tasks(store)

    # Legacy fallback: tasks.json (no dag_store configured)
    dag_dir = ctx.get("dag_dir")
    if dag_dir and os.path.isdir(dag_dir):
        return _check_dag_tasks_via_fs(dag_dir)

    tasks_path = ctx.get("tasks_path", "runs")
    tasks_file = os.path.join(tasks_path, "tasks.json")
    if not os.path.exists(tasks_file):
        return "No pending tasks"
    try:
        import json
        tasks = json.load(open(tasks_file))
        if not tasks:
            return "No pending tasks"
        lines = [f"{t.get('id', '?')}: {t.get('status', 'unknown')} — {t.get('description', '')}" for t in tasks]
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading tasks: {e}"


def _check_dag_tasks_via_fs(dag_dir: str) -> str:
    """Fallback: scan dag_dir directly when no store is available."""
    if not os.path.isdir(dag_dir):
        return "No pending tasks"

    entries = []
    for run_dir in sorted(os.listdir(dag_dir)):
        dag_path = os.path.join(dag_dir, run_dir, "dag.yaml")
        if not os.path.exists(dag_path):
            continue
        try:
            with open(dag_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError):
            continue

        run_id = data.get("run_id", run_dir)
        run_status = data.get("status", "?")
        entries.append(f"[{run_id}] run: {run_status}")

        for stage in data.get("stages", []):
            stage_id = stage.get("id", "?")
            stage_status = stage.get("status", "?")
            entries.append(f"  [{stage_id}] stage: {stage_status}")
            for task in stage.get("tasks", []):
                tid = task.get("id", "?")
                tstatus = task.get("status", "?")
                tresult = task.get("result") or ""
                terror = task.get("error") or ""
                line = f"    {tid}: {tstatus}"
                if tresult:
                    line += f" — result: {tresult}"
                if terror:
                    line += f" — error: {terror[:300]}"
                entries.append(line)

    if not entries:
        return "No pending tasks"
    return "\n".join(entries)


def _stop_task(task_id: str, ctx: ToolContext) -> str:
    if not task_id:
        return "Error: 'task_id' is required"
    cancel_dir = ctx.get("cancel_dir", "runs/cancellations")
    try:
        os.makedirs(cancel_dir, exist_ok=True)
        marker = os.path.join(cancel_dir, f"{task_id}.cancel")
        import json
        with open(marker, "w") as f:
            json.dump({"task_id": task_id, "cancelled_at": str(__import__("datetime").datetime.now())}, f)
        return f"Cancellation requested for task '{task_id}'"
    except Exception as e:
        return f"Error cancelling task: {e}"
