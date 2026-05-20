"""Tests for memory pipeline."""
import os
import json
import tempfile
import asyncio
import pytest
from cococat.core.session import Session, SessionManager
from cococat.memory import MemoryStore
from cococat.db import Database
from cococat.providers.base import LLMResponse
class FakeLLM:
    async def chat(self, messages, tools=None, **kwargs):
        content = messages[-1]["content"]
        if "Extract" in content:
            return LLMResponse(content='[{"text": "User prefers short answers", "tags": "preference"}]')
        return LLMResponse(content="Summary: user asked about refund policy.")
@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d
@pytest.fixture
def llm():
    return FakeLLM()
