from __future__ import annotations

from typing import Any

import httpx

from .base import LLMProvider, LLMResponse, ToolCallRequest


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str = "", model: str = "", base_url: str = ""):
        self.api_key = api_key
        self.model = model or "claude-sonnet-4-20250514"
        self.base_url = base_url.rstrip("/") or "https://api.anthropic.com"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    def _to_anthropic_messages(self, messages: list[dict]) -> list[dict]:
        result = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            tc = m.get("tool_calls")
            tcid = m.get("tool_call_id")
            if role == "tool":
                result.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": tcid, "content": content}]})
            elif tc:
                blocks = []
                if content:
                    blocks.append({"type": "text", "text": content})
                for t in tc:
                    blocks.append({"type": "tool_use", "id": t["id"], "name": t["name"], "input": t.get("arguments", {})})
                result.append({"role": "assistant", "content": blocks})
            else:
                result.append({"role": role, "content": content})
        return result

    def _to_anthropic_tools(self, tools: list[dict]) -> list[dict]:
        result = []
        for t in tools:
            fn = t.get("function", t)
            result.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return result

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        body = {
            "model": model or self.model,
            "messages": self._to_anthropic_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = self._to_anthropic_tools(tools)

        try:
            resp = self._client.post("/v1/messages", json=body)
        except httpx.TimeoutException as e:
            return LLMResponse(content=f"Timeout: {e}", finish_reason="error", error_type="timeout", error_should_retry=True)
        except httpx.RequestError as e:
            return LLMResponse(content=f"Connection error: {e}", finish_reason="error", error_type="connection", error_should_retry=True)

        if resp.status_code != 200:
            try:
                err = resp.json()
                err_type = err.get("error", {}).get("type", "")
            except Exception:
                err_type = ""
            return LLMResponse(
                content=f"API error {resp.status_code}: {resp.text[:200]}",
                finish_reason="error",
                error_status_code=resp.status_code,
                error_type=err_type,
            )

        data = resp.json()
        content = ""
        tool_calls = []
        stop_reason = data.get("stop_reason", "end_turn")
        finish = "stop"
        if stop_reason == "tool_use":
            finish = "tool_calls"
        elif stop_reason == "max_tokens":
            finish = "length"

        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCallRequest(
                    id=block["id"], name=block["name"], arguments=block.get("input", {}),
                ))

        usage = data.get("usage", {})
        return LLMResponse(
            content=content, tool_calls=tool_calls, finish_reason=finish,
            usage={"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)},
        )
