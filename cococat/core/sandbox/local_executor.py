"""LocalExecutor — runs Agent in-process (development mode, no hardware isolation)."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable

from cococat.core.sandbox.sandbox import Sandbox

logger = logging.getLogger("cococat.sandbox.local")


class LocalExecutor:
    """Local subprocess executor — runs Agent code in a child process.

    Creates temporary Agent instances on each run() call (fire-and-forget).
    Accepts a get_llm callable via constructor for dependency injection.
    """

    def __init__(
        self,
        max_workers: int = 4,
        get_llm: Callable[[str], Any] | None = None,
    ):
        self._max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._counter = 0
        self._get_llm_fn = get_llm

    async def create(self, template: str, permissions: dict) -> Sandbox:
        self._counter += 1
        sandbox_id = f"local-{self._counter}"
        logger.info("LocalExecutor: created %s", sandbox_id)
        return Sandbox(id=sandbox_id, template=template, permissions=permissions)

    async def run(self, sandbox: Sandbox, task: dict, on_event: Callable | None) -> str:
        logger.info("LocalExecutor: running task in %s", sandbox.id)
        from cococat.core.agent import Agent, AgentRole
        from cococat.core.tools import create_core_tools

        prompt = task.get("prompt", "")
        agent_id = task.get("agent_id", sandbox.id)

        provided_tools = task.get("tools")
        if provided_tools:
            tools = provided_tools
        else:
            tools = create_core_tools()

        llm = self._resolve_llm(agent_id)
        if not llm:
            return f"[System] No LLM provider for agent '{agent_id}'"

        agent = Agent(
            id=agent_id,
            name=agent_id,
            role=AgentRole.SUB,
            llm=llm,
            tools=tools,
            agent_dir=f"agents/{agent_id}" if os.path.isdir(f"agents/{agent_id}") else None,
        )

        try:
            result = await agent.run(
                prompt,
                on_text=lambda t: on_event("text_delta", {"content": t}) if on_event else None,
                on_tool=lambda n, s: on_event("stream_tool", {"name": n, "status": s}) if on_event else None,
                on_reasoning=lambda c: on_event("stream_reasoning", {"content": c}) if on_event else None,
            )
            return result
        except Exception as e:
            logger.error("LocalExecutor: task failed: %s", e)
            return f"Error: {e}"

    async def destroy(self, sandbox: Sandbox) -> None:
        logger.info("LocalExecutor: destroyed %s", sandbox.id)

    def _resolve_llm(self, agent_id: str):
        """Resolve LLM provider via injected callable or default DB lookup."""
        if self._get_llm_fn:
            return self._get_llm_fn(agent_id)

        from cococat.providers.factory import ProviderFactory
        from cococat.providers.credentials import CredentialManager

        factory = ProviderFactory(credential_manager=CredentialManager("config/auth.json"))
        model = "deepseek-v4-flash"

        rows = []
        try:
            import sqlite3
            db_path = os.environ.get("COCOCAT_DB", "cococat.db")
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT model FROM agents WHERE id = ?", (agent_id,)
            ).fetchall()
            conn.close()
        except Exception:
            pass

        if rows:
            model = rows[0][0]

        return factory.create_sync(model)
