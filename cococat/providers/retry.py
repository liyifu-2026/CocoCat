"""Retry logic with exponential backoff + jitter + smart transient detection."""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger("cococat.retry")

# HTTP 429 errors that should NOT be retried (quota/billing issues — unfixable)
_NON_RETRYABLE_429_TOKENS = {
    "insufficient_quota",
    "quota_exceeded",
    "billing",
    "quota",
    "超出配额",
    "余额不足",
}

# Transient error markers (retryable)
_TRANSIENT_TOKENS = {
    "rate limit", "rate_limit", "overloaded", "timeout", "timed out",
    "connection", "connectionerror", "timeouterror",
    "service unavailable", "internal server error",
    "server error", "too many requests",
}


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True


def _is_transient(exception: Exception) -> bool:
    """Check if an exception represents a transient (retryable) error."""
    status = getattr(exception, "status_code", None)

    # 429 with quota token → NOT retryable
    if status == 429:
        msg = str(exception).lower()
        for token in _NON_RETRYABLE_429_TOKENS:
            if token in msg:
                return False
        return True  # Other 429s (rate limits) are retryable

    # 408, 409, 5xx → retryable
    if status in (408, 409) or (status and 500 <= status < 600):
        return True

    # Built-in connection/timeout types are always transient
    if isinstance(exception, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
        return True

    # Check message tokens
    msg = str(exception).lower()
    for token in _TRANSIENT_TOKENS:
        if token in msg:
            return True

    return False


async def with_retry(
    fn: Callable[[], Awaitable[Any]],
    config: RetryConfig = RetryConfig(),
) -> Any:
    """Call fn with exponential backoff retry on transient errors.

    Raises the original exception if all retries exhausted or error is permanent.
    """
    last_error = None

    for attempt in range(config.max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            if attempt == config.max_retries:
                break
            if not _is_transient(e):
                break

            delay = min(config.base_delay * (2 ** attempt), config.max_delay)
            if config.jitter:
                delay += random.random()

            logger.debug(
                "Retry %d/%d after %.1fs: %s",
                attempt + 1, config.max_retries, delay, str(e)[:100],
            )
            await asyncio.sleep(delay)

    raise last_error  # type: ignore[misc]
