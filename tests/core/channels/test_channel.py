"""Tests for channel types, base, capabilities, and channel factory."""
from cococat.core.channels.context import (
    ReplyType, MessageType, ContextType,
    WECHAT_MP_CAPS, ILINK_CAPS, FEISHU_CAPS,
    Context, Reply,
)
from cococat.core.channels.base import ChatMessage, ChannelBase


# ── ChatMessage tests (from tests/test_channel.py) ──

def test_chat_message_creation():
    msg = ChatMessage(channel_type="test", scene_id="s1", user_id="u1", content="hello")
    assert msg.channel_type == "test"
    assert msg.scene_id == "s1"
    assert msg.user_id == "u1"
    assert msg.content == "hello"


def test_chat_message_defaults():
    msg = ChatMessage(channel_type="t", scene_id="s", user_id="u", content="c")
    assert msg.msg_type == "text"
    assert msg.msg_id != ""


def test_chat_message_extra_kwargs():
    msg = ChatMessage(channel_type="t", scene_id="s", user_id="u", content="c", user_name="Alice")
    assert msg.extra.get("user_name") == "Alice"


# ── Channel state tests (from tests/test_channel.py) ──

def test_channel_4_state_constants():
    assert ChannelBase.CONN_DISCONNECTED == "disconnected"
    assert ChannelBase.CONN_CONNECTING == "connecting"
    assert ChannelBase.CONN_CONNECTED == "connected"
    assert ChannelBase.CONN_RECONNECTING == "reconnecting"


def test_channel_initial_state():
    ch = ChannelBase()
    assert ch.connected_state == ChannelBase.CONN_DISCONNECTED


def test_channel_is_running():
    ch = ChannelBase()
    assert ch.is_running() == False
    for state in (ChannelBase.CONN_CONNECTED, ChannelBase.CONN_CONNECTING, ChannelBase.CONN_RECONNECTING):
        ch.connected_state = state
        assert ch.is_running() == True
    ch.connected_state = ChannelBase.CONN_DISCONNECTED
    assert ch.is_running() == False


def test_channel_stop():
    ch = ChannelBase()
    ch.connected_state = ChannelBase.CONN_CONNECTED
    ch.stop()
    assert ch.connected_state == ChannelBase.CONN_DISCONNECTED


def test_channel_send_raises():
    ch = ChannelBase()
    try:
        ch.send("reply", "user1")
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass


def test_wait_startup_timeout():
    ch = ChannelBase()
    success, error = ch.wait_startup(timeout=0.01)
    assert success == False
    assert error == "timeout"


# ── Context tests (from tests/test_channel.py) ──

def test_context_creation():
    ctx = Context(ContextType.TEXT, "hello")
    assert ctx.type == ContextType.TEXT
    assert ctx.content == "hello"


def test_context_dict_access():
    ctx = Context(ContextType.TEXT, "hello", session_id="s1", receiver="u1")
    assert ctx["session_id"] == "s1"
    assert ctx.get("receiver") == "u1"
    assert ctx.get("nonexistent", "default") == "default"


def test_context_setitem():
    ctx = Context(ContextType.TEXT, "hello")
    ctx["key"] = "value"
    assert ctx["key"] == "value"


def test_reply_creation():
    r = Reply(ReplyType.TEXT, "hello")
    assert r.type == ReplyType.TEXT
    assert r.content == "hello"


def test_context_type_enum():
    expected = ["text", "voice", "image", "image_create", "file", "video", "sharing", "function"]
    for val in expected:
        assert any(e.value == val for e in ContextType)


def test_reply_type_enum():
    expected = ["text", "voice", "image", "image_url", "file", "video", "video_url", "error", "info"]
    for val in expected:
        assert any(e.value == val for e in ReplyType)


def test_compose_context():
    class TestChannel(ChannelBase):
        channel_type = "test_ch"
        def startup(self): pass
        def send(self, r, c): pass

    ch = TestChannel()
    ctx = ch._compose_context(ContextType.TEXT, "hello", session_id="s1", receiver="u1")
    assert ctx.type == ContextType.TEXT
    assert ctx.content == "hello"
    assert ctx["channel_type"] == "test_ch"
    assert ctx["origin_ctype"] == ContextType.TEXT


def test_generate_reply_with_on_message():
    class TestChannel(ChannelBase):
        channel_type = "test"
        def startup(self): pass
        def send(self, r, c): pass

    ch = TestChannel()
    received = []
    ch.on_message = lambda m: received.append(m.content)
    ctx = Context(ContextType.TEXT, "route_me", msg=ChatMessage(content="route_me"), session_id="s1", receiver="u1")
    reply = ch._generate_reply(ctx)
    assert received == ["route_me"]
    assert reply.content == ""


def test_generate_reply_echo_stub():
    class TestChannel(ChannelBase):
        channel_type = "test"
        def startup(self): pass
        def send(self, r, c): pass

    ch = TestChannel()
    ctx = Context(ContextType.TEXT, "echo", msg=ChatMessage(content="echo"), session_id="s1", receiver="u1")
    reply = ch._generate_reply(ctx)
    assert reply.content == "echo"


