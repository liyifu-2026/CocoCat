"""Channel management routes — thin delegation to ChannelManager."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext

logger = logging.getLogger("cococat.routes.channels")
router = APIRouter(prefix="/api/channels", tags=["channels"])


class ChannelConnect(BaseModel):
    target_type: str
    target_id: str
    channel_type: str
    config: dict = {}
    user_id: str = ""


class MainChannelConfig(BaseModel):
    channel_type: str
    config: dict = {}


CHANNEL_TYPES = [
    {
        "channel_type": "feishu",
        "display_name": "飞书",
        "english_name": "Feishu / Lark",
        "description": "飞书机器人，支持富文本卡片、流式输出、多线程对话",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video", "sticker", "link", "post"],
            "send": ["text", "card", "image", "voice", "file", "video"],
            "streaming": True, "cards": True, "reactions": True, "threads": True,
        },
        "config_fields": [
            {"key": "app_id", "label": "App ID", "required": True, "type": "text", "placeholder": "cli_a6b..."},
            {"key": "app_secret", "label": "App Secret", "required": True, "type": "password", "placeholder": ""},
        ],
        "notes": "", "icon_type": "hand",
    },
    {
        "channel_type": "wechat",
        "display_name": "微信公众",
        "english_name": "WeChat Official",
        "description": "微信公众号，通过被动回复 XML 消息与用户交互",
        "capabilities": {
            "receive": ["text", "image", "voice", "location", "link", "event"],
            "send": ["text", "image", "voice", "card"],
            "streaming": False, "cards": True, "reactions": False, "threads": False,
        },
        "config_fields": [
            {"key": "app_id", "label": "App ID", "required": True, "type": "text", "placeholder": "wxXXXXXXXXXXXXXXXX"},
            {"key": "token", "label": "Token", "required": True, "type": "text", "placeholder": "从微信后台获取"},
            {"key": "encoding_aes_key", "label": "Encoding AES Key", "required": False, "type": "text", "placeholder": "消息加解密密钥（可选）"},
        ],
        "notes": "需要公网 IP 和已备案域名以接收微信回调", "icon_type": "simple",
    },
    {
        "channel_type": "weixin",
        "display_name": "个人微信",
        "english_name": "iLink Bot",
        "description": "个人微信机器人，通过 ilink 接口实现消息收发，扫码登录无需手动填配置",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video", "sticker"],
            "send": ["text", "image", "file", "video", "card"],
            "streaming": False, "cards": True, "reactions": False, "threads": False,
        },
        "config_fields": [],
        "notes": "自动通过二维码扫码登录，无需手动填写凭证", "icon_type": "hand",
    },
    {
        "channel_type": "telegram",
        "display_name": "Telegram",
        "english_name": "Telegram Bot",
        "description": "Telegram Bot，通过 Bot API 收发消息，支持 Markdown 格式",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video", "sticker"],
            "send": ["text", "image", "file", "video"],
            "streaming": False, "cards": False, "reactions": False, "threads": False,
        },
        "config_fields": [
            {"key": "bot_token", "label": "Bot Token", "required": True, "type": "password", "placeholder": "从 @BotFather 获取"},
        ],
        "notes": "", "icon_type": "simple",
    },
    {
        "channel_type": "discord",
        "display_name": "Discord",
        "english_name": "Discord Bot",
        "description": "Discord 机器人，支持频道消息收发和 Embed 卡片",
        "capabilities": {
            "receive": ["text", "image", "voice", "file", "video"],
            "send": ["text", "image", "file", "video", "card"],
            "streaming": False, "cards": True, "reactions": False, "threads": False,
        },
        "config_fields": [
            {"key": "bot_token", "label": "Bot Token", "required": True, "type": "password", "placeholder": "从 Discord Developer Portal 获取"},
        ],
        "notes": "", "icon_type": "simple",
    },
    {
        "channel_type": "web_api",
        "display_name": "Web API",
        "english_name": "HTTP REST",
        "description": "通用 HTTP API 渠道，通过 REST 接口收发消息，可用于嵌入第三方应用",
        "capabilities": {
            "receive": ["text"],
            "send": ["text"],
            "streaming": False, "cards": False, "reactions": False, "threads": False,
        },
        "config_fields": [
            {"key": "endpoint", "label": "Endpoint URL", "required": True, "type": "text", "placeholder": "https://example.com/api/chat"},
            {"key": "api_key", "label": "API Key", "required": False, "type": "password", "placeholder": "可选认证密钥"},
        ],
        "notes": "", "icon_type": "hand",
    },
]


# ── routes ───────────────────────────────────────────────────

@router.get("")
async def list_channels(ctx: AppContext = Depends(get_ctx)):
    from cococat.scene.config import list_scenes as list_scene_configs
    mgr = ctx.channel_manager

    result = []
    for config in list_scene_configs():
        for ch in config.channels:
            key = f"scene:{config.id}:{ch['type']}"
            result.append({
                "target_type": "scene",
                "target_id": config.id,
                "channel_type": ch["type"],
                "status": mgr.get_status(key).get("status", "stopped") if mgr else "stopped",
            })
    return {"channels": result}


@router.get("/main")
async def list_main_channels(ctx: AppContext = Depends(get_ctx)):
    mgr = ctx.channel_manager
    store = ctx.config_store
    channels = store.get_channel_configs().get("channels", {}) if store else {}
    result = []

    for ct, info in channels.items():
        key = f"main:main:{ct}"
        status = mgr.get_status(key).get("status", "stopped") if mgr else "stopped"
        if status == "connected":
            ch_status = "connected"
        elif status == "connecting":
            ch_status = "connecting"
        elif info.get("enabled"):
            ch_status = "configured"
        else:
            ch_status = "unconfigured"
        display_name = ct
        for t in CHANNEL_TYPES:
            if t["channel_type"] == ct:
                display_name = t["display_name"]
                break
        result.append({
            "channel_type": ct,
            "display_name": display_name,
            "enabled": info.get("enabled", False),
            "status": ch_status,
            "connected_since": mgr.get_status(key).get("connected_since") if mgr else None,
            "message_count": mgr.get_status(key).get("message_count", 0) if mgr else 0,
        })
    return {"channels": result}


@router.post("/main/config")
async def save_main_channel_config(body: MainChannelConfig, ctx: AppContext = Depends(get_ctx)):
    store = ctx.config_store
    cfg = store.get_channel_configs()
    if "channels" not in cfg:
        cfg["channels"] = {}
    channels = cfg["channels"]
    if body.channel_type not in channels:
        channels[body.channel_type] = {"enabled": False, "config": {}}
    channels[body.channel_type]["config"] = body.config
    channels[body.channel_type]["enabled"] = True
    store.save_channel_configs(cfg)
    return {"status": "ok"}


@router.post("/connect")
async def connect_channel(body: ChannelConnect, ctx: AppContext = Depends(get_ctx)):
    mgr = ctx.channel_manager
    try:
        return mgr.connect(body.target_type, body.target_id, body.channel_type, body.config, ctx, user_id=body.user_id or ctx.user_id or "")
    except Exception as e:
        logger.exception("Failed to connect channel %s", body.channel_type)
        return {"status": "error", "error": str(e)}


@router.post("/disconnect")
async def disconnect_channel(body: ChannelConnect, ctx: AppContext = Depends(get_ctx)):
    mgr = ctx.channel_manager
    store = ctx.config_store
    mgr.disconnect(body.target_type, body.target_id, body.channel_type, user_id=body.user_id or ctx.user_id or "")

    if body.target_type == "main":
        cfg = store.get_channel_configs()
        channels = cfg.get("channels", {})
        if body.channel_type in channels:
            channels[body.channel_type]["enabled"] = False
            store.save_channel_configs(cfg)

    return {"status": "disconnected"}


@router.get("/types")
async def list_channel_types():
    return {"types": CHANNEL_TYPES}


@router.get("/qr/{channel_type}")
async def get_qr_state(channel_type: str):
    if channel_type != "weixin":
        return {"error": "QR login only supported for weixin"}
    try:
        from cococat.core.channels.weixin import get_qr_state as _get_qr
        return _get_qr()
    except ImportError:
        return {"error": "weixin module not available"}
