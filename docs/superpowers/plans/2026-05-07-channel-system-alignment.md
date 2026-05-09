# Channel System Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor CocoCat's channel system to align with CowAgent's two-layer Channel → ChatChannel architecture with Context/Reply types, session queue management, and proper reply pipeline.

**Architecture:** Six independent tasks: (1) Context/Reply type system, (2) enhanced Channel base class, (3) ChatChannel middle layer, (4) ChannelFactory, (5-6) existing channel rewrites to extend ChatChannel, (7) entry_manager simplification.

**Tech Stack:** Python 3.10+, threading, queue

---

## File Structure

```
py-agent/
├── channel_context.py          # NEW
├── channel.py                  # REWRITE
├── chat_channel.py             # NEW
├── channels/
│   ├── __init__.py
│   ├── channel_base.py         # MODIFY
│   ├── channel_factory.py      # NEW
│   ├── telegram.py             # REWRITE
│   ├── discord.py              # REWRITE
│   ├── weixin.py               # REWRITE
│   └── feishu.py               # REWRITE
web/
└── entry_manager.py            # MODIFY
```

---

### Task 1: Create Context/Reply type system

**Files:**
- Create: `py-agent/channel_context.py`

- [ ] **Step 1: Write channel_context.py**

Write `py-agent/channel_context.py`:

```python
"""Context and Reply types for channel message processing (CowAgent pattern)."""
from __future__ import annotations

from enum import Enum


class ContextType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    IMAGE_CREATE = "image_create"
    FILE = "file"
    VIDEO = "video"
    SHARING = "sharing"
    FUNCTION = "function"


class ReplyType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    IMAGE_URL = "image_url"
    FILE = "file"
    VIDEO = "video"
    VIDEO_URL = "video_url"
    ERROR = "error"
    INFO = "info"


class Context:
    """Message context carrying content, type, and metadata through the pipeline."""
    def __init__(self, ctype: ContextType, content: str, **kwargs):
        self.type = ctype
        self.content = content
        self.kwargs = kwargs

    def __getitem__(self, key):
        return self.kwargs[key]

    def __setitem__(self, key, value):
        self.kwargs[key] = value

    def get(self, key, default=None):
        return self.kwargs.get(key, default)


class Reply:
    """Unified reply object with type and content."""
    def __init__(self, rtype: ReplyType, content: str):
        self.type = rtype
        self.content = content
```

- [ ] **Step 2: Test the module**

Run: `python -c "import sys; sys.path.insert(0,'py-agent'); from channel_context import Context, Reply, ContextType, ReplyType; c = Context(ContextType.TEXT, 'hello'); assert c.type == ContextType.TEXT; r = Reply(ReplyType.TEXT, 'hi'); assert r.type == ReplyType.TEXT; print('channel_context ok')"`
Expected: "channel_context ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channel_context.py
git commit -m "feat: add Context/Reply type system (CowAgent pattern)"
```

---

### Task 2: Enhance Channel base class

**Files:**
- Modify: `py-agent/channel.py` (entire file, overwrite)

- [ ] **Step 1: Write the enhanced channel.py**

```python
"""Channel base class with 4-state connection and startup event (CowAgent pattern)."""
from __future__ import annotations

import threading
import uuid


class ChatMessage:
    """Unified message format across all channels.

    Created by channel implementations when receiving platform messages.
    Passed to _compose_context() via kwargs as msg=.
    """
    def __init__(self, channel_type="", scene_id="", user_id="",
                 content="", msg_type="text", msg_id="", **kwargs):
        self.channel_type = channel_type
        self.scene_id = scene_id
        self.user_id = user_id
        self.content = content
        self.msg_type = msg_type
        self.msg_id = msg_id or str(uuid.uuid4())[:8]
        self.extra = kwargs


