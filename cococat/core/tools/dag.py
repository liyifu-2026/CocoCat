"""DAG tools — define, append, update, dispatch, check, stop."""
import os
import uuid

import yaml


def _define_dag(yaml_str: str, ctx: dict) -> str:
    if not yaml_str:
        return "Error: 'yaml' is required"
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        return f"Error parsing YAML: {e}"

    dag_dir = ctx.get("dag_dir", "runs")
    run_id = uuid.uuid4().hex[:12]
    run_dir = os.path.join(dag_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)

    data["run_id"] = run_id
    data.setdefault("created_by", "main")
    data.setdefault("status", "running")
    for stage in data.get("stages", []):
        for task in stage.get("tasks", []):
            task.setdefault("status", "pending")

    dag_path = os.path.join(run_dir, "dag.yaml")
    with open(dag_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    return run_id


def _load_dag(run_id: str, dag_dir: str) -> tuple[dict | None, str | None]:
    dag_path = os.path.join(dag_dir, run_id, "dag.yaml")
    if not os.path.exists(dag_path):
        return None, f"Error: run '{run_id}' not found"
    try:
        with open(dag_path, encoding="utf-8") as f:
            return yaml.safe_load(f), None
    except yaml.YAMLError as e:
        return None, f"Error reading dag.yaml: {e}"


def _save_dag(run_id: str, data: dict, dag_dir: str) -> None:
    dag_path = os.path.join(dag_dir, run_id, "dag.yaml")
    with open(dag_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def _append_stage(run_id: str, stage_yaml: str, ctx: dict) -> str:
    if not run_id:
        return "Error: 'run_id' is required"
    if not stage_yaml:
        return "Error: 'stage_yaml' is required"

    dag_dir = ctx.get("dag_dir", "runs")
    data, err = _load_dag(run_id, dag_dir)
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
    _save_dag(run_id, data, dag_dir)
    return f"Appended stage '{stage.get('id', '?')}' to run '{run_id}'"


def _update_dag(run_id: str, path: str, value: str, ctx: dict) -> str:
    if not run_id:
        return "Error: 'run_id' is required"
    if not path:
        return "Error: 'path' is required"
    if not value:
        return "Error: 'value' is required"

    dag_dir = ctx.get("dag_dir", "runs")
    data, err = _load_dag(run_id, dag_dir)
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

    _save_dag(run_id, data, dag_dir)
    return f"Updated '{path}' to '{value}' in run '{run_id}'"


async def _dispatch_task(run_id: str, task_id: str, prompt: str, ctx: dict) -> str:
    if not run_id:
        return "Error: 'run_id' is required"
    if not task_id:
        return "Error: 'task_id' is required"
    if not prompt:
        return "Error: 'prompt' is required"

    dag_dir = ctx.get("dag_dir", "runs")
    executor = ctx.get("sub_agent_executor")

    if not executor:
        return "Error: sub_agent_executor not configured — dispatch_task requires a running agent system"

    data, err = _load_dag(run_id, dag_dir)
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

    task_node["status"] = "running"
    _save_dag(run_id, data, dag_dir)

    try:
        result = await executor(prompt, task_id)
    except Exception as e:
        task_node["status"] = "failed"
        task_node["error"] = str(e)
        _save_dag(run_id, data, dag_dir)
        return f"Error dispatching task '{task_id}': {e}"

    task_node["status"] = "done"
    task_node["result"] = result
    _save_dag(run_id, data, dag_dir)

    return f"Task '{task_id}' completed in run '{run_id}'"


def _check_tasks(ctx: dict) -> str:
    dag_dir = ctx.get("dag_dir")
    if dag_dir and os.path.isdir(dag_dir):
        return _check_dag_tasks(dag_dir)

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


def _check_dag_tasks(dag_dir: str) -> str:
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
                entries.append(f"    {tid}: {tstatus}")

    if not entries:
        return "No pending tasks"
    return "\n".join(entries)


def _stop_task(task_id: str, ctx: dict) -> str:
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
