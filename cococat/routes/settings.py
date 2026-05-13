"""Settings routes — API key configuration."""
import os
import re
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("cococat.routes.settings")

router = APIRouter(prefix="/api", tags=["settings"])

# Known API keys that can be configured via settings UI
KNOWN_KEYS = [
    {"name": "tavily", "env_key": "TAVILY_API_KEY", "label": "Tavily Search API"},
]


def _env_path() -> str:
    return os.environ.get("COCOCAT_ENV_FILE", ".env")


def _read_env() -> dict[str, str]:
    """Parse .env file into key-value dict."""
    path = _env_path()
    result = {}
    if not os.path.exists(path):
        return result
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _write_env(data: dict[str, str]) -> None:
    """Write key-value dict to .env file, preserving existing content."""
    path = _env_path()
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            original_lines = f.readlines()
    else:
        original_lines = []

    lines = []
    seen = set()
    for line in original_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in data:
                lines.append(f"{k}={data[k]}\n")
                seen.add(k)
                continue
            if k in existing:
                continue
        lines.append(line)

    # Add new keys not seen in original file
    for k, v in data.items():
        if k not in seen:
            lines.append(f"{k}={v}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


class SetKeyRequest(BaseModel):
    name: str
    value: str


@router.get("/settings")
async def get_settings():
    """Return API key status for known services."""
    env_vars = _read_env()

    keys = []
    for spec in KNOWN_KEYS:
        env_key = spec["env_key"]
        has_key = bool(env_vars.get(env_key) or os.environ.get(env_key))
        keys.append({
            "name": spec["name"],
            "env_key": env_key,
            "label": spec["label"],
            "has_key": has_key,
        })

    return {"keys": keys}


@router.put("/settings/key")
async def set_api_key(req: SetKeyRequest):
    """Save an API key to .env file."""
    spec = next((k for k in KNOWN_KEYS if k["name"] == req.name), None)
    if not spec:
        raise HTTPException(status_code=400, detail=f"Unknown key: {req.name}")

    env_key = spec["env_key"]
    _write_env({env_key: req.value})

    # Also set in current process env for immediate use
    os.environ[env_key] = req.value

    return {"saved": True, "name": req.name}
