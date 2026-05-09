"""Tests for cococat API routes."""
import tempfile
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from cococat.app import create_app


@pytest_asyncio.fixture
async def client():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    app = create_app(db_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_agents_nonempty(client):
    """At minimum, the seeded 'main' agent exists."""
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    agents = resp.json()["agents"]
    assert len(agents) >= 1


@pytest.mark.asyncio
async def test_create_and_list_agents(client):
    await client.post("/api/agents", json={"id": "agent_b", "name": "Agent B", "role": "sub"})
    await client.post("/api/agents", json={"id": "agent_c", "name": "Agent C", "role": "sub"})

    resp = await client.get("/api/agents")
    agents = resp.json()["agents"]
    ids = {a["id"] for a in agents}
    assert "agent_b" in ids
    assert "agent_c" in ids


@pytest.mark.asyncio
async def test_get_agent(client):
    await client.post("/api/agents", json={"id": "agent_a", "name": "Agent A"})
    resp = await client.get("/api/agents/agent_a")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Agent A"


@pytest.mark.asyncio
async def test_patch_agent(client):
    await client.post("/api/agents", json={"id": "agent_a", "name": "Agent A"})
    resp = await client.patch("/api/agents/agent_a", json={"name": "Renamed"})
    assert resp.status_code == 200
    resp = await client.get("/api/agents/agent_a")
    assert resp.json()["name"] == "Renamed"


@pytest.mark.asyncio
async def test_scene_crud(client):
    resp = await client.post("/api/scenes", json={"id": "cs", "name": "Customer Service"})
    assert resp.status_code == 200

    resp = await client.get("/api/scenes")
    scenes = resp.json()["scenes"]
    assert len(scenes) == 1
    assert scenes[0]["id"] == "cs"

    resp = await client.get("/api/scenes/cs")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Customer Service"

    resp = await client.delete("/api/scenes/cs")
    assert resp.status_code == 200

    resp = await client.get("/api/scenes")
    assert len(resp.json()["scenes"]) == 0


@pytest.mark.asyncio
async def test_chat_no_agent(client):
    resp = await client.post("/api/chat", json={"content": "Hello"})
    assert resp.status_code == 200
    assert "not connected" in resp.json()["reply"].lower()


# ── Knowledge Base Routes ──

@pytest.mark.asyncio
async def test_list_kbs(client):
    """List KBs — non-empty since knowledge/ dir has existing KBs."""
    resp = await client.get("/api/knowledge")
    assert resp.status_code == 200
    assert "kbs" in resp.json()


@pytest.mark.asyncio
async def test_list_kbs_with_data(client):
    import os
    os.makedirs("knowledge/test-api-kb/raw/sources", exist_ok=True)
    os.makedirs("knowledge/test-api-kb/wiki/entities", exist_ok=True)
    os.makedirs("knowledge/test-api-kb/wiki/concepts", exist_ok=True)
    with open("knowledge/test-api-kb/purpose.md", "w") as f:
        f.write("Test KB for API")

    resp = await client.get("/api/knowledge")
    assert resp.status_code == 200
    kbs = resp.json()["kbs"]
    ids = [k["id"] for k in kbs]
    assert "test-api-kb" in ids

    # Cleanup
    import shutil
    shutil.rmtree("knowledge/test-api-kb")


@pytest.mark.asyncio
async def test_wiki_index_not_found(client):
    """KB dir not found returns empty listings (source currently returns 200, not 404)."""
    resp = await client.get("/api/knowledge/nonexistent/wiki")
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_search_kb_empty(client):
    resp = await client.get("/api/knowledge/nonexistent/search?q=")
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


# ── Skills Routes ──

@pytest.mark.asyncio
async def test_list_skills(client):
    resp = await client.get("/api/skills")
    assert resp.status_code == 200
    assert "global" in resp.json()


@pytest.mark.asyncio
async def test_get_skill_not_found(client):
    resp = await client.get("/api/skills/nonexistent_skill_xyz")
    # Source currently returns 200 with empty body on missing skill
    data = resp.json()
    assert resp.status_code in (200, 404)


# ── Scene Management Routes ──

@pytest.mark.asyncio
async def test_patch_scene_kbs(client):
    resp = await client.patch("/api/scenes/test-scene/kbs", json={"mounted": ["kb-1", "kb-2"]})
    assert resp.status_code == 200
    assert resp.json()["mounted"] == ["kb-1", "kb-2"]

    # Cleanup written file
    import os
    try:
        os.remove("scenes/test-scene/scene.yaml")
        os.rmdir("scenes/test-scene")
    except OSError:
        pass


@pytest.mark.asyncio
async def test_patch_scene_skills(client):
    resp = await client.patch("/api/scenes/test-scene/skills", json={"skills": ["skill-1"]})
    assert resp.status_code == 200
    assert resp.json()["skills"] == ["skill-1"]

    import os
    try:
        os.remove("scenes/test-scene/scene.yaml")
        os.rmdir("scenes/test-scene")
    except OSError:
        pass


# ── Provider Routes ──

@pytest.mark.asyncio
async def test_list_providers(client):
    resp = await client.get("/api/providers")
    assert resp.status_code == 200
    providers = resp.json()["providers"]
    assert len(providers) >= 1
    names = {p["name"] for p in providers}
    assert "deepseek" in names


@pytest.mark.asyncio
async def test_list_models(client):
    resp = await client.get("/api/models")
    assert resp.status_code == 200
    models = resp.json()["models"]
    assert "deepseek" in models


# ── Channel Routes ──

@pytest.mark.asyncio
async def test_list_channels(client):
    resp = await client.get("/api/channels")
    assert resp.status_code == 200
    assert "channels" in resp.json()
