"""ReAct agent loop (nanobot AgentRunner + claw-code ConversationRuntime pattern)."""
import json
import os
from datetime import datetime
import time as _time
from providers import make_provider
from tools import ToolRegistry, create_default_registry, PermissionMode
from plugin_hooks import HookRegistry
from context import build_system_prompt, build_tool_descriptions, load_agent_skills, load_agent_profile, load_user_profile
from dream import run_dream as auto_dream

_enc = None


def _get_encoder():
    global _enc
    if _enc is None:
        try:
            import tiktoken
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


def _snip_history(messages: list[dict], budget: int = 131072) -> list[dict]:
    current = estimate_messages_tokens(messages)
    if current <= budget:
        return messages
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    if len(non_system) <= 2:
        return messages
    keep = non_system[-4:]
    to_snip = non_system[:-4]
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


def append_history(agent_id: str, prompt: str, response_summary: str, iterations: int):
    import json, os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hist_dir = os.path.join(base, "agents", agent_id, "memory")
    os.makedirs(hist_dir, exist_ok=True)
    hist_path = os.path.join(hist_dir, "history.jsonl")
    entry = {
        "prompt": prompt[:500],
        "response_summary": response_summary[:500],
        "iterations": iterations,
        "timestamp": datetime.now().isoformat(),
    }
    with open(hist_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


_USAGE_LOG_PATH: str | None = None


def _get_usage_log_path() -> str:
    global _USAGE_LOG_PATH
    if _USAGE_LOG_PATH is None:
        _USAGE_LOG_PATH = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "agents", "_usage.jsonl",
        )
    return _USAGE_LOG_PATH


def _log_usage(agent_id: str, prompt: str, usage: dict, iterations: int):
    import json as _json
    if not usage.get("input", 0) and not usage.get("output", 0):
        return
    entry = {
        "timestamp": datetime.now().isoformat(),
        "agent_id": agent_id,
        "input_tokens": usage.get("input", 0),
        "output_tokens": usage.get("output", 0),
        "total_tokens": usage.get("input", 0) + usage.get("output", 0),
        "iterations": iterations,
    }
    try:
        log_path = _get_usage_log_path()
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


MAX_DEPTH = 3


def _microcompact_tool_results(messages: list[dict], max_tool_chars: int = 16000) -> list[dict]:
    result = []
    for msg in messages:
        if msg.get("role") == "tool" and isinstance(msg.get("content"), str):
            content = msg["content"]
            if len(content) > max_tool_chars:
                msg = dict(msg)
                msg["content"] = content[:max_tool_chars] + f"\n...[truncated {len(content) - max_tool_chars} chars]"
        result.append(msg)
    return result


