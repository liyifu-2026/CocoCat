"""Personal WeChat channel via ilink bot API (CowAgent pattern)."""
import sys, os, json, time, threading, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage

API_BASE = "https://ilinkai.weixin.qq.com"


class WeixinApi:
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
        r = self.session.get(f"{self.base_url}/ilink/bot/get_bot_qrcode", params={"bot_type": 3})
        return r.json()

    def poll_qr(self, qrcode):
        r = self.session.get(f"{self.base_url}/ilink/bot/get_qrcode_status", params={"qrcode": qrcode})
        return r.json()

    def get_updates(self, buf=""):
        r = self.session.post(f"{self.base_url}/ilink/bot/getupdates", json={"buf": buf}, timeout=45)
        return r.json()

    def send_message(self, to_username: str, content: str):
        items = [{"type": 1, "content": content}]
        r = self.session.post(f"{self.base_url}/ilink/bot/sendmessage", json={
            "BaseRequest": {"to_username": to_username, "context_token": ""},
            "msg_items": items,
        })
        return r.json()


class WeixinChannel(Channel):
    channel_type = "weixin"

    def __init__(self):
        super().__init__()
        self.api = None
        self._running = False
        self._poll_thread = None
        self._credentials_file = ""

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        self._credentials_file = config.get("credentials_file", "") or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "agents", "_weixin_credentials.json"
        )
        self._login()
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _login(self):
        if os.path.exists(self._credentials_file):
            with open(self._credentials_file) as f:
                creds = json.load(f)
            self.api = WeixinApi(token=creds.get("token", ""), bot_id=creds.get("bot_id", ""))
            print("[WeChat] Logged in from saved credentials")
            return
        import qrcode
        print("[WeChat] Fetching QR code for login...")
        api = WeixinApi()
        qr_data = api.fetch_qr()
        qrcode_url = qr_data.get("qrcode", "")
        if qrcode_url:
            qr = qrcode.QRCode()
            qr.add_data(qrcode_url)
            qr.print_ascii()
            print(f"[WeChat] Or open: {qrcode_url}")
            for _ in range(120):
                status = api.poll_qr(qrcode_url)
                if status.get("status") == "confirmed":
                    self.api = WeixinApi(token=status.get("bot_token"), bot_id=status.get("ilink_bot_id"))
                    creds = {"token": status["bot_token"], "bot_id": status["ilink_bot_id"], "base_url": API_BASE}
                    os.makedirs(os.path.dirname(self._credentials_file), exist_ok=True)
                    with open(self._credentials_file, "w") as f:
                        json.dump(creds, f)
                    print("[WeChat] Login successful!")
                    return
                time.sleep(1)
        print("[WeChat] Login timeout")

    def _poll_loop(self):
        buf = ""
        while self._running:
            try:
                data = self.api.get_updates(buf)
                if "msgs" in data:
                    for msg in data["msgs"]:
                        if msg.get("message_type") == 1:
                            self._handle_message(msg)
                if "get_updates_buf" in data:
                    buf = data["get_updates_buf"]
            except Exception as e:
                print(f"[WeChat] Poll error: {e}")
                time.sleep(5)

    def _handle_message(self, raw: dict):
        content = raw.get("content", "")
        from_user = raw.get("from_username", "") or raw.get("from_user", "")
        if not from_user or not content:
            return
        chat_msg = ChatMessage(
            channel_type="weixin", scene_id=self.scene_id,
            user_id=from_user, content=content,
        )
        if self.on_message:
            self.on_message(chat_msg)

    def send(self, reply: str, user_id: str):
        if self.api:
            self.api.send_message(user_id, reply)
