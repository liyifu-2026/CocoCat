"""AgentPool — manages multiple Agent instances."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cococat.core.agent import AgentRole

if TYPE_CHECKING:
    from cococat.core.event_bus import EventBus
    from cococat.core.agent import Agent

logger = logging.getLogger("cococat.agent_pool")


class AgentPool:
    """Manages a pool of Agent instances.

    - Tracks agent states
    - Provides free sub-agent lookup
    """

    def __init__(self, bus: EventBus, max_agents: int = 10):
        self._bus = bus
        self._max_agents = max_agents
        self._agents: dict[str, Agent] = {}

    def add_agent(self, agent: Agent) -> bool:
        """Add an agent to the pool. Returns False if pool is full."""
        if len(self._agents) >= self._max_agents:
            logger.warning("AgentPool full, cannot add %s", agent.id)
            return False
        self._agents[agent.id] = agent
        return True

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_free_sub_agents(self) -> list[Agent]:
        """Return all idle worker agents (backward compat wrapper)."""
        return self.get_free_workers()

    def get_free_workers(self) -> list[Agent]:
        """Return all idle worker agents."""
        return [
            a for a in self._agents.values()
            if a.role == AgentRole.WORKER
        ]

    def get_residents(self) -> list[Agent]:
        """Return all resident agents."""
        return [
            a for a in self._agents.values()
            if a.role == AgentRole.RESIDENT
        ]

    def get_resident(self, agent_id: str) -> Agent | None:
        """Get a resident agent by ID."""
        agent = self._agents.get(agent_id)
        if agent and agent.role == AgentRole.RESIDENT:
            return agent
        return None

    def list_agents(self) -> list[Agent]:
        """List all agents in the pool."""
        return list(self._agents.values())


