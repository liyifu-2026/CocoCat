"""Multi-provider LLM client with retry and fallback chain.
Supports OpenAI-compatible, Anthropic Claude, and Google Gemini."""
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


def _sanitize_openai_messages(messages):
    allowed = {"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"}
    return [{k: v for k, v in m.items() if k in allowed} for m in messages]


class OpenAICompatibleProvider(Provider):
    def __init__(self, api_key=None, model=None, base_url=None):
        from openai import OpenAI
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        base_url = base_url or os.environ.get("OPENAI_BASE_URL", "")
        self.client = OpenAI(api_key=self.api_key, base_url=base_url or None)

    def chat(self, messages, tools=None, max_tokens=4096, temperature=0.7) -> LLMResponse:
        kwargs = dict(model=self.model, messages=_sanitize_openai_messages(messages), max_tokens=max_tokens, temperature=temperature)
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
        kwargs = dict(model=self.model, messages=_sanitize_openai_messages(messages), max_tokens=max_tokens, temperature=temperature, stream=True, stream_options={"include_usage": True})
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


class AnthropicProvider(Provider):
    """Provider for Anthropic Claude API."""

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    def _to_anthropic_messages(self, messages):
        anthro = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            tc = m.get("tool_calls")
            tcid = m.get("tool_call_id")
            if role == "tool":
                anthro.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": tcid, "content": content}]})
            elif tc:
                blocks = []
                if content:
                    blocks.append({"type": "text", "text": content})
                for t in tc:
                    blocks.append({"type": "tool_use", "id": t["id"], "name": t["name"], "input": t.get("arguments", {})})
                anthro.append({"role": "assistant", "content": blocks})
            else:
                anthro.append({"role": role, "content": content})
        return anthro

    def _to_openai_tools(self, tools):
        result = []
        for t in tools:
            func = t.get("function", t)
            result.append({"name": func["name"], "description": func.get("description", ""), "input_schema": func.get("parameters", {"type": "object", "properties": {}})})
        return result

    def _parse_response(self, data):
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
                tool_calls.append({"id": block["id"], "name": block["name"], "arguments": block.get("input", {})})
        return LLMResponse(content=content, tool_calls=tool_calls, finish_reason=finish)

    def chat(self, messages, tools=None, max_tokens=4096, temperature=0.7) -> LLMResponse:
        import httpx
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        body = {"model": self.model, "messages": self._to_anthropic_messages(messages), "max_tokens": max_tokens, "temperature": temperature}
        if tools:
            body["tools"] = self._to_openai_tools(tools)
        resp = httpx.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        return self._parse_response(resp.json())


class GeminiProvider(Provider):
    """Provider for Google Gemini API."""

    def _to_gemini_contents(self, messages):
        contents = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            tc = m.get("tool_calls")
            tcid = m.get("tool_call_id")
            gemini_role = "model" if role == "assistant" else "user"
            if role == "tool":
                fn_resp = {"functionResponse": {"name": "tool", "response": {"content": content}}}
                contents.append({"role": "user", "parts": [fn_resp]})
            elif tc:
                parts = []
                if content:
                    parts.append({"text": content})
                for t in tc:
                    parts.append({"functionCall": {"name": t["name"], "args": t.get("arguments", {})}})
                contents.append({"role": gemini_role, "parts": parts})
            else:
                contents.append({"role": gemini_role, "parts": [{"text": content}]})
        return contents

    def _to_gemini_tools(self, tools):
        decls = []
        for t in tools:
            func = t.get("function", t)
            decls.append({"name": func["name"], "description": func.get("description", ""), "parameters": func.get("parameters", {"type": "object", "properties": {}})})
        return [{"functionDeclarations": decls}]

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        self._call_counter = 0

    def _parse_response(self, data):
        content = ""
        tool_calls = []
        fr = "stop"
        try:
            cand = data["candidates"][0]
            finish = cand.get("finishReason", "STOP")
            if finish == "FUNCTION_CALL":
                fr = "tool_calls"
            elif finish == "MAX_TOKENS":
                fr = "length"
            for part in cand["content"]["parts"]:
                if "text" in part:
                    content += part["text"]
                elif "functionCall" in part:
                    self._call_counter += 1
                    fc = part["functionCall"]
                    tool_calls.append({"id": f"gemini_{self._call_counter}", "name": fc["name"], "arguments": fc.get("args", {})})
        except (KeyError, IndexError):
            pass
        return LLMResponse(content=content, tool_calls=tool_calls, finish_reason=fr)

    def chat(self, messages, tools=None, max_tokens=4096, temperature=0.7) -> LLMResponse:
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        body = {"contents": self._to_gemini_contents(messages), "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature}}
        if tools:
            body["tools"] = self._to_gemini_tools(tools)
        resp = httpx.post(url, json=body, timeout=120)
        resp.raise_for_status()
        return self._parse_response(resp.json())


class LLMClient:
    """Multi-provider client with retry and fallback chain."""

    def __init__(self, providers=None):
        self.providers = providers or []
        if not self.providers:
            self.providers = self._auto_detect_providers()

    def _auto_detect_providers(self) -> list:
        providers = []
        if os.environ.get("OPENAI_API_KEY", ""):
            providers.append(OpenAICompatibleProvider(
                api_key=os.environ["OPENAI_API_KEY"],
                model=os.environ.get("LLM_MODEL", "deepseek-v4-flash"),
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com"),
            ))
        if os.environ.get("ANTHROPIC_API_KEY", ""):
            providers.append(AnthropicProvider(
                api_key=os.environ["ANTHROPIC_API_KEY"],
                model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            ))
        if os.environ.get("GEMINI_API_KEY", ""):
            providers.append(GeminiProvider(
                api_key=os.environ["GEMINI_API_KEY"],
                model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            ))
        if not providers:
            providers.append(OpenAICompatibleProvider(
                model=os.environ.get("LLM_MODEL", "deepseek-v4-flash"),
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com"),
            ))
        return providers

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
