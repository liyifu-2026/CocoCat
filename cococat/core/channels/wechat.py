"""WeChat Official Account channel."""
import time

try:
    from wechatpy import parse_message
    from wechatpy.utils import check_signature
except ImportError:
    parse_message = None
    check_signature = None

from .base import ChannelBase, ChatMessage
from .factory import register_channel


class WeChatChannel(ChannelBase):
    channel_type = "wechat"

    def __init__(self):
        super().__init__()
        self.token = ""
        self.app_id = ""
        self.app_secret = ""

    def startup(self):
        self.token = self._config.get("token", "")
        self.app_id = self._config.get("app_id", "")
        self.app_secret = self._config.get("app_secret", "")
        self.report_startup_success()

    def verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        if not check_signature:
            return False
        try:
            check_signature(self.token, signature, timestamp, nonce)
            return True
        except Exception:
            return False

    def parse_wechat_message(self, body: bytes) -> ChatMessage | None:
        if not parse_message:
            return None
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

    def send(self, reply, context):
        raise NotImplementedError("WeChat uses passive reply via HTTP response")


register_channel("wechat", WeChatChannel)
