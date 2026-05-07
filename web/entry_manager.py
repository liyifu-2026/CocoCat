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


def _route_to_scene(runtime, channel_type: str, user_id: str, content: str):
    """Route a message to a scene's agent via its AgentHandle."""
    if runtime.state.name != "ACTIVE" or not runtime.agent_handle:
        print(f"[EntryManager] Scene '{runtime.scene_id}' not active, dropping message from {user_id}")
        return
    reply_url = os.environ.get(
        "COCOCAT_REPLY_URL",
        "http://localhost:8080/api/channels/reply"
    )
    runtime.agent_handle.send_message(channel_type, user_id, content, reply_url=reply_url)


def _start_entry(channel_type: str, scene_id: str, config: dict, target_id: str, target_type: str):
    """Start a channel via ChannelFactory in a background thread."""
    try:
        from channels.channel_factory import create_channel
        ch = create_channel(channel_type)
        ch.on_message = lambda msg: _route_to_agent(
            target_id, channel_type, msg.user_id, msg.content
        )
        ch.start(scene_id, config)
        print(f"[EntryManager] {channel_type} channel started for {target_type} '{target_id}'")
    except Exception as e:
        print(f"[EntryManager] Failed to start {channel_type} channel: {e}")


def _start_scene_channels(runtime):
    """Start all enabled channels for a scene runtime."""
    from channels.channel_factory import create_channel

    for ch_cfg in runtime.config.channels:
        if not ch_cfg.enabled:
            continue
        if ch_cfg.channel_type == "web_api":
            print(f"[EntryManager] Web API for scene '{runtime.scene_id}' — handled by FastAPI")
            continue
        try:
            ch = create_channel(ch_cfg.channel_type)
            ch.on_message = lambda msg, s=runtime, ct=ch_cfg.channel_type: _route_to_scene(
                s, ct, msg.user_id, msg.content
            )
            ch.start(runtime.scene_id, ch_cfg.config)
            runtime.channels.append(ch)
            print(f"[EntryManager] {ch_cfg.channel_type} channel started for scene '{runtime.scene_id}'")
        except Exception as e:
            print(f"[EntryManager] Failed to start {ch_cfg.channel_type}: {e}")


def start_agent_entries(agent_id: str):
    """Start all enabled entries for an agent."""
    entries_path = os.path.join(BASE_DIR, "agents", agent_id, "entries.json")
    entries = _read_entry_config(entries_path)

    for entry in entries:
        if not entry.get("enabled", False):
            continue
        channel = entry.get("channel", "")
        config = entry.get("config", {})
        if channel == "web_api":
            print(f"[EntryManager] Web API entry for agent '{agent_id}' — handled by FastAPI routes")
        else:
            _start_entry(channel, agent_id, config, agent_id, "agent")


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

    for entry in entries:
        if not entry.get("enabled", False):
            continue
        channel = entry.get("channel", "")
        config = entry.get("config", {})

        # Route entry to all agents in the scene
        if channel == "web_api":
            print(f"[EntryManager] Web API entry for scene '{scene_id}' — handled by FastAPI routes")
        else:
            for target_agent in agents_in_scene:
                _start_entry(channel, scene_id, config, target_agent, "scene")


def start_all_entries():
    """Start all entries for all scenes via SceneRuntime."""
    from scene_manager import SceneManager
    from scene_config import list_scenes, load_scene_config

    mgr = SceneManager()

    for scene_id in list_scenes():
        config = load_scene_config(scene_id)
        if not config or not config.channels:
            continue
        runtime = mgr.get_or_create(scene_id)
        if runtime is None:
            continue
        _start_scene_channels(runtime)

    print("[EntryManager] All entries started")
