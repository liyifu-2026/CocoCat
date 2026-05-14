"""FastAPI application context — typed dependency injection via Depends."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cococat.db import Database
    from cococat.core.event_bus import EventBus
    from cococat.core.agent_pool import AgentPool
    from cococat.routes.ws import WsManager
    from cococat.core.sub_agent import SubAgentExecutor


@dataclass
class AppContext:
    db: Any = None          # Database
    bus: Any = None         # EventBus
    pool: Any = None        # AgentPool
    ws_manager: Any = None  # WsManager

    sandbox_provider: Any = None   # SandboxProvider
    sub_executor: Any = None       # SubAgentExecutor | None
    creds: Any = None              # CredentialManager | None
