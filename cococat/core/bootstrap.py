"""Agent bootstrap — wires providers, sandbox, tools, and loads modes.
"""
from __future__ import annotations

import logging
import os
import shutil

import yaml

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


def _setup_executor(ctx, factory, args):
    from cococat.core.sandbox import ExecutorProvider

    def get_llm(agent_id: str):
        model = ctx.config_store.get_default("worker_model") or "deepseek-chat"

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


# ── Cron bootstrap ─────────────────────────────────────────

def _bootstrap_cron_yaml(cron_dir: str) -> None:
    yaml_path = os.path.join(os.getcwd(), "config", "cron.yaml")
    if not os.path.exists(yaml_path):
        logger.info("No config/cron.yaml found, skipping cron bootstrap")
        return

    os.makedirs(cron_dir, exist_ok=True)
    try:
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception:
        logger.exception("Failed to load config/cron.yaml")
        return

    tasks = config.get("tasks", []) if config else []
    for entry in tasks:
        import json as _json
        name = entry.get("name", "task")
        filename = f"cron-{name}.json"
        filepath = os.path.join(cron_dir, filename)
        if os.path.exists(filepath):
            continue
        job = {
            "id": f"cron-{name}",
            "name": name,
            "schedule": entry.get("schedule", "@daily"),
            "task": entry.get("task", f"Run {name}"),
            "mode": entry.get("mode", "default"),
            "scene_scope": entry.get("scene_scope", ""),
            "at_time": entry.get("at_time", ""),
            "status": "active",
            "last_run": 0,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            _json.dump(job, f, indent=2)
        logger.info("Seeded cron job: %s (%s)", filename, job["schedule"])


# ── Main entry ─────────────────────────────────────────────

def load_agents(app, args) -> None:
    ctx = app.state.ctx

    agents_dir = str(ctx.config_store.agents_dir)
    if os.path.isdir(agents_dir):
        for name in os.listdir(agents_dir):
            if name.startswith("sub-"):
                path = os.path.join(agents_dir, name)
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    logger.debug("Cleaned up stale sub-agent dir: %s", name)

    _setup_providers(ctx, args.auth)
    _setup_executor(ctx, ctx.provider_factory, args)

    from cococat.core.sub_agent import SubAgentExecutor
    ctx.sub_executor = SubAgentExecutor(bus=ctx.bus, sandbox_provider=ctx.sandbox_provider)

    from cococat.core.modes import list_modes
    modes = list_modes()
    print(f"Loaded {len(modes)} modes: {[m.id for m in modes]}")

    _bootstrap_cron_yaml(str(ctx.config_store.cron_dir))

    from cococat.core.cron_tasks import register_compile_handlers, bootstrap_system_cron_tasks
    register_compile_handlers()
    bootstrap_system_cron_tasks(str(ctx.config_store.cron_dir))
