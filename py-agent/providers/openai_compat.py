from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .base import LLMProvider, LLMResponse, ToolCallRequest

ALLOWED_MESSAGE_KEYS = frozenset({
    "role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content",
})


def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in m.items() if k in ALLOWED_MESSAGE_KEYS} for m in messages]


def _parse_tool_calls(tool_calls_data: list[dict]) -> list[ToolCallRequest]:
    result: list[ToolCallRequest] = []
    for tc in tool_calls_data:
        try:
            args = json.loads(tc["function"]["arguments"])
        except (json.JSONDecodeError, KeyError):
            args = {"_error": f"failed to parse: {tc.get('function', {}).get('arguments', '?')}"}
        result.append(ToolCallRequest(
            id=tc["id"],
            name=tc["function"]["name"],
            arguments=args,
        ))
    return result


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
        extra_headers: dict[str, str] | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        base_url = base_url or os.environ.get("OPENAI_BASE_URL", "")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(120),
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": model or self.model,
            "messages": _sanitize_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        try:
            resp = self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException:
            return LLMResponse(content=None, finish_reason="error", error_type="timeout", error_should_retry=True)
        except httpx.ConnectError:
            return LLMResponse(content=None, finish_reason="error", error_type="connection", error_should_retry=True)

        if resp.status_code != 200:
            error_type = None
            error_content = ""
            try:
                err_body = resp.json()
                error_type = err_body.get("error", {}).get("type")
                error_content = err_body.get("error", {}).get("message", "")
            except (json.JSONDecodeError, AttributeError):
                error_content = resp.text
            return LLMResponse(
                content=error_content,
                finish_reason="error",
                error_status_code=resp.status_code,
                error_type=error_type,
            )

        data = resp.json()
        choice = data["choices"][0]
        message = choice.get("message", {})

        content = message.get("content")
        tool_calls = _parse_tool_calls(message.get("tool_calls") or [])
        finish_reason = choice.get("finish_reason", "stop")
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            reasoning_content=message.get("reasoning_content"),
        )

    def chat_stream(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
        body: dict[str, Any] = {
            "model": model or self.model,
            "messages": _sanitize_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        try:
            with self._client.stream("POST", "/chat/completions", json=body) as resp:
                content_chunks: list[str] = []
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if not chunk.get("choices"):
                        continue
                    delta = chunk["choices"][0].get("delta", {})
                    if delta.get("content"):
                        content_chunks.append(delta["content"])
                        yield {"type": "delta", "content": delta["content"]}
                yield {"type": "done", "content": "".join(content_chunks)}
        except Exception as e:
            yield {"type": "error", "content": str(e)}
