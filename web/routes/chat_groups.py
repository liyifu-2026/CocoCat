"""Chat group routes — proxies to Rust HTTP API (replaces old JSONL storage)."""
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
RUST_API = "http://localhost:3000/api/chat/groups"


async def _proxy(method: str, path: str, body: dict | None = None, params: dict | None = None):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{RUST_API}{path}"
            resp = await client.request(method, url, json=body, params=params, timeout=30)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)


@router.get("/api/chat/groups")
async def list_groups():
    return await _proxy("GET", "")


@router.post("/api/chat/groups")
async def create_group(body: dict):
    return await _proxy("POST", "", body)


@router.get("/api/chat/groups/{group_id}")
async def get_group(group_id: str):
    return await _proxy("GET", f"/{group_id}")


@router.patch("/api/chat/groups/{group_id}")
async def update_group(group_id: str, body: dict):
    return await _proxy("PATCH", f"/{group_id}", body)


@router.delete("/api/chat/groups/{group_id}")
async def delete_group_route(group_id: str):
    return await _proxy("DELETE", f"/{group_id}")


@router.post("/api/chat/groups/{group_id}/members")
async def add_member(group_id: str, body: dict):
    return await _proxy("POST", f"/{group_id}/members", body)


@router.delete("/api/chat/groups/{group_id}/members/{agent_id}")
async def remove_member(group_id: str, agent_id: str):
    return await _proxy("DELETE", f"/{group_id}/members/{agent_id}")


@router.post("/api/chat/groups/{group_id}/messages")
async def send_message(group_id: str, body: dict):
    return await _proxy("POST", f"/{group_id}/messages", body)


@router.get("/api/chat/groups/{group_id}/messages")
async def get_messages(group_id: str, limit: int = 100):
    return await _proxy("GET", f"/{group_id}/messages", params={"limit": limit})


@router.post("/api/chat/groups/{group_id}/messages/{msg_id}/recall")
async def recall_message(group_id: str, msg_id: int):
    return await _proxy("POST", f"/{group_id}/messages/{msg_id}/recall")


@router.post("/api/chat/groups/{group_id}/messages/{msg_id}/read")
async def mark_read(group_id: str, msg_id: int, body: dict):
    return await _proxy("POST", f"/{group_id}/messages/{msg_id}/read", body)
