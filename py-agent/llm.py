"""OpenAI-compatible LLM client (nanobot pattern)."""
import json
import os
from openai import OpenAI


class LLMClient:
    """Thin wrapper around OpenAI API for chat completions."""

    def __init__(self, api_key: str | None = None, model: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        base_url = base_url or os.environ.get("OPENAI_BASE_URL", "")
        self.client = OpenAI(api_key=self.api_key, base_url=base_url or None)

    def _sanitize_messages(self, messages: list[dict]) -> list[dict]:
        """Remove non-standard fields that some providers don't accept."""
        allowed_msg_keys = {"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"}
        sanitized = []
        for msg in messages:
            clean = {k: v for k, v in msg.items() if k in allowed_msg_keys}
            sanitized.append(clean)
        return sanitized

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> dict:
        """Call LLM and return response with content and/or tool_calls."""
        kwargs = dict(
            model=self.model,
            messages=self._sanitize_messages(messages),
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)

        choice = response.model_dump()["choices"][0]
        message = choice.get("message", {})

        result = {
            "content": message.get("content") or "",
            "tool_calls": [],
            "finish_reason": choice.get("finish_reason", "stop"),
            "reasoning_content": message.get("reasoning_content"),
        }

        raw_tool_calls = message.get("tool_calls") or []
        for tc in raw_tool_calls:
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                args = {"_error": f"failed to parse arguments: {tc.get('function', {}).get('arguments', '?')}"}
            result["tool_calls"].append({
                "id": tc["id"],
                "name": tc["function"]["name"],
                "arguments": args,
            })

        return result
