from __future__ import annotations

import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    reasoning_content: str | None = None
    error_status_code: int | None = None
    error_type: str | None = None
    error_should_retry: bool | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def should_execute_tools(self) -> bool:
        if not self.has_tool_calls:
            return False
        return self.finish_reason in ("tool_calls", "stop")


@dataclass(frozen=True)
class GenerationSettings:
    temperature: float = 0.7
    max_tokens: int = 4096
    reasoning_effort: str | None = None


class LLMProvider(ABC):
    generation: GenerationSettings = GenerationSettings()

    _CHAT_RETRY_DELAYS = (1, 2, 4)
    _TRANSIENT_ERROR_MARKERS = (
        "429", "rate limit", "500", "502", "503", "504",
        "overloaded", "timeout", "timed out", "connection",
        "server error", "temporarily unavailable",
    )
    _RETRYABLE_STATUS_CODES = frozenset({408, 409, 429})
    _NON_RETRYABLE_TOKENS = frozenset({
        "insufficient_quota", "quota_exceeded",
        "billing_hard_limit_reached", "insufficient_balance",
        "payment_required",
    })

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        ...

    def chat_stream(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7,
                    reasoning_effort=None):
        """Default: yield full response as a single delta. Override for true streaming."""
        response = self.chat(
            messages=messages, tools=tools, model=model,
            max_tokens=max_tokens, temperature=temperature,
            reasoning_effort=reasoning_effort,
        )
        if response.content:
            yield {"type": "delta", "content": response.content}
        yield {"type": "done", "content": response.content or ""}

    @classmethod
    def _is_transient(cls, response: LLMResponse) -> bool:
        if response.error_should_retry is not None:
            return response.error_should_retry
        if response.error_status_code:
            if response.error_status_code == 429:
                return cls._is_retryable_429(response)
            if response.error_status_code in cls._RETRYABLE_STATUS_CODES or response.error_status_code >= 500:
                return True
        err = (response.content or "").lower()
        return any(m in err for m in cls._TRANSIENT_ERROR_MARKERS)

    @classmethod
    def _is_retryable_429(cls, response: LLMResponse) -> bool:
        type_val = (response.error_type or "").lower()
        if any(t in type_val for t in cls._NON_RETRYABLE_TOKENS):
            return False
        content = (response.content or "").lower()
        if any(t in content for t in cls._NON_RETRYABLE_TOKENS):
            return False
        return True

    @classmethod
    def _extract_retry_after(cls, content: str | None) -> float | None:
        if not content:
            return None
        text = content.lower()
        patterns = (
            r"retry after\s+(\d+(?:\.\d+)?)",
            r"try again in\s+(\d+(?:\.\d+)?)",
            r"retry[_-]?after[\"'\s:=]+(\d+(?:\.\d+)?)",
        )
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return max(0.1, float(m.group(1)))
        return None

    def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        retry_mode: str = "standard",
    ) -> LLMResponse:
        attempt = 0
        delays = list(self._CHAT_RETRY_DELAYS)
        last_response: LLMResponse | None = None

        while True:
            attempt += 1
            try:
                response = self.chat(
                    messages=messages, tools=tools, model=model,
                    max_tokens=max_tokens, temperature=temperature,
                    reasoning_effort=reasoning_effort,
                )
            except Exception as e:
                response = LLMResponse(
                    content=f"LLM call error: {e}",
                    finish_reason="error",
                    error_type="exception",
                    error_should_retry=True,
                )

            if response.finish_reason != "error":
                return response

            last_response = response

            if not self._is_transient(response):
                return response

            if retry_mode != "persistent" and attempt > len(delays):
                break

            base_delay = delays[min(attempt - 1, len(delays) - 1)]
            delay = self._extract_retry_after(response.content) or base_delay
            delay = delay + random.random()
            time.sleep(delay)

        return last_response if last_response else LLMResponse(content="LLM call failed", finish_reason="error")
