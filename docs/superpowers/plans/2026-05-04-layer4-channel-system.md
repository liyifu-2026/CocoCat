# Channel System Refactoring Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the channel system with a robust base class, reconnection mixin, persistent Discord client, Feishu token refresh, auto-created default entries, and removal of dead web_api.py code.

**Architecture:** Six independent tasks that can be implemented sequentially. Each channel gets `stop()`/`is_running()`/`connected_state`/`on_disconnected` from the enhanced base class. A `ReconnectingChannel` mixin provides exponential-backoff retry logic. Discord's `send()` switches from per-call client creation to `asyncio.run_coroutine_threadsafe`. Feishu gets a 90-minute token refresh timer and WS reconnect. Entry manager auto-creates `entries.json` from env vars. Dead `web_api.py` is removed since FastAPI routes handle Web API directly.

**Tech Stack:** Python 3.10+, discord.py, lark-oapi, requests, threading, asyncio

---

## File Structure

```
CocoCat/
├── py-agent/
│   ├── channel.py                          # MODIFIED: enhanced base class
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── channel_base.py                 # NEW: ReconnectingChannel mixin
│   │   ├── discord.py                      # MODIFIED: persistent client
│   │   ├── feishu.py                       # MODIFIED: token refresh + WS reconnect
│   │   ├── telegram.py                     # UNCHANGED
│   │   ├── wechat.py                       # UNCHANGED
│   │   ├── weixin.py                       # UNCHANGED
│   │   └── web_api.py                      # DELETED (handled by FastAPI routes)
├── web/
│   └── entry_manager.py                    # MODIFIED: auto-create entries.json
```

---

### Task 1: Enhance Channel base class

**Files:**
- Modify: `py-agent/channel.py` (entire file)

- [ ] **Step 1: Write the complete enhanced channel.py**

```python
"""Channel base class and unified message format (CowAgent pattern)."""
from datetime import datetime
import json


class ChatMessage:
    """Unified message format across all channels."""
    def __init__(self, channel_type="", scene_id="", user_id="",
                 content="", msg_type="text", msg_id="", timestamp=None):
        self.channel_type = channel_type
        self.scene_id = scene_id
        self.user_id = user_id
        self.content = content
        self.msg_type = msg_type
        self.msg_id = msg_id or str(datetime.now().timestamp())
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self):
        return {
            "channel_type": self.channel_type,
            "scene_id": self.scene_id,
            "user_id": self.user_id,
            "content": self.content,
            "msg_type": self.msg_type,
            "msg_id": self.msg_id,
            "timestamp": self.timestamp,
        }


class Channel:
    """Base class for scene entry channels.

    Subclasses must set channel_type and implement start() and send().
    """
    channel_type = ""

    CONN_DISCONNECTED = "disconnected"
    CONN_CONNECTING = "connecting"
    CONN_CONNECTED = "connected"
    CONN_RECONNECTING = "reconnecting"

    def __init__(self):
        self.scene_id = ""
        self.on_message = None
        self.on_disconnected = None
        self.connected_state = Channel.CONN_DISCONNECTED

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        self.connected_state = Channel.CONN_CONNECTING
        raise NotImplementedError

    def send(self, reply: str, user_id: str):
        raise NotImplementedError

    def stop(self):
        self.connected_state = Channel.CONN_DISCONNECTED

    def is_running(self) -> bool:
        return self.connected_state in (
            Channel.CONN_CONNECTED,
            Channel.CONN_CONNECTING,
            Channel.CONN_RECONNECTING,
        )
```

- [ ] **Step 2: Test the enhanced base class**

