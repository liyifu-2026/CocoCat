"""Discord channel via discord.py bot (generic pattern)."""
import sys, os, json, threading, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage


class DiscordChannel(Channel):
    channel_type = "discord"

    def __init__(self):
        super().__init__()
        self.bot_token = ""
        self._running = False
        self._thread = None
        self._loop = None

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        self.bot_token = config.get("bot_token", "")
        if not self.bot_token:
            print("[Discord] No bot_token provided")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_bot, daemon=True)
        self._thread.start()
        print(f"[Discord] Bot started for scene '{scene_id}'")

    def _run_bot(self):
        import discord
        intents = discord.Intents.default()
        intents.message_content = True

        class BotClient(discord.Client):
            def __init__(self, channel_ref):
                super().__init__(intents=intents)
                self.channel_ref = channel_ref

            async def on_ready(self):
                print(f"[Discord] Logged in as {self.user}")

            async def on_message(self, message):
                if message.author.bot:
                    return
                chat_msg = ChatMessage(
                    channel_type="discord",
                    scene_id=self.channel_ref.scene_id,
                    user_id=str(message.author.id),
                    content=message.content,
                )
                if self.channel_ref.on_message:
                    self.channel_ref.on_message(chat_msg)

            async def close(self):
                await super().close()

        client = BotClient(self)
        try:
            client.run(self.bot_token)
        except Exception as e:
            print(f"[Discord] Bot error: {e}")

    def send(self, reply: str, user_id: str):
        import discord
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._send_dm(user_id, reply))
            loop.close()
        except Exception as e:
            print(f"[Discord] Send error: {e}")

    async def _send_dm(self, user_id: str, reply: str):
        import discord
        intents = discord.Intents.default()
        intents.message_content = True
        async with discord.Client(intents=intents) as client:
            await client.login(self.bot_token)
            user = await client.fetch_user(int(user_id))
            if user:
                await user.send(reply)
            await client.close()
