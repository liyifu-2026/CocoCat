"""Tests for channel types and base."""
from cococat.core.channels.context import (
    ReplyType, MessageType,
    WECHAT_MP_CAPS, ILINK_CAPS, FEISHU_CAPS,
)
from cococat.core.channels.base import ChatMessage, ChannelBase


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
