"""Anthropic provider — Messages API (different format from OpenAI)."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import httpx

from cococat.providers.base import BaseProvider

logger = logging.getLogger("cococat.providers.anthropic")


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude (Messages API)."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str = "https://api.anthropic.com",
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._max_tokens = max_tokens
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """Convert OpenAI-format messages to Anthropic format.

        Returns (system_prompt, anthropic_messages).
        """
        system = ""
        converted = []

        for msg in messages:
            role = msg["role"]

            if role == "system":
                system = msg.get("content", "")
                continue

            if role == "user":
                converted.append({
                    "role": "user",
                    "content": [{"type": "text", "text": msg.get("content", "")}],
                })

            elif role == "assistant":
                blocks = []
                if msg.get("content"):
                    blocks.append({"type": "text", "text": msg["content"]})
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        args = tc["function"].get("arguments", "{}")
                        if isinstance(args, str):
                            args = json.loads(args)
                        blocks.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": args,
                        })
                converted.append({"role": "assistant", "content": blocks})

            elif role == "tool":
                converted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": msg.get("content", ""),
                    }],
                })

        return system, converted

    def _build_request(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> dict:
        body: dict[str, Any] = {
            "model": self._model,
            "system": system,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "stream": stream,
        }
        if tools:
            body["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": {
                        "type": "object",
                        "properties": t.get("parameters", {}),
                    },
                }
                for t in tools
            ]
        return body

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> dict:
        system, converted = self._convert_messages(messages)
        body = self._build_request(converted, system=system, tools=tools)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        result: dict = {"content": ""}

        # Extract text and tool_use from content blocks
        for block in data.get("content", []):
            if block["type"] == "text":
                result["content"] += block["text"]
            elif block["type"] == "tool_use":
                if "tool_calls" not in result:
                    result["tool_calls"] = []
                result["tool_calls"].append({
                    "id": block["id"],
                    "name": block["name"],
                    "arguments": json.dumps(block["input"]),
                })

        return result

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[dict]:
        """Streaming not implemented for Anthropic yet — falls back to non-streaming."""
        result = await self.chat(messages, tools, **kwargs)
        yield {"type": "delta", "content": result.get("content", "")}
        yield {"type": "done", "content": result.get("content", "")}
