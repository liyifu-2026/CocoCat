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

# Shared state: latest QR code data (set by channel, read by web API)
_qr_state: dict = {"qrcode_url": "", "qrcode_id": "", "status": "idle"}  # idle / waiting / scanned / confirmed / failed
_qr_lock = threading.Lock()


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


def get_qr_state() -> dict:
    with _qr_lock:
        return dict(_qr_state)


def save_credentials(token: str, bot_id: str):
    creds = {"token": token, "bot_id": bot_id, "base_url": API_BASE}
    os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(creds, f)


def load_credentials() -> dict:
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE) as f:
            return json.load(f)
    return {}


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
        # Try saved credentials first
        creds = load_credentials()
        if creds.get("token"):
            self.api = WeixinApi(token=creds["token"], bot_id=creds.get("bot_id", ""))
            logger.info("Weixin logged in from saved credentials")
        else:
            # Interactive QR login
            if not self._do_qr_login():
                logger.error("Weixin QR login failed, channel not started")
                return

        self.report_startup_success()
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _do_qr_login(self) -> bool:
        """QR code login — publishes QR state for web UI, polls WeChat for scan."""
        session = requests.Session()
        session.headers.update(_build_headers())

        # Fetch QR
        try:
            resp = session.get(f"{API_BASE}/ilink/bot/get_bot_qrcode", params={"bot_type": 3}, timeout=15)
            data = resp.json()
            qrcode_id = data.get("qrcode", "")
            qrcode_url = data.get("qrcode_img_content", "") or qrcode_id
            if not qrcode_id:
                return False
        except Exception as e:
            logger.error(f"QR fetch failed: {e}")
            return False

        # Publish QR for web UI
        with _qr_lock:
            _qr_state["qrcode_url"] = qrcode_url
            _qr_state["qrcode_id"] = qrcode_id
            _qr_state["status"] = "waiting"

        logger.info(f"Weixin QR ready, scan with WeChat: {qrcode_url[:60]}...")

        # Poll for scan (up to 3 minutes)
        for _ in range(180):
            try:
                r = session.get(f"{API_BASE}/ilink/bot/get_qrcode_status",
                                params={"qrcode": qrcode_id}, timeout=30)
                status = r.json()
                s = status.get("status", "wait")
                if s == "scanned":
                    with _qr_lock:
                        _qr_state["status"] = "scanned"
                elif s == "confirmed":
                    save_credentials(status["bot_token"], status["ilink_bot_id"])
                    self.api = WeixinApi(token=status["bot_token"], bot_id=status["ilink_bot_id"])
                    with _qr_lock:
                        _qr_state["status"] = "confirmed"
                    logger.info("Weixin login successful!")
                    return True
                elif s == "expired":
                    with _qr_lock:
                        _qr_state["status"] = "expired"
                    return False
            except Exception:
                pass
            time.sleep(1)

        with _qr_lock:
            _qr_state["status"] = "timeout"
        return False

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
        context = self._compose_context(ContextType.TEXT, content, msg=cmsg, session_id=from_user, receiver=from_user)
        if context:
            self.produce(context)

    def send(self, reply: Reply, context: Context):
        if not self.api:
            return
        receiver = context.get("receiver", "")
        if not receiver:
            return
        self.api.send_message(receiver, reply.content if reply.type == ReplyType.TEXT else str(reply.content))

    def stop(self):
        self._running = False
        super().stop()


register_channel("weixin", WeixinChannel)
