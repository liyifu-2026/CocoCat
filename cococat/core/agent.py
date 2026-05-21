"""Agent class — pure Python object, not a subprocess."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from cococat.core.agent_builder import build_system_prompt, load_memory_from_agent_dir
from cococat.core.agent_builder import resolve_skills, skills_to_prompt, skills_to_tools
from cococat.core.agent_builder import load_agent_system_prompt, get_agent_skills
from cococat.core.session import Session, load_session, save_session_pair
from cococat.core.tool_executor import make_assistant_msg, execute_tool_calls
from cococat.providers.base import ToolCallRequest
from cococat.core.types import ToolContext


@dataclass(frozen=True)
class AgentConfig:
    id: str
    name: str
    role: str
    system_prompt: str
    tools: list = field(default_factory=list)
    agent_dir: str = ""


def load_agent_config(
    agent_dir: str,
    *,
    base_tools: list | None = None,
    scene_config = None,
    is_kb_agent: bool = False,
) -> AgentConfig:
    name = "agent"
    profile_text = ""
    memory_content, pinned, compiled = "", "", ""

    if agent_dir and os.path.isdir(agent_dir):
        profile_text = load_agent_system_prompt(agent_dir)
        memory_content, pinned, compiled = load_memory_from_agent_dir(agent_dir)
        skill_names = get_agent_skills(agent_dir)
        profile_path = os.path.join(agent_dir, "profile.yaml")
        if os.path.exists(profile_path):
            import yaml
            try:
                with open(profile_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict) and data.get("name"):
                    name = data["name"]
            except Exception:
                pass
    else:
        skill_names = []

    agent_skills = resolve_skills(skill_names)

    if scene_config and hasattr(scene_config, 'skills') and scene_config.skills:
        all_names = list(dict.fromkeys(skill_names + scene_config.skills))
        merged_skills = resolve_skills(all_names)
    else:
        merged_skills = agent_skills

    skill_tools = skills_to_tools(merged_skills)
    skill_prompt = skills_to_prompt(merged_skills)

    tools = list(base_tools or [])
    tools += skill_tools

    system_prompt = build_system_prompt(
        mode_id="kb-admin" if is_kb_agent else "default",
        profile_text=profile_text,
        memory_content=memory_content,
        pinned_facts=pinned,
        compiled_content=compiled,
        scene_context=scene_config.context if scene_config else "",
        scene_kbs=scene_config.kbs if scene_config else [],
        scene_skills=skill_prompt,
        tools=tools,
    )

    return AgentConfig(
        id=os.path.basename(agent_dir.rstrip("/")) if agent_dir else "agent",
        name=name,
        role="worker",
        system_prompt=system_prompt,
        tools=tools,
        agent_dir=agent_dir or f"agents/{name}",
    )


def _resolve_session_path(agent_dir: str, session_id: str) -> str:
    agent_dir = agent_dir or "."
    if session_id:
        sessions_dir = os.path.join(agent_dir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        return os.path.join(sessions_dir, f"{session_id}.jsonl")
    os.makedirs(agent_dir, exist_ok=True)
    return os.path.join(agent_dir, "session.jsonl")


async def _invoke_llm(
    llm: Any,
    messages: list[dict],
    tools: list | None,
    *,
    on_text: Optional[Callable[[str], Any]] = None,
    on_reasoning: Optional[Callable[[str], Any]] = None,
):
    if hasattr(llm, "chat_stream"):
        collected_content: list[str] = []
        collected_tool_calls: list[dict] = []
        collected_reasoning: list[str] = []

        async for event in llm.chat_stream(messages=messages, tools=tools):
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
        return content, tool_calls, reasoning

    resp = await llm.chat(messages=messages, tools=tools)
    content = resp.content or ""
    tool_calls = resp.tool_calls or None
    reasoning = resp.reasoning_content or None
    return content, tool_calls, reasoning


async def run_agent(
    config: AgentConfig,
    llm: Any,
    message: str,
    *,
    session: Session | None = None,
    session_id: str | None = None,
    on_text: Optional[Callable[[str], Any]] = None,
    on_tool: Optional[Callable[[str, str, dict], Any]] = None,
    on_reasoning: Optional[Callable[[str], Any]] = None,
    max_iterations: int = 0,
) -> str:
    context = ToolContext()
    context.agent_id = config.id
    context.agent_dir = config.agent_dir
    context.role = config.role
    context.bound_scene = None

    tools = config.tools
    sid = session_id or ""

    messages: list[dict] = [{"role": "system", "content": config.system_prompt}]

    if session is not None:
        history = await session.sanitized_read()
    else:
        session_path = _resolve_session_path(config.agent_dir, sid)
        history = load_session(session_path)
    messages.extend(history)

    messages.append({"role": "user", "content": message})

    final_text: list[str] = []

    if max_iterations <= 0:
        max_iterations = int(os.environ.get("COCOCAT_MAX_ITERATIONS", "30"))

    for iteration in range(max_iterations):
        is_first = iteration == 0
        content, tool_calls, reasoning = await _invoke_llm(
            llm, messages, tools,
            on_text=on_text if is_first else None,
            on_reasoning=on_reasoning if is_first else None,
        )

        if tool_calls:
            if content:
                final_text.append(content)
            messages.append(make_assistant_msg(content, tool_calls, reasoning))
            await execute_tool_calls(tool_calls, messages, tools, context, on_tool)
        else:
            if content:
                final_text.append(content)
            break

        from cococat.memory.summarize import compress_session
        summary_dir = os.path.join(config.agent_dir, "memory", "summaries") if config.agent_dir else "memory/summaries"
        messages = await compress_session(messages, sid, summary_dir=summary_dir, last_activity=time.time())
    else:
        final_text.append("[ReAct loop exceeded max iterations]")

    result = "\n\n".join(filter(None, final_text))

    try:
        if session is not None:
            await session.append_pair(message, result)
        else:
            session_path = _resolve_session_path(config.agent_dir, sid)
            save_session_pair(session_path, message, result)
    except Exception:
        pass

    return result


class AgentRole(Enum):
    RESIDENT = "resident"
    WORKER = "worker"


class Agent:
    """Agent executor — takes a pre-built AgentConfig and an LLM, delegates to run_agent."""

    def __init__(self, config: AgentConfig, llm: Any):
        self.config = config
        self.id = config.id
        self.name = config.name
        self.role = AgentRole(config.role)
        self._llm = llm

    async def run(
        self,
        message: str,
        context=None,
        on_text=None,
        on_tool=None,
        on_reasoning=None,
        max_iterations: int = 0,
        session=None,
    ) -> str:
        session_id = None
        if isinstance(context, dict) and "session_id" in context:
            session_id = context["session_id"]
        elif context is not None and hasattr(context, "session_id"):
            session_id = context.session_id

        return await run_agent(
            self.config, self._llm, message,
            session=session, session_id=session_id,
            on_text=on_text, on_tool=on_tool, on_reasoning=on_reasoning,
            max_iterations=max_iterations,
        )

    def get_tools(self):
        return self.config.tools
