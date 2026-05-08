"""Entry configuration routes for channels — scenes and agents."""
import json
import os
import sys
import threading
from pathlib import Path
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "py-agent"))

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ── Scene entries ──────────────────────────────────────────────────────

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


# ── Agent entries ──────────────────────────────────────────────────────

@router.get("/api/agents/{agent_id}/entries")
def get_agent_entries(agent_id: str):
    """Get agent's entry configuration."""
    entries_path = BASE_DIR / "agents" / agent_id / "entries.json"
    if not entries_path.exists():
        return {"entries": []}
    try:
        return json.loads(entries_path.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": []}


@router.put("/api/agents/{agent_id}/entries")
def update_agent_entries(agent_id: str, body: dict):
    """Update agent's entry configuration."""
    agent_dir = BASE_DIR / "agents" / agent_id
    if not agent_dir.exists():
        return JSONResponse({"error": "agent not found"}, status_code=404)
    entries_path = agent_dir / "entries.json"
    entries = body.get("entries", [])
    entries_path.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "updated", "entries": entries}


# ── Channel connect/disconnect ─────────────────────────────────────────

CHANNEL_STATUS_CACHE: dict[str, dict] = {}


class ChannelConnectRequest(BaseModel):
    target_type: str  # "scene" or "agent"
    target_id: str
    channel_type: str
    config: dict = {}


@router.post("/api/channels/connect")
def connect_channel(body: ChannelConnectRequest):
    """Start a channel and bind it to a scene or agent."""
    from channels.channel_factory import create_channel, register_channel
    from scene_manager import SceneManager

    try:
        ch = create_channel(body.channel_type)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    # Set up on_message and start
    qr_login = getattr(ch, "channel_type", "") == "weixin"

    if body.target_type == "scene":
        mgr = SceneManager()
        runtime = mgr.get_or_create(body.target_id)
        if runtime is None:
            return JSONResponse({"error": "scene not found"}, status_code=404)
        reply_url = os.environ.get("COCOCAT_REPLY_URL", "http://localhost:8080/api/channels/reply")

        from web.entry_manager import _route_to_scene
        ch.on_message = lambda msg, rt=runtime, ct=body.channel_type: _route_to_scene(
            rt, ct, msg.user_id, msg.content
        )

        if qr_login:
            t = threading.Thread(target=lambda: ch.start(body.target_id, body.config), daemon=True)
            t.start()
        else:
            ch.start(body.target_id, body.config)

        runtime.channels.append(ch)

        _append_entry(body.target_type, body.target_id, body.channel_type, body.config)

        CHANNEL_STATUS_CACHE[f"scene:{body.target_id}:{body.channel_type}"] = {
            "status": "connecting" if qr_login else "connected", "channel_type": body.channel_type
        }
        return {"status": "connecting" if qr_login else "connected", "target_type": "scene", "target_id": body.target_id}

    elif body.target_type == "agent":
        from web.entry_manager import register_agent_channel, _route_to_agent
        ch.on_message = lambda msg, aid=body.target_id, ct=body.channel_type: _route_to_agent(
            aid, ct, msg.user_id, msg.content
        )

        if qr_login:
            t = threading.Thread(target=lambda: ch.start(body.target_id, body.config), daemon=True)
            t.start()
        else:
            ch.start(body.target_id, body.config)

        register_agent_channel(body.channel_type, body.target_id, ch)

        _append_entry(body.target_type, body.target_id, body.channel_type, body.config)

        CHANNEL_STATUS_CACHE[f"agent:{body.target_id}:{body.channel_type}"] = {
            "status": "connecting" if qr_login else "connected", "channel_type": body.channel_type
        }
        return {"status": "connecting" if qr_login else "connected", "target_type": "agent", "target_id": body.target_id}

    else:
        return JSONResponse({"error": f"unknown target_type: {body.target_type}"}, status_code=400)


@router.post("/api/channels/disconnect")
def disconnect_channel(body: ChannelConnectRequest):
    """Stop and disconnect a channel from a scene or agent."""
    cache_key = f"{body.target_type}:{body.target_id}:{body.channel_type}"
    ch = CHANNEL_STATUS_CACHE.pop(cache_key, None)

    if body.target_type == "scene":
        from scene_manager import SceneManager
        mgr = SceneManager()
        runtime = mgr.get_runtime(body.target_id)
        if runtime:
            for c in list(runtime.channels):
                if getattr(c, "channel_type", "") == body.channel_type:
                    try:
                        c.stop()
                    except Exception:
                        pass
                    runtime.channels.remove(c)

    elif body.target_type == "agent":
        from web.entry_manager import get_agent_channel
        ch = get_agent_channel(body.channel_type, body.target_id)
        if ch:
            try:
                ch.stop()
            except Exception:
                pass

    _remove_entry(body.target_type, body.target_id, body.channel_type)
    return {"status": "disconnected"}


