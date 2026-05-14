"""Tool registry and factory — no domain knowledge."""


def _make(name: str, description: str, params: dict, execute_fn) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": params,
        "execute": execute_fn,
    }


class ToolRegistry:
    """Registry for executing tools."""

    def __init__(self, tools: list[dict]):
        self._tools = {t["name"]: t for t in tools}

    async def execute(self, name: str, params: dict, context: dict | None = None) -> str:
        """Execute a tool by name. Returns string result."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        context = context or {}
        result = tool["execute"](params, context)
        if callable(getattr(result, "__await__", None)):
            result = await result
        return str(result)

    def filter(self, allowed_names: set[str]) -> list[dict]:
        """Return tools whose names are in the allowed set."""
        return [t for name, t in self._tools.items() if name in allowed_names]

    def list_tools(self) -> list[dict]:
        return list(self._tools.values())
