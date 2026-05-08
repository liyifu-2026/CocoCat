"""Personal WeChat channel via ilink bot API (ChatChannel pattern)."""
import sys, os, json, time, threading, requests, logging, random, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import ChatMessage
from channel_context import Context, ContextType, Reply, ReplyType
from chat_channel import ChatChannel
from channels.channel_factory import register_channel

logger = logging.getLogger("cococat.weixin")
API_BASE = "https://ilinkai.weixin.qq.com"
CHANNEL_VERSION = "2.0.0"
CLIENT_VERSION = "131072"
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agents", "_weixin_credentials.json")


def _random_wechat_uin() -> str:
    return base64.b64encode(str(random.randint(0, 0xFFFFFFFF)).encode()).decode()


def _build_headers(token: str = "") -> dict:
    h = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": _random_wechat_uin(),
        "iLink-App-Id": "bot",
        "iLink-App-ClientVersion": CLIENT_VERSION,
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


class WeixinApi:
    def __init__(self, token="", bot_id="", base_url=API_BASE):
        self.token = token
        self.bot_id = bot_id
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(_build_headers(token))

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

    def startup(self):
        self._login()
        self.report_startup_success()
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _login(self):
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE) as f:
                creds = json.load(f)
            self.api = WeixinApi(token=creds.get("token", ""), bot_id=creds.get("bot_id", ""))
            if self.api.token:
                logger.info("Weixin logged in from saved credentials")
                return

        # Fallback: terminal-based QR login (for CLI usage)
        from channels.weixin_session import fetch_qr, poll_qr, save_credentials
        import qrcode as qr_lib

        qr = fetch_qr()
        qrcode_id = qr["qrcode_id"]
        qrcode_url = qr["qrcode_url"]
        if not qrcode_id:
            logger.error("Failed to fetch WeChat QR code")
            return

        # Print QR in terminal
        try:
            qr_img = qr_lib.QRCode(border=1)
            qr_img.add_data(qrcode_url)
            qr_img.make(fit=True)
            qr_img.print_ascii(invert=True)
        except Exception:
            print(f"\n  微信登录链接: {qrcode_url}\n")
        print("  等待扫码...\n")

        for _ in range(120):
            status = poll_qr(qrcode_id)
            if status["status"] == "confirmed":
                save_credentials(status["bot_token"], status["bot_id"])
                self.api = WeixinApi(token=status["bot_token"], bot_id=status["bot_id"])
                logger.info("Weixin login successful!")
                return
            time.sleep(1)
        logger.error("Weixin login timeout")

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
                logger.warning(f"Weixin poll error: {e}")
                time.sleep(5)

    def _handle_raw(self, raw: dict):
        content = raw.get("content", "")
        from_user = raw.get("from_username", "") or raw.get("from_user", "")
        if not from_user or not content:
            return
        cmsg = ChatMessage(channel_type="weixin", scene_id=self.scene_id, user_id=from_user, content=content)
        context = self._compose_context(
            ContextType.TEXT, content, msg=cmsg, session_id=from_user, receiver=from_user,
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
