"""Provider package."""
from cococat.providers.base import BaseProvider, LLMResponse, ToolCallRequest
from cococat.providers.openai_compat import OpenAICompatProvider
from cococat.providers.anthropic import AnthropicProvider
from cococat.providers.credentials import CredentialManager
from cococat.providers.registry import ProviderRegistry, ProviderSpec, create_builtin_registry, find_by_name, find_by_model, find_by_env

__all__ = [
    "BaseProvider",
    "LLMResponse",
    "ToolCallRequest",
    "OpenAICompatProvider",
    "AnthropicProvider",
    "CredentialManager",
    "ProviderRegistry",
    "ProviderSpec",
    "create_builtin_registry",
    "find_by_name",
    "find_by_model",
    "find_by_env",
]
