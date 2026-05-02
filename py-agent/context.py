"""System prompt builder (nanobot ContextBuilder pattern)."""
import os


SYSTEM_PROMPT_TEMPLATE = """You are {agent_name}, a capable AI agent in the CocoCat multi-agent team.

## Identity
- Name: {agent_name}
- ID: {agent_id}

## Capabilities
You have access to the following tools:
{tool_descriptions}

## Guidelines
1. You can use tools to read/write files, execute commands, and search the workspace.
2. When you need to delegate a subtask, use the sub_agent tool to spawn a child agent.
3. Think step by step before using tools.
4. When you have completed the task, provide a clear summary of what was done.
5. You work in the directory: {workspace}

## Communication
- You receive tasks via your team and report results back.
- Be concise but thorough in your responses.
"""


def build_system_prompt(
    agent_id: str = "unknown",
    agent_name: str = "Agent",
    tool_descriptions: str = "",
    workspace: str = "",
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        agent_name=agent_name,
        tool_descriptions=tool_descriptions,
        workspace=workspace or os.getcwd(),
    )


def build_tool_descriptions(tools: list[dict]) -> str:
    """Build a human-readable tool list from OpenAI-style tool definitions."""
    lines = []
    for t in tools:
        name = t["function"]["name"]
        desc = t["function"]["description"]
        params = t["function"]["parameters"]
        required = params.get("required", [])
        props = params.get("properties", {})
        param_lines = []
        for pname, pinfo in props.items():
            req = "required" if pname in required else "optional"
            param_lines.append(f"    {pname} ({req}): {pinfo.get('description', '')}")
        param_str = "\n" + "\n".join(param_lines) if param_lines else ""
        lines.append(f"- {name}: {desc}{param_str}")
    return "\n".join(lines)
