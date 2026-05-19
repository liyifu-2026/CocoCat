"""Tests for cococat.core.event_bus."""
import asyncio
import pytest
from cococat.core.event_bus import EventBus


@pytest.mark.asyncio
async def test_publish_subscribe():
    bus = EventBus()
    received = []

    async def handler(msg):
        received.append(msg)

    bus.subscribe("test", handler)
    await bus.publish("test", {"foo": "bar"})
    await asyncio.sleep(0)  # let async handlers run
    assert received == [{"foo": "bar"}]


@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = EventBus()
    received = []

    bus.subscribe("test", lambda msg: received.append(("a", msg)))
    bus.subscribe("test", lambda msg: received.append(("b", msg)))
    await bus.publish("test", {"data": 1})
    await asyncio.sleep(0)
    assert ("a", {"data": 1}) in received
    assert ("b", {"data": 1}) in received


@pytest.mark.asyncio
async def test_different_events():
    bus = EventBus()
    received_test = []
    received_other = []

    bus.subscribe("test", lambda msg: received_test.append(msg))
    bus.subscribe("other", lambda msg: received_other.append(msg))
    await bus.publish("test", {"x": 1})
    await bus.publish("other", {"y": 2})
    await asyncio.sleep(0)
    assert received_test == [{"x": 1}]
    assert received_other == [{"y": 2}]


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received = []

    handler = lambda msg: received.append(msg)
    bus.subscribe("test", handler)
    await bus.publish("test", {"first": True})
    bus.unsubscribe("test", handler)
    await bus.publish("test", {"second": True})
    await asyncio.sleep(0)
    assert received == [{"first": True}]


@pytest.mark.asyncio
async def test_no_subscribers_no_error():
    bus = EventBus()
    # Should not raise
    await bus.publish("no_listeners", {"msg": "hello"})
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_async_handler():
    bus = EventBus()
    received = []

    async def async_handler(msg):
        await asyncio.sleep(0.01)
        received.append(msg)

    bus.subscribe("test", async_handler)
    await bus.publish("test", {"async": True})
    await asyncio.sleep(0.05)
    assert received == [{"async": True}]


@pytest.mark.asyncio
async def test_handler_exception_does_not_block_others():
    bus = EventBus()
    received = []

    def failing(msg):
        raise RuntimeError("boom")

    def ok(msg):
        received.append(msg)

    bus.subscribe("test", failing)
    bus.subscribe("test", ok)
    await bus.publish("test", {"data": 1})
    await asyncio.sleep(0)
    assert received == [{"data": 1}]
