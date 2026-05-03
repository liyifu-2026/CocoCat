"""Entry configuration routes for scenes."""
import json
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


@router.get("/api/scenes/{scene_id}/entries")
def get_scene_entries(scene_id: str):
    """Get scene's entry configuration."""
    entries_path = BASE_DIR / "scenes" / scene_id / "entries.json"
    if not entries_path.exists():
        return {"entries": []}
    try:
        return json.loads(entries_path.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": []}


@router.put("/api/scenes/{scene_id}/entries")
def update_scene_entries(scene_id: str, body: dict):
    """Update scene's entry configuration."""
    scene_dir = BASE_DIR / "scenes" / scene_id
    if not scene_dir.exists():
        return JSONResponse({"error": "scene not found"}, status_code=404)
    entries_path = scene_dir / "entries.json"
    entries = body.get("entries", [])
    entries_path.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "updated", "entries": entries}


@router.get("/api/channels")
def list_available_channels():
    """List all available channel types with their config schema."""
    return {
        "channels": [
            {
                "id": "web_api",
                "name": "Web API",
                "description": "HTTP API endpoint for programmatic access",
                "config_schema": {
                    "endpoint": {"type": "string", "description": "API endpoint path", "default": "/api/scenes/{scene_id}/chat"}
                }
            },
            {
                "id": "wechat",
                "name": "WeChat Official Account",
                "description": "WeChat Official Account webhook integration",
                "config_schema": {
                    "token": {"type": "string", "description": "WeChat verification token", "default": ""},
                    "app_id": {"type": "string", "description": "WeChat App ID", "default": ""},
                    "app_secret": {"type": "string", "description": "WeChat App Secret", "default": ""}
                }
            },
            {
                "id": "weixin",
                "name": "Personal WeChat",
                "description": "Personal WeChat via ilink bot API",
                "config_schema": {
                    "app_id": {"type": "string", "description": "WeChat app ID", "default": ""},
                    "token": {"type": "string", "description": "Access token", "default": ""}
                }
            },
            {
                "id": "feishu",
                "name": "Feishu",
                "description": "Feishu (飞书) integration via WebSocket",
                "config_schema": {
                    "app_id": {"type": "string", "description": "Feishu app ID", "default": ""},
                    "app_secret": {"type": "string", "description": "Feishu app secret", "default": ""}
                }
            }
        ]
    }
