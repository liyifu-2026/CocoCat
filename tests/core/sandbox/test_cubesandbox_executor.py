"""Test CubeSandboxExecutor — creates Agent, runs ReAct loop in sandbox."""
import pytest
from unittest.mock import patch
from cococat.providers.base import LLMResponse


class StubLLM:
    """LLM that returns a fixed response for agent.run()."""
    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(content="task completed")


class TestCubeSandboxExecutorRun:
    """CubeSandboxExecutor.run() should create Agent, run ReAct, return result."""

    @pytest.mark.asyncio
    async def test_run_creates_agent_and_returns_result(self):
        """run() with a prompt should return a string from the Agent's ReAct loop."""
        from cococat.core.sandbox.cubesandbox import CubeSandboxExecutor
        from cococat.core.sandbox.sandbox import Sandbox

        class FakeAsyncSandbox:
            def __init__(self, sandbox_id="sbx-mock"):
                self.sandbox_id = sandbox_id
                self._killed = False
                self._code = None

            async def run_code(self, code, language="python", **kwargs):
                self._code = code
                return type("Execution", (), {
                    "logs": type("Logs", (), {"stdout": [], "stderr": []})(),
                    "results": [],
                    "error": None,
                })()

            async def kill(self, **kwargs):
                self._killed = True

        sbx = FakeAsyncSandbox("sbx-run")

        with patch("cococat.core.sandbox.cubesandbox.AsyncSandbox"):
            executor = CubeSandboxExecutor(get_llm=lambda aid: StubLLM())
            executor._sandbox_instances = {"sbx-run": sbx}

            sandbox_obj = Sandbox(id="sbx-run", template="default", permissions={})
            result = await executor.run(sandbox_obj, "run this task", agent_id="main")

            assert "task completed" in result