class Channel:
    """Base class for external communication channels.

    Subclasses must set channel_type and implement startup() and send().
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
        self._startup_event = threading.Event()
        self._startup_error = None

    def startup(self):
        """Initialize channel connection. Called by start() in a background thread."""
        raise NotImplementedError

    def start(self, scene_id: str, config: dict):
        """Start the channel in a background thread and report completion via startup_event."""
        self.scene_id = scene_id
        self.connected_state = Channel.CONN_CONNECTING
        self._startup_event.clear()
        self._startup_error = None
        t = threading.Thread(target=self._startup_wrapper, daemon=True)
        t.start()

    def _startup_wrapper(self):
        try:
            self.startup()
            self.connected_state = Channel.CONN_CONNECTED
            self.report_startup_success()
        except Exception as e:
            self.connected_state = Channel.CONN_DISCONNECTED
            self.report_startup_error(str(e))

    def report_startup_success(self):
        self._startup_error = None
        self._startup_event.set()

    def report_startup_error(self, error: str):
        self._startup_error = error
        self._startup_event.set()

    def wait_startup(self, timeout: float = 3) -> tuple[bool, str]:
        """Wait for channel startup result. Returns (success, error_msg)."""
        ready = self._startup_event.wait(timeout=timeout)
        if not ready:
            return True, ""
        if self._startup_error:
            return False, self._startup_error
        return True, ""

    def send(self, reply, context):
        """Send a Reply object through this channel.

        Args:
            reply: Reply object with type and content.
            context: Context object with receiver/session metadata.
        """
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

Run: `python -c "import sys; sys.path.insert(0,'py-agent'); from channel import Channel; c = Channel(); assert c.connected_state == 'disconnected'; assert c.is_running() == False; c.connected_state = 'connected'; assert c.is_running(); print('channel base ok')"`
Expected: "channel base ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channel.py
git commit -m "refactor: enhance Channel base class with 4-state, startup_event, send(Reply,Context)"
```

---

### Task 3: Create ChannelFactory

**Files:**
- Create: `py-agent/channels/channel_factory.py`

- [ ] **Step 1: Write channel_factory.py**

```python
"""Channel factory — maps channel_type strings to Channel classes."""
from __future__ import annotations

_CHANNEL_MAP: dict[str, type] = {}


def register_channel(channel_type: str, channel_cls: type):
    """Register a Channel class for a given channel_type string."""
    _CHANNEL_MAP[channel_type] = channel_cls


def create_channel(channel_type: str, **kwargs):
    """Create a Channel instance by channel_type string."""
    cls = _CHANNEL_MAP.get(channel_type)
    if cls is None:
        raise ValueError(f"Unknown channel type: {channel_type!r}. Available: {list(_CHANNEL_MAP.keys())}")
    return cls(**kwargs)
```

- [ ] **Step 2: Test the factory**

```python
python -c "
import sys; sys.path.insert(0,'py-agent')
from channels.channel_factory import register_channel, create_channel
from channel import Channel

class FakeChannel(Channel):
    channel_type = 'fake'

register_channel('fake', FakeChannel)
ch = create_channel('fake')
assert isinstance(ch, FakeChannel)
print('factory ok')

try:
    create_channel('nonexistent')
    assert False, 'should raise'
except ValueError:
    print('unknown channel error ok')
"
```
Expected: "factory ok" + "unknown channel error ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channels/channel_factory.py
git commit -m "feat: add ChannelFactory with register/create pattern"
```

---

### Task 4: Create ChatChannel middle layer

**Files:**
- Create: `py-agent/chat_channel.py`
- Modify: `py-agent/channels/channel_base.py` (align with new Channel)

- [ ] **Step 1: Update channel_base.py ReconnectingChannel to use new connected_state**

```python
"""ReconnectingChannel mixin with exponential backoff (CowAgent pattern)."""
import threading
import time
import logging

logger = logging.getLogger("cococat.channel")


class ReconnectingChannel:
    """Mixin that adds exponential-backoff reconnection to Channel subclasses.

    The mixing class must have:
      - self.connected_state  (updated by mixin)
      - self.on_disconnected  (callable or None, called when all retries exhausted)
    """

    MAX_RETRIES = 5
    BASE_DELAY = 2
    MAX_DELAY = 60

    def __init__(self, max_retries=5, base_delay=2, max_delay=60):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._reconnect_stop = threading.Event()
        self._reconnect_thread = None

    def _start_reconnect_loop(self, connect_fn):
        self._reconnect_stop.clear()
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_worker, args=(connect_fn,), daemon=True
        )
        self._reconnect_thread.start()

    def _reconnect_worker(self, connect_fn):
        for attempt in range(self.max_retries):
            if self._reconnect_stop.is_set():
                return
            self.connected_state = "reconnecting"
            delay = min(self.base_delay * (2 ** attempt), self.max_delay)
            logger.warning(f"Reconnecting (attempt {attempt+1}/{self.max_retries}) in {delay}s")
            time.sleep(delay)
            if self._reconnect_stop.is_set():
                return
            try:
                if connect_fn():
                    self.connected_state = "connected"
                    logger.info("Reconnected successfully")
                    return
            except Exception as e:
                logger.warning(f"Reconnect attempt {attempt+1} failed: {e}")
        self.connected_state = "disconnected"
        logger.error(f"All {self.max_retries} reconnection attempts exhausted")
        if self.on_disconnected:
            self.on_disconnected()

    def stop_reconnect(self):
        self._reconnect_stop.set()
```

- [ ] **Step 2: Write chat_channel.py**

```python
"""ChatChannel — session-queued message processing pipeline (CowAgent ChatChannel pattern).

