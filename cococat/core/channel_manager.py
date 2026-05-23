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
        user_id: str = "",
    ) -> dict:
        """Create, wire, and start a channel. Returns status dict.
        
        user_id: optional CocoCat username for personal channels (e.g. 'alice').
                 When set, key format is {user_id}:{target_type}:{target_id}:{channel_type}.
        """
        from cococat.core.channels.factory import create_channel

        prefix = f"{user_id}:" if user_id else ""
        key = f"{prefix}{target_type}:{target_id}:{channel_type}"

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

        status = self._start_and_status(key, ch, channel_type, timeout=0.5)

        return {"status": status}

    # ── disconnect ───────────────────────────────────────────

    def disconnect(self, target_type: str, target_id: str, channel_type: str, user_id: str = "") -> None:
        prefix = f"{user_id}:" if user_id else ""
        key = f"{prefix}{target_type}:{target_id}:{channel_type}"
        self._status.pop(key, None)
        ch = self._instances.pop(key, None)
        if ch:
            try:
                ch.stop()
            except Exception:
                pass

    # ── auto-reconnect (startup) ─────────────────────────────

    async def auto_reconnect(self, ctx: 'AppContext') -> None:
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
                status = self._start_and_status(key, ch, ct, timeout=3)
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
                    status = self._start_and_status(key, ch, ct, timeout=3)
                    logger.info("Auto-reconnected %s's channel: %s (status=%s)", username, ct, status)
                except Exception as e:
                    logger.exception("Failed to auto-reconnect %s's channel %s: %s", username, ct, e)

    # ── internal wiring ──────────────────────────────────────

    def _make_handler(
        self, ch, get_reply_fn, ctx: 'AppContext', *,
        scene_id: str = "default", channel_type: str = "",
    ):
        """Create an on_message handler: thinking → get_reply → send → publish."""
        from cococat.core.channels.context import Reply, ReplyType, Context, ContextType

        bus = ctx.bus
        loop = asyncio.get_running_loop()

        def on_message(msg):
            async def _handle():
                _send_thinking(ch, msg)
                reply_text = await get_reply_fn(msg)
                if reply_text is None:
                    return
                reply = Reply(ReplyType.TEXT, reply_text)
                user_ctx = Context(ContextType.TEXT, msg.content,
                                   user_id=msg.user_id, receiver=msg.user_id)
                ch.send(reply, user_ctx)
                await bus.publish("scene_message", {
                    "scene_id": scene_id,
                    "channel": channel_type,
                    "user_id": msg.user_id,
                    "content": msg.content,
                })
            _schedule_coro(_handle(), loop)

        return on_message

    def _start_and_status(self, key: str, ch, channel_type: str, timeout: float = 3.0) -> str:
        """Start a channel and record its status. Returns 'connected' or 'connecting'."""
        success, _ = ch.wait_startup(timeout=timeout)
        status = "connected" if success else "connecting"

        self._status[key] = {
            "status": status,
            "channel_type": channel_type,
            "connected_since": datetime.datetime.now().isoformat() if success else None,
            "message_count": 0,
        }

        if not success:
            self._watch_async(channel_type, key, ch)

        return status

    def _wire_scene(self, ch, scene_id: str, channel_type: str, ctx: 'AppContext') -> None:
        pool = ctx.pool

        async def _get_reply(msg):
            agent = pool.get_scene_agent(scene_id)
            if not agent:
                logger.warning("No agent bound to scene %s", scene_id)
                return None
            return await agent.run(msg.content)

        ch.on_message = self._make_handler(
            ch, _get_reply, ctx, scene_id=scene_id, channel_type=channel_type)
        ch.start(scene_id, {})

    def _wire_main(self, ch, channel_type: str, ctx: 'AppContext', reuse_instance: bool = False) -> None:
        sandbox_provider = ctx.sandbox_provider

        async def _get_reply(msg):
            try:
                resolved = _resolve_channel_user(ctx, channel_type, msg.user_id)
                if resolved:
                    ctx.user_id = resolved
                reply_text = await sandbox_provider.run_once(msg.content, agent_id="main")

                self._persist_message(ctx, channel_type, msg, reply_text)

                return reply_text
            except Exception:
                logger.exception("Main channel message handler failed for %s", channel_type)
                return None

        ch.on_message = self._make_handler(
            ch, _get_reply, ctx, scene_id="default", channel_type=channel_type)
        if not reuse_instance:
            ch.start("main", {})

    def _persist_message(self, ctx: 'AppContext', channel_type: str, msg, reply_text: str) -> None:
        """Persist channel message to DB history."""
        try:
            resolved = _resolve_channel_user(ctx, channel_type, msg.user_id)
            user = resolved or "channel"
            db = getattr(ctx, 'db', None)
            if db:
                db.messages.save(
                    msg_uuid=str(__import__('uuid').uuid4()),
                    agent_id="main", user_id=user,
                    role="user", content=msg.content[:2000],
                    scene_id="default",
                )
                db.messages.save(
                    msg_uuid=str(__import__('uuid').uuid4()),
                    agent_id="main", user_id=user,
                    role="assistant", content=reply_text[:5000],
                    scene_id="default",
                )
        except Exception:
            pass

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
        row = db.fetch_one(
            "SELECT user_id FROM channel_identities WHERE channel_type = ? AND channel_user_id = ?",
            (channel_type, channel_user_id),
        )
        return row["user_id"] if row else None
    except Exception:
        return None
