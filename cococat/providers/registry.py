"""Provider registry — lookup providers by name or model keyword."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cococat.providers.registry")


class ProviderRegistry:
    """Flat registry of LLM providers.

    Auto-detection priority chain:
    1. Model-name keyword match (e.g., "deepseek-chat" matches keyword "deepseek")
    2. Environment variable detection (os.environ.get(spec.env_key))
    3. First provider with any API key configured
    """

    def __init__(self):
        self._providers: dict[str, dict] = {}

    def register(self, name: str, spec: dict) -> None:
        """Register a provider spec."""
        self._providers[name] = spec

    def find_by_name(self, name: str) -> dict | None:
        """Find provider by exact name."""
        return self._providers.get(name)

    def find_by_model(self, model: str) -> dict | None:
        """Find provider by model keyword match."""
        model_lower = model.lower()
        for spec in self._providers.values():
            for kw in spec.get("keywords", []):
                if kw in model_lower:
                    return spec
        return None

    def list_all(self) -> list[dict]:
        """List all registered providers."""
        return list(self._providers.values())


# Registry of built-in providers
BUILTIN_PROVIDERS = [
    {
        "name": "openai",
        "display_name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "keywords": ["openai", "gpt"],
    },
    {
        "name": "deepseek",
        "display_name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "keywords": ["deepseek"],
    },
    {
        "name": "anthropic",
        "display_name": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "env_key": "ANTHROPIC_API_KEY",
        "keywords": ["claude", "anthropic"],
        "backend": "anthropic",
    },
    {
        "name": "siliconflow",
        "display_name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "env_key": "SILICONFLOW_API_KEY",
        "keywords": ["siliconflow"],
    },
    {
        "name": "zhipu",
        "display_name": "ZhipuAI (GLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "env_key": "ZHIPU_API_KEY",
        "keywords": ["glm", "zhipu"],
    },
    {
        "name": "dashscope",
        "display_name": "DashScope (Qwen)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "env_key": "DASHSCOPE_API_KEY",
        "keywords": ["qwen", "dashscope"],
    },
    {
        "name": "ollama",
        "display_name": "Ollama (local)",
        "base_url": "http://localhost:11434/v1",
        "env_key": "",
        "keywords": ["ollama", "llama", "mistral", "codellama"],
    },
]


def create_builtin_registry() -> ProviderRegistry:
    """Create a registry with all built-in providers."""
    reg = ProviderRegistry()
    for spec in BUILTIN_PROVIDERS:
        reg.register(spec["name"], spec)
    return reg
