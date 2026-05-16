"""Tool registry and factory — no domain knowledge."""

from cococat.core.types import ToolContext


def _make(name: str, description: str, params: dict, execute_fn, **extra) -> "Tool":
    from cococat.core.tools import Tool
    return Tool(name=name, description=description, parameters=params, execute=execute_fn, **extra)


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
