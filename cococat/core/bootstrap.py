"""Agent bootstrap — wires providers, sandbox, tools, and loads agents from DB.

Each service has its own factory function.  load_agents() orchestrates them in order.
"""
from __future__ import annotations

import logging
import os
import asyncio
import shutil

import yaml

from cococat.core.agent import Agent, AgentRole

logger = logging.getLogger("cococat.bootstrap")


# ── Service factories ──────────────────────────────────────

def _setup_providers(ctx, auth_path: str):
    from cococat.providers.credentials import CredentialManager
    from cococat.providers.factory import ProviderFactory

    creds = CredentialManager(auth_path, config_store=ctx.config_store)
    factory = ProviderFactory(credential_manager=creds)
    ctx.creds = creds
    ctx.provider_factory = factory
    return factory


def _setup_dag_store(ctx):
    from cococat.dag.store import SqliteDagStore, FileDagStore

    db = ctx.db
    dag_store = SqliteDagStore(db) if db is not None else FileDagStore(str(ctx.config_store.runs_dir))
    ctx.dag_store = dag_store
    return dag_store


def _setup_sandbox(ctx, factory, args):
    from cococat.core.sandbox import ExecutorProvider

    db = ctx.db

    def get_llm(agent_id: str):
        model = ctx.config_store.get_default("worker_model") or "deepseek-chat"
        try:
            stored_model = db.agents.get_model(agent_id)
            if stored_model:
                model = stored_model
        except Exception:
            pass

        # Use per-user credentials when available
        if ctx.user_id:
            from cococat.config_store import ConfigStore
            from cococat.providers.credentials import CredentialManager
            from cococat.providers.factory import ProviderFactory
            user_creds = CredentialManager(config_store=ConfigStore(user_id=ctx.user_id))
            user_factory = ProviderFactory(credential_manager=user_creds)
            provider = user_factory.create_sync(model)
            if provider:
                return provider

        return factory.create_sync(model)

    if args.cube_sandbox:
        from cococat.core.sandbox.cubesandbox import CubeSandboxExecutor
        executor = CubeSandboxExecutor(template_id=args.cube_sandbox_template, get_llm=get_llm)
        sandbox_provider = ExecutorProvider(executor=executor)
        logger.info("CubeSandbox enabled (template=%s)", args.cube_sandbox_template)
    else:
        from cococat.core.sandbox.local_executor import InProcessExecutor
        from cococat.core.tools import resolve_tavily_key
        tavily_key = resolve_tavily_key(ctx.config_store)
        sandbox_provider = ExecutorProvider(executor=InProcessExecutor(get_llm=get_llm, tavily_api_key=tavily_key))

    ctx.sandbox_provider = sandbox_provider
    return sandbox_provider


def _setup_sub_executor(ctx, sandbox_provider):
    from cococat.core.sub_agent import SubAgentExecutor

    sub_executor = SubAgentExecutor(
        bus=ctx.bus, pool=ctx.pool, sandbox_provider=sandbox_provider,
    )
    ctx.sub_executor = sub_executor
    return sub_executor


def _setup_config_store(ctx):
    from cococat.config_store import ConfigStore
    ctx.config_store = ConfigStore()
    return ctx.config_store


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
    from cococat.core.tools import ToolCatalog, resolve_tavily_key

    pool = ctx.pool
    db = ctx.db
    config_dir = str(ctx.config_store.residents_dir)
    tavily_key = resolve_tavily_key(ctx.config_store)
    catalog = ToolCatalog(
        sub_agent_executor=sub_executor.dispatch,
        dag_store=dag_store,
        tavily_api_key=tavily_key,
    )

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
            profile_dir = str(ctx.config_store.agents_dir / agent_id)
            os.makedirs(profile_dir, exist_ok=True)
            profile_path = os.path.join(profile_dir, "profile.yaml")
            if not os.path.exists(profile_path):
                with open(profile_path, "w", encoding="utf-8") as f:
                    yaml.dump({"skills": skills}, f, default_flow_style=False)
                logger.info("Created %s with skills: %s", profile_path, skills)

        tools = catalog.resident(kb_agent=is_kb)

        agent = Agent(
            id=agent_id, name=name, role=AgentRole.RESIDENT,
            llm=provider, tools=tools, agent_dir=str(ctx.config_store.agents_dir / agent_id),
        )
        agent.page = cfg.get("page", "")
        pool.add_agent(agent)

        cron_entries = cfg.get("cron", [])
        if cron_entries:
            _seed_cron_jobs(agent_id, cron_entries, ctx.config_store)

        existing = db._conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not existing:
            db._conn.execute(
                "INSERT INTO agents (id, name, role, model, status) VALUES (?, ?, ?, ?, 'running')",
                (agent_id, name, "resident", model),
            )
            db._conn.commit()

        logger.info("Resident loaded: %s (%s) → %s", name, agent_id, model)


