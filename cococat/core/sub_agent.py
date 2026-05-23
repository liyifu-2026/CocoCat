"""Sub-agent executor — async fire-and-forget task delegation."""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.core.event_bus import EventBus
    from cococat.core.sandbox import ExecutorProvider

logger = logging.getLogger("cococat.sub_agent")


class SubAgentExecutor:
    """Dispatches sub-agent tasks via ExecutorProvider (fire-and-forget).

    Publishes sub_agent_complete events with task results.
    """

    def __init__(
        self,
        bus: EventBus,
        sandbox_provider: ExecutorProvider | None = None,
    ):
        self._bus = bus
        self._sandbox = sandbox_provider

    async def dispatch(self, task: str, from_agent: str = "main",
                        session_id: str | None = None,
                        mode: str = "default") -> str:
        """Dispatch a task to a sub-agent sandbox. Returns result string."""
        if not self._sandbox:
            logger.warning("No executor configured for dispatch from %s", from_agent)
            return "Error: No executor configured"

        task_id = uuid.uuid4().hex[:12]

        try:
            result = await self._sandbox.run_once(
                prompt=task,
                agent_id=f"sub-{task_id}",
                session_id=session_id,
                mode=mode,
            )
            await self._bus.publish("sub_agent_complete", {
                "task_id": task_id,
                "from_agent": from_agent,
                "agent_id": f"sub-{task_id}",
                "result": result,
            })
            return result
        except Exception as e:
            logger.exception("Sub-agent sandbox task %s failed", task_id)
            await self._bus.publish("sub_agent_complete", {
                "task_id": task_id,
                "from_agent": from_agent,
                "agent_id": f"sub-{task_id}",
                "error": str(e),
            })
            return f"Error: {e}"
