"""Discord bot channel via discord.py (CowAgent ChatChannel pattern)."""
import sys, os, threading, asyncio, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage
from channel_context import Context, ContextType, Reply, ReplyType
from chat_channel import ChatChannel
from channels.channel_factory import register_channel

logger = logging.getLogger("cococat.discord")


class DiscordChannel(ChatChannel):
    channel_type = "discord"

    def __init__(self):
        super().__init__()
        self.bot_token = ""
        self._loop = None
        self._client = None
        self._bot_thread = None

    def startup(self):
        self.bot_token = self._config.get("bot_token", "")
        if not self.bot_token:
            raise RuntimeError("No bot_token provided")
        self._loop = asyncio.new_event_loop()
        self._bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self._bot_thread.start()

    def _run_bot(self):
        import discord
        asyncio.set_event_loop(self._loop)
        intents = discord.Intents.default()
        intents.message_content = True

        class BotClient(discord.Client):
            def __init__(self, channel_ref):
                super().__init__(intents=intents)
                self.channel_ref = channel_ref

            async def on_ready(self):
                self.channel_ref.connected_state = Channel.CONN_CONNECTED
                self.channel_ref.report_startup_success()
                logger.info(f"Discord logged in as {self.user}")

            async def on_message(self, message):
                if message.author.bot:
                    return
                cmsg = ChatMessage(
                    channel_type="discord",
                    scene_id=self.channel_ref.scene_id,
                    user_id=str(message.author.id),
                    content=message.content,
                )
                context = self.channel_ref._compose_context(
                    ContextType.TEXT, message.content, msg=cmsg,
                    session_id=str(message.author.id),
                    receiver=str(message.author.id),
                )
                if context:
                    self.channel_ref.produce(context)

        self._client = BotClient(self)
        try:
            self._client.run(self.bot_token, log_handler=None)
        except Exception as e:
            logger.error(f"Bot error: {e}")
            self.connected_state = Channel.CONN_DISCONNECTED

    def send(self, reply: Reply, context: Context):
        if not self._client or not self._client.is_ready():
            logger.warning("Bot not ready")
            return
        user_id = context.get("receiver", "")
        if not user_id:
            return
        async def _send():
            try:
                user = await self._client.fetch_user(int(user_id))
                await user.send(reply.content)
            except Exception as e:
                logger.error(f"Send error: {e}")
        asyncio.run_coroutine_threadsafe(_send(), self._loop)

    def stop(self):
        if self._client:
            asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
        super().stop()


register_channel("discord", DiscordChannel)
