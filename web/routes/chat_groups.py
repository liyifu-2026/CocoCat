"""Chat group routes — proxies to Rust HTTP API (replaces old JSONL storage)."""
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()
RUST_API = "http://localhost:3000/api/chat/groups"


async def _proxy(method: str, path: str, request: Request, body: dict | None = None, params: dict | None = None):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{RUST_API}{path}"
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth
            resp = await client.request(method, url, json=body, params=params, headers=headers, timeout=30)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)


@router.get("/api/chat/groups")
async def list_groups(request: Request):
    return await _proxy("GET", "", request)


@router.post("/api/chat/groups")
async def create_group(request: Request, body: dict):
    return await _proxy("POST", "", request, body)


@router.get("/api/chat/groups/{group_id}")
async def get_group(request: Request, group_id: str):
    return await _proxy("GET", f"/{group_id}", request)


@router.patch("/api/chat/groups/{group_id}")
async def update_group(request: Request, group_id: str, body: dict):
    return await _proxy("PATCH", f"/{group_id}", request, body)


@router.delete("/api/chat/groups/{group_id}")
async def delete_group_route(request: Request, group_id: str):
    return await _proxy("DELETE", f"/{group_id}", request)


@router.post("/api/chat/groups/{group_id}/members")
async def add_member(request: Request, group_id: str, body: dict):
    return await _proxy("POST", f"/{group_id}/members", request, body)


@router.delete("/api/chat/groups/{group_id}/members/{agent_id}")
async def remove_member(request: Request, group_id: str, agent_id: str):
    return await _proxy("DELETE", f"/{group_id}/members/{agent_id}", request)


@router.post("/api/chat/groups/{group_id}/messages")
async def send_message(request: Request, group_id: str, body: dict):
    return await _proxy("POST", f"/{group_id}/messages", request, body)


@router.get("/api/chat/groups/{group_id}/messages")
async def get_messages(request: Request, group_id: str, limit: int = 100):
    return await _proxy("GET", f"/{group_id}/messages", request, params={"limit": limit})


@router.post("/api/chat/groups/{group_id}/messages/{msg_id}/recall")
async def recall_message(request: Request, group_id: str, msg_id: int):
    return await _proxy("POST", f"/{group_id}/messages/{msg_id}/recall", request)


@router.post("/api/chat/groups/{group_id}/messages/{msg_id}/read")
async def mark_read(request: Request, group_id: str, msg_id: int, body: dict):
    return await _proxy("POST", f"/{group_id}/messages/{msg_id}/read", request, body)
