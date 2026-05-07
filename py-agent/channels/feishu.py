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
