"""Executor abstract base — defines the execution environment interface."""
from __future__ import annotations

from typing import Callable

from cococat.core.sandbox.sandbox import Sandbox


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