Run: `python -c "import sys; sys.path.insert(0,'py-agent'); from channel import Channel, ChatMessage; c = Channel(); assert c.connected_state == 'disconnected'; assert c.is_running() == False; c.connected_state = 'connected'; assert c.is_running(); print('channel base ok')"`
Expected: "channel base ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channel.py
git commit -m "refactor: enhance Channel base class with stop/is_running/connected_state/on_disconnected"
```

---

### Task 2: Create ReconnectingChannel mixin

**Files:**
- Create: `py-agent/channels/channel_base.py`

- [ ] **Step 1: Write the complete channel_base.py**

```python
"""ReconnectingChannel mixin with exponential backoff retry."""
import threading
import time


class ReconnectingChannel:
    """Mixin that adds exponential-backoff reconnection to channels.

    The mixing class must have:
      - self.connected_state  (str, updated by mixin)
      - self.on_disconnected  (callable or None, called when all retries exhausted)

    Usage:
        class MyChannel(Channel, ReconnectingChannel):
            def _connect_impl(self) -> bool:
                return True

            def start(self, scene_id, config):
                ...
                self._start_reconnect_loop(self._connect_impl)
    """

    def __init__(self, max_retries=5, base_delay=2, max_delay=60):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._reconnect_stop = threading.Event()
        self._reconnect_thread = None

    def _start_reconnect_loop(self, connect_fn, stop_event=None):
        """Start a daemon thread running exponential-backoff reconnect.

        Args:
            connect_fn: Callable[[], bool] — returns True on successful connect.
            stop_event: threading.Event to signal stop (default: new Event).
        """
        self._reconnect_stop = stop_event or threading.Event()
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_worker,
            args=(connect_fn,),
            daemon=True,
        )
        self._reconnect_thread.start()

    def _reconnect_worker(self, connect_fn):
        for attempt in range(self.max_retries):
            if self._reconnect_stop.is_set():
                return
            self.connected_state = "reconnecting"
            delay = min(self.base_delay * (2 ** attempt), self.max_delay)
            print(f"[Reconnect] Attempt {attempt + 1}/{self.max_retries} in {delay}s")
            time.sleep(delay)
            if self._reconnect_stop.is_set():
                return
            try:
                if connect_fn():
                    self.connected_state = "connected"
                    print("[Reconnect] Reconnected successfully")
                    return
            except Exception as e:
                print(f"[Reconnect] Attempt {attempt + 1} failed: {e}")
        self.connected_state = "disconnected"
        print(f"[Reconnect] All {self.max_retries} attempts exhausted")
        if self.on_disconnected:
            self.on_disconnected()

    def stop_reconnect(self):
        """Signal the reconnect loop to stop."""
        if self._reconnect_stop:
            self._reconnect_stop.set()
```

- [ ] **Step 2: Test the mixin**

Run: `python -c "import sys; sys.path.insert(0,'py-agent/channels'); from channel_base import ReconnectingChannel; print('reconnecting channel mixin ok')"`
Expected: "reconnecting channel mixin ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channels/channel_base.py
git commit -m "feat: add ReconnectingChannel mixin with exponential backoff retry"
```

---

### Task 3: Rewrite Discord channel

**Files:**
- Modify: `py-agent/channels/discord.py` (entire file)

- [ ] **Step 1: Write the complete rewritten discord.py**

