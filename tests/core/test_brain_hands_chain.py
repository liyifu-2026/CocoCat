"""Integration tests for the brain→hands→web_search/fetch chain.

Simulates the full flow:
1. Chat route creates main AI tools → ExecutorProvider.run_once()
2. Main AI defines DAG → dispatches task
3. TaskWorker picks up pending task → SubAgentExecutor.dispatch()
4. Sub-agent runs with create_core_tools() → calls web_search/web_fetch
5. Result propagates back

Uses mocked LLM to verify the chain end-to-end without real API calls.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from cococat.providers.base import LLMResponse


# ── Mock LLM that responds with tool_calls ──

def _make_mock_llm(tool_call_name: str, tool_call_args: dict):
    """Create a mock LLM provider that calls a specific tool then returns text."""
    class MockLLM:
        def __init__(self):
            self.call_count = 0
            self.messages_history = []

        async def chat_stream(self, messages, tools=None, **kwargs):
            self.messages_history.append({"stream": True, "messages": messages, "tools": [t["name"] for t in (tools or [])]})
            self.call_count += 1
            yield {"type": "delta", "content": "Let me search for that."}
            yield {
                "type": "tool_call",
                "id": f"call_{self.call_count}",
                "name": tool_call_name,
                "arguments": json.dumps(tool_call_args),
            }
            yield {"type": "done", "content": "Let me search for that."}

        async def chat(self, messages, tools=None, **kwargs):
            self.messages_history.append({"stream": False, "messages": messages, "tools": [t["name"] for t in (tools or [])]})
            self.call_count += 1
            return LLMResponse(content="Here are the results based on the tool output.")

    return MockLLM()


# ── Helper to create a sub-agent executor with mocked LLM ──

async def _run_sub_agent_with_tool(
    tool_name: str,
    tool_args: dict,
    monkeypatch,
    mock_tool_result: str = "mock tool result",
):
    """Run a full sub-agent dispatch cycle with mocked LLM.

    Returns (agent_result, llm_mock) for assertions.
    """
    from cococat.core.sandbox import ExecutorProvider, InProcessExecutor
    from cococat.core.sub_agent import SubAgentExecutor
    from cococat.core.event_bus import EventBus

    mock_llm = _make_mock_llm(tool_name, tool_args)

    executor = InProcessExecutor()
    executor._resolve_llm = lambda agent_id: mock_llm

    provider = ExecutorProvider(executor=executor)
    bus = EventBus()

    sub = SubAgentExecutor(bus=bus, sandbox_provider=provider)

    result = await sub.dispatch(
        task=f"Use {tool_name} to search for test query",
        from_agent="main",
    )

    return result, mock_llm


class TestBrainHandsWebSearchChain:
    """End-to-end tests for brain dispatching to hands with web tools."""

    @pytest.mark.asyncio
    async def test_sub_agent_gets_web_search_in_tools(self, monkeypatch):
        """Sub-agent must have web_search available in its tool list."""
        from cococat.core.sandbox import InProcessExecutor
        from cococat.core.tools import create_core_tools

        mock_llm = _make_mock_llm("web_search", {"query": "test"})
        executor = InProcessExecutor()
        executor._resolve_llm = lambda agent_id: mock_llm

        # Simulate what _do_run does
        tools = create_core_tools()
        names = [t["name"] for t in tools]

        assert "web_search" in names, "create_core_tools() must include web_search"
        assert "web_fetch" in names, "create_core_tools() must include web_fetch"
        assert "read_file" in names
        assert "bash" in names

    @pytest.mark.asyncio
    async def test_web_search_passes_api_key_to_tool(self):
        """web_search tool receives tavily_api_key from context."""
        from cococat.core.tools import create_core_tools, ToolRegistry

        tools = create_core_tools(tavily_api_key="test-key-123")
        reg = ToolRegistry(tools)

        # The tool definition injects tavily_api_key into ctx
        web_search_tool = next(t for t in tools if t["name"] == "web_search")

        with patch("cococat.core.tools.web.TavilyClient") as mock_tavily:
            mock_client = MagicMock()
            mock_client.search.return_value = {"results": []}
            mock_tavily.return_value = mock_client

            await reg.execute("web_search", {"query": "test"})

            # Verify TavilyClient was created with the API key (keyword arg)
            mock_tavily.assert_called_once_with(api_key="test-key-123")

    @pytest.mark.asyncio
    async def test_web_fetch_handles_400_from_target(self):
        """web_fetch should gracefully handle 400 from target URL."""
        from cococat.core.tools import create_core_tools, ToolRegistry
        import httpx

        tools = create_core_tools()
        reg = ToolRegistry(tools)

        with patch("httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "400 Bad Request",
                request=MagicMock(),
                response=MagicMock(status_code=400),
            )
            mock_get.return_value = mock_resp

            result = await reg.execute("web_fetch", {"url": "https://example.com"})

            assert "error" in result.lower()
            assert "400" in result or "bad request" in result.lower()

    @pytest.mark.asyncio
    async def test_web_search_handles_tavily_400_error(self):
        """web_search should gracefully handle Tavily API returning 400."""
        from cococat.core.tools import create_core_tools, ToolRegistry
        from cococat.core.tools.web import TavilyClient as TavilyImport

        tools = create_core_tools(tavily_api_key="test-key")
        reg = ToolRegistry(tools)

        # Verify Tavily is importable
        if TavilyImport is None:
            result = await reg.execute("web_search", {"query": "test"})
            assert "tavily-python" in result.lower()
            return

        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("400 Bad Request from Tavily")

        with patch("cococat.core.tools.web.TavilyClient", return_value=mock_client):
            result = await reg.execute("web_search", {"query": "test"})

            assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_tool_schema_passes_deepseek_validation(self):
        """All tool schemas must pass DeepSeek API validation rules."""
        from cococat.providers.openai_compat import _tool_to_openai
        from cococat.core.tools import create_core_tools

        tools = create_core_tools()

        for t in tools:
            converted = _tool_to_openai(t)

            # DeepSeek requires: each tool must have type=function wrapper
            fc = {"type": "function", "function": converted}

            # Must be serializable
            serialized = json.dumps(fc)

            # Required fields check
            assert "name" in converted, f"{t['name']}: missing name"
            assert "description" in converted, f"{t['name']}: missing description"
            assert "parameters" in converted, f"{t['name']}: missing parameters"

            params = converted["parameters"]
            assert params["type"] == "object"
            assert isinstance(params["properties"], dict)
            assert isinstance(params.get("required", []), list)

            # Array types must have items (DeepSeek strict requirement)
            for prop_name, prop_schema in params["properties"].items():
                if prop_schema.get("type") == "array":
                    assert "items" in prop_schema, (
                        f"{t['name']}.{prop_name}: array type requires 'items' "
                        f"— DeepSeek API returns 400 without it"
                    )


class TestSubAgentToolDispatch:
    """Test that sub-agents correctly receive and use web tools."""

    @pytest.mark.asyncio
    async def test_sub_agent_tool_result_propagates_correctly(self):
        """Tool result from web_search must be passed to LLM in correct format."""
        from cococat.core.tool_executor import execute_tool_calls

        messages = [{"role": "system", "content": "You are a test agent."}]

        tool_calls = [{
            "id": "call_abc",
            "name": "web_search",
            "arguments": '{"query": "test"}',
        }]

        mock_tools = [{
            "name": "web_search",
            "description": "Search the web",
            "parameters": {"query": "string"},
            "execute": lambda p, ctx: "Found: test results here",
        }]

        await execute_tool_calls(
            tool_calls, messages, mock_tools,
            context={}, on_tool=None,
        )

        # Verify the tool result message was appended
        # _execute_tool_calls appends only the tool result message
        # (assistant message is added by the caller run() method)
        assert len(messages) == 2  # system + tool
        tool_msg = messages[1]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "call_abc"
        assert "Found: test results" in tool_msg["content"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_handles_malformed_json(self):
        """execute_tool_calls must handle json.JSONDecodeError gracefully."""
        from cococat.core.tool_executor import execute_tool_calls

        messages = [{"role": "system", "content": "test"}]

        tool_calls = [{
            "id": "call_bad",
            "name": "web_search",
            "arguments": "{bad json!!!",
        }]

        mock_tools = [{
            "name": "web_search",
            "description": "Search",
            "parameters": {"query": "string"},
            "execute": lambda p, ctx: "ok",
        }]

        await execute_tool_calls(
            tool_calls, messages, mock_tools,
            context={}, on_tool=None,
        )

        assert len(messages) == 2
        tool_msg = messages[1]
        assert tool_msg["role"] == "tool"
        assert "error" in tool_msg["content"].lower()


class TestToolExecuteCallable:
    """Verify all tool execute callables work correctly."""

    def test_web_search_execute_callable_is_async_compatible(self):
        """web_search.execute must return an awaitable or plain result."""
        from cococat.core.tools import create_core_tools

        tools = create_core_tools()
        ws = next(t for t in tools if t["name"] == "web_search")

        # Execute must be callable
        assert callable(ws["execute"])

        # Execute returns a string (direct call, not async)
        result = ws["execute"]({"query": "test"}, {})
        assert isinstance(result, str)
        assert len(result) > 0

        # Should not be a coroutine (it's a plain function)
        assert not hasattr(result, "__await__")

    def test_web_fetch_execute_callable_is_async_compatible(self):
        """web_fetch.execute must return an awaitable or plain result."""
        from cococat.core.tools import create_core_tools

        tools = create_core_tools()
        wf = next(t for t in tools if t["name"] == "web_fetch")

        assert callable(wf["execute"])

        with patch("httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = "<html>test</html>"
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            result = wf["execute"]({"url": "https://example.com"}, {})
            assert isinstance(result, str)

    def test_all_core_tools_have_execute_callable(self):
        """Every core tool must have a callable execute field."""
        from cococat.core.tools import create_core_tools

        tools = create_core_tools()
        for t in tools:
            assert callable(t.get("execute")), (
                f"Tool '{t['name']}' has no callable execute field"
            )


class TestDagDispatchWithWebSearch:
    """Test the DAG dispatch → sub-agent → web_search pipeline."""

    @pytest.mark.asyncio
    async def test_dispatch_task_marks_task_pending(self, tmp_path):
        """_dispatch_task should mark task as pending in dag.yaml."""
        from cococat.core.tools.dag import _dispatch_task, _define_dag
        from cococat.dag.store import FileDagStore

        store = FileDagStore(str(tmp_path / "runs"))

        yaml_str = """