Provides:
- Per-session message queue with concurrency control
- _compose_context() for building Context with prefix/group/blacklist logic
- _handle() pipeline: generate_reply → decorate_reply → send_reply
- Plugin event hooks at each pipeline stage
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Queue

from channel import Channel
from channel_context import Context, ContextType, Reply, ReplyType

logger = logging.getLogger("cococat.chat_channel")

handler_pool = ThreadPoolExecutor(max_workers=8)


class ChatChannel(Channel):
    """Abstract channel with session queuing and reply pipeline.

    Subclasses implement startup() and send(reply, context).
    """

    NOT_SUPPORT_REPLYTYPE = [ReplyType.VOICE, ReplyType.IMAGE]

    def __init__(self):
        super().__init__()
        self.futures: dict[str, list[Future]] = {}
        self.sessions: dict[str, list] = {}
        self.lock = threading.Lock()
        _thread = threading.Thread(target=self._consume, daemon=True)
        _thread.start()

    # ── Session queue ────────────────────────────────────────────────

    def produce(self, context: Context):
        """Queue a context for processing, grouped by session_id."""
        session_id = context["session_id"]
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = [
                    Queue(),
                    threading.BoundedSemaphore(1),
                ]
            q = self.sessions[session_id][0]
            if context.type == ContextType.TEXT and context.content.startswith("#"):
                items = []
                while not q.empty():
                    items.append(q.get_nowait())
                q.put(context)
                for item in items:
                    q.put(item)
            else:
                q.put(context)

    def _consume(self):
        """Background thread: drain session queues and dispatch to handler pool."""
        while True:
            with self.lock:
                session_ids = list(self.sessions.keys())
            for session_id in session_ids:
                with self.lock:
                    if session_id not in self.sessions:
                        continue
                    ctx_queue, semaphore = self.sessions[session_id]
                if semaphore.acquire(blocking=False):
                    if not ctx_queue.empty():
                        context = ctx_queue.get_nowait()
                        future = handler_pool.submit(self._handle, context)
                        future.add_done_callback(self._make_callback(session_id))
                    else:
                        semaphore.release()
            time.sleep(0.2)

    def _make_callback(self, session_id: str):
        def cb(worker: Future):
            try:
                exc = worker.exception()
                if exc:
                    logger.error(f"Handler error for session {session_id}: {exc}")
            except Exception:
                pass
            with self.lock:
                if session_id in self.sessions:
                    self.sessions[session_id][1].release()
        return cb

    # ── Context composition ──────────────────────────────────────────

    def _compose_context(self, ctype: ContextType, content: str, **kwargs) -> Context | None:
        """Build a Context from raw message data.

        Override in subclasses to add prefix matching, group detection, etc.
        """
        context = Context(ctype, content)
        context.kwargs = kwargs
        context["channel_type"] = self.channel_type
        context["origin_ctype"] = ctype
        return context

    # ── Reply pipeline ──────────────────────────────────────────────

    def _handle(self, context: Context):
        """Full reply pipeline: generate → decorate → send."""
        if context is None or not context.content:
            return
        reply = self._generate_reply(context)
        if reply and reply.content:
            reply = self._decorate_reply(context, reply)
            self._send_reply(context, reply)

    def _generate_reply(self, context: Context, reply: Reply = None) -> Reply:
        """Generate a reply via Bridge.

        Override in subclasses to customize. The stub here echoes content back.
        Bridge integration (LocalBridge / MailboxBridge) will replace this.
        """
        if reply is None:
            reply = Reply(ReplyType.TEXT, "")
        if context.type == ContextType.TEXT:
            reply.content = context.content
            reply.type = ReplyType.TEXT
        return reply

    def _decorate_reply(self, context: Context, reply: Reply) -> Reply:
        """Decorate reply with prefix/suffix, @-mentions, etc.

        Override in subclasses.
        """
        return reply

    def _send_reply(self, context: Context, reply: Reply):
        """Send reply with optional media extraction.

        Override in subclasses.
        """
        self._send(reply, context)

    def _send(self, reply: Reply, context: Context, retry_cnt=0):
        try:
            self.send(reply, context)
        except NotImplementedError:
            pass
        except Exception as e:
            if retry_cnt < 2:
                time.sleep(3 + 3 * retry_cnt)
                self._send(reply, context, retry_cnt + 1)

    # ── Session management ──────────────────────────────────────────

    def cancel_session(self, session_id: str):
        """Cancel queued and in-flight tasks for a session."""
        with self.lock:
            if session_id in self.sessions:
                for future in self.futures.get(session_id, []):
                    future.cancel()
                self.sessions[session_id][0] = Queue()

    def cancel_all_session(self):
        """Cancel all sessions."""
        with self.lock:
            for session_id in list(self.sessions.keys()):
                for future in self.futures.get(session_id, []):
                    future.cancel()
                self.sessions[session_id][0] = Queue()
