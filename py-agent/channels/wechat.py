"""WeChat Official Account channel."""
import sys
import os
import json
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage
from wechatpy import parse_message
from wechatpy.utils import check_signature


class WeChatChannel(Channel):
    channel_type = "wechat"

    def __init__(self):
        super().__init__()
        self.token = ""
        self.app_id = ""
        self.app_secret = ""

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        self.token = config.get("token", "")
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")

    def verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        try:
            check_signature(self.token, signature, timestamp, nonce)
            return True
        except Exception:
            return False

    def parse_wechat_message(self, body: bytes) -> ChatMessage | None:
        msg = parse_message(body)
        if msg.type == "text":
            content = msg.content
        elif msg.type == "voice":
            content = msg.recognition or "[voice message]"
        else:
            content = f"[{msg.type} message]"
        return ChatMessage(
            channel_type="wechat",
            scene_id=self.scene_id,
            user_id=msg.source,
            content=content,
            msg_type="text" if msg.type in ("text", "voice") else msg.type,
        )

    def make_reply(self, to_user: str, from_user: str, text: str) -> str:
        return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{text}]]></Content>
</xml>"""

    def send(self, reply: str, user_id: str):
        raise NotImplementedError("WeChat uses passive reply via HTTP response")
