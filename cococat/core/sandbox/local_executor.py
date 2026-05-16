"""LocalExecutor — runs Agent in-process (development mode, no hardware isolation)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from cococat.core.sandbox.sandbox import Sandbox

logger = logging.getLogger("cococat.sandbox.local")


class LocalExecutor:
    """Local in-process executor — runs Agent code in same Python process.

    Creates temporary Agent instances on each run() call.
    Accepts optional sandbox_run callable to route bash tool execution to CubeSandbox MicroVM.
    """

    def __init__(
        self,
        max_workers: int = 4,
        get_llm: Callable[[str], Any] | None = None,
        sandbox_run: Callable[[str], Any] | None = None,
    ):
        self._max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._counter = 0
        self._get_llm_fn = get_llm
        self._sandbox_run = sandbox_run

    async def create(self, template: str, permissions: dict) -> Sandbox:
        self._counter += 1
        sandbox_id = f"local-{self._counter}"
        logger.info("LocalExecutor: created %s", sandbox_id)
        return Sandbox(id=sandbox_id, template=template, permissions=permissions)

    async def run(self, sandbox: Sandbox, task: dict, on_event: Callable | None) -> str:
        async with self._semaphore:
            return await self._do_run(sandbox, task, on_event)

    async def _do_run(self, sandbox: Sandbox, task: dict, on_event: Callable | None) -> str:
        logger.info("LocalExecutor: running task in %s", sandbox.id)
        from cococat.core.tools import create_core_tools
        from cococat.core.sandbox import _make_and_run_agent

        prompt = task.get("prompt", "")
        agent_id = task.get("agent_id", sandbox.id)
        session_id = task.get("session_id")

        provided_tools = task.get("tools")
        if provided_tools:
            tools = provided_tools
        else:
            tools = create_core_tools(sandbox_run=self._sandbox_run)

        return await _make_and_run_agent(
            agent_id=agent_id,
            prompt=prompt,
            tools=tools,
            resolve_llm=self._resolve_llm,
            session_id=session_id,
            on_event=on_event,
        )

    async def destroy(self, sandbox: Sandbox) -> None:
        logger.info("LocalExecutor: destroyed %s", sandbox.id)

    def _resolve_llm(self, agent_id: str):
        """Resolve LLM provider via injected callable."""
        return self._get_llm_fn(agent_id) if self._get_llm_fn else None
