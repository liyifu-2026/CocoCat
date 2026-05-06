from .registry import PROVIDERS, find_by_name, find_by_model, find_by_env

__all__ = [
    "PROVIDERS", "find_by_name", "find_by_model", "find_by_env",
    "LLMProvider", "LLMResponse", "ToolCallRequest", "make_provider",
]


def __getattr__(name):
    import importlib

    _lazy = {
        "LLMProvider": "providers.base",
        "LLMResponse": "providers.base",
        "ToolCallRequest": "providers.base",
        "make_provider": "providers.factory",
    }
    if name in _lazy:
        return getattr(importlib.import_module(_lazy[name]), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
