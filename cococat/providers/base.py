"""Base provider interface."""
from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """Abstract LLM provider. All providers implement this interface."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> dict:
        """Send a chat request. Returns {'content': str, 'tool_calls': [...]|None}."""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ):
        """Send a streaming chat request. Yields delta events."""
        ...
