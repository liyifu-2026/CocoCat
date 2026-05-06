"""Tests for message bus."""
import sys, os, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from message import InboundMessage, OutboundMessage
from bus import MessageBus


class TestMessageBus:
    def test_publish_inbound_delivers_to_subscriber(self):
        bus = MessageBus()
        received = []
        bus.subscribe_inbound(lambda m: received.append(m))
        msg = InboundMessage(channel="test", source="u1", content="hi", agent_id="a1")
        bus.publish_inbound(msg)
        assert len(received) == 1
        assert received[0].content == "hi"

    def test_publish_outbound_delivers_to_subscriber(self):
        bus = MessageBus()
        received = []
        bus.subscribe_outbound(lambda m: received.append(m))
        msg = OutboundMessage(channel="test", target="u1", content="hello")
        bus.publish_outbound(msg)
        assert len(received) == 1
        assert received[0].content == "hello"

    def test_multiple_inbound_subscribers(self):
        bus = MessageBus()
        r1, r2 = [], []
        bus.subscribe_inbound(lambda m: r1.append(m))
        bus.subscribe_inbound(lambda m: r2.append(m))
        bus.publish_inbound(InboundMessage(channel="t", source="u", content="x", agent_id="a"))
        assert len(r1) == 1 and len(r2) == 1

    def test_subscriber_error_does_not_block_others(self):
        bus = MessageBus()
        received = []

        def failing(m):
            raise RuntimeError("boom")

        bus.subscribe_inbound(failing)
        bus.subscribe_inbound(lambda m: received.append(m))
        bus.publish_inbound(InboundMessage(channel="t", source="u", content="x", agent_id="a"))
        assert len(received) == 1

    def test_wait_for_inbound_returns_message(self):
        bus = MessageBus()
        msg = InboundMessage(channel="t", source="u", content="x", agent_id="a")

        def publish():
            time.sleep(0.05)
            bus.publish_inbound(msg)

        threading.Thread(target=publish, daemon=True).start()
        result = bus.wait_for_inbound(timeout=1)
        assert result is not None
        assert result.content == "x"

    def test_wait_for_inbound_timeout(self):
        bus = MessageBus()
        result = bus.wait_for_inbound(timeout=0.1)
        assert result is None

    def test_drain_inbound(self):
        bus = MessageBus()
        bus.publish_inbound(InboundMessage(channel="t", source="u1", content="a", agent_id="a"))
        bus.publish_inbound(InboundMessage(channel="t", source="u2", content="b", agent_id="a"))
        drained = bus.drain_inbound()
        assert len(drained) == 2

    def test_drain_empty(self):
        bus = MessageBus()
        assert bus.drain_inbound() == []

    def test_subscribe_is_thread_safe(self):
        bus = MessageBus()
        errors = []

        def subscribe_many():
            for i in range(100):
                bus.subscribe_inbound(lambda m: None)

        threads = [threading.Thread(target=subscribe_many, daemon=True) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(bus._inbound_handlers) == 1000


class TestInboundMessage:
    def test_defaults(self):
        msg = InboundMessage(channel="t", source="u", content="c", agent_id="a")
        assert msg.scene_id == "default"
        assert msg.metadata == {}

    def test_custom_scene(self):
        msg = InboundMessage(channel="t", source="u", content="c", agent_id="a", scene_id="s1")
        assert msg.scene_id == "s1"


class TestOutboundMessage:
    def test_defaults(self):
        msg = OutboundMessage(channel="t", target="u", content="c")
        assert msg.metadata == {}
