"""Sub-agent executor — async fire-and-forget task delegation."""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.core.event_bus import EventBus
    from cococat.core.agent_pool import AgentPool
    from cococat.core.sandbox import ExecutorProvider

logger = logging.getLogger("cococat.sub_agent")


class SubAgentExecutor:
    """Manages async sub-agent task dispatch and result delivery.

    Two modes:
    1. AgentPool mode: finds free sub agents from pool, runs synchronously
    2. ExecutorProvider mode: create-per-task via ExecutorProvider

    Fire-and-forget pattern for tools; synchronous for DAG worker.
    Returns the task result string (not task_id) for caller convenience.
    """

    def __init__(
        self,
        bus: EventBus,
        pool: AgentPool | None = None,
        sandbox_provider: ExecutorProvider | None = None,
    ):
        self._bus = bus
        self._pool = pool
        self._sandbox = sandbox_provider
        self._busy: set[str] = set()

    async def dispatch(self, task: str, from_agent: str = "main", session_id: str | None = None) -> str | None:
        """Dispatch a task. Returns the result string. Uses sandbox_provider if available, otherwise pool."""
        if self._sandbox:
            return await self._dispatch_via_sandbox(task, from_agent, session_id)

        if self._pool:
            return await self._dispatch_via_pool(task, from_agent)

        logger.warning("No executor configured for dispatch from %s", from_agent)
        return None

    async def _dispatch_via_pool(self, task: str, from_agent: str) -> str | None:
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

        try:
            result = await agent.run(task)
            await self._bus.publish("sub_agent_complete", {
                "task_id": task_id,
                "from_agent": from_agent,
                "agent_id": agent.id,
                "result": result,
            })
            return result
        except Exception as e:
            logger.exception("Sub-agent task %s failed", task_id)
            await self._bus.publish("sub_agent_complete", {
                "task_id": task_id,
                "from_agent": from_agent,
                "agent_id": agent.id,
                "error": str(e),
            })
            return f"Error: {e}"
        finally:
            self._busy.discard(agent.id)

    async def _dispatch_via_sandbox(self, task: str, from_agent: str, session_id: str | None = None) -> str | None:
        task_id = uuid.uuid4().hex[:12]

        try:
            result = await self._sandbox.run_once(
                prompt=task,
                agent_id=f"sub-{task_id}",
                session_id=session_id,
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

    async def get_pending_tasks(self) -> list[str]:
        """Return list of active task IDs (stub — real impl tracks tasks)."""
        return []
