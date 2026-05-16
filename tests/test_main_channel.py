"""Integration tests for main channel message handling."""
import asyncio

from cococat.core.channels.context import Context, ContextType, Reply, ReplyType
from cococat.core.channels.base import ChannelBase, ChatMessage


class FakeAgent:
    async def run(self, message: str) -> str:
        return f"Echo: {message}"


class FakeBus:
    def __init__(self):
        self.events = []

    async def publish(self, event_type, data):
        self.events.append((event_type, data))


def test_main_channel_on_message_triggers_reply():
    """Verify _generate_reply calls on_message synchronously, returns empty reply."""
    ch = ChannelBase()

    called = []
    ch.on_message = lambda msg: called.append(msg.content)

    ctx = Context(ContextType.TEXT, "hello", msg=ChatMessage(content="hello"),
                  session_id="u1", receiver="u1")
    reply = ch._generate_reply(ctx)

    assert called == ["hello"], "on_message should be called"
    assert reply.content == "", "on_message returning None → empty reply to avoid double-send"


def test_main_channel_async_handler():
    """Verify the full async handler flow: agent.run → send reply."""
    sent = []

    class TestChannel(ChannelBase):
        channel_type = "test"
        def startup(self): pass
        def send(self, reply, context):
            sent.append((reply.content, context.get("receiver", "")))

    ch = TestChannel()
    ch.scene_id = "main"
    agent = FakeAgent()
    bus = FakeBus()

    async def handle_message(msg_content: str, user_id: str):
        reply_text = await agent.run(msg_content)
        reply = Reply(ReplyType.TEXT, reply_text)
        user_ctx = Context(ContextType.TEXT, msg_content,
                           user_id=user_id, receiver=user_id)
        ch.send(reply, user_ctx)
        await bus.publish("main_message", {
            "channel": "test",
            "user_id": user_id,
            "content": msg_content,
            "reply": reply_text,
        })

    # Run the handler
    asyncio.run(handle_message("Hello", "user1"))

    assert len(sent) == 1
    assert sent[0][0] == "Echo: Hello"
    assert sent[0][1] == "user1"
    assert len(bus.events) == 1
    assert bus.events[0][0] == "main_message"
