"""InProcessExecutor — in-process agent executor (development mode, no hardware isolation)."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable

from cococat.core.sandbox.sandbox import Sandbox

logger = logging.getLogger("cococat.sandbox.local")


class InProcessExecutor:
    """In-process agent executor — runs Agent code in same Python process.

    Creates temporary Agent instances on each run() call.
    Accepts optional sandbox_run callable to route bash tool execution to CubeSandbox MicroVM.
    """

    def __init__(
        self,
        max_workers: int = 4,
        get_llm: Callable[[str], Any] | None = None,
        sandbox_run: Callable[[str], Any] | None = None,
        tavily_api_key: str | None = None,
    ):
        self._max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._counter = 0
        self._get_llm_fn = get_llm
        self._sandbox_run = sandbox_run
        self._tavily_api_key = tavily_api_key

    async def create(self, template: str, permissions: dict) -> Sandbox:
        self._counter += 1
        sandbox_id = f"local-{self._counter}"
        logger.info("InProcessExecutor: created %s", sandbox_id)
        return Sandbox(id=sandbox_id, template=template, permissions=permissions)

    async def run(self, sandbox: Sandbox, task: str,
                  agent_id: str = "coco", mode: str = "default",
                  scene_id: str | None = None, user_id: str | None = None,
                  on_event: Callable | None = None, tools: list | None = None,
                  session_id: str | None = None) -> str:
        async with self._semaphore:
            return await self._do_run(sandbox, task,
                                      agent_id=agent_id, mode=mode,
                                      scene_id=scene_id, user_id=user_id,
                                      on_event=on_event, tools=tools,
                                      session_id=session_id)

    async def _do_run(self, sandbox: Sandbox, task: str, agent_id: str,
                      mode: str, scene_id: str | None, user_id: str | None,
                      on_event: Callable | None, tools: list | None,
                      session_id: str | None) -> str:
        logger.info("InProcessExecutor: running task in %s", sandbox.id)
        from cococat.core.sandbox import _make_and_run_agent

        if tools is None:
            tools = self._resolve_tools_for_mode(mode)

        return await _make_and_run_agent(
            agent_id=agent_id,
            prompt=task,
            tools=tools,
            resolve_llm=self._resolve_llm,
            session_id=session_id,
            on_event=on_event,
            agents_dir=os.environ.get("COCOCAT_AGENTS_DIR"),
            mode=mode,
            scene_id=scene_id,
            user_id=user_id,
        )

    def _resolve_tools_for_mode(self, mode: str) -> list:
        from cococat.core.tools import ToolCatalog
        return ToolCatalog(sandbox_run=self._sandbox_run, tavily_api_key=self._tavily_api_key).worker()

    async def destroy(self, sandbox: Sandbox) -> None:
        logger.info("InProcessExecutor: destroyed %s", sandbox.id)

    def _resolve_llm(self, agent_id: str):
        """Resolve LLM provider via injected callable."""
        return self._get_llm_fn(agent_id) if self._get_llm_fn else None
