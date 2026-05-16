"""Agent bootstrap — wires providers, sandbox, tools, and loads agents from DB.

All startup wiring lives here so __main__.py stays clean.
"""
from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

import yaml

from cococat.core.agent import Agent, AgentRole

if TYPE_CHECKING:
    from cococat.db import Database

logger = logging.getLogger("cococat.bootstrap")


def _seed_default_residents(config_dir: str) -> None:
    """Create default resident configs if they don't exist."""
    import yaml

    coco_path = os.path.join(config_dir, "coco.yaml")
    if not os.path.exists(coco_path):
        with open(coco_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "id": "coco",
                "name": "Coco",
                "role": "resident",
                "page": "/chat",
                "model": "deepseek-chat",
                "skills": [],
                "cron": [],
            }, f, allow_unicode=True)

    kb_path = os.path.join(config_dir, "kb-agent.yaml")
    if not os.path.exists(kb_path):
        with open(kb_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "id": "kb-agent",
                "name": "知识库管理员",
                "role": "resident",
                "page": "/knowledge",
                "model": "deepseek-chat",
                "skills": ["knowledge-ingestion"],
                "cron": [
                    {"name": "lint", "schedule": "@daily"},
                    {"name": "dedup", "schedule": "@weekly"},
                    {"name": "overview", "schedule": "@weekly"},
                ],
            }, f, allow_unicode=True)


def _load_residents(ctx, factory, sub_executor, dag_store) -> None:
    """Load resident agents from config/residents/*.yaml and seed DB."""
    import yaml
    import glob as glob_mod
    from cococat.core.tools import create_resident_tools

    pool = ctx.pool
    db = ctx.db

    config_dir = "config/residents"
    if not os.path.isdir(config_dir):
        os.makedirs(config_dir, exist_ok=True)
        _seed_default_residents(config_dir)

    for config_path in sorted(glob_mod.glob(os.path.join(config_dir, "*.yaml"))):
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        except Exception:
            logger.exception("Failed to load resident config: %s", config_path)
            continue

        agent_id = cfg.get("id", "")
        name = cfg.get("name", agent_id)
        model = cfg.get("model", "deepseek-chat")
        is_kb = (agent_id == "kb-agent")

        provider = factory.create_sync(model)
        if not provider:
            logger.warning("No provider for resident %s, using stub", agent_id)
            class StubLLM:
                async def chat(self, messages, tools=None, **kwargs):
                    return type('obj', (object,), {'content': f'[No provider for {model}]', 'tool_calls': None})()
            provider = StubLLM()

        tools = create_resident_tools(
            sub_agent_executor=sub_executor.dispatch,
            dag_store=dag_store,
            is_kb_agent=is_kb,
        )

        agent = Agent(
            id=agent_id,
            name=name,
            role=AgentRole.RESIDENT,
            llm=provider,
            tools=tools,
            agent_dir=f"agents/{agent_id}",
        )
        pool.add_agent(agent)

        # Ensure DB has the agent record
        existing = db._conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not existing:
            db._conn.execute(
                "INSERT INTO agents (id, name, role, model, status) VALUES (?, ?, ?, ?, 'running')",
                (agent_id, name, "resident", model),
            )
            db._conn.commit()

        logger.info("Resident loaded: %s (%s) → %s", name, agent_id, model)


def load_agents(app, args) -> None:
    """Create providers, sandbox, tools, and load running agents into the pool."""
    ctx = app.state.ctx
    db: Database = ctx.db
    pool = ctx.pool

    # ── Providers ──
    from cococat.providers.credentials import CredentialManager
    from cococat.providers.factory import ProviderFactory

    creds = CredentialManager(args.auth)
    factory = ProviderFactory(credential_manager=creds)
    ctx.creds = creds
    ctx.provider_factory = factory

    # ── DAG store ──
    from cococat.core.dag_store import SqliteDagStore, FileDagStore

    dag_store = SqliteDagStore(db) if db is not None else FileDagStore("runs")
    ctx.dag_store = dag_store

    # ── LLM resolver ──
    def _load_worker_default_model() -> str:
        try:
            with open("config/defaults.json", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("worker_model", "deepseek-chat")
        except Exception:
            return "deepseek-chat"

    def get_llm(agent_id: str):
        model = _load_worker_default_model()
        try:
            stored_model = db.agents.get_model(agent_id)
            if stored_model:
                model = stored_model
        except Exception:
            pass
        return factory.create_sync(model)

    # ── Sandbox ──
    from cococat.core.sandbox import SandboxProvider

    sandbox_run = None

    if args.cube_sandbox:
        from cococat.core.sandbox.cubesandbox import CubeSandboxExecutor
        cube = CubeSandboxExecutor(template_id=args.cube_sandbox_template, get_llm=get_llm)
        sandbox_provider = SandboxProvider(executor=cube)
        ctx.sandbox_provider = sandbox_provider
        logger.info("CubeSandbox enabled (template=%s)", args.cube_sandbox_template)
    else:
        from cococat.core.sandbox.local_executor import LocalExecutor
        sandbox_provider = SandboxProvider(executor=LocalExecutor(get_llm=get_llm))
        ctx.sandbox_provider = sandbox_provider

    # ── Sub-agent executor ──
    from cococat.core.sub_agent import SubAgentExecutor

    sub_executor = SubAgentExecutor(bus=ctx.bus, pool=pool, sandbox_provider=sandbox_provider)
    ctx.sub_executor = sub_executor

    # ── Tools ──
    from cococat.core.tools import create_core_tools

    tools = create_core_tools(
        sub_agent_executor=sub_executor.dispatch,
        dag_store=dag_store,
        sandbox_run=sandbox_run,
    )

    # ── Load agents ──
    # Load resident agents from config first, then DB workers
    _load_residents(ctx, factory, sub_executor, dag_store)

    rows = db.agents.list_running()
    for r in rows:
        role_str = r["role"]
        try:
            role = AgentRole(role_str)
        except ValueError:
            role_map = {
                "main": AgentRole.RESIDENT,
                "sub": AgentRole.WORKER,
                "worker": AgentRole.WORKER,
                "leader": AgentRole.RESIDENT,
                "employee": AgentRole.WORKER,
            }
            role = role_map.get(role_str)
            if not role:
                logger.warning("Skipping agent %s with unknown role '%s'", r["name"], role_str)
                continue

        # Skip resident agents — they are loaded via _load_residents
        if role == AgentRole.RESIDENT:
            continue

        model = r["model"]
        provider = factory.create_sync(model)
        if not provider:
            logger.warning("No provider for agent %s (model=%s), using stub", r["name"], model)
            class StubLLM:
                async def chat(self, messages, tools=None, **kwargs):
                    return type('obj', (object,), {'content': f"[No provider for model '{model}']", 'tool_calls': None})()
            provider = StubLLM()

        worker_tools = create_core_tools(
            sub_agent_executor=sub_executor.dispatch,
            dag_store=dag_store,
        )

        agent = Agent(
            id=r["id"],
            name=r["name"],
            role=role,
            llm=provider,
            tools=worker_tools,
            agent_dir=f"agents/{r['id']}",
        )
        pool.add_agent(agent)
        logger.info("Worker loaded: %s (%s) → %s", r["name"], r["id"], model)
