"""Feishu (飞书) channel via WebSocket + REST API."""
import json, time, threading, requests, logging

from .base import ChannelBase, ChatMessage
from .context import Context, ContextType, Reply, ReplyType
from .factory import register_channel

logger = logging.getLogger("cococat.feishu")
API_BASE = "https://open.feishu.cn/open-apis"
WS_URL = "wss://open.feishu.cn/open-apis/ws/bot"


class FeishuChannel(ChannelBase):
    channel_type = "feishu"

    def __init__(self):
        super().__init__()
        self._app_id = ""
        self._app_secret = ""
        self._token = ""
        self._running = False
        self._ws_thread = None

    def startup(self):
        self._app_id = self._config.get("app_id", "")
        self._app_secret = self._config.get("app_secret", "")
        if not self._app_id or not self._app_secret:
            logger.error("Feishu app_id and app_secret not configured")
            return
        if not self._refresh_token():
            return
        self.report_startup_success()
        self._running = True
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._ws_thread.start()

    def _refresh_token(self) -> bool:
        try:
            resp = requests.post(
                f"{API_BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self._app_id, "app_secret": self._app_secret},
                timeout=10,
            )
            data = resp.json()
            self._token = data.get("tenant_access_token", "")
            if self._token:
                logger.info("Feishu tenant_access_token obtained")
                return True
            logger.error(f"Feishu auth failed: {data}")
            return False
        except Exception as e:
            logger.error(f"Feishu token request error: {e}")
            return False

    def _ws_loop(self):
        while self._running:
            try:
                import websocket
                ws = websocket.create_connection(
                    WS_URL,
                    header={"Authorization": f"Bearer {self._token}"},
                    timeout=60,
                )
                logger.info("Feishu WebSocket connected")
                while self._running:
                    try:
                        data = json.loads(ws.recv())
                        self._handle_ws(data)
                    except websocket.WebSocketTimeoutException:
                        continue
                    except Exception as e:
                        logger.warning(f"Feishu WS recv error: {e}")
                        break
                ws.close()
            except ImportError:
                logger.error("websocket-client not installed. Run: pip install websocket-client")
                time.sleep(300)
            except Exception as e:
                logger.warning(f"Feishu WS connect error: {e}")
                time.sleep(10)

    def _handle_ws(self, data: dict):
        header = data.get("header", {})
        event_type = header.get("event_type", "")
        if event_type != "im.message.receive_v1":
            return
        event = data.get("event", {})
        msg = event.get("message", {})
        if msg.get("message_type") != "text":
            return
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {}).get("open_id", "")
        content_str = msg.get("content", "{}")
        try:
            content = json.loads(content_str).get("text", "")
        except Exception:
            content = content_str
        message_id = msg.get("message_id", "")
        chat_id = msg.get("chat_id", "")
        if not content or (not sender_id and not chat_id):
            return
        user_id = sender_id or chat_id
        cmsg = ChatMessage(channel_type="feishu", scene_id=self.scene_id, user_id=user_id, content=content)
        context = self._compose_context(
            ContextType.TEXT, content, msg=cmsg, session_id=user_id,
            receiver=user_id, message_id=message_id, chat_id=chat_id,
        )
        if context:
            reply = self._generate_reply(context)
            if reply and reply.content:
                self.send(reply, context)

    def send(self, reply: Reply, context: Context):
        if not self._token:
            if not self._refresh_token():
                return
        receiver = context.get("receiver", "")
        if not receiver:
            return
        content = reply.content if reply.type == ReplyType.TEXT else str(reply.content)
        body = {
            "receive_id": receiver,
            "msg_type": "text",
            "content": json.dumps({"text": content}),
        }
        try:
            resp = requests.post(
                f"{API_BASE}/im/v1/messages?receive_id_type=open_id",
                json=body,
                headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                timeout=15,
            )
            data = resp.json()
            if data.get("code", -1) != 0:
                logger.warning(f"Feishu send error: {data}")
        except Exception as e:
            logger.warning(f"Feishu send exception: {e}")

    def stop(self):
        self._running = False
        super().stop()


register_channel("feishu", FeishuChannel)
