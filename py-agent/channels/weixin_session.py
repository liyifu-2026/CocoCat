"""WeChat QR login session manager — shared between web API and channel."""
import json, os, threading, time, requests, logging, random, base64

logger = logging.getLogger("cococat.weixin")
API_BASE = "https://ilinkai.weixin.qq.com"
CHANNEL_VERSION = "2.0.0"
CLIENT_VERSION = "131072"

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agents", "_weixin_credentials.json")

_sessions: dict[str, dict] = {}
_lock = threading.Lock()


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


def fetch_qr() -> dict:
    """Fetch a fresh QR code from WeChat ilink API. Returns {qrcode_id, qrcode_url}."""
    session = requests.Session()
    session.headers.update(_build_headers())
    resp = session.get(f"{API_BASE}/ilink/bot/get_bot_qrcode", params={"bot_type": 3}, timeout=15)
    data = resp.json()
    return {
        "qrcode_id": data.get("qrcode", ""),
        "qrcode_url": data.get("qrcode_img_content", "") or data.get("qrcode", ""),
    }


def poll_qr(qrcode_id: str) -> dict:
    """Poll WeChat API for QR scan status. Returns {status, bot_token, bot_id}."""
    session = requests.Session()
    session.headers.update(_build_headers())
    try:
        resp = session.get(
            f"{API_BASE}/ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode_id},
            timeout=30,
        )
        data = resp.json()
        return {
            "status": data.get("status", "wait"),
            "bot_token": data.get("bot_token", ""),
            "bot_id": data.get("ilink_bot_id", ""),
        }
    except requests.exceptions.Timeout:
        return {"status": "wait"}


def save_credentials(token: str, bot_id: str):
    creds = {"token": token, "bot_id": bot_id, "base_url": API_BASE}
    os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(creds, f)
    logger.info("WeChat credentials saved")


def load_credentials() -> dict:
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE) as f:
            return json.load(f)
    return {}
