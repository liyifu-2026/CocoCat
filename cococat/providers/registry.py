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
        "base_url": "https://api.deepseek.com",
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
    {
        "name": "gemini",
        "display_name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "env_key": "GEMINI_API_KEY",
        "keywords": ["gemini"],
    },
    {
        "name": "groq",
        "display_name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "keywords": ["groq"],
    },
    {
        "name": "mistral",
        "display_name": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "env_key": "MISTRAL_API_KEY",
        "keywords": ["mistral"],
    },
    {
        "name": "moonshot",
        "display_name": "Moonshot (Kimi)",
        "base_url": "https://api.moonshot.cn/v1",
        "env_key": "MOONSHOT_API_KEY",
        "keywords": ["moonshot", "kimi"],
    },
    {
        "name": "volcengine",
        "display_name": "Volcengine (Doubao)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "env_key": "VOLCENGINE_API_KEY",
        "keywords": ["volcengine", "doubao"],
    },
    {
        "name": "openrouter",
        "display_name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "keywords": ["openrouter"],
    },
    {
        "name": "minimax",
        "display_name": "MiniMax",
        "base_url": "https://api.minimax.chat/v1",
        "env_key": "MINIMAX_API_KEY",
        "keywords": ["minimax"],
    },
]


def create_builtin_registry() -> ProviderRegistry:
    """Create a registry with all built-in providers."""
    reg = ProviderRegistry()
    for spec in BUILTIN_PROVIDERS:
        reg.register(spec["name"], spec)
    return reg
