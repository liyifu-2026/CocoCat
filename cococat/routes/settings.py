"""Settings routes — API key and workspace configuration."""
import os
import logging
import subprocess
import shutil

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext

logger = logging.getLogger("cococat.routes.settings")

router = APIRouter(prefix="/api", tags=["settings"])

# Known API keys that can be configured via settings UI
KNOWN_KEYS = [
    {"name": "tavily", "env_key": "TAVILY_API_KEY", "label": "Tavily Search API"},
]


class SetKeyRequest(BaseModel):
    name: str
    value: str


@router.get("/settings")
async def get_settings(ctx: AppContext = Depends(get_ctx)):
    """Return API key status, max iterations, and current workspace."""
    from cococat.core.workspace import WorkspaceManager
    store = ctx.config_store
    env_vars = store.env_keys() if store else {}

    keys = []
    for spec in KNOWN_KEYS:
        env_key = spec["env_key"]
        has_key = bool(env_vars.get(env_key) or os.environ.get(env_key))
        if not has_key and store:
            has_key = bool(store.get_auth(spec["name"]))
        keys.append({
            "name": spec["name"],
            "env_key": env_key,
            "label": spec["label"],
            "has_key": has_key,
        })

    ws = WorkspaceManager()
    max_iter = int(os.environ.get("COCOCAT_MAX_ITERATIONS", "30"))
    return {
        "keys": keys,
        "workspace": str(ws.path),
        "max_iterations": max_iter,
    }


@router.put("/settings/key")
async def set_api_key(req: SetKeyRequest, ctx: AppContext = Depends(get_ctx)):
    """Save an API key to .env file."""
    spec = next((k for k in KNOWN_KEYS if k["name"] == req.name), None)
    if not spec:
        raise HTTPException(status_code=400, detail=f"Unknown key: {req.name}")

    env_key = spec["env_key"]
    if ctx.config_store:
        ctx.config_store.set_env(env_key, req.value)
    os.environ[env_key] = req.value

    return {"saved": True, "name": req.name}


class SetWorkspaceRequest(BaseModel):
    value: str


class SetMaxIterationsRequest(BaseModel):
    value: int


@router.put("/settings/max-iterations")
async def set_max_iterations(req: SetMaxIterationsRequest, ctx: AppContext = Depends(get_ctx)):
    """Save max iterations to .env file."""
    if req.value < 1:
        raise HTTPException(status_code=400, detail="Must be >= 1")
    val = str(req.value)
    if ctx.config_store:
        ctx.config_store.set_env("COCOCAT_MAX_ITERATIONS", val)
    os.environ["COCOCAT_MAX_ITERATIONS"] = val
    return {"saved": True, "max_iterations": req.value}


@router.put("/settings/workspace")
async def set_workspace(req: SetWorkspaceRequest, ctx: AppContext = Depends(get_ctx)):
    """Save workspace path to .env and reload WorkspaceManager."""
    value = req.value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Workspace path is required")

    if ctx.config_store:
        ctx.config_store.set_env("COCOCAT_WORKSPACE", value)
    os.environ["COCOCAT_WORKSPACE"] = value

    from cococat.core.workspace import WorkspaceManager
    WorkspaceManager().reload()

    return {"saved": True, "workspace": value}


def _open_folder_picker() -> str | None:
    """Open a native folder picker dialog. Returns path or None if cancelled."""
    # Try tkinter first (available on most Python installs)
    try:
        import tkinter.filedialog
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = tkinter.filedialog.askdirectory(title="选择工作区目录")
        root.destroy()
        if path:
            return path
        return None
    except Exception:
        pass

    # Fallback: zenity on Linux
    if shutil.which("zenity"):
        r = subprocess.run(
            ["zenity", "--file-selection", "--directory", "--title=选择工作区目录"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return r.stdout.strip()
        return None

    # Fallback: kdialog on KDE
    if shutil.which("kdialog"):
        r = subprocess.run(
            ["kdialog", "--getexistingdirectory"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return r.stdout.strip()
        return None

    # Fallback: osascript on macOS
    if shutil.which("osascript"):
        r = subprocess.run(
            ["osascript", "-e",
             'POSIX path of (choose folder with prompt "选择工作区目录")'],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return r.stdout.strip()
        return None

    return None


@router.post("/settings/workspace/picker")
async def pick_workspace():
    """Open native folder picker and return selected path."""
    path = _open_folder_picker()
    return {"path": path}
