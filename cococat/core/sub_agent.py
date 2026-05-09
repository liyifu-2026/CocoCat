"""Sub-agent executor — async fire-and-forget task delegation."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.core.event_bus import EventBus
    from cococat.core.agent_pool import AgentPool
    from cococat.core.agent import Agent

logger = logging.getLogger("cococat.sub_agent")


class SubAgentExecutor:
    """Manages async sub-agent task dispatch and result delivery.

    Fire-and-forget pattern:
    1. Main AI calls dispatch(task, from_agent="main")
    2. Free sub agent is found and runs agent.run(task)
    3. Result published to EventBus as sub_agent_complete event
    4. Sub agent returns to available pool
    """

    def __init__(self, bus: EventBus, pool: AgentPool):
        self._bus = bus
        self._pool = pool
        self._busy: set[str] = set()  # agent IDs currently executing a task

    async def dispatch(self, task: str, from_agent: str = "main") -> str | None:
        """Dispatch a task to a free sub agent. Returns task_id or None if no free agents."""
        free = [
            a for a in self._pool.get_free_sub_agents()
            if a.id not in self._busy
        ]
        if not free:
            logger.warning("No free sub agents for task from %s", from_agent)
            return None

        agent = free[0]
        self._busy.add(agent.id)
        task_id = uuid.uuid4().hex[:12]

        async def _run():
            try:
                result = await agent.run(task)
                await self._bus.publish("sub_agent_complete", {
                    "task_id": task_id,
                    "from_agent": from_agent,
                    "agent_id": agent.id,
                    "result": result,
                })
            except Exception as e:
                logger.exception("Sub-agent task %s failed", task_id)
                await self._bus.publish("sub_agent_complete", {
                    "task_id": task_id,
                    "from_agent": from_agent,
                    "agent_id": agent.id,
                    "error": str(e),
                })
            finally:
                self._busy.discard(agent.id)

        asyncio.create_task(_run())
        return task_id

    async def get_pending_tasks(self) -> list[str]:
        """Return list of active task IDs (stub — real impl tracks tasks)."""
        return []