@router.get("/api/channels/{target_type}/{target_id}/{channel_type}/status")
def get_channel_status(target_type: str, target_id: str, channel_type: str):
    """Get the connection status of a channel (auto-refreshes cache from runtime)."""
    if target_type == "scene":
        from scene_manager import SceneManager
        mgr = SceneManager()
        runtime = mgr.get_runtime(target_id)
        if runtime:
            for ch in runtime.channels:
                if getattr(ch, "channel_type", "") == channel_type:
                    running = ch.is_running() if hasattr(ch, "is_running") else bool(getattr(ch, "_running", False))
                    status = "connected" if running else "connecting"
                    cache_key = f"{target_type}:{target_id}:{channel_type}"
                    CHANNEL_STATUS_CACHE[cache_key] = {"status": status, "channel_type": channel_type}
                    return {"status": status, "channel_type": channel_type, "connected": running}
        return {"status": "disconnected", "channel_type": channel_type, "connected": False}

    elif target_type == "agent":
        from web.entry_manager import get_agent_channel
        ch = get_agent_channel(channel_type, target_id)
        if ch:
            running = ch.is_running() if hasattr(ch, "is_running") else bool(getattr(ch, "_running", False))
            status = "connected" if running else "connecting"
            cache_key = f"{target_type}:{target_id}:{channel_type}"
            CHANNEL_STATUS_CACHE[cache_key] = {"status": status, "channel_type": channel_type}
            return {"status": status, "channel_type": channel_type, "connected": running}
        return {"status": "disconnected", "channel_type": channel_type, "connected": False}

    return JSONResponse({"error": "unknown target_type"}, status_code=400)


# ── WeChat QR login ────────────────────────────────────────────────────

@router.get("/api/channels/weixin/qr")
def get_weixin_qr_code():
    """Get WeChat QR code as a data URI image for web display."""
    try:
        from channels.weixin import WeixinApi
        import qrcode
        import io
        import base64

        api = WeixinApi()
        qr_data = api.fetch_qr()
        qrcode_content = qr_data.get("qrcode", "") or qr_data.get("qrcode_img_content", "")

        if not qrcode_content:
            return JSONResponse({"error": "Failed to get QR code from WeChat API"}, status_code=500)

        # Generate QR code image from the content string
        qr = qrcode.QRCode(border=2)
        qr.add_data(qrcode_content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        data_uri = f"data:image/png;base64,{img_b64}"

        return {
            "qrcode_url": data_uri,
            "qrcode": qrcode_content,
        }
    except Exception as e:
        return JSONResponse({"error": f"Failed to get QR code: {e}"}, status_code=500)


# ── Available channel types ────────────────────────────────────────────

@router.get("/api/channels")
def list_available_channels():
    """List all available channel types with their config schema."""
    return {
        "channels": CHANNEL_DEFINITIONS
    }


# ── Helpers ────────────────────────────────────────────────────────────

CHANNEL_DEFINITIONS = [
    {
        "id": "web_api",
        "name": "Web API",
        "description": "HTTP API endpoint for programmatic access",
        "config_fields": [
            {"key": "endpoint", "label": "Endpoint", "type": "text", "default": "/api/scenes/{scene_id}/chat"}
        ]
    },
    {
        "id": "weixin",
        "name": "Personal WeChat",
        "description": "Personal WeChat via ilink bot API (QR code login)",
        "config_fields": [],
        "needs_qr_login": True
    },
    {
        "id": "feishu",
        "name": "Feishu",
        "description": "Feishu (飞书) integration via WebSocket",
        "config_fields": [
            {"key": "app_id", "label": "App ID", "type": "text"},
            {"key": "app_secret", "label": "App Secret", "type": "secret"},
        ]
    },
    {
        "id": "telegram",
        "name": "Telegram",
        "description": "Telegram Bot via Bot API polling",
        "config_fields": [
            {"key": "bot_token", "label": "Bot Token", "type": "secret"}
        ]
    },
    {
        "id": "discord",
        "name": "Discord",
        "description": "Discord bot via discord.py",
        "config_fields": [
            {"key": "bot_token", "label": "Bot Token", "type": "secret"}
        ]
    },
]


def _append_entry(target_type: str, target_id: str, channel_type: str, config: dict):
    """Add a channel entry to the target's entries.json."""
    if target_type == "scene":
        entries_path = BASE_DIR / "scenes" / target_id / "entries.json"
    elif target_type == "agent":
        entries_path = BASE_DIR / "agents" / target_id / "entries.json"
    else:
        return

    current = {"entries": []}
    if entries_path.exists():
        try:
            current = json.loads(entries_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    current["entries"] = [e for e in current.get("entries", [])
                          if e.get("channel") != channel_type]
    current["entries"].append({"channel": channel_type, "enabled": True, "config": config})
    entries_path.parent.mkdir(parents=True, exist_ok=True)
    entries_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def _remove_entry(target_type: str, target_id: str, channel_type: str):
    """Remove a channel entry from the target's entries.json."""
    if target_type == "scene":
        entries_path = BASE_DIR / "scenes" / target_id / "entries.json"
    elif target_type == "agent":
        entries_path = BASE_DIR / "agents" / target_id / "entries.json"
    else:
        return

    if not entries_path.exists():
        return
    try:
        current = json.loads(entries_path.read_text(encoding="utf-8"))
        current["entries"] = [e for e in current.get("entries", [])
                              if e.get("channel") != channel_type]
        entries_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
