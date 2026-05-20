"""Provider routes — list, configure, test LLM providers and manage models."""
import json
import httpx
import logging
import os
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext
from cococat.providers.registry import create_builtin_registry

logger = logging.getLogger("cococat.routes.providers")

router = APIRouter(prefix="/api", tags=["providers"])


# ── config paths ──

def _auth_path() -> str:
    return os.environ.get("COCOCAT_AUTH_FILE", "config/auth.json")


def _models_path() -> str:
    return os.environ.get("COCOCAT_MODELS_FILE", "config/models.json")


def _custom_providers_path() -> str:
    return os.environ.get("COCOCAT_CUSTOM_PROVIDERS_FILE", "config/providers.json")


# ── request models ──

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


class SaveProviderConfigRequest(BaseModel):
    display_name: str | None = None
    base_url: str


class BatchUpdateModelsRequest(BaseModel):
    models: list[str]  # full list of enabled model IDs
    default: str | None = None


# ── in-memory caches ──

_MODELS_CACHE: dict[str, list[str]] = {}
_MODELS_DEFAULT: dict[str, str] = {}


# ── custom providers persistence ──

def _load_custom_providers(store=None) -> list[dict]:
    if store is not None:
        return store.get_custom_providers()
    path = _custom_providers_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_custom_providers(data: list[dict], store=None) -> None:
    if store is not None:
        store.save_custom_providers(data)
        return
    path = _custom_providers_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _find_custom_provider(name: str, store=None) -> dict | None:
    custom = _load_custom_providers(store)
    for p in custom:
        if p.get("name") == name:
            return p
    return None


def _is_builtin(name: str) -> bool:
    reg = create_builtin_registry()
    return reg.find_by_name(name) is not None


# ── models persistence ──

def _load_user_models(store=None) -> dict[str, list[str]]:
    if store is not None:
        data = store.get_models()
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k != "__defaults__"}
    return _load_user_models_fallback()


def _save_user_models(data: dict[str, list[str]], store=None) -> None:
    if store is not None:
        existing = store.get_models()
        defaults = existing.get("__defaults__", {})
        existing.update(data)
        existing["__defaults__"] = defaults
        store.save_models(existing)
        return
    path = _models_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_user_models_fallback() -> dict[str, list[str]]:
    path = _models_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _load_default_models(store=None) -> dict[str, str]:
    if store is not None:
        data = store.get_models()
        if isinstance(data, dict):
            return data.get("__defaults__", {})
    path = _models_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data.get("__defaults__", {})
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_default_models(defaults: dict[str, str], store=None) -> None:
    if store is not None:
        data = store.get_models()
        data["__defaults__"] = defaults
        store.save_models(data)
        return
    path = _models_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = _load_user_models()
    data["__defaults__"] = defaults
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _resolve_key(name: str, creds=None, env_key: str = "") -> str | None:
    """Resolve API key: credential manager → env var."""
    if creds:
        key = creds.get(name)
        if key:
            return key
    if env_key:
        return os.environ.get(env_key) or None
    return None


def _save_auth_key(name: str, key: str, store=None) -> None:
    if store is not None:
        store.set_auth(name, key)
        return
    path = _auth_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    auth_data: dict = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                auth_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            auth_data = {}
    auth_data[name] = key
    with open(path, "w", encoding="utf-8") as f:
        json.dump(auth_data, f, indent=2, ensure_ascii=False)


async def _test_connection(base_url: str, api_key: str | None = None) -> dict:
    """Test connectivity to a provider. Returns {ok, status, error?, latency_ms}."""
    base = base_url.rstrip("/")
    url = f"{base}/models"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            elapsed = round((time.monotonic() - start) * 1000)
            if resp.status_code in (401, 403):
                return {"ok": False, "status": resp.status_code, "error": "Unauthorized — check API key", "latency_ms": elapsed}
            if resp.status_code >= 500:
                return {"ok": False, "status": resp.status_code, "error": f"Server error (HTTP {resp.status_code})", "latency_ms": elapsed}
            return {"ok": True, "status": resp.status_code, "latency_ms": elapsed}
    except httpx.TimeoutException:
        elapsed = round((time.monotonic() - start) * 1000)
        return {"ok": False, "status": 0, "error": "Connection timed out", "latency_ms": elapsed}
    except Exception as e:
        elapsed = round((time.monotonic() - start) * 1000)
        return {"ok": False, "status": 0, "error": str(e), "latency_ms": elapsed}


# ── routes ──

