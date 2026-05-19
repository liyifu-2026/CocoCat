"""Test DAG tools — define_dag, append_stage, dispatch_task, update_dag."""
import pytest
from cococat.core.tools import create_core_tools, ToolRegistry
from cococat.dag.store import FileDagStore


def _dag_store(tmp_path):
    return FileDagStore(str(tmp_path / "runs"))


class TestDefineDag:
    @pytest.mark.asyncio
    async def test_creates_run_directory_and_returns_run_id(self, tmp_path):
        store = _dag_store(tmp_path)
        tools = create_core_tools(dag_store=store)
        reg = ToolRegistry(tools)

        dag_yaml = """
stages:
  - id: coding
    name: 并行编码
    parallel: true
    depends_on: []
    tasks:
      - id: code-a
        description: Write module A
"""
        result = await reg.execute("define_dag", {"yaml": dag_yaml})

        assert result is not None
        run_id = result.strip()
        assert len(run_id) > 0

        data = store.load(run_id)
        assert data is not None
        assert data["status"] == "running"
        assert len(data["stages"]) == 1
        assert data["stages"][0]["id"] == "coding"

    @pytest.mark.asyncio
    async def test_requires_yaml_parameter(self):
        tools = create_core_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("define_dag", {})
        assert "Error" in result or "yaml" in result.lower()


class TestAppendStage:
    @pytest.mark.asyncio
    async def test_appends_stage_to_existing_dag(self, tmp_path):
        store = _dag_store(tmp_path)
        tools = create_core_tools(dag_store=store)
        reg = ToolRegistry(tools)

        run_id = await reg.execute("define_dag", {"yaml": """
stages:
  - id: coding
    name: 编码
    parallel: true
    tasks:
      - id: code-a
"""})

        stage_yaml = """
id: review
name: 审查
parallel: true
depends_on:
  - coding
tasks:
  - id: review-a
"""
        result = await reg.execute("append_stage", {
            "run_id": run_id.strip(),
            "stage_yaml": stage_yaml,
        })

        assert "appended" in result.lower()

        data = store.load(run_id.strip())
        assert len(data["stages"]) == 2
        assert data["stages"][1]["id"] == "review"

    @pytest.mark.asyncio
    async def test_append_stage_missing_params(self):
        tools = create_core_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("append_stage", {})
        assert "error" in result.lower()


class TestUpdateDag:
    @pytest.mark.asyncio
    async def test_updates_task_status_in_dag(self, tmp_path):
        store = _dag_store(tmp_path)
        tools = create_core_tools(dag_store=store)
        reg = ToolRegistry(tools)

        run_id = await reg.execute("define_dag", {"yaml": """
stages:
  - id: coding
    name: 编码
    tasks:
      - id: code-a
"""})

        result = await reg.execute("update_dag", {
            "run_id": run_id.strip(),
            "path": "stages.0.tasks.0.status",
            "value": "done",
        })

        assert "updated" in result.lower()

        data = store.load(run_id.strip())
        assert data["stages"][0]["tasks"][0]["status"] == "done"

    @pytest.mark.asyncio
    async def test_update_dag_missing_params(self):
        tools = create_core_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("update_dag", {})
        assert "error" in result.lower()


class TestDispatchTask:
    @pytest.mark.asyncio
    async def test_dispatches_and_updates_task_status(self, tmp_path):
        store = _dag_store(tmp_path)

        async def mock_executor(task: str, agent_id: str) -> str:
            return "task result here"

        tools = create_core_tools(dag_store=store, sub_agent_executor=mock_executor)
        reg = ToolRegistry(tools)

        run_id = await reg.execute("define_dag", {"yaml": """
stages:
  - id: coding
    name: 编码
    tasks:
      - id: code-a
"""})

        result = await reg.execute("dispatch_task", {
            "run_id": run_id.strip(),
            "task_id": "code-a",
            "prompt": "write a function",
        })

        assert "dispatched" in result.lower()

        data = store.load(run_id.strip())
        task = data["stages"][0]["tasks"][0]
        assert task["id"] == "code-a"
        assert task["status"] == "pending"
        assert task["prompt"] == "write a function"

    @pytest.mark.asyncio
    async def test_dispatches_returns_error_when_no_executor(self, tmp_path):
        store = _dag_store(tmp_path)
        tools = create_core_tools(dag_store=store)
        reg = ToolRegistry(tools)

        run_id = await reg.execute("define_dag", {"yaml": """
stages:
  - id: coding
    name: 编码
    tasks:
      - id: code-a
"""})

        result = await reg.execute("dispatch_task", {
            "run_id": run_id.strip(),
            "task_id": "code-a",
            "prompt": "hello",
        })

        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_dispatch_missing_params(self):
        tools = create_core_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("dispatch_task", {})
        assert "error" in result.lower()


class TestCheckTasksDag:
    @pytest.mark.asyncio
    async def test_check_tasks_finds_dag_tasks(self, tmp_path):
        store = _dag_store(tmp_path)

        async def mock_executor(task: str, agent_id: str) -> str:
            return "result"

        tools = create_core_tools(dag_store=store, sub_agent_executor=mock_executor)
        reg = ToolRegistry(tools)

        run_id = await reg.execute("define_dag", {"yaml": """
stages:
  - id: coding
    name: 编码
    tasks:
      - id: code-a
"""})

        await reg.execute("dispatch_task", {
            "run_id": run_id.strip(),
            "task_id": "code-a",
            "prompt": "write code",
        })

        result = await reg.execute("check_tasks", {})
        assert "code-a" in result
        assert "pending" in result.lower()

    @pytest.mark.asyncio
    async def test_check_tasks_no_runs(self, tmp_path):
        store = _dag_store(tmp_path)
        tools = create_core_tools(dag_store=store)
        reg = ToolRegistry(tools)

        result = await reg.execute("check_tasks", {})
        assert isinstance(result, str)
