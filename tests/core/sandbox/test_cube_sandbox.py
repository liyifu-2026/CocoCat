"""Test CubeSandboxExecutor — wraps e2b_code_interpreter SDK."""
import pytest
from unittest.mock import patch
from cococat.core.sandbox import Sandbox
from cococat.providers.base import LLMResponse


class FakeAsyncSandbox:
    """Mock of e2b_code_interpreter.AsyncSandbox."""
    def __init__(self, sandbox_id="sbx-mock", **kwargs):
        self.sandbox_id = sandbox_id
        self._killed = False
        self._code = None

    async def run_code(self, code, language="python", **kwargs):
        self._code = code
        stdout = type("StdoutList", (), {
            "__iter__": lambda s: iter(["hello from sandbox\n"]),
        })()
        return type("Execution", (), {
            "logs": type("Logs", (), {"stdout": stdout, "stderr": []})(),
            "results": [],
            "error": None,
        })()

    async def kill(self, **kwargs):
        self._killed = True


class TestCubeSandboxExecutor:
    @pytest.mark.asyncio
    async def test_creates_sandbox_via_e2b_sdk(self):
        """CubeSandboxExecutor uses AsyncSandbox.create() to create sandbox."""
        create_kwargs = {}

        async def fake_create(**kwargs):
            create_kwargs.update(kwargs)
            return FakeAsyncSandbox("sbx-abc123")

        with patch("cococat.core.sandbox.cubesandbox.AsyncSandbox") as MockAsyncSandbox:
            MockAsyncSandbox.create = fake_create

            from cococat.core.sandbox import CubeSandboxExecutor
            executor = CubeSandboxExecutor(template_id="test-template", timeout_seconds=120)
            sandbox = await executor.create("default", {})

            assert sandbox.id == "sbx-abc123"
            assert create_kwargs["template"] == "test-template"

    @pytest.mark.asyncio
    async def test_destroys_sandbox_via_sdk(self):
        """CubeSandboxExecutor calls sandbox.kill() to destroy."""
        sbx = FakeAsyncSandbox("sbx-xyz")

        with patch("cococat.core.sandbox.cubesandbox.AsyncSandbox") as MockAsyncSandbox:
            from cococat.core.sandbox import CubeSandboxExecutor
            executor = CubeSandboxExecutor()
            executor._sandbox_instances = {"sbx-xyz": sbx}

            sandbox_obj = Sandbox(id="sbx-xyz", template="default", permissions={})
            await executor.destroy(sandbox_obj)

            assert sbx._killed is True
            assert "sbx-xyz" not in executor._sandbox_instances

    @pytest.mark.asyncio
    async def test_run_creates_agent_and_returns_result(self):
        """CubeSandboxExecutor.run() creates Agent, runs ReAct, returns result."""
        sbx = FakeAsyncSandbox("sbx-run")

        class StubLLM:
            async def chat(self, messages, tools=None, **kwargs):
                return LLMResponse(content="hello from agent")

        with patch("cococat.core.sandbox.cubesandbox.AsyncSandbox"):
            from cococat.core.sandbox import CubeSandboxExecutor, Sandbox
            executor = CubeSandboxExecutor(get_llm=lambda aid: StubLLM())
            executor._sandbox_instances = {"sbx-run": sbx}

            sandbox_obj = Sandbox(id="sbx-run", template="default", permissions={})
            result = await executor.run(sandbox_obj, "run this task", agent_id="main")

            assert "hello from agent" in result

    @pytest.mark.asyncio
    async def test_sandbox_run_executes_code(self):
        """_sandbox_run executes raw code in the MicroVM."""
        sbx = FakeAsyncSandbox("sbx-run")

        with patch("cococat.core.sandbox.cubesandbox.AsyncSandbox"):
            from cococat.core.sandbox import CubeSandboxExecutor
            executor = CubeSandboxExecutor()
            executor._sandbox_instances = {"sbx-run": sbx}

            result = await executor._sandbox_run("sbx-run", "print('hello')")
            assert "hello from sandbox" in result
            assert "print('hello')" in sbx._code

    @pytest.mark.asyncio
    async def test_handles_sdk_unavailable(self):
        """CubeSandboxExecutor handles when SDK create fails."""
        async def fake_create(**kwargs):
            raise RuntimeError("Connection refused")

        with patch("cococat.core.sandbox.cubesandbox.AsyncSandbox") as MockAsyncSandbox:
            MockAsyncSandbox.create = fake_create

            from cococat.core.sandbox import CubeSandboxExecutor
            executor = CubeSandboxExecutor()

            with pytest.raises(RuntimeError, match="Connection refused|CubeSandbox create failed"):
                await executor.create("default", {})

    @pytest.mark.asyncio
    async def test_accepts_config_from_env(self, monkeypatch):
        """CubeSandboxExecutor reads config from environment variables."""
        monkeypatch.setenv("E2B_API_URL", "http://cube:3000")
        monkeypatch.setenv("E2B_API_KEY", "dummy")
        monkeypatch.setenv("CUBESANDBOX_TEMPLATE_ID", "env-template")

        from cococat.core.sandbox import CubeSandboxExecutor
        executor = CubeSandboxExecutor()
        assert executor._template_id == "env-template"

    @pytest.mark.asyncio
    async def test_sandbox_provider_with_cube_executor(self):
        """ExecutorProvider can use CubeSandboxExecutor as backend."""
        async def fake_create(**kwargs):
            return FakeAsyncSandbox("sbx-test")

        with patch("cococat.core.sandbox.cubesandbox.AsyncSandbox") as MockAsyncSandbox:
            MockAsyncSandbox.create = fake_create

            from cococat.core.sandbox import CubeSandboxExecutor, ExecutorProvider
            executor = CubeSandboxExecutor()
            provider = ExecutorProvider(executor=executor)
            sandbox_id = await provider.create(permissions={"kbs": ["faq"]})
            assert sandbox_id == "sbx-test"
