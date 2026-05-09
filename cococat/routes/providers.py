"""Provider routes."""
from fastapi import APIRouter, Request
from cococat.providers.registry import create_builtin_registry

router = APIRouter(prefix="/api", tags=["providers"])


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
