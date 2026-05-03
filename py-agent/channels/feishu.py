"""Feishu (飞书) channel via WebSocket mode (CowAgent pattern)."""
import sys, os, json, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage


class FeishuChannel(Channel):
    channel_type = "feishu"

    def __init__(self):
        super().__init__()
        self.app_id = ""
        self.app_secret = ""
        self._token = ""
        self._ws_thread = None

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")
        if not self.app_id or not self.app_secret:
            print("[Feishu] app_id and app_secret required")
            return
        self._get_token()
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._ws_thread.start()

    def _get_token(self):
        import requests
        r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
                          json={"app_id": self.app_id, "app_secret": self.app_secret})
        self._token = r.json().get("tenant_access_token", "")

    def _ws_loop(self):
        try:
            import lark_oapi as lark
        except ImportError:
            print("[Feishu] lark_oapi not installed")
            return

        def handle_message(msg):
            event = json.loads(lark.JSON.marshal(msg))
            self._handle_event(event)

        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(handle_message) \
            .build()

        ws_client = lark.ws.Client(self.app_id, self.app_secret, event_handler=event_handler,
                                   log_level=lark.LogLevel.DEBUG)
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
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        body = {"receive_id": user_id, "msg_type": "text", "content": json.dumps({"text": reply})}
        requests.post(url, json=body, headers=headers)
