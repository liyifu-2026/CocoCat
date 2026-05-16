"""OpenAI-compatible provider (covers OpenAI, DeepSeek, SiliconFlow, etc.)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

import httpx

from cococat.providers.base import BaseProvider, LLMResponse, ToolCallRequest
from cococat.providers.usage import TokenUsage, log_usage

logger = logging.getLogger("cococat.providers.openai_compat")


def _tool_to_openai(tool: dict) -> dict:
    """Convert CocoCat flat tool format to OpenAI/DeepSeek function schema.

    Ensures API-compliant JSON Schema:
    - array types get items: {type: "string"} (required by DeepSeek/OpenAI)
    - number, integer, string, boolean types pass through as-is
    - Empty params receive a minimal safe schema
    """
    params = tool.get("parameters", {})
    properties = {}
    for name, ptype in params.items():
        prop: dict = {"type": ptype, "description": ""}
        if ptype == "array":
            prop["items"] = {"type": "string"}
        properties[name] = prop

    if not properties:
        return {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }

    return {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": list(params.keys()),
        },
    }


class OpenAICompatProvider(BaseProvider):
    """Provider for any OpenAI-compatible API (OpenAI, DeepSeek, Groq, Ollama, etc.)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        provider_name: str = "",
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._provider_name = provider_name

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
                {"type": "function", "function": _tool_to_openai(t)} for t in tools
            ]
        return body

    def _log_usage(self, data: dict, start_time: float, provider_name: str = "") -> None:
        """Extract usage from API response and log it."""
        usage = data.get("usage", {})
        if not usage:
            return
        elapsed_ms = (time.monotonic() - start_time) * 1000
        log_usage(TokenUsage(
            model=data.get("model", self._model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            provider=provider_name,
            duration_ms=round(elapsed_ms, 1),
        ))

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send a non-streaming chat request."""
        body = self._build_request(messages, tools, stream=False)
        start_time = time.monotonic()

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if resp.status_code >= 400:
                err_body = resp.text[:1000]
                logger.error("DeepSeek 400: status=%s body=%s request_body=%s",
                           resp.status_code, err_body, json.dumps(body, ensure_ascii=False)[:2000])
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content") or ""
        tool_calls = [
            ToolCallRequest(
                id=tc["id"],
                name=tc["function"]["name"],
                arguments=tc["function"]["arguments"],
            )
            for tc in (msg.get("tool_calls") or [])
        ]
        finish_reason = choice.get("finish_reason", "stop")
        usage = data.get("usage", {})

        self._log_usage(data, start_time, provider_name=self._provider_name)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)},
            reasoning_content=msg.get("reasoning_content"),
        )

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[dict]:
        """Send a streaming chat request. Yields {'type': 'delta'|'tool_call'|'reasoning'|'done', ...}."""
        body = self._build_request(messages, tools, stream=True)
        body["stream_options"] = {"include_usage": True}

        accumulated = []
        tc_buffer: dict[int, dict] = {}  # index → {id, name, arguments}
        last_usage: dict = {}
        start_time = time.monotonic()

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
                            if "usage" in chunk:
                                last_usage = chunk
                            choice = chunk.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            reasoning = delta.get("reasoning_content", "")
                            tool_calls = delta.get("tool_calls")

                            if content:
                                accumulated.append(content)
                                yield {"type": "delta", "content": content}
                            if reasoning:
                                yield {"type": "reasoning", "content": reasoning}
                            if tool_calls:
                                for tc in tool_calls:
                                    idx = tc.get("index", 0)
                                    if idx not in tc_buffer:
                                        tc_buffer[idx] = {"id": "", "name": "", "arguments": ""}
                                    entry = tc_buffer[idx]
                                    if "id" in tc and tc["id"]:
                                        entry["id"] = tc["id"]
                                    func = tc.get("function", {})
                                    if func.get("name"):
                                        entry["name"] = func["name"]
                                    if func.get("arguments"):
                                        entry["arguments"] += func["arguments"]
                                    # Emit tool_call when we have a complete one
                                    if entry["name"] and entry["arguments"]:
                                        try:
                                            json.loads(entry["arguments"])  # validate
                                            yield {"type": "tool_call", "id": entry["id"], "name": entry["name"], "arguments": entry["arguments"]}
                                            # Reset for potential next call
                                            tc_buffer[idx] = {"id": "", "name": "", "arguments": ""}
                                        except json.JSONDecodeError:
                                            pass  # wait for more chunks
                        except json.JSONDecodeError:
                            continue

        self._log_usage(last_usage, start_time, provider_name=self._provider_name)
        yield {"type": "done", "content": "".join(accumulated)}