def consolidate(messages: list[dict], llm, budget: int = 131072, depth: int = 0) -> list[dict]:
    """Upgraded consolidator: boundary-aware, multi-round, fallback."""
    if depth >= MAX_DEPTH:
        return messages
    current = estimate_messages_tokens(messages)
    if current <= budget:
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) < 4:
        return messages

    # Find a safe split at a round boundary near the midpoint
    target = max(1, len(non_system) // 2)
    split = target
    while split > 0:
        msg = non_system[split - 1]
        if msg.get("role") == "tool":
            split -= 1
        elif msg.get("role") == "assistant" and "tool_calls" in msg:
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
        response = llm.chat_with_retry(messages=[{"role": "user", "content": prompt}], max_tokens=256, temperature=0.3, retry_mode="persistent")
        summary = (response.get("content") or "").strip()
    except Exception:
        pass

    if not summary:
        summary = f"[Consolidated {len(to_consolidate)} messages: {content[:200]}...]"

    summary_msg = {"role": "system", "content": f"[Consolidated]\n{summary}"}
    result = system_msgs + [summary_msg] + keep

    if estimate_messages_tokens(result) > budget:
        return consolidate(result, llm, budget, depth + 1)

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
        llm = None,
        max_iterations: int = 20,
        workspace: str = "",
        scene_name: str = "default",
        scene_context: str = "",
        scene_skills: str = "",
        permission_mode: PermissionMode = PermissionMode.FULL_ACCESS,
        user_id: str = "",
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.tools = tools or create_default_registry()
        self.llm = llm or make_provider()
        self.max_iterations = max_iterations
        self.workspace = workspace
        self.scene_name = scene_name
        self.scene_context = scene_context
        self.scene_skills = scene_skills
        self.reasoning_effort = ""
        self.permission_mode = permission_mode
        self.user_id = user_id
        self.hook_registry = HookRegistry()
        try:
            from plugin_manager import discover_plugins, load_plugin_hooks
            for pname, manifest in discover_plugins().items():
                hooks = load_plugin_hooks(manifest)
                self.hook_registry.register_all(hooks)
        except Exception:
            pass

        # Cache for context that doesn't change between requests
        self._profile_cache = None
        self._skills_cache = None
        self._kbs_cache = None
        self._knowledge_cache = None

    def _invalidate_cache(self):
        self._profile_cache = None
        self._skills_cache = None
        self._kbs_cache = None
        self._knowledge_cache = None

    def update_scene(self, scene_id: str, context: str = "", skills: str = ""):
        """Update scene context at runtime (called by AgentHandle.assign_to_scene)."""
        self.scene_name = scene_id
        self.scene_context = context
        self.scene_skills = skills
        self._invalidate_cache()
        import logging
        logging.getLogger("cococat.agent_loop").info(f"Scene updated: {scene_id}")

    def _build_system_prompt(self, user_id: str = "", knowledge_overview: str = None, agent_skills: str = None):
        from context import build_system_prompt, build_tool_descriptions, load_agent_memory, load_agent_profile, load_user_profile, load_mounted_kbs, load_knowledge_overview, load_agent_skills
        tool_defs = self.tools.get_definitions()
        tool_desc = build_tool_descriptions(tool_defs)
        agent_memory = load_agent_memory(self.agent_id)
        if self._profile_cache is None:
            self._profile_cache = load_agent_profile(self.agent_id)
        agent_profile = self._profile_cache
        uid = user_id or self.user_id
        user_profile = load_user_profile(self.agent_id, uid)
        user_conversation = ""
        if self._kbs_cache is None:
            self._kbs_cache = load_mounted_kbs(self.scene_name)
        mounted_kbs = self._kbs_cache
        scene_context = self.scene_context
        if mounted_kbs:
            scene_context += f"\n## Available Knowledge Bases\nMounted KBs: {', '.join(mounted_kbs)}\nRead wiki pages via read_file — see knowledge_overview for the index."
        if knowledge_overview is None:
            if self._knowledge_cache is None:
                self._knowledge_cache = load_knowledge_overview(self.scene_name)
            knowledge_overview = self._knowledge_cache
        if agent_skills is None:
            if self._skills_cache is None:
                self._skills_cache = load_agent_skills(self.agent_id)
            agent_skills = self._skills_cache
        return build_system_prompt(
            agent_id=self.agent_id, agent_name=self.agent_name,
            tool_descriptions=tool_desc, workspace=self.workspace,
            scene_name=self.scene_name, scene_context=scene_context,
            agent_memory=agent_memory, agent_skills=agent_skills, env_skills=self.scene_skills,
            profile=agent_profile, user_profile=user_profile, user_conversation=user_conversation,
            knowledge_overview=knowledge_overview,
        )

    def run(self, prompt: str, user_id: str = "", history: list | None = None, on_progress=None, on_tool=None, on_reasoning=None) -> dict:
        """Execute a task prompt and return the result.

        Callbacks (nanobot pattern):
          on_progress(msg): status string updates
          on_tool(name, args, status, result): tool lifecycle events
          on_reasoning(content): LLM reasoning/thinking tokens
        """
        uid = user_id or self.user_id
        try:
            from agent_status import report as _report_status
            _report_status(self.agent_id, "busy", prompt[:100])
        except Exception:
            pass
        if on_progress:
            on_progress("Building system prompt...")
        system_prompt = self._build_system_prompt(user_id=uid)
        tool_defs = self.tools.get_definitions()

        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if history:
            for h in history:
                if isinstance(h, dict) and h.get("role") and h.get("content"):
                    messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": prompt})

        iteration = 0
        final_content = ""
        total_usage = {"input": 0, "output": 0}

        while iteration < self.max_iterations:
            iteration += 1
            if on_progress:
                on_progress(f"Iteration {iteration}/{self.max_iterations}")

            if iteration > 1:
                current_tokens = estimate_messages_tokens(messages)
                budget = 131072
                if current_tokens > budget * 0.75:
                    messages = consolidate(messages, self.llm, budget=budget)
                messages = _snip_history(messages, budget=budget)
                messages = _microcompact_tool_results(messages)

            if on_progress:
                on_progress(f"Calling LLM (iteration {iteration})...")
            content = ""
            tool_calls = []
            reasoning = None
            response = None

            # Stream if no tools needed (text-only response), else use retry
            if not tool_defs and hasattr(self.llm, 'chat_stream'):
                for chunk in self.llm.chat_stream(messages=messages):
                    if chunk["type"] == "delta":
                        content += chunk["content"]
                        if on_progress:
                            on_progress(chunk["content"])
                    elif chunk["type"] == "done":
                        if chunk["content"]:
                            content = chunk["content"]
                        response = self.llm.chat(messages=messages) if not content else None
            else:
                for retry in range(3):
                    response = self.llm.chat_with_retry(
                        messages=messages,
                        tools=tool_defs if tool_defs else None,
                        retry_mode="persistent",
                    )
                    content = response.content or ""
                    tool_calls = response.tool_calls or []
                    reasoning = response.reasoning_content
                    if reasoning and on_reasoning:
                        on_reasoning(reasoning)
                    if content.strip() or tool_calls:
                        break

            if response and response.usage:
                u = response.usage
                total_usage["input"] += u.get("prompt_tokens", 0) or u.get("input_tokens", 0) or 0
                total_usage["output"] += u.get("completion_tokens", 0) or u.get("output_tokens", 0) or 0

            if response and response.finish_reason == "length" and content.strip():
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "Please continue from where you left off."})
                for _ in range(5):
                    response = self.llm.chat_with_retry(
                        messages=messages,
                        tools=tool_defs if tool_defs else None,
                        retry_mode="persistent",
                    )
                    content += (response.content or "")
                    if response.finish_reason != "length":
                        break

            if tool_calls:
                assistant_msg = {"role": "assistant", "content": content}
                if reasoning:
                    assistant_msg["reasoning_content"] = reasoning
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in tool_calls
                ]
                messages.append(assistant_msg)

                from concurrent.futures import ThreadPoolExecutor, as_completed
                tool_names = [tc.name for tc in tool_calls]
                if on_tool:
                    for tc in tool_calls:
                        on_tool(tc.name, tc.arguments, "start", "")
                with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
                    futures = {}
                    for tc in tool_calls:
                        tool_name = tc.name
                        tool_args = tc.arguments
                        allowed, reason, modified_args = self.hook_registry.run_pre_tool_call(tool_name, tool_args)
                        if not allowed:
                            result = f"Error: Tool call denied by plugin: {reason}"
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": result,
                            })
                            continue
                        f = executor.submit(self.tools.execute, tool_name, modified_args, self.permission_mode)
                        futures[f] = (tc, tool_name, modified_args)
                    for f in as_completed(futures):
                        tc, tool_name, modified_args = futures[f]
                        try:
                            result = f.result(timeout=60)
                            if on_tool:
                                on_tool(tool_name, modified_args, "done", result[:200])
                        except Exception as e:
                            result = f"Tool error: {e}"
                            if on_tool:
                                on_tool(tool_name, modified_args, "error", str(e)[:200])
                        result = self.hook_registry.run_post_tool_call(tool_name, modified_args, result)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        })

                continue

            final_content = content
            assistant_msg = {"role": "assistant", "content": content}
            if reasoning:
                assistant_msg["reasoning_content"] = reasoning
            messages.append(assistant_msg)
            break

        try:
            from agent_status import report as _report_status
            _report_status(self.agent_id, "idle", f"done in {iteration} iters")
        except Exception:
            pass
        append_history(self.agent_id, prompt, final_content, iteration)
        if uid:
            from dream import append_user_history
            from utils import user_hash as _user_hash
            append_user_history(self.agent_id, _user_hash(uid), {
                "role": "assistant", "content": final_content[:500],
                "timestamp": datetime.now().isoformat(),
            })
        auto_dream(self.agent_id, self.agent_name, self.llm)
        if total_usage.get("input", 0) or total_usage.get("output", 0):
            _log_usage(self.agent_id, prompt, total_usage, iteration)

        return {
            "content": final_content,
            "iterations": iteration,
        }
