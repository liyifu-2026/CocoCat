"""Provider registry — lookup providers by name or model keyword."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger("cococat.providers.registry")


@dataclass(frozen=True)
class ProviderSpec:
    """Immutable spec for a single LLM provider."""
    name: str
    keywords: tuple[str, ...]
    env_key: str
    display_name: str = ""
    backend: str = "openai_compat"
    default_api_base: str = ""
    supports_streaming: bool = False


BUILTIN_PROVIDERS: list[ProviderSpec] = [
    # ── Primary Providers ──
    ProviderSpec("openai",      ("openai", "gpt"),       "OPENAI_API_KEY",      "OpenAI",       "openai_compat", "https://api.openai.com/v1",               supports_streaming=True),
    ProviderSpec("anthropic",   ("anthropic", "claude"), "ANTHROPIC_API_KEY",   "Anthropic",    "anthropic",     "https://api.anthropic.com",               supports_streaming=True),
    ProviderSpec("deepseek",    ("deepseek",),           "DEEPSEEK_API_KEY",    "DeepSeek",     "openai_compat", "https://api.deepseek.com",               supports_streaming=True),
    ProviderSpec("gemini",      ("gemini", "gemma"),     "GEMINI_API_KEY",      "Google Gemini", "openai_compat", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    ProviderSpec("siliconflow", ("siliconflow",),        "SILICONFLOW_API_KEY", "SiliconFlow",  "openai_compat", "https://api.siliconflow.cn/v1",           supports_streaming=True),
    ProviderSpec("dashscope",   ("qwen", "dashscope"),   "DASHSCOPE_API_KEY",   "DashScope",    "openai_compat", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    ProviderSpec("zhipu",       ("zhipu", "glm"),        "ZHIPUAI_API_KEY",     "Zhipu AI",     "openai_compat", "https://open.bigmodel.cn/api/paas/v4"),
    # ── Global / Proxy Providers ──
    ProviderSpec("openrouter",  ("openrouter",),         "OPENROUTER_API_KEY",  "OpenRouter",   "openai_compat", "https://openrouter.ai/api/v1",           supports_streaming=True),
    ProviderSpec("groq",        ("groq",),               "GROQ_API_KEY",        "Groq",         "openai_compat", "https://api.groq.com/openai/v1",          supports_streaming=True),
    ProviderSpec("together",    ("together",),           "TOGETHER_API_KEY",    "Together AI",  "openai_compat", "https://api.together.xyz/v1",            supports_streaming=True),
    ProviderSpec("fireworks",   ("fireworks",),          "FIREWORKS_API_KEY",   "Fireworks AI", "openai_compat", "https://api.fireworks.ai/inference/v1",   supports_streaming=True),
    ProviderSpec("deepinfra",   ("deepinfra", "deep-infra"), "DEEPINFRA_API_KEY", "Deep Infra",  "openai_compat", "https://api.deepinfra.com/v1/openai",     supports_streaming=True),
    ProviderSpec("cerebras",    ("cerebras",),           "CEREBRAS_API_KEY",    "Cerebras",     "openai_compat", "https://api.cerebras.ai/v1",              supports_streaming=True),
    ProviderSpec("xai",         ("xai", "grok"),         "XAI_API_KEY",         "xAI",          "openai_compat", "https://api.x.ai/v1",                     supports_streaming=True),
    # ── Chinese Providers ──
    ProviderSpec("moonshot",    ("moonshot", "kimi"),    "MOONSHOT_API_KEY",    "Moonshot AI",  "openai_compat", "https://api.moonshot.cn/v1",              supports_streaming=True),
    ProviderSpec("minimax",     ("minimax",),            "MINIMAX_API_KEY",     "MiniMax",      "openai_compat", "https://api.minimax.chat/v1",             supports_streaming=True),
    ProviderSpec("doubao",      ("doubao", "volcengine", "bytedance"), "DOUBAO_API_KEY", "Doubao", "openai_compat", "https://ark.cn-beijing.volces.com/api/v3", supports_streaming=True),
    ProviderSpec("baichuan",    ("baichuan",),           "BAICHUAN_API_KEY",    "Baichuan",     "openai_compat", "https://api.baichuan-ai.com/v1",          supports_streaming=True),
    # ── Cloud Providers ──
    ProviderSpec("azure",       ("azure",),              "AZURE_OPENAI_API_KEY","Azure OpenAI", "openai_compat", "https://RESOURCE_NAME.openai.azure.com", supports_streaming=True),
    ProviderSpec("aws-bedrock", ("bedrock",),            "AWS_ACCESS_KEY_ID",   "Amazon Bedrock","openai_compat", "https://bedrock-runtime.REGION.amazonaws.com"),
    # ── Local / Self-Hosted ──
    ProviderSpec("ollama",      ("ollama",),             "OLLAMA_HOST",         "Ollama",       "openai_compat", "http://localhost:11434/v1",              supports_streaming=True),
    ProviderSpec("lmstudio",    ("lmstudio", "lm-studio"),"LMSTUDIO_API_KEY",   "LM Studio",    "openai_compat", "http://localhost:1234/v1",               supports_streaming=True),
    ProviderSpec("llamacpp",    ("llamacpp", "llama.cpp"),"LLAMACPP_API_KEY",  "llama.cpp",    "openai_compat", "http://localhost:8080/v1",               supports_streaming=True),
    # ── Other Providers ──
    ProviderSpec("huggingface", ("huggingface", "hf"),   "HUGGINGFACE_API_KEY", "Hugging Face", "openai_compat", "https://api-inference.huggingface.co/v1", supports_streaming=True),
    ProviderSpec("mistral",     ("mistral",),            "MISTRAL_API_KEY",     "Mistral AI",   "openai_compat", "https://api.mistral.ai/v1",              supports_streaming=True),
    ProviderSpec("cohere",      ("cohere",),             "COHERE_API_KEY",      "Cohere",       "openai_compat", "https://api.cohere.com/v1",               supports_streaming=True),
    ProviderSpec("replicate",   ("replicate",),          "REPLICATE_API_KEY",   "Replicate",    "openai_compat", "https://api.replicate.com/v1",           supports_streaming=True),
    ProviderSpec("perplexity",  ("perplexity",),         "PERPLEXITY_API_KEY",  "Perplexity",   "openai_compat", "https://api.perplexity.ai",               supports_streaming=True),
    # ── Custom / Generic ──
    ProviderSpec("custom",      ("custom",),             "",                    "Custom",       "openai_compat", ""),
]


class ProviderRegistry:
    """Flat registry of LLM providers.

    Stores ProviderSpec objects. Supports lookup by name, model keyword,
    and environment variable presence.
    """

    def __init__(self):
        self._providers: dict[str, ProviderSpec] = {}

    def register(self, spec: ProviderSpec) -> None:
        self._providers[spec.name] = spec

    def find_by_name(self, name: str) -> ProviderSpec | None:
        return self._providers.get(name)

    def find_by_model(self, model: str) -> ProviderSpec | None:
        model_lower = model.lower()
        for spec in self._providers.values():
            for kw in spec.keywords:
                if kw in model_lower:
                    return spec
        return None

    def list_all(self) -> list[ProviderSpec]:
        return list(self._providers.values())


# Module-level builtin registry (lazily created)
_builtin_registry: ProviderRegistry | None = None


def _get_builtin_registry() -> ProviderRegistry:
    global _builtin_registry
    if _builtin_registry is None:
        _builtin_registry = create_builtin_registry()
    return _builtin_registry


def create_builtin_registry() -> ProviderRegistry:
    reg = ProviderRegistry()
    for spec in BUILTIN_PROVIDERS:
        reg.register(spec)
    return reg


def find_by_name(name: str) -> ProviderSpec | None:
    return _get_builtin_registry().find_by_name(name)


def find_by_model(model: str) -> ProviderSpec | None:
    return _get_builtin_registry().find_by_model(model)


def find_by_env() -> ProviderSpec | None:
    for spec in BUILTIN_PROVIDERS:
        if spec.env_key and os.environ.get(spec.env_key):
            return spec
    return None
