"""Integration test: complex DAG with multiple sub-agents via Main AI tools.

Simulates Main AI orchestrating a multi-stage DAG, dispatching tasks to
sub-agents, and verifying the full chain: define_dag → dispatch_task → 
sub-agent execution → DAG status tracking → check_tasks.

No real LLM required — sub-agents use StubLLM, Main AI tools are invoked
directly (simulating what the LLM would do).
"""
import pytest
from cococat.core.sub_agent import SubAgentExecutor
from cococat.core.event_bus import EventBus
from cococat.dag.store import FileDagStore
from cococat.providers.base import LLMResponse


class StubLLM:
    """Returns a fixed result for sub-agent tasks."""
    def __init__(self, response="done"):
        self._response = response
        self.calls = []

    async def chat(self, messages, tools=None, **kwargs):
        self.calls.append(messages)
        return LLMResponse(content=self._response)


class StubLLMFactory:
    """Creates StubLLMs that return task-specific responses."""
    def __init__(self):
        self.llms = {}

    def get(self, agent_id):
        if agent_id not in self.llms:
            self.llms[agent_id] = StubLLM(f"[{agent_id}] completed task")
        return self.llms[agent_id]


@pytest.fixture
def dag_env(tmp_path):
    """Set up a DAG environment with sub-agent executor."""
    dag_dir = str(tmp_path / "runs")
    store = FileDagStore(dag_dir)
    bus = EventBus()
    llm_factory = StubLLMFactory()

    executor = SubAgentExecutor(bus=bus, pool=None, sandbox_provider=None)
    executor._stub_llm_factory = llm_factory

    return {
        "dag_store": store,
        "dag_dir": dag_dir,
        "bus": bus,
        "executor": executor,
        "llm_factory": llm_factory,
        "tmp_path": tmp_path,
    }


