"""SceneManager — manages SceneRuntime lifecycle and agent assignment."""
from __future__ import annotations

import logging
from enum import Enum
from threading import Lock

from scene_config import SceneConfig, load_scene_config
from agent_handle import AgentHandle

logger = logging.getLogger("cococat.scene_manager")


class SceneState(Enum):
    IDLE = "idle"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"


class SceneRuntime:
    """Runtime instance of a scene with lifecycle management."""

    def __init__(self, config: SceneConfig):
        self.config = config
        self.state = SceneState.IDLE
        self.agent_handle: AgentHandle | None = None
        self.channels: list = []

    @property
    def scene_id(self) -> str:
        return self.config.scene_id

    @property
    def agent_id(self) -> str | None:
        return self.agent_handle.agent_id if self.agent_handle else None

    def assign_agent(self, agent_id: str) -> bool:
        """Assign an agent to this scene. Returns True on success."""
        if self.state not in (SceneState.IDLE, SceneState.ACTIVE):
            logger.warning(f"Cannot assign: scene {self.scene_id} is {self.state.value}")
            return False
        self.state = SceneState.ACTIVATING
        self.agent_handle = AgentHandle(agent_id)
        self.agent_handle.assign_to_scene(self.scene_id, self.config.context)
        self.state = SceneState.ACTIVE
        logger.info(f"Scene {self.scene_id} activated with agent {agent_id}")
        return True

    def unassign_agent(self) -> bool:
        """Unassign the current agent. Returns True on success."""
        if self.state != SceneState.ACTIVE:
            logger.warning(f"Cannot unassign: scene {self.scene_id} is {self.state.value}")
            return False
        self.state = SceneState.DEACTIVATING
        for ch in self.channels:
            try:
                ch.stop()
            except Exception as e:
                logger.warning(f"Error stopping channel: {e}")
        self.channels.clear()
        if self.agent_handle:
            self.agent_handle.release()
            self.agent_handle = None
        self.state = SceneState.IDLE
        logger.info(f"Scene {self.scene_id} deactivated")
        return True


class SceneManager:
    """Singleton — manages all scene runtimes."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._runtimes = {}
        return cls._instance

    def get_or_create(self, scene_id: str) -> SceneRuntime | None:
        """Get existing runtime or create from config. Returns None if scene unknown."""
        if scene_id in self._runtimes:
            return self._runtimes[scene_id]
        config = load_scene_config(scene_id)
        if config is None:
            return None
        runtime = SceneRuntime(config)
        self._runtimes[scene_id] = runtime
        return runtime

    def get_runtime(self, scene_id: str) -> SceneRuntime | None:
        return self._runtimes.get(scene_id)

    def assign_agent(self, scene_id: str, agent_id: str) -> bool:
        runtime = self.get_or_create(scene_id)
        if runtime is None:
            logger.error(f"Scene {scene_id} not found")
            return False
        return runtime.assign_agent(agent_id)

    def unassign_agent(self, scene_id: str) -> bool:
        runtime = self.get_runtime(scene_id)
        if runtime is None:
            return False
        return runtime.unassign_agent()

    def is_agent_busy(self, agent_id: str) -> bool:
        """Check if an agent is already assigned to any active scene."""
        for rt in self._runtimes.values():
            if rt.agent_handle and rt.agent_handle.agent_id == agent_id and rt.state == SceneState.ACTIVE:
                return True
        return False

    def get_free_agent(self, roster: list[str]) -> str | None:
        """Return the first agent in roster that is not busy in another scene."""
        for agent_id in roster:
            if not self.is_agent_busy(agent_id):
                return agent_id
        return None

    def list_active(self) -> list[str]:
        return [s for s, r in self._runtimes.items() if r.state == SceneState.ACTIVE]

    def list_idle(self) -> list[str]:
        return [s for s, r in self._runtimes.items() if r.state == SceneState.IDLE]
