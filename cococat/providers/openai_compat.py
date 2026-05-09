"""OpenAI-compatible provider (covers OpenAI, DeepSeek, SiliconFlow, etc.)."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import httpx

from cococat.providers.base import BaseProvider

logger = logging.getLogger("cococat.providers.openai_compat")


class OpenAICompatProvider(BaseProvider):
    """Provider for any OpenAI-compatible API (OpenAI, DeepSeek, Groq, Ollama, etc.)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 120.0,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def _build_request(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> dict:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            body["tools"] = [
                {"type": "function", "function": t} for t in tools
            ]
        return body

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> str:
        """Send a non-streaming chat request."""
        body = self._build_request(messages, tools, stream=False)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        result: dict = {"content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            result["tool_calls"] = [
                {
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                }
                for tc in msg["tool_calls"]
            ]
        return result

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[dict]:
        """Send a streaming chat request. Yields {'type': 'delta'|'done', 'content': ...}."""
        body = self._build_request(messages, tools, stream=True)
        body["stream_options"] = {"include_usage": True}

        accumulated = []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                accumulated.append(content)
                                yield {"type": "delta", "content": content}
                        except json.JSONDecodeError:
                            continue

        yield {"type": "done", "content": "".join(accumulated)}
