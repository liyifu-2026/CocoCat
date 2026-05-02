"""ReAct agent loop (nanobot AgentRunner + claw-code ConversationRuntime pattern)."""
import json
import os
from datetime import datetime
from llm import LLMClient
from tools import ToolRegistry, create_default_registry
from context import build_system_prompt, build_tool_descriptions, load_agent_memory


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

    def run(self, prompt: str) -> dict:
        """Execute a task prompt and return the result."""
        tool_defs = self.tools.get_definitions()
        tool_desc = build_tool_descriptions(tool_defs)
        agent_memory = load_agent_memory(self.agent_id)

        system_prompt = build_system_prompt(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            tool_descriptions=tool_desc,
            workspace=self.workspace,
            scene_name=self.scene_name,
            scene_context=self.scene_context,
            env_skills=self.scene_skills,
            agent_memory=agent_memory,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        iteration = 0
        final_content = ""

        while iteration < self.max_iterations:
            iteration += 1

            response = self.llm.chat(
                messages=messages,
                tools=tool_defs if tool_defs else None,
            )

            content = response.get("content", "") or ""
            tool_calls = response.get("tool_calls", []) or []
            reasoning = response.get("reasoning_content")

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

                for tc in tool_calls:
                    result = self.tools.execute(tc["name"], tc.get("arguments", {}))
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
