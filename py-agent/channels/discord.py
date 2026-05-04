"""Discord bot channel implementation."""
import threading
import logging
import asyncio
import time

logger = logging.getLogger("cococat.discord")

try:
    import discord
    from discord import Intents, Client
except ImportError:
    discord = None
    Client = None
    Intents = None

from channel import Channel, ChatMessage


class BotClient(discord.Client):
    def __init__(self, channel_instance):
        intents = Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.channel_instance = channel_instance

    async def on_ready(self):
        logger.info(f"Discord bot logged in as {self.user}")

    async def on_message(self, message):
        if message.author == self.user:
            return
        if self.channel_instance.on_message:
            msg = ChatMessage(
                content=message.content,
                user_id=str(message.author.id),
                user_name=message.author.name,
            )
            self.channel_instance.on_message(msg)


class DiscordChannel(Channel):
    def start(self, scene_id: str, config: dict):
        bot_token = config.get("bot_token")
        if not bot_token:
            logger.error("Discord: bot_token not configured")
            return
        self._bot_token = bot_token
        self._loop = asyncio.new_event_loop()
        self._client = BotClient(self)
        self._thread = threading.Thread(target=self._run_bot, daemon=True)
        self._thread.start()

    def _run_bot(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._client.run(self._bot_token, log_handler=None)
        except Exception as e:
            logger.error(f"Discord bot error: {e}")

    def stop(self):
        if self._client:
            self._client.close()

    def send(self, reply: str, user_id: str):
        if not self._client or not self._client.is_ready():
            logger.warning("Discord: bot not ready")
            return
        async def _send():
            try:
                user = await self._client.fetch_user(int(user_id))
                await user.send(reply)
            except Exception as e:
                logger.error(f"Discord send error: {e}")
        asyncio.run_coroutine_threadsafe(_send(), self._loop).result(timeout=10)