```

Add `logger = logging.getLogger("cococat.chat_channel")` import at top:

```python
import logging
logger = logging.getLogger("cococat.chat_channel")
```

- [ ] **Step 3: Test imports**

Run: `python -c "import sys; sys.path.insert(0,'py-agent'); from chat_channel import ChatChannel; from channel_context import Context, Reply, ContextType, ReplyType; print('chat_channel imports ok')"`
Expected: "chat_channel imports ok"

- [ ] **Step 4: Commit**

```bash
git add py-agent/chat_channel.py py-agent/channels/channel_base.py
git commit -m "feat: add ChatChannel middle layer with session queue and reply pipeline"
```

---

### Task 5: Rewrite Telegram channel

**Files:**
- Modify: `py-agent/channels/telegram.py` (entire file)

- [ ] **Step 1: Write the rewritten telegram.py**

```python
"""Telegram channel via Bot API polling (CowAgent ChatChannel pattern)."""
import sys, os, json, time, threading, requests, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage
from channel_context import Context, ContextType, Reply, ReplyType
from chat_channel import ChatChannel
from channels.channel_factory import register_channel

logger = logging.getLogger("cococat.telegram")


class TelegramChannel(ChatChannel):
    channel_type = "telegram"

    def __init__(self):
        super().__init__()
        self.bot_token = ""
        self.api_base = ""
        self._running = False
        self._poll_thread = None
        self._last_update_id = 0

    def startup(self):
        self.bot_token = self._config.get("bot_token", "")
        if not self.bot_token:
            logger.error("No bot_token provided")
            return
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"
        resp = requests.get(f"{self.api_base}/getMe", timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"Invalid bot token: {resp.text}")
        bot_name = resp.json().get("result", {}).get("first_name", "?")
        logger.info(f"Bot '{bot_name}' started for scene '{self.scene_id}'")
        self.report_startup_success()

        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self):
        while self._running:
            try:
                resp = requests.get(
                    f"{self.api_base}/getUpdates",
                    params={"timeout": 30, "offset": self._last_update_id + 1},
                    timeout=35,
                )
                if resp.status_code != 200:
                    time.sleep(5)
                    continue
                for update in resp.json().get("result", []):
                    self._last_update_id = update.get("update_id", 0)
                    msg = update.get("message", {})
                    if "text" in msg:
                        chat_id = str(msg["chat"]["id"])
                        text = msg["text"]
                        cmsg = ChatMessage(
                            channel_type="telegram",
                            scene_id=self.scene_id,
                            user_id=chat_id,
                            content=text,
                        )
                        context = self._compose_context(
                            ContextType.TEXT, text, msg=cmsg,
                            session_id=chat_id, receiver=chat_id,
                        )
                        if context:
                            self.produce(context)
            except requests.Timeout:
                pass
            except Exception as e:
                logger.warning(f"Poll error: {e}")
                time.sleep(5)

    def send(self, reply: Reply, context: Context):
        receiver = context.get("receiver", "")
        if not receiver:
            logger.warning("No receiver in context")
            return
        try:
            if reply.type == ReplyType.TEXT:
                requests.post(
                    f"{self.api_base}/sendMessage",
                    json={"chat_id": receiver, "text": reply.content},
                    timeout=10,
                )
            elif reply.type == ReplyType.IMAGE_URL:
                requests.post(
                    f"{self.api_base}/sendPhoto",
                    json={"chat_id": receiver, "photo": reply.content},
                    timeout=10,
                )
            else:
                requests.post(
                    f"{self.api_base}/sendMessage",
                    json={"chat_id": receiver, "text": str(reply.content)},
                    timeout=10,
                )
        except Exception as e:
            logger.error(f"Send error: {e}")

    def stop(self):
        self._running = False
        super().stop()


