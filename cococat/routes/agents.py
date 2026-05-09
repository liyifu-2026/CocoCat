"""Agent routes."""
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreate(BaseModel):
    id: str
    name: str
    role: str = "sub"
    model: str = "deepseek-chat"


class AgentUpdate(BaseModel):
    name: str | None = None
    model: str | None = None


@router.get("")
async def list_agents(request: Request):
    db = request.app.state.db
    rows = db.execute(
        "SELECT id, name, role, status, scene_id, model, created_at FROM agents"
    )
    return {
        "agents": [
            {
                "id": r[0], "name": r[1], "role": r[2],
                "status": r[3], "scene_id": r[4], "model": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]
    }


@router.post("")
async def create_agent(body: AgentCreate, request: Request):
    db = request.app.state.db
    db.execute_insert(
        "INSERT INTO agents (id, name, role, model, status) VALUES (?, ?, ?, ?, 'stopped')",
        (body.id, body.name, body.role, body.model),
    )
    return {"status": "created", "id": body.id}


@router.get("/{agent_id}")
async def get_agent(agent_id: str, request: Request):
    db = request.app.state.db
    rows = db.execute(
        "SELECT id, name, role, status, scene_id, model FROM agents WHERE id = ?",
        (agent_id,),
    )
    if not rows:
        return {"error": "not found"}, 404
    r = rows[0]
    return {
        "id": r[0], "name": r[1], "role": r[2],
        "status": r[3], "scene_id": r[4], "model": r[5],
    }


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdate, request: Request):
    db = request.app.state.db
    if body.name:
        db.execute("UPDATE agents SET name = ? WHERE id = ?", (body.name, agent_id))
    if body.model:
        db.execute("UPDATE agents SET model = ? WHERE id = ?", (body.model, agent_id))
    db.commit()
    return {"status": "updated"}
