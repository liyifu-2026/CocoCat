"""SandboxProvider — abstract execution environment for agents.

用法:
  provider = SandboxProvider(executor=LocalExecutor())
  result = await provider.run_once("your prompt", agent_id="main", tools=...)
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from cococat.core.sandbox.sandbox import Sandbox  # noqa: F401 — re-export
from cococat.core.sandbox.local_executor import LocalExecutor  # noqa: F401 — re-export
from cococat.core.sandbox.cubesandbox import CubeSandboxExecutor  # noqa: F401 — re-export

logger = logging.getLogger("cococat.sandbox")


class Executor:
    """Abstract executor backend."""

    async def create(self, template: str, permissions: dict) -> Sandbox:
        raise NotImplementedError

    async def run(self, sandbox: Sandbox, task: dict, on_event: Callable | None) -> str:
        raise NotImplementedError

    async def destroy(self, sandbox: Sandbox) -> None:
        raise NotImplementedError


class SandboxProvider:
    """Manages agent execution environments.

    create() / destroy() 管理沙箱生命周期。
    run() 在沙箱内执行一个 agent 任务。
    """

    def __init__(self, executor=None):
        from cococat.core.sandbox.local_executor import LocalExecutor
        self._executor = executor or LocalExecutor()
        self._sandboxes: dict[str, Sandbox] = {}

    async def create(self, template: str = "default", permissions: dict | None = None) -> str:
        sandbox = await self._executor.create(template, permissions or {})
        self._sandboxes[sandbox.id] = sandbox
        return sandbox.id

    async def run(
        self,
        sandbox_id: str,
        task: dict,
        on_event: Callable[[str, dict], Any] | None = None,
    ) -> str:
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            raise ValueError(f"Unknown sandbox: {sandbox_id}")
        return await self._executor.run(sandbox, task, on_event)

    async def destroy(self, sandbox_id: str) -> None:
        sandbox = self._sandboxes.pop(sandbox_id, None)
        if sandbox:
            await self._executor.destroy(sandbox)

    async def run_once(
        self,
        prompt: str,
        agent_id: str = "main",
        permissions: dict | None = None,
        tools: list[dict] | None = None,
        on_event: Callable[[str, dict], Any] | None = None,
    ) -> str:
        """Create a sandbox, run a task, destroy it. One-shot convenience."""
        sandbox_id = await self.create(permissions=permissions)
        try:
            return await self.run(sandbox_id, {
                "prompt": prompt,
                "agent_id": agent_id,
                "tools": tools or [],
            }, on_event)
        finally:
            await self.destroy(sandbox_id)