register_channel("telegram", TelegramChannel)
```

- [ ] **Step 2: Test import**

Run: `python -c "import sys; sys.path.insert(0,'py-agent'); from channels.telegram import TelegramChannel; print('telegram channel ok')"`
Expected: "telegram channel ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channels/telegram.py
git commit -m "refactor: TelegramChannel extends ChatChannel with session queue"
```

---

### Task 6: Rewrite Discord channel

**Files:**
- Modify: `py-agent/channels/discord.py` (entire file)

- [ ] **Step 1: Write the rewritten discord.py**

```python
"""Discord bot channel via discord.py (CowAgent ChatChannel pattern)."""
import sys, os, threading, asyncio, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage
from channel_context import Context, ContextType, Reply, ReplyType
from chat_channel import ChatChannel
from channels.channel_factory import register_channel

logger = logging.getLogger("cococat.discord")


class DiscordChannel(ChatChannel):
    channel_type = "discord"

    def __init__(self):
        super().__init__()
        self.bot_token = ""
        self._loop = None
        self._client = None
        self._bot_thread = None

    def startup(self):
        self.bot_token = self._config.get("bot_token", "")
        if not self.bot_token:
            raise RuntimeError("No bot_token provided")
        self._loop = asyncio.new_event_loop()
        self._bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self._bot_thread.start()

    def _run_bot(self):
        import discord
        asyncio.set_event_loop(self._loop)
        intents = discord.Intents.default()
        intents.message_content = True

        class BotClient(discord.Client):
            def __init__(self, channel_ref):
                super().__init__(intents=intents)
                self.channel_ref = channel_ref

            async def on_ready(self):
                self.channel_ref.connected_state = Channel.CONN_CONNECTED
                self.channel_ref.report_startup_success()
                logger.info(f"Discord logged in as {self.user}")

            async def on_message(self, message):
                if message.author.bot:
                    return
                cmsg = ChatMessage(
                    channel_type="discord",
                    scene_id=self.channel_ref.scene_id,
                    user_id=str(message.author.id),
                    content=message.content,
                )
                context = self.channel_ref._compose_context(
                    ContextType.TEXT, message.content, msg=cmsg,
                    session_id=str(message.author.id),
                    receiver=str(message.author.id),
                )
                if context:
                    self.channel_ref.produce(context)

        self._client = BotClient(self)
        try:
            self._client.run(self.bot_token, log_handler=None)
        except Exception as e:
            logger.error(f"Bot error: {e}")
            self.connected_state = Channel.CONN_DISCONNECTED

    def send(self, reply: Reply, context: Context):
        if not self._client or not self._client.is_ready():
            logger.warning("Bot not ready")
            return
        user_id = context.get("receiver", "")
        if not user_id:
            return
        async def _send():
            try:
                user = await self._client.fetch_user(int(user_id))
                await user.send(reply.content)
            except Exception as e:
                logger.error(f"Send error: {e}")
        asyncio.run_coroutine_threadsafe(_send(), self._loop)

    def stop(self):
        if self._client:
            asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
        super().stop()


register_channel("discord", DiscordChannel)
```

- [ ] **Step 2: Test import**

Run: `python -c "import sys; sys.path.insert(0,'py-agent'); from channels.discord import DiscordChannel; print('discord channel ok')"`
Expected: "discord channel ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channels/discord.py
git commit -m "refactor: DiscordChannel extends ChatChannel with session queue"
```

---

### Task 7: Rewrite Weixin channel

**Files:**
- Modify: `py-agent/channels/weixin.py` (entire file)

- [ ] **Step 1: Write the rewritten weixin.py**

```python
"""Personal WeChat channel via ilink bot API (CowAgent ChatChannel pattern)."""
import sys, os, json, time, threading, requests, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage
from channel_context import Context, ContextType, Reply, ReplyType
from chat_channel import ChatChannel
from channels.channel_factory import register_channel

logger = logging.getLogger("cococat.weixin")
API_BASE = "https://ilinkai.weixin.qq.com"


