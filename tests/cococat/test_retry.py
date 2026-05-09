"""Tests for provider retry logic."""
import pytest
from cococat.providers.retry import RetryConfig, with_retry


@pytest.mark.asyncio
async def test_retry_succeeds_first_try():
    calls = []

    async def fn():
        calls.append(1)
        return "ok"

    result = await with_retry(fn, RetryConfig(max_retries=3))
    assert result == "ok"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retry_on_transient_error():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("timeout")
        return "ok"

    result = await with_retry(fn, RetryConfig(max_retries=5, base_delay=0.01))
    assert result == "ok"
    assert len(calls) == 3  # Failed 2, succeeded 3rd


@pytest.mark.asyncio
async def test_retry_exhausted():
    calls = []

    async def fn():
        calls.append(1)
        raise ConnectionError("always fails")

    with pytest.raises(ConnectionError):
        await with_retry(fn, RetryConfig(max_retries=2, base_delay=0.01))
    assert len(calls) == 3  # Initial + 2 retries


@pytest.mark.asyncio
async def test_no_retry_on_non_transient():
    calls = []

    async def fn():
        calls.append(1)
        raise ValueError("invalid parameter")

    with pytest.raises(ValueError):
        await with_retry(fn, RetryConfig(max_retries=3, base_delay=0.01))
    assert len(calls) == 1  # No retry on permanent errors


@pytest.mark.asyncio
async def test_retry_on_429_rate_limit():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 2:
            # Simulate HTTP 429
            e = Exception("rate limit exceeded")
            setattr(e, "status_code", 429)
            raise e
        return "ok"

    result = await with_retry(fn, RetryConfig(max_retries=3, base_delay=0.01))
    assert result == "ok"


@pytest.mark.asyncio
async def test_no_retry_on_429_quota_exceeded():
    calls = []

    async def fn():
        calls.append(1)
        e = Exception("insufficient_quota")
        setattr(e, "status_code", 429)
        raise e

    with pytest.raises(Exception):
        await with_retry(fn, RetryConfig(max_retries=3, base_delay=0.01))
    assert len(calls) == 1  # Quota errors are non-retryable


@pytest.mark.asyncio
async def test_retry_on_status_408():
    calls = []

    async def fn():
        calls.append(1)
        e = Exception("request timeout")
        setattr(e, "status_code", 408)
        raise e

    with pytest.raises(Exception):
        await with_retry(fn, RetryConfig(max_retries=2, base_delay=0.01))
    assert len(calls) == 3  # 408 is transient


@pytest.mark.asyncio
async def test_retry_on_status_500():
    calls = []

    async def fn():
        calls.append(1)
        e = Exception("server error")
        setattr(e, "status_code", 500)
        raise e

    with pytest.raises(Exception):
        await with_retry(fn, RetryConfig(max_retries=1, base_delay=0.01))
    assert len(calls) == 2  # 500 is transient


@pytest.mark.asyncio
async def test_retry_on_connection_error_type():
    """Built-in ConnectionError should be auto-detected as transient."""
    calls = []

    async def fn():
        calls.append(1)
        raise ConnectionError("always fails")

    with pytest.raises(ConnectionError):
        await with_retry(fn, RetryConfig(max_retries=2, base_delay=0.01))
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_retry_on_timeout_error_type():
    """TimeoutError should be auto-detected as transient."""
    calls = []

    async def fn():
        calls.append(1)
        raise TimeoutError("timed out")

    with pytest.raises(TimeoutError):
        await with_retry(fn, RetryConfig(max_retries=2, base_delay=0.01))
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_retry_message_token_overloaded():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("server is overloaded")
        return "ok"

    result = await with_retry(fn, RetryConfig(max_retries=5, base_delay=0.01))
    assert result == "ok"


@pytest.mark.asyncio
async def test_retry_quota_exceeded_chinese():
    calls = []

    async def fn():
        calls.append(1)
        e = Exception("余额不足")
        setattr(e, "status_code", 429)
        raise e

    with pytest.raises(Exception):
        await with_retry(fn, RetryConfig(max_retries=2, base_delay=0.01))
    assert len(calls) == 1  # Chinese quota token — non-retryable


@pytest.mark.asyncio
async def test_retry_jitter_disabled():
    calls = []

    async def fn():
        calls.append(1)
        raise ConnectionError("transient")

    with pytest.raises(ConnectionError):
        await with_retry(fn, RetryConfig(max_retries=1, base_delay=0.01, jitter=False))
    assert len(calls) == 2  # Still retries once


@pytest.mark.asyncio
async def test_retry_zero_max_retries():
    calls = []

    async def fn():
        calls.append(1)
        raise ConnectionError("fail")

    with pytest.raises(ConnectionError):
        await with_retry(fn, RetryConfig(max_retries=0, base_delay=0.01))
    assert len(calls) == 1  # Try once, no retry
