"""Test CubeSandbox integration — sandbox_run wired into bash tool."""
import pytest
from cococat.core.tools.execution import make_execution_tools
from cococat.core.tools.file_ops import make_readonly_file_tools


def _create_tools(sandbox_run=None):
    return list(make_execution_tools(sandbox_run).values()) + list(make_readonly_file_tools().values())


class TestCubeSandboxIntegration:
    """Verify sandbox_run is passed through to bash tool."""

    @pytest.mark.asyncio
    async def test_bash_with_sandbox_run(self):
        calls = []

        async def fake_sandbox_run(code: str) -> str:
            calls.append(code)
            return "sandbox output: ok"

        tools = _create_tools(sandbox_run=fake_sandbox_run)
        bash_tool = next(t for t in tools if t["name"] == "bash")

        result = await bash_tool["execute"]({"command": "echo hello"}, {})

        assert len(calls) == 1
        assert "subprocess.run" in calls[0]
        assert result == "sandbox output: ok"

    @pytest.mark.asyncio
    async def test_bash_without_sandbox_run(self):
        tools = _create_tools(sandbox_run=None)
        bash_tool = next(t for t in tools if t["name"] == "bash")

        result = await bash_tool["execute"]({"command": "echo hello"}, {})

        assert "hello" in result or result == "(no output)" or "Error" not in result

    @pytest.mark.asyncio
    async def test_sandbox_run_not_passed_to_other_tools(self):
        calls = []

        async def fake_sandbox_run(code: str) -> str:
            calls.append(code)
            return "ok"

        tools = _create_tools(sandbox_run=fake_sandbox_run)
        read_tool = next(t for t in tools if t["name"] == "read_file")

        result = read_tool["execute"]({"path": "/nonexistent"}, {})
        # Should not call sandbox_run for read_file
        assert len(calls) == 0


class TestInProcessExecutorWithSandboxRun:
    """Verify InProcessExecutor accepts sandbox_run."""

    @pytest.mark.asyncio
    async def test_local_executor_accepts_sandbox_run(self):
        from cococat.core.sandbox import InProcessExecutor, Sandbox

        sandbox_calls = []

        async def sb_run(code: str) -> str:
            sandbox_calls.append(code)
            return "ok"

        executor = InProcessExecutor(sandbox_run=sb_run)
        assert executor._sandbox_run is sb_run

        sandbox = Sandbox(id="test-1", template="default", permissions={})
        result = await executor.run(sandbox, "say hi", agent_id="test-agent")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_sandbox_provider_with_custom_executor(self):
        from cococat.core.sandbox import ExecutorProvider, InProcessExecutor

        async def sb_run(code: str) -> str:
            return "sandbox: ok"

        executor = InProcessExecutor(sandbox_run=sb_run)
        provider = ExecutorProvider(executor=executor)
        assert provider._executor is executor
        assert provider._executor._sandbox_run is sb_run


class TestCubeSandboxExecutorInterface:
    """Verify CubeSandboxExecutor matches Executor interface."""

    @pytest.mark.asyncio
    async def test_cubesandbox_executor_has_required_methods(self):
        from cococat.core.sandbox.cubesandbox import CubeSandboxExecutor
        cube = CubeSandboxExecutor()

        assert hasattr(cube, "create")
        assert hasattr(cube, "run")
        assert hasattr(cube, "destroy")
