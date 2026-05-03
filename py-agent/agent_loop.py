"""ReAct agent loop (nanobot AgentRunner + claw-code ConversationRuntime pattern)."""
import json
import os
from datetime import datetime
from llm import LLMClient
from tools import ToolRegistry, create_default_registry, PermissionMode
from context import build_system_prompt, build_tool_descriptions, load_agent_memory, load_agent_skills
import tiktoken


def append_history(agent_id: str, prompt: str, response: str, iterations: int):
    """Append a task result to the agent's history.jsonl (nanobot pattern)."""
    if not agent_id or agent_id == "unknown":
        return
    history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", agent_id, "memory")
    history_path = os.path.join(history_dir, "history.jsonl")
    os.makedirs(history_dir, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt[:200],
        "response_summary": response[:200],
        "iterations": iterations,
    }
    try:
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def auto_dream(agent_id: str, agent_name: str, llm) -> None:
    """Auto-trigger Dream after every 3 unprocessed entries."""
    from dream import get_unprocessed_history, run_dream
    unprocessed, _ = get_unprocessed_history(agent_id)
    if len(unprocessed) >= 3:
        try:
            run_dream(agent_id, agent_name, llm_client=llm)
        except Exception:
            pass


import re


def _microcompact_tool_results(messages: list[dict], max_tool_chars: int = 2000) -> list[dict]:
    """Truncate verbose tool results to prevent context bloat (nanobot pattern)."""
    result = []
    for msg in messages:
        if msg.get("role") == "tool" and isinstance(msg.get("content"), str):
            content = msg["content"]
            if len(content) > max_tool_chars:
                msg = dict(msg)
                msg["content"] = content[:max_tool_chars] + f"\n...[truncated {len(content) - max_tool_chars} chars]"
        result.append(msg)
    return result


_enc = None
def _get_encoder():
    global _enc
    if _enc is None:
        try:
            _enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _enc = None
    return _enc

def estimate_tokens(text: str) -> int:
    enc = _get_encoder()
    if enc:
        return len(enc.encode(text))
    return len(text) // 4  # fallback


