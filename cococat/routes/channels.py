"""Channel management routes."""
import json
import os
import sys
import yaml
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext

router = APIRouter(prefix="/api/channels", tags=["channels"])


CHANNEL_FACTORY_PATH = os.environ.get("CHANNEL_FACTORY_PATH", "py-agent")


def _get_channel_factory():
    """Lazily load channel_factory from the configured path."""
    factory_path = CHANNEL_FACTORY_PATH
    if factory_path not in sys.path:
        sys.path.insert(0, factory_path)
    try:
        from channels.channel_factory import create_channel
        return create_channel
    except ImportError as e:
        raise RuntimeError(
            f"Cannot import channel_factory from '{factory_path}'. "
            f"Set CHANNEL_FACTORY_PATH or ensure py-agent is installed."
        ) from e


class ChannelConnect(BaseModel):
    target_type: str  # "scene" or "main"
    target_id: str
    channel_type: str
    config: dict = {}


class MainChannelConfig(BaseModel):
    channel_type: str
    config: dict = {}


CHANNEL_STATUS: dict[str, dict] = {}

# ── Channel type metadata (static) ──

CHANNEL_TYPES = [
    {
        "channel_type": "feishu",
        "display_name": "飞书",
        "english_name": "Feishu / Lark",
        "description": "飞书机器人，支持富文本卡片、流式输出、多线程对话",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video", "sticker", "link", "post"],
            "send": ["text", "card", "image", "voice", "file", "video"],
            "streaming": True,
            "cards": True,
            "reactions": True,
            "threads": True,
        },
        "config_fields": [
            {"key": "app_id", "label": "App ID", "required": True, "type": "text", "placeholder": "cli_a6b..."},
            {"key": "app_secret", "label": "App Secret", "required": True, "type": "password", "placeholder": ""},
        ],
        "notes": "",
        "icon_type": "hand",
    },
    {
        "channel_type": "wechat",
        "display_name": "微信公众",
        "english_name": "WeChat Official",
        "description": "微信公众号，通过被动回复 XML 消息与用户交互",
        "capabilities": {
            "receive": ["text", "image", "voice", "location", "link", "event"],
            "send": ["text", "image", "voice", "card"],
            "streaming": False,
            "cards": True,
            "reactions": False,
            "threads": False,
        },
        "config_fields": [
            {"key": "app_id", "label": "App ID", "required": True, "type": "text", "placeholder": "wxXXXXXXXXXXXXXXXX"},
            {"key": "token", "label": "Token", "required": True, "type": "text", "placeholder": "从微信后台获取"},
            {"key": "encoding_aes_key", "label": "Encoding AES Key", "required": False, "type": "text", "placeholder": "消息加解密密钥（可选）"},
        ],
        "notes": "需要公网 IP 和已备案域名以接收微信回调",
        "icon_type": "simple",
    },
    {
        "channel_type": "weixin",
        "display_name": "个人微信",
        "english_name": "iLink Bot",
        "description": "个人微信机器人，通过 ilink 接口实现消息收发，扫码登录无需手动填配置",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video", "sticker"],
            "send": ["text", "image", "file", "video", "card"],
            "streaming": False,
            "cards": True,
            "reactions": False,
            "threads": False,
        },
        "config_fields": [],
        "notes": "自动通过二维码扫码登录，无需手动填写凭证",
        "icon_type": "hand",
    },
    {
        "channel_type": "telegram",
        "display_name": "Telegram",
        "english_name": "Telegram Bot",
        "description": "Telegram Bot，通过 Bot API 收发消息，支持 Markdown 格式",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video", "sticker"],
            "send": ["text", "image", "file", "video"],
            "streaming": False,
            "cards": False,
            "reactions": False,
            "threads": False,
        },
        "config_fields": [
            {"key": "bot_token", "label": "Bot Token", "required": True, "type": "password", "placeholder": "从 @BotFather 获取"},
        ],
        "notes": "",
        "icon_type": "simple",
    },
    {
        "channel_type": "discord",
        "display_name": "Discord",
        "english_name": "Discord Bot",
        "description": "Discord 机器人，支持频道消息收发和 Embed 卡片",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video"],
            "send": ["text", "image", "file", "video", "card"],
            "streaming": False,
            "cards": True,
            "reactions": False,
            "threads": False,
        },
        "config_fields": [
            {"key": "bot_token", "label": "Bot Token", "required": True, "type": "password", "placeholder": "从 Discord Developer Portal 获取"},
        ],
        "notes": "",
        "icon_type": "simple",
    },
    {
        "channel_type": "web_api",
        "display_name": "Web API",
        "english_name": "HTTP REST",
        "description": "通用 HTTP API 渠道，通过 REST 接口收发消息，可用于嵌入第三方应用",
        "capabilities": {
            "receive": ["text"],
            "send": ["text"],
            "streaming": False,
            "cards": False,
            "reactions": False,
            "threads": False,
        },
        "config_fields": [
            {"key": "endpoint", "label": "Endpoint URL", "required": True, "type": "text", "placeholder": "https://example.com/api/chat"},
            {"key": "api_key", "label": "API Key", "required": False, "type": "password", "placeholder": "可选认证密钥"},
        ],
        "notes": "",
        "icon_type": "hand",
    },
]