stages:
  - id: search
    tasks:
      - id: search-web
        description: Search the web
"""
        run_id = _define_dag(yaml_str, {"dag_store": store})

        async def mock_executor(prompt, agent_id):
            return "search result from sub-agent"

        result = await _dispatch_task(
            run_id=run_id,
            task_id="search-web",
            prompt="Use web_search to find python docs",
            ctx={"dag_store": store, "sub_agent_executor": mock_executor},
        )

        assert "dispatched" in result.lower()

        data = store.load(run_id)
        task = data["stages"][0]["tasks"][0]
        assert task["id"] == "search-web"
        assert task["status"] == "pending"
        assert "web_search" in task.get("prompt", "")

    @pytest.mark.asyncio
    async def test_execute_pending_dag_task_runs_sub_agent(self, tmp_path):
        """execute_pending_dag_task should execute and get results."""
        from cococat.dag import execute_pending_dag_task
        from cococat.dag.store import FileDagStore

        store = FileDagStore(str(tmp_path / "runs"))

        dag_data = {
            "run_id": "run-001",
            "status": "running",
            "stages": [{
                "id": "stage-1",
                "tasks": [{
                    "id": "task-1",
                    "status": "pending",
                    "prompt": "Use web_search to find latest news",
                }],
            }],
        }
        store.save("run-001", dag_data)

        execution_log = []

        async def mock_executor(prompt, task_id, session_id=None):
            execution_log.append({"prompt": prompt, "task_id": task_id, "session_id": session_id})
            return f"Result from {task_id}: found 3 articles"

        count = await execute_pending_dag_task(store, mock_executor)

        assert count == 1
        assert len(execution_log) == 1
        assert execution_log[0]["task_id"] == "task-1"
        assert "web_search" in execution_log[0]["prompt"]

        updated = store.load("run-001")
        assert updated["stages"][0]["tasks"][0]["status"] == "done"
        assert "Result from task-1" in updated["stages"][0]["tasks"][0]["result"]
