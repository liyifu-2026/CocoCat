"""Channel lifecycle manager — owns connection state and connect/disconnect logic."""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
import random
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.context import AppContext

logger = logging.getLogger("cococat.channel_manager")

THINKING_MESSAGES = [
    "(Coco思考中...)",
    "(让我想想...)",
    "(整理思路中...)",
    "(Coco回复中...)",
    "(稍等一下~)",
    "(理解消息中...)",
    "(接收中...)",
    "(马上就好...)",
]


class ChannelManager:
    """Owns channel instances, status, and connect/disconnect/auto-reconnect logic.

    Route handlers delegate here — they no longer manage channel lifecycles directly.
    """

    def __init__(self):
        self._instances: dict[str, object] = {}
        self._status: dict[str, dict] = {}

    # ── query ────────────────────────────────────────────────

    def get_status(self, key: str) -> dict:
        return self._status.get(key, {})

    def get_instance(self, key: str):
        return self._instances.get(key)

    # ── connect ──────────────────────────────────────────────

    def connect(
        self,
        target_type: str,
        target_id: str,
        channel_type: str,
        config: dict,
        ctx: 'AppContext',
    ) -> dict:
        """Create, wire, and start a channel. Returns status dict."""
        from cococat.core.channels.factory import create_channel

        key = f"{target_type}:{target_id}:{channel_type}"

        old = self._instances.pop(key, None)
        if old:
            try:
                old.stop()
            except Exception:
                pass

        ch = create_channel(channel_type)
        self._instances[key] = ch

        if target_type == "scene":
            self._wire_scene(ch, target_id, channel_type, ctx)
        elif target_type == "main":
            self._wire_main(ch, channel_type, ctx, reuse_instance=False)

        success, _ = ch.wait_startup(timeout=0.5)
        status = "connected" if success else "connecting"

        if not success:
            self._watch_async(channel_type, key, ch)

        self._status[key] = {
            "status": status,
            "channel_type": channel_type,
            "connected_since": datetime.datetime.now().isoformat() if success else None,
            "message_count": 0,
        }
        return {"status": status}

    # ── disconnect ───────────────────────────────────────────

    def disconnect(self, target_type: str, target_id: str, channel_type: str) -> None:
        key = f"{target_type}:{target_id}:{channel_type}"
        self._status.pop(key, None)
        ch = self._instances.pop(key, None)
        if ch:
            try:
                ch.stop()
            except Exception:
                pass

    # ── auto-reconnect (startup) ─────────────────────────────

    def auto_reconnect(self, ctx: 'AppContext', loop) -> None:
        """Reconnect enabled channels with valid credentials on startup.
        
        Reconnects both global main channels and per-user personal channels.
        """
        from cococat.core.channels.factory import create_channel

        # ── Global main channels ──
        store = ctx.config_store
        if store:
            cfg = store.get_channel_configs()
        else:
            import yaml
            path = os.path.join("config", "main.yaml")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
            else:
                cfg = {}
        channels = cfg.get("channels", {})

        for ct, info in channels.items():
            if not info.get("enabled"):
                continue
            config = info.get("config", {})
            if not _channel_has_credentials(ct, config, str(ctx.config_store.agents_dir)):
                logger.info("Channel %s is enabled but has no credentials, skipping auto-reconnect", ct)
                continue

            key = f"main:main:{ct}"
            if key in self._instances:
                continue
            try:
                ch = create_channel(ct)
                self._instances[key] = ch
                self._wire_main(ch, ct, ctx, reuse_instance=True)
                ch.start("main", config)
                success, _ = ch.wait_startup(timeout=3)
                status = "connected" if success else "connecting"
                self._status[key] = {
                    "status": status,
                    "channel_type": ct,
                    "connected_since": datetime.datetime.now().isoformat() if success else None,
                    "message_count": 0,
                }
                if not success:
                    self._watch_async(ct, key, ch)
                logger.info("Auto-reconnected global channel: %s (status=%s)", ct, status)
            except Exception as e:
                logger.exception("Failed to auto-reconnect channel %s: %s", ct, e)

        # ── Per-user personal channels ──
        users_config_dir = "config/users"
        if not os.path.isdir(users_config_dir):
            return
        for username in os.listdir(users_config_dir):
            user_channels_path = os.path.join(users_config_dir, username, "channels.json")
            if not os.path.exists(user_channels_path):
                continue
            try:
                import json as _json
                with open(user_channels_path, encoding="utf-8") as f:
                    user_channels = _json.load(f)
            except Exception:
                continue

            for ct, info in (user_channels.get("channels", {}) or {}).items():
                if not info.get("enabled"):
                    continue
                config = info.get("config", {})
                key = f"{username}:main:null:{ct}"
                if key in self._instances:
                    continue
                try:
                    ch = create_channel(ct)
                    self._instances[key] = ch
                    self._wire_main(ch, ct, ctx, reuse_instance=True)
                    ch.start(username, config)
                    success, _ = ch.wait_startup(timeout=3)
                    status = "connected" if success else "connecting"
                    self._status[key] = {
                        "status": status,
                        "channel_type": ct,
                        "connected_since": datetime.datetime.now().isoformat() if success else None,
                        "message_count": 0,
                    }
                    if not success:
                        self._watch_async(ct, key, ch)
                    logger.info("Auto-reconnected %s's channel: %s (status=%s)", username, ct, status)
                except Exception as e:
                    logger.exception("Failed to auto-reconnect %s's channel %s: %s", username, ct, e)

    # ── internal wiring ──────────────────────────────────────

    def _wire_scene(self, ch, scene_id: str, channel_type: str, ctx: 'AppContext') -> None:
        from cococat.core.channels.context import Reply, ReplyType, Context, ContextType

        pool = ctx.pool
        bus = ctx.bus
        loop = asyncio.get_running_loop()

        def on_message(msg, scene_id=scene_id, ct=channel_type):
            async def _handle():
                agent = pool.get_scene_agent(scene_id)
                if not agent:
                    logger.warning("No agent bound to scene %s", scene_id)
                    return
                _send_thinking(ch, msg)
                reply_text = await agent.run(msg.content)
                reply = Reply(ReplyType.TEXT, reply_text)
                user_ctx = Context(ContextType.TEXT, msg.content,
                                   user_id=msg.user_id, scene_id=scene_id)
                ch.send(reply, user_ctx)
                await bus.publish("scene_message", {
                    "scene_id": scene_id,
                    "channel": ct,
                    "user_id": msg.user_id,
                    "content": msg.content,
                })
            _schedule_coro(_handle(), loop)

        ch.on_message = on_message
        ch.start(scene_id, {})

    def _wire_main(self, ch, channel_type: str, ctx: 'AppContext', reuse_instance: bool = False) -> None:
        from cococat.core.channels.context import Reply, ReplyType, Context, ContextType

        bus = ctx.bus
        sandbox_provider = ctx.sandbox_provider
        loop = asyncio.get_running_loop()

        def on_message(msg, ct=channel_type):
            async def _handle():
                try:
                    logger.info("Main channel handler: msg from %s/%s: %s",
                                ct, msg.user_id, msg.content[:50])
                    resolved = _resolve_channel_user(ctx, ct, msg.user_id)
                    if resolved:
                        ctx.user_id = resolved
                    _send_thinking(ch, msg)
                    reply_text = await sandbox_provider.run_once(msg.content, agent_id="main")
                    reply = Reply(ReplyType.TEXT, reply_text)
                    user_ctx = Context(ContextType.TEXT, msg.content,
                                       user_id=msg.user_id, receiver=msg.user_id)
                    ch.send(reply, user_ctx)
                    await bus.publish("main_message", {
                        "channel": ct,
                        "user_id": msg.user_id,
                        "content": msg.content,
                        "reply": reply_text,
                    })
                except Exception:
                    logger.exception("Main channel message handler failed for %s", ct)
            _schedule_coro(_handle(), loop)

        ch.on_message = on_message
        if not reuse_instance:
            ch.start("main", {})

    # ── internal helper ──────────────────────────────────────

    def _watch_async(self, channel_type: str, key: str, ch) -> None:
        def _watch():
            ok, err = ch.wait_startup(timeout=300)
            if ok:
                self._status[key] = {
                    "status": "connected",
                    "channel_type": channel_type,
                    "connected_since": datetime.datetime.now().isoformat(),
                    "message_count": 0,
                }
            else:
                self._status.pop(key, None)
                self._instances.pop(key, None)
                try:
                    ch.stop()
                except Exception:
                    pass
        threading.Thread(target=_watch, daemon=True).start()