@router.get("/providers")
async def list_providers(ctx: AppContext = Depends(get_ctx)):
    """List all providers (builtin + custom) with status and model counts."""
    reg = create_builtin_registry()
    creds = ctx.creds
    custom = _load_custom_providers(ctx.config_store)
    user_models = _load_user_models(ctx.config_store)

    builtin_names = {s.name for s in reg.list_all()}
    result = []

    for spec in reg.list_all():
        name = spec.name
        key = _resolve_key(name, creds, spec.env_key)
        # Check for custom base_url override
        custom_override = next((cp for cp in custom if cp["name"] == name), None)
        base_url = custom_override.get("base_url", "") if custom_override else spec.default_api_base
        display_name = custom_override.get("display_name", "") if custom_override else ""
        models = user_models.get(name, [])

        result.append({
            "name": name,
            "display_name": display_name or spec.display_name,
            "base_url": base_url,
            "env_key": spec.env_key,
            "has_key": key is not None,
            "connected": key is not None,
            "custom": False,
            "enabled_count": len(models),
            "keywords": list(spec.keywords),
        })

    for cp in custom:
        name = cp["name"]
        if name in builtin_names:
            continue
        key = _resolve_key(name, creds, cp.get("env_key", ""))
        result.append({
            "name": name,
            "display_name": cp.get("display_name", name),
            "base_url": cp.get("base_url", ""),
            "env_key": cp.get("env_key", ""),
            "has_key": key is not None,
            "connected": key is not None,
            "custom": True,
            "enabled_count": len(user_models.get(name, [])),
            "keywords": [],
        })

    return {"providers": result}


@router.get("/models")
async def list_models(ctx: AppContext = Depends(get_ctx)):
    """List available models, grouped by provider (for dropdowns)."""
    reg = create_builtin_registry()
    user_models = _load_user_models(ctx.config_store)

    result = {}
    for spec in reg.list_all():
        name = spec.name
        models = list(user_models.get(name, []))
        if not models:
            models = list(_MODELS_CACHE.get(name, []))

        result[name] = {
            "display_name": spec.display_name,
            "models": models,
        }

    return {"models": result}


@router.get("/models/enabled")
async def list_enabled_models(ctx: AppContext = Depends(get_ctx)):
    """List ONLY user-enabled models grouped by provider.
    
    Only providers with at least one enabled model are included.
    This is the source for model selectors in Agent settings.
    """
    reg = create_builtin_registry()
    user_models = _load_user_models(ctx.config_store)

    result = {}
    for spec in reg.list_all():
        name = spec.name
        models = list(user_models.get(name, []))
        if models:
            result[name] = {
                "display_name": spec.display_name,
                "models": models,
            }

    return {"providers": result}


def _get_user_config_store(ctx: AppContext):
    """Return a ConfigStore scoped to ctx.user_id, or global fallback."""
    if ctx.user_id:
        from cococat.config_store import ConfigStore
        return ConfigStore(user_id=ctx.user_id)
    return ctx.config_store


@router.put("/providers/key")
async def save_provider_key(req: SetKeyRequest, ctx: AppContext = Depends(get_ctx)):
    """Save API key and test connectivity. Returns {saved, ok, error?, status}."""
    reg = create_builtin_registry()
    spec = reg.find_by_name(req.name)
    custom_prov = None
    base_url = ""
    store = _get_user_config_store(ctx)

    if spec:
        base_url = spec.default_api_base
    else:
        custom_prov = _find_custom_provider(req.name, store)
        if custom_prov:
            base_url = custom_prov.get("base_url", "")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {req.name}")

    _save_auth_key(req.name, req.key, store)

    # Set env var immediately
    env_key = spec.env_key if spec else custom_prov.get("env_key", "") if custom_prov else ""
    if env_key:
        os.environ[env_key] = req.key

    # Test connection
    test_result = await _test_connection(base_url, req.key)

    return {
        "saved": True,
        "name": req.name,
        "ok": test_result["ok"],
        "status": test_result.get("status", 0),
        "error": test_result.get("error"),
        "latency_ms": test_result.get("latency_ms", 0),
    }


@router.post("/providers/test")
async def test_provider_connection(req: TestKeyRequest):
    """Test provider connectivity."""
    if not req.base_url:
        raise HTTPException(status_code=400, detail="base_url is required")
    return await _test_connection(req.base_url, req.key)


# ── provider config (base_url, display_name, key) ──

@router.get("/providers/{name}/config")
async def get_provider_config(name: str, ctx: AppContext = Depends(get_ctx)):
    """Get provider config: base_url, display_name, and saved API key (with admin fallback)."""
    store = _get_user_config_store(ctx)
    custom = _load_custom_providers(store)
    c = next((p for p in custom if p["name"] == name), None)
    base_url = c.get("base_url", "") if c else ""
    display_name = c.get("display_name", "") if c else ""

    reg = create_builtin_registry()
    spec = reg.find_by_name(name)
    if spec and not base_url:
        base_url = spec.default_api_base
        display_name = display_name or spec.display_name

    key = store.get_auth(name)

    # Fallback: if user has no key, check admin's shared key
    if not key and ctx.user_id and ctx.user_id != "admin":
        from cococat.config_store import ConfigStore
        admin_store = ConfigStore(user_id="admin")
        key = admin_store.get_auth(name)

    return {
        "name": name,
        "base_url": base_url,
        "display_name": display_name,
        "key": key or "",
    }

