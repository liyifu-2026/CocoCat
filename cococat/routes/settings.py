"""Settings routes — API key and workspace configuration."""
import os
import logging
import subprocess
import shutil

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
    """Return API key status and current workspace."""
    from cococat.core.workspace import WorkspaceManager
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

    ws = WorkspaceManager()
    return {
        "keys": keys,
        "workspace": str(ws.path),
    }


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


class SetWorkspaceRequest(BaseModel):
    value: str


@router.put("/settings/workspace")
async def set_workspace(req: SetWorkspaceRequest):
    """Save workspace path to .env and reload WorkspaceManager."""
    value = req.value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Workspace path is required")

    _write_env({"COCOCAT_WORKSPACE": value})
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
