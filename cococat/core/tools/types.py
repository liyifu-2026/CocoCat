"""Tool types — Tool dataclass, ToolRegistry, and context helpers."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

from cococat.core.types import ToolContext, SandboxEnv, MemoryEnv, WebEnv


@dataclass
class Tool:
    """A tool with name, description, parameters, and execute function.

    Supports both dict-style access (t["name"]) and attribute access (t.name)
    for backward compatibility.
    """
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable
    requires_sandbox: bool = False
    sandbox_operation: str = ""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def keys(self):
        return ["name", "description", "parameters", "execute", "requires_sandbox", "sandbox_operation"]

    def __iter__(self):
        return iter(self.keys())


class ToolRegistry:
    """Registry for executing tools."""

    def __init__(self, tools: list | dict):
        if isinstance(tools, dict):
            self._tools = tools
        else:
            self._tools = {t["name"]: t for t in tools}

    async def execute(self, name: str, params: dict, context: ToolContext | None = None) -> str:
        """Execute a tool by name. Returns string result."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        context = context or {}
        result = tool["execute"](params, context)
        if callable(getattr(result, "__await__", None)):
            result = await result
        return str(result)

    def filter(self, allowed_names: set[str]) -> list:
        """Return tools whose names are in the allowed set."""
        return [t for name, t in self._tools.items() if name in allowed_names]

    def list_tools(self) -> list:
        return list(self._tools.values())


def _make(name: str, description: str, params: dict, execute_fn, **extra) -> Tool:
    return Tool(name=name, description=description, parameters=params, execute=execute_fn, **extra)


def _ensure_tool_context(ctx):
    """Convert dict to ToolContext if needed (test/direct-call compat)."""
    if isinstance(ctx, ToolContext):
        return ctx
    sandbox = SandboxEnv(run=ctx.get("sandbox_run"))
    mem = MemoryEnv(
        memory_path=ctx.get("memory_path", ""),
        agent_dir=ctx.get("agent_dir", ""),
        exp_path=ctx.get("exp_path", "memory/experiences"),
    )
    web = WebEnv(tavily_api_key=ctx.get("tavily_api_key"))
    fields = {"agent_id", "agent_dir", "scene_id", "user_id", "bound_scene", "role", "session_id",
              "db", "sub_agent_executor", "cron_path", "_llm"}
    direct = {k: v for k, v in ctx.items() if k in fields}
    return ToolContext(sandbox=sandbox, memory=mem, web=web, **direct)


def _with_env(ctx: ToolContext | dict, **overrides) -> ToolContext:
    """Return a new ToolContext with overridden environment fields."""
    return _ensure_tool_context(ctx).copy_with(**overrides)