# ── module-level helpers ─────────────────────────────────────

def _schedule_coro(coro, loop):
    try:
        asyncio.run_coroutine_threadsafe(coro, loop)
    except Exception:
        logger.warning("Cannot schedule coroutine")


def _send_thinking(ch, msg):
    text = random.choice(THINKING_MESSAGES)
    from cococat.core.channels.context import Reply, ReplyType, Context, ContextType
    thinking_reply = Reply(ReplyType.TEXT, text)
    thinking_ctx = Context(ContextType.TEXT, msg.content,
                           user_id=msg.user_id, receiver=msg.user_id)
    ch.send(thinking_reply, thinking_ctx)


def _channel_has_credentials(channel_type: str, config: dict, agents_dir: str = "agents") -> bool:
    import os
    if channel_type == "weixin":
        return os.path.exists(os.path.join(agents_dir, "_weixin_credentials.json"))
    if channel_type == "feishu":
        return bool(config.get("app_id") and config.get("app_secret"))
    if channel_type in ("telegram", "discord"):
        return bool(config.get("bot_token"))
    if channel_type == "wechat":
        return bool(config.get("app_id") and config.get("token"))
    return bool(config)


def _resolve_channel_user(ctx, channel_type: str, channel_user_id: str) -> str | None:
    """Look up channel_identities table to map channel sender to CocoCat user."""
    if not channel_user_id:
        return None
    db = getattr(ctx, 'db', None)
    if not db:
        return None
    try:
        row = db._conn.execute(
            "SELECT user_id FROM channel_identities WHERE channel_type = ? AND channel_user_id = ?",
            (channel_type, channel_user_id),
        ).fetchone()
        return row["user_id"] if row else None
    except Exception:
        return None
