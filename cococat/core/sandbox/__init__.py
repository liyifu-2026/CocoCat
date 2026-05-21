"""ExecutorProvider — unified execution provider for agents.

Usage:
  provider = ExecutorProvider(executor=InProcessExecutor())
  result = await provider.run_once("your prompt", agent_id="main", tools=...)
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from cococat.core.sandbox.sandbox import Sandbox  # noqa: F401 — re-export
from cococat.core.sandbox.local_executor import InProcessExecutor  # noqa: F401 — re-export
from cococat.core.sandbox.cubesandbox import CubeSandboxExecutor  # noqa: F401 — re-export

__all__ = ["Sandbox", "ExecutorProvider", "InProcessExecutor", "CubeSandboxExecutor"]

logger = logging.getLogger("cococat.sandbox")



import os as _os


def _resolve_agents_dir(scene_id: str | None = None, user_id: str | None = None) -> str:
    if scene_id and user_id:
        return f"scenes/{scene_id}/sessions/{user_id}"
    elif scene_id:
        return f"scenes/{scene_id}/sessions"
    return "sessions/default"


async def _make_and_run_agent(
    agent_id: str,
    prompt: str,
    tools: list[dict],
    resolve_llm: Callable[[str], Any],
    session_id: str | None = None,
    on_event: Callable | None = None,
    agents_dir: str | None = None,
    mode: str = "default",
    scene_id: str | None = None,
    user_id: str | None = None,
) -> str:
    """Create an Agent with WORKER role and run it, returning the result.

    Shared by InProcessExecutor and CubeSandboxExecutor to avoid
    duplicating Agent construction and agent.run() boilerplate.
    """
    from cococat.core.agent import Agent, AgentRole

    llm = resolve_llm(agent_id)
    if not llm:
        return f"[System] No LLM provider for agent '{agent_id}'"

    if agents_dir is None:
        agents_dir = _resolve_agents_dir(scene_id=scene_id, user_id=user_id)

    agent_dir = _os.path.join(agents_dir, agent_id)
    agent = Agent(
        id=agent_id,
        name=agent_id,
        role=AgentRole.WORKER,
        llm=llm,
        tools=tools,
        agent_dir=agent_dir if _os.path.isdir(agent_dir) else None,
        mode=mode,
    )

    try:
        result = await agent.run(
            prompt,
            context={"session_id": session_id} if session_id else None,
            on_text=(lambda t: on_event("text_delta", {"content": t})) if on_event else None,
            on_tool=(lambda n, s, d=None: on_event("stream_tool", {"name": n, "status": s, **(d or {})})) if on_event else None,
            on_reasoning=(lambda c: on_event("stream_reasoning", {"content": c})) if on_event else None,
        )
        return result
    except Exception as e:
        logger.exception("_make_and_run_agent failed for %s", agent_id)
        return f"Error: {e}"

class Executor:
    """Abstract executor backend."""

    async def create(self, template: str, permissions: dict) -> Sandbox:
        raise NotImplementedError

    async def run(self, sandbox: Sandbox, task: str,
                  agent_id: str = "coco", mode: str = "default",
                  scene_id: str | None = None, user_id: str | None = None,
                  on_event: Callable | None = None, tools: list | None = None,
                  session_id: str | None = None) -> str:
        raise NotImplementedError

    async def destroy(self, sandbox: Sandbox) -> None:
        raise NotImplementedError


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
