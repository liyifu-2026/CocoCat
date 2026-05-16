"""Agent bootstrap — wires providers, sandbox, tools, and loads agents from DB.

All startup wiring lives here so __main__.py stays clean.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from cococat.core.agent import Agent, AgentRole

if TYPE_CHECKING:
    from cococat.db import Database

logger = logging.getLogger("cococat.bootstrap")


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
            stored_model = db.get_agent_model(agent_id)
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
    rows = db.list_running_agents()
    for r in rows:
        role_str = r["role"]
        try:
            role = AgentRole(role_str)
        except ValueError:
            role_map = {"worker": AgentRole.SUB, "leader": AgentRole.MAIN, "employee": AgentRole.SUB}
            role = role_map.get(role_str)
            if not role:
                logger.warning("Skipping agent %s with unknown role '%s'", r["name"], role_str)
                continue

        model = r["model"]
        provider = factory.create_sync(model)
        if not provider:
            logger.warning("No provider for agent %s (model=%s), using stub", r["name"], model)

            class StubLLM:
                async def chat(self, messages, tools=None, **kwargs):
                    return {"content": f"[No provider for model '{model}'] Please configure API key."}

            provider = StubLLM()

        agent = Agent(
            id=r["id"],
            name=r["name"],
            role=role,
            llm=provider,
            tools=tools,
            agent_dir=f"agents/{r['id']}",
        )
        pool.add_agent(agent)
        logger.info("Agent loaded: %s (%s) → %s", r["name"], r["id"], model)
