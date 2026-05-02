"""Multi-provider LLM client with retry and fallback (nanobot pattern)."""
import json
import os
import time
import random


class LLMResponse:
    def __init__(self, content="", tool_calls=None, finish_reason="stop", reasoning_content=None):
        self.content = content or ""
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason
        self.reasoning_content = reasoning_content

    def to_dict(self):
        return {
            "content": self.content,
            "tool_calls": self.tool_calls,
            "finish_reason": self.finish_reason,
            "reasoning_content": self.reasoning_content,
        }


class Provider:
    """Base provider interface."""
    def chat(self, messages, tools=None, max_tokens=4096, temperature=0.7) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatibleProvider(Provider):
    def __init__(self, api_key=None, model=None, base_url=None):
        from openai import OpenAI
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        base_url = base_url or os.environ.get("OPENAI_BASE_URL", "")
        self.client = OpenAI(api_key=self.api_key, base_url=base_url or None)

    def chat(self, messages, tools=None, max_tokens=4096, temperature=0.7) -> LLMResponse:
        kwargs = dict(model=self.model, messages=self._sanitize(messages), max_tokens=max_tokens, temperature=temperature)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        choice = response.model_dump()["choices"][0]
        message = choice.get("message", {})

        tool_calls = []
        for tc in (message.get("tool_calls") or []):
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                args = {"_error": f"failed to parse: {tc.get('function', {}).get('arguments', '?')}"}
            tool_calls.append({"id": tc["id"], "name": tc["function"]["name"], "arguments": args})

        return LLMResponse(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            reasoning_content=message.get("reasoning_content"),
        )

    def chat_stream(self, messages, tools=None, max_tokens=4096, temperature=0.7):
        """Stream tokens from LLM. Yields dicts with 'type': 'delta'|'done'."""
        kwargs = dict(model=self.model, messages=self._sanitize(messages), max_tokens=max_tokens, temperature=temperature, stream=True, stream_options={"include_usage": True})
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = self.client.chat.completions.create(**kwargs)
        content_chunks = []
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content_chunks.append(delta.content)
                yield {"type": "delta", "content": delta.content}
        yield {"type": "done", "content": "".join(content_chunks)}

    def _sanitize(self, messages):
        allowed = {"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"}
        return [{k: v for k, v in m.items() if k in allowed} for m in messages]


class LLMClient:
    """Multi-provider client with retry and fallback chain."""

    def __init__(self, providers=None):
        self.providers = providers or []
        if not self.providers:
            key = os.environ.get("OPENAI_API_KEY", "")
            model = os.environ.get("LLM_MODEL", "deepseek-v4-flash")
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
            self.providers = [OpenAICompatibleProvider(api_key=key, model=model, base_url=base_url)]

    def chat(self, messages, tools=None, max_tokens=4096, temperature=0.7, max_retries=3) -> dict:
        last_error = None
        for attempt in range(max_retries + 1):
            for provider_idx, provider in enumerate(self.providers):
                try:
                    resp = provider.chat(messages, tools=tools, max_tokens=max_tokens, temperature=temperature)
                    return resp.to_dict()
                except Exception as e:
                    last_error = e
                    if provider_idx < len(self.providers) - 1:
                        continue
                    if attempt < max_retries:
                        delay = (2 ** attempt) + random.random()
                        time.sleep(delay)
                        continue
        return {"content": f"LLM call failed after {max_retries} retries: {last_error}", "tool_calls": [], "finish_reason": "error"}

    def chat_stream(self, messages, tools=None, max_tokens=4096, temperature=0.7):
        for provider in self.providers:
            if hasattr(provider, 'chat_stream'):
                yield from provider.chat_stream(messages, tools=tools, max_tokens=max_tokens, temperature=temperature)
                return
        yield {"type": "done", "content": "(streaming not supported)"}
