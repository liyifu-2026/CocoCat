"""Telegram channel via Bot API polling (CowAgent pattern)."""
import sys, os, json, time, threading, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage


class TelegramChannel(Channel):
    channel_type = "telegram"

    def __init__(self):
        super().__init__()
        self.bot_token = ""
        self.api_base = ""
        self._running = False
        self._poll_thread = None
        self._last_update_id = 0

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        self.bot_token = config.get("bot_token", "")
        if not self.bot_token:
            print("[Telegram] No bot_token provided")
            return
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"
        try:
            resp = requests.get(f"{self.api_base}/getMe", timeout=10)
            if resp.status_code != 200:
                print(f"[Telegram] Invalid bot token: {resp.text}")
                return
            bot_name = resp.json().get("result", {}).get("first_name", "?")
            print(f"[Telegram] Bot '{bot_name}' started for scene '{scene_id}'")
        except Exception as e:
            print(f"[Telegram] Connection error: {e}")
            return
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self):
        while self._running:
            try:
                url = f"{self.api_base}/getUpdates"
                params = {"timeout": 30, "offset": self._last_update_id + 1}
                resp = requests.get(url, params=params, timeout=35)
                if resp.status_code != 200:
                    time.sleep(5)
                    continue
                data = resp.json()
                for update in data.get("result", []):
                    self._last_update_id = update.get("update_id", 0)
                    msg = update.get("message", {})
                    if "text" in msg:
                        chat_id = str(msg["chat"]["id"])
                        text = msg["text"]
                        chat_msg = ChatMessage(
                            channel_type="telegram", scene_id=self.scene_id,
                            user_id=chat_id, content=text,
                        )
                        if self.on_message:
                            self.on_message(chat_msg)
            except requests.Timeout:
                pass
            except Exception as e:
                print(f"[Telegram] Poll error: {e}")
                time.sleep(5)

    def send(self, reply: str, user_id: str):
        try:
            url = f"{self.api_base}/sendMessage"
            requests.post(url, json={"chat_id": user_id, "text": reply}, timeout=10)
        except Exception as e:
            print(f"[Telegram] Send error: {e}")