@router.put("/providers/{name}/config")
async def save_provider_config(name: str, req: SaveProviderConfigRequest, ctx: AppContext = Depends(get_ctx)):
    """Update base_url/display_name for a provider.

    Builtin: overrides stored in custom providers file as patch.
    Custom: updates the custom provider entry directly.
    """
    base_url = req.base_url.strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="base_url is required")

    custom = _load_custom_providers(ctx.config_store)
    existing = next((p for p in custom if p["name"] == name), None)

    if existing:
        existing["base_url"] = base_url
        if req.display_name:
            existing["display_name"] = req.display_name
    elif _is_builtin(name):
        # Store override for builtin
        entry = {"name": name, "base_url": base_url}
        if req.display_name:
            entry["display_name"] = req.display_name
        custom.append(entry)
    else:
        # New custom provider
        entry = {
            "name": name,
            "display_name": req.display_name or name,
            "base_url": base_url,
        }
        custom.append(entry)

    _save_custom_providers(custom, ctx.config_store)
    return {"saved": True, "name": name}


@router.delete("/providers/{name}")
async def delete_provider(name: str, ctx: AppContext = Depends(get_ctx)):
    """Delete a custom provider. Builtin providers cannot be deleted."""
    if _is_builtin(name):
        raise HTTPException(status_code=403, detail="Builtin providers cannot be deleted")

    custom = _load_custom_providers(ctx.config_store)
    custom = [p for p in custom if p["name"] != name]
    _save_custom_providers(custom, ctx.config_store)

    return {"deleted": True, "name": name}


# ── models ──

def _normalize_models(data: dict, api: str = "") -> list[str]:
    """Extract model IDs from provider response."""
    models = data.get("data", [])
    if models:
        return [m["id"] for m in models if "id" in m]
    models = data.get("models", [])
    if models:
        return [m.get("id") or m.get("name", "") for m in models if isinstance(m, dict)]
    return []


@router.post("/providers/fetch-models")
async def fetch_provider_models(req: FetchModelsRequest):
    """Fetch available models from provider's /models endpoint."""
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
            model_ids = _normalize_models(data)
            if model_ids:
                _MODELS_CACHE[req.name] = model_ids
            return {"models": model_ids}
    except httpx.TimeoutException:
        return {"error": "Connection timed out", "models": []}
    except Exception as e:
        return {"error": str(e), "models": []}


@router.get("/providers/{name}/models")
async def get_provider_models(name: str, ctx: AppContext = Depends(get_ctx)):
    """Get structured models for a provider.

    Returns {enabled: [...], default: "..."}.
    enabled = user-saved enabled models.
    Available models are now provided by the frontend via modelpedia catalog.
    """
    reg = create_builtin_registry()
    spec = reg.find_by_name(name)
    custom_prov = None if spec else _find_custom_provider(name, ctx.config_store)

    if not spec and not custom_prov:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")

    user_models = _load_user_models(ctx.config_store)
    enabled = list(user_models.get(name, []))
    defaults = _load_default_models(ctx.config_store)

    default = defaults.get(name, enabled[0] if enabled else "")

    return {
        "enabled": enabled,
        "default": default,
    }


@router.put("/providers/{name}/models")
async def update_provider_models(name: str, req: UpdateModelsRequest, ctx: AppContext = Depends(get_ctx)):
    """Add or remove a single model for a provider."""
    user_models = _load_user_models(ctx.config_store)
    models = list(user_models.get(name, []))

    if req.action == "add":
        if req.model_id not in models:
            models.append(req.model_id)
    elif req.action == "remove":
        models = [m for m in models if m != req.model_id]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    user_models[name] = models
    _save_user_models(user_models, ctx.config_store)

    return {"models": models}


@router.put("/providers/{name}/models/batch")
async def batch_update_models(name: str, req: BatchUpdateModelsRequest, ctx: AppContext = Depends(get_ctx)):
    """Batch update enabled models and optional default model."""
    user_models = _load_user_models(ctx.config_store)
    user_models[name] = req.models

    # Persist default model
    if req.default is not None:
        defaults = _load_default_models(ctx.config_store)
        if req.default:
            defaults[name] = req.default
        else:
            defaults.pop(name, None)
        _save_default_models(defaults, ctx.config_store)

    _save_user_models(user_models, ctx.config_store)

    return {
        "models": req.models,
        "default": req.default,
    }
