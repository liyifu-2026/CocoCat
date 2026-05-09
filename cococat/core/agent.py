"""Agent class — pure Python object, not a subprocess."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from cococat.core.sandbox import PathSandbox, wrap_tool_with_sandbox
from cococat.kb import inject_kb_context
from cococat.prompt import build_system_prompt, load_memory_from_agent_dir
from cococat.skills import load_scene_skills
from cococat.profile import load_agent_system_prompt


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
        agent_dir: str | None = None,
    ):
        self.id = id
        self.name = name
        self.role = role
        self.state = AgentState.IDLE
        self.bound_scene: str | None = None
        self._llm = llm
        self._agent_dir = agent_dir  # For loading memory files

        memory_content, pinned = "", ""
        profile_text = ""
        if agent_dir:
            memory_content, pinned = load_memory_from_agent_dir(agent_dir)
            profile_text = load_agent_system_prompt(agent_dir)

        self._system_prompt = system_prompt or build_system_prompt(
            agent_profile=name + ("\n" + profile_text if profile_text else ""),
            memory_content=memory_content,
            pinned_facts=pinned,
        )
        self._default_system_prompt = self._system_prompt
        self._base_tools = tools or self._default_tools()
        self._scene_tools: list[dict] = []
        self._sandbox: Optional[PathSandbox] = None

    def bind_to_scene(self, scene) -> None:
        """Bind this agent to a scene. Accepts SceneConfig object or scene_id string."""
        if self.role == AgentRole.MAIN:
            raise ValueError("Main AI cannot bind to a scene.")

        # Try to load SceneConfig if string passed
        scene_id = scene
        scene_config = None
        if isinstance(scene, str):
            from cococat.scene.config import load_scene_config
            scene_config = load_scene_config(scene)
            if scene_config is None:
                scene_id = scene
        else:
            scene_config = scene
            scene_id = scene.id

        self.bound_scene = scene_id
        self.state = AgentState.WORKING

        # Apply scene context + skills
        if scene_config:
            self._system_prompt = build_system_prompt(
                agent_profile=self.name,
                scene_context=scene_config.context,
                scene_kbs=scene_config.kbs,
                scene_skills=scene_config.skills,
            )
            # Load scene skills from disk
            self._scene_tools = load_scene_skills(scene_id) if scene_id else []
            # Apply KB sandbox
            self._sandbox = PathSandbox(allowed_kbs=scene_config.kbs)
        else:
            self._sandbox = None

    def unbind(self) -> None:
        """Unbind from scene, return to idle."""
        self.bound_scene = None
        self.state = AgentState.IDLE
        self._scene_tools = []
        self._sandbox = None
        self._system_prompt = self._default_system_prompt

    def get_tools(self) -> list[dict]:
        """Return tools based on current state/scene. Sandbox-wrapped if bound."""
        tools = list(self._base_tools)
        if self._scene_tools:
            tools += self._scene_tools
        if self._sandbox:
            tools = [wrap_tool_with_sandbox(t, self._sandbox) for t in tools]
        return tools

    def set_scene_tools(self, tools: list[dict]) -> None:
        """Set scene-specific tools (called when binding to scene)."""
        self._scene_tools = tools

    async def run(
        self,
        message: str,
        context: Optional[dict] = None,
        on_text: Optional[Callable[[str], Any]] = None,
        on_tool: Optional[Callable[[str, str], Any]] = None,
        max_iterations: int = 20,
    ) -> str:
        """Run the agent on a message using ReAct loop.

        Loop:
        1. Send messages to LLM with tools
        2. If response has tool_calls → execute tools → append results → go to 1
        3. If text-only → return content

        If on_text is provided, it will be called for each streaming text delta.
        If on_tool is provided, it will be called as on_tool(tool_name, status).
        """
        context = context or {}
        tools = self.get_tools()
        llm = self._llm

        messages: list[dict] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": message},
        ]

        final_text: list[str] = []

        for iteration in range(max_iterations):
            # Use non-streaming for tool-use loop (simpler)
            resp = await llm.chat(
                messages=messages,
                tools=tools if tools else None,
                **context,
            )

            content = resp.get("content", "") if isinstance(resp, dict) else str(resp)
            tool_calls = resp.get("tool_calls") if isinstance(resp, dict) else None

            if tool_calls:
                # Append assistant message with tool calls
                assistant_msg: dict = {"role": "assistant", "content": content}
                assistant_msg["tool_calls"] = [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in tool_calls
                ]
                messages.append(assistant_msg)

                # Execute each tool
                for tc in tool_calls:
                    if on_tool:
                        await on_tool(tc["name"], "start")
                    try:
                        import json
                        params = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
                        # Execute tool
                        tool = next((t for t in tools if t["name"] == tc["name"]), None)
                        if tool:
                            result = tool["execute"](params, {})
                            if callable(getattr(result, "__await__", None)):
                                result = await result
                            result_str = str(result)
                        else:
                            result_str = f"Unknown tool: {tc['name']}"
                    except Exception as e:
                        result_str = f"Tool error: {e}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_str,
                    })
                    if on_tool:
                        await on_tool(tc["name"], "done")
            else:
                # Text response — done
                if content:
                    final_text.append(content)
                break
        else:
            final_text.append("[ReAct loop exceeded max iterations]")

        return "".join(final_text)

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
