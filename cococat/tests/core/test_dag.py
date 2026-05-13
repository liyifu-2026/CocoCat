"""Test DAG tools — define_dag, append_stage, dispatch_task, update_dag."""
import os
import yaml
import pytest
from cococat.core.tools import create_core_tools, ToolRegistry


class TestDefineDag:
    @pytest.mark.asyncio
    async def test_creates_run_directory_and_returns_run_id(self, tmp_path):
        """When define_dag is called, it creates runs/{run_id}/dag.yaml and returns run_id."""
        dag_dir = str(tmp_path / "runs")
        tools = create_core_tools(dag_dir=dag_dir)
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

        # Returns run_id
        assert result is not None
        run_id = result.strip()
        assert len(run_id) > 0

        # dag.yaml was created
        dag_path = os.path.join(dag_dir, run_id, "dag.yaml")
        assert os.path.exists(dag_path)

        # Verify content
        with open(dag_path) as f:
            data = yaml.safe_load(f)
        assert data["status"] == "running"
        assert len(data["stages"]) == 1
        assert data["stages"][0]["id"] == "coding"

    @pytest.mark.asyncio
    async def test_requires_yaml_parameter(self):
        """define_dag without yaml parameter returns error."""
        tools = create_core_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("define_dag", {})
        assert "Error" in result or "yaml" in result.lower()


class TestAppendStage:
    @pytest.mark.asyncio
    async def test_appends_stage_to_existing_dag(self, tmp_path):
        """append_stage adds a new stage to an existing DAG run."""
        dag_dir = str(tmp_path / "runs")
        tools = create_core_tools(dag_dir=dag_dir)
        reg = ToolRegistry(tools)

        # Create a DAG first
        run_id = await reg.execute("define_dag", {"yaml": """
stages:
  - id: coding
    name: 编码
    parallel: true
    tasks:
      - id: code-a
"""})

        # Append a new stage
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

        # Verify the DAG now has 2 stages
        dag_path = os.path.join(dag_dir, run_id.strip(), "dag.yaml")
        with open(dag_path) as f:
            data = yaml.safe_load(f)
        assert len(data["stages"]) == 2
        assert data["stages"][1]["id"] == "review"

    @pytest.mark.asyncio
    async def test_append_stage_missing_params(self):
        """append_stage without required params returns error."""
        tools = create_core_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("append_stage", {})
        assert "error" in result.lower()


class TestUpdateDag:
    @pytest.mark.asyncio
    async def test_updates_task_status_in_dag(self, tmp_path):
        """update_dag modifies a node in dag.yaml."""
        dag_dir = str(tmp_path / "runs")
        tools = create_core_tools(dag_dir=dag_dir)
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

        # Verify the change
        dag_path = os.path.join(dag_dir, run_id.strip(), "dag.yaml")
        with open(dag_path) as f:
            data = yaml.safe_load(f)
        assert data["stages"][0]["tasks"][0]["status"] == "done"

    @pytest.mark.asyncio
    async def test_update_dag_missing_params(self):
        """update_dag without required params returns error."""
        tools = create_core_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("update_dag", {})
        assert "error" in result.lower()


class TestDispatchTask:
    @pytest.mark.asyncio
    async def test_dispatches_and_updates_task_status(self, tmp_path):
        """dispatch_task calls the executor and updates task status to done."""
        dag_dir = str(tmp_path / "runs")
        dispatched = {}

        async def mock_executor(task: str, agent_id: str) -> str:
            dispatched["task"] = task
            dispatched["agent_id"] = agent_id
            return "task result here"

        tools = create_core_tools(dag_dir=dag_dir, sub_agent_executor=mock_executor)
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

        assert "completed" in result.lower()
        assert dispatched["task"] == "write a function"
        assert dispatched["agent_id"] == "code-a"

        # Verify task status is "done" in dag.yaml
        dag_path = os.path.join(dag_dir, run_id.strip(), "dag.yaml")
        with open(dag_path) as f:
            data = yaml.safe_load(f)
        task = data["stages"][0]["tasks"][0]
        assert task["id"] == "code-a"
        assert task["status"] == "done"
        assert task["result"] == "task result here"

    @pytest.mark.asyncio
    async def test_dispatches_returns_error_when_no_executor(self, tmp_path):
        """dispatch_task without sub_agent_executor returns error."""
        dag_dir = str(tmp_path / "runs")
        tools = create_core_tools(dag_dir=dag_dir)
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
        """dispatch_task without required params returns error."""
        tools = create_core_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("dispatch_task", {})
        assert "error" in result.lower()


class TestCheckTasksDag:
    @pytest.mark.asyncio
    async def test_check_tasks_finds_dag_tasks(self, tmp_path):
        """check_tasks returns task status from DAG runs."""
        dag_dir = str(tmp_path / "runs")

        async def mock_executor(task: str, agent_id: str) -> str:
            return "result"

        tools = create_core_tools(dag_dir=dag_dir, sub_agent_executor=mock_executor)
        reg = ToolRegistry(tools)

        # Create a DAG run with one completed task
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

        result = await reg.execute("check_tasks", {}, {"dag_dir": dag_dir})
        assert "code-a" in result
        assert "done" in result.lower()

    @pytest.mark.asyncio
    async def test_check_tasks_no_runs(self, tmp_path):
        """check_tasks with no runs returns empty status."""
        dag_dir = str(tmp_path / "runs")
        tools = create_core_tools(dag_dir=dag_dir)
        reg = ToolRegistry(tools)

        # No DAG runs exist yet
        result = await reg.execute("check_tasks", {}, {"dag_dir": dag_dir})
        # Should not crash
        assert isinstance(result, str)
