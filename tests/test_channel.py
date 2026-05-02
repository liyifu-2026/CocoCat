import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from channel import Channel, ChatMessage


def test_chat_message_creation():
    msg = ChatMessage(channel_type="test", scene_id="s1", user_id="u1", content="hello")
    assert msg.channel_type == "test"
    assert msg.scene_id == "s1"
    assert msg.user_id == "u1"
    assert msg.content == "hello"


def test_chat_message_to_dict():
    msg = ChatMessage(channel_type="test", scene_id="s1", user_id="u1", content="hello")
    d = msg.to_dict()
    assert d["channel_type"] == "test"
    assert d["content"] == "hello"


def test_chat_message_defaults():
    msg = ChatMessage(channel_type="t", scene_id="s", user_id="u", content="c")
    assert msg.msg_type == "text"
    assert msg.msg_id != ""


def test_channel_base_start_raises():
    ch = Channel()
    try:
        ch.start("test", {})
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass


def test_channel_base_send_raises():
    ch = Channel()
    try:
        ch.send("reply", "user1")
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass
