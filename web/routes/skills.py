"""Skills routes — proxy to Rust API."""
from fastapi import APIRouter, Request
import httpx
from fastapi.responses import JSONResponse

router = APIRouter()
RUST_API = "http://localhost:3000/api"


async def _proxy(method: str, path: str, request: Request):
    async with httpx.AsyncClient() as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth
            resp = await client.request(method, f"{RUST_API}{path}", headers=headers, timeout=30)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)


@router.get("/api/skills/warehouse")
async def list_warehouse(request: Request):
    return await _proxy("GET", "/skills/warehouse", request)


@router.post("/api/skills/warehouse/install")
async def install_skill(request: Request):
    return await _proxy("POST", "/skills/warehouse/install", request)


@router.get("/api/skills")
async def list_skills(request: Request):
    return await _proxy("GET", "/skills", request)


@router.post("/api/skills")
async def create_skill(request: Request):
    return await _proxy("POST", "/skills", request)


@router.get("/api/agents/capabilities")
async def capabilities(request: Request):
    return await _proxy("GET", "/agents/capabilities", request)