def _load_workers(ctx, factory, sub_executor, dag_store) -> None:
    from cococat.core.tools import ToolCatalog, resolve_tavily_key

    pool = ctx.pool
    db = ctx.db
    tavily_key = resolve_tavily_key(ctx.config_store)
    catalog = ToolCatalog(
        sub_agent_executor=sub_executor.dispatch,
        dag_store=dag_store,
        tavily_api_key=tavily_key,
    )

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

        worker_tools = catalog.worker()

        agent = Agent(
            id=r["id"], name=r["name"], role=role,
            llm=provider, tools=worker_tools,
            agent_dir=str(ctx.config_store.agents_dir / r['id']),
        )
        pool.add_agent(agent)
        logger.info("Worker loaded: %s (%s) → %s", r["name"], r["id"], model)


def _seed_cron_jobs(agent_id: str, entries: list[dict], config_store) -> None:
    import json as _json
    cron_dir = str(config_store.cron_dir)
    os.makedirs(cron_dir, exist_ok=True)
    for entry in entries:
        name = entry.get("name", "task")
        schedule = entry.get("schedule", "@daily")
        filename = f"{agent_id}-{name}.json"
        filepath = os.path.join(cron_dir, filename)
        if not os.path.exists(filepath):
            at_time = entry.get("at_time", "")
            job = {
                "id": f"{agent_id}-{name}",
                "agent_id": agent_id,
                "name": name,
                "schedule": schedule,
                "task": entry.get("task", f"Run {name} maintenance"),
                "at_time": at_time,
                "status": "active",
                "last_run": 0,
                "created_at": __import__("datetime").datetime.now().isoformat(),
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
                    {"name": "lint", "schedule": "@daily", "task": "Call run_lint to check all knowledge bases for orphan pages, broken wikilinks, and missing frontmatter"},
                    {"name": "dedup", "schedule": "@weekly", "task": "Call run_dedup to detect and merge duplicate content across all knowledge base wiki pages"},
                    {"name": "overview", "schedule": "@weekly", "task": "Call gen_overview to generate a fresh global summary of all knowledge base content into overview.md"},
                ],
            }, f, allow_unicode=True)


# ── Main entry ─────────────────────────────────────────────

def load_agents(app, args) -> None:
    """Orchestrate startup: create services, load agents into pool."""
    ctx = app.state.ctx

    # ── Migration: legacy config → per-user structure ──
    _migrate_legacy_config(ctx)

    # Clean up stale sub-agent session directories from previous runs
    agents_dir = str(ctx.config_store.agents_dir)
    if os.path.isdir(agents_dir):
        for name in os.listdir(agents_dir):
            if name.startswith("sub-"):
                path = os.path.join(agents_dir, name)
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    logger.debug("Cleaned up stale sub-agent dir: %s", name)

    factory = _setup_providers(ctx, args.auth)
    dag_store = _setup_dag_store(ctx)
    sandbox_provider = _setup_sandbox(ctx, factory, args)
    sub_executor = _setup_sub_executor(ctx, sandbox_provider)

    _load_residents(ctx, factory, sub_executor, dag_store)
    _load_workers(ctx, factory, sub_executor, dag_store)

    # Register system cron tasks (compile chain + dream poll)
    from cococat.core.cron_tasks import register_compile_handlers, bootstrap_system_cron_tasks
    register_compile_handlers()
    bootstrap_system_cron_tasks(str(ctx.config_store.cron_dir))


def _migrate_legacy_config(ctx) -> None:
    """One-time migration: copy legacy global config → config/users/admin/."""
    import shutil as _shutil
    admin_config = "config/users/admin"
    admin_agents = "agents/admin"

    # Migrate config/auth.json
    if os.path.exists("config/auth.json") and not os.path.exists(f"{admin_config}/auth.json"):
        os.makedirs(admin_config, exist_ok=True)
        _shutil.copy2("config/auth.json", f"{admin_config}/auth.json")
        os.remove("config/auth.json")
        logger.info("Migrated config/auth.json → config/users/admin/auth.json")

    # Migrate agents/ → agents/admin/
    if os.path.isdir("agents") and not os.path.isdir(admin_agents):
        # Only migrate if admin agent dir doesn't exist yet
        has_agents = any(
            not name.startswith("sub-") and not name.startswith("_") and os.path.isdir(os.path.join("agents", name))
            for name in os.listdir("agents")
        )
        if has_agents:
            os.makedirs(admin_agents, exist_ok=True)
            for name in os.listdir("agents"):
                src = os.path.join("agents", name)
                dst = os.path.join(admin_agents, name)
                if name.startswith("sub-") or name.startswith("_"):
                    continue
                if os.path.isdir(src) and not os.path.exists(dst):
                    _shutil.copytree(src, dst)
                    logger.info("Migrated agents/%s → agents/admin/%s", name, name)
