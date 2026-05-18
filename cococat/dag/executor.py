"""DAG task executor — find and execute pending tasks."""
from __future__ import annotations
import logging
from cococat.dag.store import DagStore

logger = logging.getLogger("cococat.dag")


async def execute_pending_dag_task(store: DagStore, executor: callable) -> int:
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
