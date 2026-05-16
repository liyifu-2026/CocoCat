"""Shared types for tool context, messages, and LLM interfaces."""
from __future__ import annotations

from typing import Callable, Awaitable, TypedDict


class ToolContext(TypedDict, total=False):
    """Context dict passed through the tool execution pipeline.

    Populated by Agent.run() and enriched by tool factory lambdas.
    """
    agent_id: str
    agent_dir: str
    bound_scene: str | None
    role: str
    session_id: str | None
    memory_path: str
    exp_path: str
    db: object  # Database — avoids circular import
    dag_store: object  # DagStore — avoids circular import
    dag_dir: str
    tasks_path: str
    cancel_dir: str
    cron_path: str
    todos_path: str
    sub_agent_executor: Callable[[str, str], Awaitable[str]] | None
    sandbox_run: Callable[[str], Awaitable[str]] | None
    tavily_api_key: str | None
