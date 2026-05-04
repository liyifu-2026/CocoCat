"""E2E tests for the FastAPI backend."""
import pytest
import os
import sys
import subprocess
import time
import json
import signal
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

API_BASE = "http://localhost:8080"


@pytest.fixture(scope="module")
def server():
    """Start the FastAPI server for E2E tests."""
    web_dir = Path(__file__).resolve().parent.parent.parent / "web"
    proc = subprocess.Popen(
        ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"],
        cwd=web_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def token(server):
    """Get auth token for API requests."""
    import httpx
    password = os.environ.get("WEB_PASSWORD", "admin")
    try:
        resp = httpx.post(f"{API_BASE}/api/auth/login", json={"password": password}, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except Exception:
        pass
    return None


@pytest.mark.skipif(
    not os.environ.get("WEB_PASSWORD"),
    reason="WEB_PASSWORD not set, skipping authenticated tests"
)
class TestAgentsAPI:
    def test_list_agents(self, token):
        import httpx
        resp = httpx.get(
            f"{API_BASE}/api/agents",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert len(data["agents"]) > 0

    def test_agent_detail(self, token):
        import httpx
        resp = httpx.get(
            f"{API_BASE}/api/agents",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        assert resp.status_code == 200
        agents = resp.json().get("agents", [])
        if agents:
            agent_id = agents[0]["id"]
            detail = httpx.get(
                f"{API_BASE}/api/agents/{agent_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            assert detail.status_code == 200
            assert detail.json()["id"] == agent_id

    def test_agent_profile(self, token):
        import httpx
        resp = httpx.get(
            f"{API_BASE}/api/agents",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        agents = resp.json().get("agents", [])
        if agents:
            agent_id = agents[0]["id"]
            profile = httpx.get(
                f"{API_BASE}/api/agents/{agent_id}/profile",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            assert profile.status_code == 200


class TestHealthEndpoint:
    def test_server_running(self, server):
        import httpx
        try:
            resp = httpx.get(f"{API_BASE}/api/agents", timeout=5)
            assert resp.status_code in (200, 401, 403)
        except httpx.ConnectError:
            pytest.skip("Server not reachable")

    def test_login_endpoint(self, server):
        import httpx
        resp = httpx.post(
            f"{API_BASE}/api/auth/login",
            json={"password": "wrong_password"},
            timeout=5,
        )
        assert resp.status_code == 401


class TestScenesAPI:
    def test_list_scenes(self, token):
        import httpx
        resp = httpx.get(
            f"{API_BASE}/api/scenes",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


@pytest.mark.skipif(
    not os.environ.get("PYTHON_AGENT_PATH"),
    reason="PYTHON_AGENT_PATH not set"
)
class TestAgentRuntime:
    def test_ping(self):
        runtime_path = os.environ.get("PYTHON_AGENT_PATH", "py-agent/agent_runtime.py")
        proc = subprocess.Popen(
            ["python3", "-u", runtime_path, "--id", "test", "--name", "Test"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        request = json.dumps({"jsonrpc": "2.0", "method": "ping", "params": {}, "id": 1})
        stdout, _ = proc.communicate(input=request + "\n", timeout=10)
        resp = json.loads(stdout.strip())
        assert resp["result"]["pong"] is True
        proc.wait()

    def test_echo(self):
        runtime_path = os.environ.get("PYTHON_AGENT_PATH", "py-agent/agent_runtime.py")
        proc = subprocess.Popen(
            ["python3", "-u", runtime_path, "--id", "test", "--name", "Test"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        request = json.dumps({"jsonrpc": "2.0", "method": "echo", "params": {"msg": "hello"}, "id": 2})
        stdout, _ = proc.communicate(input=request + "\n", timeout=10)
        resp = json.loads(stdout.strip())
        assert resp["result"]["msg"] == "hello"
        proc.wait()
