"""Telegram channel via Bot API polling (CowAgent ChatChannel pattern)."""
import sys, os, json, time, threading, requests, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage
from channel_context import Context, ContextType, Reply, ReplyType
from chat_channel import ChatChannel
from channels.channel_factory import register_channel

logger = logging.getLogger("cococat.telegram")


class TelegramChannel(ChatChannel):
    channel_type = "telegram"

    def __init__(self):
        super().__init__()
        self.bot_token = ""
        self.api_base = ""
        self._running = False
        self._poll_thread = None
        self._last_update_id = 0

    def startup(self):
        self.bot_token = self._config.get("bot_token", "")
        if not self.bot_token:
            logger.error("No bot_token provided")
            return
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"
        resp = requests.get(f"{self.api_base}/getMe", timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"Invalid bot token: {resp.text}")
        bot_name = resp.json().get("result", {}).get("first_name", "?")
        logger.info(f"Bot '{bot_name}' started for scene '{self.scene_id}'")
        self.report_startup_success()

        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self):
        while self._running:
            try:
                resp = requests.get(
                    f"{self.api_base}/getUpdates",
                    params={"timeout": 30, "offset": self._last_update_id + 1},
                    timeout=35,
                )
                if resp.status_code != 200:
                    time.sleep(5)
                    continue
                for update in resp.json().get("result", []):
                    self._last_update_id = update.get("update_id", 0)
                    msg = update.get("message", {})
                    if "text" in msg:
                        chat_id = str(msg["chat"]["id"])
                        text = msg["text"]
                        cmsg = ChatMessage(
                            channel_type="telegram",
                            scene_id=self.scene_id,
                            user_id=chat_id,
                            content=text,
                        )
                        context = self._compose_context(
                            ContextType.TEXT, text, msg=cmsg,
                            session_id=chat_id, receiver=chat_id,
                        )
                        if context:
                            self.produce(context)
            except requests.Timeout:
                pass
            except Exception as e:
                logger.warning(f"Poll error: {e}")
                time.sleep(5)

    def send(self, reply: Reply, context: Context):
        receiver = context.get("receiver", "")
        if not receiver:
            logger.warning("No receiver in context")
            return
        try:
            if reply.type == ReplyType.TEXT:
                requests.post(
                    f"{self.api_base}/sendMessage",
                    json={"chat_id": receiver, "text": reply.content},
                    timeout=10,
                )
            elif reply.type == ReplyType.IMAGE_URL:
                requests.post(
                    f"{self.api_base}/sendPhoto",
                    json={"chat_id": receiver, "photo": reply.content},
                    timeout=10,
                )
            else:
                requests.post(
                    f"{self.api_base}/sendMessage",
                    json={"chat_id": receiver, "text": str(reply.content)},
                    timeout=10,
                )
        except Exception as e:
            logger.error(f"Send error: {e}")

    def stop(self):
        self._running = False
        super().stop()


register_channel("telegram", TelegramChannel)
