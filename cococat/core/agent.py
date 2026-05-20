"""Agent class — pure Python object, not a subprocess."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from cococat.core.agent_builder import build_system_prompt, load_memory_from_agent_dir, KB_AGENT_STATIC_PREFIX
from cococat.core.agent_builder import resolve_skills, skills_to_prompt, skills_to_tools
from cococat.core.agent_builder import load_agent_system_prompt, get_agent_skills
from cococat.core.session import Session, load_session, save_session_pair
from cococat.core.tool_executor import make_assistant_msg, execute_tool_calls
from cococat.providers.base import ToolCallRequest
from cococat.core.types import ToolContext


@dataclass(frozen=True)
class AgentConfig:
    """Agent 的不可变配置——所有构建在创建时一次性完成。"""
    id: str
    name: str
    role: str                     # "resident" | "worker"
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
    """加载 profile / memory / skills → 合并 → 不可变 AgentConfig。"""
    name = "agent"
    profile_text = ""
    memory_content, pinned, compiled = "", "", ""

    if agent_dir and os.path.isdir(agent_dir):
        profile_text = load_agent_system_prompt(agent_dir)
        memory_content, pinned, compiled = load_memory_from_agent_dir(agent_dir)
        skill_names = get_agent_skills(agent_dir)
        # 从 profile.yaml 提取 agent name
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

    agent_profile_str = name + ("\n" + profile_text if profile_text else "")
    system_prompt = build_system_prompt(
        agent_profile=agent_profile_str,
        memory_content=memory_content,
        pinned_facts=pinned,
        compiled_content=compiled,
        scene_context=scene_config.context if scene_config else "",
        scene_kbs=scene_config.kbs if scene_config else [],
        scene_skills=skill_prompt,
        tools=tools,
        static_prefix=KB_AGENT_STATIC_PREFIX if is_kb_agent else None,
    )

    return AgentConfig(
        id=os.path.basename(agent_dir.rstrip("/")) if agent_dir else "agent",
        name=name,
        role="worker",
        system_prompt=system_prompt,
        tools=tools,
        agent_dir=agent_dir,
    )


def _resolve_session_path(agent_dir: str, session_id: str) -> str:
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
    """Invoke LLM (streaming or non-streaming). Returns (content, tool_calls, reasoning)."""
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
    """Execute ReAct loop: history → iterate LLM → execute tools → persist → dream."""
    context = ToolContext()
    context.agent_id = config.id
    context.agent_dir = config.agent_dir or f"agents/{config.id}"  # fallback — callers should pass explicit agent_dir
    context.role = config.role
    context.bound_scene = None

    tools = config.tools

    messages: list[dict] = [{"role": "system", "content": config.system_prompt}]

    if session is not None:
        history = await session.sanitized_read()
    else:
        sid = session_id or ""
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

        # Compress session if token threshold exceeded
        from cococat.memory.summarize import compress_session
        sid = session_id or "default"
        summary_dir = os.path.join(config.agent_dir, "memory", "summaries") if config.agent_dir else "memory/summaries"
        messages = await compress_session(messages, sid, summary_dir=summary_dir,
                                          last_activity=time.time())
    else:
        final_text.append("[ReAct loop exceeded max iterations]")

    result = "\n\n".join(filter(None, final_text))

    try:
        if session is not None:
            await session.append_pair(message, result)
        else:
            sid = session_id or ""
            session_path = _resolve_session_path(config.agent_dir, sid)
            save_session_pair(session_path, message, result)
    except Exception:
        pass

    try:
        pass
    except Exception:
        pass

    return result


class AgentRole(Enum):
    RESIDENT = "resident"   # Permanent, page-bound, peer-level
    WORKER = "worker"       # Ephemeral pool, created/destroyed per task


class Agent:
    """薄兼容壳——委托给 AgentConfig + run_agent。"""

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
        agent_dir_path = agent_dir or f"agents/{id}"  # fallback — callers should pass explicit agent_dir
        config = load_agent_config(
            agent_dir_path,
            base_tools=tools,
            is_kb_agent=(id == "kb-agent"),
        )

        self.config = AgentConfig(
            id=id,
            name=name,
            role=role.value,
            system_prompt=system_prompt or config.system_prompt,
            tools=config.tools,
            agent_dir=agent_dir_path,
        )
        self.id = id
        self.name = name
        self.role = role
        self.page = ""
        self._llm = llm
        self._agent_dir = agent_dir_path

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
            self.config,
            self._llm,
            message,
            session=session,
            session_id=session_id,
            on_text=on_text,
            on_tool=on_tool,
            on_reasoning=on_reasoning,
            max_iterations=max_iterations,
        )

    def get_tools(self):
        return self.config.tools

    async def init(self):
        pass
