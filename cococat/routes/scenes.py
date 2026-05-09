"""Scene routes."""
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


class SceneCreate(BaseModel):
    id: str
    name: str


class SceneUpdate(BaseModel):
    name: str | None = None


@router.get("")
async def list_scenes(request: Request):
    db = request.app.state.db
    rows = db.execute("SELECT id, name, description, created_at FROM scenes")
    return {
        "scenes": [
            {"id": r[0], "name": r[1], "description": r[2], "created_at": r[3]}
            for r in rows
        ]
    }


@router.post("")
async def create_scene(body: SceneCreate, request: Request):
    db = request.app.state.db
    db.execute_insert(
        "INSERT INTO scenes (id, name) VALUES (?, ?)",
        (body.id, body.name),
    )
    return {"status": "created", "id": body.id}


@router.get("/{scene_id}")
async def get_scene(scene_id: str, request: Request):
    db = request.app.state.db
    rows = db.execute("SELECT id, name, description, roster FROM scenes WHERE id = ?", (scene_id,))
    if not rows:
        return {"error": "not found"}, 404
    r = rows[0]
    return {"id": r[0], "name": r[1], "description": r[2], "roster": r[3]}


@router.delete("/{scene_id}")
async def delete_scene(scene_id: str, request: Request):
    db = request.app.state.db
    db.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
    db.commit()
    return {"status": "deleted"}
