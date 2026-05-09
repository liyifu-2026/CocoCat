"""Discord channel via WebSocket Gateway + REST API (ChatChannel pattern)."""
import sys, os, json, time, threading, requests, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import ChatMessage
from channel_context import Context, ContextType, Reply, ReplyType
from chat_channel import ChatChannel
from channels.channel_factory import register_channel

logger = logging.getLogger("cococat.discord")
API_BASE = "https://discord.com/api/v10"
GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"


class DiscordChannel(ChatChannel):
    channel_type = "discord"

    def __init__(self):
        super().__init__()
        self._token = ""
        self._running = False
        self._ws_thread = None
        self._seq = None
        self._session_id = None

    def startup(self):
        self._token = self._config.get("bot_token", "")
        if not self._token:
            logger.error("Discord bot_token not configured")
            return
        self.report_startup_success()
        self._running = True
        self._ws_thread = threading.Thread(target=self._gateway_loop, daemon=True)
        self._ws_thread.start()

    def _api_get(self, path: str) -> dict:
        try:
            resp = requests.get(f"{API_BASE}{path}", headers={"Authorization": f"Bot {self._token}"}, timeout=15)
            return resp.json() if resp.status_code == 200 else {}
        except Exception:
            return {}

    def _api_post(self, path: str, data: dict) -> dict:
        try:
            resp = requests.post(
                f"{API_BASE}{path}",
                json=data,
                headers={"Authorization": f"Bot {self._token}", "Content-Type": "application/json"},
                timeout=15,
            )
            return resp.json()
        except Exception:
            return {}

    def _gateway_loop(self):
        while self._running:
            try:
                import websocket
                ws = websocket.create_connection(GATEWAY_URL, timeout=60)
                self._ws_handshake(ws)
            except ImportError:
                logger.error("websocket-client not installed. Run: pip install websocket-client")
                time.sleep(300)
                continue
            except Exception as e:
                logger.warning(f"Discord gateway connect error: {e}")
                time.sleep(10)
                continue

    def _ws_handshake(self, ws):
        # Receive HELLO
        hello = json.loads(ws.recv())
        heartbeat_interval = hello.get("d", {}).get("heartbeat_interval", 41250)
        logger.info(f"Discord gateway hello, heartbeat: {heartbeat_interval}ms")

        # Send IDENTIFY
        identify = {
            "op": 2,
            "d": {
                "token": f"Bot {self._token}",
                "intents": 1 << 9,  # GUILD_MESSAGES
                "properties": {"os": "linux", "browser": "cococat", "device": "cococat"},
            },
        }
        ws.send(json.dumps(identify))

        # Start heartbeat thread
        hb_thread = threading.Thread(target=self._heartbeat, args=(ws, heartbeat_interval), daemon=True)
        hb_thread.start()

        # Main event loop
        while self._running:
            try:
                data = json.loads(ws.recv())
                op = data.get("op", -1)
                if op == 0:  # DISPATCH
                    self._seq = data.get("s")
                    if data.get("t") == "MESSAGE_CREATE":
                        self._handle_dispatch(data["d"])
                elif op == 7:  # RECONNECT
                    logger.info("Discord requested reconnect")
                    ws.close()
                    return
                elif op == 9:  # INVALID_SESSION
                    logger.warning("Discord invalid session, re-identifying")
                    ws.send(json.dumps(identify))
                elif op == 11:  # HEARTBEAT_ACK
                    pass
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                logger.warning(f"Discord WS recv error: {e}")
                break

    def _heartbeat(self, ws, interval_ms: int):
        while self._running:
            time.sleep(interval_ms / 1000.0)
            try:
                ws.send(json.dumps({"op": 1, "d": self._seq}))
            except Exception:
                break

    def _handle_dispatch(self, msg: dict):
        content = msg.get("content", "")
        if not content or msg.get("author", {}).get("bot", False):
            return
        author = msg.get("author", {})
        user_id = author.get("id", "")
        username = author.get("username", "unknown")
        channel_id = msg.get("channel_id", "")

        cmsg = ChatMessage(
            channel_type="discord",
            scene_id=self.scene_id,
            user_id=user_id,
            content=content,
        )
        context = self._compose_context(
            ContextType.TEXT, content, msg=cmsg,
            session_id=user_id, receiver=user_id,
            channel_id=channel_id, username=username,
        )
        if context:
            self.produce(context)

    def send(self, reply: Reply, context: Context):
        channel_id = context.get("channel_id", "") or getattr(context, "kwargs", {}).get("channel_id", "")
        if not channel_id:
            return
        content = reply.content if reply.type == ReplyType.TEXT else str(reply.content)
        # Discord supports Markdown natively
        for chunk in _split_long(content, 1900):
            self._api_post(f"/channels/{channel_id}/messages", {"content": chunk})

    def stop(self):
        self._running = False
        super().stop()


def _split_long(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = text.rfind(" ", 0, limit) if " " in text[:limit] else limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks


register_channel("discord", DiscordChannel)