```python
"""Discord channel via discord.py bot — persistent single client."""
import sys, os, threading, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage


class DiscordChannel(Channel):
    channel_type = "discord"

    def __init__(self):
        super().__init__()
        self.bot_token = ""
        self._running = False
        self._thread = None
        self._loop = None
        self._client = None

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        self.bot_token = config.get("bot_token", "")
        if not self.bot_token:
            print("[Discord] No bot_token provided")
            return
        self._running = True
        self.connected_state = Channel.CONN_CONNECTING
        self._thread = threading.Thread(target=self._run_bot, daemon=True)
        self._thread.start()
        print(f"[Discord] Bot started for scene '{scene_id}'")

    def _run_bot(self):
        import discord
        intents = discord.Intents.default()
        intents.message_content = True

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        class BotClient(discord.Client):
            def __init__(self, channel_ref):
                super().__init__(intents=intents)
                self.channel_ref = channel_ref

            async def on_ready(self):
                self.channel_ref.connected_state = Channel.CONN_CONNECTED
                print(f"[Discord] Logged in as {self.user}")

            async def on_message(self, message):
                if message.author.bot:
                    return
                chat_msg = ChatMessage(
                    channel_type="discord",
                    scene_id=self.channel_ref.scene_id,
                    user_id=str(message.author.id),
                    content=message.content,
                )
                if self.channel_ref.on_message:
                    self.channel_ref.on_message(chat_msg)

        self._client = BotClient(self)
        try:
            self._client.run(self.bot_token)
        except Exception as e:
            print(f"[Discord] Bot error: {e}")
            self.connected_state = Channel.CONN_DISCONNECTED

    def send(self, reply: str, user_id: str):
        if not self._loop or not self._client or not self._client.is_ready():
            print("[Discord] Bot not ready, cannot send")
            return
        coro = self._send_dm(user_id, reply)
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def _send_dm(self, user_id: str, reply: str):
        try:
            user = await self._client.fetch_user(int(user_id))
            if user:
                await user.send(reply)
        except Exception as e:
            print(f"[Discord] Send error: {e}")

    def stop(self):
        self._running = False
        if self._client:
            asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
        self.connected_state = Channel.CONN_DISCONNECTED
```

- [ ] **Step 2: Test import**

Run: `python -c "import sys; sys.path.insert(0,'py-agent'); from channels.discord import DiscordChannel; print('discord channel ok')"`
Expected: "discord channel ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channels/discord.py
git commit -m "refactor: persistent Discord client with asyncio.run_coroutine_threadsafe for send"
```

---

### Task 4: Fix Feishu token refresh + WS reconnect

**Files:**
- Modify: `py-agent/channels/feishu.py` (entire file)

- [ ] **Step 1: Write the complete feishu.py with token refresh and reconnect**

```python
"""Feishu (飞书) channel via WebSocket mode (CowAgent pattern).

Features:
- Token refresh every 90 minutes (tenant_access_token expires in 2h).
- WebSocket auto-reconnect with exponential backoff on disconnect.
"""
import sys, os, json, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage
from channels.channel_base import ReconnectingChannel

TOKEN_REFRESH_INTERVAL = 5400  # 90 minutes