# ── Channel factory tests (from tests/test_channel.py) ──

def test_channel_factory():
    from cococat.core.channels.factory import register_channel, create_channel

    class FakeChannel(ChannelBase):
        channel_type = "fake"
        def startup(self): pass
        def send(self, r, c): pass

    register_channel("fake", FakeChannel)
    ch = create_channel("fake")
    assert isinstance(ch, FakeChannel)


def test_channel_factory_unknown():
    from cococat.core.channels.factory import create_channel
    try:
        create_channel("nonexistent")
        assert False
    except ValueError:
        pass


def test_weixin_channel_import():
    from cococat.core.channels.weixin import WeixinChannel
    assert WeixinChannel.channel_type == "weixin"


def test_feishu_channel_import():
    from cococat.core.channels.feishu import FeishuChannel
    assert FeishuChannel.channel_type == "feishu"


def test_telegram_channel_import():
    from cococat.core.channels.telegram import TelegramChannel
    assert TelegramChannel.channel_type == "telegram"


def test_discord_channel_import():
    from cococat.core.channels.discord import DiscordChannel
    assert DiscordChannel.channel_type == "discord"


def test_wechat_channel_import():
    from cococat.core.channels.wechat import WeChatChannel
    assert WeChatChannel.channel_type == "wechat"


def test_factory_all_channels_registered():
    from cococat.core.channels.factory import create_channel
    expected = {"weixin", "feishu", "telegram", "discord", "wechat"}
    for ct in expected:
        ch = create_channel(ct)
        assert ch.channel_type == ct


def test_weixin_qr_state():
    from cococat.core.channels.weixin import get_qr_state
    state = get_qr_state()
    assert "qrcode_url" in state
    assert "qrcode_id" in state
    assert "status" in state
    assert state["status"] in ("idle", "waiting", "scanned", "confirmed", "expired", "timeout")


def test_wechat_passive_reply():
    from cococat.core.channels.wechat import WeChatChannel
    ch = WeChatChannel()
    try:
        ch.send(None, None)
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass


# ── Channel capabilities tests (from tests/cococat/test_channel.py) ──

class TestChannel(ChannelBase):
    """Minimal channel for testing."""
    channel_type = "test"

    def __init__(self):
        super().__init__()
        self.caps = ILINK_CAPS
        self.sent: list = []

    def startup(self):
        self.report_startup_success()

    def send(self, reply, context):
        self.sent.append((reply, context))
        return True


def test_message_types():
    msg = ChatMessage(
        channel_type="wechat",
        user_id="user123",
        content="Hello",
        msg_type="text",
    )
    assert msg.content == "Hello"


def test_message_with_media():
    msg = ChatMessage(
        channel_type="ilink",
        user_id="user456",
        content="Check this",
    )
    assert msg.user_id == "user456"


def test_wechat_caps():
    assert WECHAT_MP_CAPS.can_receive(MessageType.TEXT)
    assert WECHAT_MP_CAPS.can_receive(MessageType.IMAGE)
    assert not WECHAT_MP_CAPS.can_receive(MessageType.FILE)
    assert WECHAT_MP_CAPS.can_send(ReplyType.TEXT)
    assert WECHAT_MP_CAPS.can_send(ReplyType.CARD)
    assert not WECHAT_MP_CAPS.streaming


def test_ilink_caps():
    assert ILINK_CAPS.can_receive(MessageType.FILE)
    assert ILINK_CAPS.can_receive(MessageType.VIDEO)
    assert ILINK_CAPS.chunk_long_text
    assert ILINK_CAPS.max_text_length == 4000


def test_feishu_caps():
    assert FEISHU_CAPS.streaming
    assert FEISHU_CAPS.cards
    assert FEISHU_CAPS.reactions
    assert FEISHU_CAPS.threads
    assert FEISHU_CAPS.can_receive(MessageType.POST)
    assert FEISHU_CAPS.can_send(ReplyType.CARD)


def test_chunk_text():
    ch = TestChannel()
    text = "A" * 8000
    chunks = ch.chunk_text(text)
    assert len(chunks) == 2
    assert len(chunks[0]) == 4000


def test_chunk_text_short():
    ch = TestChannel()
    chunks = ch.chunk_text("Hello")
    assert len(chunks) == 1
    assert chunks[0] == "Hello"


def test_reply_helpers():
    ch = TestChannel()
    assert ch.text_reply("Hi").type == ReplyType.TEXT
    assert ch.image_reply("/tmp/x.png").type == ReplyType.IMAGE
    assert ch.file_reply("/tmp/x.pdf").type == ReplyType.FILE
    assert ch.card_reply({}).type == ReplyType.CARD


def test_send_chunked():
    ch = TestChannel()
    sent_chunks = []
    ch.send_chunked("Hello world", lambda chunk: sent_chunks.append(chunk))
    assert len(sent_chunks) == 1
    assert sent_chunks[0] == "Hello world"


def test_streaming_card():
    ch = TestChannel()
    card = ch.streaming_card({"title": "Loading..."}, replace_id="msg_1")
    assert card.streaming is True
    assert card.replace_message_id == "msg_1"
