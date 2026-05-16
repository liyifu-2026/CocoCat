"""Anthropic provider — Messages API (different format from OpenAI)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

import httpx

from cococat.providers.base import BaseProvider, LLMResponse, ToolCallRequest
from cococat.providers.usage import TokenUsage, log_usage

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

    def _log_usage(self, data: dict, start_time: float) -> None:
        """Extract usage from Anthropic response and log it."""
        usage = data.get("usage", {})
        if not usage:
            return
        elapsed_ms = (time.monotonic() - start_time) * 1000
        log_usage(TokenUsage(
            model=data.get("model", self._model),
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            provider="anthropic",
            duration_ms=round(elapsed_ms, 1),
        ))

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        system, converted = self._convert_messages(messages)
        body = self._build_request(converted, system=system, tools=tools)
        start_time = time.monotonic()

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

        content = ""
        tool_calls: list[ToolCallRequest] = []

        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCallRequest(
                    id=block["id"],
                    name=block["name"],
                    arguments=block["input"],
                ))

        stop_reason = data.get("stop_reason", "end_turn")
        finish = "stop"
        if stop_reason == "tool_use":
            finish = "tool_calls"
        elif stop_reason == "max_tokens":
            finish = "length"

        usage = data.get("usage", {})
        self._log_usage(data, start_time)
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish,
            usage={"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)},
        )

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[dict]:
        """Streaming not implemented for Anthropic yet — falls back to non-streaming."""
        result = await self.chat(messages, tools, **kwargs)
        yield {"type": "delta", "content": result.content or ""}
        yield {"type": "done", "content": result.content or ""}
