"""Test DAG API endpoint."""
import os
import yaml
import tempfile
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from cococat.app import create_app
from cococat.dag.store import FileDagStore


def _create_dag_run(runs_dir: str, run_id: str, stages: list[dict], status: str = "running"):
    run_dir = os.path.join(runs_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)
    data = {
        "run_id": run_id,
        "created_by": "main",
        "status": status,
        "stages": stages,
    }
    dag_path = os.path.join(run_dir, "dag.yaml")
    with open(dag_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


@pytest_asyncio.fixture
async def client(tmp_path):
    runs_dir = str(tmp_path / "runs")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    app = create_app(db_path)
    app.state.ctx.dag_store = FileDagStore(runs_dir)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, tmp_path


@pytest.mark.asyncio
async def test_list_dag_runs_empty(client):
    c, _ = client
    resp = await c.get("/api/dag")
    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    assert data["runs"] == []


@pytest.mark.asyncio
async def test_list_dag_runs_with_data(client):
    c, tmp_path = client
    runs_dir = str(tmp_path / "runs")
    _create_dag_run(runs_dir, "abc123", [
        {
            "id": "coding",
            "name": "编码",
            "tasks": [
                {"id": "code-a", "status": "done", "result": "ok"},
                {"id": "code-b", "status": "running"},
            ],
        }
    ])
    _create_dag_run(runs_dir, "def456", [
        {
            "id": "review",
            "name": "审查",
            "tasks": [
                {"id": "review-a", "status": "pending"},
            ],
        }
    ], status="completed")

    resp = await c.get("/api/dag")
    assert resp.status_code == 200
    data = resp.json()
    runs = data["runs"]
    assert len(runs) == 2

    ids = {r["run_id"] for r in runs}
    assert "abc123" in ids
    assert "def456" in ids

    run_a = next(r for r in runs if r["run_id"] == "abc123")
    assert run_a["status"] == "running"
    assert len(run_a["stages"]) == 1
    assert len(run_a["stages"][0]["tasks"]) == 2


@pytest.mark.asyncio
async def test_get_single_dag_run(client):
    c, tmp_path = client
    runs_dir = str(tmp_path / "runs")
    _create_dag_run(runs_dir, "abc123", [
        {
            "id": "coding",
            "name": "编码",
            "tasks": [
                {"id": "code-a", "status": "done"},
            ],
        }
    ])

    resp = await c.get("/api/dag/abc123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "abc123"
    assert data["status"] == "running"
    assert len(data["stages"]) == 1


@pytest.mark.asyncio
async def test_get_nonexistent_dag_run(client):
    c, _ = client
    resp = await c.get("/api/dag/nonexistent")
    assert resp.status_code == 404
