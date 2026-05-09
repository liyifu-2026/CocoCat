"""EventBus — asyncio pub/sub for in-process messaging."""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Awaitable

logger = logging.getLogger("cococat.event_bus")

Handler = Callable[[Any], Awaitable[None] | None]


class EventBus:
    """Simple asyncio pub/sub event bus.

    No external message broker. No serialization. All handlers run in-process.
    A handler can be sync (returns None) or async (returns Awaitable).
    Handler exceptions are caught and logged — they never block other handlers.
    """

    def __init__(self):
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """Register a handler for an event type."""
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Handler) -> None:
        """Remove a handler from an event type."""
        handlers = self._subscribers[event_type]
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    async def publish(self, event_type: str, data: Any) -> None:
        """Publish an event to all subscribers of event_type.

        Handlers are called concurrently via asyncio.gather.
        Handler exceptions are caught and logged — they never propagate.
        """
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return

        async def _safe_call(h: Handler) -> None:
            try:
                result = h(data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception(
                    "EventBus handler error for event '%s'", event_type
                )

        tasks = [_safe_call(h) for h in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)
