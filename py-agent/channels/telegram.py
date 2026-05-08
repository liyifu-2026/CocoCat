"""Telegram channel via Bot API long-polling (ChatChannel pattern)."""
import sys, os, json, time, threading, requests, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import ChatMessage
from channel_context import Context, ContextType, Reply, ReplyType
from chat_channel import ChatChannel
from channels.channel_factory import register_channel

logger = logging.getLogger("cococat.telegram")
API_BASE = "https://api.telegram.org"


class TelegramChannel(ChatChannel):
    channel_type = "telegram"

    def __init__(self):
        super().__init__()
        self._token = ""
        self._running = False
        self._poll_thread = None

    def startup(self):
        self._token = self._config.get("bot_token", "")
        if not self._token:
            logger.error("Telegram bot_token not configured")
            return
        logger.info("Telegram bot starting...")
        self.report_startup_success()
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _api(self, method: str, data: dict | None = None) -> dict:
        url = f"{API_BASE}/bot{self._token}/{method}"
        try:
            if data:
                resp = requests.post(url, json=data, timeout=30)
            else:
                resp = requests.get(url, timeout=30)
            return resp.json()
        except Exception as e:
            logger.warning(f"Telegram API error ({method}): {e}")
            return {}

    def _poll_loop(self):
        offset = 0
        while self._running:
            try:
                updates = self._api("getUpdates", {"offset": offset, "timeout": 30})
                if updates.get("ok"):
                    for upd in updates.get("result", []):
                        offset = upd["update_id"] + 1
                        msg = upd.get("message") or upd.get("channel_post") or upd.get("edited_message")
                        if not msg:
                            continue
                        text = msg.get("text") or msg.get("caption", "")
                        chat_id = str(msg["chat"]["id"])
                        user_id = str(msg.get("from", {}).get("id", chat_id))
                        if not text:
                            continue
                        self._handle_raw(text, user_id, chat_id)
            except Exception as e:
                logger.warning(f"Telegram poll error: {e}")
                time.sleep(5)

    def _handle_raw(self, content: str, user_id: str, chat_id: str):
        cmsg = ChatMessage(channel_type="telegram", scene_id=self.scene_id, user_id=user_id, content=content)
        context = self._compose_context(ContextType.TEXT, content, msg=cmsg, session_id=user_id,
                                         receiver=user_id, chat_id=chat_id)
        if context:
            self.produce(context)

    def send(self, reply: Reply, context: Context):
        receiver = context.get("receiver", "")
        chat_id = context.kwargs.get("chat_id", receiver) if hasattr(context, "kwargs") else receiver
        if not chat_id:
            return
        text = reply.content if reply.type == ReplyType.TEXT else str(reply.content)
        # Split long messages for Telegram (4096 char limit)
        for chunk in _split_long(text, 4000):
            self._api("sendMessage", {"chat_id": chat_id, "text": chunk})

    def stop(self):
        self._running = False
        super().stop()


def _split_long(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = text.rfind(" ", 0, limit) if " " in text[:limit] else limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks


register_channel("telegram", TelegramChannel)
