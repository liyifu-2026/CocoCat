"""LLM provider management routes — provider config, model catalog, health check, agent models."""
import json
import os
import sys
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "py-agent"))

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ── Schemas ────────────────────────────────────────────────────────────

class ProviderUpdate(BaseModel):
    api_base: str = ""
    default_model: str = ""
    api_key: str = ""  # Will be stored in auth.json, not providers.json


class AgentModelUpdate(BaseModel):
    provider: str = ""
    model: str = ""
    reasoning_effort: str = ""


# ── Provider list ──────────────────────────────────────────────────────

@router.get("/api/providers")
def list_providers():
    """List all providers with their config status (keys masked)."""
    from providers.registry import PROVIDERS
    from provider_config import get_provider, get_api_key

    result = []
    for spec in PROVIDERS:
        cfg = get_provider(spec.name)
        key = get_api_key(spec.name)
        result.append({
            "name": spec.name,
            "keywords": list(spec.keywords),
            "api_base": cfg.get("api_base", spec.default_api_base or ""),
            "default_model": cfg.get("default_model", ""),
            "has_key": bool(key),
            "key_masked": _mask_key(key),
        })
    return {"providers": result}


@router.get("/api/providers/{name}")
def get_provider_detail(name: str):
    """Get a single provider's full config."""
    from providers.registry import PROVIDERS
    from provider_config import get_provider as get_cfg, get_api_key

    spec = next((p for p in PROVIDERS if p.name == name), None)
    if not spec:
        return JSONResponse({"error": f"provider '{name}' not found"}, status_code=404)

    cfg = get_cfg(name)
    key = get_api_key(name)
    return {
        "name": spec.name,
        "api_base": cfg.get("api_base", spec.default_api_base or ""),
        "default_model": cfg.get("default_model", ""),
        "has_key": bool(key),
        "key_masked": _mask_key(key),
    }


# ── Provider config update ────────────────────────────────────────────

@router.put("/api/providers/{name}")
def update_provider(name: str, body: ProviderUpdate):
    """Update a provider's configuration."""
    from providers.registry import PROVIDERS
    from provider_config import update_provider as save_cfg, set_api_key

    spec = next((p for p in PROVIDERS if p.name == name), None)
    if not spec:
        return JSONResponse({"error": f"provider '{name}' not found"}, status_code=404)

    config_data = {}
    if body.api_base:
        config_data["api_base"] = body.api_base
    if body.default_model:
        config_data["default_model"] = body.default_model

    if config_data:
        save_cfg(name, config_data)

    if body.api_key:
        set_api_key(name, body.api_key)

    return {"status": "updated", "provider": name}


# ── Health check ──────────────────────────────────────────────────────

@router.post("/api/providers/{name}/test")
def test_provider(name: str):
    """Test provider connectivity by listing models."""
    from providers.registry import PROVIDERS
    from providers.factory import make_provider_by_name

    spec = next((p for p in PROVIDERS if p.name == name), None)
    if not spec:
        return JSONResponse({"error": f"provider '{name}' not found"}, status_code=404)

    if not spec.default_api_base:
        return {"status": "error", "message": "provider has no default API base URL"}

    try:
        provider = make_provider_by_name(name)
        if provider is None:
            return {"status": "error", "message": "provider creation failed"}
        if not provider.api_key:
            return {"status": "error", "message": "no API key configured"}

        import httpx
        api_base = provider.api_base.rstrip("/")
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        resp = httpx.get(f"{api_base}/v1/models", headers=headers, timeout=10)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            model_names = [m.get("id", "") for m in models[:10]]
            return {"status": "ok", "models": model_names}
        else:
            return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Model catalog ─────────────────────────────────────────────────────

@router.get("/api/models")
def list_models(provider: str = ""):
    """List available models from the catalog, optionally filtered by provider."""
    from provider_config import get_available_models, load_models

    catalog = load_models()
    if not catalog:
        return {"models": [], "note": "catalog not loaded"}

    if provider:
        models = get_available_models(provider)
    else:
        all_models = []
        for pname, pdata in catalog.items():
            for m in pdata.get("models", []):
                m_copy = dict(m)
                m_copy["provider"] = pname
                all_models.append(m_copy)
        models = all_models

    return {"models": models, "provider": provider or "all"}


@router.post("/api/models/refresh")
def refresh_model_catalog():
    """Force refresh the model catalog from models.dev."""
    from provider_config import fetch_and_cache_models
    ok = fetch_and_cache_models()
    return {"status": "ok" if ok else "failed"}


# ── Agent model assignments ───────────────────────────────────────────

@router.get("/api/agents/{agent_id}/model")
def get_agent_model_config(agent_id: str):
    """Get the model assignment for an agent."""
    from provider_config import get_agent_model
    return get_agent_model(agent_id)


@router.put("/api/agents/{agent_id}/model")
def set_agent_model_config(agent_id: str, body: AgentModelUpdate):
    """Set the model assignment for an agent."""
    from provider_config import set_agent_model
    set_agent_model(agent_id, body.provider, body.model, body.reasoning_effort)
    return {"status": "updated", "agent_id": agent_id}


# ── Helpers ───────────────────────────────────────────────────────────

def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return ""
    return key[:4] + "●●●●" + key[-4:]
