from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    keywords: tuple[str, ...]
    env_key: str
    display_name: str = ""
    backend: str = "openai_compat"
    default_api_base: str = ""
    supports_streaming: bool = False


PROVIDERS: list[ProviderSpec] = [
    ProviderSpec("deepseek",    ("deepseek",),           "DEEPSEEK_API_KEY",    "DeepSeek",    "openai_compat", "https://api.deepseek.com",                  supports_streaming=True),
    ProviderSpec("openai",      ("openai", "gpt"),       "OPENAI_API_KEY",      "OpenAI",      "openai_compat", "https://api.openai.com/v1",                   supports_streaming=True),
    ProviderSpec("anthropic",   ("anthropic", "claude"), "ANTHROPIC_API_KEY",   "Anthropic",   "anthropic",     "https://api.anthropic.com",                   supports_streaming=True),
    ProviderSpec("gemini",      ("gemini", "gemma"),     "GEMINI_API_KEY",      "Gemini",      "openai_compat", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    ProviderSpec("siliconflow", ("siliconflow",),        "SILICONFLOW_API_KEY", "SiliconFlow", "openai_compat", "https://api.siliconflow.cn/v1",              supports_streaming=True),
    ProviderSpec("dashscope",   ("qwen", "dashscope"),   "DASHSCOPE_API_KEY",   "DashScope",   "openai_compat", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    ProviderSpec("zhipu",       ("zhipu", "glm"),        "ZHIPUAI_API_KEY",     "Zhipu",       "openai_compat", "https://open.bigmodel.cn/api/paas/v4"),
    ProviderSpec("custom", ("custom",), "", "Custom", "openai_compat", ""),
]


def find_by_name(name: str) -> ProviderSpec | None:
    for spec in PROVIDERS:
        if spec.name == name:
            return spec
    return None


def find_by_model(model: str) -> ProviderSpec | None:
    """Match model name against provider keywords (first keyword match wins)."""
    lower = model.lower()
    for spec in PROVIDERS:
        for kw in spec.keywords:
            if kw in lower:
                return spec
    return None


def find_by_env() -> ProviderSpec | None:
    """Return first provider whose env_key is set in os.environ."""
    for spec in PROVIDERS:
        if spec.env_key and os.environ.get(spec.env_key):
            return spec
    return None