MAIN_CONFIG_PATH = os.path.join("config", "main.yaml")


def _load_main_config() -> dict:
    """Load main.yaml channel config."""
    if not os.path.exists(MAIN_CONFIG_PATH):
        return {"channels": {}}
    with open(MAIN_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"channels": {}}


def _save_main_config(data: dict):
    """Write main.yaml channel config."""
    os.makedirs(os.path.dirname(MAIN_CONFIG_PATH), exist_ok=True)
    with open(MAIN_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)


@router.get("")
async def list_channels():
    """List all configured channels."""
    result = []
    scenes_dir = "scenes"
    if os.path.isdir(scenes_dir):
        for scene_id in os.listdir(scenes_dir):
            path = os.path.join(scenes_dir, scene_id, "scene.yaml")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for ch in data.get("channels", []):
                key = f"scene:{scene_id}:{ch['type']}"
                result.append({
                    "target_type": "scene",
                    "target_id": scene_id,
                    "channel_type": ch["type"],
                    "status": CHANNEL_STATUS.get(key, {}).get("status", "stopped"),
                })

    return {"channels": result}


@router.get("/main")
async def list_main_channels():
    """List Main AI configured channels with runtime status."""
    cfg = _load_main_config()
    channels = cfg.get("channels", {})
    result = []

    for ct, info in channels.items():
        key = f"main:main:{ct}"
        status = CHANNEL_STATUS.get(key, {}).get("status", "stopped")
        display_name = ct
        for t in CHANNEL_TYPES:
            if t["channel_type"] == ct:
                display_name = t["display_name"]
                break
        result.append({
            "channel_type": ct,
            "display_name": display_name,
            "enabled": info.get("enabled", False),
            "status": "connected" if status == "connected" else (
                "configured" if info.get("config") else "unconfigured"
            ),
            "connected_since": CHANNEL_STATUS.get(key, {}).get("connected_since"),
            "message_count": CHANNEL_STATUS.get(key, {}).get("message_count", 0),
        })

    return {"channels": result}


@router.post("/main/config")
async def save_main_channel_config(body: MainChannelConfig):
    """Save or update a channel's configuration in main.yaml."""
    cfg = _load_main_config()
    if "channels" not in cfg:
        cfg["channels"] = {}
    channels = cfg["channels"]

    if body.channel_type not in channels:
        channels[body.channel_type] = {"enabled": False, "config": {}}

    channels[body.channel_type]["config"] = body.config
    channels[body.channel_type]["enabled"] = bool(body.config)

    _save_main_config(cfg)
    return {"status": "ok"}


@router.post("/connect")
async def connect_channel(body: ChannelConnect, ctx: AppContext = Depends(get_ctx)):
    """Connect/start a channel."""
    key = f"{body.target_type}:{body.target_id}:{body.channel_type}"

    try:
        create_channel = _get_channel_factory()
        ch = create_channel(body.channel_type)

        if body.target_type == "scene":
            pool = ctx.pool
            bus = ctx.bus

            async def route(msg, scene_id=body.target_id, ct=body.channel_type):
                agent = pool.get_scene_agent(scene_id)
                if agent:
                    reply = await agent.run(msg.content)
                    await ch.send(reply, msg.user_id)
                await bus.publish("scene_message", {
                    "scene_id": scene_id,
                    "channel": ct,
                    "user_id": msg.user_id,
                    "content": msg.content,
                })

            ch.on_message = route
            ch.start(body.target_id, body.config)

        CHANNEL_STATUS[key] = {"status": "connected", "channel_type": body.channel_type}
        return {"status": "connected"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/disconnect")
async def disconnect_channel(body: ChannelConnect):
    """Disconnect/stop a channel."""
    key = f"{body.target_type}:{body.target_id}:{body.channel_type}"
    CHANNEL_STATUS.pop(key, None)
    return {"status": "disconnected"}


@router.get("/types")
async def list_channel_types():
    """Return metadata for all supported channel types."""
    return {"types": CHANNEL_TYPES}