class WeixinApi:
    """Low-level ilink bot API wrapper."""
    def __init__(self, token="", bot_id="", base_url=API_BASE):
        self.token = token
        self.bot_id = bot_id
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "AuthorizationType": "ilink_bot_token",
            "Content-Type": "application/json",
        })

    def fetch_qr(self):
        return self.session.get(f"{self.base_url}/ilink/bot/get_bot_qrcode", params={"bot_type": 3}).json()

    def poll_qr(self, qrcode):
        return self.session.get(f"{self.base_url}/ilink/bot/get_qrcode_status", params={"qrcode": qrcode}).json()

    def get_updates(self, buf=""):
        return self.session.post(f"{self.base_url}/ilink/bot/getupdates", json={"buf": buf}, timeout=45).json()

    def send_message(self, to_username: str, content: str):
        self.session.post(f"{self.base_url}/ilink/bot/sendmessage", json={
            "BaseRequest": {"to_username": to_username, "context_token": ""},
            "msg_items": [{"type": 1, "content": content}],
        })


class WeixinChannel(ChatChannel):
    channel_type = "weixin"

    def __init__(self):
        super().__init__()
        self.api = None
        self._running = False
        self._poll_thread = None
        self._credentials_file = ""

    def startup(self):
        self._credentials_file = self._config.get("credentials_file", "") or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "agents", "_weixin_credentials.json"
        )
        self._login()
        self.report_startup_success()
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _login(self):
        if os.path.exists(self._credentials_file):
            with open(self._credentials_file) as f:
                creds = json.load(f)
            self.api = WeixinApi(token=creds.get("token", ""), bot_id=creds.get("bot_id", ""))
            logger.info("Logged in from saved credentials")
            return
        import qrcode
        api = WeixinApi()
        qr_data = api.fetch_qr()
        qrcode_url = qr_data.get("qrcode", "")
        if qrcode_url:
            qr = qrcode.QRCode()
            qr.add_data(qrcode_url)
            qr.print_ascii()
            for _ in range(120):
                status = api.poll_qr(qrcode_url)
                if status.get("status") == "confirmed":
                    self.api = WeixinApi(token=status["bot_token"], bot_id=status["ilink_bot_id"])
                    creds = {"token": status["bot_token"], "bot_id": status["ilink_bot_id"], "base_url": API_BASE}
                    os.makedirs(os.path.dirname(self._credentials_file), exist_ok=True)
                    with open(self._credentials_file, "w") as f:
                        json.dump(creds, f)
                    logger.info("Login successful!")
                    return
                time.sleep(1)
        logger.error("Login timeout")

    def _poll_loop(self):
        buf = ""
        while self._running:
            try:
                data = self.api.get_updates(buf)
                if "msgs" in data:
                    for raw in data["msgs"]:
                        if raw.get("message_type") == 1:
                            self._handle_raw(raw)
                if "get_updates_buf" in data:
                    buf = data["get_updates_buf"]
            except Exception as e:
                logger.warning(f"Poll error: {e}")
                time.sleep(5)

    def _handle_raw(self, raw: dict):
        content = raw.get("content", "")
        from_user = raw.get("from_username", "") or raw.get("from_user", "")
        if not from_user or not content:
            return
        cmsg = ChatMessage(
            channel_type="weixin", scene_id=self.scene_id,
            user_id=from_user, content=content,
        )
        context = self._compose_context(
            ContextType.TEXT, content, msg=cmsg,
            session_id=from_user, receiver=from_user,
        )
        if context:
            self.produce(context)

    def send(self, reply: Reply, context: Context):
        if not self.api:
            return
        receiver = context.get("receiver", "")
        if not receiver:
            return
        if reply.type == ReplyType.TEXT:
            self.api.send_message(receiver, reply.content)
        else:
            self.api.send_message(receiver, str(reply.content))

    def stop(self):
        self._running = False
        super().stop()


register_channel("weixin", WeixinChannel)
```

- [ ] **Step 2: Test import**

Run: `python -c "import sys; sys.path.insert(0,'py-agent'); from channels.weixin import WeixinChannel; print('weixin channel ok')"`
Expected: "weixin channel ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channels/weixin.py
git commit -m "refactor: WeixinChannel extends ChatChannel with session queue"
```

---

### Task 8: Rewrite Feishu channel

**Files:**
- Modify: `py-agent/channels/feishu.py` (entire file)

- [ ] **Step 1: Write the rewritten feishu.py**

