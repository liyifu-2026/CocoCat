"""Tool types — Tool dataclass, ToolRegistry, and context helpers."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

from cococat.core.types import ToolContext


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

    def __init__(self, tools: list):
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


def _ensure_tool_context(ctx: dict | ToolContext | None) -> ToolContext:
    """Convert a dict or None to a ToolContext safely."""
    return ToolContext.from_dict(ctx)


def _merge_ctx(ctx: dict | ToolContext | None, **overrides) -> ToolContext:
    """Merge overrides into ctx, returning a new ToolContext."""
    base = _ensure_tool_context(ctx)
    for key, val in overrides.items():
        setattr(base, key, val)
    return base