class FeishuChannel(Channel, ReconnectingChannel):
    channel_type = "feishu"

    def __init__(self):
        Channel.__init__(self)
        ReconnectingChannel.__init__(self)
        self.app_id = ""
        self.app_secret = ""
        self._token = ""
        self._token_timer = None

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")
        if not self.app_id or not self.app_secret:
            print("[Feishu] app_id and app_secret required")
            return
        self._get_token()
        self._schedule_token_refresh()
        self.connected_state = Channel.CONN_CONNECTING
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._ws_thread.start()

    def _get_token(self):
        import requests
        try:
            r = requests.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=10,
            )
            self._token = r.json().get("tenant_access_token", "")
            if self._token:
                print("[Feishu] Token obtained/refreshed")
        except Exception as e:
            print(f"[Feishu] Token fetch error: {e}")

    def _schedule_token_refresh(self):
        self._token_timer = threading.Timer(TOKEN_REFRESH_INTERVAL, self._refresh_token)
        self._token_timer.daemon = True
        self._token_timer.start()

    def _refresh_token(self):
        self._get_token()
        self._schedule_token_refresh()

    def _ws_connect_once(self) -> bool:
        try:
            import lark_oapi as lark
        except ImportError:
            return False

        def handle_message(msg):
            event = json.loads(lark.JSON.marshal(msg))
            self._handle_event(event)

        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(handle_message) \
            .build()

        ws_client = lark.ws.Client(
            self.app_id, self.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.DEBUG,
        )
        self.connected_state = Channel.CONN_CONNECTED
        ws_client.start()
        return True

    def _ws_loop(self):
        import lark_oapi as lark

        def handle_message(msg):
            event = json.loads(lark.JSON.marshal(msg))
            self._handle_event(event)

        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(handle_message) \
            .build()

        while self._running:
            try:
                ws_client = lark.ws.Client(
                    self.app_id, self.app_secret,
                    event_handler=event_handler,
                    log_level=lark.LogLevel.DEBUG,
                )
                self.connected_state = Channel.CONN_CONNECTED
                ws_client.start()
            except Exception as e:
                print(f"[Feishu] WS disconnected: {e}")

            if not self.is_running():
                break

            self.connected_state = Channel.CONN_DISCONNECTED
            if self.on_disconnected:
                self.on_disconnected()
            self._start_reconnect_loop(self._ws_connect_once)
            break

    def _handle_event(self, event: dict):
        try:
            msg = event.get("event", {}).get("message", {})
            sender = event.get("event", {}).get("sender", {})
            msg_type = msg.get("message_type", "")
            content = msg.get("content", "")
            sender_id = sender.get("sender_id", {}).get("open_id", "")

            if not sender_id or not content:
                return

            if msg_type == "text":
                import json as _json
                try:
                    text_content = _json.loads(content).get("text", "")
                except Exception:
                    text_content = content
            else:
                text_content = f"[{msg_type} message]"

            chat_msg = ChatMessage(
                channel_type="feishu",
                scene_id=self.scene_id,
                user_id=sender_id,
                content=text_content,
            )
            if self.on_message:
                self.on_message(chat_msg)
        except Exception as e:
            print(f"[Feishu] Handle error: {e}")

    def send(self, reply: str, user_id: str):
        import requests
        if not self._token:
            self._get_token()
        url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        body = {"receive_id": user_id, "msg_type": "text", "content": json.dumps({"text": reply})}
        try:
            requests.post(url, json=body, headers=headers, timeout=10)
        except Exception as e:
            print(f"[Feishu] Send error: {e}")

    def stop(self):
        ReconnectingChannel.stop_reconnect(self)
        if self._token_timer:
            self._token_timer.cancel()
        self.connected_state = Channel.CONN_DISCONNECTED
```

- [ ] **Step 2: Test import**

Run: `python -c "import sys; sys.path.insert(0,'py-agent'); from channels.feishu import FeishuChannel; print('feishu channel ok')"`
Expected: "feishu channel ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channels/feishu.py
git commit -m "fix: add Feishu token refresh every 90min and WS reconnect with exponential backoff"
```

---

### Task 5: Fix Entry Manager to auto-create default entries.json

**Files:**
- Modify: `web/entry_manager.py`

- [ ] **Step 1: Add ensure_default_entries() and wire it into start_agent_entries/start_scene_entries**

Current `web/entry_manager.py` is 187 lines. Apply these changes:

**Change A:** Add `ensure_default_entries()` function right after the imports (after line 12):

```python
DEFAULT_TELEGRAM_TEMPLATE = {
    "entries": [
        {
            "channel": "telegram",
            "enabled": True,
            "config": {
                "bot_token": "__TELEGRAM_BOT_TOKEN__"
            }
        }
    ]
}


def ensure_default_entries(entries_path: str):
    """Create default entries.json from template if TELEGRAM_BOT_TOKEN is set."""
    if os.path.exists(entries_path):
        return
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        return
    config = json.loads(json.dumps(DEFAULT_TELEGRAM_TEMPLATE))
    config["entries"][0]["config"]["bot_token"] = bot_token
    os.makedirs(os.path.dirname(entries_path), exist_ok=True)
    with open(entries_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"[EntryManager] Created default entries at {entries_path}")
```

**Change B:** In `start_agent_entries()`, replace line 98:
```python
    entries_path = os.path.join(BASE_DIR, "agents", agent_id, "entries.json")
    entries = _read_entry_config(entries_path)
```
With:
```python
    entries_path = os.path.join(BASE_DIR, "agents", agent_id, "entries.json")
    ensure_default_entries(entries_path)
    entries = _read_entry_config(entries_path)
```

