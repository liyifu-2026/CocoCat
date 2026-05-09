"""Tests for channel types and adapter."""
import pytest
from cococat.channel_types import (
    ChatMessage, Reply, ReplyType, MessageType,
    MediaAttachment, MediaCapabilities,
    WECHAT_MP_CAPS, ILINK_CAPS, FEISHU_CAPS,
)
from cococat.channel_adapter import ChannelAdapter


class TestAdapter(ChannelAdapter):
    """Minimal adapter for testing."""
    def __init__(self):
        super().__init__(ILINK_CAPS)
        self.sent: list = []

    async def start(self, scene_id, config):
        pass

    async def stop(self):
        pass

    async def send(self, reply, user_id):
        self.sent.append((reply, user_id))
        return True


def test_message_types():
    msg = ChatMessage(
        channel_type="wechat",
        user_id="user123",
        content="Hello",
        msg_type=MessageType.TEXT,
    )
    assert msg.content == "Hello"
    assert msg.media == []


def test_message_with_media():
    msg = ChatMessage(
        channel_type="ilink",
        user_id="user456",
        content="Check this",
        msg_type=MessageType.IMAGE,
        media=[MediaAttachment(type="image", media_id="img_001", url="http://x.com/i.jpg")],
    )
    assert len(msg.media) == 1
    assert msg.media[0].media_id == "img_001"


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
    adapter = TestAdapter()
    text = "A" * 8000
    chunks = adapter.chunk_text(text)
    assert len(chunks) == 2
    assert len(chunks[0]) == 4000


def test_chunk_text_short():
    adapter = TestAdapter()
    chunks = adapter.chunk_text("Hello")
    assert len(chunks) == 1
    assert chunks[0] == "Hello"


def test_adapter_reply_helpers():
    adapter = TestAdapter()
    assert adapter.text_reply("Hi").type == ReplyType.TEXT
    assert adapter.image_reply("/tmp/x.png").type == ReplyType.IMAGE
    assert adapter.file_reply("/tmp/x.pdf").type == ReplyType.FILE
    assert adapter.card_reply({}).type == ReplyType.CARD


@pytest.mark.asyncio
async def test_adapter_send_text():
    adapter = TestAdapter()
    await adapter.send_chunked("Hello world", "user1")
    assert len(adapter.sent) == 1
    assert adapter.sent[0][0].type == ReplyType.TEXT


@pytest.mark.asyncio
async def test_streaming_card():
    adapter = TestAdapter()
    card = adapter.streaming_card({"title": "Loading..."}, replace_id="msg_1")
    assert card.streaming is True
    assert card.replace_message_id == "msg_1"
