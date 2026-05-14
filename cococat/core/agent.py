"""Agent class — pure Python object, not a subprocess."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from cococat.core.sandbox_path import PathSandbox, wrap_tool_with_sandbox
from cococat.kb import inject_kb_context
from cococat.prompt import build_system_prompt, load_memory_from_agent_dir
from cococat.skills import load_scene_skills
from cococat.profile import load_agent_system_prompt
from cococat.core.tools import create_core_tools


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
        self._base_tools = tools or create_core_tools()
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
        on_reasoning: Optional[Callable[[str], Any]] = None,
        max_iterations: int = 20,
    ) -> str:
        """Run the agent on a message using ReAct loop.

        Loop:
        1. Send messages to LLM with tools
        2. If response has tool_calls → execute tools → append results → go to 1
        3. If text-only → return content

        If on_text is provided, it will be called for each streaming text delta.
        If on_tool is provided, it will be called as on_tool(tool_name, status).
        If on_reasoning is provided, it will be called for reasoning content.
        """
        context = context or {}
        context.setdefault("agent_id", self.id)
        context.setdefault("agent_dir", self._agent_dir or f"agents/{self.id}")
        context.setdefault("bound_scene", self.bound_scene)
        context.setdefault("role", self.role.value)
        tools = self.get_tools()
        llm = self._llm

        messages: list[dict] = [{"role": "system", "content": self._system_prompt}]

        session_path = self._session_path()
        history = _load_session(session_path)
        messages.extend(history)

        messages.append({"role": "user", "content": message})

        final_text: list[str] = []

        for iteration in range(max_iterations):
            use_stream = iteration == 0 and hasattr(llm, "chat_stream")

            if use_stream:
                collected_content = []
                collected_tool_calls = []

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
                    if event["type"] == "delta":
                        collected_content.append(event["content"])
                    if event["type"] == "tool_call":
                        collected_tool_calls.append({
                            "id": event.get("id", ""),
                            "name": event.get("name", ""),
                            "arguments": event.get("arguments", ""),
                        })

                content = "".join(collected_content)
                tool_calls = collected_tool_calls if collected_tool_calls else None
            else:
                resp = await llm.chat(
                    messages=messages,
                    tools=tools if tools else None,
                    **context,
                )
                content = resp.get("content", "") if isinstance(resp, dict) else str(resp)
                tool_calls = resp.get("tool_calls") if isinstance(resp, dict) else None

            if tool_calls:
                messages.append(self._make_assistant_msg(content, tool_calls))
                await self._execute_tool_calls(tool_calls, messages, tools, context, on_tool)
            else:
                if content:
                    final_text.append(content)
                break
        else:
            final_text.append("[ReAct loop exceeded max iterations]")

        return "".join(final_text)

    @staticmethod
    def _make_assistant_msg(content: str, tool_calls: list[dict]) -> dict:
        """Build the assistant message with tool_calls in OpenAI format."""
        msg: dict = {"role": "assistant", "content": content}
        msg["tool_calls"] = [
            {"id": tc["id"], "type": "function",
             "function": {"name": tc["name"], "arguments": tc["arguments"]}}
            for tc in tool_calls
        ]
        return msg

    @staticmethod
    async def _execute_tool_calls(
        tool_calls: list[dict],
        messages: list[dict],
        tools: list[dict],
        context: dict,
        on_tool: Callable | None = None,
    ) -> None:
        """Execute a batch of tool calls and append results to messages."""
        import json

        for tc in tool_calls:
            if on_tool:
                await on_tool(tc["name"], "start")
            try:
                params = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
                tool = next((t for t in tools if t["name"] == tc["name"]), None)
                if tool:
                    result = tool["execute"](params, context)
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

    def _session_path(self) -> str:
        agent_dir = self._agent_dir or f"agents/{self.id}"
        os.makedirs(agent_dir, exist_ok=True)
        return os.path.join(agent_dir, "session.jsonl")


def _load_session(path: str, max_lines: int = 30) -> list[dict]:
    if not os.path.exists(path):
        return []
    messages = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("role") in ("user", "assistant"):
                        messages.append({"role": msg["role"], "content": msg.get("content", "")})
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return messages[-max_lines:]


def _save_session_pair(path: str, user_msg: str, assistant_reply: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"role": "user", "content": user_msg}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"role": "assistant", "content": assistant_reply}, ensure_ascii=False) + "\n")
