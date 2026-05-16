"""Structured token usage logging for LLM providers."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger("cococat.providers.usage")


@dataclass
class TokenUsage:
    """Token consumption for a single LLM API call."""
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    provider: str
    duration_ms: float


def log_usage(usage: TokenUsage) -> None:
    """Emit structured token usage as a JSON log line."""
    logger.info(json.dumps(asdict(usage), ensure_ascii=False))