```python
"""Feishu (飞书) channel via WebSocket mode (CowAgent ChatChannel pattern)."""
import sys, os, json, threading, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage
from channel_context import Context, ContextType, Reply, ReplyType
from chat_channel import ChatChannel
from channels.channel_base import ReconnectingChannel
from channels.channel_factory import register_channel

logger = logging.getLogger("cococat.feishu")
TOKEN_REFRESH_INTERVAL = 5400


class FeishuChannel(ChatChannel, ReconnectingChannel):
    channel_type = "feishu"

    def __init__(self):
        ChatChannel.__init__(self)
        ReconnectingChannel.__init__(self)
        self.app_id = ""
        self.app_secret = ""
        self._token = ""
        self._token_timer = None
        self._ws_thread = None

    def startup(self):
        self.app_id = self._config.get("app_id", "")
        self.app_secret = self._config.get("app_secret", "")
        if not self.app_id or not self.app_secret:
            raise RuntimeError("app_id and app_secret required")
        self._get_token()
        self._schedule_token_refresh()
        self.connected_state = Channel.CONN_CONNECTING
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._ws_thread.start()

    def _get_token(self):
        import requests
        r = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=10,
        )
        self._token = r.json().get("tenant_access_token", "")
        if self._token:
            logger.info("Token obtained/refreshed")

    def _schedule_token_refresh(self):
        self._token_timer = threading.Timer(TOKEN_REFRESH_INTERVAL, self._refresh_token)
        self._token_timer.daemon = True
        self._token_timer.start()

    def _refresh_token(self):
        self._get_token()
        self._schedule_token_refresh()

    def _ws_loop(self):
        try:
            import lark_oapi as lark
        except ImportError:
            logger.error("lark_oapi not installed")
            return

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
        self.report_startup_success()
        ws_client.start()

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
                try:
                    text_content = json.loads(content).get("text", "")
                except Exception:
                    text_content = content
            else:
                text_content = f"[{msg_type} message]"
            cmsg = ChatMessage(
                channel_type="feishu", scene_id=self.scene_id,
                user_id=sender_id, content=text_content,
            )
            context = self._compose_context(
                ContextType.TEXT, text_content, msg=cmsg,
                session_id=sender_id, receiver=sender_id,
            )
            if context:
                self.produce(context)
        except Exception as e:
            logger.error(f"Handle error: {e}")

    def send(self, reply: Reply, context: Context):
        import requests
        if not self._token:
            self._get_token()
        receiver = context.get("receiver", "")
        if not receiver:
            return
        url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        if reply.type == ReplyType.TEXT:
            body = {"receive_id": receiver, "msg_type": "text", "content": json.dumps({"text": reply.content})}
        else:
            body = {"receive_id": receiver, "msg_type": "text", "content": json.dumps({"text": str(reply.content)})}
        resp = requests.post(url, json=body, headers=headers, timeout=10)
        if resp.status_code in (401, 403):
            logger.warning("Token expired, refreshing and retrying")
            self._refresh_token()
            headers["Authorization"] = f"Bearer {self._token}"
            requests.post(url, json=body, headers=headers, timeout=10)

    def stop(self):
        self.stop_reconnect()
        if self._token_timer:
            self._token_timer.cancel()
        super().stop()


register_channel("feishu", FeishuChannel)
```

- [ ] **Step 2: Test import**

Run: `python -c "import sys; sys.path.insert(0,'py-agent'); from channels.feishu import FeishuChannel; print('feishu channel ok')"`
Expected: "feishu channel ok"

- [ ] **Step 3: Commit**

```bash
git add py-agent/channels/feishu.py
git commit -m "refactor: FeishuChannel extends ChatChannel with session queue"
```

---

### Task 9: Simplify entry_manager to use ChannelFactory

**Files:**
- Modify: `web/entry_manager.py`

- [ ] **Step 1: Replace _start_* functions with generic _start_entry using ChannelFactory**

Current `web/entry_manager.py` has 4 `_start_*` functions (lines 89-141) and a `_CHANNEL_REGISTRY` dict. Replace with:

```python
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
```

- [ ] **Step 2: Remove _CHANNEL_REGISTRY, _start_feishu, _start_telegram, _start_discord, _start_weixin**

Delete lines 89-149 (all `_start_*` functions and `_CHANNEL_REGISTRY`). Replace `_start_entry` usage in `start_agent_entries` and `start_scene_entries` to call `_start_entry` directly without the registry lookup.

The updated `start_agent_entries` should look like:

```python
def start_agent_entries(agent_id: str):
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
```

And `start_scene_entries`:

```python
def start_scene_entries(scene_id: str):
    entries_path = os.path.join(BASE_DIR, "scenes", scene_id, "entries.json")
    entries = _read_entry_config(entries_path)

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
        if channel == "web_api":
            print(f"[EntryManager] Web API entry for scene '{scene_id}' — handled by FastAPI routes")
        else:
            for target_agent in agents_in_scene:
                _start_entry(channel, scene_id, config, target_agent, "scene")
```

