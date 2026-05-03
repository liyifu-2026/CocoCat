"""Tool registry — Tool base class and PluginTool for plugin system."""
from tools import Tool


class PluginTool(Tool):
    """Base class for plugin-provided tools."""

    def execute(self, **kwargs) -> str:
        if hasattr(self, "_handler"):
            result = self._handler(**kwargs)
            return str(result) if result is not None else ""
        raise NotImplementedError
