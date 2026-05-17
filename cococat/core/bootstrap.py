"""Agent bootstrap — wires providers, sandbox, tools, and loads agents from DB.

Each service has its own factory function.  load_agents() orchestrates them in order.
"""
from __future__ import annotations

import json
import logging
import os
import asyncio

import yaml

from cococat.core.agent import Agent, AgentRole

logger = logging.getLogger("cococat.bootstrap")


# ── Service factories ──────────────────────────────────────

def _setup_providers(ctx, auth_path: str):
    from cococat.providers.credentials import CredentialManager
    from cococat.providers.factory import ProviderFactory

    creds = CredentialManager(auth_path)
    factory = ProviderFactory(credential_manager=creds)
    ctx.creds = creds
    ctx.provider_factory = factory
    return factory


def _setup_dag_store(ctx):
    from cococat.core.dag_store import SqliteDagStore, FileDagStore

    db = ctx.db
    dag_store = SqliteDagStore(db) if db is not None else FileDagStore("runs")
    ctx.dag_store = dag_store
    return dag_store


def _setup_sandbox(ctx, factory, args):
    from cococat.core.sandbox import SandboxProvider

    db = ctx.db

    def get_llm(agent_id: str):
        model = _load_worker_default_model()
        try:
            stored_model = db.agents.get_model(agent_id)
            if stored_model:
                model = stored_model
        except Exception:
            pass
        return factory.create_sync(model)

    if args.cube_sandbox:
        from cococat.core.sandbox.cubesandbox import CubeSandboxExecutor
        executor = CubeSandboxExecutor(template_id=args.cube_sandbox_template, get_llm=get_llm)
        sandbox_provider = SandboxProvider(executor=executor)
        logger.info("CubeSandbox enabled (template=%s)", args.cube_sandbox_template)
    else:
        from cococat.core.sandbox.local_executor import LocalExecutor
        sandbox_provider = SandboxProvider(executor=LocalExecutor(get_llm=get_llm))

    ctx.sandbox_provider = sandbox_provider
    return sandbox_provider


def _setup_sub_executor(ctx, sandbox_provider):
    from cococat.core.sub_agent import SubAgentExecutor

    sub_executor = SubAgentExecutor(
        bus=ctx.bus, pool=ctx.pool, sandbox_provider=sandbox_provider,
    )
    ctx.sub_executor = sub_executor
    return sub_executor


# ── Agent loading ──────────────────────────────────────────

def _create_stub_llm(model: str):
    class StubLLM:
        async def chat(self, messages, tools=None, **kwargs):
            return type('obj', (object,), {
                'content': f"[No provider for model '{model}']",
                'tool_calls': None,
            })()
    return StubLLM()


def _load_residents(ctx, factory, sub_executor, dag_store) -> None:
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
            try:
                provider = asyncio.run(factory.create(model))
            except Exception:
                pass
        provider = provider or _create_stub_llm(model)

        skills = cfg.get("skills", [])
        if skills:
            profile_dir = f"agents/{agent_id}"
            os.makedirs(profile_dir, exist_ok=True)
            profile_path = os.path.join(profile_dir, "profile.yaml")
            if not os.path.exists(profile_path):
                with open(profile_path, "w", encoding="utf-8") as f:
                    yaml.dump({"skills": skills}, f, default_flow_style=False)
                logger.info("Created %s with skills: %s", profile_path, skills)

        tools = create_resident_tools(
            sub_agent_executor=sub_executor.dispatch,
            dag_store=dag_store,
            is_kb_agent=is_kb,
        )

        agent = Agent(
            id=agent_id, name=name, role=AgentRole.RESIDENT,
            llm=provider, tools=tools, agent_dir=f"agents/{agent_id}",
        )
        pool.add_agent(agent)

        cron_entries = cfg.get("cron", [])
        if cron_entries:
            _seed_cron_jobs(agent_id, cron_entries)

        existing = db._conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not existing:
            db._conn.execute(
                "INSERT INTO agents (id, name, role, model, status) VALUES (?, ?, ?, ?, 'running')",
                (agent_id, name, "resident", model),
            )
            db._conn.commit()

        logger.info("Resident loaded: %s (%s) → %s", name, agent_id, model)


