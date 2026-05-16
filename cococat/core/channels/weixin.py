"""Personal WeChat channel via ilink bot API."""
import os, json, time, threading, requests, logging, random, base64, uuid as _uuid

from .base import ChannelBase, ChatMessage
from .context import Context, ContextType, Reply, ReplyType
from .factory import register_channel

logger = logging.getLogger("cococat.weixin")
API_BASE = "https://ilinkai.weixin.qq.com"
CHANNEL_VERSION = "2.0.0"
CLIENT_VERSION = "131072"
CREDENTIALS_FILE = os.path.join("agents", "_weixin_credentials.json")

_qr_state: dict = {"qrcode_url": "", "qrcode_id": "", "status": "idle"}
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
    """ilink bot API wrapper."""

    def __init__(self, token="", base_url=API_BASE):
        self.token = token
        self.base_url = base_url.rstrip("/")

    def _post(self, endpoint: str, body: dict, timeout: int = 45) -> dict:
        url = f"{self.base_url}/{endpoint}"
        headers = _build_headers(self.token)
        body.setdefault("base_info", {}).setdefault("channel_version", CHANNEL_VERSION)
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            return {"ret": 0, "msgs": []}
        except Exception as e:
            logger.warning(f"Weixin API error {endpoint}: {e}")
            return {"ret": -1, "msgs": []}

    def get_updates(self, buf: str = "", timeout: int = 45) -> dict:
        return self._post("ilink/bot/getupdates", {"get_updates_buf": buf}, timeout=timeout)

    def send_text(self, to_user_id: str, text: str, context_token: str = "") -> dict:
        return self._post("ilink/bot/sendmessage", {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user_id,
                "client_id": _uuid.uuid4().hex[:16],
                "message_type": 2,
                "message_state": 2,
                "item_list": [{"type": 1, "text_item": {"text": text}}],
                "context_token": context_token,
            }
        })


class WeixinChannel(ChannelBase):
    channel_type = "weixin"

    def __init__(self):
        super().__init__()
        self.api = None
        self._running = False
        self._poll_thread = None
        self._context_tokens: dict[str, str] = {}

    def startup(self):
        logger.info("WeixinChannel startup begin, credentials=%s", bool(creds.get("token")))
        creds = load_credentials()
        if creds.get("token"):
            self.api = WeixinApi(token=creds["token"])
            with _qr_lock:
                _qr_state["status"] = "confirmed"
            logger.info("Weixin logged in from saved credentials")
        else:
            if not self._do_qr_login():
                logger.error("Weixin QR login failed, channel not started")
                return
        self.report_startup_success()
        logger.info("Weixin startup OK, starting poll thread")
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _do_qr_login(self) -> bool:
        session = requests.Session()
        session.headers.update(_build_headers())
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

        with _qr_lock:
            _qr_state.update({"qrcode_url": qrcode_url, "qrcode_id": qrcode_id, "status": "waiting"})
        logger.info("Weixin QR ready")

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
                    self.api = WeixinApi(token=status["bot_token"])
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
        logger.info("Weixin poll loop started")
        buf = ""
        while self._running:
            try:
                data = self.api.get_updates(buf, timeout=45)
                if data.get("ret", 0) != 0:
                    time.sleep(5)
                    continue
                if "msgs" in data:
                    logger.info("Weixin got %d msgs", len(data["msgs"]))
                    for raw in data["msgs"]:
                        if raw.get("message_type") == 1:
                            self._handle_raw(raw)
                if "get_updates_buf" in data:
                    buf = data.get("get_updates_buf", "")
                tokens = data.get("context_tokens", {})
                if isinstance(tokens, dict):
                    self._context_tokens = {str(k): str(v) for k, v in tokens.items() if k and v}
            except Exception as e:
                logger.warning(f"Weixin poll error: {e}")
                time.sleep(5)

    def _handle_raw(self, raw: dict):
        from_user = raw.get("from_user_id", "")
        ctx_token = raw.get("context_token", "")
        if ctx_token and from_user:
            self._context_tokens[from_user] = ctx_token

        content = _extract_text(raw.get("item_list", []))
        if not from_user or not content:
            return
        logger.info("Weixin msg from %s: %s", from_user, content[:50])
        cmsg = ChatMessage(channel_type="weixin", scene_id=self.scene_id, user_id=from_user, content=content)
        context = self._compose_context(ContextType.TEXT, content, msg=cmsg, session_id=from_user, receiver=from_user)
        if context:
            reply = self._generate_reply(context)
            if reply and reply.content:
                self.send(reply, context)

    def send(self, reply: Reply, context: Context):
        if not self.api:
            return
        receiver = context.get("receiver", "")
        if not receiver:
            return
        text = reply.content if reply.type == ReplyType.TEXT else str(reply.content)
        text = _strip_markdown(text)
        ctx_token = self._context_tokens.get(receiver, "")
        self.api.send_text(receiver, text, ctx_token)

    def stop(self):
        self._running = False
        with _qr_lock:
            _qr_state["status"] = "idle"
        if os.path.exists(CREDENTIALS_FILE):
            os.remove(CREDENTIALS_FILE)
            logger.info("Weixin credentials cleared on disconnect")
        super().stop()


def _extract_text(item_list: list) -> str:
    parts = []
    for item in item_list:
        if item.get("type") == 1:
            parts.append(item.get("text_item", {}).get("text", ""))
    return "".join(parts)


def _strip_markdown(text: str) -> str:
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


register_channel("weixin", WeixinChannel)
