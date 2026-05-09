"""DeepSeek provider compat — normalizes thinking format + reasoning_effort."""

from __future__ import annotations

import logging

logger = logging.getLogger("cococat.providers.deepseek_compat")

# reasoning_effort → thinking mapping for DeepSeek
_EFFORT_MAP = {
    "low": "enabled",
    "medium": "enabled",
    "high": "enabled",
    "xhigh": "enabled",
    "max": "enabled",
}


def matches(model_id: str) -> bool:
    """Check if this model needs DeepSeek compat."""
    return "deepseek" in model_id.lower()


def apply(request: dict, model_id: str, options: dict | None = None) -> dict:
    """Apply DeepSeek-specific normalizations to the request.

    DeepSeek uses `thinking: {type: "enabled"/"disabled"}` instead of
    reasoning_effort. Also bumps max_tokens for thinking mode.
    """
    options = options or {}

    # Normalize thinking format
    if "thinking" not in request:
        mode = options.get("mode", "chat")
        if mode == "utility":
            request["thinking"] = {"type": "disabled"}
        else:
            request["thinking"] = {"type": "enabled"}

    # If reasoning_effort is set, convert to thinking
    if "reasoning_effort" in request:
        effort = request.pop("reasoning_effort")
        if effort in _EFFORT_MAP:
            request["thinking"] = {"type": _EFFORT_MAP[effort]}

    # Ensure max_tokens is sufficient for thinking mode
    if request.get("thinking", {}).get("type") == "enabled":
        max_tokens = request.get("max_tokens", 0)
        if max_tokens and max_tokens < 32768:
            request["max_tokens"] = max(max_tokens, 32768)
        elif not max_tokens:
            request["max_tokens"] = 32768

    # DeepSeek can handle max_tokens as None (unlimited)
    if "max_tokens" in request and request["max_tokens"] == 0:
        del request["max_tokens"]

    return request