class TestComplexDAG:
    """Full DAG lifecycle: 2 stages, 3 tasks, cross-stage dependencies."""

    @pytest.mark.asyncio
    async def test_define_and_execute_multi_stage_dag(self, dag_env):
        """Main AI defines a 2-stage DAG with 3 tasks, dispatches all."""
        store = dag_env["dag_store"]

        # ── Stage 1: define DAG ──
        from cococat.core.tools.dag import _define_dag
        dag_yaml = """
stages:
  - id: analysis
    tasks:
      - id: analyze-code
        description: Analyze codebase structure
      - id: analyze-deps
        description: Analyze dependencies
  - id: implementation
    tasks:
      - id: write-report
        description: Write final report
"""
        run_id = _define_dag(dag_yaml, {"dag_store": store})
        assert run_id

        # ── Stage 2: dispatch all tasks (fire-and-forget) ──
        from cococat.core.tools.dag import _dispatch_task

        executor_fn = dag_env["executor"].dispatch
        base_ctx = {"dag_store": store, "sub_agent_executor": executor_fn}

        with _patch_executor(dag_env):
            r1 = await _dispatch_task(run_id, "analyze-code", "analyze the codebase", base_ctx)
            assert "dispatched" in r1.lower()

            r2 = await _dispatch_task(run_id, "analyze-deps", "analyze deps", base_ctx)
            assert "dispatched" in r2.lower()

            r3 = await _dispatch_task(run_id, "write-report", "write report", base_ctx)
            assert "dispatched" in r3.lower()

        # ── Stage 2b: TaskWorker picks up and executes pending tasks ──
        from cococat.dag import execute_pending_dag_task
        with _patch_executor(dag_env):
            for _ in range(3):
                await execute_pending_dag_task(store, executor_fn)

        # ── Stage 3: verify DAG status ──
        from cococat.core.tools.dag import _check_dag_tasks
        status = _check_dag_tasks(store)

        assert "analysis" in status
        assert "implementation" in status
        assert "done" in status
        assert "analyze-code" in status
        assert "analyze-deps" in status
        assert "write-report" in status

        # ── Stage 4: verify dag.yaml contains results ──
        data = store.load(run_id)
        assert data["run_id"] == run_id
        for stage in data["stages"]:
            for task in stage["tasks"]:
                assert task["status"] == "done"
                assert "result" in task
                assert "completed" in task["result"]

    @pytest.mark.asyncio
    async def test_dag_failure_propagation(self, dag_env):
        """When a task fails, it should be marked 'failed' with error info."""
        from cococat.core.tools.dag import _define_dag, _dispatch_task
        store = dag_env["dag_store"]

        run_id = _define_dag("""
stages:
  - id: test-stage
    tasks:
      - id: failing-task
        description: This task will fail
""", {"dag_store": store})

        async def failing_executor(task, agent_id, session_id=None):
            raise RuntimeError("simulated failure")

        ctx = {"dag_store": store, "sub_agent_executor": failing_executor}
        result = await _dispatch_task(run_id, "failing-task", "do it", ctx)
        assert "dispatched" in result.lower()

        from cococat.dag import execute_pending_dag_task
        await execute_pending_dag_task(store, failing_executor)
        data = store.load(run_id)
        task = data["stages"][0]["tasks"][0]
        assert task["status"] == "failed"
        assert "simulated failure" in task["error"]

    @pytest.mark.asyncio
    async def test_check_tasks_aggregates_across_runs(self, dag_env):
        """check_tasks() should report status across all DAG runs."""
        from cococat.core.tools.dag import _define_dag, _dispatch_task, _check_dag_tasks
        store = dag_env["dag_store"]

        r1 = _define_dag("stages: [{id: s1, tasks: [{id: t1, description: x}]}]", {"dag_store": store})
        r2 = _define_dag("stages: [{id: s2, tasks: [{id: t2, description: y}]}]", {"dag_store": store})

        ctx = {"dag_store": store, "sub_agent_executor": dag_env["executor"].dispatch}
        with _patch_executor(dag_env):
            await _dispatch_task(r1, "t1", "do x", ctx)
            await _dispatch_task(r2, "t2", "do y", ctx)

        from cococat.dag import execute_pending_dag_task
        with _patch_executor(dag_env):
            await execute_pending_dag_task(store, dag_env["executor"].dispatch)
            await execute_pending_dag_task(store, dag_env["executor"].dispatch)

        status = _check_dag_tasks(store)
        assert r1 in status
        assert r2 in status
        assert "done" in status

    @pytest.mark.asyncio
    async def test_parallel_tasks_same_stage(self, dag_env):
        """Tasks in the same stage can be dispatched in parallel (via gather)."""
        import asyncio
        from cococat.core.tools.dag import _define_dag, _dispatch_task
        store = dag_env["dag_store"]

        run_id = _define_dag("""
stages:
  - id: parallel-stage
    tasks:
      - id: task-a
      - id: task-b
      - id: task-c
""", {"dag_store": store})

        ctx = {"dag_store": store, "sub_agent_executor": dag_env["executor"].dispatch}
        with _patch_executor(dag_env):
            results = await asyncio.gather(
                _dispatch_task(run_id, "task-a", "do a", ctx),
                _dispatch_task(run_id, "task-b", "do b", ctx),
                _dispatch_task(run_id, "task-c", "do c", ctx),
            )

        assert len(results) == 3
        for r in results:
            assert "dispatched" in r.lower()

        from cococat.dag import execute_pending_dag_task
        with _patch_executor(dag_env):
            for _ in range(3):
                await execute_pending_dag_task(store, dag_env["executor"].dispatch)


class _patch_executor:
    """Context manager that patches SubAgentExecutor.dispatch to use stub LLMs."""

    def __init__(self, dag_env):
        self._dag_env = dag_env
        self._original = None

    def __enter__(self):
        from cococat.core.sandbox import SandboxProvider, LocalExecutor
        llm_factory = self._dag_env["llm_factory"]
        executor = self._dag_env["executor"]
        
        local = LocalExecutor(get_llm=lambda aid: llm_factory.get(aid))
        sbx = SandboxProvider(executor=local)
        self._original = executor._sandbox
        executor._sandbox = sbx
        return self

    def __exit__(self, *args):
        self._dag_env["executor"]._sandbox = self._original
