"""Agent class — pure Python object, not a subprocess."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from cococat.core.sandbox_path import PathSandbox, wrap_tool_with_sandbox
from cococat.prompt import build_system_prompt, load_memory_from_agent_dir, KB_AGENT_STATIC_PREFIX
from cococat.skills import resolve_skills, skills_to_prompt, skills_to_tools
from cococat.profile import load_agent_system_prompt
from cococat.core.session import Session, load_session, save_session_pair, maybe_trigger_dream
from cococat.core.tools import create_core_tools
from cococat.core.tool_executor import make_assistant_msg, execute_tool_calls
from cococat.providers.base import ToolCallRequest
from cococat.core.types import ToolContext


class AgentState(Enum):
    IDLE = "idle"
    WORKING = "working"


class AgentRole(Enum):
    RESIDENT = "resident"   # Permanent, page-bound, peer-level
    WORKER = "worker"       # Ephemeral pool, created/destroyed per task


@dataclass
class SystemPrompt:
    static_prefix: str
    dynamic_suffix: str


class Agent:
    """An AI agent — Python object, not a subprocess.

    Key properties:
    - Resident: permanent, page-bound, peer-level. Global tools and KBs.
    - Worker: ephemeral pool, can bind to one scene at a time. Scene-scoped tools when bound.
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
        self.page = ""
        self.state = AgentState.IDLE
        self.bound_scene: str | None = None
        self._llm = llm
        self._agent_dir = agent_dir  # For loading memory files

        memory_content, pinned = "", ""
        profile_text = ""
        self._agent_skill_names: list[str] = []
        if agent_dir:
            memory_content, pinned = load_memory_from_agent_dir(agent_dir)
            profile_text = load_agent_system_prompt(agent_dir)
            from cococat.profile import get_agent_skills
            self._agent_skill_names = get_agent_skills(agent_dir)

        self._base_tools = tools or create_core_tools()
        self._scene_tools: list[dict] = []
        self._sandbox: Optional[PathSandbox] = None

        # Load agent skills from profile
        self._agent_skills = resolve_skills(self._agent_skill_names)
        agent_skills_prompt = skills_to_prompt(self._agent_skills)
        agent_skill_tools = skills_to_tools(self._agent_skills)
        self._base_tools = list(self._base_tools) + agent_skill_tools

        self._system_prompt = system_prompt or build_system_prompt(
            agent_profile=name + ("\n" + profile_text if profile_text else ""),
            memory_content=memory_content,
            pinned_facts=pinned,
            scene_skills=agent_skills_prompt,
            tools=self._base_tools,
            static_prefix=KB_AGENT_STATIC_PREFIX if id == "kb-agent" else None,
        )
        self._default_system_prompt = self._system_prompt

    def bind_to_scene(self, scene) -> None:
        """Bind this agent to a scene. Accepts SceneConfig object or scene_id string."""
        if self.role == AgentRole.RESIDENT:
            raise ValueError("Resident agents cannot bind to a scene (they are page-bound).")

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
            # Merge agent skills + scene skills (union, de-duplicated)
            all_skill_names = list(dict.fromkeys(self._agent_skill_names + scene_config.skills))
            merged_skills = resolve_skills(all_skill_names)
            merged_prompt = skills_to_prompt(merged_skills)
            merged_tools = skills_to_tools(merged_skills)

            self._system_prompt = build_system_prompt(
                agent_profile=self.name,
                scene_context=scene_config.context,
                scene_kbs=scene_config.kbs,
                scene_skills=merged_prompt,
                tools=list(self._base_tools) + merged_tools,
            )
            self._scene_tools = merged_tools
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
        context: ToolContext | None = None,
        on_text: Optional[Callable[[str], Any]] = None,
        on_tool: Optional[Callable[[str, str, dict], Any]] = None,
        on_reasoning: Optional[Callable[[str], Any]] = None,
        max_iterations: int = 20,
        session: Session | None = None,
    ) -> str:
        """Run the agent on a message using ReAct loop.

        Loop:
        1. Send messages to LLM with tools
        2. If response has tool_calls → execute tools → append results → go to 1
        3. If text-only → return content

        If on_text is provided, it will be called for each streaming text delta.
        If on_tool is provided, it will be called as on_tool(name, status, data) with
          data = {tool_call_id, arguments?|result?, elapsed?}.
        If on_reasoning is provided, it will be called for reasoning content.
        """
        context = ToolContext(**(context if isinstance(context, dict) else {})) if context is not None and not isinstance(context, ToolContext) else (context or ToolContext())
        context.agent_id = self.id
        context.agent_dir = self._agent_dir or f"agents/{self.id}"
        context.bound_scene = self.bound_scene
        context.role = self.role.value
        session_id = context.session_id
        tools = self.get_tools()
        llm = self._llm

        messages: list[dict] = [{"role": "system", "content": self._system_prompt}]

        if session is not None:
            history = await session.sanitized_read()
        else:
            session_path = self._session_path(session_id)
            history = load_session(session_path)
        messages.extend(history)

        messages.append({"role": "user", "content": message})

        final_text: list[str] = []

        for iteration in range(max_iterations):
            use_stream = iteration == 0 and hasattr(llm, "chat_stream")
            reasoning = None

            if use_stream:
                collected_content = []
                collected_tool_calls = []
                collected_reasoning = []

                async for event in llm.chat_stream(
                    messages=messages,
                    tools=tools if tools else None,
                ):
                    if event["type"] == "delta" and on_text:
                        r = on_text(event["content"])
                        if callable(getattr(r, "__await__", None)):
                            await r
                    if event["type"] == "reasoning" and on_reasoning:
                        r = on_reasoning(event["content"])
                        if callable(getattr(r, "__await__", None)):
                            await r
                    if event["type"] == "reasoning":
                        collected_reasoning.append(event["content"])
                    if event["type"] == "delta":
                        collected_content.append(event["content"])
                    if event["type"] == "tool_call":
                        collected_tool_calls.append({
                            "id": event.get("id", ""),
                            "name": event.get("name", ""),
                            "arguments": event.get("arguments", ""),
                        })

                content = "".join(collected_content)
                reasoning = "".join(collected_reasoning) if collected_reasoning else None
                tool_calls = [ToolCallRequest(**tc) for tc in collected_tool_calls] if collected_tool_calls else []
            else:
                resp = await llm.chat(
                    messages=messages,
                    tools=tools if tools else None,
                )
                content = resp.content or ""
                tool_calls = resp.tool_calls or None
                reasoning = resp.reasoning_content or None

            if tool_calls:
                final_text.append(content) if content else None
                messages.append(make_assistant_msg(content, tool_calls, reasoning))
                await execute_tool_calls(tool_calls, messages, tools, context, on_tool)
            else:
                if content:
                    final_text.append(content)
                break
        else:
            final_text.append("[ReAct loop exceeded max iterations]")

        result = "\n\n".join(filter(None, final_text))

        # Persist this round to session log
        try:
            if session is not None:
                await session.append_pair(message, result)
            else:
                save_session_pair(session_path, message, result)
        except Exception:
            pass

        # Auto-Dream: extract long-term memory from accumulated conversation
        try:
            dream_path = session.path if session is not None else session_path
            maybe_trigger_dream(dream_path)
        except Exception:
            pass

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
                "parameters": {
                    "type": "object",
                    "properties": {"file_path": {"type": "string", "description": "Path to file"}},
                    "required": ["file_path"],
                },
            },
            {
                "name": "bash",
                "description": "Execute a shell command",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string", "description": "Shell command"}},
                    "required": ["command"],
                },
            },
            {
                "name": "sub_agent",
                "description": "Spawn a sub-agent for a task",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Task description"},
                        "agent_id": {"type": "string", "description": "Agent ID"},
                    },
                    "required": ["task", "agent_id"],
                },
            },
        ]

    def _session_path(self, session_id: str | None = None) -> str:
        agent_dir = self._agent_dir or f"agents/{self.id}"
        os.makedirs(agent_dir, exist_ok=True)
        if session_id:
            sessions_dir = os.path.join(agent_dir, "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            return os.path.join(sessions_dir, f"{session_id}.jsonl")
        return os.path.join(agent_dir, "session.jsonl")
