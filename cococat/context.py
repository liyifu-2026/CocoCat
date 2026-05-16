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
    from cococat.core.dag_store import DagStore
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
