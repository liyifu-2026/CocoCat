"""DAG tools — define, append, update, dispatch, check, stop."""
import os
import uuid

import yaml

from cococat.dag.store import DagStore
from cococat.core.types import ToolContext


def _resolve(ctx) -> ToolContext:
    return ToolContext.from_dict(ctx)


def _define_dag(yaml_str: str, ctx: ToolContext) -> str:
    ctx = _resolve(ctx)
    if not yaml_str:
        return "Error: 'yaml' is required"
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        return f"Error parsing YAML: {e}"

    store = ctx.dag.store
    if store is None:
        return "Error: dag_store not configured"

    run_id = uuid.uuid4().hex[:12]
    data["run_id"] = run_id
    data.setdefault("created_by", "main")
    data.setdefault("status", "running")
    if ctx.session_id:
        data["session_id"] = ctx.session_id
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
    ctx = _resolve(ctx)
    if not run_id:
        return "Error: 'run_id' is required"
    if not stage_yaml:
        return "Error: 'stage_yaml' is required"

    store = ctx.dag.store
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
    ctx = _resolve(ctx)
    if not run_id:
        return "Error: 'run_id' is required"
    if not path:
        return "Error: 'path' is required"
    if not value:
        return "Error: 'value' is required"

    store = ctx.dag.store
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


async def _dispatch_task(run_id: str, task_id: str, prompt: str, ctx: ToolContext, title: str | None = None) -> str:
    ctx = _resolve(ctx)
    if not run_id:
        return "Error: 'run_id' is required"
    if not task_id:
        return "Error: 'task_id' is required"
    if not prompt:
        return "Error: 'prompt' is required"

    store = ctx.dag.store
    if store is None:
        return "Error: dag_store not configured"

    executor = ctx.dag.executor
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
    if title:
        task_node["title"] = title
    _save_dag(run_id, data, store)

    display = title or task_id
    return f"Task '{display}' dispatched in run '{run_id}' — will execute in background"


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
    ctx = _resolve(ctx)
    store = ctx.dag.store
    if store is not None:
        return _check_dag_tasks(store)
    return "No pending tasks"


def _stop_task(task_id: str, ctx: ToolContext) -> str:
    ctx = _resolve(ctx)
    if not task_id:
        return "Error: 'task_id' is required"
    cancel_dir = ctx.dag.cancel_dir
    try:
        os.makedirs(cancel_dir, exist_ok=True)
        marker = os.path.join(cancel_dir, f"{task_id}.cancel")
        import json
        with open(marker, "w") as f:
            json.dump({"task_id": task_id, "cancelled_at": str(__import__("datetime").datetime.now())}, f)
        return f"Cancellation requested for task '{task_id}'"
    except Exception as e:
        return f"Error cancelling task: {e}"


def make_dag_tools(dag_store=None, sub_agent_executor=None) -> list:
    from cococat.core.tools.types import Tool, _merge_ctx, _ensure_tool_context
    from cococat.core.types import DagEnv
    return [
        Tool(name="define_dag", description="Define a DAG task graph",
             parameters={"yaml": "string"},
             execute=lambda p, ctx: _define_dag(p.get("yaml", ""), _merge_ctx(ctx, dag=DagEnv(store=dag_store)))),
        Tool(name="append_stage", description="Append a stage to an existing DAG run",
             parameters={"run_id": "string", "stage_yaml": "string"},
             execute=lambda p, ctx: _append_stage(p.get("run_id", ""), p.get("stage_yaml", ""), _merge_ctx(ctx, dag=DagEnv(store=dag_store)))),
        Tool(name="update_dag", description="Update a node in dag.yaml by dot-path",
             parameters={"run_id": "string", "path": "string", "value": "string"},
             execute=lambda p, ctx: _update_dag(p.get("run_id", ""), p.get("path", ""), p.get("value", ""), _merge_ctx(ctx, dag=DagEnv(store=dag_store)))),
        Tool(name="dispatch_task", description="Dispatch a task in a DAG run",
             parameters={"run_id": "string", "task_id": "string", "prompt": "string", "title": "string"},
             execute=lambda p, ctx: _dispatch_task(p.get("run_id", ""), p.get("task_id", ""), p.get("prompt", ""),
                 _merge_ctx(ctx, dag=DagEnv(store=dag_store, executor=sub_agent_executor)), p.get("title"))),
        Tool(name="check_tasks", description="Check pending task status",
             parameters={},
             execute=lambda p, ctx: _check_tasks(_merge_ctx(ctx, dag=DagEnv(store=dag_store)))),
        Tool(name="stop_task", description="Cancel a running task",
             parameters={"task_id": "string"},
             execute=lambda p, ctx: _stop_task(p.get("task_id", ""), _ensure_tool_context(ctx))),
    ]
