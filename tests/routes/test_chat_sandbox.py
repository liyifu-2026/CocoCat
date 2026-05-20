"""Test chat route uses ExecutorProvider instead of AgentPool."""
import tempfile
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


class MockProvider:
    """Captures calls to run_once and returns a canned response."""
    def __init__(self):
        self.captured_prompts = []
        self.captured_tools = []

    async def run_once(self, prompt, agent_id, permissions=None, tools=None, on_event=None, session_id=None):
        self.captured_prompts.append(prompt)
        if tools:
            self.captured_tools.append([t["name"] for t in tools])
        return "ExecutorProvider says: hello"


@pytest_asyncio.fixture
async def client():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    from cococat.app import create_app

    app = create_app(db_path)

    mock_provider = MockProvider()
    ctx = app.state.ctx
    ctx.sandbox_provider = mock_provider

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_chat_uses_sandbox_provider(client):
    """POST /api/chat should call ExecutorProvider.run_once() instead of AgentPool."""
    resp = await client.post("/api/chat", json={
        "content": "Hello world",
        "user_id": "test",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert "ExecutorProvider says" in data["reply"]
    assert "not connected" not in data["reply"]
