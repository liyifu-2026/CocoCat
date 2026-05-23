"""ExecutorProvider — unified execution provider for agents.

Usage:
  provider = ExecutorProvider(executor=InProcessExecutor())
  result = await provider.run_once("your prompt", agent_id="main", tools=...)
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from cococat.core.sandbox.base import Executor  # noqa: F401 — re-export
from cococat.core.sandbox.sandbox import Sandbox  # noqa: F401 — re-export
from cococat.core.sandbox.local_executor import InProcessExecutor  # noqa: F401 — re-export
from cococat.core.sandbox.cubesandbox import CubeSandboxExecutor  # noqa: F401 — re-export

__all__ = ["Sandbox", "ExecutorProvider", "Executor", "InProcessExecutor", "CubeSandboxExecutor"]

logger = logging.getLogger("cococat.sandbox")


class ExecutorProvider:
    """Unified execution provider — manages agent execution environments.

    create() / destroy() manage execution lifecycle.
    run() executes an agent task within an execution environment.
    """

    def __init__(self, executor=None):
        self._executor = executor or InProcessExecutor()
        self._sandboxes: dict[str, Sandbox] = {}

    async def create(self, template: str = "default", permissions: dict | None = None) -> str:
        sandbox = await self._executor.create(template, permissions or {})
        self._sandboxes[sandbox.id] = sandbox
        return sandbox.id

    async def run(
        self,
        sandbox_id: str,
        task: str,
        agent_id: str = "coco",
        mode: str = "default",
        scene_id: str | None = None,
        user_id: str | None = None,
        on_event: Callable[[str, dict], Any] | None = None,
        tools: list[dict] | None = None,
        session_id: str | None = None,
    ) -> str:
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            raise ValueError(f"Unknown sandbox: {sandbox_id}")
        return await self._executor.run(
            sandbox, task, agent_id=agent_id, mode=mode,
            scene_id=scene_id, user_id=user_id,
            on_event=on_event, tools=tools, session_id=session_id,
        )

    async def destroy(self, sandbox_id: str) -> None:
        sandbox = self._sandboxes.pop(sandbox_id, None)
        if sandbox:
            await self._executor.destroy(sandbox)

    async def run_once(
        self,
        prompt: str,
        agent_id: str = "coco",
        mode: str = "default",
        scene_id: str | None = None,
        user_id: str | None = None,
        permissions: dict | None = None,
        tools: list[dict] | None = None,
        on_event: Callable[[str, dict], Any] | None = None,
        session_id: str | None = None,
    ) -> str:
        """Create a sandbox, run a task, destroy it. One-shot convenience."""
        sandbox_id = await self.create(permissions=permissions)
        try:
            return await self.run(
                sandbox_id, task=prompt, agent_id=agent_id, mode=mode,
                scene_id=scene_id, user_id=user_id,
                on_event=on_event, tools=tools, session_id=session_id,
            )
        finally:
            await self.destroy(sandbox_id)