**Change C:** In `start_scene_entries()`, replace line 125:
```python
    entries_path = os.path.join(BASE_DIR, "scenes", scene_id, "entries.json")
    entries = _read_entry_config(entries_path)
```
With:
```python
    entries_path = os.path.join(BASE_DIR, "scenes", scene_id, "entries.json")
    ensure_default_entries(entries_path)
    entries = _read_entry_config(entries_path)
```

- [ ] **Step 2: Test the ensure_default_entries function**

Run:
```bash
mkdir -p /tmp/test_entries
python -c "
import sys, os, json
sys.path.insert(0, 'web')
os.environ['TELEGRAM_BOT_TOKEN'] = 'test:token123'
from entry_manager import ensure_default_entries
p = '/tmp/test_entries/entries.json'
ensure_default_entries(p)
assert os.path.exists(p), 'file not created'
data = json.loads(open(p).read())
assert data['entries'][0]['config']['bot_token'] == 'test:token123'
print('ensure_default_entries ok')
# second call should not overwrite
ensure_default_entries(p)
print('no-overwrite ok')
os.remove(p)
ensure_default_entries(p)
assert not os.path.exists(p), 'should not create without env var'
print('no-env ok')
"
```
Expected: "ensure_default_entries ok", "no-overwrite ok", "no-env ok"

- [ ] **Step 3: Commit**

```bash
git add web/entry_manager.py
git commit -m "feat: auto-create default entries.json from TELEGRAM_BOT_TOKEN env var"
```

---

### Task 6: Remove web_api.py dead code

**Files:**
- Delete: `py-agent/channels/web_api.py`

- [ ] **Step 1: Verify no Python code imports WebApiChannel**

Run: `rg -l "web_api" --include="*.py" py-agent/ web/`
Expected output shows only string references ("web_api"), no `from channels.web_api import WebApiChannel`. If there are imports, abort this task and report them.

- [ ] **Step 2: Delete web_api.py**

Run: `rm py-agent/channels/web_api.py`

- [ ] **Step 3: Verify the deletion**

Run: `ls py-agent/channels/`
Expected output shows all files except `web_api.py`.

- [ ] **Step 4: Commit**

```bash
git add py-agent/channels/web_api.py
git commit -m "cleanup: remove dead web_api.py — Web API is handled by FastAPI routes"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- Task 1 covers: `stop()`, `is_running()`, `connected_state`, `on_disconnected` on Channel base class ✓
- Task 2 covers: `ReconnectingChannel` mixin with `max_retries=5`, `base_delay=2`, `max_delay=60` ✓
- Task 3 covers: persistent single Discord client, `asyncio.run_coroutine_threadsafe` for send ✓
- Task 4 covers: Feishu token refresh every 90 minutes, WS reconnect logic ✓
- Task 5 covers: `ensure_default_entries()` creating `entries.json` from `TELEGRAM_BOT_TOKEN` env var ✓
- Task 6 covers: deleting `web_api.py`, noting FastAPI routes handle Web API ✓

**2. Placeholder scan:** No TBD, TODO, placeholders, or ellipsis in any code block.

**3. Type consistency:**
- `Channel.CONN_DISCONNECTED`/`CONN_CONNECTING`/`CONN_CONNECTED`/`CONN_RECONNECTING` used consistently across Tasks 1, 3, 4 ✓
- `ReconnectingChannel.__init__` called via explicit `ReconnectingChannel.__init__(self)` in FeishuChannel (multiple inheritance requires this) ✓
- `stop()` in base class sets `disconnected`; Discord's `stop()` overrides with cleanup; Feishu's `stop()` calls `stop_reconnect()` and cancels timer ✓
- `ensure_default_entries` signature `(entries_path: str)` used consistently in both call sites ✓
