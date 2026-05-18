"""Test fire-and-forget dispatch — _dispatch_task returns immediately, TaskWorker runs later."""
import asyncio
import pytest
from cococat.core.tools.dag import _define_dag, _dispatch_task, _load_dag
from cococat.dag.store import FileDagStore


@pytest.mark.asyncio
async def test_dispatch_fire_and_forget(tmp_path):
    """_dispatch_task marks task as pending, returns immediately."""
    store = FileDagStore(str(tmp_path / "runs"))

    dag_yaml = """
stages:
  - id: s1
    tasks:
      - id: t1
        description: test task
"""
    run_id = _define_dag(dag_yaml, {"dag_store": store})

    call_log = []

    async def stub_executor(prompt: str, agent_id: str, session_id: str | None = None) -> str:
        call_log.append((prompt, agent_id))
        await asyncio.sleep(0.01)
        return "stub result"

    ctx = {"dag_store": store, "sub_agent_executor": stub_executor}
    result = await _dispatch_task(run_id, "t1", "do the thing", ctx)

    assert "dispatched" in result.lower() or "pending" in result.lower()
    assert len(call_log) == 0, "executor called synchronously — should be fire-and-forget"

    data, err = _load_dag(run_id, store)
    assert err is None
    tasks = data["stages"][0]["tasks"]
    assert tasks[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_taskworker_executes_pending_task(tmp_path):
    """TaskWorker finds pending task, executes it via executor, writes result to dag.yaml."""
    store = FileDagStore(str(tmp_path / "runs"))

    dag_yaml = """
stages:
  - id: s1
    tasks:
      - id: t1
        description: test
"""
    run_id = _define_dag(dag_yaml, {"dag_store": store})

    # Mark t1 as pending (as if dispatch_task was called)
    data, err = _load_dag(run_id, store)
    data["stages"][0]["tasks"][0]["status"] = "pending"
    store.save(run_id, data)

    async def stub_executor(prompt: str, agent_id: str, session_id: str | None = None) -> str:
        return f"executed: {prompt}"

    from cococat.dag import execute_pending_dag_task

    count = await execute_pending_dag_task(store, stub_executor)
    assert count >= 1

    data, err = _load_dag(run_id, store)
    assert data["stages"][0]["tasks"][0]["status"] == "done"
    assert "executed" in str(data["stages"][0]["tasks"][0].get("result", ""))
