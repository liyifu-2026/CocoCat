"""Integration tests for scene creation and lifecycle management."""
import pytest
from fastapi.testclient import TestClient
from cococat.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def _create_scene(client, scene_id, name="Test Scene"):
    payload = {
        "id": scene_id,
        "name": name,
        "description": "A test scene",
        "purpose": "customer_service",
        "agent_name": "Test Agent",
        "agent_tone": "friendly",
        "agent_language": "zh",
    }
    resp = client.post("/api/scenes/full", json=payload)
    assert resp.status_code == 200
    return resp.json()


def test_create_scene_returns_running_status(client):
    """Given a scene payload, When created, Then it returns running status."""
    payload = {
        "id": "test-create-1",
        "name": "创建测试场景",
        "purpose": "customer_service",
        "agent_tone": "friendly",
        "agent_language": "zh",
    }
    resp = client.post("/api/scenes/full", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "test-create-1"
    assert data["status"] == "running"


def test_pause_running_scene_sets_paused(client):
    """Given a running scene, When paused, Then status is paused."""
    _create_scene(client, "test-pause-1")
    resp = client.post("/api/scenes/test-pause-1/lifecycle", json={"action": "pause"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


def test_resume_paused_scene_sets_running(client):
    """Given a paused scene, When resumed, Then status is running."""
    _create_scene(client, "test-resume-1")
    client.post("/api/scenes/test-resume-1/lifecycle", json={"action": "pause"})
    resp = client.post("/api/scenes/test-resume-1/lifecycle", json={"action": "resume"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_archive_running_scene_sets_archived(client):
    """Given a running scene, When archived, Then status is archived."""
    _create_scene(client, "test-archive-1")
    resp = client.post("/api/scenes/test-archive-1/lifecycle", json={"action": "archive"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_cannot_pause_archived_scene(client):
    """Given an archived scene, When pause is attempted, Then it returns 400."""
    _create_scene(client, "test-archive-2")
    client.post("/api/scenes/test-archive-2/lifecycle", json={"action": "archive"})
    resp = client.post("/api/scenes/test-archive-2/lifecycle", json={"action": "pause"})
    assert resp.status_code == 400


def test_scene_list_excludes_deleted(client):
    payload = {
        "id": "test-list-1",
        "name": "列表测试",
        "purpose": "customer_service",
        "agent_tone": "friendly",
        "agent_language": "zh",
    }
    resp = client.post("/api/scenes/full", json=payload)
    assert resp.status_code == 200

    resp = client.post("/api/scenes/test-list-1/lifecycle", json={"action": "delete"})
    assert resp.status_code == 200

    resp = client.get("/api/scenes")
    assert resp.status_code == 200
    scenes = resp.json()
    scene_ids = [s["id"] for s in scenes]
    assert "test-list-1" not in scene_ids


def test_scene_list_includes_running(client):
    payload = {
        "id": "test-list-2",
        "name": "运行中场景",
        "purpose": "content_writing",
        "agent_tone": "professional",
        "agent_language": "zh",
    }
    resp = client.post("/api/scenes/full", json=payload)
    assert resp.status_code == 200

    resp = client.get("/api/scenes")
    assert resp.status_code == 200
    scenes = resp.json()
    scene_ids = [s["id"] for s in scenes]
    assert "test-list-2" in scene_ids
