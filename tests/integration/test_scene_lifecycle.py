"""Integration tests for scene creation and lifecycle management."""
import pytest
import pytest_asyncio
import tempfile
import os
from httpx import AsyncClient, ASGITransport
from cococat.app import create_app


@pytest_asyncio.fixture
async def client():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    app = create_app(db_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_scene_create_and_lifecycle(client):
    """Test full scene lifecycle: create -> pause -> resume -> archive."""
    payload = {
        "id": "test-scene-1",
        "name": "测试场景",
        "description": "一个测试场景",
        "purpose": "customer_service",
        "agent_name": "测试助手",
        "agent_tone": "friendly",
        "agent_language": "zh",
        "kbs": ["test-kb"],
        "skills": ["communication"],
        "channels": ["web"],
        "visibility": "private",
    }
    resp = await client.post("/api/scenes/full", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "test-scene-1"
    assert data["status"] == "running"
    assert data["agent_id"] == "test-scene-1"

    # Pause scene
    resp = await client.post("/api/scenes/test-scene-1/lifecycle", json={"action": "pause"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"

    # Resume scene
    resp = await client.post("/api/scenes/test-scene-1/lifecycle", json={"action": "resume"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"

    # Archive scene
    resp = await client.post("/api/scenes/test-scene-1/lifecycle", json={"action": "archive"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    # Cannot pause an archived scene (invalid transition)
    resp = await client.post("/api/scenes/test-scene-1/lifecycle", json={"action": "pause"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_scene_list_excludes_deleted(client):
    """Test that deleted scenes are excluded from the list."""
    # Create a scene
    payload = {
        "id": "test-list-1",
        "name": "列表测试",
        "purpose": "customer_service",
        "agent_tone": "friendly",
        "agent_language": "zh",
    }
    resp = await client.post("/api/scenes/full", json=payload)
    assert resp.status_code == 200

    # Delete it
    resp = await client.post("/api/scenes/test-list-1/lifecycle", json={"action": "delete"})
    assert resp.status_code == 200

    # List should not include deleted scenes
    resp = await client.get("/api/scenes")
    assert resp.status_code == 200
    scenes = resp.json()
    scene_ids = [s["id"] for s in scenes]
    assert "test-list-1" not in scene_ids


@pytest.mark.asyncio
async def test_scene_list_includes_running(client):
    """Test that running scenes appear in the list."""
    payload = {
        "id": "test-list-2",
        "name": "运行中场景",
        "purpose": "content_writing",
        "agent_tone": "professional",
        "agent_language": "zh",
    }
    resp = await client.post("/api/scenes/full", json=payload)
    assert resp.status_code == 200

    resp = await client.get("/api/scenes")
    assert resp.status_code == 200
    scenes = resp.json()
    scene_ids = [s["id"] for s in scenes]
    assert "test-list-2" in scene_ids
