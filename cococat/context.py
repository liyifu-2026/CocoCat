"""FastAPI application context — typed dependency injection via Depends."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db import Database
    from cococat.core.event_bus import EventBus
    from cococat.core.agent_pool import AgentPool
    from cococat.routes.ws import WsManager
    from cococat.core.sub_agent import SubAgentExecutor
    from cococat.core.sandbox import SandboxProvider
    from cococat.dag.store import DagStore
    from cococat.providers.credentials import CredentialManager
    from cococat.providers.factory import ProviderFactory


@dataclass
class AppContext:
    db: Database = field(default=None)
    bus: EventBus = field(default=None)
    pool: AgentPool = field(default=None)
    ws_manager: WsManager = field(default=None)

    sandbox_provider: SandboxProvider = field(default=None)
    sub_executor: SubAgentExecutor | None = field(default=None)
    creds: CredentialManager | None = field(default=None)
    provider_factory: ProviderFactory | None = field(default=None)
    dag_store: 'DagStore | None' = field(default=None)


# ── Static context reference (module-level singleton) ──────

_ctx: AppContext | None = None


def set_ctx_static(ctx: AppContext) -> None:
    global _ctx
    _ctx = ctx


def get_ctx_static() -> AppContext:
    if _ctx is None:
        raise RuntimeError("AppContext not initialised — call set_ctx_static first")
    return _ctx


# ── Fine-grained FastAPI dependencies ──────────────────────

def get_db(ctx: AppContext = None) -> Database:
    """Declare this route needs the database."""
    return ctx.db if ctx else get_ctx_static().db

def get_pool(ctx: AppContext = None) -> AgentPool:
    return ctx.pool if ctx else get_ctx_static().pool

def get_bus(ctx: AppContext = None) -> EventBus:
    return ctx.bus if ctx else get_ctx_static().bus

def get_dag_store(ctx: AppContext = None):
    return ctx.dag_store if ctx else get_ctx_static().dag_store

def get_sandbox(ctx: AppContext = None):
    return ctx.sandbox_provider if ctx else get_ctx_static().sandbox_provider

def get_sub_executor(ctx: AppContext = None):
    return ctx.sub_executor if ctx else get_ctx_static().sub_executor

def get_ws_manager(ctx: AppContext = None):
    return ctx.ws_manager if ctx else get_ctx_static().ws_manager
