"""ReAct agent loop (nanobot AgentRunner + claw-code ConversationRuntime pattern)."""
import json
from llm import LLMClient
from tools import ToolRegistry, create_default_registry
from context import build_system_prompt, build_tool_descriptions


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

        system_prompt = build_system_prompt(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            tool_descriptions=tool_desc,
            workspace=self.workspace,
            scene_name=self.scene_name,
            scene_context=self.scene_context,
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

        return {
            "content": final_content,
            "iterations": iteration,
        }