def estimate_messages_tokens(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        text = json.dumps(msg, ensure_ascii=False)
        total += estimate_tokens(text)
    return total


def _snip_history(messages: list[dict], budget: int = 8000) -> list[dict]:
    current = estimate_messages_tokens(messages)
    if current <= budget:
        return messages
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    if len(non_system) <= 2:
        return messages
    keep = non_system[-2:]
    to_snip = non_system[:-2]
    summary = {"role": "system", "content": f"[{len(to_snip)} previous messages snipped for token budget]"}
    result = system_msgs + [summary] + keep
    if estimate_messages_tokens(result) > budget:
        result = system_msgs + [{"role": "system", "content": "[Earlier conversation trimmed]"}, non_system[-1]]
    return result


CONSOLIDATION_PROMPT = """Summarize the following conversation turn in 1-2 sentences. Focus on what was asked, what tool was used, and what result was obtained.

## Content
{content}

## Summary
"""


def consolidate(messages: list[dict], llm, budget: int = 8000) -> list[dict]:
    """Upgraded consolidator: boundary-aware, multi-round, fallback."""
    current = estimate_messages_tokens(messages)
    if current <= budget:
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) < 4:
        return messages

    split = max(1, len(non_system) // 2)
    while split > 0 and split <= len(non_system):
        if split > 1:
            prev = non_system[split - 2]
            if prev.get("role") == "assistant" and "tool_calls" in prev:
                break
        if non_system[split - 1].get("role") == "tool":
            split -= 1
        else:
            break

    to_consolidate = non_system[:split]
    keep = non_system[split:]

    content_parts = []
    for m in to_consolidate:
        role = m.get("role", "?")
        text = str(m.get("content", ""))[:500]
        if text:
            content_parts.append(f"[{role}] {text}")

    if not content_parts:
        result = system_msgs + keep
        return result if estimate_messages_tokens(result) <= budget * 1.5 else system_msgs + keep[-2:]

    content = "\n\n".join(content_parts)
    prompt = CONSOLIDATION_PROMPT.format(content=content)

    summary = ""
    try:
        response = llm.chat(messages=[{"role": "user", "content": prompt}], max_tokens=256, temperature=0.3)
        summary = (response.get("content") or "").strip()
    except Exception:
        pass

    if not summary:
        summary = f"[Consolidated {len(to_consolidate)} messages: {content[:200]}...]"

    summary_msg = {"role": "system", "content": f"[Consolidated]\n{summary}"}
    result = system_msgs + [summary_msg] + keep

    if estimate_messages_tokens(result) > budget:
        return consolidate(result, llm, budget)

    return result


class AgentLoop:
    """Main agent execution loop.

    Pattern: receives a prompt -> ReAct loop (LLM call -> tool execution -> repeat) -> return result.
    Modeled after nanobot's AgentRunner.run() and claw-code's ConversationRuntime.run_turn().
    """

    def __init__(
        self,
        agent_id: str = "unknown",
        agent_name: str = "Agent",
        tools: ToolRegistry | None = None,
        llm: LLMClient | None = None,
        max_iterations: int = 20,
        workspace: str = "",
        scene_name: str = "default",
        scene_context: str = "",
        scene_skills: str = "",
        permission_mode: PermissionMode = PermissionMode.FULL_ACCESS,
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.tools = tools or create_default_registry()
        self.llm = llm or LLMClient()
        self.max_iterations = max_iterations
        self.workspace = workspace
        self.scene_name = scene_name
        self.scene_context = scene_context
        self.scene_skills = scene_skills
        self.permission_mode = permission_mode

    def _build_system_prompt(self):
        from context import build_system_prompt, build_tool_descriptions, load_agent_memory
        tool_defs = self.tools.get_definitions()
        tool_desc = build_tool_descriptions(tool_defs)
        agent_memory = load_agent_memory(self.agent_id)
        return build_system_prompt(
            agent_id=self.agent_id, agent_name=self.agent_name,
            tool_descriptions=tool_desc, workspace=self.workspace,
            scene_name=self.scene_name, scene_context=self.scene_context,
            agent_memory=agent_memory, agent_skills="", env_skills=self.scene_skills,
        )

    def run(self, prompt: str) -> dict:
        """Execute a task prompt and return the result."""
        tool_defs = self.tools.get_definitions()
        tool_desc = build_tool_descriptions(tool_defs)
        agent_memory = load_agent_memory(self.agent_id)
        agent_skills = load_agent_skills(self.agent_id)

        system_prompt = build_system_prompt(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            tool_descriptions=tool_desc,
            workspace=self.workspace,
            scene_name=self.scene_name,
            scene_context=self.scene_context,
            agent_memory=agent_memory,
            agent_skills=agent_skills,
            env_skills=self.scene_skills,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        iteration = 0
        final_content = ""

        while iteration < self.max_iterations:
            iteration += 1

            if iteration > 1:
                messages = consolidate(messages, self.llm, budget=8000)
                messages = _snip_history(messages, budget=8000)
                messages = _microcompact_tool_results(messages)

            content = ""
            tool_calls = []
            reasoning = None
            response = None
            for retry in range(3):
                response = self.llm.chat(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                )
                content = response.get("content", "") or ""
                tool_calls = response.get("tool_calls", []) or []
                reasoning = response.get("reasoning_content")
                if content.strip() or tool_calls:
                    break

            if response and response.get("finish_reason") == "length" and content.strip():
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "Please continue from where you left off."})
                response = self.llm.chat(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                )
                content += (response.get("content", "") or "")

            if tool_calls:
                assistant_msg = {"role": "assistant", "content": content}
                if reasoning:
                    assistant_msg["reasoning_content"] = reasoning
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False),
                        },
                    }
                    for tc in tool_calls
                ]
                messages.append(assistant_msg)

                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
                    futures = {}
                    for tc in tool_calls:
                        f = executor.submit(self.tools.execute, tc["name"], tc.get("arguments", {}), self.permission_mode)
                        futures[f] = tc
                    for f in as_completed(futures):
                        tc = futures[f]
                        try:
                            result = f.result(timeout=60)
                        except Exception as e:
                            result = f"Tool error: {e}"
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result,
                        })

                continue

            final_content = content
            assistant_msg = {"role": "assistant", "content": content}
            if reasoning:
                assistant_msg["reasoning_content"] = reasoning
            messages.append(assistant_msg)
            break

        append_history(self.agent_id, prompt, final_content, iteration)
        auto_dream(self.agent_id, self.agent_name, self.llm)

        return {
            "content": final_content,
            "iterations": iteration,
        }
