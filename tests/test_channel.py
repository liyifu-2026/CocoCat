from cococat.core.channels.base import ChannelBase, ChatMessage
from cococat.core.channels.context import Context, Reply, ContextType, ReplyType


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