def _load_workers(ctx, factory, sub_executor, dag_store) -> None:
    from cococat.core.tools import create_core_tools

    pool = ctx.pool
    db = ctx.db

    for r in db.agents.list_running():
        role = _map_role(r["role"])
        if not role:
            continue
        if role == AgentRole.RESIDENT:
            continue

        model = r["model"]
        provider = factory.create_sync(model)
        if not provider:
            try:
                provider = asyncio.run(factory.create(model))
            except Exception:
                pass
        provider = provider or _create_stub_llm(model)

        worker_tools = create_core_tools(
            sub_agent_executor=sub_executor.dispatch,
            dag_store=dag_store,
        )

        agent = Agent(
            id=r["id"], name=r["name"], role=role,
            llm=provider, tools=worker_tools,
            agent_dir=f"agents/{r['id']}",
        )
        pool.add_agent(agent)
        logger.info("Worker loaded: %s (%s) → %s", r["name"], r["id"], model)


def _seed_cron_jobs(agent_id: str, entries: list[dict]) -> None:
    import json as _json
    cron_dir = os.path.join("runs", "cron")
    os.makedirs(cron_dir, exist_ok=True)
    for entry in entries:
        name = entry.get("name", "task")
        schedule = entry.get("schedule", "@daily")
        filename = f"{agent_id}-{name}.json"
        filepath = os.path.join(cron_dir, filename)
        if not os.path.exists(filepath):
            job = {
                "agent_id": agent_id,
                "name": name,
                "schedule": schedule,
                "task": entry.get("task", f"Run {name} maintenance"),
            }
            with open(filepath, "w", encoding="utf-8") as f:
                _json.dump(job, f, indent=2)
            logger.info("Seeded cron job: %s (%s)", filename, schedule)


# ── Helpers ────────────────────────────────────────────────

def _map_role(role_str: str):
    try:
        return AgentRole(role_str)
    except ValueError:
        role_map = {
            "main": AgentRole.RESIDENT, "sub": AgentRole.WORKER,
            "worker": AgentRole.WORKER, "leader": AgentRole.RESIDENT,
            "employee": AgentRole.WORKER,
        }
        return role_map.get(role_str)


def _load_worker_default_model() -> str:
    try:
        with open("config/defaults.json", encoding="utf-8") as f:
            return json.load(f).get("worker_model", "deepseek-chat")
    except Exception:
        return "deepseek-chat"


def _seed_default_residents(config_dir: str) -> None:
    coco_path = os.path.join(config_dir, "coco.yaml")
    if not os.path.exists(coco_path):
        with open(coco_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "id": "coco", "name": "Coco", "role": "resident",
                "page": "/chat", "model": "deepseek-chat",
                "skills": [], "cron": [],
            }, f, allow_unicode=True)

    kb_path = os.path.join(config_dir, "kb-agent.yaml")
    if not os.path.exists(kb_path):
        with open(kb_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "id": "kb-agent", "name": "知识库管理员", "role": "resident",
                "page": "/knowledge", "model": "deepseek-chat",
                "skills": ["knowledge-ingestion"],
                "cron": [
                    {"name": "lint", "schedule": "@daily"},
                    {"name": "dedup", "schedule": "@weekly"},
                    {"name": "overview", "schedule": "@weekly"},
                ],
            }, f, allow_unicode=True)


# ── Main entry ─────────────────────────────────────────────

def load_agents(app, args) -> None:
    """Orchestrate startup: create services, load agents into pool."""
    ctx = app.state.ctx

    factory = _setup_providers(ctx, args.auth)
    dag_store = _setup_dag_store(ctx)
    sandbox_provider = _setup_sandbox(ctx, factory, args)
    sub_executor = _setup_sub_executor(ctx, sandbox_provider)

    _load_residents(ctx, factory, sub_executor, dag_store)
    _load_workers(ctx, factory, sub_executor, dag_store)
