"""Agent class — pure Python object, not a subprocess."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class AgentState(Enum):
    IDLE = "idle"
    WORKING = "working"


class AgentRole(Enum):
    MAIN = "main"
    SUB = "sub"


@dataclass
class SystemPrompt:
    static_prefix: str
    dynamic_suffix: str


class Agent:
    """An AI agent — Python object, not a subprocess.

    Key properties:
    - Main AI: never binds to a scene. Global tools and KBs.
    - Sub AI: can bind to one scene at a time. When bound, tools are scene-scoped.
    """

    def __init__(
        self,
        id: str,
        name: str,
        role: AgentRole,
        llm: Any,
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
    ):
        self.id = id
        self.name = name
        self.role = role
        self.state = AgentState.IDLE
        self.bound_scene: str | None = None
        self._llm = llm

        self._system_prompt = system_prompt or "You are a helpful AI assistant."
        self._base_tools = tools or self._default_tools()
        self._scene_tools: list[dict] = []

    def bind_to_scene(self, scene_id: str) -> None:
        """Bind this agent to a scene. Main AI cannot bind. Overwrites existing binding."""
        if self.role == AgentRole.MAIN:
            raise ValueError("Main AI cannot bind to a scene.")
        self.bound_scene = scene_id
        self.state = AgentState.WORKING

    def unbind(self) -> None:
        """Unbind from scene, return to idle."""
        self.bound_scene = None
        self.state = AgentState.IDLE
        self._scene_tools = []

    def get_tools(self) -> list[dict]:
        """Return tools based on current state/scene."""
        tools = list(self._base_tools)
        if self._scene_tools:
            tools += self._scene_tools
        return tools

    def set_scene_tools(self, tools: list[dict]) -> None:
        """Set scene-specific tools (called when binding to scene)."""
        self._scene_tools = tools

    async def run(self, message: str, context: dict | None = None) -> str:
        """Run the agent on a message. Creates a short-lived session."""
        context = context or {}
        tools = self.get_tools()

        result = await self._llm.chat(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": message},
            ],
            tools=tools if tools else None,
            **context,
        )
        return result

    async def init(self):
        """One-time setup. Load tools compile system prompt, etc."""
        pass

    @staticmethod
    def _default_tools() -> list[dict]:
        """Minimal default tools for testing. Full tool set defined in tools module."""
        return [
            {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"file_path": "string"},
            },
            {
                "name": "bash",
                "description": "Execute a shell command",
                "parameters": {"command": "string"},
            },
            {
                "name": "sub_agent",
                "description": "Spawn a sub-agent for a task",
                "parameters": {"task": "string", "agent_id": "string"},
            },
        ]
