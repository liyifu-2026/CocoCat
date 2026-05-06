"""Entry manager — reads entry configs and starts channels for agents and scenes."""
import json
import os
import sys
import threading
import logging

logger = logging.getLogger("cococat.entry_manager")

# Add py-agent to path for channel imports
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "py-agent"))

from channel import ChatMessage

DEFAULT_ENTRIES_TEMPLATE = [
    {
        "channel_type": "telegram",
        "enabled": True,
        "config": {
            "bot_token": "${TELEGRAM_BOT_TOKEN}",
        },
    },
]

def ensure_default_entries(agent_dir: str):
    entries_path = os.path.join(agent_dir, "entries.json")
    if os.path.exists(entries_path):
        return
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return
    entries = []
    for tmpl in DEFAULT_ENTRIES_TEMPLATE:
        entry = json.loads(json.dumps(tmpl).replace("${TELEGRAM_BOT_TOKEN}", bot_token))
        entries.append(entry)
    with open(entries_path, "w") as f:
        json.dump(entries, f, indent=2)
    logger.info(f"Created default entries.json at {entries_path}")


def _read_entry_config(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        data = json.loads(open(path, "r", encoding="utf-8").read())
        return data.get("entries", [])
    except Exception:
        return []


def _route_to_agent(agent_id: str, channel_type: str, user_id: str, content: str):
    """Write incoming message to agent's mailbox (with FileLock for consistency)."""
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
    from sandbox import FileLock

    mailbox_dir = os.path.join(BASE_DIR, "agents", "mailbox", agent_id)
    os.makedirs(mailbox_dir, exist_ok=True)
    inbox_path = os.path.join(mailbox_dir, "inbox.jsonl")

    entry = {
        "from": f"channel:{channel_type}:{user_id}",
        "content": content,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "status": "unread",
        "channel": channel_type,
        "external_user": user_id,
    }
    with FileLock(inbox_path):
        with open(inbox_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Notify WebSocket clients
    try:
        import importlib, asyncio
        web_main = importlib.import_module("web.main")
        asyncio.ensure_future(web_main.manager.broadcast("message", {
            "type": "inbound",
            "agent_id": agent_id,
            "channel": channel_type,
            "from": user_id,
            "content": content[:200],
        }))
    except Exception:
        pass


def _start_feishu(scene_id: str, config: dict, target_id: str, target_type: str):
    """Start Feishu channel in background thread."""
    try:
        from channels.feishu import FeishuChannel
        ch = FeishuChannel()
        ch.on_message = lambda msg: _route_to_agent(
            target_id, "feishu", msg.user_id, msg.content
        )
        ch.start(scene_id, config)
        print(f"[EntryManager] Feishu channel started for {target_type} '{target_id}'")
    except Exception as e:
        print(f"[EntryManager] Failed to start Feishu channel: {e}")


def _start_telegram(scene_id: str, config: dict, target_id: str, target_type: str):
    try:
        from channels.telegram import TelegramChannel
        ch = TelegramChannel()
        ch.on_message = lambda msg: _route_to_agent(
            target_id, "telegram", msg.user_id, msg.content
        )
        ch.start(scene_id, config)
        print(f"[EntryManager] Telegram channel started for {target_type} '{target_id}'")
    except Exception as e:
        print(f"[EntryManager] Failed to start Telegram channel: {e}")


def _start_discord(scene_id: str, config: dict, target_id: str, target_type: str):
    try:
        from channels.discord import DiscordChannel
        ch = DiscordChannel()
        ch.on_message = lambda msg: _route_to_agent(
            target_id, "discord", msg.user_id, msg.content
        )
        ch.start(scene_id, config)
        print(f"[EntryManager] Discord channel started for {target_type} '{target_id}'")
    except Exception as e:
        print(f"[EntryManager] Failed to start Discord channel: {e}")


def _start_weixin(scene_id: str, config: dict, target_id: str, target_type: str):
    """Start WeChat personal channel in background thread."""
    try:
        from channels.weixin import WeixinChannel
        ch = WeixinChannel()
        ch.on_message = lambda msg: _route_to_agent(
            target_id, "weixin", msg.user_id, msg.content
        )
        ch.start(scene_id, config)
        print(f"[EntryManager] Weixin channel started for {target_type} '{target_id}'")
    except Exception as e:
        print(f"[EntryManager] Failed to start Weixin channel: {e}")


def start_agent_entries(agent_id: str):
    """Start all enabled entries for an agent."""
    entries_path = os.path.join(BASE_DIR, "agents", agent_id, "entries.json")
    entries = _read_entry_config(entries_path)

    for entry in entries:
        if not entry.get("enabled", False):
            continue
        channel = entry.get("channel", "")
        config = entry.get("config", {})

        if channel == "feishu":
            t = threading.Thread(target=_start_feishu, args=(agent_id, config, agent_id, "agent"), daemon=True)
            t.start()
        elif channel == "weixin":
            t = threading.Thread(target=_start_weixin, args=(agent_id, config, agent_id, "agent"), daemon=True)
            t.start()
        elif channel == "telegram":
            t = threading.Thread(target=_start_telegram, args=(agent_id, config, agent_id, "agent"), daemon=True)
            t.start()
        elif channel == "discord":
            t = threading.Thread(target=_start_discord, args=(agent_id, config, agent_id, "agent"), daemon=True)
            t.start()
        elif channel == "web_api":
            print(f"[EntryManager] Web API entry for agent '{agent_id}' — handled by FastAPI routes")


def start_scene_entries(scene_id: str):
    """Start all enabled entries for a scene — routes to any agent in the scene."""
    entries_path = os.path.join(BASE_DIR, "scenes", scene_id, "entries.json")
    entries = _read_entry_config(entries_path)

    # Find agents in this scene
    roster_path = os.path.join(BASE_DIR, "scenes", scene_id, "roster.json")
    agents_in_scene = []
    if os.path.exists(roster_path):
        try:
            roster = json.loads(open(roster_path, "r", encoding="utf-8").read())
            agents_in_scene = roster.get("agents", [])
        except Exception:
            pass

    if not agents_in_scene:
        print(f"[EntryManager] Scene '{scene_id}' has no agents assigned, skipping entries")
        return

    # For now, route to the first available agent
    target_agent = agents_in_scene[0]

    for entry in entries:
        if not entry.get("enabled", False):
            continue
        channel = entry.get("channel", "")
        config = entry.get("config", {})

        if channel == "feishu":
            t = threading.Thread(target=_start_feishu, args=(scene_id, config, target_agent, "scene"), daemon=True)
            t.start()
        elif channel == "weixin":
            t = threading.Thread(target=_start_weixin, args=(scene_id, config, target_agent, "scene"), daemon=True)
            t.start()
        elif channel == "telegram":
            t = threading.Thread(target=_start_telegram, args=(scene_id, config, target_agent, "scene"), daemon=True)
            t.start()
        elif channel == "discord":
            t = threading.Thread(target=_start_discord, args=(scene_id, config, target_agent, "scene"), daemon=True)
            t.start()
        elif channel == "web_api":
            print(f"[EntryManager] Web API entry for scene '{scene_id}' — handled by FastAPI routes")


def start_all_entries():
    """Start all entries for all agents and scenes."""
    print("[EntryManager] Starting all entries...")

    # Agent entries
    agents_dir = os.path.join(BASE_DIR, "agents")
    if os.path.exists(agents_dir):
        for d in os.listdir(agents_dir):
            agent_dir = os.path.join(agents_dir, d)
            if os.path.isdir(agent_dir) and d != "mailbox" and d != "dispatch_queue" and d != "dispatch_messages" and not d.startswith("_"):
                ensure_default_entries(agent_dir)
                start_agent_entries(d)

    # Scene entries
    scenes_dir = os.path.join(BASE_DIR, "scenes")
    if os.path.exists(scenes_dir):
        for d in os.listdir(scenes_dir):
            scene_dir = os.path.join(scenes_dir, d)
            if os.path.isdir(scene_dir):
                start_scene_entries(d)

    print("[EntryManager] All entries started")