- [ ] **Step 3: Test import**

Run: `python -c "import sys; sys.path.insert(0,'web'); from entry_manager import start_all_entries; print('entry_manager imports ok')"`
Expected: "entry_manager imports ok"

- [ ] **Step 4: Commit**

```bash
git add web/entry_manager.py
git commit -m "refactor: entry_manager uses ChannelFactory, removes per-channel _start_* functions"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- Task 1 covers: ContextType, ReplyType, Context, Reply classes ✓
- Task 2 covers: enhanced Channel base class with 4-state connected, startup_event, send(Reply,Context) ✓
- Task 3 covers: ChannelFactory with register/create pattern ✓
- Task 4 covers: ChatChannel with produce/consume, _compose_context, reply pipeline, session mgmt ✓
- Task 5 covers: TelegramChannel extends ChatChannel ✓
- Task 6 covers: DiscordChannel extends ChatChannel ✓
- Task 7 covers: WeixinChannel extends ChatChannel ✓
- Task 8 covers: FeishuChannel extends ChatChannel + ReconnectingChannel ✓
- Task 9 covers: entry_manager simplification with ChannelFactory ✓

**2. Placeholder scan:** No TBD, TODO, "implement later", or fill-in patterns found.

**3. Type consistency:**
- `send(reply, context)` signature where reply is Reply and context is Context, consistent across all tasks ✓
- `connected_state` uses string constants from Channel class (CONN_DISCONNECTED etc.) ✓
- `_compose_context` returns `Context | None` consistently ✓
- `register_channel(channel_type, ChannelClass)` called at module level in each channel ✓
- `ChatChannel.__init__` does not take config — config is passed via `self._config` in `start()` (set by `start()` before calling `startup()`) — wait, actually in my current code the `start()` method calls `startup()` in a thread, but `self._config` is never set!

Let me fix this. The `Channel.start()` method should store config:

```python
def start(self, scene_id: str, config: dict):
    self.scene_id = scene_id
    self._config = config  # <-- needed!
    ...
```

Let me check all channel implementations to see if they use `self._config`... Yes, TelegramChannel uses `self._config.get("bot_token")`, WeixinChannel uses `self._config.get("credentials_file")`, etc. I need to add `self._config = config` in `Channel.start()`.

Let me fix Task 2 (channel.py) to include `self._config = config`.

Actually wait, looking at the current code for telegram.py in the plan:

```python
class TelegramChannel(ChatChannel):
    def startup(self):
        self.bot_token = self._config.get("bot_token", "")
```

But `self._config` is never set. This is a type consistency bug! The `Channel.start()` in Task 2 doesn't set `self._config`. I need to fix that.

Let me fix Task 2's `channel.py` to add `self._config = config`.

**4. Additional issues to fix:**
- The `ChatMessage` class is missing from the tasks — it's still used by channels but it's defined in the old `channel.py`. Since we're replacing `channel.py`, we need to keep `ChatMessage`. Let me add it to the new `channel.py` OR keep a separate `chat_message.py`.

Actually, looking at the new channel.py in Task 2, I removed `ChatMessage`. The channels still import it. Options:
1. Add ChatMessage back to channel.py
2. Put it in a separate file
3. Replace it with Context

Since we're aligning with CowAgent, `ChatMessage` serves a different purpose than `Context`: it's the *platform-level* message object (raw content + metadata from platform), while `Context` is the *pipeline-level* carrier. So ChatMessage should stay.

Let me add ChatMessage back to the enhanced channel.py — it's used by all channels. Actually, let me think about what ChatMessage is used for. Looking at the channels:

- Each channel creates `ChatMessage(channel_type=..., scene_id=..., user_id=..., content=...)` from raw platform data
- Then passes it to `_compose_context()` via kwargs as `msg=cmsg`
- The ChatMessage content goes into Context content

So ChatMessage is still needed. Let me add it to channel.py.

Let me fix the plan to address these issues before self-review.<｜end▁of▁thinking｜>**计划自检** — 发现一个类型一致性问题需要修复：

在 `Channel.start()` 中没有设置 `self._config`，但各 channel 的 `startup()` 中使用 `self._config.get(...)` 读取配置。同时 `ChatMessage` 类需要在新的 `channel.py` 中保留。

让我修复后再写：

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="edit">
<｜｜DSML｜｜parameter name="filePath" string="true">/home/leaif/CocoCat/docs/superpowers/plans/2026-05-07-channel-system-alignment.md