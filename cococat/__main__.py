"""CocoCat v2 server entry point.

Usage:
    python -m cococat serve          # Start server on default port
    python -m cococat serve --port 8000 --db /path/to/cococat.db
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import uvicorn

from cococat.app import create_app
from cococat.core.agent import Agent, AgentRole
from cococat.db import Database

logger = logging.getLogger("cococat")


def main():
    parser = argparse.ArgumentParser(description="CocoCat v2 server")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    parser.add_argument("--db", type=str, default="cococat.db", help="SQLite database path")
    parser.add_argument("--auth", type=str, default="config/auth.json", help="Auth config path")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--log-level", type=str, default="info", help="Log level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = create_app(args.db)

    # Populate agent pool from DB
    _load_agents_from_db(app, args)

    logger.info("Starting CocoCat v2 on http://%s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


def _load_agents_from_db(app, args) -> None:
    """Load agents from DB into the AgentPool."""
    ctx = app.state.ctx
    db = ctx.db
    pool = ctx.pool

    rows = db.execute("SELECT id, name, role, model FROM agents WHERE status = 'running'")

    from cococat.providers.credentials import CredentialManager
    from cococat.providers.factory import ProviderFactory
    from cococat.core.sandbox import SandboxProvider
    from cococat.core.sub_agent import SubAgentExecutor
    from cococat.core.tools import create_core_tools

    creds = CredentialManager(args.auth)
    factory = ProviderFactory(credential_manager=creds)

    sandbox_provider = SandboxProvider()
    ctx.sandbox_provider = sandbox_provider
    ctx.creds = creds

    sub_executor = SubAgentExecutor(
        bus=ctx.bus,
        pool=pool,
        sandbox_provider=sandbox_provider,
    )
    ctx.sub_executor = sub_executor

    tools = create_core_tools(
        sub_agent_executor=sub_executor.dispatch,
    )

    for r in rows:
        role_str = r[2]
        try:
            role = AgentRole(role_str)
        except ValueError:
            role_map = {"worker": AgentRole.SUB, "leader": AgentRole.MAIN, "employee": AgentRole.SUB}
            role = role_map.get(role_str)
            if not role:
                logger.warning("Skipping agent %s with unknown role '%s'", r[1], role_str)
                continue

        provider = factory.create_sync(r[3])
        if not provider:
            logger.warning("No provider for agent %s (model=%s), using stub", r[1], r[3])

            class StubLLM:
                async def chat(self, messages, tools=None, **kwargs):
                    return {"content": f"[No provider for model '{r[3]}'] Please configure API key."}

            provider = StubLLM()

        agent = Agent(
            id=r[0],
            name=r[1],
            role=role,
            llm=provider,
            tools=tools,
            agent_dir=f"agents/{r[0]}",
        )
        pool.add_agent(agent)
        logger.info("Agent loaded: %s (%s) → %s", r[1], r[0], r[3])


if __name__ == "__main__":
    main()
