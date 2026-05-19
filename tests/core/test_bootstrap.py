"""Tests for cococat.core.bootstrap factory/helper functions."""
import os
import json
import yaml
import pytest
from unittest.mock import MagicMock

from cococat.core.agent import AgentRole
from cococat.core.bootstrap import (
    _create_stub_llm,
    _map_role,
    _seed_default_residents,
    _seed_cron_jobs,
    _setup_providers,
    _setup_sub_executor,
)
from cococat.providers.credentials import CredentialManager
from cococat.providers.factory import ProviderFactory
from cococat.core.sub_agent import SubAgentExecutor


def _make_config_store():
    store = MagicMock()
    store.cron_dir = os.path.join("runs", "cron")
    return store


# ── _create_stub_llm ────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_stub_llm_returns_stub_with_model_in_content():
    stub = _create_stub_llm("gpt-4")
    result = await stub.chat([])
    assert "gpt-4" in result.content
    assert result.tool_calls is None


# ── _map_role ───────────────────────────────────────────────

def test_map_role_known_strings():
    assert _map_role("worker") == AgentRole.WORKER
    assert _map_role("resident") == AgentRole.RESIDENT
    assert _map_role("main") == AgentRole.RESIDENT
    assert _map_role("sub") == AgentRole.WORKER
    assert _map_role("leader") == AgentRole.RESIDENT
    assert _map_role("employee") == AgentRole.WORKER


def test_map_role_unknown_returns_none():
    assert _map_role("unknown_role") is None


def test_map_role_enum_passthrough():
    assert _map_role(AgentRole.RESIDENT) == AgentRole.RESIDENT
    assert _map_role(AgentRole.WORKER) == AgentRole.WORKER


# ── _seed_default_residents ─────────────────────────────────

def test_seed_default_residents_creates_both_files(tmp_path):
    config_dir = str(tmp_path)
    _seed_default_residents(config_dir)
    coco = os.path.join(config_dir, "coco.yaml")
    kb = os.path.join(config_dir, "kb-agent.yaml")
    assert os.path.exists(coco)
    assert os.path.exists(kb)
    with open(coco) as f:
        data = yaml.safe_load(f)
    assert data["id"] == "coco"
    assert data["name"] == "Coco"
    assert data["role"] == "resident"
    with open(kb) as f:
        data = yaml.safe_load(f)
    assert data["id"] == "kb-agent"
    assert data["role"] == "resident"


def test_seed_default_residents_idempotent(tmp_path):
    config_dir = str(tmp_path)
    _seed_default_residents(config_dir)
    coco_path = os.path.join(config_dir, "coco.yaml")
    mtime1 = os.path.getmtime(coco_path)
    _seed_default_residents(config_dir)
    assert os.path.getmtime(coco_path) == mtime1


# ── _seed_cron_jobs ─────────────────────────────────────────

def test_seed_cron_jobs_creates_file_with_fields():
    entries = [{"name": "lint", "schedule": "@daily", "task": "Run lint"}]
    config_store = _make_config_store()
    _seed_cron_jobs("agent-x", entries, config_store)
    path = os.path.join("runs", "cron", "agent-x-lint.json")
    assert os.path.exists(path)
    with open(path) as f:
        job = json.load(f)
    assert job["id"] == "agent-x-lint"
    assert job["name"] == "lint"
    assert job["schedule"] == "@daily"
    assert job["task"] == "Run lint"
    assert job["agent_id"] == "agent-x"
    os.remove(path)


def test_seed_cron_jobs_defaults():
    entries = [{"name": "cleanup"}]
    config_store = _make_config_store()
    _seed_cron_jobs("agent-x", entries, config_store)
    path = os.path.join("runs", "cron", "agent-x-cleanup.json")
    with open(path) as f:
        job = json.load(f)
    assert job["schedule"] == "@daily"
    assert job["task"] == "Run cleanup maintenance"
    os.remove(path)


def test_seed_cron_jobs_idempotent():
    entries = [{"name": "idem", "schedule": "@daily"}]
    config_store = _make_config_store()
    _seed_cron_jobs("agent-x", entries, config_store)
    path = os.path.join("runs", "cron", "agent-x-idem.json")
    mtime1 = os.path.getmtime(path)
    _seed_cron_jobs("agent-x", entries, config_store)
    assert os.path.getmtime(path) == mtime1
    os.remove(path)


# ── _setup_providers ────────────────────────────────────────

def test_setup_providers_sets_creds_and_factory():
    ctx = MagicMock()
    ctx.config_store = MagicMock()
    factory = _setup_providers(ctx, auth_path="config/test-auth.json")
    assert isinstance(ctx.creds, CredentialManager)
    assert isinstance(ctx.provider_factory, ProviderFactory)
    assert isinstance(factory, ProviderFactory)
    assert ctx.config_store == ctx.creds._config_store


# ── _setup_sub_executor ─────────────────────────────────────

def test_setup_sub_executor_sets_sub_executor():
    ctx = MagicMock()
    ctx.bus = MagicMock()
    ctx.pool = MagicMock()
    sandbox_provider = MagicMock()
    executor = _setup_sub_executor(ctx, sandbox_provider)
    assert isinstance(executor, SubAgentExecutor)
    assert ctx.sub_executor is executor
