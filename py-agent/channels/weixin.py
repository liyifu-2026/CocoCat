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
