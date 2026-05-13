"""Provider routes."""
import json
import os
import logging

import httpx
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from cococat.providers.registry import create_builtin_registry

logger = logging.getLogger("cococat.routes.providers")

router = APIRouter(prefix="/api", tags=["providers"])


def _auth_path() -> str:
    return os.environ.get("COCOCAT_AUTH_FILE", "config/auth.json")


class SetKeyRequest(BaseModel):
    name: str
    key: str


class TestKeyRequest(BaseModel):
    name: str | None = None
    base_url: str
    key: str | None = None


class FetchModelsRequest(BaseModel):
    name: str
    base_url: str
    key: str | None = None


class UpdateModelsRequest(BaseModel):
    action: str  # "add" or "remove"
    model_id: str


_MODELS_CACHE: dict[str, list[str]] = {}
_MODELS_USER: dict[str, list[str]] = {}


def _models_path() -> str:
    return os.environ.get("COCOCAT_MODELS_FILE", "config/models.json")


def _load_user_models() -> dict[str, list[str]]:
    path = _models_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


@router.get("/providers")
async def list_providers(request: Request):
    """List configured LLM providers."""
    reg = create_builtin_registry()
    creds = request.app.state.creds if hasattr(request.app.state, "creds") else None

    result = []
    for spec in reg.list_all():
        has_key = False
        if creds:
            has_key = creds.get(spec["name"]) is not None
        else:
            import os
            env_key = spec.get("env_key", "")
            has_key = bool(env_key and os.environ.get(env_key))

        result.append({
            "name": spec["name"],
            "display_name": spec["display_name"],
            "base_url": spec.get("base_url", ""),
            "env_key": spec.get("env_key", ""),
            "has_key": has_key,
            "keywords": spec.get("keywords", []),
        })

    return {"providers": result}


@router.get("/models")
async def list_models(request: Request):
    """List available models, grouped by provider."""
    reg = create_builtin_registry()

    result = {}
    for spec in reg.list_all():
        result[spec["name"]] = {
            "display_name": spec["display_name"],
            "models": spec.get("keywords", []),
        }

    return {"models": result}


@router.put("/providers/key")
async def save_provider_key(req: SetKeyRequest):
    """Save an API key for a provider to config/auth.json."""
    reg = create_builtin_registry()
    spec = next((s for s in reg.list_all() if s["name"] == req.name), None)
    if not spec:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.name}")

    path = _auth_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    auth_data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                auth_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            auth_data = {}

    auth_data[req.name] = req.key

    with open(path, "w", encoding="utf-8") as f:
        json.dump(auth_data, f, indent=2, ensure_ascii=False)

    # Also set env var for immediate use
    env_key = spec.get("env_key", "")
    if env_key:
        os.environ[env_key] = req.key

    return {"saved": True, "name": req.name}


@router.post("/providers/test")
async def test_provider_connection(req: TestKeyRequest):
    """Test provider connectivity by calling GET {base_url}/models."""
    if not req.base_url:
        raise HTTPException(status_code=400, detail="base_url is required")

    base = req.base_url.rstrip("/")
    url = f"{base}/models"

    headers = {"Content-Type": "application/json"}
    if req.key:
        headers["Authorization"] = f"Bearer {req.key}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (401, 403):
                return {"ok": False, "status": resp.status_code, "error": f"HTTP {resp.status_code}: Unauthorized"}
            return {"ok": resp.status_code < 500, "status": resp.status_code}
    except httpx.TimeoutException:
        return {"ok": False, "status": 0, "error": "Connection timed out"}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}


def _normalize_models(data: dict, api: str) -> list[str]:
    """Extract model IDs from provider response (OpenAI-compatible format)."""
    models = data.get("data", [])
    if models:
        return [m["id"] for m in models if "id" in m]
    # Anthropic format
    models = data.get("models", [])
    if models:
        return [m.get("id") or m.get("name", "") for m in models if isinstance(m, dict)]
    return []


@router.post("/providers/fetch-models")
async def fetch_provider_models(req: FetchModelsRequest):
    """Fetch available models from provider's /models endpoint and cache them."""
    if not req.base_url:
        raise HTTPException(status_code=400, detail="base_url is required")

    base = req.base_url.rstrip("/")
    url = f"{base}/models"

    headers = {"Content-Type": "application/json"}
    if req.key:
        headers["Authorization"] = f"Bearer {req.key}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (401, 403):
                return {"error": f"HTTP {resp.status_code}: Unauthorized", "models": []}
            if not resp.is_success:
                return {"error": f"HTTP {resp.status_code}", "models": []}

            data = resp.json()
            model_ids = _normalize_models(data, "openai-completions")
            if model_ids:
                _MODELS_CACHE[req.name] = model_ids
            return {"models": model_ids}
    except httpx.TimeoutException:
        return {"error": "Connection timed out", "models": []}
    except Exception as e:
        return {"error": str(e), "models": []}


@router.get("/providers/{name}/models")
async def get_provider_models(name: str):
    """Get combined (saved + discovered) model list for a provider."""
    user_models = _load_user_models()
    saved = user_models.get(name, [])
    discovered = _MODELS_CACHE.get(name, [])
    combined = list(dict.fromkeys(saved + discovered))  # dedup, preserve order
    return {"models": combined}


@router.put("/providers/{name}/models")
async def update_provider_models(name: str, req: UpdateModelsRequest):
    """Add or remove a model for a provider."""
    user_models = _load_user_models()
    models = user_models.get(name, [])

    if req.action == "add":
        if req.model_id not in models:
            models.append(req.model_id)
    elif req.action == "remove":
        models = [m for m in models if m != req.model_id]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    user_models[name] = models
    os.makedirs(os.path.dirname(_models_path()) or ".", exist_ok=True)
    with open(_models_path(), "w", encoding="utf-8") as f:
        json.dump(user_models, f, indent=2, ensure_ascii=False)

    return {"models": models}
