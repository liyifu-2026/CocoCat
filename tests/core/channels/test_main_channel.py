"""Integration tests for main channel message handling."""
import asyncio
import threading

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
    ch = ChannelBase()
    called = []
    ch.on_message = lambda msg: called.append(msg.content)
    ctx = Context(ContextType.TEXT, "hello", msg=ChatMessage(content="hello"),
                  session_id="u1", receiver="u1")
    reply = ch._generate_reply(ctx)
    assert called == ["hello"]
    assert reply.content == ""


def test_main_channel_async_handler():
    sent = []

    class TestChannel(ChannelBase):
        channel_type = "test"
        def startup(self): pass
        def send(self, reply, context):
            sent.append((reply.content, context.get("receiver", "")))

    ch = TestChannel()
    agent = FakeAgent()
    bus = FakeBus()

    async def handle_message(msg_content: str, user_id: str):
        reply_text = await agent.run(msg_content)
        reply = Reply(ReplyType.TEXT, reply_text)
        ch.send(reply, Context(ContextType.TEXT, msg_content,
                                user_id=user_id, receiver=user_id))
        await bus.publish("main_message", {"reply": reply_text})

    asyncio.run(handle_message("Hello", "user1"))

    assert len(sent) == 1
    assert sent[0][0] == "Echo: Hello"
    assert len(bus.events) == 1


def _schedule_coro(coro, loop):
    asyncio.run_coroutine_threadsafe(coro, loop)


def test_thread_to_event_loop_bridge():
    """Simulate background thread → event loop coroutine scheduling."""
    agent = FakeAgent()
    bus = FakeBus()
    sent = []

    async def main():
        loop = asyncio.get_running_loop()

        def background():
            async def _handle():
                reply_text = await agent.run("Hello")
                sent.append(reply_text)
                await bus.publish("msg", {"reply": reply_text})
            _schedule_coro(_handle(), loop)

        t = threading.Thread(target=background)
        t.start()
        t.join(timeout=5)
        await asyncio.sleep(0.2)

        assert sent == ["Echo: Hello"]
        assert len(bus.events) == 1

    asyncio.run(main())
